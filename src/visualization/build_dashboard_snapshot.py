"""
build_dashboard_snapshot.py
------------------------------
Regenerates dashboard/dashboard_data.json from the latest segmented dataset,
so the static web dashboard reflects the most recent pipeline run.

Usage:
    python src/visualization/build_dashboard_snapshot.py
"""
import pandas as pd
import numpy as np
import json
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("DashboardSnapshot")

DATA_PATH = "data/processed/telecom_customers_segmented.csv"
OUT_PATH = "dashboard/dashboard_data.json"


def build_payload(df: pd.DataFrame) -> dict:
    payload = {
        "kpis": {
            "total_customers": int(len(df)),
            "churn_rate_pct": round((df["Churn"] == "Yes").mean() * 100, 2),
            "total_mrr": round(df["MonthlyCharges"].sum(), 2),
            "arpu": round(df["MonthlyCharges"].mean(), 2),
            "at_risk_mrr": round(df.loc[df["Churn"] == "Yes", "MonthlyCharges"].sum(), 2),
            "avg_tenure": round(df["tenure"].mean(), 1),
        },
        "churn_by_contract": df.groupby("Contract")["Churn"].apply(lambda x: round((x == "Yes").mean() * 100, 2)).to_dict(),
        "customers_by_contract": df["Contract"].value_counts().to_dict(),
        "churn_by_region": df.groupby("Region")["Churn"].apply(lambda x: round((x == "Yes").mean() * 100, 2)).to_dict(),
        "mrr_by_region": df.groupby("Region")["MonthlyCharges"].sum().round(2).to_dict(),
        "customers_by_region": df["Region"].value_counts().to_dict(),
        "churn_by_payment": df.groupby("PaymentMethod")["Churn"].apply(lambda x: round((x == "Yes").mean() * 100, 2)).to_dict(),
        "internet_service_mix": df["InternetService"].value_counts().to_dict(),
        "persona_distribution": df["Persona"].value_counts().to_dict(),
        "persona_churn": df.groupby("Persona")["Churn"].apply(lambda x: round((x == "Yes").mean() * 100, 2)).to_dict(),
        "persona_avg_charges": df.groupby("Persona")["MonthlyCharges"].mean().round(2).to_dict(),
        "gender_split": df["gender"].value_counts().to_dict(),
        "senior_citizen_churn": df.groupby("SeniorCitizen")["Churn"].apply(lambda x: round((x == "Yes").mean() * 100, 2)).to_dict(),
    }

    tenure_bins = pd.cut(df["tenure"], bins=[-1, 12, 24, 36, 48, 60, 72],
                          labels=["0-12", "13-24", "25-36", "37-48", "49-60", "61-72"])
    payload["tenure_distribution"] = df.groupby(tenure_bins, observed=True).size().to_dict()
    payload["churn_by_tenure_bucket"] = df.groupby(tenure_bins, observed=True)["Churn"].apply(
        lambda x: round((x == "Yes").mean() * 100, 2)
    ).to_dict()

    hist_counts, hist_edges = np.histogram(df["MonthlyCharges"], bins=10)
    payload["monthly_charges_hist"] = {"counts": hist_counts.tolist(), "edges": [round(e, 1) for e in hist_edges.tolist()]}

    monthly = df.copy()
    monthly["SignupMonth"] = pd.to_datetime(df["SignupDate"]).dt.to_period("M").astype(str)
    trend = monthly.groupby("SignupMonth").agg(
        signups=("customerID", "count"), churned=("Churn", lambda x: (x == "Yes").sum())
    ).reset_index().sort_values("SignupMonth")
    payload["monthly_trend"] = {
        "months": trend["SignupMonth"].tolist(),
        "signups": trend["signups"].tolist(),
        "churned": trend["churned"].tolist(),
    }

    top_value = df.sort_values("CustomerValueScore", ascending=False).head(15)[
        ["customerID", "Region", "Contract", "MonthlyCharges", "tenure", "Persona", "Churn"]
    ]
    payload["top_value_customers"] = top_value.to_dict(orient="records")
    return payload


def main():
    logger.info(f"Loading segmented data from {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    payload = build_payload(df)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    logger.info(f"Dashboard snapshot written -> {OUT_PATH}")


if __name__ == "__main__":
    main()
