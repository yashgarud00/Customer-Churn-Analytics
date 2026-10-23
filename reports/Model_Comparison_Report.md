# Model Comparison Report

## Results

| model               |   accuracy |   precision |   recall |     f1 |   roc_auc |
|:--------------------|-----------:|------------:|---------:|-------:|----------:|
| Logistic Regression |     0.7067 |      0.7826 |   0.7124 | 0.7458 |    0.7884 |
| Random Forest       |     0.7092 |      0.769  |   0.7414 | 0.7549 |    0.7819 |
| XGBoost             |     0.7063 |      0.7841 |   0.709  | 0.7447 |    0.7789 |
| Decision Tree       |     0.6954 |      0.7837 |   0.6848 | 0.731  |    0.7739 |


## Selected Model: **Logistic Regression**

**Why Logistic Regression:** It achieves the highest ROC-AUC (0.7884) among all candidates, meaning it best separates churners from non-churners across all decision thresholds. Recall (0.7124) was weighted heavily in model selection because in this business, a **false negative (missed churner) costs far more** than a false positive (an unnecessary retention offer) -- the retention offer is cheap, losing the customer is not.

## Artifacts
- `models/best_model.pkl`
- `models/scaler.pkl`
- `models/encoders.pkl`
- `reports/figures/roc_comparison.png`
- `reports/figures/feature_importance.png`
