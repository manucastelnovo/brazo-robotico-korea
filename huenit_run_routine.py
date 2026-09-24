#!/usr/bin/env python3
"""
HUENIT saved-routine runner.

Runs JSON routines created by the HUENIT gamepad Teach system without
requiring the controller.

Commands:
    python huenit_run_routine.py list
    python huenit_run_routine.py play <routine>
    python huenit_run_routine.py play <routine> --repeat 5
    python huenit_run_routine.py loop <routine>
    python huenit_run_routine.py name <routine> <friendly_name>
    python huenit_run_routine.py copy <routine> <friendly_name>
    python huenit_run_routine.py home

Routine names may be given with or without ".json".
"""

import argparse
import json
import time
import shutil
from pathlib import Path

import serial
from serial.tools import list_ports


# ---------------- CONFIG ----------------

BAUD = 115200
FEED_MM_MIN = 1200

ROUTINES_DIR = Path.home() / "Desktop" / "HUENIT_Routines"

VAC_ON_CMD = "M1400 A1023"
VAC_OFF_CMD = "M1400 A0"
VALVE_ON_CMD = "M1401 A1"
VALVE_OFF_CMD = "M1401 A0"

RELEASE_TIME_S = 0.3


# ---------------- CONNECTION ----------------

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
        self.ser.reset_input_buffer()

    def send(self, line):
        self.ser.write((line.strip() + "\n").encode("ascii", "ignore"))
        self.ser.flush()

    def wait_until_motion_complete(self, timeout=120.0):
        """
        M400 only becomes useful to this standalone runner if we keep the
        serial port open and wait for HUENIT's 'ok' response.
        """
        self.ser.reset_input_buffer()
        self.send("M400")

        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue

            reply = raw.decode("utf-8", "ignore").strip()
            if reply:
                print(f"HUENIT: {reply}")

            if "ok" in reply.lower():
                return

        raise TimeoutError("HUENIT did not finish the queued motion before timeout.")

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


# ---------------- MODULE ACTIONS ----------------

def vacuum_on(g):
    g.send(VALVE_OFF_CMD)
    g.send(VAC_ON_CMD)


def vacuum_off(g):
    g.send(VAC_OFF_CMD)


def vacuum_release(g):
    g.send(VAC_OFF_CMD)
    g.send(VALVE_ON_CMD)
    time.sleep(RELEASE_TIME_S)
    g.send(VALVE_OFF_CMD)


def gripper_open(g):
    # HUENIT gripper state 1
    g.send(VALVE_OFF_CMD)
    g.send("M1400 A1000")


def gripper_close(g):
    # HUENIT gripper state 2
    g.send(VALVE_ON_CMD)
    g.send("M1400 A1000")
    time.sleep(3.0)
    g.send("M1400 A300")


def gripper_release(g):
    # HUENIT gripper state 0
    g.send(VAC_OFF_CMD)
    g.send(VALVE_ON_CMD)
    time.sleep(0.3)
    g.send(VAC_OFF_CMD)
    g.send(VALVE_OFF_CMD)


def go_home(g):
    print("Going HOME...")
    g.send("G90")
    g.send("M1008 A5")
    g.wait_until_motion_complete()
    g.send("G91")
    print("HOME complete.")


# ---------------- ROUTINE FILES ----------------

def ensure_routines_dir():
    ROUTINES_DIR.mkdir(parents=True, exist_ok=True)


def routine_files():
    ensure_routines_dir()
    return sorted(
        ROUTINES_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def resolve_routine(name):
    """
    Resolve a routine by:
      - full path
      - filename with/without .json
      - friendly alias stored inside the JSON
    """
    candidate = Path(name)

    if candidate.exists():
        return candidate

    file_candidate = candidate
    if file_candidate.suffix.lower() != ".json":
        file_candidate = file_candidate.with_suffix(".json")

    file_candidate = ROUTINES_DIR / file_candidate.name

    if file_candidate.exists():
        return file_candidate

    # Friendly alias lookup.
    wanted = name.strip().lower()

    for path in routine_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if isinstance(payload, dict):
            alias = str(payload.get("name", "")).strip().lower()
            if alias and alias == wanted:
                return path

    raise FileNotFoundError(
        f'Routine or alias "{name}" not found in {ROUTINES_DIR}'
    )


def load_routine(path):
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, dict):
        events = payload.get("events")
        if not isinstance(events, list):
            raise ValueError("Routine JSON does not contain an events list.")
        return payload, events

    if isinstance(payload, list):
        # Backward-compatible fallback.
        return {"events": payload}, payload

    raise ValueError("Unsupported routine JSON format.")


def list_routines():
    files = routine_files()

    print(f"\nRoutine folder:\n{ROUTINES_DIR}\n")

    if not files:
        print("No saved routines.")
        return

    print("SAVED ROUTINES")
    print("-" * 72)

    for index, path in enumerate(files, start=1):
        try:
            payload, events = load_routine(path)
            event_count = len(events)
            alias = str(payload.get("name", "")).strip() if isinstance(payload, dict) else ""
        except Exception:
            event_count = "?"
            alias = ""

        modified = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(path.stat().st_mtime),
        )

        alias_text = f"  name:{alias}" if alias else ""
        print(
            f"{index:>2}. {path.name:<38} "
            f"events:{str(event_count):>5}  {modified}{alias_text}"
        )


def validate_friendly_name(name):
    name = name.strip()
    if not name:
        raise ValueError("Routine name cannot be empty.")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if any(ch not in allowed for ch in name):
        raise ValueError(
            "Use only letters, numbers, underscore (_) and hyphen (-) in routine names."
        )

    return name


def set_routine_name(path, friendly_name, rename_file=True):
    """
    Store a friendly name inside the routine JSON.
    By default also rename the JSON file to <friendly_name>.json.
    """
    friendly_name = validate_friendly_name(friendly_name)
    payload, events = load_routine(path)

    if not isinstance(payload, dict):
        payload = {"events": events}

    # Prevent duplicate aliases.
    wanted = friendly_name.lower()
    for other in routine_files():
        if other.resolve() == path.resolve():
            continue
        try:
            other_payload = json.loads(other.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(other_payload, dict):
            other_name = str(other_payload.get("name", "")).strip().lower()
            if other_name == wanted:
                raise ValueError(
                    f'Another routine already uses the name "{friendly_name}".'
                )

    payload["name"] = friendly_name

    destination = path
    if rename_file:
        destination = ROUTINES_DIR / f"{friendly_name}.json"
        if destination.exists() and destination.resolve() != path.resolve():
            raise ValueError(f'File "{destination.name}" already exists.')

    # Write first, then remove old file if the filename changed.
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if destination.resolve() != path.resolve():
        path.unlink()

    return destination


def copy_routine_with_name(path, friendly_name):
    """Create a named copy while keeping the original timestamped routine."""
    friendly_name = validate_friendly_name(friendly_name)
    payload, events = load_routine(path)

    if not isinstance(payload, dict):
        payload = {"events": events}

    destination = ROUTINES_DIR / f"{friendly_name}.json"
    if destination.exists():
        raise ValueError(f'File "{destination.name}" already exists.')

    # Prevent duplicate aliases.
    wanted = friendly_name.lower()
    for other in routine_files():
        try:
            other_payload = json.loads(other.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(other_payload, dict):
            other_name = str(other_payload.get("name", "")).strip().lower()
            if other_name == wanted:
                raise ValueError(
                    f'Another routine already uses the name "{friendly_name}".'
                )

    payload["name"] = friendly_name
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


# ---------------- PLAYBACK ----------------

def execute_event(g, event, feed_mm_min):
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
            g.send("G1 " + " ".join(parts) + f" F{feed_mm_min}")

    elif event_type == "vacuum":
        if event.get("state"):
            vacuum_on(g)
        else:
            vacuum_off(g)

    elif event_type == "release":
        vacuum_release(g)

    elif event_type == "home":
        go_home(g)

    elif event_type == "gripper":
        action = event.get("action")

        if action == "open":
            gripper_open(g)
        elif action == "close":
            gripper_close(g)
        elif action == "release":
            gripper_release(g)
        else:
            print(f'WARNING: unknown gripper action "{action}"')

    else:
        print(f'WARNING: unknown event type "{event_type}"')


def play_once(g, payload, events, cycle=None):
    feed = int(payload.get("feed_mm_min", FEED_MM_MIN))

    if cycle is None:
        print(f"\nPLAY: {len(events)} events")
    else:
        print(f"\nPLAY cycle {cycle}: {len(events)} events")

    # Teach recordings are relative movements.
    g.send("G21")
    g.send("G91")

    previous_t = 0.0

    for event in events:
        target_t = float(event.get("t", previous_t))
        delay = max(0.0, target_t - previous_t)

        if delay:
            time.sleep(delay)

        execute_event(g, event, feed)
        previous_t = target_t

    print("Waiting for HUENIT to finish all queued movements...")
    g.wait_until_motion_complete()
    print("Cycle complete.")


def run_play(path, repeat):
    payload, events = load_routine(path)

    if not events:
        print("Routine contains no events.")
        return

    port = auto_detect_huenit_port()
    print("HUENIT:", port)
    print("Routine:", path.name)

    g = GCodeIO(port, BAUD)

    try:
        for cycle in range(1, repeat + 1):
            play_once(g, payload, events, cycle if repeat > 1 else None)

        print("\nPLAY complete.")

    finally:
        g.close()
        print("Disconnected.")


def run_loop(path):
    payload, events = load_routine(path)

    if not events:
        print("Routine contains no events.")
        return

    port = auto_detect_huenit_port()
    print("HUENIT:", port)
    print("Routine:", path.name)
    print("\nLOOP mode. Press CTRL+C to stop.")

    g = GCodeIO(port, BAUD)
    cycle = 1

    try:
        while True:
            play_once(g, payload, events, cycle)
            cycle += 1

    except KeyboardInterrupt:
        print("\n\nLOOP stopped by user.")

        # Keep the port alive briefly while HUENIT handles what was already sent.
        # CTRL+C stops future routine events; it cannot retract commands already
        # buffered inside the controller.
        try:
            g.wait_until_motion_complete(timeout=30.0)
        except Exception:
            pass

    finally:
        g.close()
        print("Disconnected.")


def run_home():
    port = auto_detect_huenit_port()
    print("HUENIT:", port)

    g = GCodeIO(port, BAUD)

    try:
        go_home(g)
    finally:
        g.close()
        print("Disconnected.")


# ---------------- CLI ----------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Run HUENIT Teach routines without a gamepad."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List saved routines.")

    play = sub.add_parser("play", help="Play a saved routine.")
    play.add_argument("routine", help="Routine filename or path.")
    play.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of repetitions (default: 1).",
    )

    loop = sub.add_parser("loop", help="Loop a routine until CTRL+C.")
    loop.add_argument("routine", help="Routine filename or path.")

    name_cmd = sub.add_parser(
        "name",
        help="Give a routine a friendly name and rename its JSON file.",
    )
    name_cmd.add_argument("routine", help="Existing routine filename/path/alias.")
    name_cmd.add_argument("friendly_name", help="New short name, e.g. coffee.")

    copy_cmd = sub.add_parser(
        "copy",
        help="Create a friendly named copy and keep the original routine.",
    )
    copy_cmd.add_argument("routine", help="Existing routine filename/path/alias.")
    copy_cmd.add_argument("friendly_name", help="Name for the copy.")

    sub.add_parser("home", help="Send HUENIT to HOME.")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "list":
            list_routines()

        elif args.command == "play":
            if args.repeat < 1:
                parser.error("--repeat must be 1 or greater.")

            path = resolve_routine(args.routine)
            run_play(path, args.repeat)

        elif args.command == "loop":
            path = resolve_routine(args.routine)
            run_loop(path)

        elif args.command == "name":
            path = resolve_routine(args.routine)
            new_path = set_routine_name(path, args.friendly_name, rename_file=True)
            print(f'Routine named "{args.friendly_name}".')
            print(f"Saved as: {new_path}")

        elif args.command == "copy":
            path = resolve_routine(args.routine)
            new_path = copy_routine_with_name(path, args.friendly_name)
            print(f'Named copy created: "{args.friendly_name}"')
            print(f"Saved as: {new_path}")

        elif args.command == "home":
            run_home()

    except (FileNotFoundError, ValueError, RuntimeError, serial.SerialException) as exc:
        print(f"\nERROR: {exc}")


if __name__ == "__main__":
    main()
