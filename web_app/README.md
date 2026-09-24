# HUENIT face-login web app

A local web app with two parts:

- **Bridge** (`web_app/bridge`, Python, FastAPI): owns the camera and arm COM ports and reuses
  `huenit_face_viewer.CameraStream` and `huenit_arm.py`.
- **UI** (`web_app/ui`, Next.js): the `/login` and `/control` pages. Not built yet.

> **Local demo only.** The bridge listens on `127.0.0.1` only. 2D face recognition can be fooled
> with a photo, so this login is **not** real security.

## Run the bridge

Run these from the repo root. Install once:

```powershell
$PY = ".\.venv\Scripts\python.exe"   # or just "python"; see SETUP.md
& $PY -m pip install -r web_app\bridge\requirements.txt
```

### Mock mode (no hardware, the default)

```powershell
& $PY -m web_app.bridge
```

- The mock camera shows synthetic frames and "recognizes" ID 1 after 2 s.
- To test the other cases, set `$env:HUENIT_MOCK_FACE = "2"` (a different person) or `"none"`.
- The mock arm only logs the G-code it would send.

### Real hardware

1. Close the camera viewer and every gamepad or arm script. Only one process can own each COM port.
2. Enable the real devices (you can turn on just one of them):

   ```powershell
   $env:HUENIT_MOCK_CAMERA = "0"
   $env:HUENIT_MOCK_ARM = "0"
   & $PY -m web_app.bridge
   ```

Ports are detected by USB serial number: `..._HUECAMA` is the camera, `..._HUEARMA` is the arm.
To set them by hand, use `$env:HUENIT_CAM_PORT` and `$env:HUENIT_PORT`.

The camera must have a Face Recognition model saved in **slot 1** (HUENIT OS > AI Models > Face
Recognition). In recognition mode it streams at about 2 fps.

### Tests

```powershell
& $PY -m pytest web_app\bridge\tests
```

## Endpoints

All endpoints are on `http://127.0.0.1:8765`.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Camera and arm mode (mock or real) and status |
| `GET /camera/stream` | MJPEG video; starts the camera |
| `WS /camera/status` | Recognition state for each new frame; includes a one-time `grant` once ID 1 is recognized |
| `POST /auth/redeem` | `{grant}` -> `{token, exp}`; also stops the camera |
| `WS /arm/jog` | Needs a session token (`huenit_session` cookie or `?token=`). Messages: `jog`, `stop`, `home`, `ping` |

## How login works

The bridge decides, not the browser. It needs ID `"1"` with `percent >= 80` on **3 consecutive
new frames** within **10 s**. It then issues a one-time grant, valid for 30 s. The grant is
exchanged for an HMAC-signed session token that lasts 30 min.

The signing secret is stored in `web_app/.session_secret`, which is git-ignored and created on
first run. The Next.js app will read the same file.

## Arm safety

- The bridge waits for the arm's `ok` after every command, so only one command is ever in flight.
  Moves never pile up in a queue.
- Motion stops at once when any of these happens:
  - no message from the browser for 0.3 s,
  - the WebSocket disconnects,
  - a `stop` message arrives.
- The bridge caps speed at 150 mm/s, no matter what the browser sends.
