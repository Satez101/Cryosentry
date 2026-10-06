import sqlite3
import time

import config

READING_COLS = [
    "ts", "session", "label", "is_test",
    "level", "raw_level", "air_temp", "water_temp", "vib",
    "rate", "r2", "noise", "jump", "wtemp_delta",
    "anomaly", "surge_prob", "interference_prob",
    "risk", "raw_tier", "tier", "ttb_min", "baseline_alarm",
]


def connect(path=None):
    con = sqlite3.connect(path or config.DB_PATH, timeout=10, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        "CREATE TABLE IF NOT EXISTS readings ("
        "ts REAL, session TEXT, label TEXT, is_test INTEGER, "
        "level REAL, raw_level REAL, air_temp REAL, water_temp REAL, vib REAL, "
        "rate REAL, r2 REAL, noise REAL, jump REAL, wtemp_delta REAL, "
        "anomaly REAL, surge_prob REAL, interference_prob REAL, "
        "risk REAL, raw_tier INTEGER, tier INTEGER, ttb_min REAL, baseline_alarm INTEGER)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS events ("
        "ts REAL, session TEXT, kind TEXT, tier INTEGER, message TEXT)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
    con.commit()
    return con


def save_reading(con, row):
    values = [row.get(c) for c in READING_COLS]
    placeholders = ",".join("?" * len(READING_COLS))
    con.execute(
        f"INSERT INTO readings ({','.join(READING_COLS)}) VALUES ({placeholders})",
        values,
    )
    con.commit()


def log_event(con, session, kind, tier, message):
    con.execute(
        "INSERT INTO events (ts, session, kind, tier, message) VALUES (?,?,?,?,?)",
        (time.time(), session, kind, tier, message),
    )
    con.commit()
    print(f"[event] {kind}: {message}")
