import serial
import time
import requests

PORT = "COM12"
BAUD = 115200

SENSOR_HEIGHT = 60.0
DANGER_LEVEL = 30.0

TELEGRAM_TOKEN = ""
CHAT_ID = ""

ser = serial.Serial(PORT, BAUD, timeout=3)
time.sleep(2)

alerted = False


def send_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("ALERT:", message)
        return
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})


while True:
    line = ser.readline().decode("utf-8").strip()
    if not line:
        continue

    parts = line.split(",")
    if len(parts) != 3:
        continue

    distance = float(parts[0])
    if distance < 0:
        continue

    level = SENSOR_HEIGHT - distance
    print("Water level:", round(level, 1), "cm")

    if level >= DANGER_LEVEL and not alerted:
        send_alert("WARNING: Water level is " + str(round(level, 1)) + " cm")
        alerted = True

    if level < DANGER_LEVEL:
        alerted = False
