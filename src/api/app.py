"""
app.py
-------
Flask REST API for the Customer Churn Analytics Platform.

Endpoints:
    POST /predict            -> single or batch churn prediction
    GET  /customers           -> paginated customer listing with filters
    GET  /customers/<id>       -> single customer 360 view
    GET  /analytics              -> aggregate KPIs (churn rate, MRR, at-risk revenue)
    GET  /analytics/segments      -> persona/segment summary
    GET  /dashboard                -> pre-aggregated payload for the web dashboard
    GET  /health                     -> liveness check

Run locally:
    python src/api/app.py
Run in Docker:
    see Docker/Dockerfile.api + docker-compose.yml
"""
import os
import logging
import joblib
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("API")

app = Flask(__name__)
CORS(app)

MODEL_DIR = os.getenv("MODEL_DIR", "models")
DATA_PATH = os.getenv("SEGMENTED_DATA_PATH", "data/processed/telecom_customers_segmented.csv")

# --------------------------------------------------------------------------
# Load artifacts once at startup (not per-request -- production practice)
# --------------------------------------------------------------------------
try:
    model = joblib.load(os.path.join(MODEL_DIR, "best_model.pkl"))
    scaler = joblib.load(os.path.join(MODEL_DIR, "scaler.pkl"))
    encoders = joblib.load(os.path.join(MODEL_DIR, "encoders.pkl"))
    metadata = joblib.load(os.path.join(MODEL_DIR, "metadata.pkl"))
    logger.info(f"Loaded model: {metadata['model_name']}")
except FileNotFoundError:
    model = scaler = encoders = metadata = None
    logger.warning("Model artifacts not found -- run src/modeling/train_models.py first. "
                    "/predict will return 503 until then.")

try:
    df_customers = pd.read_csv(DATA_PATH)
    logger.info(f"Loaded {len(df_customers)} customers for lookup endpoints")
except FileNotFoundError:
    df_customers = pd.DataFrame()
    logger.warning(f"{DATA_PATH} not found -- run the full pipeline first.")


def preprocess_input(record: dict) -> pd.DataFrame:
    """Applies the same encoding/scaling pipeline used at training time."""
    row = pd.DataFrame([record])[metadata["feature_cols"]]
    for col in metadata["categorical_cols"]:
        le = encoders[col]
        row[col] = row[col].astype(str).apply(lambda v: v if v in le.classes_ else le.classes_[0])
        row[col] = le.transform(row[col])
    row[metadata["numeric_cols"]] = scaler.transform(row[metadata["numeric_cols"]])
    return row


def risk_segment(prob: float) -> str:
    if prob >= 0.66:
        return "High"
    if prob >= 0.33:
        return "Medium"
    return "Low"


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": model is not None,
        "data_loaded": not df_customers.empty,
    })


@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return jsonify({"error": "Model not loaded. Run the training pipeline first."}), 503

    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({"error": "Request body must be JSON."}), 400

    records = payload if isinstance(payload, list) else [payload]
    missing_fields = [f for f in metadata["feature_cols"] if any(f not in r for r in records)]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {sorted(set(missing_fields))}"}), 400

    try:
        results = []
        for record in records:
            X = preprocess_input(record)
            prob = float(model.predict_proba(X)[0, 1])
            results.append({
                "customerID": record.get("customerID", "N/A"),
                "churn_probability": round(prob, 4),
                "risk_segment": risk_segment(prob),
                "model_version": metadata["model_name"],
            })
        return jsonify(results if isinstance(payload, list) else results[0])
    except Exception as e:
        logger.exception("Prediction failed")
        return jsonify({"error": str(e)}), 400


@app.route("/customers", methods=["GET"])
def list_customers():
    if df_customers.empty:
        return jsonify({"error": "No customer data loaded."}), 503

    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 25)), 200)
    region = request.args.get("region")
    contract = request.args.get("contract")
    churn = request.args.get("churn")

    df = df_customers
    if region:
        df = df[df["Region"].str.lower() == region.lower()]
    if contract:
        df = df[df["Contract"].str.lower() == contract.lower()]
    if churn is not None:
        df = df[df["Churn"].str.lower() == churn.lower()]

    total = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start:start + page_size]

    cols = ["customerID", "gender", "Region", "Contract", "MonthlyCharges", "tenure", "Churn", "Persona"]
    return jsonify({
        "page": page, "page_size": page_size, "total": total,
        "customers": page_df[cols].to_dict(orient="records"),
    })


@app.route("/customers/<customer_id>", methods=["GET"])
def get_customer(customer_id):
    if df_customers.empty:
        return jsonify({"error": "No customer data loaded."}), 503
    row = df_customers[df_customers["customerID"] == customer_id]
    if row.empty:
        return jsonify({"error": f"Customer {customer_id} not found."}), 404
    return jsonify(row.iloc[0].to_dict())


@app.route("/analytics", methods=["GET"])
def analytics():
    if df_customers.empty:
        return jsonify({"error": "No customer data loaded."}), 503

    df = df_customers
    churn_rate = round((df["Churn"] == "Yes").mean() * 100, 2)
    total_mrr = round(df["MonthlyCharges"].sum(), 2)
    arpu = round(df["MonthlyCharges"].mean(), 2)
    at_risk_mrr = round(df.loc[df["Churn"] == "Yes", "MonthlyCharges"].sum(), 2)

    by_contract = (
        df.groupby("Contract")
        .agg(customers=("customerID", "count"), churn_rate_pct=("Churn", lambda x: round((x == "Yes").mean() * 100, 2)))
        .reset_index().to_dict(orient="records")
    )
    by_region = (
        df.groupby("Region")
        .agg(customers=("customerID", "count"), mrr=("MonthlyCharges", "sum"),
             churn_rate_pct=("Churn", lambda x: round((x == "Yes").mean() * 100, 2)))
        .reset_index().to_dict(orient="records")
    )

    return jsonify({
        "total_customers": len(df),
        "overall_churn_rate_pct": churn_rate,
        "total_mrr": total_mrr,
        "arpu": arpu,
        "at_risk_mrr_actual_churned": at_risk_mrr,
        "by_contract": by_contract,
        "by_region": by_region,
    })


@app.route("/analytics/segments", methods=["GET"])
def analytics_segments():
    if df_customers.empty or "Persona" not in df_customers.columns:
        return jsonify({"error": "Segmentation data not available."}), 503
    summary = (
        df_customers.groupby("Persona")
        .agg(customers=("customerID", "count"),
             avg_tenure=("tenure", "mean"),
             avg_monthly_charges=("MonthlyCharges", "mean"),
             churn_rate_pct=("Churn", lambda x: round((x == "Yes").mean() * 100, 2)))
        .round(2).reset_index().to_dict(orient="records")
    )
    return jsonify(summary)


@app.route("/dashboard", methods=["GET"])
def dashboard_payload():
    """Single aggregated payload the web dashboard fetches on load."""
    if df_customers.empty:
        return jsonify({"error": "No customer data loaded."}), 503
    df = df_customers

    churn_by_contract = (
        df.groupby("Contract")["Churn"].apply(lambda x: round((x == "Yes").mean() * 100, 2)).to_dict()
    )
    churn_by_region = (
        df.groupby("Region")["Churn"].apply(lambda x: round((x == "Yes").mean() * 100, 2)).to_dict()
    )
    persona_counts = df["Persona"].value_counts().to_dict() if "Persona" in df.columns else {}
    tenure_hist = np.histogram(df["tenure"], bins=10)
    charges_hist = np.histogram(df["MonthlyCharges"], bins=10)

    return jsonify({
        "kpis": {
            "total_customers": len(df),
            "churn_rate_pct": round((df["Churn"] == "Yes").mean() * 100, 2),
            "total_mrr": round(df["MonthlyCharges"].sum(), 2),
            "arpu": round(df["MonthlyCharges"].mean(), 2),
        },
        "churn_by_contract": churn_by_contract,
        "churn_by_region": churn_by_region,
        "persona_distribution": persona_counts,
        "tenure_histogram": {"counts": tenure_hist[0].tolist(), "bins": tenure_hist[1].tolist()},
        "charges_histogram": {"counts": charges_hist[0].tolist(), "bins": charges_hist[1].tolist()},
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
