-- =========================================================================
-- analytical_queries.sql
-- 50+ advanced SQL queries for the Customer Churn Analytics Platform.
-- Organized by category. All queries target the star schema built by
-- schema.sql / procedures.sql (churn_analytics.vw_customer_360 etc).
-- These are the exact kind of queries an interviewer will ask you to
-- explain line-by-line -- know what each one answers, business-wise.
-- =========================================================================
SET search_path TO churn_analytics, public;

-- =========================== 1. BASIC JOINS =============================

-- Q1. INNER JOIN: customers with their billing info
SELECT c.customer_id, c.gender, b.contract_type, b.monthly_charges
FROM dim_customers c
INNER JOIN dim_billing b ON b.customer_id = c.customer_id
LIMIT 100;

-- Q2. LEFT JOIN: all customers, with predictions if they exist
SELECT c.customer_id, p.churn_probability, p.risk_segment
FROM dim_customers c
LEFT JOIN fact_predictions p ON p.customer_id = c.customer_id;

-- Q3. RIGHT JOIN: all predictions, matched back to customer info (equivalent LEFT JOIN swapped)
SELECT p.customer_id, p.risk_segment, c.region
FROM dim_customers c
RIGHT JOIN fact_predictions p ON p.customer_id = c.customer_id;

-- Q4. FULL OUTER JOIN: reconcile customers vs segmentation coverage gaps
SELECT c.customer_id AS customer_tbl_id, seg.customer_id AS segment_tbl_id, seg.persona
FROM dim_customers c
FULL OUTER JOIN fact_customer_segments seg ON seg.customer_id = c.customer_id
WHERE c.customer_id IS NULL OR seg.customer_id IS NULL;

-- Q5. Multi-table join: full 360 view assembled manually
SELECT c.customer_id, c.region, b.contract_type, s.internet_service, fc.churn
FROM dim_customers c
JOIN dim_billing b ON b.customer_id = c.customer_id
JOIN dim_services s ON s.customer_id = c.customer_id
JOIN fact_churn fc ON fc.customer_id = c.customer_id;

-- Q6. Self-join style: customers in the same region as a given customer
SELECT c2.customer_id, c2.region
FROM dim_customers c1
JOIN dim_customers c2 ON c1.region = c2.region AND c1.customer_id <> c2.customer_id
WHERE c1.customer_id = 'CUST-100001';

-- =========================== 2. AGGREGATION ==============================

-- Q7. Churn rate by contract type
SELECT b.contract_type,
       COUNT(*) AS total,
       SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) AS churned,
       ROUND(100.0 * SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END)/COUNT(*), 2) AS churn_rate_pct
FROM dim_billing b JOIN fact_churn fc ON fc.customer_id = b.customer_id
GROUP BY b.contract_type
ORDER BY churn_rate_pct DESC;

-- Q8. Average monthly charges by internet service type
SELECT s.internet_service, ROUND(AVG(b.monthly_charges),2) AS avg_charges
FROM dim_services s JOIN dim_billing b ON b.customer_id = s.customer_id
GROUP BY s.internet_service;

-- Q9. Revenue by region
SELECT c.region, ROUND(SUM(b.monthly_charges),2) AS mrr
FROM dim_customers c JOIN dim_billing b ON b.customer_id = c.customer_id
GROUP BY c.region ORDER BY mrr DESC;

-- Q10. Customer count by payment method
SELECT payment_method, COUNT(*) AS customer_count
FROM dim_billing GROUP BY payment_method ORDER BY customer_count DESC;

-- Q11. HAVING: contract types with churn rate above 30%
SELECT b.contract_type, ROUND(100.0*SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END)/COUNT(*),2) AS churn_rate
FROM dim_billing b JOIN fact_churn fc ON fc.customer_id = b.customer_id
GROUP BY b.contract_type
HAVING 100.0*SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END)/COUNT(*) > 30;

-- Q12. HAVING: regions with more than 500 customers
SELECT region, COUNT(*) AS cnt FROM dim_customers
GROUP BY region HAVING COUNT(*) > 500;

-- Q13. Tenure buckets and churn rate per bucket
SELECT
    CASE
        WHEN tenure_months <= 12 THEN '0-12 months'
        WHEN tenure_months <= 24 THEN '13-24 months'
        WHEN tenure_months <= 48 THEN '25-48 months'
        ELSE '49+ months'
    END AS tenure_bucket,
    COUNT(*) AS customers,
    ROUND(100.0*SUM(CASE WHEN churn THEN 1 ELSE 0 END)/COUNT(*),2) AS churn_rate_pct
FROM fact_churn
GROUP BY 1 ORDER BY 1;

-- =========================== 3. CASE STATEMENTS ===========================

-- Q14. Categorize customers by spend tier
SELECT customer_id,
    CASE
        WHEN monthly_charges < 40 THEN 'Low Spender'
        WHEN monthly_charges < 80 THEN 'Mid Spender'
        ELSE 'High Spender'
    END AS spend_tier
FROM dim_billing;

-- Q15. Flag customers at high churn risk based on business rules (not ML)
SELECT c.customer_id,
    CASE
        WHEN b.contract_type = 'Month-to-month' AND fc.support_tickets_last_year >= 3 THEN 'High Risk'
        WHEN b.contract_type = 'Month-to-month' THEN 'Medium Risk'
        ELSE 'Low Risk'
    END AS heuristic_risk
FROM dim_customers c
JOIN dim_billing b ON b.customer_id = c.customer_id
JOIN fact_churn fc ON fc.customer_id = c.customer_id;

-- Q16. Payment method risk flag (electronic check correlates with churn)
SELECT payment_method,
    CASE WHEN payment_method = 'Electronic check' THEN 'Watch List' ELSE 'Standard' END AS payment_flag
FROM dim_billing GROUP BY payment_method;

-- =========================== 4. SUBQUERIES ================================

-- Q17. Customers whose monthly charges exceed the overall average
SELECT customer_id, monthly_charges
FROM dim_billing
WHERE monthly_charges > (SELECT AVG(monthly_charges) FROM dim_billing);

-- Q18. Customers in the region with the highest churn rate
SELECT customer_id, region FROM dim_customers
WHERE region = (
    SELECT region FROM vw_regional_summary
    ORDER BY churn_rate_pct DESC LIMIT 1
);

-- Q19. Correlated subquery: customers paying above their region's average
SELECT c.customer_id, c.region, b.monthly_charges
FROM dim_customers c
JOIN dim_billing b ON b.customer_id = c.customer_id
WHERE b.monthly_charges > (
    SELECT AVG(b2.monthly_charges)
    FROM dim_customers c2 JOIN dim_billing b2 ON b2.customer_id = c2.customer_id
    WHERE c2.region = c.region
);

-- Q20. Subquery in FROM: top 5 highest-MRR regions
SELECT * FROM (
    SELECT region, SUM(monthly_charges) AS mrr
    FROM dim_customers c JOIN dim_billing b ON b.customer_id = c.customer_id
    GROUP BY region
) t ORDER BY mrr DESC LIMIT 5;

-- =========================== 5. CTEs ======================================

-- Q21. CTE: churn rate by tenure bucket, cleanly separated from final select
WITH tenure_buckets AS (
    SELECT customer_id,
        CASE WHEN tenure_months <= 12 THEN '0-12' WHEN tenure_months <= 24 THEN '13-24'
             ELSE '25+' END AS bucket,
        churn
    FROM fact_churn
)
SELECT bucket, COUNT(*) AS n, ROUND(100.0*SUM(CASE WHEN churn THEN 1 ELSE 0 END)/COUNT(*),2) AS churn_pct
FROM tenure_buckets GROUP BY bucket;

-- Q22. Multi-CTE: high value + high risk customer intersection (retention priority list)
WITH high_value AS (
    SELECT customer_id FROM dim_billing WHERE monthly_charges > 80
),
high_risk AS (
    SELECT customer_id FROM fact_predictions WHERE risk_segment = 'High'
)
SELECT hv.customer_id
FROM high_value hv
JOIN high_risk hr ON hr.customer_id = hv.customer_id;

-- Q23. Recursive-style CTE alternative: running total of monthly signups (non-recursive, uses window)
WITH monthly AS (
    SELECT DATE_TRUNC('month', signup_date) AS m, COUNT(*) AS signups
    FROM dim_customers GROUP BY 1
)
SELECT m, signups, SUM(signups) OVER (ORDER BY m) AS cumulative_signups
FROM monthly ORDER BY m;

-- =========================== 6. WINDOW FUNCTIONS ==========================

-- Q24. Rank customers by monthly charges within each region
SELECT customer_id, region, monthly_charges,
       RANK() OVER (PARTITION BY region ORDER BY monthly_charges DESC) AS spend_rank
FROM dim_customers c JOIN dim_billing b ON b.customer_id = c.customer_id;

-- Q25. DENSE_RANK: top spenders per contract type
SELECT customer_id, contract_type, monthly_charges,
       DENSE_RANK() OVER (PARTITION BY contract_type ORDER BY monthly_charges DESC) AS rnk
FROM dim_billing;

-- Q26. ROW_NUMBER: deduplicate / pick most recent prediction per customer
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY predicted_at DESC) AS rn
    FROM fact_predictions
) t WHERE rn = 1;

-- Q27. NTILE: split customers into 4 revenue quartiles
SELECT customer_id, monthly_charges,
       NTILE(4) OVER (ORDER BY monthly_charges) AS revenue_quartile
FROM dim_billing;

-- Q28. Moving average: 3-month rolling average of monthly signups
WITH monthly AS (
    SELECT DATE_TRUNC('month', signup_date) AS m, COUNT(*) AS signups
    FROM dim_customers GROUP BY 1
)
SELECT m, signups,
       ROUND(AVG(signups) OVER (ORDER BY m ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3mo
FROM monthly ORDER BY m;

-- Q29. LAG/LEAD: month-over-month change in signups
WITH monthly AS (
    SELECT DATE_TRUNC('month', signup_date) AS m, COUNT(*) AS signups
    FROM dim_customers GROUP BY 1
)
SELECT m, signups, signups - LAG(signups) OVER (ORDER BY m) AS mom_change
FROM monthly ORDER BY m;

-- Q30. Cumulative revenue by signup cohort
SELECT DATE_TRUNC('month', c.signup_date) AS cohort_month,
       SUM(b.monthly_charges) AS cohort_mrr,
       SUM(SUM(b.monthly_charges)) OVER (ORDER BY DATE_TRUNC('month', c.signup_date)) AS cumulative_mrr
FROM dim_customers c JOIN dim_billing b ON b.customer_id = c.customer_id
GROUP BY 1 ORDER BY 1;

-- Q31. PERCENT_RANK: percentile standing of each customer's spend
SELECT customer_id, monthly_charges,
       ROUND(PERCENT_RANK() OVER (ORDER BY monthly_charges)::numeric, 4) AS spend_percentile
FROM dim_billing;

-- Q32. FIRST_VALUE / LAST_VALUE: min & max spend per contract type shown per row
SELECT customer_id, contract_type, monthly_charges,
       FIRST_VALUE(monthly_charges) OVER (PARTITION BY contract_type ORDER BY monthly_charges) AS min_in_group,
       LAST_VALUE(monthly_charges) OVER (PARTITION BY contract_type ORDER BY monthly_charges
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS max_in_group
FROM dim_billing;

-- =========================== 7. RETENTION ANALYSIS =========================

-- Q33. Cohort retention: % of each signup-month cohort still active at month N
WITH cohorts AS (
    SELECT c.customer_id, DATE_TRUNC('month', c.signup_date) AS cohort_month, fc.tenure_months, fc.churn
    FROM dim_customers c JOIN fact_churn fc ON fc.customer_id = c.customer_id
)
SELECT cohort_month,
       COUNT(*) AS cohort_size,
       SUM(CASE WHEN NOT churn THEN 1 ELSE 0 END) AS still_active,
       ROUND(100.0*SUM(CASE WHEN NOT churn THEN 1 ELSE 0 END)/COUNT(*),2) AS retention_rate_pct
FROM cohorts GROUP BY cohort_month ORDER BY cohort_month;

-- Q34. Retention by contract type over tenure buckets
SELECT contract_type,
       CASE WHEN fc.tenure_months <=12 THEN '0-12' WHEN fc.tenure_months<=24 THEN '13-24' ELSE '25+' END AS bucket,
       ROUND(100.0*SUM(CASE WHEN NOT fc.churn THEN 1 ELSE 0 END)/COUNT(*),2) AS retention_pct
FROM dim_billing b JOIN fact_churn fc ON fc.customer_id = b.customer_id
GROUP BY contract_type, bucket ORDER BY contract_type, bucket;

-- Q35. Customers retained for 24+ months (loyalty milestone) by region
SELECT c.region, COUNT(*) AS loyal_customers
FROM dim_customers c JOIN fact_churn fc ON fc.customer_id = c.customer_id
WHERE fc.tenure_months >= 24 AND NOT fc.churn
GROUP BY c.region ORDER BY loyal_customers DESC;

-- =========================== 8. CLV & REVENUE ANALYSIS =====================

-- Q36. Estimated CLV per customer using the stored function
SELECT customer_id, churn_analytics.calculate_clv(customer_id) AS estimated_clv
FROM dim_customers LIMIT 100;

-- Q37. Average CLV by contract type
SELECT contract_type, ROUND(AVG(churn_analytics.calculate_clv(customer_id)),2) AS avg_clv
FROM dim_billing GROUP BY contract_type;

-- Q38. Total revenue at risk (sum of MRR for predicted high-risk customers)
SELECT ROUND(SUM(b.monthly_charges),2) AS at_risk_mrr
FROM fact_predictions p JOIN dim_billing b ON b.customer_id = p.customer_id
WHERE p.risk_segment = 'High';

-- Q39. Revenue lost to actual churned customers (historical)
SELECT ROUND(SUM(b.monthly_charges),2) AS mrr_lost_to_churn
FROM fact_churn fc JOIN dim_billing b ON b.customer_id = fc.customer_id
WHERE fc.churn = TRUE;

-- Q40. Top 20 customers by CLV who are also high churn risk (priority retention list)
SELECT c.customer_id, churn_analytics.calculate_clv(c.customer_id) AS clv, p.churn_probability
FROM dim_customers c
JOIN fact_predictions p ON p.customer_id = c.customer_id
WHERE p.risk_segment = 'High'
ORDER BY clv DESC LIMIT 20;

-- Q41. Revenue by tenure bucket
SELECT CASE WHEN fc.tenure_months<=12 THEN '0-12' WHEN fc.tenure_months<=24 THEN '13-24'
            WHEN fc.tenure_months<=48 THEN '25-48' ELSE '49+' END AS bucket,
       ROUND(SUM(b.monthly_charges),2) AS mrr
FROM fact_churn fc JOIN dim_billing b ON b.customer_id = fc.customer_id
GROUP BY 1 ORDER BY 1;

-- Q42. Year-over-year revenue growth (by signup year, proxy for cohort revenue)
SELECT EXTRACT(YEAR FROM c.signup_date) AS signup_year, ROUND(SUM(b.monthly_charges),2) AS mrr
FROM dim_customers c JOIN dim_billing b ON b.customer_id = c.customer_id
GROUP BY 1 ORDER BY 1;

-- =========================== 9. STATISTICAL / SEGMENT QUERIES ==============

-- Q43. Churn rate by senior citizen status
SELECT c.senior_citizen, ROUND(100.0*SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END)/COUNT(*),2) AS churn_pct
FROM dim_customers c JOIN fact_churn fc ON fc.customer_id = c.customer_id
GROUP BY c.senior_citizen;

-- Q44. Churn rate by number of support tickets
SELECT support_tickets_last_year, COUNT(*) AS n,
       ROUND(100.0*SUM(CASE WHEN churn THEN 1 ELSE 0 END)/COUNT(*),2) AS churn_pct
FROM fact_churn GROUP BY support_tickets_last_year ORDER BY support_tickets_last_year;

-- Q45. Cross-tab: contract type vs internet service churn rate
SELECT b.contract_type, s.internet_service,
       ROUND(100.0*SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END)/COUNT(*),2) AS churn_pct,
       COUNT(*) AS n
FROM dim_billing b
JOIN dim_services s ON s.customer_id = b.customer_id
JOIN fact_churn fc ON fc.customer_id = b.customer_id
GROUP BY b.contract_type, s.internet_service
ORDER BY churn_pct DESC;

-- Q46. Customers with no add-on services (upsell opportunity)
SELECT COUNT(*) AS customers_no_addons
FROM dim_services
WHERE online_security = 'No' AND online_backup = 'No' AND device_protection = 'No' AND tech_support = 'No';

-- Q47. Segment summary (persona-level churn & value)
SELECT * FROM vw_segment_summary ORDER BY churn_rate_pct DESC;

-- Q48. Prediction model calibration check: avg predicted probability vs actual churn rate by decile
WITH deciles AS (
    SELECT p.customer_id, p.churn_probability, fc.churn,
           NTILE(10) OVER (ORDER BY p.churn_probability) AS decile
    FROM fact_predictions p JOIN fact_churn fc ON fc.customer_id = p.customer_id
)
SELECT decile,
       ROUND(AVG(churn_probability),4) AS avg_predicted_prob,
       ROUND(AVG(CASE WHEN churn THEN 1.0 ELSE 0 END),4) AS actual_churn_rate
FROM deciles GROUP BY decile ORDER BY decile;

-- Q49. Customers gained vs lost per month (net customer movement)
WITH signups AS (
    SELECT DATE_TRUNC('month', signup_date) AS m, COUNT(*) AS gained FROM dim_customers GROUP BY 1
),
churns AS (
    SELECT DATE_TRUNC('month', churn_date) AS m, COUNT(*) AS lost FROM fact_churn WHERE churn_date IS NOT NULL GROUP BY 1
)
SELECT COALESCE(s.m, c.m) AS month, COALESCE(gained,0) AS gained, COALESCE(lost,0) AS lost,
       COALESCE(gained,0) - COALESCE(lost,0) AS net_change
FROM signups s FULL OUTER JOIN churns c ON s.m = c.m
ORDER BY month;

-- Q50. Executive summary single-row KPI snapshot (feeds dashboard cards)
SELECT
    (SELECT COUNT(*) FROM dim_customers) AS total_customers,
    (SELECT ROUND(100.0*SUM(CASE WHEN churn THEN 1 ELSE 0 END)/COUNT(*),2) FROM fact_churn) AS overall_churn_rate_pct,
    (SELECT ROUND(SUM(monthly_charges),2) FROM dim_billing) AS total_mrr,
    (SELECT ROUND(AVG(monthly_charges),2) FROM dim_billing) AS arpu,
    (SELECT ROUND(SUM(monthly_charges),2) FROM fact_predictions p JOIN dim_billing b ON b.customer_id=p.customer_id WHERE risk_segment='High') AS at_risk_mrr;

-- Q51. BONUS: customers whose spend increased relative to their cohort average (CTE + window combo)
WITH cohort_avg AS (
    SELECT c.customer_id, DATE_TRUNC('month', c.signup_date) AS cohort,
           b.monthly_charges,
           AVG(b.monthly_charges) OVER (PARTITION BY DATE_TRUNC('month', c.signup_date)) AS cohort_avg_charges
    FROM dim_customers c JOIN dim_billing b ON b.customer_id = c.customer_id
)
SELECT customer_id, cohort, monthly_charges, cohort_avg_charges
FROM cohort_avg
WHERE monthly_charges > cohort_avg_charges * 1.5;

-- Q52. BONUS: paperless billing adoption vs churn rate
SELECT paperless_billing, ROUND(100.0*SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END)/COUNT(*),2) AS churn_pct
FROM dim_billing b JOIN fact_churn fc ON fc.customer_id = b.customer_id
GROUP BY paperless_billing;
