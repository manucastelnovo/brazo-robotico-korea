"""Bridge settings. The main values can be overridden with environment variables."""

import os
from dataclasses import dataclass, field

HOST = "127.0.0.1"  # never bind to other interfaces: this is a local demo
PORT = 8765
DEFAULT_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def _env_flag(name, default):
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "")


def _env_float(name, default):
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    mock_camera: bool = True
    mock_arm: bool = True

    # Face login: idx "1" with percent >= threshold on N consecutive new frames
    # within window_s seconds of the first match.
    threshold_percent: float = 80.0
    required_streak: int = 3
    window_s: float = 10.0
    grant_ttl_s: float = 30.0
    session_ttl_s: float = 30 * 60.0
    allowed_origins: tuple = DEFAULT_ORIGINS
    secret: str = field(default=None, repr=False)  # None = load or create the shared file

    # Gamepad jog (same approach as huenit_gamepad_gripper.py)
    deadman_timeout_s: float = 0.3
    control_hz: float = 50.0
    default_speed_mm_s: float = 60.0
    max_speed_mm_s: float = 150.0
    feed_mm_min: float = 1200.0
    ramp_alpha: float = 0.16
    min_step_mm: float = 0.002

    @classmethod
    def from_env(cls):
        origins = os.environ.get("HUENIT_ALLOWED_ORIGINS")
        return cls(
            mock_camera=_env_flag("HUENIT_MOCK_CAMERA", "1"),
            mock_arm=_env_flag("HUENIT_MOCK_ARM", "1"),
            threshold_percent=_env_float("HUENIT_FACE_THRESHOLD", "80"),
            required_streak=int(os.environ.get("HUENIT_FACE_STREAK", "3")),
            window_s=_env_float("HUENIT_FACE_WINDOW_S", "10"),
            allowed_origins=tuple(o.strip() for o in origins.split(",")) if origins else DEFAULT_ORIGINS,
            max_speed_mm_s=min(_env_float("HUENIT_MAX_SPEED", "150"), 150.0),
        )
