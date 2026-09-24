"""HUENIT arm jog control for the bridge.

Same continuous G1 jog as huenit_gamepad_gripper.py (G91 relative mode, small
steps, ramped velocity, deadzone applied in the browser), with two safety
changes:

  - Flow control: every command waits for the arm's "ok" before the next one,
    so there is never more than one command in flight. The step size follows
    the real elapsed time, so a slow arm gets bigger steps, not a queue.
  - Dead man switch: if the browser stops sending messages for
    deadman_timeout_s, or the last client disconnects, motion stops at once.
"""

import logging
import math
import threading
import time

from . import _paths  # noqa: F401  (makes huenit_arm importable)

log = logging.getLogger("bridge.arm")

ACK_TIMEOUT_S = 5.0
MOVE_TIMEOUT_S = 60.0
MAX_DT_S = 0.1          # cap one step after a stall (e.g. a slow "ok")
FEED_MARGIN = 1.2       # each step's feed rate is fast enough to finish within dt

# Same setup and HOME sequence as huenit_gamepad_gripper.py
SETUP_COMMANDS = ("G90", "G21", "G91")  # millimetres + relative positioning
HOME_COMMANDS = (
    ("G90", ACK_TIMEOUT_S),
    ("M1008 A5", MOVE_TIMEOUT_S),
    ("M400", MOVE_TIMEOUT_S),
    ("G91", ACK_TIMEOUT_S),
)


class RealArm:
    """The HUENIT arm over USB, through huenit_arm.sendCommand (waits for "ok")."""

    mode = "real"

    def connect(self):
        import huenit_arm

        port = huenit_arm.detect_arm_port()
        if not port:
            raise ConnectionError("HUENIT arm not found. Connect it or set $env:HUENIT_PORT.")
        log.info("Arm on %s", port)
        huenit_arm.sendCommand("M400", timeout=ACK_TIMEOUT_S)

    def send(self, line, timeout=ACK_TIMEOUT_S):
        import huenit_arm

        huenit_arm.sendCommand(line, timeout=timeout)

    def close(self):
        import huenit_arm

        huenit_arm._close()


class MockArm:
    """Logs the G-code instead of moving anything, with a simulated "ok" latency."""

    mode = "mock"

    def __init__(self, latency_s=0.008):
        self.latency_s = latency_s
        self.history = []
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = threading.Lock()

    def connect(self):
        log.info("Mock arm connected (G-code is only logged)")

    def send(self, line, timeout=ACK_TIMEOUT_S):
        with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.latency_s:
                time.sleep(self.latency_s)
            log.debug("G-code: %s", line)
            self.history.append(line)
        finally:
            with self._lock:
                self.in_flight -= 1

    def close(self):
        pass


def _clamp(value, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(value):
        return 0.0
    return max(low, min(high, value))


class JogController:
    """Turns jog vectors from the browser into G1 steps, one command at a time.

    All G-code is sent from a single thread (the control loop), so commands can
    never overlap. step() is public so tests can drive it with a fake clock.
    """

    def __init__(self, backend, settings, clock=time.monotonic):
        self.backend = backend
        self.settings = settings
        self.clock = clock
        self.speed = settings.default_speed_mm_s
        self.connected = False
        self.error = None
        self.last_gcode = None
        self._lock = threading.Lock()
        self._armed = set()
        self._target = (0.0, 0.0, 0.0)
        self._last_message = None
        self._home_requested = False
        self._velocity = [0.0, 0.0, 0.0]
        self._residual = [0.0, 0.0, 0.0]
        self._last_step = None
        self._stop_event = threading.Event()
        self._thread = None

    # ---------------- called from the web handlers ----------------

    def arm(self, client_id):
        with self._lock:
            self._armed.add(client_id)
            self._last_message = self.clock()

    def disarm(self, client_id):
        with self._lock:
            self._armed.discard(client_id)
            if not self._armed:
                self._stop_locked()

    @property
    def armed(self):
        return bool(self._armed)

    def touch(self):
        """Any message from the browser keeps the dead man switch alive."""
        with self._lock:
            self._last_message = self.clock()

    def set_vector(self, vx, vy, vz, speed=None):
        with self._lock:
            self._target = (_clamp(vx, -1, 1), _clamp(vy, -1, 1), _clamp(vz, -1, 1))
            if speed is not None:
                self.speed = _clamp(speed, 1.0, self.settings.max_speed_mm_s) or 1.0
            self._last_message = self.clock()

    def stop(self):
        with self._lock:
            self._stop_locked()

    def _stop_locked(self):
        self._target = (0.0, 0.0, 0.0)
        self._velocity = [0.0, 0.0, 0.0]
        self._residual = [0.0, 0.0, 0.0]
        self._home_requested = False

    def home(self):
        with self._lock:
            self._stop_locked()
            if self._armed:
                self._home_requested = True

    def state(self):
        return {
            "type": "state",
            "speed": round(self.speed, 1),
            "armed": self.armed,
            "connected": self.connected,
            "error": self.error,
            "last_gcode": self.last_gcode,
        }

    # ---------------- control loop ----------------

    def _send(self, line, timeout=ACK_TIMEOUT_S):
        self.backend.send(line, timeout=timeout)
        self.last_gcode = line

    def connect(self):
        self.backend.connect()
        for line in SETUP_COMMANDS:
            self._send(line)
        self.connected = True
        self.error = None

    def step(self):
        """One control tick. Sends at most one G1 (or the HOME sequence)."""
        now = self.clock()
        dt = 0.0 if self._last_step is None else min(now - self._last_step, MAX_DT_S)
        self._last_step = now

        with self._lock:
            if self._home_requested:
                self._home_requested = False
                home = True
            else:
                home = False
                alive = (
                    bool(self._armed)
                    and self._last_message is not None
                    and now - self._last_message <= self.settings.deadman_timeout_s
                )
                if not alive:
                    # Hard stop, no ramp down: the browser is gone or silent.
                    self._stop_locked()
                    return None
                target = [t * self.speed for t in self._target]
                alpha = self.settings.ramp_alpha
                deltas = []
                for i in range(3):
                    self._velocity[i] += (target[i] - self._velocity[i]) * alpha
                    deltas.append(self._velocity[i] * dt + self._residual[i])

        if home:
            for line, timeout in HOME_COMMANDS:
                self._send(line, timeout=timeout)
            self._last_step = self.clock()
            return "HOME"

        parts = []
        with self._lock:
            for i, axis in enumerate("XYZ"):
                if abs(deltas[i]) >= self.settings.min_step_mm:
                    parts.append(f"{axis}{deltas[i]:.4f}")
                    self._residual[i] = 0.0
                else:
                    self._residual[i] = deltas[i]
        if not parts or dt <= 0:
            return None

        # The feed rate must let the arm finish this step within dt,
        # otherwise steps pile up in the arm's planner.
        distance = math.sqrt(sum(d * d for d in deltas))
        feed = max(self.settings.feed_mm_min, distance / dt * 60.0 * FEED_MARGIN)
        line = "G1 " + " ".join(parts) + f" F{feed:.0f}"
        self._send(line)
        return line

    def _loop(self):
        period = 1.0 / self.settings.control_hz
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                if not self.connected:
                    self.connect()
                self.step()
            except Exception as e:  # lost the arm: stop, report, retry later
                log.error("Arm error: %s", e)
                self.connected = False
                self.error = str(e)
                self.stop()
                try:
                    self.backend.close()
                except Exception:
                    pass
                self._stop_event.wait(1.0)
                continue
            self._stop_event.wait(max(0.0, period - (time.monotonic() - started)))

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def close(self):
        self.stop()
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        try:
            self.backend.close()
        except Exception:
            pass
