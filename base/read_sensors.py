import serial
import time

PORT = "COM12"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=3)
time.sleep(2)

print("Reading from Arduino...")

while True:
    line = ser.readline().decode("utf-8").strip()
    if not line:
        continue

    parts = line.split(",")
    if len(parts) != 3:
        continue

    distance = float(parts[0])
    temp = float(parts[1])
    vib = float(parts[2])

    print("Distance:", distance, "cm | Temp:", temp, "C | Vibration:", vib, "g")
