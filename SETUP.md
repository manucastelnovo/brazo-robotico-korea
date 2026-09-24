# Setup: HUENIT robot arm + AI camera scripts

Get these Python scripts running on a Windows PC with a HUENIT robotic arm and the HUENIT AI Camera:
write text with a pen, control the arm with a gamepad, and watch the camera (with face recognition) on the PC.

> You only need Python and `pip`. HUENIT LAB is **not** required, except for firmware updates and a few
> legacy scripts (see [What needs HUENIT LAB](#what-needs-huenit-lab)).

## Quick path

1. Install [Python 3.10 or newer](https://www.python.org/downloads/). Check **"Add python.exe to PATH"**.
2. Open PowerShell in this folder, create a virtual environment and install the dependencies into it:
   ```powershell
   python -m venv .venv
   $PY = ".\.venv\Scripts\python.exe"
   & $PY -m pip install -r requirements.txt
   ```
3. Try it without hardware:
   ```powershell
   & $PY .\huenit_text_writer\huenit_text_writer.py "HELLO" --dry-run
   ```
4. You should see a list of `G1 X.. Y.. Z..` commands. You're ready. Continue with [Run the scripts](#4-run-the-scripts).

> `$PY` points to the Python inside `.venv`, so packages never land in your system Python.
> Define it again in every new PowerShell window (from this folder).

---

## 1. What you need

| Item | Notes |
|---|---|
| Windows 10/11 PC | Tested on Windows 11 |
| Python 3.10+ | Tested with 3.10 and 3.11 |
| HUENIT robotic arm | With its DC power supply |
| Pen holder module | Only for writing/drawing |
| HUENIT AI Camera | Only for the camera viewer |
| USB-C cables | USB 3.1 or better is recommended by HUENIT |
| Logitech F310 gamepad | Optional, only for the gamepad scripts |

## 2. Install the software

### Python dependencies

[`requirements.txt`](requirements.txt) installs everything the scripts use:

| Package | Used by |
|---|---|
| `pyserial` | All scripts (USB serial link to the arm and the camera) |
| `opencv-python` (4.x) | Camera viewer. OpenCV 5 is excluded: it removed the face detector used by `--ai pc` |
| `numpy` | Camera viewer |
| `pygame` | Gamepad scripts |

In every new PowerShell window, define `$PY` again (step 2 of the Quick path).

### USB driver

The arm and the camera use an FTDI USB-serial chip. Windows 10/11 normally installs its driver automatically
the first time you plug them in. If no COM port appears, install the
[FTDI VCP driver](https://ftdichip.com/drivers/vcp-drivers/).

### What needs HUENIT LAB

[HUENIT LAB](https://huenit.gitbook.io/huenit-manual-en/huenit-user-manual/how-to-use-huenit-lab/0.-getting-ready/installing-huenit-lab)
is only needed for:

- **Firmware updates** (recommended once): **[...] > Update Firmware**, one device at a time.
  These scripts were tested with camera firmware MicroPython v2.0.67.
- **Legacy scripts** that import HUENIT's own library from its install folder:
  `calibrar_z.py`, `calibrar_z_fino.py`, `cuadrado.py`, `circulo_cuadrado.py`, `mover_huenit.py`, `secuencia_huenit.py`.
  Run them with HUENIT's bundled Python:
  ```powershell
  & "C:\Program Files\Huenit robotics\resources\huenit_py\huenit_env_win\python.exe" .\calibrar_z_fino.py
  ```

## 3. Connect the hardware

### Robotic arm

1. Plug the power supply into **DC IN** on the back. The arm moves to its home position (X0 Y180 Z0).
2. Connect the arm's **PC** USB-C port to the computer.

### AI Camera

1. Connect the camera's USB-C port **directly to the computer**.
2. The camera cannot be connected to the PC and to the arm at the same time.

> ⚠️ HUENIT warns: if the camera is already attached to the arm, connect the arm's DC power **before** the camera,
> otherwise an overcurrent can reach the camera.

### Find the COM ports

Both devices show up as "USB Serial Port (COMx)" with the same FTDI chip. The serial number tells them apart:

```powershell
& $PY -m serial.tools.list_ports -v
```

```text
COM5    hwid: USB VID:PID=0403:6015 SER=D30GQNFF_HUEARMA   <- arm
COM6    hwid: USB VID:PID=0403:6015 SER=D30GTIL7_HUECAMA   <- camera
```

- The scripts auto-detect the ports using that serial number, so both devices can stay connected at the same time.
- To force a port, use `--port COM5` or `$env:HUENIT_PORT = "COM5"` (arm) and `--port COM6` (camera viewer).

## 4. Run the scripts

Run everything from PowerShell inside this folder, with `$PY` defined (see the Quick path).

### Write text with the arm

1. Put the pen in the pen holder and tape a sheet of paper in front of the arm (around X 0..60, Y 215..245 mm).
2. Check the pen height (see [Calibrate the pen height](#calibrate-the-pen-height)).
3. Write:
   ```powershell
   & $PY .\huenit_text_writer\huenit_text_writer.py "HELLO WORLD" --height 15
   ```

| Option | Meaning |
|---|---|
| `--dry-run` | Print the G-code, don't move the arm |
| `--height 15` | Letter height in mm (default 10) |
| `--x 5 --y 220` | Start position in mm |
| `--port COM5` | Arm port |

Supported characters: `A-Z`, `0-9`, space, `-`, `.`. Other characters are skipped and leave a space.

Prefer questions instead of flags? Run the interactive version with no arguments:
`& $PY .\huenit_text_writer_interactive\huenit_text_writer.py`

### Calibrate the pen height

The pen must press slightly on the paper (the holder has a spring). The writer uses:

| Constant | Value | Where |
|---|---|---|
| `Z_ARRIBA` (pen up) | `-45.0` | `huenit_text_writer/huenit_text_writer.py` |
| `Z_DIBUJO` (pen down) | `-56.0` | same file |

If your table, paper or pen differ, find your value and put it in `Z_DIBUJO` (and ~10 mm higher in `Z_ARRIBA`):

- **With HUENIT LAB:** run `calibrar_z_fino.py` with HUENIT's Python (see [What needs HUENIT LAB](#what-needs-huenit-lab)).
  Press **ENTER** to lower 0.2 mm, `u` + ENTER to raise, `q` + ENTER to finish, and note `Z FINAL`.
- **Without it:** use `--dry-run` values as a guide and adjust `Z_DIBUJO` in small steps (0.5 mm) until the
  pen touches the paper and the spring compresses a little.

### Watch the AI Camera on the PC

```powershell
& $PY .\huenit_camera_viewer\huenit_face_viewer.py
```

A window opens with the live video. **Q/ESC** quits (the camera goes back to HUENIT OS), **S** saves a snapshot.

| Mode | Command | Speed |
|---|---|---|
| Faces found by the PC | `--ai pc` (default) | ~8 fps |
| Faces found by the camera | `--ai camera` | ~6 fps |
| **Who** it is (your trained model) | `--ai 1 --names "1=Alice,2=Bob"` | ~2 fps |

To use `--ai 1`, first train and save a face model **on the camera** (it can't be done from the PC):

1. HUENIT OS > **AI Model > Face Recognition**.
2. Face the camera and tap the screen to register the face. The first face gets `ID 1`, the second one `ID 2`, and so on.
3. Hold the side button **2 s** > **End Training**.
4. Hold it **2 s** again > **Save Current Model** > choose an empty slot **1-5** (slot 6 is not saved).

More details: [`huenit_camera_viewer/README.md`](huenit_camera_viewer/README.md).

### Control the arm with a gamepad (optional)

```powershell
& $PY .\test_gamepad.py                 # check the gamepad is detected
& $PY .\huenit_gamepad_gripper.py       # move, vacuum, gripper, teach & replay
& $PY .\huenit_run_routine.py list      # replay saved routines without the gamepad
```

The controls are listed at the top of each script.

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Reinstall Python with "Add python.exe to PATH", or use `py` instead of `python`. |
| `ModuleNotFoundError` | You ran `python` instead of `& $PY`. Define `$PY` (Quick path, step 2). |
| No COM port appears | Check the cable and install the [FTDI VCP driver](https://ftdichip.com/drivers/vcp-drivers/). |
| `No se encontró HUENIT` / arm not found | Check DC power and the USB cable. Pass `--port COMx`. |
| The arm writes in the air or tears the paper | Adjust `Z_DIBUJO` (see [Calibrate the pen height](#calibrate-the-pen-height)). |
| `No Reachable` / the arm refuses a move | The point is out of reach. Use smaller text or move `--x/--y` closer to X0 Y200. |
| Camera viewer: `HUENIT AI Camera not found` | Connect the camera directly to the PC, not through the arm. |
| Camera stops answering | Unplug and replug its USB cable. The viewer also resets it by itself. |
| `AI model slot N is empty` | Train and save a Face Recognition model in that slot (see above). |
| `'cv2' has no attribute 'CascadeClassifier'` | OpenCV 5 got installed: `& $PY -m pip install "opencv-python<5"`. |
| `Corrupt JPEG data` in the console | Harmless: one damaged frame was skipped. |

## Checklist

- [ ] `python --version` prints 3.10 or newer
- [ ] `& $PY -m pip install -r requirements.txt` finished without errors
- [ ] `--dry-run` prints G-code
- [ ] The arm writes `HELLO` on paper
- [ ] The camera viewer shows live video

## Next step

- Camera internals and all viewer options: [`huenit_camera_viewer/README.md`](huenit_camera_viewer/README.md)
- Text writer details: [`huenit_text_writer/README.md`](huenit_text_writer/README.md)
- Official HUENIT manual: <https://huenit.gitbook.io/huenit-manual-en>
