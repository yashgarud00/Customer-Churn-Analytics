# Power BI Dashboard — Build Guide

Power BI's `.pbix` file format is a proprietary binary that can't be generated
headlessly, so this project ships a fully functional **web dashboard**
(`dashboard/index.html`) as the live, demoable artifact. This guide lets you
recreate the same 5 pages in actual Power BI Desktop in ~15 minutes for your
resume/portfolio screenshots, or to connect it to the live PostgreSQL database.

## 1. Connect to Data

- Open Power BI Desktop → **Get Data** → **PostgreSQL database**
- Server: `localhost`, Database: `churn_db` (or your Docker Compose values)
- Import these views directly (already built for BI consumption):
  `vw_customer_360`, `vw_monthly_churn_trend`, `vw_churn_by_contract`,
  `vw_at_risk_revenue`, `vw_regional_summary`, `vw_segment_summary`
- Alternatively, load `data/processed/telecom_customers_segmented.csv` for a
  quick offline build without Postgres running.

## 2. Data Model

Set relationships (Model view):
- `vw_customer_360[customer_id]` 1—* to prediction/segment tables if imported separately
- Mark `dim_customers` (or the customer_id column) as the primary key table

## 3. DAX Measures

```
Total Customers = DISTINCTCOUNT(vw_customer_360[customer_id])

Churned Customers = CALCULATE([Total Customers], vw_customer_360[churn] = TRUE())

Churn Rate % = DIVIDE([Churned Customers], [Total Customers], 0)

Total MRR = SUM(vw_customer_360[monthly_charges])

ARPU = DIVIDE([Total MRR], [Total Customers], 0)

At-Risk MRR =
CALCULATE(
    [Total MRR],
    vw_customer_360[churn] = TRUE()
)

Avg Tenure (Months) = AVERAGE(vw_customer_360[tenure_months])

Retention Rate % = 1 - [Churn Rate %]

MoM Churn Change =
VAR CurrentMonth = [Churn Rate %]
VAR PriorMonth = CALCULATE([Churn Rate %], PREVIOUSMONTH('Date'[Date]))
RETURN CurrentMonth - PriorMonth

CLV Estimate =
SUMX(
    vw_customer_360,
    vw_customer_360[monthly_charges] *
    SWITCH(
        vw_customer_360[contract_type],
        "Two year", 48,
        "One year", 24,
        10
    )
)

High Risk Customer Count =
CALCULATE([Total Customers], fact_predictions[risk_segment] = "High")
```

## 4. Pages & Visuals

**Page 1 — Executive Summary**
- KPI cards: Total Customers, Churn Rate %, Total MRR, ARPU, At-Risk MRR
- Line chart: monthly signups vs churned (from `vw_monthly_churn_trend`)
- Bar chart: Churn Rate % by Contract Type
- Slicer: Region, Contract Type (applies to whole page via sync)

**Page 2 — Customer Analytics**
- Donut chart: Persona distribution (`fact_customer_segments`)
- Bar chart: Churn Rate % by Persona
- Table: Top 15 customers by `CLV Estimate`, with conditional formatting
  (red background if `risk_segment = "High"`)
- Bookmark: "High-Risk Only" filter toggle

**Page 3 — Revenue Analytics**
- Histogram: Monthly Charges distribution (use a calculated bucket column)
- Bar chart: MRR by Region
- Map visual: bubble size = MRR by Region (requires lat/long or Region as a
  recognized geography — add a mapping table if using real geographies)
- KPI card: Projected Annual Revenue (`[Total MRR] * 12`)

**Page 4 — Churn Dashboard**
- Bar chart: Churn Rate % by Payment Method
- Bar chart: Churn Rate % by Senior Citizen status
- Decomposition tree: Churn Rate % by Contract Type → Internet Service → Payment Method
- Forecast: add a forecast line to the monthly churn trend (built-in Power BI forecasting, 3-month horizon)

**Page 5 — Regional Dashboard**
- Filled map or bar chart: Customers by Region
- Bar chart: Churn Rate % by Region
- Drill-through: click a region bar → drill through to a filtered Page 2 (Customer Analytics) for that region

## 5. Interactivity to Configure

- **Slicers**: Region, Contract Type, Payment Method, Persona — placed on
  Page 1, synced to all pages (Format → Edit Interactions)
- **Drill Through**: set up on Page 5 → Page 2 as described above
- **Bookmarks**: "High-Risk Only" and "All Customers" states on Page 2
- **Tooltips**: enable report-page tooltips on the regional map showing churn rate + MRR on hover

## 6. Publishing

- Publish to Power BI Service (`File → Publish → Publish to Power BI`)
- Set a scheduled refresh against the PostgreSQL database (Gateway required
  if Postgres isn't cloud-hosted) so the dashboard reflects new ETL runs
- Share the report link on your resume/portfolio, or export key pages as
  images for a README screenshot section
