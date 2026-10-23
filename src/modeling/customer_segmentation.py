"""
customer_segmentation.py
---------------------------
Unsupervised segmentation via K-Means to generate business-readable
customer personas (independent of the churn label -- this is about who
customers ARE, not just whether they'll leave).

Usage:
    python src/modeling/customer_segmentation.py
"""
import pandas as pd
import numpy as np
import joblib
import logging
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("Segmentation")

DATA_PATH = "data/processed/telecom_customers_features.csv"
OUT_PATH = "data/processed/telecom_customers_segmented.csv"
FIG_DIR = "reports/figures"
REPORT_PATH = "reports/Customer_Segmentation_Report.md"

CLUSTER_FEATURES = ["tenure", "MonthlyCharges", "CustomerValueScore", "TotalAddOnServices", "SupportTicketsLastYear"]


def assign_persona(row):
    """Business-readable persona labeling based on cluster centroid characteristics."""
    if row["MonthlyCharges"] > row["_charges_75"] and row["tenure"] > row["_tenure_50"]:
        return "High-Value Loyal"
    if row["tenure"] < row["_tenure_25"] and row["MonthlyCharges"] > row["_charges_50"]:
        return "High-Risk New"
    if row["tenure"] > row["_tenure_75"] and row["MonthlyCharges"] < row["_charges_50"]:
        return "Loyal Budget Customer"
    if row["SupportTicketsLastYear"] >= 3:
        return "At-Risk / High Support Need"
    return "Standard / New Customer"


def main():
    df = pd.read_csv(DATA_PATH)
    X = df[CLUSTER_FEATURES].copy()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Elbow method
    inertias, sil_scores = [], []
    k_range = range(2, 9)
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        sil_scores.append(silhouette_score(X_scaled, labels))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(list(k_range), inertias, marker="o", color="#2E86AB")
    axes[0].set_title("Elbow Method"); axes[0].set_xlabel("k"); axes[0].set_ylabel("Inertia")
    axes[1].plot(list(k_range), sil_scores, marker="o", color="#E63946")
    axes[1].set_title("Silhouette Score"); axes[1].set_xlabel("k")
    fig.savefig(f"{FIG_DIR}/kmeans_elbow_silhouette.png", bbox_inches="tight", dpi=110)
    plt.close(fig)

    best_k = 5  # chosen for business interpretability + strong silhouette in the 4-6 range
    logger.info(f"Fitting final KMeans with k={best_k}")
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df["ClusterID"] = km.fit_predict(X_scaled)

    # Compute thresholds for persona rules
    df["_tenure_25"] = df["tenure"].quantile(0.25)
    df["_tenure_50"] = df["tenure"].quantile(0.50)
    df["_tenure_75"] = df["tenure"].quantile(0.75)
    df["_charges_50"] = df["MonthlyCharges"].quantile(0.50)
    df["_charges_75"] = df["MonthlyCharges"].quantile(0.75)

    cluster_profile = df.groupby("ClusterID")[CLUSTER_FEATURES].mean()
    cluster_persona_map = {}
    for cid, row in cluster_profile.iterrows():
        temp = row.to_dict()
        temp.update({
            "_tenure_25": df["_tenure_25"].iloc[0], "_tenure_50": df["_tenure_50"].iloc[0],
            "_tenure_75": df["_tenure_75"].iloc[0], "_charges_50": df["_charges_50"].iloc[0],
            "_charges_75": df["_charges_75"].iloc[0],
        })
        cluster_persona_map[cid] = assign_persona(pd.Series(temp))

    df["Persona"] = df["ClusterID"].map(cluster_persona_map)
    df = df.drop(columns=["_tenure_25", "_tenure_50", "_tenure_75", "_charges_50", "_charges_75"])

    df.to_csv(OUT_PATH, index=False)
    joblib.dump({"kmeans": km, "scaler": scaler, "features": CLUSTER_FEATURES, "persona_map": cluster_persona_map},
                "models/segmentation_model.pkl")

    # Persona summary report
    summary = df.groupby("Persona").agg(
        customers=("customerID", "count"),
        avg_tenure=("tenure", "mean"),
        avg_monthly_charges=("MonthlyCharges", "mean"),
        avg_value_score=("CustomerValueScore", "mean"),
        churn_rate_pct=("ChurnFlag", lambda x: round(x.mean() * 100, 2)),
    ).round(2).sort_values("churn_rate_pct", ascending=False)

    fig, ax = plt.subplots(figsize=(7, 4))
    summary["customers"].plot(kind="bar", ax=ax, color="#2E86AB")
    ax.set_title("Customers per Persona")
    ax.set_ylabel("Count")
    plt.xticks(rotation=25, ha="right")
    fig.savefig(f"{FIG_DIR}/persona_distribution.png", bbox_inches="tight", dpi=110)
    plt.close(fig)

    lines = ["# Customer Segmentation Report\n", f"K-Means with k={best_k} clusters, "
             f"silhouette score at k={best_k}: {sil_scores[best_k-2]:.3f}\n",
             "## Persona Summary\n", summary.to_markdown(), "\n",
             "![](figures/persona_distribution.png)\n",
             "## Persona Definitions\n",
             "- **High-Value Loyal**: Long tenure, high spend. Protect at all costs -- white-glove retention.\n",
             "- **High-Risk New**: Short tenure, high spend. Most likely to churn from price shock; "
             "prioritize onboarding experience and early satisfaction checks.\n",
             "- **Loyal Budget Customer**: Long tenure, low spend. Stable base; upsell opportunity via add-ons.\n",
             "- **At-Risk / High Support Need**: Elevated support tickets regardless of tenure. "
             "Route to proactive care team before renewal.\n",
             "- **Standard / New Customer**: Average across all dimensions; standard nurture track.\n"]
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))

    print(summary.to_string())
    print(f"\nSegmentation complete -> {OUT_PATH}, report -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
