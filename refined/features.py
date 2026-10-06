from collections import deque

import numpy as np

import config

FEATURE_NAMES = ["level", "rate", "r2", "noise", "jump", "vib", "wtemp_delta"]


def speed_of_sound(temp_c):
    return 331.3 + 0.606 * temp_c


def level_from_echo(echo_time_s, air_temp_c, compensate=True):
    t = air_temp_c if compensate else config.ASSUMED_AIR_TEMP_C
    distance_cm = speed_of_sound(t) * echo_time_s / 2 * 100
    return config.SENSOR_HEIGHT_CM - distance_cm


class FeatureWindow:
    def __init__(self, size=None):
        size = size or config.WINDOW_SIZE
        self.t = deque(maxlen=size)
        self.level = deque(maxlen=size)
        self.vib = deque(maxlen=size)
        self.wtemp = deque(maxlen=size)

    def add(self, ts, level, vib, wtemp):
        self.t.append(ts)
        self.level.append(level)
        self.vib.append(vib)
        self.wtemp.append(wtemp if wtemp is not None else np.nan)

    def ready(self):
        return len(self.level) >= config.MIN_WINDOW

    def compute(self):
        t = np.array(self.t) - self.t[0]
        t_min = t / 60.0
        y = np.array(self.level)

        slope, intercept = np.polyfit(t_min, y, 1)
        fit = slope * t_min + intercept
        resid = y - fit

        ss_res = float(np.sum(resid ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-9
        r2 = max(0.0, 1 - ss_res / ss_tot)

        jump = float(np.max(np.abs(np.diff(y[-5:])))) if len(y) > 1 else 0.0
        vib_recent = float(np.max(list(self.vib)[-5:]))

        w = np.array(self.wtemp, dtype=float)
        w = w[~np.isnan(w)]
        wtemp_delta = float(w[-1] - w[0]) if len(w) > 1 else 0.0

        return {
            "level": float(y[-1]),
            "rate": float(slope),
            "r2": float(r2),
            "noise": float(np.std(resid)),
            "jump": jump,
            "vib": vib_recent,
            "wtemp_delta": wtemp_delta,
        }
