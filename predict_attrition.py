"""Predict employee attrition with logistic regression (implemented in NumPy) and evaluate it on a hold-out test set.

Run:  python predict_attrition.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "hr_attrition_raw.csv"
OUT = ROOT / "outputs"
SEED, TEST_SHARE, L2, STEPS, RATE = 42, 0.25, 0.01, 3000, 0.1
NUMERIC = ["Age", "MonthlyIncome", "YearsAtCompany", "TotalWorkingYears", "DistanceFromHome", "NumCompaniesWorked",
           "JobSatisfaction", "EnvironmentSatisfaction", "WorkLifeBalance", "JobLevel", "StockOptionLevel",
           "YearsSinceLastPromotion"]


def features(raw):
    X = raw[NUMERIC].astype(float).copy()
    X["OverTime"] = (raw.OverTime == "Yes").astype(float)
    X["Single"] = (raw.MaritalStatus == "Single").astype(float)
    X["TravelsFrequently"] = (raw.BusinessTravel == "Travel_Frequently").astype(float)
    X["SalesDepartment"] = (raw.Department == "Sales").astype(float)
    return X


def stratified_split(y, rng):
    test = np.zeros(len(y), dtype=bool)
    for cls in (0, 1):
        idx = rng.permutation(np.flatnonzero(y == cls))
        test[idx[: int(round(TEST_SHARE * len(idx)))]] = True
    return ~test, test


def fit_logistic(X, y):
    """Gradient descent on the L2-regularised log loss."""
    w, b = np.zeros(X.shape[1]), 0.0
    for _ in range(STEPS):
        p = 1 / (1 + np.exp(-(X @ w + b)))
        w -= RATE * (X.T @ (p - y) / len(y) + L2 * w)
        b -= RATE * np.mean(p - y)
    return w, b


def roc_auc(y, score):
    ranks = rankdata(score)
    pos = y == 1
    return (ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum())


def metrics(y, pred):
    tp, fp = int(((pred == 1) & (y == 1)).sum()), int(((pred == 1) & (y == 0)).sum())
    fn, tn = int(((pred == 0) & (y == 1)).sum()), int(((pred == 0) & (y == 0)).sum())
    precision, recall = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return {"accuracy": (tp + tn) / len(y), "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / max(precision + recall, 1e-9), "confusion": (tn, fp, fn, tp)}


def roc_curve(y, score):
    order = np.argsort(-score)
    tpr = np.cumsum(y[order] == 1) / (y == 1).sum()
    fpr = np.cumsum(y[order] == 0) / (y == 0).sum()
    return np.r_[0, fpr], np.r_[0, tpr]


def main():
    OUT.mkdir(exist_ok=True)
    raw = pd.read_csv(RAW)
    X_df, y = features(raw), (raw.Attrition == "Yes").to_numpy(int)
    train, test = stratified_split(y, np.random.default_rng(SEED))
    mean, std = X_df[train].mean(), X_df[train].std()  # scale with training statistics only
    X = ((X_df - mean) / std).to_numpy()

    w, b = fit_logistic(X[train], y[train])
    prob = 1 / (1 + np.exp(-(X[test] @ w + b)))
    auc = roc_auc(y[test], prob)
    at_half = metrics(y[test], (prob >= 0.5).astype(int))
    threshold = y[train].mean()  # flag anyone above the base attrition rate
    at_base = metrics(y[test], (prob >= threshold).astype(int))

    coef = pd.DataFrame({"feature": X_df.columns, "coefficient": w, "odds_ratio": np.exp(w)})
    coef = coef.reindex(coef.coefficient.abs().sort_values(ascending=False).index).round(3)
    coef.to_csv(OUT / "model_coefficients.csv", index=False)

    fpr, tpr = roc_curve(y[test], prob)
    plt.figure(figsize=(5.5, 5))
    plt.plot(fpr, tpr, color="#1F4E79", label=f"Logistic regression (AUC = {auc:.2f})")
    plt.plot([0, 1], [0, 1], color="#9CA3AF", linestyle="--", label="Random guess")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate (recall)")
    plt.title("ROC curve on the test set")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(OUT / "roc_curve.png", dpi=150)
    plt.close()

    def row(name, m):
        tn, fp, fn, tp = m["confusion"]
        return (f"{name:28s} accuracy {m['accuracy']:.3f}  precision {m['precision']:.3f}  recall {m['recall']:.3f}  "
                f"F1 {m['f1']:.3f}  (TP {tp}, FP {fp}, FN {fn}, TN {tn})")

    lines = [
        "ATTRITION PREDICTION - LOGISTIC REGRESSION", "=" * 60,
        f"Train / test: {train.sum()} / {test.sum()} employees (stratified, seed {SEED}); {X.shape[1]} features",
        f"Baseline accuracy (predict nobody leaves): {1 - y[test].mean():.3f}",
        f"ROC AUC on test set: {auc:.3f}",
        row("Threshold 0.50", at_half),
        row(f"Threshold {threshold:.2f} (base rate)", at_base),
        "", "Strongest drivers (standardised coefficients; odds ratio per 1 standard deviation)",
        coef.head(8).to_string(index=False),
    ]
    text = "\n".join(lines)
    (OUT / "model_summary.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
