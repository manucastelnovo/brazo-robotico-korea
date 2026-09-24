#!/usr/bin/env python3
"""
HUENIT Gripper Module Test

Standalone test for the HUENIT gripper module based on the functions
found in HUENIT's robot.py.

Keyboard controls:
  0  -> gripper state 0
  1  -> gripper state 1
  2  -> gripper state 2
  Q  -> quit

Test the states one at a time and observe what the physical gripper does.
"""

import time
import serial
from serial.tools import list_ports

BAUD = 115200


def auto_detect_huenit_port():
    """Detect the HUENIT FTDI serial controller."""
    VID, PID = 0x0403, 0x6015
    ports = list(list_ports.comports())

    if not ports:
        raise RuntimeError("No serial ports found.")

    candidates = []

    for p in ports:
        score = 0
        vid = getattr(p, "vid", None)
        pid = getattr(p, "pid", None)
        product = (getattr(p, "product", "") or "").lower()
        manufacturer = (getattr(p, "manufacturer", "") or "").lower()
        serial_number = (getattr(p, "serial_number", "") or "")

        if vid == VID and pid == PID:
            score += 5
        if "huenit" in product or "huearm" in product:
            score += 3
        if serial_number and "HUECAM" in serial_number.upper():
            continue  # HUENIT AI Camera: same FTDI VID/PID, not the arm
        if serial_number and "HUEARM" in serial_number.upper():
            score += 2
        if "ftdi" in manufacturer:
            score += 1

        if score:
            candidates.append((score, p.device))

    if not candidates:
        available = ", ".join(
            f"{p.device}({getattr(p, 'product', None)})" for p in ports
        )
        raise RuntimeError(f"HUENIT not found. Available ports: {available}")

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


class GCodeIO:
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        time.sleep(1.0)

    def send(self, line):
        command = line.strip()
        print(f"  > {command}")
        self.ser.write((command + "\n").encode("ascii", "ignore"))
        self.ser.flush()
        time.sleep(0.05)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


def pump_off(g):
    g.send("M1400 A0")


def valve_on(g):
    g.send("M1401 A1")


def valve_off(g):
    g.send("M1401 A0")


def gripper(g, state):
    """
    Exact behavior derived from HUENIT robot.py.
    We intentionally do not label the states OPEN/CLOSE yet:
    first we verify them physically.
    """
    print(f"\nGRIPPER STATE {state}")

    if state == 0:
        pump_off(g)
        valve_on(g)
        time.sleep(0.3)
        pump_off(g)
        valve_off(g)

    elif state == 1:
        valve_off(g)
        g.send("M1400 A1000")

    elif state == 2:
        valve_on(g)
        g.send("M1400 A1000")
        time.sleep(3.0)
        g.send("M1400 A300")

    else:
        raise ValueError("Gripper state must be 0, 1, or 2.")


def main():
    print("\n===================================")
    print(" HUENIT GRIPPER MODULE TEST")
    print("===================================\n")

    try:
        port = auto_detect_huenit_port()
        print("HUENIT:", port)
        g = GCodeIO(port, BAUD)
    except Exception as exc:
        print("Connection error:", exc)
        return

    print("""
CONTROLS
-------------------------
0   Gripper state 0
1   Gripper state 1
2   Gripper state 2
Q   Quit
-------------------------

Keep your fingers clear of the gripper while testing.
""")

    try:
        while True:
            command = input("Command [0/1/2/Q]: ").strip().lower()

            if command == "0":
                gripper(g, 0)

            elif command == "1":
                gripper(g, 1)

            elif command == "2":
                gripper(g, 2)

            elif command == "q":
                break

            else:
                print("Use 0, 1, 2, or Q.")

    except KeyboardInterrupt:
        print("\nCTRL+C")

    finally:
        print("\nStopping gripper...")
        try:
            pump_off(g)
            valve_off(g)
        except Exception:
            pass

        g.close()
        print("Disconnected.")


if __name__ == "__main__":
    main()
