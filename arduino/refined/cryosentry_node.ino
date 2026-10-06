#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>

const int PIN_TRIG = 9;
const int PIN_ECHO = 10;
const int PIN_ONEWIRE = 2;
const int PIN_BUZZER = 8;
const int PIN_LED_GREEN = 5;
const int PIN_LED_YELLOW = 6;
const int PIN_LED_RED = 7;

const int MPU_ADDR = 0x68;
const unsigned long SAMPLE_INTERVAL_MS = 2000;
const unsigned long ECHO_TIMEOUT_US = 40000UL;
const int PINGS_PER_READING = 5;
const int VIB_SAMPLES = 40;

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature tempSensor(&oneWire);

unsigned long lastSample = 0;
float cachedTemp = 20.0;

void setup() {
  Serial.begin(115200);

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  digitalWrite(PIN_TRIG, LOW);

  tempSensor.begin();
  tempSensor.setWaitForConversion(false);
  tempSensor.requestTemperatures();

  Wire.begin();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);

  delay(500);
  Serial.println("# CRYOSENTRY node ready");
}

unsigned long pingOnce() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(20);
  digitalWrite(PIN_TRIG, LOW);
  return pulseIn(PIN_ECHO, HIGH, ECHO_TIMEOUT_US);
}

unsigned long medianPing() {
  unsigned long vals[PINGS_PER_READING];
  int count = 0;

  for (int i = 0; i < PINGS_PER_READING; i++) {
    unsigned long t = pingOnce();
    if (t > 0) vals[count++] = t;
    delay(60);
  }

  if (count < 3) return 0;

  for (int i = 1; i < count; i++) {
    unsigned long key = vals[i];
    int j = i - 1;
    while (j >= 0 && vals[j] > key) {
      vals[j + 1] = vals[j];
      j--;
    }
    vals[j + 1] = key;
  }
  return vals[count / 2];
}

float vibrationRMS() {
  float mags[VIB_SAMPLES];
  int n = 0;

  for (int i = 0; i < VIB_SAMPLES; i++) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x3B);
    if (Wire.endTransmission(false) != 0) continue;
    if (Wire.requestFrom(MPU_ADDR, 6, true) != 6) continue;

    int16_t ax = (Wire.read() << 8) | Wire.read();
    int16_t ay = (Wire.read() << 8) | Wire.read();
    int16_t az = (Wire.read() << 8) | Wire.read();

    float x = ax / 16384.0;
    float y = ay / 16384.0;
    float z = az / 16384.0;
    mags[n++] = sqrt(x * x + y * y + z * z);
    delay(4);
  }

  if (n < 5) return 0.0;

  float mean = 0;
  for (int i = 0; i < n; i++) mean += mags[i];
  mean /= n;

  float ss = 0;
  for (int i = 0; i < n; i++) ss += (mags[i] - mean) * (mags[i] - mean);
  return sqrt(ss / n);
}

void updateIndicators(float vib) {
  bool active = vib > 0.05;
  digitalWrite(PIN_LED_GREEN, !active);
  digitalWrite(PIN_LED_YELLOW, active);
}

void loop() {
  unsigned long now = millis();
  if (now - lastSample < SAMPLE_INTERVAL_MS) return;
  lastSample = now;

  unsigned long echo = medianPing();
  bool ok = echo > 0;

  float t = tempSensor.getTempCByIndex(0);
  if (t != DEVICE_DISCONNECTED_C && t > -55 && t < 125) cachedTemp = t;
  tempSensor.requestTemperatures();

  float vib = vibrationRMS();
  updateIndicators(vib);

  Serial.print(ok ? 1 : 0);
  Serial.print(",");
  Serial.print(echo);
  Serial.print(",");
  Serial.print(cachedTemp, 2);
  Serial.print(",");
  Serial.println(vib, 4);
}
