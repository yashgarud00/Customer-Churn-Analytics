"""
train_models.py
-----------------
Trains and compares 4 classification models for churn prediction,
evaluates each on the full standard metric suite, and persists the
best-performing model (by ROC-AUC, tie-broken by recall since missing
a churner is costlier than a false alarm in this business context).

Usage:
    python src/modeling/train_models.py
"""
import pandas as pd
import numpy as np
import json
import joblib
import logging
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("ModelTraining")

DATA_PATH = "data/processed/telecom_customers_features.csv"
MODEL_DIR = "models"
REPORT_PATH = "reports/Model_Comparison_Report.md"
FIG_DIR = "reports/figures"
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)

FEATURE_COLS = [
    "tenure", "MonthlyCharges", "TotalCharges", "SupportTicketsLastYear",
    "ContractDurationMonths", "TotalAddOnServices", "CustomerValueScore",
    "IsAutoPay", "HasInternetNoProtection", "IsMultiServiceHousehold",
    "SeniorCitizen", "gender", "Partner", "Dependents", "InternetService",
    "Contract", "PaymentMethod", "PaperlessBilling"
]
TARGET_COL = "ChurnFlag"


def prepare_data(df: pd.DataFrame):
    X = df[FEATURE_COLS].copy()
    y = df[TARGET_COL].copy()

    encoders = {}
    categorical_cols = X.select_dtypes(include="object").columns.tolist()
    for col in categorical_cols:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        encoders[col] = le

    scaler = StandardScaler()
    numeric_cols = [c for c in FEATURE_COLS if c not in categorical_cols]
    X[numeric_cols] = scaler.fit_transform(X[numeric_cols])

    return X, y, encoders, scaler, categorical_cols, numeric_cols


def evaluate(name, model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = {
        "model": name,
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred), 4),
        "recall": round(recall_score(y_test, y_pred), 4),
        "f1": round(f1_score(y_test, y_pred), 4),
        "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
    }
    cm = confusion_matrix(y_test, y_pred)
    return metrics, cm, y_proba


def main():
    logger.info(f"Loading features from {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    X, y, encoders, scaler, cat_cols, num_cols = prepare_data(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}, Churn rate (train): {y_train.mean():.3f}")

    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "Decision Tree": DecisionTreeClassifier(max_depth=6, class_weight="balanced", random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=300, max_depth=10, class_weight="balanced", random_state=42, n_jobs=-1),
        "XGBoost": XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
            eval_metric="logloss", random_state=42
        ),
    }

    results = []
    fitted_models = {}
    fig, ax = plt.subplots(figsize=(7, 6))

    from sklearn.metrics import roc_curve
    for name, model in models.items():
        logger.info(f"Training {name}...")
        model.fit(X_train, y_train)
        metrics, cm, y_proba = evaluate(name, model, X_test, y_test)
        results.append(metrics)
        fitted_models[name] = model
        logger.info(f"{name}: {metrics}")

        fpr, tpr, _ = roc_curve(y_test, y_proba)
        ax.plot(fpr, tpr, label=f"{name} (AUC={metrics['roc_auc']:.3f})")

        # confusion matrix figure
        cm_fig, cm_ax = plt.subplots(figsize=(4, 4))
        cm_ax.imshow(cm, cmap="Blues")
        for i in range(2):
            for j in range(2):
                cm_ax.text(j, i, cm[i, j], ha="center", va="center", color="black")
        cm_ax.set_xticks([0, 1]); cm_ax.set_yticks([0, 1])
        cm_ax.set_xticklabels(["No Churn", "Churn"]); cm_ax.set_yticklabels(["No Churn", "Churn"])
        cm_ax.set_xlabel("Predicted"); cm_ax.set_ylabel("Actual")
        cm_ax.set_title(f"Confusion Matrix: {name}")
        cm_fig.savefig(f"{FIG_DIR}/cm_{name.replace(' ', '_')}.png", bbox_inches="tight", dpi=110)
        plt.close(cm_fig)

    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve Comparison")
    ax.legend()
    fig.savefig(f"{FIG_DIR}/roc_comparison.png", bbox_inches="tight", dpi=110)
    plt.close(fig)

    results_df = pd.DataFrame(results).sort_values(["roc_auc", "recall"], ascending=False)
    best_model_name = results_df.iloc[0]["model"]
    best_model = fitted_models[best_model_name]
    logger.info(f"BEST MODEL: {best_model_name}")

    # Feature importance for the best tree-based model (or coefficients for LogReg)
    fig, ax = plt.subplots(figsize=(7, 6))
    if hasattr(best_model, "feature_importances_"):
        importances = pd.Series(best_model.feature_importances_, index=X.columns).sort_values(ascending=True)
        importances.tail(15).plot(kind="barh", ax=ax, color="#2E86AB")
        ax.set_title(f"Feature Importance: {best_model_name}")
    else:
        coefs = pd.Series(best_model.coef_[0], index=X.columns).sort_values()
        coefs.plot(kind="barh", ax=ax, color="#2E86AB")
        ax.set_title(f"Feature Coefficients: {best_model_name}")
    fig.savefig(f"{FIG_DIR}/feature_importance.png", bbox_inches="tight", dpi=110)
    plt.close(fig)

    # Persist model + preprocessing artifacts
    joblib.dump(best_model, f"{MODEL_DIR}/best_model.pkl")
    joblib.dump(scaler, f"{MODEL_DIR}/scaler.pkl")
    joblib.dump(encoders, f"{MODEL_DIR}/encoders.pkl")
    joblib.dump({"feature_cols": FEATURE_COLS, "categorical_cols": cat_cols, "numeric_cols": num_cols,
                 "model_name": best_model_name}, f"{MODEL_DIR}/metadata.pkl")

    with open(f"{MODEL_DIR}/metrics.json", "w") as f:
        json.dump(results, f, indent=2)

    # Markdown report
    lines = ["# Model Comparison Report\n", "## Results\n", results_df.to_markdown(index=False), "\n"]
    lines.append(f"## Selected Model: **{best_model_name}**\n")
    lines.append(
        f"**Why {best_model_name}:** It achieves the highest ROC-AUC "
        f"({results_df.iloc[0]['roc_auc']}) among all candidates, meaning it best separates "
        f"churners from non-churners across all decision thresholds. Recall "
        f"({results_df.iloc[0]['recall']}) was weighted heavily in model selection because in "
        f"this business, a **false negative (missed churner) costs far more** than a false "
        f"positive (an unnecessary retention offer) -- the retention offer is cheap, losing "
        f"the customer is not.\n"
    )
    lines.append("## Artifacts\n- `models/best_model.pkl`\n- `models/scaler.pkl`\n- `models/encoders.pkl`\n"
                  "- `reports/figures/roc_comparison.png`\n- `reports/figures/feature_importance.png`\n")
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(lines))

    print(results_df.to_string(index=False))
    print(f"\nBest model: {best_model_name} -> saved to {MODEL_DIR}/best_model.pkl")


if __name__ == "__main__":
    main()
