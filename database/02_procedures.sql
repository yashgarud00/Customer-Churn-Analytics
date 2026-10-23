-- =========================================================================
-- procedures.sql
-- Stored procedures & functions for the Churn Analytics platform
-- =========================================================================
SET search_path TO churn_analytics, public;

-- -------------------------------------------------------------------------
-- FUNCTION: normalize_staging_to_star()
-- Populates the star schema (dim_*/fact_*) from the flat "customers"
-- staging table that the Python ETL loads. Idempotent (safe to re-run).
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION churn_analytics.normalize_staging_to_star()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    INSERT INTO dim_customers (customer_id, gender, senior_citizen, partner, dependents, region, signup_date)
    SELECT "customerID", gender, "SeniorCitizen"::boolean, (Partner = 'Yes'), (Dependents = 'Yes'),
           "Region", "SignupDate"::date
    FROM public.customers
    ON CONFLICT (customer_id) DO UPDATE
        SET gender = EXCLUDED.gender,
            senior_citizen = EXCLUDED.senior_citizen,
            partner = EXCLUDED.partner,
            dependents = EXCLUDED.dependents,
            region = EXCLUDED.region;

    INSERT INTO dim_services (customer_id, phone_service, multiple_lines, internet_service,
                                online_security, online_backup, device_protection, tech_support,
                                streaming_tv, streaming_movies)
    SELECT "customerID", ("PhoneService" = 'Yes'), "MultipleLines", "InternetService",
           "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport",
           "StreamingTV", "StreamingMovies"
    FROM public.customers
    ON CONFLICT (customer_id) DO NOTHING;

    INSERT INTO dim_billing (customer_id, contract_type, paperless_billing, payment_method,
                              monthly_charges, total_charges)
    SELECT "customerID", "Contract", ("PaperlessBilling" = 'Yes'), "PaymentMethod",
           "MonthlyCharges", "TotalCharges"
    FROM public.customers
    ON CONFLICT (customer_id) DO NOTHING;

    INSERT INTO fact_churn (customer_id, tenure_months, support_tickets_last_year, churn, churn_date)
    SELECT "customerID", tenure, "SupportTicketsLastYear", ("Churn" = 'Yes'),
           CASE WHEN "Churn" = 'Yes' THEN CURRENT_DATE ELSE NULL END
    FROM public.customers
    ON CONFLICT (customer_id) DO NOTHING;

    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- -------------------------------------------------------------------------
-- FUNCTION: calculate_clv(customer_id)
-- Simple CLV estimate = avg_monthly_revenue * expected_lifetime_months
-- expected_lifetime_months is derived from contract type churn-adjusted
-- survival heuristic (a simplified, explainable CLV -- production systems
-- would use a proper survival model, see notebooks/ModelTraining.ipynb).
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION churn_analytics.calculate_clv(p_customer_id VARCHAR)
RETURNS NUMERIC AS $$
DECLARE
    v_monthly_charges NUMERIC;
    v_contract VARCHAR;
    v_expected_lifetime_months NUMERIC;
    v_clv NUMERIC;
BEGIN
    SELECT monthly_charges, contract_type INTO v_monthly_charges, v_contract
    FROM dim_billing WHERE customer_id = p_customer_id;

    IF v_monthly_charges IS NULL THEN
        RETURN NULL;
    END IF;

    v_expected_lifetime_months := CASE v_contract
        WHEN 'Two year' THEN 48
        WHEN 'One year' THEN 24
        ELSE 10
    END;

    v_clv := v_monthly_charges * v_expected_lifetime_months;
    RETURN ROUND(v_clv, 2);
END;
$$ LANGUAGE plpgsql;

-- -------------------------------------------------------------------------
-- PROCEDURE: refresh_customer_value_scores()
-- Recomputes a 0-100 customer value score combining revenue + tenure +
-- loyalty, used by dashboards and the segmentation model.
-- -------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE churn_analytics.refresh_customer_value_scores()
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE fact_customer_segments fcs
    SET customer_value_score = sub.score
    FROM (
        SELECT b.customer_id,
               ROUND(
                   (0.5 * (b.monthly_charges / NULLIF(mx.max_charges, 0)) * 100) +
                   (0.3 * (fc.tenure_months::numeric / NULLIF(mx.max_tenure, 0)) * 100) +
                   (0.2 * CASE b.contract_type
                            WHEN 'Two year' THEN 100
                            WHEN 'One year' THEN 60
                            ELSE 20 END)
               , 2) AS score
        FROM dim_billing b
        JOIN fact_churn fc ON fc.customer_id = b.customer_id
        CROSS JOIN (SELECT MAX(monthly_charges) AS max_charges, MAX(tenure_months) AS max_tenure
                     FROM dim_billing db2 JOIN fact_churn fc2 ON fc2.customer_id = db2.customer_id) mx
    ) sub
    WHERE fcs.customer_id = sub.customer_id;
END;
$$;

-- -------------------------------------------------------------------------
-- FUNCTION: get_churn_rate(p_contract_type)
-- Returns churn rate % for a given contract type (or overall if NULL)
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION churn_analytics.get_churn_rate(p_contract_type VARCHAR DEFAULT NULL)
RETURNS NUMERIC AS $$
DECLARE
    v_rate NUMERIC;
BEGIN
    SELECT ROUND(100.0 * SUM(CASE WHEN fc.churn THEN 1 ELSE 0 END) / COUNT(*), 2)
    INTO v_rate
    FROM fact_churn fc
    JOIN dim_billing b ON b.customer_id = fc.customer_id
    WHERE p_contract_type IS NULL OR b.contract_type = p_contract_type;

    RETURN v_rate;
END;
$$ LANGUAGE plpgsql;
