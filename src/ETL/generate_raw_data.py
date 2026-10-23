"""
generate_raw_data.py
---------------------
Simulates a realistic RAW telecom customer export, the kind you'd receive
from an operational CRM/billing system before any cleaning.

Intentionally injects the kinds of real-world data quality problems an
analyst has to handle:
  - Missing values (MCAR + MNAR patterns)
  - Duplicate customer records
  - Inconsistent categorical labels ("Yes"/"yes"/"Y")
  - Outliers in numeric fields
  - Incorrect data types stored as strings
  - Negative / impossible values
  - Mixed date formats

This is NOT the dataset the model trains on -- it's the RAW layer.
Phase 4 (cleaning) turns this into the CLEANED layer.

Usage:
    python src/ETL/generate_raw_data.py --n_customers 12000 --seed 42
"""
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import os

def generate(n_customers: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    customer_ids = [f"CUST-{100000+i}" for i in range(n_customers)]

    genders = rng.choice(["Male", "Female"], size=n_customers, p=[0.505, 0.495])
    senior_citizen = rng.choice([0, 1], size=n_customers, p=[0.84, 0.16])
    partner = rng.choice(["Yes", "No"], size=n_customers, p=[0.48, 0.52])
    dependents = rng.choice(["Yes", "No"], size=n_customers, p=[0.30, 0.70])

    tenure_months = rng.integers(0, 73, size=n_customers)

    phone_service = rng.choice(["Yes", "No"], size=n_customers, p=[0.90, 0.10])
    multiple_lines = np.where(
        phone_service == "No", "No phone service",
        rng.choice(["Yes", "No"], size=n_customers, p=[0.42, 0.58])
    )

    internet_service = rng.choice(["DSL", "Fiber optic", "No"], size=n_customers, p=[0.34, 0.44, 0.22])

    def internet_dependent_feature(p_yes=0.5):
        vals = rng.choice(["Yes", "No"], size=n_customers, p=[p_yes, 1 - p_yes])
        return np.where(internet_service == "No", "No internet service", vals)

    online_security = internet_dependent_feature(0.35)
    online_backup = internet_dependent_feature(0.40)
    device_protection = internet_dependent_feature(0.40)
    tech_support = internet_dependent_feature(0.35)
    streaming_tv = internet_dependent_feature(0.45)
    streaming_movies = internet_dependent_feature(0.45)

    contract = rng.choice(
        ["Month-to-month", "One year", "Two year"], size=n_customers, p=[0.55, 0.24, 0.21]
    )
    paperless_billing = rng.choice(["Yes", "No"], size=n_customers, p=[0.59, 0.41])
    payment_method = rng.choice(
        ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"],
        size=n_customers, p=[0.34, 0.23, 0.22, 0.21]
    )

    # Monthly charges depend on services (so EDA/correlations are meaningful)
    base = 18.0
    base += np.where(internet_service == "DSL", 24.0, 0)
    base += np.where(internet_service == "Fiber optic", 45.0, 0)
    base += np.where(phone_service == "Yes", 8.0, 0)
    for feat in [online_security, online_backup, device_protection, tech_support, streaming_tv, streaming_movies]:
        base += np.where(feat == "Yes", 6.5, 0)
    noise = rng.normal(0, 6, size=n_customers)
    monthly_charges = np.round(base + noise, 2)
    monthly_charges = np.clip(monthly_charges, 18, None)

    total_charges = np.round(monthly_charges * tenure_months + rng.normal(0, 15, size=n_customers), 2)
    total_charges = np.clip(total_charges, 0, None)

    support_tickets_last_year = rng.poisson(1.4, size=n_customers)

    # ---- Churn generation (logical, not random) so EDA/ML find real signal ----
    churn_score = (
        -0.03 * tenure_months
        + 0.02 * monthly_charges
        + np.where(contract == "Month-to-month", 1.4, np.where(contract == "One year", 0.2, -1.2))
        + np.where(payment_method == "Electronic check", 0.6, 0)
        + np.where(internet_service == "Fiber optic", 0.5, 0)
        + np.where(tech_support == "No", 0.35, 0)
        + 0.12 * support_tickets_last_year
        + np.where(senior_citizen == 1, 0.25, 0)
        + rng.normal(0, 1.1, size=n_customers)
    )
    churn_prob = 1 / (1 + np.exp(-(churn_score - 1.0)))
    churn = (rng.random(n_customers) < churn_prob).astype(int)
    churn_label = np.where(churn == 1, "Yes", "No")

    signup_start = datetime(2019, 1, 1)
    signup_date = [signup_start + timedelta(days=int(rng.integers(0, 2000))) for _ in range(n_customers)]

    region = rng.choice(
        ["North", "South", "East", "West", "Central"], size=n_customers, p=[0.22, 0.21, 0.19, 0.20, 0.18]
    )

    df = pd.DataFrame({
        "customerID": customer_ids,
        "gender": genders,
        "SeniorCitizen": senior_citizen,
        "Partner": partner,
        "Dependents": dependents,
        "tenure": tenure_months,
        "PhoneService": phone_service,
        "MultipleLines": multiple_lines,
        "InternetService": internet_service,
        "OnlineSecurity": online_security,
        "OnlineBackup": online_backup,
        "DeviceProtection": device_protection,
        "TechSupport": tech_support,
        "StreamingTV": streaming_tv,
        "StreamingMovies": streaming_movies,
        "Contract": contract,
        "PaperlessBilling": paperless_billing,
        "PaymentMethod": payment_method,
        "MonthlyCharges": monthly_charges,
        "TotalCharges": total_charges,
        "SupportTicketsLastYear": support_tickets_last_year,
        "SignupDate": signup_date,
        "Region": region,
        "Churn": churn_label,
    })

    # ---------------- Inject realistic data quality problems ----------------

    # 1. Missing values (MCAR in TotalCharges, MNAR in TechSupport-adjacent cols)
    missing_idx = rng.choice(df.index, size=int(0.02 * n_customers), replace=False)
    df.loc[missing_idx, "TotalCharges"] = np.nan

    missing_idx2 = rng.choice(df.index, size=int(0.015 * n_customers), replace=False)
    df.loc[missing_idx2, "MonthlyCharges"] = np.nan

    missing_idx3 = rng.choice(df.index, size=int(0.03 * n_customers), replace=False)
    df.loc[missing_idx3, "Partner"] = np.nan

    # 2. Inconsistent categorical casing / labels (real CRMs are messy)
    inconsistent_idx = rng.choice(df.index, size=int(0.05 * n_customers), replace=False)
    df.loc[inconsistent_idx, "Churn"] = df.loc[inconsistent_idx, "Churn"].map(
        {"Yes": random.choice(["yes", "Y", "YES "]), "No": random.choice(["no", "N", "NO "])}
    )

    gender_messy_idx = rng.choice(df.index, size=int(0.03 * n_customers), replace=False)
    df.loc[gender_messy_idx, "gender"] = df.loc[gender_messy_idx, "gender"].map(
        {"Male": "M", "Female": "F"}
    )

    # 3. Duplicate rows (exact + near-duplicate customerID with different casing)
    dup_sample = df.sample(n=int(0.015 * n_customers), random_state=seed)
    df = pd.concat([df, dup_sample], ignore_index=True)

    # 4. Outliers in MonthlyCharges / tenure
    outlier_idx = rng.choice(df.index, size=15, replace=False)
    df.loc[outlier_idx, "MonthlyCharges"] = df.loc[outlier_idx, "MonthlyCharges"] * rng.uniform(3, 5)

    tenure_outlier_idx = rng.choice(df.index, size=8, replace=False)
    df.loc[tenure_outlier_idx, "tenure"] = -1  # impossible negative tenure (data entry error)

    # 5. TotalCharges stored as string with stray spaces (classic Telco-churn-dataset bug)
    space_idx = rng.choice(df.index, size=int(0.01 * len(df)), replace=False)
    df["TotalCharges"] = df["TotalCharges"].astype(object)
    df.loc[space_idx, "TotalCharges"] = " "

    # 6. Mixed date formats in SignupDate
    df["SignupDate"] = df["SignupDate"].astype(object)
    alt_fmt_idx = rng.choice(df.index, size=int(0.1 * len(df)), replace=False)
    for i in alt_fmt_idx:
        d = df.loc[i, "SignupDate"]
        if isinstance(d, datetime):
            df.loc[i, "SignupDate"] = d.strftime("%d/%m/%Y")

    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_customers", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="data/raw/telecom_customers_raw.csv")
    args = parser.parse_args()

    df = generate(args.n_customers, args.seed)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Generated {len(df)} raw rows -> {args.out}")
    print(f"Missing values total: {df.isnull().sum().sum()}")
    print(f"Duplicate customerIDs: {df['customerID'].duplicated().sum()}")


if __name__ == "__main__":
    main()
