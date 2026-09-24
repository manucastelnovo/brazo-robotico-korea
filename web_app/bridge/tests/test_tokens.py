from conftest import FakeClock
from web_app.bridge.tokens import GrantStore, sign_token, verify_token

SECRET = "test-secret"


def test_valid_token_verifies():
    token, exp = sign_token(SECRET, 60, now=1000)
    payload = verify_token(SECRET, token, now=1010)
    assert payload["sub"] == "face-1"
    assert payload["exp"] == exp == 1060


def test_expired_token_is_rejected():
    token, _ = sign_token(SECRET, 60, now=1000)
    assert verify_token(SECRET, token, now=1060) is None


def test_tampered_or_foreign_token_is_rejected():
    token, _ = sign_token(SECRET, 60, now=1000)
    body, signature = token.split(".")
    flipped = ("A" if body[0] != "A" else "B") + body[1:]
    assert verify_token(SECRET, f"{flipped}.{signature}", now=1010) is None
    assert verify_token("other-secret", token, now=1010) is None
    assert verify_token(SECRET, "garbage", now=1010) is None
    assert verify_token(SECRET, None, now=1010) is None
    assert verify_token(SECRET, "a.b.c", now=1010) is None


def test_grant_is_one_time():
    grants = GrantStore(ttl_s=30, clock=FakeClock())
    code = grants.create()
    assert grants.redeem(code)
    assert not grants.redeem(code)
    assert not grants.redeem("unknown")


def test_grant_expires():
    clock = FakeClock()
    grants = GrantStore(ttl_s=30, clock=clock)
    code = grants.create()
    clock.advance(31)
    assert not grants.redeem(code)
