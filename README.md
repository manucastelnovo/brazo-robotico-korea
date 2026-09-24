# HUENIT Robot Scripts

Python scripts for the **HUENIT robotic arm** and the **HUENIT AI Camera** on Windows:

- ✍️ Write text on paper with a pen.
- 🎮 Control the arm with a gamepad, and record and replay movements.
- 📷 Watch the AI Camera live on the PC, with face detection and face recognition.

No HUENIT LAB install needed: just Python and `pip` (HUENIT LAB is only used for firmware updates).

## Setup

1. Install [Python 3.10 or newer](https://www.python.org/downloads/). Check **"Add python.exe to PATH"**.
2. Open PowerShell in this folder, create a virtual environment and install the dependencies:
   ```powershell
   python -m venv .venv
   $PY = ".\.venv\Scripts\python.exe"
   & $PY -m pip install -r requirements.txt
   ```
3. Check that it works without hardware:
   ```powershell
   & $PY .\huenit_text_writer\huenit_text_writer.py "HELLO" --dry-run
   ```
   You should see a list of `G1 X.. Y.. Z..` commands.
4. Connect the arm (DC power + USB) and/or the camera (USB). The ports are detected automatically.

> `$PY` is the Python inside `.venv`, so nothing is installed in your system Python.
> Define it again in every new PowerShell window.

Full guide (hardware, USB driver, pen calibration, face training, troubleshooting): **[SETUP.md](SETUP.md)**.

## Usage

```powershell
# Write text with the arm (letter height in mm)
& $PY .\huenit_text_writer\huenit_text_writer.py "HELLO WORLD" --height 15

# Watch the AI Camera on the PC
& $PY .\huenit_camera_viewer\huenit_face_viewer.py            # faces detected on the PC
& $PY .\huenit_camera_viewer\huenit_face_viewer.py --ai 1     # recognize who it is (trained model in slot 1)

# Control the arm with a Logitech F310 gamepad
& $PY .\huenit_gamepad_gripper.py
```

## Scripts

| Script | What it does | Needs |
|---|---|---|
| `huenit_text_writer/huenit_text_writer.py` | Writes text with a pen (A-Z, 0-9, `-`, `.`) | arm |
| `huenit_text_writer_interactive/huenit_text_writer.py` | Same, but asks for the text and the settings | arm |
| `huenit_camera_viewer/huenit_face_viewer.py` | Live camera video on the PC + face detection and recognition | camera |
| `huenit_gamepad.py` | Move the arm with a gamepad | arm, gamepad |
| `huenit_gamepad_teach_replay.py` | Gamepad + record and replay movements | arm, gamepad |
| `huenit_gamepad_gripper.py` | Gamepad + teach & replay + suction and gripper | arm, gamepad |
| `huenit_run_routine.py` | Replay saved routines without the gamepad | arm |
| `huenit_jog_control.py` | Move the arm with the keyboard | arm |
| `huenit_teach_replay.py` | Keyboard teach & replay using the arm's encoders | arm |
| `huenit_gripper_test.py` | Test the gripper module states | arm, gripper |
| `test_gamepad.py` | Check that the gamepad is detected | gamepad |
| `calibrar_z.py` | Find the pen height (Z): lowers the pen 1 mm per ENTER | arm, pen |
| `calibrar_z_fino.py` | Fine pen height: 0.2 mm steps, `u` to go up | arm, pen |
| `cuadrado.py` | Draws a 30 x 30 mm square | arm, pen |
| `circulo_cuadrado.py` | Draws a circle with a square inscribed in it | arm, pen |
| `mover_huenit.py`, `secuencia_huenit.py` | Simple movement tests | arm |
| `huenit_arm.py` | Small library (`checkConnection`, `moveG0`) used by the scripts above | - |

## Documentation

- [SETUP.md](SETUP.md): complete setup guide and troubleshooting.
- [huenit_camera_viewer/README.md](huenit_camera_viewer/README.md): camera viewer modes and how it works.
- [huenit_text_writer/README.md](huenit_text_writer/README.md): text writer options.
- [Official HUENIT manual](https://huenit.gitbook.io/huenit-manual-en).
