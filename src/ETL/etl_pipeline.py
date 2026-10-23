"""
etl_pipeline.py
----------------
Production-style ETL pipeline for the Customer Churn Analytics platform.

EXTRACT  -> read raw CSV export (simulating a CRM/billing dump)
TRANSFORM-> clean, validate, standardize, engineer base fields
LOAD     -> write to the database layer (SQLite by default for local dev,
            PostgreSQL in production via DATABASE_URL env var)

Every step is logged to logs/etl.log AND stdout, with row counts before/after
so a run can be audited (a real analytics team will ask "how many rows did
you drop and why").

Usage:
    python src/ETL/etl_pipeline.py
    DATABASE_URL=postgresql://user:pass@host:5432/churn_db python src/ETL/etl_pipeline.py
"""
import os
import sys
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

# --------------------------------------------------------------------------
# Config (never hardcode secrets -- pull from environment with safe defaults)
# --------------------------------------------------------------------------
RAW_PATH = os.getenv("RAW_DATA_PATH", "data/raw/telecom_customers_raw.csv")
CLEANED_PATH = os.getenv("CLEANED_DATA_PATH", "data/cleaned/telecom_customers_cleaned.csv")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/churn.db")
LOG_DIR = "logs"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CLEANED_PATH), exist_ok=True)
os.makedirs("database", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "etl.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ETL")


# --------------------------------------------------------------------------
# EXTRACT
# --------------------------------------------------------------------------
def extract(path: str) -> pd.DataFrame:
    logger.info(f"EXTRACT: reading raw file from {path}")
    if not os.path.exists(path):
        logger.error(f"Raw file not found at {path}. Run generate_raw_data.py first.")
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    logger.info(f"EXTRACT: loaded {len(df):,} rows, {df.shape[1]} columns")
    return df


# --------------------------------------------------------------------------
# TRANSFORM
# --------------------------------------------------------------------------
def transform(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("TRANSFORM: starting cleaning & standardization")
    start_rows = len(df)

    # 1. Standardize column names
    df.columns = [c.strip() for c in df.columns]

    # 2. Drop exact duplicate rows
    before = len(df)
    df = df.drop_duplicates()
    logger.info(f"TRANSFORM: dropped {before - len(df)} exact duplicate rows")

    # 3. Drop duplicate customerIDs (keep first occurrence)
    before = len(df)
    df = df.drop_duplicates(subset="customerID", keep="first")
    logger.info(f"TRANSFORM: dropped {before - len(df)} duplicate customerID rows")

    # 4. Standardize Churn labels
    df["Churn"] = (
        df["Churn"].astype(str).str.strip().str.lower().map({"yes": "Yes", "no": "No"})
    )
    unmapped = df["Churn"].isna().sum()
    if unmapped:
        logger.warning(f"TRANSFORM: {unmapped} rows had unmappable Churn values -> dropped")
        df = df.dropna(subset=["Churn"])

    # 5. Standardize gender labels
    df["gender"] = df["gender"].replace({"M": "Male", "F": "Female"})

    # 6. Fix TotalCharges: strip whitespace-only strings -> NaN -> numeric
    df["TotalCharges"] = df["TotalCharges"].astype(str).str.strip().replace("", np.nan)
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")

    # 7. Impute missing numeric values with column median (documented, defensible choice)
    for col in ["TotalCharges", "MonthlyCharges"]:
        n_missing = df[col].isna().sum()
        if n_missing:
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            logger.info(f"TRANSFORM: imputed {n_missing} missing '{col}' values with median={median_val:.2f}")

    # 8. Fix impossible / negative tenure values -> treat as missing, impute with median
    invalid_tenure = (df["tenure"] < 0).sum()
    if invalid_tenure:
        df.loc[df["tenure"] < 0, "tenure"] = np.nan
        median_tenure = df["tenure"].median()
        df["tenure"] = df["tenure"].fillna(median_tenure)
        logger.info(f"TRANSFORM: fixed {invalid_tenure} negative tenure values (imputed median={median_tenure:.0f})")

    # 9. Cap outliers in MonthlyCharges using IQR method (documented business rule)
    q1, q3 = df["MonthlyCharges"].quantile([0.25, 0.75])
    iqr = q3 - q1
    upper_bound = q3 + 3 * iqr
    n_outliers = (df["MonthlyCharges"] > upper_bound).sum()
    if n_outliers:
        df.loc[df["MonthlyCharges"] > upper_bound, "MonthlyCharges"] = upper_bound
        logger.info(f"TRANSFORM: capped {n_outliers} MonthlyCharges outliers at {upper_bound:.2f} (IQR method)")

    # 10. Impute missing categorical (Partner) with mode
    if df["Partner"].isna().sum():
        n_missing = df["Partner"].isna().sum()
        mode_val = df["Partner"].mode()[0]
        df["Partner"] = df["Partner"].fillna(mode_val)
        logger.info(f"TRANSFORM: imputed {n_missing} missing 'Partner' values with mode='{mode_val}'")

    # 11. Standardize SignupDate to a single ISO format
    def parse_date(val):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(str(val).split(" ")[0] if fmt == "%Y-%m-%d" else str(val), fmt)
            except (ValueError, TypeError):
                continue
        return pd.to_datetime(val, errors="coerce")

    df["SignupDate"] = df["SignupDate"].apply(parse_date)
    n_bad_dates = df["SignupDate"].isna().sum()
    if n_bad_dates:
        logger.warning(f"TRANSFORM: {n_bad_dates} SignupDate values could not be parsed")

    # 12. Data validation assertions (fail loudly if something is structurally wrong)
    assert df["customerID"].is_unique, "customerID is not unique after cleaning!"
    assert df["Churn"].isin(["Yes", "No"]).all(), "Churn has values outside Yes/No!"
    assert (df["MonthlyCharges"] >= 0).all(), "Negative MonthlyCharges present!"
    assert (df["tenure"] >= 0).all(), "Negative tenure present!"

    logger.info(f"TRANSFORM: complete. {start_rows} -> {len(df)} rows ({start_rows - len(df)} removed)")
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# LOAD
# --------------------------------------------------------------------------
def load(df: pd.DataFrame, db_url: str, csv_out: str):
    logger.info(f"LOAD: writing cleaned CSV -> {csv_out}")
    df.to_csv(csv_out, index=False)

    logger.info(f"LOAD: writing to database -> {db_url.split('@')[-1] if '@' in db_url else db_url}")
    engine = create_engine(db_url)
    df.to_sql("customers", engine, if_exists="replace", index=False)
    logger.info(f"LOAD: wrote {len(df):,} rows to 'customers' table")
    engine.dispose()


def generate_data_quality_report(raw_df: pd.DataFrame, clean_df: pd.DataFrame, out_path: str):
    lines = [
        "# Data Quality Report",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Volume",
        f"- Raw rows: {len(raw_df):,}",
        f"- Cleaned rows: {len(clean_df):,}",
        f"- Rows removed: {len(raw_df) - len(clean_df):,} ({(1 - len(clean_df)/len(raw_df))*100:.2f}%)",
        "",
        "## Missing Values (raw)",
    ]
    miss = raw_df.isnull().sum()
    miss = miss[miss > 0]
    for col, cnt in miss.items():
        lines.append(f"- {col}: {cnt} ({cnt/len(raw_df)*100:.2f}%)")
    lines += [
        "",
        "## Missing Values (cleaned)",
        f"- Total remaining nulls: {clean_df.isnull().sum().sum()}",
        "",
        "## Duplicates",
        f"- Duplicate customerIDs in raw: {raw_df['customerID'].duplicated().sum()}",
        f"- Duplicate customerIDs in cleaned: {clean_df['customerID'].duplicated().sum()}",
        "",
        "## Churn class balance (cleaned)",
        clean_df["Churn"].value_counts(normalize=True).mul(100).round(2).to_string(),
    ]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    logger.info(f"Data quality report written -> {out_path}")


def main():
    logger.info("=" * 70)
    logger.info("ETL PIPELINE START")
    logger.info("=" * 70)
    raw_df = extract(RAW_PATH)
    clean_df = transform(raw_df.copy())
    load(clean_df, DATABASE_URL, CLEANED_PATH)
    generate_data_quality_report(raw_df, clean_df, "reports/data_quality_report.md")
    logger.info("ETL PIPELINE COMPLETE")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
