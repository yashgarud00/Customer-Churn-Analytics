-- =========================================================================
-- views.sql
-- Analytical views consumed by Power BI, the Flask API, and ad-hoc SQL
-- =========================================================================
SET search_path TO churn_analytics, public;

-- Full denormalized customer view (single source of truth for BI tools)
CREATE OR REPLACE VIEW vw_customer_360 AS
SELECT
    c.customer_id,
    c.gender,
    c.senior_citizen,
    c.partner,
    c.dependents,
    c.region,
    c.signup_date,
    s.phone_service,
    s.internet_service,
    s.online_security,
    s.tech_support,
    s.streaming_tv,
    s.streaming_movies,
    b.contract_type,
    b.paperless_billing,
    b.payment_method,
    b.monthly_charges,
    b.total_charges,
    fc.tenure_months,
    fc.support_tickets_last_year,
    fc.churn,
    fc.churn_date,
    churn_analytics.calculate_clv(c.customer_id) AS estimated_clv
FROM dim_customers c
JOIN dim_services s ON s.customer_id = c.customer_id
JOIN dim_billing b ON b.customer_id = c.customer_id
JOIN fact_churn fc ON fc.customer_id = c.customer_id;

-- Monthly churn & revenue trend (used by Executive Summary dashboard page)
CREATE OR REPLACE VIEW vw_monthly_churn_trend AS
SELECT
    DATE_TRUNC('month', c.signup_date) AS signup_month,
    COUNT(*) AS customers_signed_up,
    SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) AS customers_churned,
    ROUND(100.0 * SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_pct,
    ROUND(SUM(b.monthly_charges), 2) AS mrr_at_signup
FROM dim_customers c
JOIN fact_churn fc ON fc.customer_id = c.customer_id
JOIN dim_billing b ON b.customer_id = c.customer_id
GROUP BY 1
ORDER BY 1;

-- Churn rate by contract type (used repeatedly across dashboard pages)
CREATE OR REPLACE VIEW vw_churn_by_contract AS
SELECT
    b.contract_type,
    COUNT(*) AS total_customers,
    SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) AS churned_customers,
    ROUND(100.0 * SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_pct,
    ROUND(AVG(b.monthly_charges), 2) AS avg_monthly_charges
FROM dim_billing b
JOIN fact_churn fc ON fc.customer_id = b.customer_id
GROUP BY b.contract_type;

-- High-risk revenue exposure (used by API GET /analytics and dashboard KPI cards)
CREATE OR REPLACE VIEW vw_at_risk_revenue AS
SELECT
    p.risk_segment,
    COUNT(*) AS customer_count,
    ROUND(SUM(b.monthly_charges), 2) AS mrr_exposed
FROM fact_predictions p
JOIN dim_billing b ON b.customer_id = p.customer_id
GROUP BY p.risk_segment;

-- Regional performance (Regional Dashboard page)
CREATE OR REPLACE VIEW vw_regional_summary AS
SELECT
    c.region,
    COUNT(*) AS total_customers,
    SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) AS churned_customers,
    ROUND(100.0 * SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_pct,
    ROUND(SUM(b.monthly_charges), 2) AS mrr,
    ROUND(AVG(fc.tenure_months), 1) AS avg_tenure_months
FROM dim_customers c
JOIN fact_churn fc ON fc.customer_id = c.customer_id
JOIN dim_billing b ON b.customer_id = c.customer_id
GROUP BY c.region;

-- Customer segments / personas summary (Customer Analytics page)
CREATE OR REPLACE VIEW vw_segment_summary AS
SELECT
    seg.persona,
    COUNT(*) AS customer_count,
    ROUND(AVG(seg.customer_value_score), 2) AS avg_value_score,
    ROUND(AVG(b.monthly_charges), 2) AS avg_monthly_charges,
    ROUND(100.0 * SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate_pct
FROM fact_customer_segments seg
JOIN dim_billing b ON b.customer_id = seg.customer_id
JOIN fact_churn fc ON fc.customer_id = seg.customer_id
GROUP BY seg.persona;
