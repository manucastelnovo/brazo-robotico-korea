#!/usr/bin/env python3
"""
HUENIT + Logitech F310
Gamepad control with Teach & Replay.

Controls:
  Left stick        X / Y
  Right stick Y     Z
  A                 Vacuum ON
  B                 Vacuum OFF
  RT                Active RELEASE
  Left stick click  STOP REPLAY / LOOP
  Right stick click LOOP
D-pad LEFT      Gripper OPEN
D-pad RIGHT     Gripper CLOSE
D-pad DOWN      Gripper RELEASE last routine
  D-pad LEFT       Gripper OPEN
  D-pad RIGHT      Gripper CLOSE
  D-pad DOWN       Gripper RELEASE
  LB                Slower
  RB                Faster
  X                 Start/Stop TEACH
  Y                 REPLAY last routine
  START             HOME
  BACK              Exit

Notes:
- Based on the working HUENIT continuous G1 jog approach.
- Encoder polling (M1008 A3) is intentionally not used.
- Teach records the relative G1 displacements actually sent to HUENIT.
"""

import time
import json
from pathlib import Path

import pygame
import serial
from serial.tools import list_ports

# ---------------- HUENIT CONFIG ----------------

BAUD = 115200
CONTROL_HZ = 80
START_SPEED_MM_S = 120.0
FEED_MM_MIN = 1200
RAMP_ALPHA = 0.16
MIN_STEP_MM = 0.002
DEADZONE = 0.15

VAC_ON_CMD = "M1400 A1023"
VAC_OFF_CMD = "M1400 A0"
VALVE_ON_CMD = "M1401 A1"
VALVE_OFF_CMD = "M1401 A0"
RELEASE_TIME_S = 0.3

# ---------------- F310 XINPUT MAPPING ----------------
# Verify these with test_gamepad.py if your Windows mapping differs.

AXIS_X = 0
AXIS_Y = 1
AXIS_Z = 3
AXIS_LT = 2
AXIS_RT = 5
TRIGGER_THRESHOLD = 0.5
TRIGGER_DELTA = 0.7

BUTTON_A = 0
BUTTON_B = 1
BUTTON_X = 2
BUTTON_Y = 3
BUTTON_LB = 4
BUTTON_RB = 5
BUTTON_BACK = 6
BUTTON_START = 7
BUTTON_L3 = 8
BUTTON_R3 = 9

# ---------------- ROUTINES ----------------

ROUTINES_DIR = Path.home() / "Desktop" / "HUENIT_Routines"
ROUTINES_DIR.mkdir(parents=True, exist_ok=True)


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
        self.ser = serial.Serial(port, baud, timeout=0.02)
        time.sleep(1.0)

    def send(self, line):
        self.ser.write((line.strip() + "\n").encode("ascii", "ignore"))
        self.ser.flush()

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


def gripper_open(g):
    """HUENIT gripper state 1: actively open."""
    g.send(VALVE_OFF_CMD)
    g.send("M1400 A1000")


def gripper_close(g):
    """HUENIT gripper state 2: close/grip, then reduce holding power."""
    g.send(VALVE_ON_CMD)
    g.send("M1400 A1000")
    time.sleep(3.0)
    g.send("M1400 A300")


def gripper_release(g):
    """HUENIT gripper state 0: release pneumatic pressure."""
    g.send(VAC_OFF_CMD)
    g.send(VALVE_ON_CMD)
    time.sleep(0.3)
    g.send(VAC_OFF_CMD)
    g.send(VALVE_OFF_CMD)


def apply_deadzone(value):
    if abs(value) < DEADZONE:
        return 0.0

    sign = 1.0 if value > 0 else -1.0
    scaled = (abs(value) - DEADZONE) / (1.0 - DEADZONE)
    return sign * scaled


def save_routine(events):
    """Save the current recording as a timestamped JSON file."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = ROUTINES_DIR / f"routine_{stamp}.json"

    payload = {
        "format": "huenit_gamepad_teach_v1",
        "created": stamp,
        "feed_mm_min": FEED_MM_MIN,
        "events": events,
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def replay_routine(g, events, pad):
    """Replay relative movements/actions and allow LT to abort safely."""
    if not events:
        print("\nNo routine recorded.")
        return

    print(f"\nREPLAY: {len(events)} events")
    print("LEFT STICK CLICK = STOP REPLAY")

    previous_t = 0.0

    def stop_requested():
        pygame.event.pump()
        return bool(pad.get_button(BUTTON_L3))

    def interruptible_wait(seconds):
        end_time = time.perf_counter() + max(0.0, seconds)
        while time.perf_counter() < end_time:
            if stop_requested():
                return True
            time.sleep(min(0.01, max(0.0, end_time - time.perf_counter())))
        return stop_requested()

    for event in events:
        if stop_requested():
            g.send("M400")
            print("\nREPLAY STOPPED by LEFT STICK CLICK.")
            return

        target_t = float(event.get("t", previous_t))
        delay = max(0.0, target_t - previous_t)

        if delay and interruptible_wait(delay):
            g.send("M400")
            print("\nREPLAY STOPPED by LEFT STICK CLICK.")
            return

        event_type = event.get("type")

        if event_type == "move":
            dx = float(event.get("dx", 0.0))
            dy = float(event.get("dy", 0.0))
            dz = float(event.get("dz", 0.0))

            parts = []
            if dx:
                parts.append(f"X{dx:.4f}")
            if dy:
                parts.append(f"Y{dy:.4f}")
            if dz:
                parts.append(f"Z{dz:.4f}")

            if parts:
                g.send("G1 " + " ".join(parts) + f" F{FEED_MM_MIN}")

        elif event_type == "vacuum":
            if event.get("state"):
                g.send(VALVE_OFF_CMD)
                g.send(VAC_ON_CMD)
            else:
                g.send(VAC_OFF_CMD)

        elif event_type == "release":
            g.send(VAC_OFF_CMD)
            g.send(VALVE_ON_CMD)
            if interruptible_wait(RELEASE_TIME_S):
                g.send(VALVE_OFF_CMD)
                g.send("M400")
                print("\nREPLAY STOPPED by LEFT STICK CLICK.")
                return
            g.send(VALVE_OFF_CMD)

        elif event_type == "home":
            g.send("G90")
            g.send("M1008 A5")
            g.send("M400")
            g.send("G91")

        elif event_type == "gripper":
            action = event.get("action")

            if action == "open":
                gripper_open(g)

            elif action == "close":
                # Keep STOP responsive during the 3-second close phase.
                g.send(VALVE_ON_CMD)
                g.send("M1400 A1000")
                if interruptible_wait(3.0):
                    g.send(VAC_OFF_CMD)
                    g.send(VALVE_OFF_CMD)
                    g.send("M400")
                    print("\nREPLAY STOPPED by LEFT STICK CLICK.")
                    return
                g.send("M1400 A300")

            elif action == "release":
                g.send(VAC_OFF_CMD)
                g.send(VALVE_ON_CMD)
                if interruptible_wait(0.3):
                    g.send(VAC_OFF_CMD)
                    g.send(VALVE_OFF_CMD)
                    g.send("M400")
                    print("\nREPLAY STOPPED by LEFT STICK CLICK.")
                    return
                g.send(VAC_OFF_CMD)
                g.send(VALVE_OFF_CMD)

        previous_t = target_t

    g.send("M400")
    print("\nREPLAY complete.")


def loop_routine(g, events, pad):
    """Continuously replay the last routine until L3 is pressed."""
    if not events:
        print("\nNo routine recorded.")
        return

    print("\nLOOP started.")
    print("LEFT STICK CLICK = STOP LOOP")

    cycle = 1

    while True:
        pygame.event.pump()

        if pad.get_button(BUTTON_L3):
            g.send("M400")
            print("\nLOOP STOPPED by LEFT STICK CLICK.")
            return

        print(f"\nLOOP cycle {cycle}")
        replay_routine(g, events, pad)

        # replay_routine returns both when completed and when L3 aborts.
        # Check L3 immediately to distinguish an abort from a normal cycle.
        pygame.event.pump()
        if pad.get_button(BUTTON_L3):
            g.send("M400")
            print("\nLOOP STOPPED.")
            # Wait for release so the click is not carried into manual control.
            while pad.get_button(BUTTON_L3):
                pygame.event.pump()
                time.sleep(0.01)
            return

        cycle += 1


def main():
    print("\n========================================")
    print(" HUENIT + LOGITECH F310 + TEACH/REPLAY")
    print("========================================\n")

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("ERROR: No gamepad detected.")
        pygame.quit()
        return

    pad = pygame.joystick.Joystick(0)
    pad.init()
    print("Gamepad:", pad.get_name())


    try:
        port = auto_detect_huenit_port()
    except Exception as exc:
        print("\nHUENIT is not connected.")
        print(exc)
        print("\nGamepad detection is OK. Connect HUENIT later and run again.")
        pygame.quit()
        return

    print("HUENIT:", port)

    try:
        g = GCodeIO(port, BAUD)
    except Exception as exc:
        print("Serial error:", exc)
        pygame.quit()
        return

    print("""
CONTROLS
----------------------------------------
Left stick       X / Y
Right stick Y    Z
A                Vacuum ON
B                Vacuum OFF
RT               Active RELEASE
Left stick click STOP REPLAY / LOOP
Right stick click LOOP
D-pad LEFT      Gripper OPEN
D-pad RIGHT     Gripper CLOSE
D-pad DOWN      Gripper RELEASE
LB               Slower
RB               Faster
X                Start / Stop TEACH
Y                REPLAY
START            HOME
BACK             Exit
----------------------------------------
""")

    # Same setup used by the working jog program:
    # millimetres + relative positioning.
    g.send("G90")
    time.sleep(0.1)
    g.send("G21")
    time.sleep(0.1)
    g.send("G91")
    time.sleep(0.1)

    speed = START_SPEED_MM_S

    vx = vy = vz = 0.0
    residual_x = residual_y = residual_z = 0.0

    vacuum = False
    running = True
    previous_buttons = {}
    previous_hat = (0, 0)
    previous_rt = False

    teaching = False
    teach_start = None
    recording = []

    last_time = time.time()

    def pressed(button):
        current = bool(pad.get_button(button))
        previous = previous_buttons.get(button, False)
        previous_buttons[button] = current
        return current and not previous

    try:
        while running:
            pygame.event.pump()

            # -------- Buttons --------

            if pressed(BUTTON_BACK):
                running = False
                continue

            if pressed(BUTTON_X):
                if not teaching:
                    recording = []
                    teaching = True
                    teach_start = time.perf_counter()
                    print("\nTEACH started. Move HUENIT with the gamepad.")
                else:
                    teaching = False
                    path = save_routine(recording)
                    print(f"\nTEACH stopped: {len(recording)} events.")
                    print(f"Saved: {path}")

            if pressed(BUTTON_Y) and not teaching:
                # Bring commanded velocity to zero before replay.
                vx = vy = vz = 0.0
                residual_x = residual_y = residual_z = 0.0
                replay_routine(g, recording, pad)
                last_time = time.time()

            if pressed(BUTTON_R3) and not teaching:
                # Continuous replay until L3 is pressed.
                vx = vy = vz = 0.0
                residual_x = residual_y = residual_z = 0.0
                loop_routine(g, recording, pad)
                last_time = time.time()

            if pressed(BUTTON_START):
                # HOME is available in both CONTROL and TEACH modes.
                # When teaching, record the HOME action so Replay can reproduce it.
                vx = vy = vz = 0.0
                residual_x = residual_y = residual_z = 0.0

                if teaching:
                    recording.append({
                        "t": time.perf_counter() - teach_start,
                        "type": "home",
                    })

                print("\nGoing HOME...")
                g.send("G90")
                g.send("M1008 A5")
                g.send("M400")
                g.send("G91")
                last_time = time.time()
                print("\nHOME complete.")

            if pressed(BUTTON_A):
                if not vacuum:
                    g.send(VALVE_OFF_CMD)
                    g.send(VAC_ON_CMD)
                    vacuum = True
                    print("\nVacuum ON")
                    if teaching:
                        recording.append({
                            "t": time.perf_counter() - teach_start,
                            "type": "vacuum",
                            "state": True,
                        })

            if pressed(BUTTON_B):
                if vacuum:
                    g.send(VAC_OFF_CMD)
                    vacuum = False
                    print("\nVacuum OFF")
                    if teaching:
                        recording.append({
                            "t": time.perf_counter() - teach_start,
                            "type": "vacuum",
                            "state": False,
                        })

            # RT = active vacuum release.
            # Logitech F310 triggers are analog axes in XInput mode.
            rt_value = pad.get_axis(AXIS_RT)
            rt_pressed = rt_value > TRIGGER_THRESHOLD

            if rt_pressed and not previous_rt:
                g.send(VAC_OFF_CMD)
                g.send(VALVE_ON_CMD)
                time.sleep(RELEASE_TIME_S)
                g.send(VALVE_OFF_CMD)
                vacuum = False
                print("\nActive RELEASE")

                if teaching:
                    recording.append({
                        "t": time.perf_counter() - teach_start,
                        "type": "release",
                    })

            previous_rt = rt_pressed

            if pressed(BUTTON_LB):
                speed = max(1.0, speed * 0.75)
                print(f"\nSpeed: {speed:.1f} mm/s")

            if pressed(BUTTON_RB):
                # No artificial upper limit: user requested unrestricted increase.
                speed = speed * 1.25
                print(f"\nSpeed: {speed:.1f} mm/s")

            # -------- Gripper / D-pad --------
            # pygame hats: left=(-1,0), right=(1,0), down=(0,-1)
            hat = pad.get_hat(0) if pad.get_numhats() > 0 else (0, 0)

            if hat != previous_hat:
                action = None

                if hat == (-1, 0):
                    print("\nGripper OPEN")
                    gripper_open(g)
                    action = "open"

                elif hat == (1, 0):
                    print("\nGripper CLOSE")
                    gripper_close(g)
                    action = "close"

                elif hat == (0, -1):
                    print("\nGripper RELEASE")
                    gripper_release(g)
                    action = "release"

                if action and teaching:
                    recording.append({
                        "t": time.perf_counter() - teach_start,
                        "type": "gripper",
                        "action": action,
                    })

                previous_hat = hat

            # -------- Analog input --------

            x_input = apply_deadzone(pad.get_axis(AXIS_X))
            y_input = apply_deadzone(-pad.get_axis(AXIS_Y))
            z_input = apply_deadzone(-pad.get_axis(AXIS_Z))

            # -------- Fixed-rate control loop --------

            now = time.time()
            dt = now - last_time
            period = 1.0 / CONTROL_HZ

            if dt < period:
                time.sleep(period - dt)
                now = time.time()
                dt = now - last_time

            last_time = now

            target_x = x_input * speed
            target_y = y_input * speed
            target_z = z_input * speed

            vx += (target_x - vx) * RAMP_ALPHA
            vy += (target_y - vy) * RAMP_ALPHA
            vz += (target_z - vz) * RAMP_ALPHA

            dx = vx * dt + residual_x
            dy = vy * dt + residual_y
            dz = vz * dt + residual_z

            parts = []
            sent_dx = sent_dy = sent_dz = 0.0

            if abs(dx) >= MIN_STEP_MM:
                parts.append(f"X{dx:.4f}")
                sent_dx = dx
                residual_x = 0.0
            else:
                residual_x = dx

            if abs(dy) >= MIN_STEP_MM:
                parts.append(f"Y{dy:.4f}")
                sent_dy = dy
                residual_y = 0.0
            else:
                residual_y = dy

            if abs(dz) >= MIN_STEP_MM:
                parts.append(f"Z{dz:.4f}")
                sent_dz = dz
                residual_z = 0.0
            else:
                residual_z = dz

            if parts:
                g.send("G1 " + " ".join(parts) + f" F{FEED_MM_MIN}")

                if teaching:
                    recording.append({
                        "t": time.perf_counter() - teach_start,
                        "type": "move",
                        "dx": round(sent_dx, 4),
                        "dy": round(sent_dy, 4),
                        "dz": round(sent_dz, 4),
                    })

            mode = "TEACH" if teaching else "CONTROL"

            print(
                f"\r[{mode}] "
                f"X:{x_input:+.2f} "
                f"Y:{y_input:+.2f} "
                f"Z:{z_input:+.2f} | "
                f"Speed:{speed:.1f} mm/s | "
                f"Vac:{'ON' if vacuum else 'OFF'} | "
                f"Events:{len(recording)}     ",
                end="",
                flush=True,
            )

    except KeyboardInterrupt:
        print("\nCTRL+C")

    finally:
        print("\nStopping HUENIT...")

        try:
            g.send("M400")
            g.send("G90")
            if vacuum:
                g.send(VAC_OFF_CMD)
        except Exception:
            pass

        g.close()
        pygame.quit()
        print("Disconnected.")


if __name__ == "__main__":
    main()
