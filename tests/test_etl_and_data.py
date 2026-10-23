"""
test_etl_and_data.py
----------------------
Data validation & ETL correctness tests. Run: pytest tests/ -v
"""
import pandas as pd
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

CLEANED_PATH = "data/cleaned/telecom_customers_cleaned.csv"
FEATURES_PATH = "data/processed/telecom_customers_features.csv"
SEGMENTED_PATH = "data/processed/telecom_customers_segmented.csv"


@pytest.fixture(scope="module")
def cleaned_df():
    if not os.path.exists(CLEANED_PATH):
        pytest.skip("Run the ETL pipeline first: python src/ETL/etl_pipeline.py")
    return pd.read_csv(CLEANED_PATH)


@pytest.fixture(scope="module")
def features_df():
    if not os.path.exists(FEATURES_PATH):
        pytest.skip("Run feature engineering first: python src/preprocessing/feature_engineering.py")
    return pd.read_csv(FEATURES_PATH)


class TestCleanedData:
    def test_no_duplicate_customer_ids(self, cleaned_df):
        assert cleaned_df["customerID"].is_unique

    def test_churn_only_yes_no(self, cleaned_df):
        assert set(cleaned_df["Churn"].unique()) <= {"Yes", "No"}

    def test_no_negative_tenure(self, cleaned_df):
        assert (cleaned_df["tenure"] >= 0).all()

    def test_no_negative_charges(self, cleaned_df):
        assert (cleaned_df["MonthlyCharges"] >= 0).all()
        assert (cleaned_df["TotalCharges"] >= 0).all()

    def test_total_charges_is_numeric(self, cleaned_df):
        assert pd.api.types.is_numeric_dtype(cleaned_df["TotalCharges"])

    def test_no_nulls_in_key_columns(self, cleaned_df):
        key_cols = ["customerID", "Churn", "MonthlyCharges", "tenure", "Contract"]
        for col in key_cols:
            assert cleaned_df[col].isnull().sum() == 0, f"{col} has null values"

    def test_gender_standardized(self, cleaned_df):
        assert set(cleaned_df["gender"].unique()) <= {"Male", "Female"}


class TestFeatureEngineering:
    def test_churn_flag_binary(self, features_df):
        assert set(features_df["ChurnFlag"].unique()) <= {0, 1}

    def test_customer_value_score_range(self, features_df):
        assert features_df["CustomerValueScore"].between(0, 100).all()

    def test_total_addon_services_range(self, features_df):
        assert features_df["TotalAddOnServices"].between(0, 6).all()

    def test_is_autopay_binary(self, features_df):
        assert set(features_df["IsAutoPay"].unique()) <= {0, 1}

    def test_no_infinite_values(self, features_df):
        numeric_df = features_df.select_dtypes(include=[np.number])
        assert not np.isinf(numeric_df.to_numpy()).any()


class TestSegmentation:
    @pytest.fixture(scope="class")
    def segmented_df(self):
        if not os.path.exists(SEGMENTED_PATH):
            pytest.skip("Run segmentation first: python src/modeling/customer_segmentation.py")
        return pd.read_csv(SEGMENTED_PATH)

    def test_every_customer_has_persona(self, segmented_df):
        assert segmented_df["Persona"].isnull().sum() == 0

    def test_cluster_ids_valid(self, segmented_df):
        assert segmented_df["ClusterID"].between(0, 10).all()
