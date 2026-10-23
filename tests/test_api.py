"""
test_api.py
-------------
Flask API endpoint tests using the test client (no live server needed).
Run: pytest tests/test_api.py -v
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

MODEL_EXISTS = os.path.exists("models/best_model.pkl")


@pytest.fixture
def client():
    from src.api.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data


@pytest.mark.skipif(not MODEL_EXISTS, reason="Model not trained yet")
def test_predict_requires_json(client):
    resp = client.post("/predict", data="not json", content_type="text/plain")
    assert resp.status_code == 400


@pytest.mark.skipif(not MODEL_EXISTS, reason="Model not trained yet")
def test_predict_missing_fields(client):
    resp = client.post("/predict", json={"customerID": "X"})
    assert resp.status_code == 400


@pytest.mark.skipif(not MODEL_EXISTS, reason="Model not trained yet")
def test_predict_valid_payload(client):
    payload = {
        "customerID": "TEST-001", "tenure": 5, "MonthlyCharges": 80.0, "TotalCharges": 400.0,
        "SupportTicketsLastYear": 2, "ContractDurationMonths": 1, "TotalAddOnServices": 1,
        "CustomerValueScore": 50.0, "IsAutoPay": 0, "HasInternetNoProtection": 1,
        "IsMultiServiceHousehold": 0, "SeniorCitizen": 0, "gender": "Male", "Partner": "No",
        "Dependents": "No", "InternetService": "Fiber optic", "Contract": "Month-to-month",
        "PaymentMethod": "Electronic check", "PaperlessBilling": "Yes",
    }
    resp = client.post("/predict", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 0 <= data["churn_probability"] <= 1
    assert data["risk_segment"] in ("Low", "Medium", "High")


def test_customers_endpoint_pagination(client):
    resp = client.get("/customers?page=1&page_size=5")
    if resp.status_code == 503:
        pytest.skip("No customer data loaded")
    data = resp.get_json()
    assert len(data["customers"]) <= 5


def test_customer_not_found(client):
    resp = client.get("/customers/DOES-NOT-EXIST")
    assert resp.status_code in (404, 503)


def test_analytics_endpoint(client):
    resp = client.get("/analytics")
    if resp.status_code == 503:
        pytest.skip("No customer data loaded")
    data = resp.get_json()
    assert "overall_churn_rate_pct" in data
    assert 0 <= data["overall_churn_rate_pct"] <= 100
