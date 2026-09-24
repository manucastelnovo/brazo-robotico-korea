# HUENIT Camera Face Viewer

Shows the HUENIT AI Camera video on the PC and draws a box around detected faces.

## Run

Connect the AI Camera to the PC with USB-C, then from this folder:

```powershell
& "C:\Program Files\Huenit robotics\resources\huenit_py\huenit_env_win\python.exe" .\huenit_face_viewer.py
```

The camera port is auto-detected (the arm on another port is ignored). To force it:

```powershell
... .\huenit_face_viewer.py --port COM6
```

## Where faces are detected (`--ai`)

| Mode | Command | What you get |
|---|---|---|
| `pc` (default) | `.\huenit_face_viewer.py` | OpenCV on the PC finds faces (~8 fps) |
| `camera` | `.\huenit_face_viewer.py --ai camera` | HUENIT built-in `face_detect` model on the camera AI chip (~6 fps) |
| `1`..`5` | `.\huenit_face_viewer.py --ai 1 --names "1=Manu,2=Marcos"` | Your trained Face Recognition model: shows WHO it is (~2 fps) |

Recognition mode is slower on purpose: its three AI models fill the camera memory, so the camera cannot
compress JPEG and sends raw pixels (every other row) at 2,000,000 baud instead.

To use `1`..`5`, first train and save a model on the camera (HUENIT OS):

1. AI Models > Face Recognition. Tap the screen to register each face.
2. Hold the camera button 2 s > End Training.
3. Hold it 2 s again > Save Current Model > pick an empty slot 1-5 (slot 6 cannot be saved).

`--names` maps the IDs the camera reports to names. IDs follow the training order starting at 1
(first face registered = `ID 1`).

## Keys

- `Q` / `ESC`: quit (the camera goes back to HUENIT OS)
- `S`: save a snapshot

## Options

| Option | Default | Meaning |
|---|---|---|
| `--ai` | pc | `pc`, `camera` or a model slot `1`-`5` |
| `--names` | - | Names for trained IDs, e.g. `"1=Manu,2=Marcos"` |
| `--quality` | 60 | JPEG quality on the camera. Higher = sharper but fewer fps |
| `--scale` | 2.0 | Window zoom |
| `--no-detect` | off | Video only |
| `--no-flip` | off | Disable vertical flip + mirror |
| `--no-reset` | off | Leave the camera in the MicroPython REPL on exit |

## How it works

1. The camera runs MicroPython (CanMV, K210). The script interrupts HUENIT OS with Ctrl-C
   and pastes a small program (Ctrl-E ... Ctrl-D). Nothing is written to the camera flash.
2. The camera sends JPEG frames over USB at 1,500,000 baud (~7 fps at quality 60).
3. The PC cuts frames between the `FFD8` / `FFD9` markers and decodes them.
4. In `camera` / slot modes the camera runs `cam.ai_init(...)`, `cam.compute(img)` and `cam.get_output()`
   (the same API HUENIT LAB block coding generates) and sends a line `@F <id> [x, y, w, h, ...]` before each frame.

Only the slot modes recognize who a face is; `pc` and `camera` only find faces.

## Troubleshooting

- A `Corrupt JPEG data` line in the console is harmless (one frame lost a few bytes and is skipped).
- If the camera stops answering, unplug and replug its USB cable. The script also tries a reset by itself.
