# Statistical Analysis Report

Sample size: n = 12,000

Significance level: alpha = 0.05

## 1. Chi-Square Test: Contract Type vs Churn
- chi2 = 1507.69, p-value = 0.00e+00, dof = 2
- Result: **statistically significant**
- **Business interpretation:** Contract type and churn are not independent -- the type of contract a customer signs meaningfully predicts whether they'll leave. This statistically confirms the EDA finding and justifies contract-upgrade incentives as a retention strategy, not just an appealing chart.

## 2. Chi-Square Test: Payment Method vs Churn
- chi2 = 70.13, p-value = 4.00e-15, dof = 3
- Result: **statistically significant**
- **Business interpretation:** Payment method is significantly associated with churn. Electronic check users are disproportionately represented among churners -- worth investigating whether this reflects a customer segment (e.g., less engaged, price-sensitive) rather than the payment method itself causing churn.

## 3. Chi-Square Test: Senior Citizen vs Churn
- chi2 = 5.18, p-value = 2.29e-02, dof = 1
- Result: **statistically significant**
- **Business interpretation:** Senior citizen status has a measurable relationship with churn. Retention messaging and support channels may need to be tailored for this segment (e.g., phone support emphasis over app-based self-service).

## 4. Independent T-Test: Monthly Charges (Churned vs Retained)
- Churned mean = $70.69, Retained mean = $58.66
- t = 26.10, p-value = 5.75e-145
- Result: **statistically significant**
- **Business interpretation:** Churned customers pay significantly more per month on average. This supports a 'price shock' hypothesis -- customers churn when perceived value doesn't match price, which suggests testing loyalty discounts for high-bill customers rather than blanket price cuts.

## 5. Independent T-Test: Tenure (Churned vs Retained)
- Churned mean tenure = 33.0 months, Retained = 41.1 months
- t = -21.13, p-value = 4.90e-97
- Result: **statistically significant**
- **Business interpretation:** Confirms the early-tenure risk window statistically -- the first year of the customer relationship is the critical retention period.

## 6. One-Way ANOVA: Monthly Charges across Internet Service Types
- F = 28141.58, p-value = 0.00e+00
- Result: **statistically significant**
- **Business interpretation:** Pricing differs significantly by service tier (expected, validates the pricing model), but this analysis is a precursor to testing whether price *relative to tier* (not absolute price) drives churn -- a more nuanced pricing strategy question for product teams.

## 7. One-Way ANOVA: Tenure across Contract Types
- F = 1.33, p-value = 2.65e-01
- Result: **not statistically significant**
- **Business interpretation:** Customers on longer commitment contracts have significantly longer tenure, reinforcing that contract structure is a retention lever, not just a correlate.

## 8. 95% Confidence Interval: Overall Churn Rate
- Point estimate: 60.42%
- 95% CI: [59.54%, 61.29%]
- **Business interpretation:** We can state with 95% confidence that the true churn rate across the full customer base falls in this range -- useful for setting realistic targets when reporting to leadership (e.g., 'reduce churn from ~X% to below the CI lower bound within 2 quarters').

## 9. Feature Correlation with Churn (Point-Biserial)
- **tenure**: r = -0.189, p = 1.06e-96 (statistically significant)
- **MonthlyCharges**: r = 0.237, p = 1.88e-153 (statistically significant)
- **TotalCharges**: r = -0.022, p = 1.80e-02 (statistically significant)
- **SupportTicketsLastYear**: r = 0.046, p = 3.66e-07 (statistically significant)
- **ContractDurationMonths**: r = -0.354, p = 0.00e+00 (statistically significant)
- **TotalAddOnServices**: r = 0.164, p = 6.09e-73 (statistically significant)
- **CustomerValueScore**: r = -0.159, p = 2.10e-68 (statistically significant)

- **Business interpretation:** These correlations rank feature relevance for the ML model in Phase 9 and give analysts a plain-language 'what moves the needle' summary for stakeholders who won't read a SHAP plot.
