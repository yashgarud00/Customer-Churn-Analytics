-- =========================================================================
-- schema.sql
-- Normalized PostgreSQL schema for Customer Churn Analytics Platform
-- =========================================================================
-- Design notes:
--   - The raw "customers" table (loaded by the ETL) is a wide, denormalized
--     staging table. This schema NORMALIZES it into a proper star-like
--     schema for analytics: a customer dimension, a services dimension,
--     and a billing/fact table, plus a churn_events fact table.
--   - Run this AFTER the ETL has populated the staging "customers" table.
--   - Compatible with PostgreSQL 13+.
-- =========================================================================

CREATE SCHEMA IF NOT EXISTS churn_analytics;
SET search_path TO churn_analytics, public;

-- -------------------------------------------------------------------------
-- DIMENSION: customers
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_customers (
    customer_id         VARCHAR(20) PRIMARY KEY,
    gender               VARCHAR(10) NOT NULL CHECK (gender IN ('Male','Female')),
    senior_citizen       BOOLEAN NOT NULL DEFAULT FALSE,
    partner              BOOLEAN NOT NULL DEFAULT FALSE,
    dependents           BOOLEAN NOT NULL DEFAULT FALSE,
    region               VARCHAR(20),
    signup_date          DATE NOT NULL,
    created_at           TIMESTAMP NOT NULL DEFAULT now(),
    updated_at           TIMESTAMP NOT NULL DEFAULT now()
);

-- -------------------------------------------------------------------------
-- DIMENSION: services subscribed by each customer
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_services (
    customer_id          VARCHAR(20) PRIMARY KEY REFERENCES dim_customers(customer_id) ON DELETE CASCADE,
    phone_service         BOOLEAN NOT NULL DEFAULT FALSE,
    multiple_lines        VARCHAR(20) NOT NULL DEFAULT 'No',
    internet_service       VARCHAR(20) NOT NULL DEFAULT 'No' CHECK (internet_service IN ('DSL','Fiber optic','No')),
    online_security        VARCHAR(25) NOT NULL DEFAULT 'No internet service',
    online_backup           VARCHAR(25) NOT NULL DEFAULT 'No internet service',
    device_protection        VARCHAR(25) NOT NULL DEFAULT 'No internet service',
    tech_support              VARCHAR(25) NOT NULL DEFAULT 'No internet service',
    streaming_tv               VARCHAR(25) NOT NULL DEFAULT 'No internet service',
    streaming_movies             VARCHAR(25) NOT NULL DEFAULT 'No internet service'
);

-- -------------------------------------------------------------------------
-- DIMENSION: contract & billing configuration
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_billing (
    customer_id           VARCHAR(20) PRIMARY KEY REFERENCES dim_customers(customer_id) ON DELETE CASCADE,
    contract_type          VARCHAR(20) NOT NULL CHECK (contract_type IN ('Month-to-month','One year','Two year')),
    paperless_billing        BOOLEAN NOT NULL DEFAULT FALSE,
    payment_method             VARCHAR(30) NOT NULL,
    monthly_charges              NUMERIC(10,2) NOT NULL CHECK (monthly_charges >= 0),
    total_charges                  NUMERIC(12,2) NOT NULL CHECK (total_charges >= 0)
);

-- -------------------------------------------------------------------------
-- FACT: churn events (one row per customer's latest known status)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_churn (
    customer_id          VARCHAR(20) PRIMARY KEY REFERENCES dim_customers(customer_id) ON DELETE CASCADE,
    tenure_months          INTEGER NOT NULL CHECK (tenure_months >= 0),
    support_tickets_last_year INTEGER NOT NULL DEFAULT 0,
    churn                     BOOLEAN NOT NULL,
    churn_date                 DATE,
    recorded_at                  TIMESTAMP NOT NULL DEFAULT now()
);

-- -------------------------------------------------------------------------
-- FACT: model predictions (populated by the ML pipeline / API)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_predictions (
    prediction_id        BIGSERIAL PRIMARY KEY,
    customer_id            VARCHAR(20) NOT NULL REFERENCES dim_customers(customer_id) ON DELETE CASCADE,
    churn_probability        NUMERIC(5,4) NOT NULL CHECK (churn_probability BETWEEN 0 AND 1),
    risk_segment                VARCHAR(10) NOT NULL CHECK (risk_segment IN ('Low','Medium','High')),
    model_version                  VARCHAR(20) NOT NULL,
    predicted_at                     TIMESTAMP NOT NULL DEFAULT now()
);

-- -------------------------------------------------------------------------
-- FACT: customer segments (from K-Means clustering)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_customer_segments (
    customer_id           VARCHAR(20) PRIMARY KEY REFERENCES dim_customers(customer_id) ON DELETE CASCADE,
    cluster_id               INTEGER NOT NULL,
    persona                     VARCHAR(30) NOT NULL,
    customer_value_score          NUMERIC(6,2),
    assigned_at                      TIMESTAMP NOT NULL DEFAULT now()
);

-- -------------------------------------------------------------------------
-- Indexes (query performance for common analytical filters)
-- -------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_billing_contract_type   ON dim_billing(contract_type);
CREATE INDEX IF NOT EXISTS idx_billing_payment_method   ON dim_billing(payment_method);
CREATE INDEX IF NOT EXISTS idx_churn_flag                ON fact_churn(churn);
CREATE INDEX IF NOT EXISTS idx_churn_tenure                ON fact_churn(tenure_months);
CREATE INDEX IF NOT EXISTS idx_customers_region               ON dim_customers(region);
CREATE INDEX IF NOT EXISTS idx_customers_signup_date             ON dim_customers(signup_date);
CREATE INDEX IF NOT EXISTS idx_predictions_customer                ON fact_predictions(customer_id);
CREATE INDEX IF NOT EXISTS idx_predictions_risk_segment               ON fact_predictions(risk_segment);
CREATE INDEX IF NOT EXISTS idx_segments_persona                          ON fact_customer_segments(persona);

-- -------------------------------------------------------------------------
-- Trigger: auto-update updated_at on dim_customers
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION churn_analytics.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_customers_updated_at ON dim_customers;
CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON dim_customers
    FOR EACH ROW
    EXECUTE FUNCTION churn_analytics.set_updated_at();

-- -------------------------------------------------------------------------
-- Trigger: prevent churn_date being set when churn = false
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION churn_analytics.validate_churn_date()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.churn = FALSE AND NEW.churn_date IS NOT NULL THEN
        RAISE EXCEPTION 'churn_date must be NULL when churn = FALSE for customer %', NEW.customer_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_churn_date ON fact_churn;
CREATE TRIGGER trg_validate_churn_date
    BEFORE INSERT OR UPDATE ON fact_churn
    FOR EACH ROW
    EXECUTE FUNCTION churn_analytics.validate_churn_date();
