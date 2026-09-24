"""HUENIT AI Camera access for the bridge: real camera (CameraStream) or a mock.

Every backend exposes start() / stop() / get_frame() -> (frame_bgr, face, count),
the same shape as huenit_face_viewer.CameraStream.get_frame().
"""

import logging
import os
import threading
import time

import cv2
import numpy as np

from . import _paths  # noqa: F401  (makes huenit_face_viewer importable)

log = logging.getLogger("bridge.camera")

FACE_SLOT = 1          # Face Recognition model slot trained in HUENIT OS
STOP_JOIN_S = 30.0     # the real camera start can block ~25 s


class RealCamera:
    """The HUENIT AI Camera running the trained Face Recognition model (slot 1)."""

    mode = "real"

    def __init__(self, slot=FACE_SLOT):
        self.slot = slot
        self.stream = None

    @staticmethod
    def find_port():
        """Camera port by USB serial ("..._HUECAMA"), so the arm is never probed."""
        import huenit_face_viewer as viewer

        env_port = os.environ.get("HUENIT_CAM_PORT")
        if env_port:
            return env_port
        for p in viewer.list_ports.comports():
            if "HUECAM" in (p.serial_number or "").upper():
                return p.device
        return viewer.detect_camera_port()

    def start(self):
        import huenit_face_viewer as viewer

        port = self.find_port()
        if not port:
            raise RuntimeError("HUENIT AI Camera not found. Connect it or set $env:HUENIT_CAM_PORT.")
        log.info("Starting camera on %s (face recognition slot %s)", port, self.slot)
        self.stream = viewer.CameraStream(port, ai_model=self.slot)
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream = None

    def get_frame(self):
        stream = self.stream
        return stream.get_frame() if stream is not None else (None, None, 0)


class MockCamera:
    """Synthetic 320x240 frames with scripted face results.

    face_mode (default $env:HUENIT_MOCK_FACE or "1"):
      "1"     ID 1 with percent 91 after `face_delay_s` seconds (login works)
      "2"     a different person (ID 2): login never succeeds
      "none"  no face at all
    """

    mode = "mock"

    def __init__(self, face_mode=None, fps=5.0, face_delay_s=2.0, startup_s=0.5):
        self.face_mode = face_mode or os.environ.get("HUENIT_MOCK_FACE", "1")
        self.fps = fps
        self.face_delay_s = face_delay_s
        self.startup_s = startup_s
        self.latest = None
        self.latest_face = None
        self.frame_count = 0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        time.sleep(self.startup_s)  # the real camera takes a while too
        self.stop_event.clear()
        self.started_at = time.monotonic()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _face(self, elapsed):
        if elapsed < self.face_delay_s or self.face_mode == "none":
            return None
        if self.face_mode == "2":
            return {"idx": "2", "rect": [100, 60, 120, 120], "score": None, "percent": 88.0}
        return {"idx": "1", "rect": [100, 60, 120, 120], "score": None, "percent": 91.0}

    def _loop(self):
        while not self.stop_event.is_set():
            elapsed = time.monotonic() - self.started_at
            frame = np.zeros((240, 320, 3), np.uint8)
            frame[:] = (40, 30, 20)
            x = int(160 + 110 * np.sin(elapsed * 1.5))
            cv2.circle(frame, (x, 170), 18, (0, 200, 255), -1)
            cv2.putText(frame, "MOCK CAMERA", (70, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            face = self._face(elapsed)
            if face:
                fx, fy, fw, fh = face["rect"]
                cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 255, 0), 2)
            with self.lock:
                self.latest = frame
                self.latest_face = face
                self.frame_count += 1
            self.stop_event.wait(1.0 / self.fps)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def get_frame(self):
        with self.lock:
            return self.latest, self.latest_face, self.frame_count


class CameraService:
    """Owns the camera lifecycle: start in the background, stop, restart.

    status: "off" | "starting" | "streaming" | "error"
    """

    def __init__(self, backend):
        self.backend = backend
        self.status = "off"
        self.error = None
        self._lock = threading.Lock()
        self._start_thread = None

    @property
    def mode(self):
        return self.backend.mode

    def ensure_started(self):
        """Start the camera if it is off or failed. Returns immediately."""
        with self._lock:
            if self.status in ("starting", "streaming"):
                return
            self.status = "starting"
            self.error = None
            self._start_thread = threading.Thread(target=self._run_start, daemon=True)
            self._start_thread.start()

    def _run_start(self):
        try:
            self.backend.start()
        except Exception as e:  # report it to the UI instead of crashing
            log.error("Camera start failed: %s", e)
            try:
                self.backend.stop()
            except Exception:
                pass
            with self._lock:
                if self.status == "starting":
                    self.status = "error"
                    self.error = str(e)
            return
        with self._lock:
            if self.status == "starting":
                self.status = "streaming"

    def stop(self):
        """Stop the camera (idempotent). Blocks until the camera is released."""
        with self._lock:
            start_thread = self._start_thread
            self._start_thread = None
            if self.status == "off" and start_thread is None:
                return
            self.status = "off"
        if start_thread is not None:
            start_thread.join(timeout=STOP_JOIN_S)
        try:
            self.backend.stop()
        except Exception as e:
            log.warning("Camera stop failed: %s", e)

    def get_frame(self):
        if self.status != "streaming":
            return None, None, 0
        return self.backend.get_frame()
