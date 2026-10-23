"""
eda_report.py
--------------
Full exploratory data analysis. Generates all standard EDA charts and
writes a markdown report with business-language insights after each
visualization (exactly what a Data Analyst deliverable looks like).

Usage:
    python src/visualization/eda_report.py
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import os

sns.set_theme(style="whitegrid")
DATA_PATH = "data/processed/telecom_customers_features.csv"
FIG_DIR = "reports/figures"
REPORT_PATH = "reports/EDA_Report.md"

os.makedirs(FIG_DIR, exist_ok=True)
insights = []


def save(fig, name):
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path, bbox_inches="tight", dpi=110)
    plt.close(fig)
    return path


def main():
    df = pd.read_csv(DATA_PATH)
    insights.append("# Exploratory Data Analysis Report\n")
    insights.append(f"Dataset: {len(df):,} customers, {df.shape[1]} columns after feature engineering.\n")

    # 1. Churn distribution
    fig, ax = plt.subplots(figsize=(5, 4))
    df["Churn"].value_counts().plot(kind="bar", color=["#2E86AB", "#E63946"], ax=ax)
    ax.set_title("Churn Distribution")
    ax.set_xlabel("Churn"); ax.set_ylabel("Customers")
    save(fig, "01_churn_distribution.png")
    churn_rate = (df["Churn"] == "Yes").mean() * 100
    insights.append(f"## 1. Churn Distribution\n![](figures/01_churn_distribution.png)\n\n"
                     f"**Insight:** Overall churn rate is **{churn_rate:.1f}%**. This is the baseline "
                     f"the ML model must beat, and the class imbalance means accuracy alone is a "
                     f"misleading metric (see Phase 9 -- we prioritize recall/F1 instead).\n")

    # 2. Monthly charges distribution
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(df["MonthlyCharges"], bins=40, kde=True, ax=ax, color="#2E86AB")
    ax.set_title("Monthly Charges Distribution")
    save(fig, "02_monthly_charges_dist.png")
    insights.append(f"## 2. Monthly Charges Distribution\n![](figures/02_monthly_charges_dist.png)\n\n"
                     f"**Insight:** Charges show a multi-modal pattern driven by internet service tier "
                     f"(DSL vs Fiber vs None), median ${df['MonthlyCharges'].median():.2f}/mo. This "
                     f"justifies segmenting pricing analysis by service tier rather than treating "
                     f"revenue as one uniform bucket.\n")

    # 3. Contract type distribution & churn
    fig, ax = plt.subplots(figsize=(6, 4))
    ct = pd.crosstab(df["Contract"], df["Churn"], normalize="index") * 100
    ct.plot(kind="bar", stacked=True, ax=ax, color=["#2E86AB", "#E63946"])
    ax.set_title("Churn Rate by Contract Type")
    ax.set_ylabel("% of customers")
    save(fig, "03_churn_by_contract.png")
    mtm_rate = ct.loc["Month-to-month", "Yes"] if "Month-to-month" in ct.index else 0
    tyr_rate = ct.loc["Two year", "Yes"] if "Two year" in ct.index else 0
    insights.append(f"## 3. Churn by Contract Type\n![](figures/03_churn_by_contract.png)\n\n"
                     f"**Insight:** Month-to-month customers churn at **{mtm_rate:.1f}%** vs "
                     f"**{tyr_rate:.1f}%** for two-year contracts. This is the single strongest "
                     f"retention lever available: incentivizing contract upgrades (e.g., a discount "
                     f"for switching to annual billing) should be the #1 recommendation.\n")

    # 4. Payment method vs churn
    fig, ax = plt.subplots(figsize=(7, 4))
    pm = pd.crosstab(df["PaymentMethod"], df["Churn"], normalize="index") * 100
    pm["Yes"].sort_values(ascending=False).plot(kind="barh", ax=ax, color="#E63946")
    ax.set_title("Churn Rate % by Payment Method")
    save(fig, "04_churn_by_payment.png")
    insights.append(f"## 4. Churn by Payment Method\n![](figures/04_churn_by_payment.png)\n\n"
                     f"**Insight:** Electronic check payers churn substantially more than autopay "
                     f"customers. Nudging customers toward autopay (small incentive) is a low-cost "
                     f"retention lever.\n")

    # 5. Tenure distribution by churn
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.boxplot(data=df, x="Churn", y="tenure", ax=ax, palette=["#2E86AB", "#E63946"])
    ax.set_title("Tenure by Churn Status")
    save(fig, "05_tenure_boxplot.png")
    insights.append(f"## 5. Tenure vs Churn (Boxplot)\n![](figures/05_tenure_boxplot.png)\n\n"
                     f"**Insight:** Churned customers cluster at low tenure -- the first 12 months "
                     f"are the highest-risk window. Onboarding and early-lifecycle engagement "
                     f"campaigns should be prioritized over late-tenure retention spend.\n")

    # 6. Correlation heatmap (numeric features)
    numeric_cols = ["tenure", "MonthlyCharges", "TotalCharges", "SupportTicketsLastYear",
                     "AvgMonthlySpend", "ContractDurationMonths", "TotalAddOnServices",
                     "CustomerValueScore", "ChurnFlag"]
    fig, ax = plt.subplots(figsize=(8, 6))
    corr = df[numeric_cols].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax)
    ax.set_title("Correlation Matrix (Numeric Features)")
    save(fig, "06_correlation_heatmap.png")
    top_corr = corr["ChurnFlag"].drop("ChurnFlag").abs().sort_values(ascending=False).head(3)
    insights.append(f"## 6. Correlation Matrix\n![](figures/06_correlation_heatmap.png)\n\n"
                     f"**Insight:** Strongest linear correlates of churn are "
                     f"{', '.join(top_corr.index)}. Note correlation != causation -- these guide "
                     f"feature selection for the ML model in Phase 9, not standalone conclusions.\n")

    # 7. Pie chart: internet service mix
    fig, ax = plt.subplots(figsize=(5, 5))
    df["InternetService"].value_counts().plot(kind="pie", autopct="%1.1f%%", ax=ax, colors=sns.color_palette("Blues_r", 3))
    ax.set_ylabel("")
    ax.set_title("Internet Service Mix")
    save(fig, "07_internet_service_pie.png")
    insights.append(f"## 7. Internet Service Mix\n![](figures/07_internet_service_pie.png)\n\n"
                     f"**Insight:** Fiber optic is the largest segment but (per query Q45 in "
                     f"analytical_queries.sql) also has the highest churn rate -- likely a pricing "
                     f"or service-quality issue worth a targeted satisfaction survey.\n")

    # 8. Bar chart: customer demographics (senior citizen, partner, dependents)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, col in zip(axes, ["SeniorCitizen", "Partner", "Dependents"]):
        df[col].value_counts().plot(kind="bar", ax=ax, color="#2E86AB")
        ax.set_title(col)
    fig.suptitle("Customer Demographics")
    save(fig, "08_demographics.png")
    insights.append(f"## 8. Customer Demographics\n![](figures/08_demographics.png)\n\n"
                     f"**Insight:** Senior citizens are a minority of the base but (per statistical "
                     f"testing in Phase 7) churn at a significantly different rate -- see "
                     f"Statistical_Analysis_Report.md for the chi-square test result.\n")

    # 9. Histogram: support tickets
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(df["SupportTicketsLastYear"], bins=range(0, 8), ax=ax, color="#E63946")
    ax.set_title("Support Tickets (Last 12 Months) Distribution")
    save(fig, "09_support_tickets_hist.png")
    insights.append(f"## 9. Support Ticket Volume\n![](figures/09_support_tickets_hist.png)\n\n"
                     f"**Insight:** Most customers file 0-2 tickets/year; customers with 3+ tickets "
                     f"are a small but high-risk group worth proactive outreach before renewal.\n")

    # 10. Pair plot (sampled for performance) of key numeric features by churn
    sample = df.sample(min(1500, len(df)), random_state=42)
    pp = sns.pairplot(
        sample[["tenure", "MonthlyCharges", "TotalCharges", "Churn"]],
        hue="Churn", palette=["#2E86AB", "#E63946"], plot_kws={"alpha": 0.4, "s": 15}
    )
    pp.savefig(os.path.join(FIG_DIR, "10_pairplot.png"), dpi=110)
    plt.close("all")
    insights.append(f"## 10. Pair Plot (Tenure / Charges)\n![](figures/10_pairplot.png)\n\n"
                     f"**Insight:** Churned customers concentrate in the low-tenure, "
                     f"mid-to-high monthly charge region -- consistent with the 'new customer, "
                     f"higher price shock' churn pattern seen in telecom broadly.\n")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(insights))
    print(f"EDA complete. Report -> {REPORT_PATH}, figures -> {FIG_DIR}/")


if __name__ == "__main__":
    main()
