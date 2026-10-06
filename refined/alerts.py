import threading
import time

import config
from database import log_event

TIER_EMOJI = ["🟢", "🟡", "🟠", "🔴"]


def send_telegram(chat_id, text):
    if not config.TELEGRAM_TOKEN or not chat_id:
        print(f"[telegram disabled] {text}")
        return

    def _send():
        import requests
        try:
            requests.post(
                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": text},
                timeout=10,
            )
        except Exception as e:
            print(f"[telegram] send failed: {e}")

    threading.Thread(target=_send, daemon=True).start()


class Alerter:
    def __init__(self, con, session, quiet=False):
        self.con = con
        self.session = session
        self.quiet = quiet
        self.last_critical = 0
        self.last_valid = time.time()
        self.offline_sent = False
        self.stuck_sent = False
        self.last_rejection = 0

    def _send(self, text):
        if not self.quiet:
            send_telegram(config.CHAT_TEAM, text)

    @staticmethod
    def _summary(f, a):
        ttb = a["ttb_min"]
        if ttb == 0:
            ttb_text = "now"
        elif ttb is not None:
            ttb_text = f"~{ttb:.1f} min"
        else:
            ttb_text = "not rising"

        return (
            f"Risk Index: {a['risk']:.0f}/100\n"
            f"Water level: {f['level']:.1f} cm (danger {config.DANGER_LEVEL_CM:.0f} cm)\n"
            f"Rate of rise: {f['rate']:+.2f} cm/min\n"
            f"Estimated breach: {ttb_text}\n"
            f"Surge probability: {a['surge_prob'] * 100:.0f}%"
        )

    def on_reading(self, f, a, tier, changed, old_tier):
        now = time.time()
        name = config.TIER_NAMES[tier]

        if changed:
            direction = "escalated" if tier > old_tier else "de-escalated"
            text = (
                f"{TIER_EMOJI[tier]} CRYOSENTRY {name}: risk {direction}\n"
                f"{config.SITE_NAME}\n" + self._summary(f, a)
            )
            if tier == 3:
                text += "\n\nACTION: evacuate downstream areas immediately."
                self.last_critical = now

            log_event(
                self.con, self.session, "TIER_CHANGE", tier,
                f"{config.TIER_NAMES[old_tier]} -> {name} (risk {a['risk']:.0f})",
            )
            self._send(text)

        elif tier == 3 and now - self.last_critical > config.CRITICAL_REPEAT_S:
            self.last_critical = now
            self._send("🔴 CRYOSENTRY CRITICAL (repeat)\n" + self._summary(f, a))
            log_event(self.con, self.session, "ALERT_REPEAT", 3, "Critical alert repeated")

        if a["interference_detected"] and now - self.last_rejection > 10:
            self.last_rejection = now
            log_event(
                self.con, self.session, "REJECTED", tier,
                f"Interference rejected (anomaly {a['anomaly']:.2f}, "
                f"interference prob {a['interference_prob']:.2f})",
            )

    def valid_reading(self):
        self.last_valid = time.time()
        if self.offline_sent:
            self.offline_sent = False
            log_event(self.con, self.session, "SENSOR_ONLINE", None, "Sensor back online")
            self._send("✅ CRYOSENTRY: sensor back online.")

    def check_heartbeat(self):
        if self.offline_sent:
            return
        if time.time() - self.last_valid > config.HEARTBEAT_TIMEOUT_S:
            self.offline_sent = True
            log_event(
                self.con, self.session, "SENSOR_OFFLINE", None,
                f"No valid reading for {config.HEARTBEAT_TIMEOUT_S} s",
            )
            self._send(
                "⚠️ CRYOSENTRY SENSOR OFFLINE\n"
                f"No valid reading for {config.HEARTBEAT_TIMEOUT_S} s. Inspect the station."
            )

    def check_stuck(self, recent_levels):
        needed = int(config.STUCK_WINDOW_S / config.SAMPLE_INTERVAL_S * 0.8)
        if len(recent_levels) < needed:
            return

        spread = max(recent_levels) - min(recent_levels)
        if spread < 0.01 and not self.stuck_sent:
            self.stuck_sent = True
            log_event(self.con, self.session, "SENSOR_STUCK", None, "Readings frozen")
            self._send("⚠️ CRYOSENTRY: sensor readings frozen. Possible fault.")
        elif spread >= 0.01:
            self.stuck_sent = False
