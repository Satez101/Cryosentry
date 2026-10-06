import argparse
import time
from collections import deque
from datetime import datetime

import config
import database
from alerts import Alerter
from features import FeatureWindow, level_from_echo
from risk_engine import RiskEngine, TierManager, baseline_alarm
from sensors import make_sensors

LABELS = ["NORMAL", "INTERFERENCE", "SURGE"]


def parse_args():
    ap = argparse.ArgumentParser(description="CRYOSENTRY monitoring loop")
    ap.add_argument("--record", choices=LABELS, help="label this session for training data")
    ap.add_argument("--test", action="store_true", help="mark session as a held-out test trial")
    ap.add_argument("--port", help="serial port override")
    ap.add_argument("--quiet", action="store_true", help="suppress Telegram messages")
    ap.add_argument("--minutes", type=float, help="stop automatically after N minutes")
    return ap.parse_args()


def main():
    args = parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    kind = ("test-" if args.test else "") + (args.record.lower() if args.record else "live")
    session = f"{kind}-{stamp}"

    con = database.connect()
    sensors = make_sensors(port=args.port)
    engine = RiskEngine()
    tiers = TierManager()
    window = FeatureWindow()
    alerter = Alerter(con, session, quiet=args.quiet)
    stuck_levels = deque(maxlen=int(config.STUCK_WINDOW_S / config.SAMPLE_INTERVAL_S))

    ai_state = "enabled" if engine.ai_enabled else "rule-based"
    print(f"CRYOSENTRY started | AI {ai_state} | session {session}")
    database.log_event(con, session, "START", 0, f"Monitoring started (AI {ai_state})")

    started = time.time()

    try:
        while True:
            cycle_start = time.time()
            if args.minutes and cycle_start - started > args.minutes * 60:
                break

            reading = sensors.read()
            if not reading["ok"]:
                alerter.check_heartbeat()
                time.sleep(config.SAMPLE_INTERVAL_S)
                continue

            alerter.valid_reading()

            level = level_from_echo(reading["echo_time_s"], reading["air_temp_c"], True)
            raw_level = level_from_echo(reading["echo_time_s"], reading["air_temp_c"], False)

            window.add(cycle_start, level, reading["vib_rms_g"], reading["water_temp_c"])
            stuck_levels.append(level)
            alerter.check_stuck(list(stuck_levels))

            row = {
                "ts": cycle_start,
                "session": session,
                "label": args.record,
                "is_test": int(args.test),
                "level": level,
                "raw_level": raw_level,
                "air_temp": reading["air_temp_c"],
                "water_temp": reading["water_temp_c"],
                "vib": reading["vib_rms_g"],
                "tier": tiers.tier,
            }

            if window.ready():
                f = window.compute()
                a = engine.assess(f)
                old_tier = tiers.tier
                tier, changed = tiers.update(a["raw_tier"])

                row.update({
                    "rate": f["rate"], "r2": f["r2"], "noise": f["noise"],
                    "jump": f["jump"], "wtemp_delta": f["wtemp_delta"],
                    "anomaly": a["anomaly"], "surge_prob": a["surge_prob"],
                    "interference_prob": a["interference_prob"],
                    "risk": a["risk"], "raw_tier": a["raw_tier"], "tier": tier,
                    "ttb_min": a["ttb_min"], "baseline_alarm": int(baseline_alarm(f)),
                })

                alerter.on_reading(f, a, tier, changed, old_tier)

                ttb = f"{a['ttb_min']:.1f}m" if a["ttb_min"] is not None else "--"
                print(
                    f"{datetime.now():%H:%M:%S} "
                    f"level {level:5.1f} cm (raw {raw_level:5.1f}) "
                    f"rate {f['rate']:+5.2f} cm/min  risk {a['risk']:5.1f}  "
                    f"{config.TIER_NAMES[tier]:8s} ttb {ttb}"
                )

            database.save_reading(con, row)
            elapsed = time.time() - cycle_start
            time.sleep(max(0.0, config.SAMPLE_INTERVAL_S - elapsed))

    except KeyboardInterrupt:
        pass
    finally:
        database.log_event(con, session, "STOP", None, "Monitoring stopped")
        sensors.cleanup()
        print("Stopped.")


if __name__ == "__main__":
    main()
