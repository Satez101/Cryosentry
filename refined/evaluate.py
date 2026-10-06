import sqlite3

import pandas as pd

import config


def load_trials():
    con = sqlite3.connect(config.DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM readings WHERE is_test = 1 AND rate IS NOT NULL ORDER BY ts", con
    )
    con.close()
    return df


def summarise_trial(session, g):
    label = g["label"].iloc[0]
    cryo_hits = g[g["tier"] >= 2]
    base_hits = g[g["baseline_alarm"] == 1]
    breach = g[g["level"] >= config.DANGER_LEVEL_CM]

    row = {
        "session": session,
        "label": label,
        "cryo_alarm": not cryo_hits.empty,
        "baseline_alarm": not base_hits.empty,
    }

    if label == "SURGE" and not breach.empty:
        t_breach = breach["ts"].iloc[0]

        if not cryo_hits.empty:
            first = cryo_hits.iloc[0]
            row["cryo_lead_s"] = round(t_breach - first["ts"], 1)
            if pd.notna(first["ttb_min"]):
                predicted = first["ttb_min"] * 60
                actual = t_breach - first["ts"]
                row["predicted_breach_s"] = round(predicted, 1)
                row["actual_breach_s"] = round(actual, 1)
                if actual > 0:
                    row["forecast_error_pct"] = round(abs(predicted - actual) / actual * 100, 1)

        if not base_hits.empty:
            row["baseline_lead_s"] = round(t_breach - base_hits["ts"].iloc[0], 1)

        row["rate_cm_min"] = round(g["rate"].max(), 2)

    return row


def main():
    df = load_trials()
    if df.empty:
        print("No test trials found. Record with main.py --record SURGE --test")
        return

    results = pd.DataFrame(
        [summarise_trial(session, g) for session, g in df.groupby("session")]
    )
    results.to_csv("results_trials.csv", index=False)

    surges = results[results["label"] == "SURGE"]
    interference = results[results["label"] == "INTERFERENCE"]

    print("\n=== False-alarm rejection ===")
    for name, column in (("Fixed threshold", "baseline_alarm"), ("CRYOSENTRY", "cryo_alarm")):
        tp = int(surges[column].sum())
        fn = len(surges) - tp
        fp = int(interference[column].sum())
        precision = tp / (tp + fp) if tp + fp else float("nan")
        recall = tp / len(surges) if len(surges) else float("nan")
        print(
            f"{name:17s} false alarms {fp}/{len(interference)}   "
            f"missed surges {fn}/{len(surges)}   "
            f"precision {precision:.2f}   recall {recall:.2f}"
        )

    if not surges.empty:
        print("\n=== Early-warning lead time ===")
        columns = [
            c for c in [
                "session", "rate_cm_min", "cryo_lead_s", "baseline_lead_s",
                "predicted_breach_s", "actual_breach_s", "forecast_error_pct",
            ] if c in surges.columns
        ]
        print(surges[columns].to_string(index=False))

        if "cryo_lead_s" in surges:
            print(f"\nMean CRYOSENTRY lead time: {surges['cryo_lead_s'].mean():.1f} s")
        if "forecast_error_pct" in surges:
            print(f"Mean forecast error: {surges['forecast_error_pct'].mean():.1f} %")

    print("\nPer-trial details written to results_trials.csv")


if __name__ == "__main__":
    main()
