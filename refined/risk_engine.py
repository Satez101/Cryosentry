import os

import numpy as np

import config
from features import FEATURE_NAMES


def clip01(x):
    return float(max(0.0, min(1.0, x)))


def tier_of(risk):
    tier = 0
    for i, threshold in enumerate(config.TIER_THRESHOLDS):
        if risk >= threshold:
            tier = i + 1
    return tier


def baseline_alarm(f):
    return f["level"] >= config.DANGER_LEVEL_CM or f["jump"] > config.BASELINE_JUMP_CM


class RiskEngine:
    def __init__(self, model_path=None):
        self.bundle = None
        path = model_path or config.MODEL_PATH
        if os.path.exists(path):
            import joblib
            self.bundle = joblib.load(path)
            print(f"[risk] models loaded from {path}")
        else:
            print("[risk] no trained model found, running rule-based scoring only")

    @property
    def ai_enabled(self):
        return self.bundle is not None

    def _infer(self, f):
        if not self.bundle:
            return 0.0, 0.0, 0.0

        x = np.array([[f[name] for name in FEATURE_NAMES]])

        score = float(self.bundle["iso"].decision_function(x)[0])
        hi, lo = self.bundle["iso_hi"], self.bundle["iso_lo"]
        anomaly = clip01((hi - score) / (hi - lo)) if hi != lo else 0.0

        proba = self.bundle["rf"].predict_proba(x)[0]
        classes = list(self.bundle["rf"].classes_)
        p_surge = float(proba[classes.index("SURGE")]) if "SURGE" in classes else 0.0
        p_int = float(proba[classes.index("INTERFERENCE")]) if "INTERFERENCE" in classes else 0.0

        return anomaly, p_surge, p_int

    def time_to_breach(self, level, rate):
        if level >= config.DANGER_LEVEL_CM:
            return 0.0
        if rate > 0.2:
            return (config.DANGER_LEVEL_CM - level) / rate
        return None

    def assess(self, f):
        level, rate = f["level"], f["rate"]
        ttb = self.time_to_breach(level, rate)
        span = config.DANGER_LEVEL_CM - config.NORMAL_LEVEL_CM

        factors = {
            "level": clip01((level - config.NORMAL_LEVEL_CM) / span),
            "rate": clip01(rate / config.CRITICAL_RATE_CM_PER_MIN),
            "breach": clip01(1 - ttb / config.BREACH_REF_MIN) if ttb is not None else 0.0,
            "vibration": clip01(f["vib"] / config.CRITICAL_VIB_RMS_G),
        }

        anomaly, p_surge, p_int = self._infer(f)

        if self.ai_enabled:
            factors["anomaly"] = anomaly
            factors["surge_prob"] = p_surge
            if p_int > 0.6:
                factors["rate"] *= (1 - p_int)
                factors["breach"] *= (1 - p_int)

        weights = {k: config.WEIGHTS[k] for k in factors}
        risk = 100 * sum(weights[k] * factors[k] for k in factors) / sum(weights.values())

        if level >= config.DANGER_LEVEL_CM:
            risk = max(risk, 80.0)

        return {
            "risk": round(risk, 1),
            "raw_tier": tier_of(risk),
            "ttb_min": ttb,
            "anomaly": anomaly,
            "surge_prob": p_surge,
            "interference_prob": p_int,
            "factors": factors,
            "interference_detected": self.ai_enabled and anomaly > 0.5 and p_int > 0.5,
        }


class TierManager:
    def __init__(self):
        self.tier = 0
        self._up = 0
        self._down = 0

    def update(self, raw_tier):
        old = self.tier

        if raw_tier > self.tier:
            self._up += 1
            self._down = 0
            if self._up >= config.PERSIST_UP:
                self.tier = raw_tier
                self._up = 0
        elif raw_tier < self.tier:
            self._down += 1
            self._up = 0
            if self._down >= config.PERSIST_DOWN:
                self.tier = raw_tier
                self._down = 0
        else:
            self._up = self._down = 0

        return self.tier, self.tier != old
