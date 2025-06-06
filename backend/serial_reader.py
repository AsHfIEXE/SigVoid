import serial
import json
from typing import Dict

def read_serial(port: str = "/dev/ttyUSB0", baud: int = 115200) -> Dict:
    try:
        ser = serial.Serial(port, baud, timeout=0.3)
        while True:
            try:
                line = ser.readline().decode("utf-8").strip()
                if line:
                    yield json.loads(line)
            except (serial.SerialException, json.JSONDecodeError) as e:
                print(f"Serial read error: {e}")
                continue
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
        return