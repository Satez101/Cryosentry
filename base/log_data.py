import serial
import time
import csv

PORT = "COM12"
BAUD = 115200
SENSOR_HEIGHT = 60.0
OUTPUT_FILE = "readings.csv"

ser = serial.Serial(PORT, BAUD, timeout=3)
time.sleep(2)

f = open(OUTPUT_FILE, "w", newline="")
writer = csv.writer(f)
writer.writerow(["time", "level_cm", "temp_c", "vibration_g"])

print("Logging to", OUTPUT_FILE)

try:
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
        row = [time.time(), round(level, 2), parts[1], parts[2]]
        writer.writerow(row)
        f.flush()
        print(row)

except KeyboardInterrupt:
    f.close()
    print("Stopped.")
