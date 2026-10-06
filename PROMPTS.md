# AI Prompt Log

Every prompt below was used to refine the base code in `base/` and
`arduino/base/` into the version in `refined/` and `arduino/refined/`.

The base code was written by us first. We then used an AI assistant as a
coding tool to review it, point out weaknesses, and help implement the
improvements we decided on. We reviewed, tested and debugged every change
on the physical rig ourselves. Where the AI suggested something we did not
understand or could not verify, we did not use it.

Prompts are grouped by the part of the system they refined, roughly in the
order we worked through them.

---

## 1. Sensor reliability

**Prompt 1**
> Here is our Arduino sketch that reads an ultrasonic sensor every two
> seconds. Sometimes a reading is wildly wrong, like 400 cm when the water
> is 30 cm away. What causes this and what is the standard way to deal with
> it in sensor code?

**Prompt 2**
> Explain the difference between taking an average and taking a median of
> several sensor readings. Which one is better when the bad readings are
> occasional large spikes rather than small random noise?

**Prompt 3**
> Our DS18B20 temperature read seems to be slowing the main loop down.
> Explain what `setWaitForConversion(false)` does and show how to restructure
> the loop so a slow temperature sensor does not block the ultrasonic
> readings.

---

## 2. Temperature compensation

**Prompt 4**
> Ultrasonic sensors calculate distance from the speed of sound, and the
> speed of sound changes with air temperature. Give the standard formula
> relating the two, and explain which temperature matters for our setup:
> the air between the sensor and the water, or the water itself.

**Prompt 5**
> Rewrite our distance calculation so it uses a measured air temperature
> instead of a hardcoded constant. Keep the uncompensated calculation
> available as well, because we want to log both and compare them in our
> results.

---

## 3. Feature extraction

**Prompt 6**
> Our current code only looks at one reading at a time. We think a real
> surge looks different from a splash because a surge rises steadily over
> time. What numerical features could we compute from a rolling window of
> readings that would capture that difference?

**Prompt 7**
> Explain what R-squared from a linear fit measures, and why it would be
> higher for a steady rise than for a jagged disturbance. Show how to
> compute it from a window of level readings in Python.

**Prompt 8**
> Refactor our feature calculations into a class that maintains a rolling
> window of the last 30 readings and returns all features as a dictionary.
> Use NumPy. Keep it under about 60 lines.

---

## 4. Machine learning

**Prompt 9**
> We have very few examples of real outburst surges but plenty of normal
> data. Which machine learning approach fits that situation better:
> supervised classification or anomaly detection? Explain the trade-off.

**Prompt 10**
> Explain how Isolation Forest works in simple terms, and show how to
> convert its decision_function output into a 0-1 anomaly score using
> percentiles from the training data.

**Prompt 11**
> We want to use both an Isolation Forest for anomalies and a Random Forest
> to classify normal, interference and surge. Explain what each one
> contributes and why using both is better than using either alone here.

**Prompt 12**
> Our training sessions are labelled by what we were doing, but a session
> labelled SURGE also contains calm periods between pours. How do we relabel
> individual windows based on what is actually happening in them, rather
> than trusting the session label?

**Prompt 13**
> Review our training script. Are we at risk of testing on the same data we
> trained on? Explain why cross-validation scores might be optimistic when
> consecutive feature windows overlap in time.

---

## 5. Risk scoring and alerting

**Prompt 14**
> We want to combine several factors (water level, rate of rise, vibration,
> model outputs) into one 0-100 risk score. Show a clean way to normalise
> each factor to 0-1 and apply weights, and explain how to keep the total
> within range if some factors are missing.

**Prompt 15**
> Our alert fires on a single reading crossing a threshold, so a splash sets
> it off. What is the standard technique for requiring a condition to hold
> for several consecutive readings before acting, and how do we also stop
> alerts flickering on and off at the boundary?

**Prompt 16**
> Add a safety rule to our risk score: if the water is already above the
> danger level, the risk must never report below critical even if the water
> has stopped rising. Where in the calculation should this go?

**Prompt 17**
> Our alert function makes a network request inside the main monitoring
> loop. If the network is slow, monitoring stops. Show how to send the
> message in a background thread so a failed alert can never crash or stall
> the monitoring loop.

**Prompt 18**
> A monitoring system that goes silent because its sensor died is dangerous,
> because silence looks the same as everything being fine. Show how to
> implement a heartbeat check that alerts us if no valid reading arrives
> within a set time, and a separate check for readings that are frozen at a
> constant value.

---

## 6. Structure and data handling

**Prompt 19**
> Our script reads sensors, calculates risk, saves data and draws the
> dashboard all in one file. Suggest how to split this into separate modules
> with clear responsibilities, and explain why the dashboard should read
> from the database rather than talking to the sensors directly.

**Prompt 20**
> Write a small SQLite layer that stores every reading and every event, and
> explain what WAL mode does and why it matters when the dashboard reads the
> file while the monitoring loop is writing to it.

**Prompt 21**
> Write an evaluation script that compares our system against a simple
> fixed-threshold baseline on the same recorded trials, reporting false
> alarms, missed surges, precision, recall and warning lead time.

---

## 7. Debugging help

**Prompt 22**
> We get "could not open port COM8" when our script runs, but the Arduino
> IDE shows the board on COM12. What is happening and how do we specify the
> port explicitly instead of relying on auto-detection?

**Prompt 23**
> Our ultrasonic sensor outputs 5 V on the echo pin. Explain which boards
> can accept that directly and which need a voltage divider, and show the
> resistor values for dividing 5 V down to 3.3 V.
