"""
feature_engineering.py
------------------------
Transforms the cleaned dataset into a model-ready, feature-engineered
dataset. Every feature here is chosen because it maps to a business
concept an analyst would actually explain to a stakeholder -- not just
raw encodings.

Usage:
    python src/preprocessing/feature_engineering.py
"""
import pandas as pd
import numpy as np
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("FeatureEngineering")

IN_PATH = "data/cleaned/telecom_customers_cleaned.csv"
OUT_PATH = "data/processed/telecom_customers_features.csv"


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Average monthly spend (guards against divide-by-zero for new customers)
    df["AvgMonthlySpend"] = np.where(
        df["tenure"] > 0, df["TotalCharges"] / df["tenure"], df["MonthlyCharges"]
    )

    # 2. Customer age group proxy (tenure-based lifecycle stage -- dataset has no literal age)
    df["CustomerLifecycleStage"] = pd.cut(
        df["tenure"], bins=[-1, 6, 12, 24, 48, 200],
        labels=["New (0-6mo)", "Ramping (7-12mo)", "Established (13-24mo)",
                "Mature (25-48mo)", "Veteran (49mo+)"]
    )

    # 3. Contract duration in months (numeric, for correlation/model use)
    df["ContractDurationMonths"] = df["Contract"].map(
        {"Month-to-month": 1, "One year": 12, "Two year": 24}
    )

    # 4. Payment behavior flag (auto-pay vs manual -- manual payers churn more)
    df["IsAutoPay"] = df["PaymentMethod"].isin(
        ["Bank transfer (automatic)", "Credit card (automatic)"]
    ).astype(int)

    # 5. Support ticket frequency normalized by tenure (tickets per year of tenure)
    df["SupportTicketsPerTenureYear"] = np.where(
        df["tenure"] >= 12,
        df["SupportTicketsLastYear"] / (df["tenure"] / 12),
        df["SupportTicketsLastYear"]
    )

    # 6. Total add-on services subscribed (service depth / stickiness)
    addon_cols = ["OnlineSecurity", "OnlineBackup", "DeviceProtection",
                  "TechSupport", "StreamingTV", "StreamingMovies"]
    df["TotalAddOnServices"] = df[addon_cols].apply(lambda col: (col == "Yes").astype(int)).sum(axis=1)

    # 7. Has internet + no protection services (upsell / risk flag)
    df["HasInternetNoProtection"] = (
        (df["InternetService"] != "No") &
        (df["OnlineSecurity"] == "No") &
        (df["TechSupport"] == "No")
    ).astype(int)

    # 8. Customer Value Score (0-100): blends revenue, tenure, and contract commitment
    def normalize(s):
        return (s - s.min()) / (s.max() - s.min() + 1e-9)

    df["CustomerValueScore"] = (
        0.5 * normalize(df["MonthlyCharges"]) * 100
        + 0.3 * normalize(df["tenure"]) * 100
        + 0.2 * df["ContractDurationMonths"].map({1: 20, 12: 60, 24: 100})
    ).round(2)

    # 9. High-value flag (top quartile of value score)
    threshold = df["CustomerValueScore"].quantile(0.75)
    df["IsHighValueCustomer"] = (df["CustomerValueScore"] >= threshold).astype(int)

    # 10. Multi-service household (phone + internet + streaming = "sticky" customer)
    df["IsMultiServiceHousehold"] = (
        (df["PhoneService"] == "Yes") &
        (df["InternetService"] != "No") &
        ((df["StreamingTV"] == "Yes") | (df["StreamingMovies"] == "Yes"))
    ).astype(int)

    # 11. Encode target
    df["ChurnFlag"] = (df["Churn"] == "Yes").astype(int)

    logger.info(f"Feature engineering complete: {df.shape[1]} total columns")
    return df


def main():
    logger.info(f"Loading cleaned data from {IN_PATH}")
    df = pd.read_csv(IN_PATH)
    df_feat = engineer_features(df)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    df_feat.to_csv(OUT_PATH, index=False)
    logger.info(f"Feature-engineered dataset saved -> {OUT_PATH} ({len(df_feat)} rows, {df_feat.shape[1]} cols)")

    new_features = [
        "AvgMonthlySpend", "CustomerLifecycleStage", "ContractDurationMonths", "IsAutoPay",
        "SupportTicketsPerTenureYear", "TotalAddOnServices", "HasInternetNoProtection",
        "CustomerValueScore", "IsHighValueCustomer", "IsMultiServiceHousehold", "ChurnFlag"
    ]
    logger.info(f"New engineered features: {new_features}")


if __name__ == "__main__":
    main()
