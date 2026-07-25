"""
train_models.py — Unified ML Model Trainer (Hardened)
=======================================================
Trains, evaluates, and saves:
  1. Attack Type Classifier  (models/attack_prediction_model.pkl)
  2. Threat Level Classifier (models/threat_prediction_model.pkl)
  3. Pre-computed TSI Calibration Bounds (models/tsi_bounds.json)
  4. Detailed Model Metrics  (models/metrics.json)

Design decisions
----------------
- Train/test split: TIME-ORDERED sequential (80/20 chronological).
  This is the only honest evaluation for an operational model: you
  train on past data and test on future data, not random shuffles.
- Encoding: OrdinalEncoder instead of TargetEncoder to eliminate
  target-leakage risk in the encoding step.
- Regularization: max_depth and min_samples_leaf limits prevent the
  RF from memorising a small dataset.
- Cross-validation: 5-fold StratifiedKFold reported alongside the
  held-out test metrics for a bias/variance estimate.
- Metrics: per-class precision/recall/F1, confusion matrix, and an
  explicit overfitting check (train vs test gap) are saved to
  models/metrics.json for inspection.
"""

import json
import os
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder

warnings.filterwarnings("ignore")


def _load_and_clean(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="latin1", low_memory=False)
    print(f"  Loaded {len(df)} rows, years {int(df.iyear.min())}–{int(df.iyear.max())}")

    # Warn if this looks like synthetic dummy data (perfectly balanced classes)
    if "attacktype1_txt" in df.columns:
        dist = df["attacktype1_txt"].value_counts()
        if len(dist) > 3:
            cv_ratio = dist.std() / dist.mean()
            if cv_ratio < 0.15 and len(df) < 5000:
                print()
                print("  ⚠️  WARNING: class distribution is near-uniform (CV ratio = "
                      f"{cv_ratio:.3f}) with only {len(df)} rows.")
                print("     This looks like synthetic/dummy data.")
                print("     Real GTD has ~180,000 rows with heavy class imbalance.")
                print("     Model performance will be near-random until the full GTD")
                print("     CSV is loaded at data/globalterrorism.csv.")
                print()
    return df


def train_all():
    os.makedirs("models", exist_ok=True)
    csv_path = "data/globalterrorism.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at '{csv_path}'.")

    print(f"Loading GTD Dataset from {csv_path}...")
    df = _load_and_clean(csv_path)

    metrics: dict = {}

    # =========================================================================
    # 1. TSI Calibration Bounds Export
    # =========================================================================
    print("\n--- Computing TSI Calibration Bounds ---")
    nkill  = pd.to_numeric(df.get("nkill",  pd.Series(0, index=df.index)), errors="coerce").fillna(0).clip(lower=0)
    nwound = pd.to_numeric(df.get("nwound", pd.Series(0, index=df.index)), errors="coerce").fillna(0).clip(lower=0)
    success = pd.to_numeric(df.get("success", pd.Series(1, index=df.index)), errors="coerce").fillna(0).clip(0, 1)
    claimed = pd.to_numeric(df.get("claimed", pd.Series(0, index=df.index)), errors="coerce").fillna(0).clip(0, 1)

    tsi_raw = (0.50 * np.log1p(nkill) + 0.30 * np.log1p(nwound) + 0.15 * success + 0.05 * claimed)
    bounds = {"min": float(tsi_raw.min()), "max": float(tsi_raw.max())}
    with open("models/tsi_bounds.json", "w") as f:
        json.dump(bounds, f, indent=2)
    print(f"  TSI Bounds saved: {bounds}")

    # =========================================================================
    # 2. Attack Type Prediction Model
    # =========================================================================
    print("\n--- Training Attack Type Prediction Model ---")
    cat_cols = ["country_txt", "region_txt", "weaptype1_txt", "targtype1_txt", "gname"]
    num_cols = ["iyear", "success", "suicide", "nkill", "nwound"]
    target   = "attacktype1_txt"

    df_atk = df.dropna(subset=[target]).copy()
    df_atk = df_atk[~df_atk[target].astype(str).str.strip().isin(["", "Unknown", "unknown"])].copy()
    df_atk = df_atk.sort_values(["iyear", "imonth", "iday"])  # time-ordered

    X = df_atk[cat_cols + num_cols].copy()
    y = df_atk[target].astype(str).copy()

    n = len(X)
    split_idx = int(n * 0.8)
    X_tr, X_te = X.iloc[:split_idx].copy(), X.iloc[split_idx:].copy()
    y_tr, y_te = y.iloc[:split_idx].copy(), y.iloc[split_idx:].copy()

    year_col = "iyear"
    train_years = df_atk.iloc[:split_idx][year_col].agg(["min", "max"]).tolist()
    test_years  = df_atk.iloc[split_idx:][year_col].agg(["min", "max"]).tolist()
    print(f"  Train: {split_idx} rows  ({int(train_years[0])}–{int(train_years[1])})")
    print(f"  Test:  {n - split_idx} rows  ({int(test_years[0])}–{int(test_years[1])})")

    # Leakage check
    tr_hash = set(pd.util.hash_pandas_object(X_tr, index=False))
    te_hash = set(pd.util.hash_pandas_object(X_te, index=False))
    overlap = len(tr_hash & te_hash)
    print(f"  Identical rows in both sets: {overlap}  {'✓ clean' if overlap == 0 else '⚠️ LEAKAGE'}")

    # Impute
    cat_imp = SimpleImputer(strategy="constant", fill_value="Unknown")
    X_tr[cat_cols] = cat_imp.fit_transform(X_tr[cat_cols])
    X_te[cat_cols] = cat_imp.transform(X_te[cat_cols])

    num_imp = SimpleImputer(strategy="median")
    X_tr[num_cols] = num_imp.fit_transform(X_tr[num_cols])
    X_te[num_cols] = num_imp.transform(X_te[num_cols])

    # Encode — OrdinalEncoder (no target leakage)
    oe = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    X_tr_cat = oe.fit_transform(X_tr[cat_cols])
    X_te_cat = oe.transform(X_te[cat_cols])
    X_tr_f = np.hstack([X_tr_cat, X_tr[num_cols].values])
    X_te_f = np.hstack([X_te_cat, X_te[num_cols].values])

    le_target = LabelEncoder()
    le_target.fit(y)
    y_tr_enc = le_target.transform(y_tr)
    y_te_enc = le_target.transform(y_te)
    X_full_f  = np.vstack([X_tr_f, X_te_f])
    y_full_enc = np.concatenate([y_tr_enc, y_te_enc])

    # ─── Class distribution ────────────────────────────────────────────────
    print("\n  Class distribution (training set):")
    dist = pd.Series(y_tr).value_counts()
    for cls, cnt in dist.items():
        print(f"    {cls:<45}: {cnt:>4} ({cnt/len(y_tr)*100:.1f}%)")
    majority_class = dist.index[0]
    # Baseline: always predict the train majority class → what fraction of TEST rows does it get right?
    baseline_acc = float((y_te == majority_class).sum()) / len(y_te)

    # ─── Model: Regularized RF ────────────────────────────────────────────
    model_atk = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,           # prevent memorisation
        min_samples_leaf=2,    # min 2 samples to form a leaf
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model_atk.fit(X_tr_f, y_tr_enc)

    pred_tr  = model_atk.predict(X_tr_f)
    pred_te  = model_atk.predict(X_te_f)
    acc_tr   = float(accuracy_score(y_tr_enc, pred_tr))
    acc_te   = float(accuracy_score(y_te_enc, pred_te))
    f1_te    = float(f1_score(y_te_enc, pred_te, average="weighted", zero_division=0))
    gap      = acc_tr - acc_te

    # ─── Cross-validation ─────────────────────────────────────────────────
    cv = StratifiedKFold(n_splits=5, shuffle=False)
    cv_scores = cross_val_score(model_atk, X_full_f, y_full_enc, cv=cv, scoring="accuracy")

    # ─── Per-class report ─────────────────────────────────────────────────
    report_str = classification_report(
        y_te_enc, pred_te,
        target_names=le_target.classes_,
        digits=3,
        zero_division=0,
    )
    cm = confusion_matrix(y_te_enc, pred_te).tolist()

    # ─── Feature importance ───────────────────────────────────────────────
    feat_names = cat_cols + num_cols
    importance_pairs = sorted(
        zip(feat_names, model_atk.feature_importances_),
        key=lambda x: -x[1],
    )

    print(f"\n  === ATTACK TYPE MODEL RESULTS ===")
    print(f"  Majority-class naive baseline: {majority_class!r} → {baseline_acc:.1%} acc")
    print(f"  Train accuracy:  {acc_tr:.4f}")
    print(f"  Test  accuracy:  {acc_te:.4f}")
    print(f"  Overfit gap:     {gap:.4f}  {'⚠️ overfitting' if gap > 0.15 else '✓ OK'}")
    print(f"  5-fold CV:       {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    print(f"  Weighted F1:     {f1_te:.4f}")
    print()
    print("  Per-class metrics (test set):")
    print(report_str)
    print("  Feature importance (ranked):")
    for feat, imp in importance_pairs:
        print(f"    {feat:<30}: {imp:.4f}")

    # Save
    joblib.dump(model_atk,       "models/attack_prediction_model.pkl")
    joblib.dump(le_target,       "models/target_encoder.pkl")
    joblib.dump(oe,              "models/target_feature_encoder.pkl")
    joblib.dump(cat_imp,         "models/cat_imputer.pkl")
    joblib.dump(num_imp,         "models/num_imputer.pkl")

    metrics["attack_prediction"] = {
        "train_accuracy":   acc_tr,
        "test_accuracy":    acc_te,
        "overfit_gap":      gap,
        "weighted_f1":      f1_te,
        "cv_mean":          float(cv_scores.mean()),
        "cv_std":           float(cv_scores.std()),
        "majority_class":   majority_class,
        "baseline_accuracy": float(majority_class and dist.iloc[0] / len(y_te)),
        "per_class_report": report_str,
        "confusion_matrix": cm,
        "feature_importance": [{"feature": f, "importance": float(i)} for f, i in importance_pairs],
        "train_years":      [int(train_years[0]), int(train_years[1])],
        "test_years":       [int(test_years[0]),  int(test_years[1])],
        "train_rows":       split_idx,
        "test_rows":        n - split_idx,
        "data_warning":     (len(df) < 5000),
    }

    # =========================================================================
    # 3. Threat Level Classifier
    # =========================================================================
    print("\n--- Training Threat Level Model ---")
    cat_cols_t = ["country_txt", "region_txt", "attacktype1_txt", "weaptype1_txt", "targtype1_txt"]

    df_threat = df.dropna(subset=cat_cols_t).copy()
    nkill_t  = pd.to_numeric(df_threat["nkill"],  errors="coerce").fillna(0).clip(lower=0)
    nwound_t = pd.to_numeric(df_threat["nwound"], errors="coerce").fillna(0).clip(lower=0)
    impact   = nkill_t + nwound_t

    df_threat["threat_level"] = pd.cut(
        impact, bins=[-1, 2, 10, np.inf], labels=["LOW", "MEDIUM", "HIGH"]
    ).astype(str)

    oe_t = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    X_th_cat = oe_t.fit_transform(df_threat[cat_cols_t].fillna("Unknown"))
    X_th_num = np.column_stack([nkill_t, nwound_t])
    X_th = np.hstack([X_th_cat, X_th_num])

    le_thr = LabelEncoder()
    y_th = le_thr.fit_transform(df_threat["threat_level"])

    split_th = int(len(X_th) * 0.8)
    X_tr_th, X_te_th = X_th[:split_th], X_th[split_th:]
    y_tr_th, y_te_th = y_th[:split_th], y_th[split_th:]

    model_thr = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=2,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    model_thr.fit(X_tr_th, y_tr_th)

    pred_thr = model_thr.predict(X_te_th)
    acc_thr  = float(accuracy_score(y_te_th, pred_thr))
    f1_thr   = float(f1_score(y_te_th, pred_thr, average="weighted", zero_division=0))
    print(f"  Threat Level — Test Accuracy: {acc_thr:.4f}, Weighted F1: {f1_thr:.4f}")

    feat_names_t = cat_cols_t + ["nkill", "nwound"]
    feature_importance_threat = [
        {"feature": name, "importance": float(val)}
        for name, val in zip(feat_names_t, model_thr.feature_importances_)
    ]
    # Keep legacy format for threat encoders (LabelEncoder per col for page compatibility)
    encoders_threat = {}
    for col in cat_cols_t:
        le_tmp = LabelEncoder()
        le_tmp.fit(df_threat[col].astype(str))
        encoders_threat[col] = le_tmp

    joblib.dump(model_thr,               "models/threat_prediction_model.pkl")
    joblib.dump(encoders_threat,         "models/threat_feature_encoders.pkl")
    joblib.dump(le_thr,                  "models/threat_encoder.pkl")
    joblib.dump(feature_importance_threat, "models/threat_feature_importance.pkl")

    metrics["threat_prediction"] = {
        "test_accuracy": acc_thr,
        "weighted_f1":   f1_thr,
    }

    # =========================================================================
    # 4. Save all metrics
    # =========================================================================
    with open("models/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n--- All models trained and saved successfully! ---")
    if metrics["attack_prediction"].get("data_warning"):
        print("\n⚠️  WARNING: Dataset is small/synthetic (<5000 rows).")
        print("   Classifier accuracy is near-random. Replace data/globalterrorism.csv")
        print("   with the real GTD from https://www.start.umd.edu/gtd/")
        print("   then run: ./venv/bin/python data/prepare_gtd.py && ./venv/bin/python train_models.py")


if __name__ == "__main__":
    train_all()
