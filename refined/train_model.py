import sqlite3

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict

import config
from features import FEATURE_NAMES

SURGE_MIN_RATE = 1.0
SURGE_MIN_R2 = 0.6
INT_MIN_NOISE = 0.6
INT_MIN_JUMP = 1.5
INT_MIN_VIB = 0.05

CLASSES = ["NORMAL", "INTERFERENCE", "SURGE"]


def load():
    con = sqlite3.connect(config.DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM readings "
        "WHERE label IS NOT NULL AND is_test = 0 AND rate IS NOT NULL",
        con,
    )
    con.close()
    return df


def gate_labels(df):
    y = df["label"].copy()

    surge = df["label"] == "SURGE"
    rising = (df["rate"] > SURGE_MIN_RATE) & (df["r2"] > SURGE_MIN_R2)
    y[surge & ~rising] = "NORMAL"

    inter = df["label"] == "INTERFERENCE"
    disturbed = (
        (df["noise"] > INT_MIN_NOISE)
        | (df["jump"] > INT_MIN_JUMP)
        | (df["vib"] > INT_MIN_VIB)
    )
    y[inter & ~disturbed] = "NORMAL"

    return y


def main():
    df = load()
    if df.empty:
        print("No training data found. Record sessions with main.py --record first.")
        return

    X = df[FEATURE_NAMES].fillna(0).values
    y = gate_labels(df).values

    counts = pd.Series(y).value_counts()
    print("Training windows after event gating:")
    print(counts.to_string(), "\n")

    missing = set(CLASSES) - set(counts.index)
    if missing:
        print(f"Missing classes: {missing}. Record those sessions before training.")
        return

    X_normal = X[y == "NORMAL"]
    iso = IsolationForest(n_estimators=200, contamination="auto", random_state=42)
    iso.fit(X_normal)

    scores_normal = iso.decision_function(X_normal)
    scores_abnormal = iso.decision_function(X[y != "NORMAL"])
    iso_hi = float(np.percentile(scores_normal, 5))
    iso_lo = float(np.percentile(scores_abnormal, 5))
    if iso_lo >= iso_hi:
        iso_lo = iso_hi - 0.1

    rf = RandomForestClassifier(
        n_estimators=150, max_depth=8, class_weight="balanced", random_state=42
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    pred = cross_val_predict(rf, X, y, cv=cv)

    print("Cross-validation report (optimistic: adjacent windows overlap):")
    print(classification_report(y, pred, digits=3))

    cm = pd.DataFrame(
        confusion_matrix(y, pred, labels=CLASSES),
        index=[f"true {c}" for c in CLASSES],
        columns=[f"pred {c}" for c in CLASSES],
    )
    print(cm.to_string(), "\n")

    rf.fit(X, y)

    importance = pd.Series(rf.feature_importances_, index=FEATURE_NAMES)
    print("Feature importance:")
    print(importance.sort_values(ascending=False).round(3).to_string())

    joblib.dump(
        {"iso": iso, "rf": rf, "iso_hi": iso_hi, "iso_lo": iso_lo, "features": FEATURE_NAMES},
        config.MODEL_PATH,
    )
    print(f"\nSaved models to {config.MODEL_PATH}. Restart main.py to use them.")


if __name__ == "__main__":
    main()
