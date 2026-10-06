import glob
import sys
import time

import serial

import config


def find_port():
    if sys.platform.startswith("win"):
        import serial.tools.list_ports
        candidates = [p.device for p in serial.tools.list_ports.comports()]
    elif sys.platform == "darwin":
        candidates = glob.glob("/dev/tty.usbmodem*") + glob.glob("/dev/tty.usbserial*")
    else:
        candidates = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")

    if not candidates:
        raise RuntimeError("No Arduino serial port found. Set SERIAL_PORT in config.py.")
    return candidates[0]


class ArduinoSensors:
    def __init__(self, port=None, baud=None):
        self.port_name = port or config.SERIAL_PORT or find_port()
        self.ser = serial.Serial(self.port_name, baud or config.SERIAL_BAUD, timeout=3)
        time.sleep(2.0)
        self.ser.reset_input_buffer()
        self.water_temp = config.ASSUMED_WATER_TEMP_C
        print(f"[sensors] connected on {self.port_name}")

    def _parse(self, raw):
        if not raw or raw.startswith("#"):
            return None
        parts = raw.split(",")
        if len(parts) != 4:
            return None
        try:
            return (parts[0] == "1", float(parts[1]), float(parts[2]), float(parts[3]))
        except ValueError:
            return None

    def read(self):
        try:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
        except serial.SerialException as e:
            print(f"[sensors] serial error: {e}")
            raw = ""

        parsed = self._parse(raw)
        if parsed is None:
            return {
                "ok": False,
                "echo_time_s": None,
                "air_temp_c": config.ASSUMED_AIR_TEMP_C,
                "water_temp_c": self.water_temp,
                "vib_rms_g": 0.0,
            }

        ok, echo_us, air_temp, vib = parsed
        return {
            "ok": ok,
            "echo_time_s": echo_us / 1_000_000.0 if ok else None,
            "air_temp_c": air_temp,
            "water_temp_c": self.water_temp,
            "vib_rms_g": vib,
        }

    def cleanup(self):
        self.ser.close()


def make_sensors(port=None):
    return ArduinoSensors(port=port)
