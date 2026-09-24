"""
HUENIT arm helpers without HUENIT LAB.

Drop-in replacement for the two functions the simple scripts used from HUENIT's
own library (python_protocol_cores.robot_blocks.robot):

    from huenit_arm import checkConnection, moveG0

Same names and behavior, plain G-code over pyserial:
    checkConnection()   sends "M400" and returns True if the arm answers "ok"
    moveG0(x, y, z)     sends "G0 X.. Y.. Z.." and then "M400", so it returns
                        once the arm has finished moving

Differences with HUENIT's library:
  - It needs only `pip install pyserial` (no HUENIT LAB install).
  - It picks the arm port by its serial number ("..._HUEARMA"), never the AI
    camera, which uses the same USB chip. Override with $env:HUENIT_PORT.
  - It keeps one connection open instead of reopening the port per command.
"""

import atexit
import os
import time

import serial
from serial.tools import list_ports

BAUD = 115200
HUENIT_VID = 0x0403
HUENIT_PID = 0x6015

ACK_TIMEOUT = 5.0      # seconds to wait for "ok" to a normal command
MOVE_TIMEOUT = 60.0    # seconds to wait for "ok" to M400 (end of a move)

_serial = None


def detect_arm_port():
    """Return the COM port of the HUENIT arm, or None."""
    env_port = os.environ.get("HUENIT_PORT")
    if env_port:
        return env_port

    # The AI camera uses the same FTDI chip (same VID/PID); its serial ends in "HUECAMA".
    ports = [p for p in list_ports.comports()
             if "HUECAM" not in (p.serial_number or "").upper()]

    for p in ports:
        if "HUEARM" in (p.serial_number or "").upper():
            return p.device
    for p in ports:
        if p.vid == HUENIT_VID and p.pid == HUENIT_PID:
            return p.device
    return None


def _connection():
    global _serial
    if _serial is None:
        port = detect_arm_port()
        if not port:
            raise ConnectionError("HUENIT arm not found. Connect it or set $env:HUENIT_PORT.")
        _serial = serial.Serial(port, BAUD, timeout=0.05)
        _serial.reset_input_buffer()
    return _serial


def _close():
    global _serial
    if _serial is not None:
        try:
            _serial.close()
        finally:
            _serial = None


atexit.register(_close)


def sendCommand(command, timeout=ACK_TIMEOUT):
    """Send one G-code line and wait for "ok". Returns the other lines received."""
    ser = _connection()
    ser.write((command.strip() + "\n").encode("ascii"))
    ser.flush()

    extra = []
    end = time.time() + timeout
    while time.time() < end:
        line = ser.readline().decode("utf-8", "ignore").strip()
        if not line:
            continue
        if line.startswith("ok") or line.endswith("ok"):
            return extra
        if "Unknown" in line:
            print(f"[HUENIT] {line}")
        extra.append(line)
    raise TimeoutError(f"HUENIT did not answer 'ok' to: {command.strip()}")


def checkConnection():
    """True if the arm answers "ok" to M400."""
    try:
        sendCommand("M400", timeout=1.0)
        return True
    except (ConnectionError, TimeoutError, serial.SerialException) as e:
        print(f"[HUENIT] {e}")
        _close()
        return False


def moveG0(*args):
    """Move to (x, y, z) in mm and wait until the move is finished.

    Accepts moveG0(x, y, z) or moveG0((x, y, z)), like HUENIT's library.
    """
    if len(args) == 1 and isinstance(args[0], (tuple, list)):
        x, y, z = args[0]
    elif len(args) == 3:
        x, y, z = args
    else:
        raise ValueError("moveG0 expects (x, y, z) or a single (x, y, z) tuple/list.")

    sendCommand(f"G0 X{x:.3f} Y{y:.3f} Z{z:.3f}")
    sendCommand("M400", timeout=MOVE_TIMEOUT)


def getLoc():
    """Current (x, y, z) reported by the arm (M1008 A3), as a list of floats."""
    numbers = []
    for line in sendCommand("M1008 A3"):
        for token in line.replace(":", " ").replace(",", " ").split():
            try:
                numbers.append(float(token.lstrip("XYZxyz")))
            except ValueError:
                pass
    return numbers
