"""Shared HMAC secret for session tokens.

The bridge signs tokens and the Next.js app verifies them, so both read the
same file: web_app/.session_secret (git-ignored). $env:HUENIT_SESSION_SECRET
overrides it.
"""

import os
import secrets
from pathlib import Path

SECRET_FILE = Path(__file__).resolve().parents[1] / ".session_secret"


def load_or_create(path=SECRET_FILE):
    env_secret = os.environ.get("HUENIT_SESSION_SECRET")
    if env_secret:
        return env_secret.strip()
    path = Path(path)
    if path.exists():
        value = path.read_text(encoding="ascii").strip()
        if value:
            return value
    value = secrets.token_hex(32)
    path.write_text(value + "\n", encoding="ascii")
    return value
