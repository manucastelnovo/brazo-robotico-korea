"""Signed session tokens and one-time login grants.

Token format (easy to verify from Next.js with Web Crypto):
    base64url(json payload) + "." + base64url(HMAC-SHA256(secret, first part))
Payload: {"sub": "face-1", "exp": <unix seconds>, "jti": <random id>}
"""

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time

SUBJECT = "face-1"


def _b64encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(secret, body):
    return hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()


def sign_token(secret, ttl_s, now=None):
    """Return (token, exp)."""
    now = time.time() if now is None else now
    exp = int(now + ttl_s)
    payload = {"sub": SUBJECT, "exp": exp, "jti": secrets.token_urlsafe(12)}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_b64encode(_signature(secret, body))}", exp


def verify_token(secret, token, now=None):
    """Return the payload dict if the token is valid and not expired, else None."""
    if not token or token.count(".") != 1:
        return None
    body, signature = token.split(".")
    try:
        if not hmac.compare_digest(_b64decode(signature), _signature(secret, body)):
            return None
        payload = json.loads(_b64decode(body))
    except (ValueError, UnicodeError):
        return None
    now = time.time() if now is None else now
    if not isinstance(payload, dict) or payload.get("sub") != SUBJECT:
        return None
    if not isinstance(payload.get("exp"), int) or payload["exp"] <= now:
        return None
    return payload


class GrantStore:
    """One-time random codes handed to the browser after a successful face match."""

    def __init__(self, ttl_s, clock=time.monotonic):
        self.ttl_s = ttl_s
        self.clock = clock
        self._grants = {}
        self._lock = threading.Lock()

    def create(self):
        code = secrets.token_urlsafe(24)
        with self._lock:
            self._grants[code] = self.clock() + self.ttl_s
        return code

    def redeem(self, code):
        """True once per valid, unexpired code."""
        with self._lock:
            now = self.clock()
            self._grants = {c: exp for c, exp in self._grants.items() if exp > now}
            return self._grants.pop(code, None) is not None
