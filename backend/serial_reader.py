# backend/serial_reader.py
import serial
import json
import asyncio
import time # ADD THIS LINE
from typing import Dict, Generator

# Global serial port instance
_ser = None
_port_config = {"port": "/dev/ttyUSB0", "baud": 115200}

def set_serial_config(port: str, baud: int):
    global _port_config, _ser
    if _ser and _ser.is_open:
        _ser.close()
        _ser = None # Force re-opening with new config
    _port_config["port"] = port
    _port_config["baud"] = baud

async def get_serial_port() -> serial.Serial:
    global _ser
    if _ser is None or not _ser.is_open:
        try:
            _ser = serial.Serial(_port_config["port"], _port_config["baud"], timeout=0.3)
            await asyncio.sleep(0.1) # Give time for port to initialize
            print(f"Opened serial port {_port_config['port']} at {_port_config['baud']} baud.")
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            _ser = None # Clear _ser to ensure retry next time
            raise # Re-raise to indicate failure
    return _ser

def _blocking_read_serial_generator() -> Generator[Dict, None, None]:
    """Blocking generator to be run in a separate thread."""
    global _ser
    try:
        ser_instance = asyncio.run(get_serial_port()) # Get/open serial in this thread
        while True:
            line = ser_instance.readline().decode("utf-8").strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e} from line: {line}")
            else:
                # Add a small sleep to prevent busy-waiting if no data
                time.sleep(0.01) # This line was causing the "time not defined" error
    except Exception as e:
        print(f"Critical serial read error: {e}")
        # Optionally close and reset _ser here if needed for recovery

async def read_serial_async_queue(queue: asyncio.Queue):
    """
    Async function to constantly read from the serial port
    and put data into an asyncio.Queue.
    """
    loop = asyncio.get_event_loop()
    while True:
        try:
            # Run the blocking generator in a thread pool executor
            # This is key to making the serial read non-blocking for the event loop
            generator = await loop.run_in_executor(None, _blocking_read_serial_generator)
            # Iterate through the generator *object* to get yielded data
            for data in generator:
                if data:
                    await queue.put(data)
                # Small pause to yield control and allow queue to be processed
                await asyncio.sleep(0.001)
        except serial.SerialException as e:
            print(f"Serial port disconnected/error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)
            # Reset _ser to force re-open attempt
            global _ser
            if _ser and _ser.is_open:
                _ser.close()
            _ser = None
        except Exception as e:
            print(f"Unhandled error in serial_reader_async_queue: {e}")
            await asyncio.sleep(1) # Prevent tight loop on other errors

async def send_command(command: str) -> bool:
    """Sends a command string over serial to the ESP."""
    global _ser
    try:
        ser_instance = await get_serial_port()
        cmd_bytes = (command + "\n").encode("utf-8")
        await asyncio.get_event_loop().run_in_executor(None, ser_instance.write, cmd_bytes)
        print(f"Sent command: {command}")
        return True
    except serial.SerialException as e:
        print(f"Failed to send command: {e}")
        return False
    except Exception as e:
        print(f"Error sending command: {e}")
        return False