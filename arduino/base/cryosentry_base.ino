#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>

const int TRIG = 9;
const int ECHO = 10;
const int ONEWIRE = 2;
const int MPU = 0x68;

OneWire oneWire(ONEWIRE);
DallasTemperature tempSensor(&oneWire);

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
  tempSensor.begin();

  Wire.begin();
  Wire.beginTransmission(MPU);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);
}

float readDistance() {
  digitalWrite(TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH);
  delayMicroseconds(20);
  digitalWrite(TRIG, LOW);

  long duration = pulseIn(ECHO, HIGH, 40000);
  if (duration == 0) return -1;
  return duration * 0.0343 / 2;
}

float readTemp() {
  tempSensor.requestTemperatures();
  return tempSensor.getTempCByIndex(0);
}

float readVibration() {
  Wire.beginTransmission(MPU);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU, 6, true);

  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();

  float x = ax / 16384.0;
  float y = ay / 16384.0;
  float z = az / 16384.0;

  return sqrt(x * x + y * y + z * z);
}

void loop() {
  float distance = readDistance();
  float temp = readTemp();
  float vib = readVibration();

  Serial.print(distance);
  Serial.print(",");
  Serial.print(temp);
  Serial.print(",");
  Serial.println(vib);

  delay(2000);
}
