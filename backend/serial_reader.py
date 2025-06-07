# backend/serial_reader.py
import serial
import json
import asyncio
import time # Import the time module
from typing import Dict, Generator

# Global serial port instance
_ser = None
_port_config = {"port": "/dev/ttyUSB0", "baud": 115200}

def set_serial_config(port: str, baud: int):
    """Sets the global serial port configuration. Closes existing port if open."""
    global _port_config, _ser
    if _ser and _ser.is_open:
        _ser.close()
        _ser = None # Force re-opening with new config
    _port_config["port"] = port
    _port_config["baud"] = baud
    print(f"Serial config updated to port: {_port_config['port']}, baud: {_port_config['baud']}")


async def get_serial_port() -> serial.Serial:
    """Gets and opens the global serial port instance. Retries if port is not available."""
    global _ser
    if _ser is None or not _ser.is_open:
        while True: # Loop to continuously try opening the port
            try:
                _ser = serial.Serial(_port_config["port"], _port_config["baud"], timeout=0.3)
                # Small delay after opening to allow ESP to initialize
                await asyncio.sleep(0.5)
                print(f"Successfully opened serial port {_port_config['port']} at {_port_config['baud']} baud.")
                break # Exit loop on successful open
            except serial.SerialException as e:
                print(f"Serial port error: {e}. Retrying in 3 seconds...")
                _ser = None # Clear _ser to ensure retry next time
                await asyncio.sleep(3) # Wait before retrying
            except Exception as e:
                print(f"Unexpected error when opening serial port: {e}. Retrying in 3 seconds...")
                _ser = None
                await asyncio.sleep(3)
    return _ser

def _blocking_read_serial_generator() -> Generator[Dict, None, None]:
    """
    Blocking generator to read lines from serial and parse JSON.
    This function is intended to be run in a separate thread via ThreadPoolExecutor.
    """
    try:
        global _ser
        if _ser is None or not _ser.is_open:
            raise serial.SerialException("Serial port is not open. Call get_serial_port() first.")
        ser_instance = asyncio.run(get_serial_port()) # This will try to open a new loop if needed, or use existing.

        while True:
            line = ser_instance.readline().decode("utf-8").strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    # Log malformed JSON but keep reading
                    print(f"JSON decode error: {e} from line: {line}")
            else:
                # Small sleep to prevent busy-waiting if no data
                time.sleep(0.01)
    except Exception as e:
        # This catch is for errors within the blocking read loop itself.
        print(f"Critical error in blocking serial read generator: {e}")
        # The calling async function (read_serial_async_queue) should handle reconnection.
        # Raising it here to propagate back to the executor's future.
        raise

async def read_serial_async_queue(queue: asyncio.Queue):
    """
    Async function to constantly read from the serial port using a blocking generator
    (run in an executor) and put parsed data into an asyncio.Queue.
    Handles reconnection logic.
    """
    loop = asyncio.get_event_loop()
    while True:
        try:
            # Ensure the serial port is open before attempting to get the generator
            await get_serial_port() # This will ensure _ser is set and open

            # Run the blocking generator in a thread pool executor
            # This is key to making the serial read non-blocking for the event loop
            generator = await loop.run_in_executor(None, _blocking_read_serial_generator)
            
            # Iterate through the generator *object* to get yielded data
            for data in generator: # This loop processes data from the generator as it yields
                if data:
                    await queue.put(data)
                # Small pause to yield control and allow queue to be processed
                await asyncio.sleep(0.001) # Avoid blocking the queue consumer
        except serial.SerialException as e:
            # This error is typically due to port disconnect or permissions
            print(f"Serial port disconnected/error: {e}. Attempting to reconnect in 5s...")
            # Close existing port to allow a clean re-open attempt
            global _ser
            if _ser and _ser.is_open:
                _ser.close()
            _ser = None # Clear to force `get_serial_port` to reopen
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unhandled error in read_serial_async_queue: {e}")
            await asyncio.sleep(1) # Prevent tight loop on other errors

async def send_command(command: str) -> bool:
    """Sends a command string over serial to the ESP, ensuring a newline."""
    global _ser
    try:
        ser_instance = await get_serial_port()
        cmd_bytes = (command + "\n").encode("utf-8")
        # Use run_in_executor for the blocking write operation
        await asyncio.get_event_loop().run_in_executor(None, ser_instance.write, cmd_bytes)
        print(f"Sent command: {command}")
        return True
    except serial.SerialException as e:
        print(f"Failed to send command due to serial error: {e}")
        return False
    except Exception as e:
        print(f"Error sending command: {e}")
        return False