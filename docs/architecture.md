# CRYOSENTRY Architecture

How the refined system works, from a sound pulse to an alert on a phone.

---

## The four tiers

```
TIER 1  SENSING                    Arduino UNO R4 Minima
        ultrasonic | temperature | vibration
                     |
                     |  serial, one line every 2 s
                     v
TIER 2  EDGE INTELLIGENCE          Host computer
        compensation -> filtering -> features -> models -> Risk Index
                     |
          +----------+----------+
          v                     v
TIER 3  MONITORING          TIER 4  ALERTING
        SQLite + dashboard          tiers -> Telegram + local indicators
```

---

## Tier 1: Sensing

The Arduino samples every two seconds and sends one comma-separated line:

```
ok,echo_time_us,air_temp_c,vibration_rms_g
```

Three things happen on the board rather than the host:

**Median filtering.** Each level reading is the median of five pings taken
60 ms apart. A single bad echo, from a ripple or a passing object, is
discarded before it ever reaches the host.

**Non-blocking temperature.** The DS18B20 takes around 750 ms to convert.
The sketch requests a conversion and reads the result on the *next* cycle,
so the slow sensor never stalls the fast one.

**Vibration as RMS.** Forty accelerometer samples are reduced to one number:
the root-mean-square deviation of acceleration magnitude from its mean. This
measures how much the rig is shaking, independent of its orientation.

---

## Tier 2: Edge intelligence

### Step 1: Temperature-compensated level

Ultrasonic sensors measure time, not distance. Distance comes from the speed
of sound, which depends on air temperature:

```
c = 331.3 + 0.606 * T        (metres per second, T in Celsius)
level = sensor_height - (c * echo_time / 2)
```

At 20 °C sound travels at 343.4 m/s. At −20 °C it travels at 319.2 m/s, about
7% slower. A sensor assuming room temperature at a glacial lake therefore
misreads the level by roughly 2.3 cm at a 30 cm distance, and the error grows
with distance. The system logs both the compensated and uncompensated value so
the difference can be measured directly.

### Step 2: Feature window

The last 30 readings, 60 seconds, are reduced to seven numbers:

| Feature | What it captures |
| --- | --- |
| `level` | Current water level |
| `rate` | Slope of a line fitted through the window, cm/min |
| `r2` | How well that line fits: steady rise scores high, jagged noise scores low |
| `noise` | Standard deviation of the residuals |
| `jump` | Largest single step between recent readings |
| `vib` | Peak vibration in the window |
| `wtemp_delta` | Temperature trend across the window |

`r2` is the feature that separates a real surge from a splash. Water rising
steadily fits a straight line closely. A splash or a dropped piece of ice
produces a large `jump` and high `noise` but poor `r2`.

### Step 3: Two models

**Isolation Forest** is trained only on normal lake behaviour. It scores how
unusual the current window is, without ever having seen an outburst. This
matters because real GLOF data is rare: a model that needs examples of
disasters cannot be trained on a hazard that happens once a decade.

**Random Forest** is trained on labelled windows of all three classes and
answers a different question: given that something is happening, is it a surge
or interference?

Used together, the first asks *is something unusual happening*, the second asks
*and is it the thing we care about*. When the classifier is confident the event
is interference, the rate and breach factors are damped, so a jagged spike
cannot drive the risk score up.

### Step 4: Risk Index

Each factor is scaled to 0-1 and weighted:

| Factor | Weight | Scaled as |
| --- | --- | --- |
| Level proximity | 0.25 | position between normal and danger level |
| Rate of rise | 0.20 | rate ÷ critical rate |
| Breach urgency | 0.15 | 1 − time-to-breach ÷ reference |
| Vibration | 0.10 | RMS ÷ critical RMS |
| Anomaly score | 0.10 | Isolation Forest |
| Surge probability | 0.20 | Random Forest |

The weighted sum is divided by the total weight present, so the index still
spans 0-100 when the models are unavailable and only the rule-based factors
contribute. One safety rule overrides everything: if the water is already
above the danger level, the index never reports below 80.

### Step 5: Time-to-breach

```
minutes = (danger_level - level) / rate_of_rise
```

Computed only while the water is rising. This is what makes the system an
early *detection* system rather than an alarm: it reports minutes remaining,
not that a line has already been crossed.

---

## Tier 3: Monitoring

Every reading and event is written to SQLite in WAL mode, which allows the
dashboard to read the file while the monitoring loop writes to it.

The dashboard never touches the sensors. It only reads the database. If the
dashboard crashes, monitoring and alerting continue unaffected. This
separation is deliberate: the display is the least important part of the
system and must never be able to take down the part that matters.

---

## Tier 4: Alerting

| Risk Index | Tier | Action |
| --- | --- | --- |
| 0-24 | NORMAL | Green indicator |
| 25-49 | WATCH | Yellow indicator, team notified |
| 50-74 | WARNING | Red indicator, team notified |
| 75-100 | CRITICAL | Red indicator, siren, repeated alerts |

**Persistence.** A tier escalates only after three consecutive readings agree,
six seconds. A single disturbed reading cannot raise an alert.

**Hysteresis.** A tier drops only after fifteen consecutive readings below it,
thirty seconds, so alerts do not flicker at a boundary.

**Non-blocking delivery.** Messages are sent on a background thread. A slow or
failed network request cannot stall or crash the monitoring loop.

**Self-diagnosis.** If no valid reading arrives for 30 seconds, the system
reports itself offline. If readings freeze at an identical value for five
minutes, it reports a stuck sensor. A monitoring system that fails silently is
more dangerous than no system at all, because silence is indistinguishable
from safety.

---

## Module map

| File | Responsibility |
| --- | --- |
| `config.py` | Every tunable value. Nothing is hardcoded elsewhere. |
| `sensors.py` | Serial connection and line parsing |
| `features.py` | Compensation and the rolling feature window |
| `risk_engine.py` | Model inference, Risk Index, tier management |
| `database.py` | SQLite storage for readings and events |
| `alerts.py` | Telegram delivery, heartbeat, stuck detection |
| `main.py` | The monitoring loop that ties the above together |
| `train_model.py` | Window relabelling and model training |
| `evaluate.py` | Benchmark against the fixed-threshold baseline |
| `dashboard.py` | Read-only live display |
