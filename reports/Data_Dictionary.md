# Data Dictionary

## Layer 1 — Raw (`data/raw/telecom_customers_raw.csv`)
As received from the simulated CRM/billing export. Contains intentional data quality issues (see `reports/data_quality_report.md`).

| Column | Type | Description |
|---|---|---|
| customerID | string | Unique customer identifier (may contain duplicates in raw layer) |
| gender | string | Male/Female (may appear as M/F — inconsistent casing) |
| SeniorCitizen | int (0/1) | Senior citizen flag |
| Partner | string | Yes/No, has a partner (may be null) |
| Dependents | string | Yes/No, has dependents |
| tenure | int | Months as a customer (may contain invalid negative values) |
| PhoneService | string | Yes/No |
| MultipleLines | string | Yes/No/No phone service |
| InternetService | string | DSL / Fiber optic / No |
| OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies | string | Yes/No/No internet service |
| Contract | string | Month-to-month / One year / Two year |
| PaperlessBilling | string | Yes/No |
| PaymentMethod | string | Electronic check / Mailed check / Bank transfer (automatic) / Credit card (automatic) |
| MonthlyCharges | float | Current monthly bill (may be null, may contain outliers) |
| TotalCharges | string | Lifetime charges (stored as string with stray whitespace in raw layer — classic real-world bug) |
| SupportTicketsLastYear | int | Support tickets filed in the last 12 months |
| SignupDate | string | Mixed formats (ISO and DD/MM/YYYY) in raw layer |
| Region | string | North / South / East / West / Central |
| Churn | string | Yes/No target (inconsistent casing in raw layer) |

## Layer 2 — Cleaned (`data/cleaned/telecom_customers_cleaned.csv`)
Output of `src/ETL/etl_pipeline.py`. All raw-layer issues resolved:
duplicates dropped, types corrected, missing values imputed (median for
numeric, mode for categorical), outliers capped via IQR, dates standardized
to ISO 8601. Same columns as raw layer, but type-safe and validated.

## Layer 3 — Feature-Engineered (`data/processed/telecom_customers_features.csv`)
Output of `src/preprocessing/feature_engineering.py`. Adds:

| Column | Type | Description |
|---|---|---|
| AvgMonthlySpend | float | TotalCharges / tenure (guards divide-by-zero) |
| CustomerLifecycleStage | category | New/Ramping/Established/Mature/Veteran, based on tenure bins |
| ContractDurationMonths | int | Contract type mapped to numeric months (1/12/24) |
| IsAutoPay | int (0/1) | 1 if payment method is bank transfer or credit card auto-pay |
| SupportTicketsPerTenureYear | float | Ticket rate normalized by tenure |
| TotalAddOnServices | int | Count of Yes across the 6 add-on service columns |
| HasInternetNoProtection | int (0/1) | Has internet but no security/tech support — upsell/risk flag |
| CustomerValueScore | float (0-100) | Weighted blend of spend, tenure, contract commitment |
| IsHighValueCustomer | int (0/1) | Top quartile of CustomerValueScore |
| IsMultiServiceHousehold | int (0/1) | Phone + internet + streaming bundle flag |
| ChurnFlag | int (0/1) | Binary-encoded target for modeling |

## Layer 4 — Segmented (`data/processed/telecom_customers_segmented.csv`)
Output of `src/modeling/customer_segmentation.py`. Adds:

| Column | Type | Description |
|---|---|---|
| ClusterID | int | Raw K-Means cluster assignment (k=5) |
| Persona | string | Business-readable label: High-Value Loyal / High-Risk New / Loyal Budget Customer / At-Risk / High Support Need / Standard / New Customer |

## Model Artifacts (`models/`)

| File | Description |
|---|---|
| best_model.pkl | Serialized best-performing classifier (selected by ROC-AUC + recall) |
| scaler.pkl | Fitted StandardScaler for numeric features |
| encoders.pkl | Dict of fitted LabelEncoders per categorical feature |
| metadata.pkl | Feature column lists + selected model name |
| segmentation_model.pkl | Fitted KMeans + scaler + persona mapping |
| metrics.json | Full metric comparison across all 4 trained models |
