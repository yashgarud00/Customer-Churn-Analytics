# Installation Guide

## Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional, for the production-shaped setup)
- PostgreSQL 16 (optional — SQLite is used automatically if `DATABASE_URL` is unset)

## 1. Clone & set up the environment

```bash
git clone <your-repo-url>
cd Customer-Churn-Analytics
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Run the data pipeline (in order)

```bash
python src/ETL/generate_raw_data.py --n_customers 12000 --seed 42
python src/ETL/etl_pipeline.py
python src/preprocessing/feature_engineering.py
python src/visualization/eda_report.py
python src/visualization/statistical_analysis.py
python src/modeling/train_models.py
python src/modeling/customer_segmentation.py
python src/visualization/build_dashboard_snapshot.py
```

Each step logs its progress to stdout and `logs/etl.log`. Expect this full
sequence to take under a minute on a laptop.

## 3. Start the API

```bash
python app.py
# API now live at http://localhost:5000 — try http://localhost:5000/health
```

For production, use Gunicorn instead of the Flask dev server:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

## 4. Open the dashboard

Just open `dashboard/index.html` in a browser — it reads the bundled
`dashboard_data.json` snapshot, no server required.

## 5. (Optional) Set up PostgreSQL for the full SQL layer

```bash
createdb churn_db
psql -d churn_db -f database/schema.sql
psql -d churn_db -f database/views.sql
psql -d churn_db -f database/procedures.sql

# Point the ETL at Postgres instead of SQLite:
export DATABASE_URL=postgresql://youruser:yourpass@localhost:5432/churn_db
python src/ETL/etl_pipeline.py

# Normalize the flat staging table into the star schema:
psql -d churn_db -c "SELECT churn_analytics.normalize_staging_to_star();"

# Try the 50+ analytical queries:
psql -d churn_db -f database/analytical_queries.sql
```

## 6. (Optional) Run everything in Docker

```bash
docker compose up --build
```

This starts PostgreSQL, runs the ETL as a one-off job, and starts the API
container with a healthcheck — no local Python environment needed at all.

## 7. Run the test suite

```bash
pip install pytest
pytest tests/ -v
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` on run | Make sure your virtualenv is activated and `pip install -r requirements.txt` completed |
| `/predict` returns 503 | Run `python src/modeling/train_models.py` first to generate `models/best_model.pkl` |
| Dashboard shows no data | Run `python src/visualization/build_dashboard_snapshot.py` after the pipeline |
| SQLite "unable to open database file" | Ensure the `database/` directory exists (the ETL script creates it automatically as of this version) |
| Docker build fails on `psycopg2` | The Dockerfiles install `libpq-dev` — if building outside Docker, install PostgreSQL client dev headers locally (`apt install libpq-dev` / `brew install postgresql`) |
