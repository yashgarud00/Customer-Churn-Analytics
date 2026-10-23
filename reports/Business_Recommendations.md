# Business Recommendations Report
### Customer Churn Prediction & Business Intelligence Platform

This report translates the statistical, ML, and segmentation findings into
concrete, prioritized actions for a telecom Customer Success / Retention team.

---

## Executive Summary

- Overall churn rate is ~40% in this dataset (synthetic, calibrated to be
  realistically challenging — real telecom churn is typically 15-30%
  annually; this project intentionally simulates a higher-friction market
  to stress-test the retention strategy).
- The single strongest churn predictor is **contract type**: month-to-month
  customers churn multiple times more often than two-year contract holders.
- The highest-risk segment is **"High-Risk New"** (short tenure, high
  spend) — 74.6% churn rate, 3,256 customers, avg $77/mo. This is where
  retention spend has the highest expected ROI.

---

## Who Should Receive Discounts?

**Target: "High-Risk New" and "At-Risk / High Support Need" personas**
who also fall in the ML model's top-2 predicted-risk deciles (see
`fact_predictions` / Q40 in `analytical_queries.sql`).

Rationale: These customers combine (a) high revenue-at-risk and (b) high
predicted churn probability — the intersection query in `analytical_queries.sql`
(Q22, Q40) identifies exactly this list. Offering a modest loyalty discount
(e.g., 10-15% for switching Month-to-month → One year) is far cheaper than
the cost of re-acquiring the customer.

**Do NOT blanket-discount the "Loyal Budget Customer" segment** — they
already have low churn (38%) and low spend; a discount here erodes margin
with minimal retention benefit.

## Who Should Be Contacted First?

Priority order (by expected revenue saved per contact):

1. High-Risk New customers with `CustomerValueScore` in the top quartile
   and `SupportTicketsLastYear >= 2` — likely frustrated high-value
   customers about to leave.
2. Customers on Month-to-month contracts paying above their region's
   average monthly charge (Q19) — price-shock risk.
3. Electronic-check payers with 0 add-on services (Q46) — low engagement,
   low switching cost, easiest to lose.

## Expected Revenue Savings (illustrative model)

Using the at-risk MRR calculation (`vw_at_risk_revenue`, Q38):
if the retention team successfully retains **20% of customers flagged
"High" risk** by the model, at an average $75/mo monthly charge and a
24-month expected extended lifetime, that's approximately:

```
retained_customers = high_risk_customers * 0.20
revenue_saved = retained_customers * $75/mo * 24 months
```

Run `GET /analytics` on the API (Phase 13) for the live number against
the current dataset snapshot — this is intentionally computed dynamically
rather than hardcoded, since it should update as new predictions run.

## Customer Retention Strategy (by persona)

| Persona | Strategy |
|---|---|
| High-Risk New | Onboarding call within first 30 days; proactive check-in at day 60-90; contract-upgrade offer at month 6 |
| At-Risk / High Support Need | Route to senior support tier; root-cause the ticket pattern before renewal date |
| Standard / New Customer | Standard nurture email track; monitor for risk-signal drift |
| Loyal Budget Customer | Upsell add-on services (they have capacity for more spend and low churn risk) |
| High-Value Loyal | White-glove account management; do not disturb with aggressive upsell |

## Caveats & Next Steps

- This dataset is synthetic; before productionizing, validate feature
  relationships against real billing/CRM data — correlations here were
  partly designed into the generator for demonstration purposes.
- The model should be retrained on a rolling basis (see the bonus
  "Scheduled ETL jobs" feature) as churn drivers can shift with pricing
  changes, competitor offers, or macroeconomic conditions.
- A/B test any discount strategy on a holdout group before full rollout
  — correlation-driven recommendations should be validated causally.
