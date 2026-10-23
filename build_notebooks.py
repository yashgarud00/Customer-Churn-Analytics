"""
build_notebooks.py -- generates notebooks/EDA.ipynb, FeatureEngineering.ipynb,
ModelTraining.ipynb as real, runnable Jupyter notebooks that mirror the
production scripts in src/, but in the exploratory notebook format
recruiters/interviewers expect to see in a Data Analyst portfolio.
Run once from the project root: python build_notebooks.py
"""
import nbformat as nbf

def make_notebook(cells, path):
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    }
    with open(path, "w") as f:
        nbf.write(nb, f)
    print(f"Wrote {path}")

def md(text): return nbf.v4.new_markdown_cell(text)
def code(text): return nbf.v4.new_code_cell(text)

# ============================== EDA.ipynb ==============================
eda_cells = [
md("# Exploratory Data Analysis — Customer Churn\n"
   "Interactive companion to `src/visualization/eda_report.py`. Run top to bottom.\n"
   "All business insights are written after each chart, matching the deliverable a "
   "Data Analyst would hand to a stakeholder."),
code("import pandas as pd\nimport matplotlib.pyplot as plt\nimport seaborn as sns\n"
     "sns.set_theme(style='whitegrid')\n"
     "%matplotlib inline\n\n"
     "df = pd.read_csv('../data/processed/telecom_customers_features.csv')\n"
     "df.shape"),
code("df.head()"),
md("## Churn Distribution"),
code("df['Churn'].value_counts(normalize=True).mul(100).round(1)"),
code("fig, ax = plt.subplots(figsize=(5,4))\n"
     "df['Churn'].value_counts().plot(kind='bar', color=['#2E86AB','#E63946'], ax=ax)\n"
     "ax.set_title('Churn Distribution'); plt.show()"),
md("**Insight:** Establishes the baseline churn rate the ML model must beat, and confirms "
   "class imbalance -- accuracy alone will be a misleading metric for evaluation."),
md("## Churn by Contract Type"),
code("ct = pd.crosstab(df['Contract'], df['Churn'], normalize='index') * 100\n"
     "ct.plot(kind='bar', stacked=True, figsize=(6,4), color=['#2E86AB','#E63946'])\n"
     "plt.title('Churn Rate by Contract Type'); plt.ylabel('%'); plt.show()\nct"),
md("**Insight:** Month-to-month contracts churn far more than annual/two-year commitments. "
   "This is the strongest single retention lever available to the business."),
md("## Correlation Matrix"),
code("numeric_cols = ['tenure','MonthlyCharges','TotalCharges','SupportTicketsLastYear',\n"
     "                'AvgMonthlySpend','ContractDurationMonths','TotalAddOnServices',\n"
     "                'CustomerValueScore','ChurnFlag']\n"
     "corr = df[numeric_cols].corr()\n"
     "plt.figure(figsize=(8,6))\n"
     "sns.heatmap(corr, annot=True, fmt='.2f', cmap='RdBu_r', center=0)\n"
     "plt.title('Correlation Matrix'); plt.show()"),
md("**Insight:** Tenure and contract duration are the strongest negative correlates of churn; "
   "monthly charges is a positive correlate. These guide feature selection in ModelTraining.ipynb."),
md("## Tenure vs Churn"),
code("plt.figure(figsize=(6,4))\n"
     "sns.boxplot(data=df, x='Churn', y='tenure')\n"
     "plt.title('Tenure by Churn Status'); plt.show()"),
md("**Insight:** Churned customers cluster at low tenure. The first 12 months are the "
   "highest-risk window for this business -- see Business_Recommendations.md for the "
   "resulting onboarding-focused retention strategy.\n\n"
   "Full chart set (10 total) and business writeups: see `reports/EDA_Report.md`."),
]
make_notebook(eda_cells, "notebooks/EDA.ipynb")

# ====================== FeatureEngineering.ipynb ========================
fe_cells = [
md("# Feature Engineering — Customer Churn\n"
   "Interactive companion to `src/preprocessing/feature_engineering.py`."),
code("import pandas as pd\nimport numpy as np\n\n"
     "df = pd.read_csv('../data/cleaned/telecom_customers_cleaned.csv')\ndf.shape"),
md("## 1. Average Monthly Spend\nTotalCharges / tenure, guarding against divide-by-zero for brand new customers."),
code("df['AvgMonthlySpend'] = np.where(df['tenure'] > 0, df['TotalCharges']/df['tenure'], df['MonthlyCharges'])\n"
     "df[['tenure','TotalCharges','AvgMonthlySpend']].head()"),
md("## 2. Customer Lifecycle Stage\nTenure-based bucket (this dataset has no literal customer age field)."),
code("df['CustomerLifecycleStage'] = pd.cut(df['tenure'], bins=[-1,6,12,24,48,200],\n"
     "    labels=['New (0-6mo)','Ramping (7-12mo)','Established (13-24mo)','Mature (25-48mo)','Veteran (49mo+)'])\n"
     "df['CustomerLifecycleStage'].value_counts()"),
md("## 3. Contract Duration (numeric) & Auto-Pay Flag"),
code("df['ContractDurationMonths'] = df['Contract'].map({'Month-to-month':1,'One year':12,'Two year':24})\n"
     "df['IsAutoPay'] = df['PaymentMethod'].isin(['Bank transfer (automatic)','Credit card (automatic)']).astype(int)\n"
     "df[['Contract','ContractDurationMonths','PaymentMethod','IsAutoPay']].head()"),
md("## 4. Customer Value Score (0-100)\nWeighted blend: 50% spend, 30% tenure, 20% contract commitment."),
code("def normalize(s): return (s - s.min())/(s.max()-s.min()+1e-9)\n\n"
     "df['CustomerValueScore'] = (\n"
     "    0.5*normalize(df['MonthlyCharges'])*100 +\n"
     "    0.3*normalize(df['tenure'])*100 +\n"
     "    0.2*df['ContractDurationMonths'].map({1:20,12:60,24:100})\n"
     ").round(2)\n"
     "df['CustomerValueScore'].describe()"),
md("## 5. Service Depth & Risk Flags"),
code("addon_cols = ['OnlineSecurity','OnlineBackup','DeviceProtection','TechSupport','StreamingTV','StreamingMovies']\n"
     "df['TotalAddOnServices'] = df[addon_cols].apply(lambda c: (c=='Yes').astype(int)).sum(axis=1)\n"
     "df['HasInternetNoProtection'] = ((df['InternetService']!='No') & (df['OnlineSecurity']=='No') & (df['TechSupport']=='No')).astype(int)\n"
     "df[['TotalAddOnServices','HasInternetNoProtection']].describe()"),
md("Full 11-feature pipeline (including target encoding) is in "
   "`src/preprocessing/feature_engineering.py` — this notebook demonstrates the "
   "reasoning behind each feature for a portfolio review; the script is the source of truth "
   "used by the production pipeline."),
]
make_notebook(fe_cells, "notebooks/FeatureEngineering.ipynb")

# ========================= ModelTraining.ipynb ==========================
mt_cells = [
md("# Model Training & Comparison — Customer Churn\n"
   "Interactive companion to `src/modeling/train_models.py`. "
   "Trains 4 classifiers and compares them on the full metric suite."),
code("import pandas as pd, numpy as np\n"
     "from sklearn.model_selection import train_test_split\n"
     "from sklearn.preprocessing import StandardScaler, LabelEncoder\n"
     "from sklearn.linear_model import LogisticRegression\n"
     "from sklearn.tree import DecisionTreeClassifier\n"
     "from sklearn.ensemble import RandomForestClassifier\n"
     "from xgboost import XGBClassifier\n"
     "from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score\n\n"
     "df = pd.read_csv('../data/processed/telecom_customers_features.csv')\ndf.shape"),
md("## Prepare features"),
code("feature_cols = ['tenure','MonthlyCharges','TotalCharges','SupportTicketsLastYear',\n"
     "    'ContractDurationMonths','TotalAddOnServices','CustomerValueScore','IsAutoPay',\n"
     "    'HasInternetNoProtection','IsMultiServiceHousehold','SeniorCitizen','gender',\n"
     "    'Partner','Dependents','InternetService','Contract','PaymentMethod','PaperlessBilling']\n"
     "X = df[feature_cols].copy(); y = df['ChurnFlag']\n"
     "cat_cols = X.select_dtypes(include='object').columns.tolist()\n"
     "for c in cat_cols:\n"
     "    X[c] = LabelEncoder().fit_transform(X[c].astype(str))\n"
     "num_cols = [c for c in feature_cols if c not in cat_cols]\n"
     "X[num_cols] = StandardScaler().fit_transform(X[num_cols])\n"
     "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)\n"
     "X_train.shape, X_test.shape"),
md("## Train & compare 4 models"),
code("models = {\n"
     "    'Logistic Regression': LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42),\n"
     "    'Decision Tree': DecisionTreeClassifier(max_depth=6, class_weight='balanced', random_state=42),\n"
     "    'Random Forest': RandomForestClassifier(n_estimators=300, max_depth=10, class_weight='balanced', random_state=42, n_jobs=-1),\n"
     "    'XGBoost': XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05,\n"
     "        scale_pos_weight=(y_train==0).sum()/(y_train==1).sum(), eval_metric='logloss', random_state=42),\n"
     "}\n\n"
     "results = []\n"
     "for name, model in models.items():\n"
     "    model.fit(X_train, y_train)\n"
     "    pred = model.predict(X_test)\n"
     "    proba = model.predict_proba(X_test)[:,1]\n"
     "    results.append({'model': name, 'accuracy': accuracy_score(y_test,pred),\n"
     "        'precision': precision_score(y_test,pred), 'recall': recall_score(y_test,pred),\n"
     "        'f1': f1_score(y_test,pred), 'roc_auc': roc_auc_score(y_test,proba)})\n\n"
     "results_df = pd.DataFrame(results).sort_values('roc_auc', ascending=False).round(4)\n"
     "results_df"),
md("## Model selection rationale\n"
   "The model with the highest ROC-AUC is selected, tie-broken by recall — in this "
   "business, a **missed churner (false negative) costs far more** than an unnecessary "
   "retention offer (false positive), so recall is weighted heavily.\n\n"
   "Full training pipeline (with persisted artifacts, confusion matrices, ROC curves, and "
   "feature importance plots) lives in `src/modeling/train_models.py` and produces "
   "`reports/Model_Comparison_Report.md`."),
]
make_notebook(mt_cells, "notebooks/ModelTraining.ipynb")

print("All notebooks built.")
