import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from web_app.bridge.arm_service import MockArm
from web_app.bridge.camera_service import MockCamera
from web_app.bridge.config import Settings
from web_app.bridge.main import create_app
from web_app.bridge.tokens import sign_token

SECRET = "test-secret"
ORIGIN = {"origin": "http://localhost:3000"}


def make_client(face_mode="1"):
    settings = Settings(secret=SECRET)
    camera = MockCamera(face_mode=face_mode, fps=50, face_delay_s=0, startup_s=0)
    arm = MockArm(latency_s=0)
    app = create_app(settings, camera_backend=camera, arm_backend=arm)
    return TestClient(app), app, arm


def test_health_reports_mock_devices():
    client, _, _ = make_client()
    with client:
        body = client.get("/health").json()
    assert body["camera"]["mode"] == "mock"
    assert body["camera"]["status"] == "off"
    assert body["arm"]["mode"] == "mock"


@pytest.mark.parametrize("grant", ["", "not-a-grant"])
def test_redeem_rejects_unknown_grants(grant):
    client, _, _ = make_client()
    with client:
        assert client.post("/auth/redeem", json={"grant": grant}).status_code == 401


def test_full_login_flow_then_jog():
    client, app, arm = make_client()
    with client:
        with client.websocket_connect("/camera/status", headers=ORIGIN) as ws:
            grant = None
            for _ in range(200):
                message = ws.receive_json()
                if "grant" in message:
                    grant = message["grant"]
                    break
        assert grant, "the mock face never produced a grant"
        assert message["state"] == "recognized" and message["idx"] == "1"

        response = client.post("/auth/redeem", json={"grant": grant})
        assert response.status_code == 200
        token = response.json()["token"]
        assert client.post("/auth/redeem", json={"grant": grant}).status_code == 401  # one-time

        deadline = time.monotonic() + 3
        while app.state.camera.status != "off" and time.monotonic() < deadline:
            time.sleep(0.02)
        assert app.state.camera.status == "off"  # camera released after login

        headers = {**ORIGIN, "cookie": f"huenit_session={token}"}
        with client.websocket_connect("/arm/jog", headers=headers) as ws:
            assert ws.receive_json()["type"] == "state"
            for _ in range(10):
                ws.send_json({"type": "jog", "vx": 1, "vy": 0, "vz": 0, "speed": 60, "seq": 1})
                time.sleep(0.03)
            assert app.state.jog.armed
        deadline = time.monotonic() + 1
        while app.state.jog.armed and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not app.state.jog.armed  # disconnect disarms
        assert any(line.startswith("G1 X") for line in arm.history)


def test_wrong_person_never_gets_a_grant():
    client, _, _ = make_client(face_mode="2")
    with client:
        with client.websocket_connect("/camera/status", headers=ORIGIN) as ws:
            messages = [ws.receive_json() for _ in range(15)]
    assert all("grant" not in m for m in messages)
    assert messages[-1]["idx"] == "2"


def expect_close(client, url, headers, code):
    with client.websocket_connect(url, headers=headers) as ws:
        with pytest.raises(WebSocketDisconnect) as info:
            ws.receive_json()
    assert info.value.code == code


def test_jog_rejects_missing_or_bad_token():
    client, _, _ = make_client()
    with client:
        expect_close(client, "/arm/jog", ORIGIN, 4401)
        expect_close(client, "/arm/jog?token=forged.token", ORIGIN, 4401)
        expired, _ = sign_token(SECRET, -10)
        expect_close(client, f"/arm/jog?token={expired}", ORIGIN, 4401)


def test_jog_rejects_foreign_or_missing_origin():
    client, _, _ = make_client()
    token, _ = sign_token(SECRET, 60)
    with client:
        expect_close(client, f"/arm/jog?token={token}", {"origin": "http://evil.example"}, 4403)
        expect_close(client, f"/arm/jog?token={token}", {}, 4403)
        expect_close(client, "/camera/status", {"origin": "http://evil.example"}, 4403)


def test_jog_accepts_query_token():
    client, app, _ = make_client()
    token, _ = sign_token(SECRET, 60)
    with client:
        with client.websocket_connect(f"/arm/jog?token={token}", headers=ORIGIN) as ws:
            state = ws.receive_json()
            assert state["type"] == "state" and state["armed"]
