# CRYOSENTRY

A low-cost multi-sensor early detection system for Glacial Lake Outburst
Floods (GLOFs), with machine-learning false-alarm rejection, a time-to-breach
forecast, and automated risk-tiered alerts.

IRIS National Fair 2026-27 · Environmental Engineering

---

## How this repository is organised

This repository contains **two complete versions of the same system**.

| Folder | What it is |
| --- | --- |
| `base/` + `arduino/base/` | The original code we wrote ourselves. Simple, readable, fully working. |
| `refined/` + `arduino/refined/` | The same system after refinement, with AI used as a coding tool. |
| `PROMPTS.md` | Every prompt used during refinement. |
| `docs/architecture.md` | How the system works, tier by tier. |

The base version is not a draft or a broken first attempt. It runs, reads all
three sensors, detects a rising water level and sends an alert. It is the
honest starting point: a fixed-threshold system, which is exactly the kind of
system our research is arguing against.

The refined version is what the project claims to be. Comparing the two folders
shows precisely what the refinement added, and the project paper evaluates the
refined system against the base system's threshold logic as its baseline.

---

## The difference in one table

| | `base/` | `refined/` |
| --- | --- | --- |
| Level measurement | Fixed speed of sound (343 m/s) | Compensated for measured air temperature |
| Bad readings | Used as-is | Median of 5 pings per reading |
| Decision input | One reading at a time | 7 features over a 60-second window |
| Decision method | Fixed threshold | Isolation Forest + Random Forest + weighted risk index |
| Output | Alert / no alert | Risk Index 0-100, four tiers, time-to-breach forecast |
| False alarms | Any spike triggers it | Persistence check + learned interference rejection |
| Sensor failure | Silent | Heartbeat and stuck-reading detection |
| Data | Printed, or one CSV | SQLite database + live dashboard |
| Evaluation | None | Benchmarked against the base threshold logic |

---

## Hardware

| Component | Role |
| --- | --- |
| Arduino UNO R4 Minima | Sensing node |
| JSN-SR04T waterproof ultrasonic sensor | Water level |
| DS18B20 temperature probe | Air temperature, mounted in air |
| MPU-6050 accelerometer | Vibration from ice calving and impacts |
| Host computer | Runs the decision pipeline over USB serial |

### Wiring

| Sensor pin | Arduino pin |
| --- | --- |
| Ultrasonic TRIG | D9 |
| Ultrasonic ECHO | D10 |
| DS18B20 DATA | D2, with 4.7k pull-up to 5V |
| MPU-6050 SDA / SCL | A4 / A5 |
| Buzzer | D8 |
| LEDs green / yellow / red | D5 / D6 / D7, each with 220R |

The R4 Minima is 5 V tolerant on its digital pins, so the ultrasonic echo
line connects directly. A 3.3 V board such as a Raspberry Pi would need a
voltage divider on that line.

---

## Running it

### Base version

```
pip install pyserial
python base/read_sensors.py
python base/threshold_alert.py
```

Flash `arduino/base/cryosentry_base.ino` first. Set `PORT` at the top of each
script to match your board.

### Refined version

```
pip install -r requirements.txt
```

Flash `arduino/refined/cryosentry_node.ino`. Then set `SERIAL_PORT`,
`SENSOR_HEIGHT_CM`, `NORMAL_LEVEL_CM` and `DANGER_LEVEL_CM` in
`refined/config.py` to match your rig, and add a Telegram bot token and chat
ID if you want remote alerts.

```
cd refined
python main.py
streamlit run dashboard.py
```

The dashboard opens at `http://localhost:8501`.

### Collecting data and training

```
python main.py --record NORMAL
python main.py --record INTERFERENCE
python main.py --record SURGE
python train_model.py
```

Record several minutes of each. NORMAL is calm water; INTERFERENCE is ice
drops, splashes, floating objects and knocks against the rig; SURGE is a
steady pour at varying rates. `train_model.py` relabels individual windows
based on what is actually happening in them, so calm moments inside a SURGE
session are not mislabelled.

### Evaluation

```
python main.py --record SURGE --test
python main.py --record INTERFERENCE --test
python evaluate.py
```

Trials recorded with `--test` are excluded from training and used only for
evaluation. `evaluate.py` reports false alarms, missed surges, precision,
recall and warning lead time for both the refined system and the base
threshold logic on the same trials.

---

## How the refined system works

Every two seconds the Arduino reads all three sensors and sends one line over
serial. The host then:

1. Converts the echo time to a water level using the speed of sound at the
   measured air temperature.
2. Adds the reading to a rolling 60-second window.
3. Computes seven features: level, rate of rise, steadiness of that rise,
   residual noise, largest step change, vibration intensity, temperature trend.
4. Runs two models. The Isolation Forest, trained only on normal data, scores
   how unusual the window is. The Random Forest classifies it as normal,
   interference or surge.
5. Combines everything into a 0-100 Risk Index, plus a forecast of minutes
   until the danger level is reached at the current rate.
6. Maps the index to a tier, requiring three consecutive readings to escalate
   and fifteen to de-escalate.
7. Sends an automated alert on any tier change, and logs everything.

A full walkthrough is in `docs/architecture.md`.

---

## Current limitations

- **One temperature probe, mounted in air.** Compensation corrects for the
  speed of sound through air, so the probe belongs in air. Water temperature
  is a fixed estimate in `config.py`, not a measurement.
- **Inference runs on a host computer, not on the board.** The pipeline was
  designed for an onboard single-board computer. The unit available to us
  failed to boot, so sensing runs on the Arduino and the unchanged Python
  pipeline runs on a laptop over serial. Porting it back is the first item
  in future work.
- **Alerts need an internet connection.** Telegram was chosen for cost and
  speed of implementation. A field deployment would use a GSM module for SMS.
- **Tested on a laboratory rig, not a glacial lake.** Surges and interference
  are generated by hand in a scaled water model.

---

## Declaration of AI use

The base code in `base/` and `arduino/base/` was written by us.

An AI assistant was used as a coding tool to refine it into `refined/` and
`arduino/refined/`: explaining concepts such as median filtering, temperature
compensation and anomaly detection, reviewing our code for weaknesses, and
helping implement the improvements we chose. Every prompt is logged in
`PROMPTS.md`.

All hardware assembly, wiring, data collection, testing, debugging and
experimental evaluation were carried out by us. All results reported in the
project paper come from our own physical rig.
