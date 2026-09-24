"""FastAPI bridge: camera stream + face login + gamepad jog over WebSocket.

Local demo only: bind to 127.0.0.1. 2D face recognition can be fooled with a
photo, so this login is not real security.
"""

import asyncio
import itertools
import logging
import threading
import time
from contextlib import asynccontextmanager

import cv2
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import secret as secret_store
from .arm_service import JogController, MockArm, RealArm
from .auth import RecognitionGate
from .camera_service import CameraService, MockCamera, RealCamera
from .config import Settings
from .tokens import GrantStore, sign_token, verify_token

log = logging.getLogger("bridge")

SESSION_COOKIE = "huenit_session"
POLL_S = 0.05                 # how often the async handlers look for a new frame
STATE_PUSH_S = 0.2            # jog state updates sent to the browser
JPEG_QUALITY = 80
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN_ORIGIN = 4403


class RedeemRequest(BaseModel):
    grant: str


def create_app(settings=None, camera_backend=None, arm_backend=None):
    settings = settings or Settings.from_env()
    secret = settings.secret or secret_store.load_or_create()
    if camera_backend is None:
        camera_backend = MockCamera() if settings.mock_camera else RealCamera()
    if arm_backend is None:
        arm_backend = MockArm() if settings.mock_arm else RealArm()

    camera = CameraService(camera_backend)
    jog = JogController(arm_backend, settings)
    grants = GrantStore(settings.grant_ttl_s)
    client_ids = itertools.count(1)

    @asynccontextmanager
    async def lifespan(app):
        jog.start()
        yield
        jog.close()
        await asyncio.to_thread(camera.stop)

    app = FastAPI(title="HUENIT bridge", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.settings = settings
    app.state.camera = camera
    app.state.jog = jog
    app.state.grants = grants

    def origin_allowed(websocket):
        return websocket.headers.get("origin") in settings.allowed_origins

    def stop_camera_in_background():
        threading.Thread(target=camera.stop, daemon=True).start()

    @app.get("/health")
    def health():
        return {
            "camera": {"mode": camera.mode, "status": camera.status, "error": camera.error},
            "arm": {"mode": arm_backend.mode, "connected": jog.connected, "error": jog.error},
        }

    @app.get("/camera/stream")
    async def camera_stream():
        camera.ensure_started()

        async def frames():
            last_count = None
            while camera.status in ("starting", "streaming"):
                frame, _face, count = camera.get_frame()
                if frame is not None and count != last_count:
                    last_count = count
                    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                    if ok:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                await asyncio.sleep(POLL_S)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/camera/status")
    async def camera_status(websocket: WebSocket):
        await websocket.accept()
        if not origin_allowed(websocket):
            await websocket.close(code=CLOSE_FORBIDDEN_ORIGIN)
            return
        camera.ensure_started()
        gate = RecognitionGate(settings.threshold_percent, settings.required_streak, settings.window_s)
        last_count = None
        last_status = None
        granted = False
        try:
            while True:
                _frame, face, count = camera.get_frame()
                if count != last_count or camera.status != last_status:
                    last_count, last_status = count, camera.status
                    message = gate.update(face, count, time.monotonic()) if count else gate.state()
                    message["camera_status"] = camera.status
                    message["camera_error"] = camera.error
                    if gate.recognized and not granted:
                        granted = True
                        message["grant"] = grants.create()
                    await websocket.send_json(message)
                await asyncio.sleep(POLL_S)
        except WebSocketDisconnect:
            pass

    @app.post("/auth/redeem")
    def redeem(body: RedeemRequest):
        if not grants.redeem(body.grant):
            raise HTTPException(status_code=401, detail="Invalid or expired grant")
        token, exp = sign_token(secret, settings.session_ttl_s)
        stop_camera_in_background()  # login done: release the camera
        return {"token": token, "exp": exp}

    @app.websocket("/arm/jog")
    async def arm_jog(websocket: WebSocket):
        await websocket.accept()
        if not origin_allowed(websocket):
            await websocket.close(code=CLOSE_FORBIDDEN_ORIGIN)
            return
        token = websocket.cookies.get(SESSION_COOKIE) or websocket.query_params.get("token")
        if verify_token(secret, token) is None:
            await websocket.close(code=CLOSE_UNAUTHORIZED)
            return

        client_id = next(client_ids)
        jog.arm(client_id)

        async def receive():
            while True:
                message = await websocket.receive_json()
                kind = message.get("type") if isinstance(message, dict) else None
                if kind == "jog":
                    jog.set_vector(message.get("vx"), message.get("vy"), message.get("vz"), message.get("speed"))
                elif kind == "stop":
                    jog.stop()
                    jog.touch()
                elif kind == "home":
                    jog.home()
                    jog.touch()
                else:  # "ping" or anything else still proves the browser is alive
                    jog.touch()

        async def push_state():
            while True:
                await websocket.send_json(jog.state())
                await asyncio.sleep(STATE_PUSH_S)

        tasks = [asyncio.create_task(receive()), asyncio.create_task(push_state())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            jog.disarm(client_id)  # disconnect = stop
            for task in tasks:
                try:
                    await task
                except (asyncio.CancelledError, WebSocketDisconnect, Exception):
                    pass

    return app
