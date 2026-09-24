#!/usr/bin/env python3
"""
HUENIT AI Camera -> PC face viewer

Streams live video from the HUENIT AI Camera over USB and shows it on the PC
with OpenCV, drawing a box around every detected face.

Face detection can run in three places (--ai):
  pc       OpenCV Haar cascade on the PC (default). Detects faces only.
  camera   HUENIT built-in 'face_detect' model on the camera's KPU chip.
  1..5     A Face Recognition model you trained and saved in HUENIT OS
           (AI Models > Face Recognition > Save Model). Reports WHO it is.

How it works:
  1. The camera runs MicroPython (CanMV / K210). We interrupt HUENIT OS with
     Ctrl-C and paste a small script (Ctrl-E ... Ctrl-D). Nothing is written
     to the camera's flash.
  2. The script captures frames (and runs the AI model when requested) and
     writes them to the USB serial port at high speed:
       - JPEG frames (FFD8 ... FFD9) in pc / camera modes.
       - Raw RGB565 frames with every other row ("@IMG w h" + w*h*2 bytes) in
         trained-model modes: the three recognition models use so much memory
         that the camera can no longer compress JPEG.
     In camera AI modes each frame is preceded by a text line
     "@F <id> [x, y, w, h, ...] <percent>" or "@F -" when nothing is found.
  3. The PC splits the stream into frames, drops corrupted ones and shows them.
  4. On exit the PC sends 'q', the camera answers "@BYE", both go back to
     115200 baud and the camera is reset back to HUENIT OS.

Usage (after `pip install -r requirements.txt`, see SETUP.md):
    python huenit_face_viewer.py
    python huenit_face_viewer.py --ai camera
    python huenit_face_viewer.py --ai 1 --names "1=Manu,2=Marcos"
    python huenit_face_viewer.py --port COM6 --no-detect

Keys in the video window:
    Q / ESC   quit
    S         save a snapshot (JPEG) in the current folder
"""

import argparse
import os
import re
import sys
import threading
import time

try:
    import cv2
    import numpy as np
    import serial
    from serial.tools import list_ports
except ImportError as e:
    print(f"Missing dependency: {e}. Install them with: python -m pip install -r requirements.txt")
    sys.exit(1)

REPL_BAUD = 115200
JPEG_BAUD = 1500000
RAW_BAUD = 2000000  # 3,000,000 loses bytes in both directions on this hardware

HUENIT_VID = 0x0403
HUENIT_PID = 0x6015

JPEG_START = b"\xff\xd8"
JPEG_END = b"\xff\xd9"
RAW_HEADER = re.compile(rb"@IMG (\d+) (\d+)\n")

READY_MARKER = b"STREAM_READY"
STOPPED_MARKER = b"STREAM_STOPPED"
AI_FAILED_MARKER = b"AI_FAILED"
BYE_MARKER = b"@BYE"

FACE_LINE = re.compile(rb"@F (\S+) \[([^\]]*)\](?: (\S+))?")

# Script executed on the camera. Markers are built by concatenation so the
# echo of the pasted source never contains them. chr(10) avoids escaping
# issues with a newline literal. Every write is assigned to "_" because paste
# mode behaves like the interactive prompt and would otherwise print the
# number of bytes written into the video stream.
CAMERA_SCRIPT = """import sensor, lcd, time
from machine import UART
NL = chr(10)
lcd.init()
{setup}
print('STREAM' + '_READY')
time.sleep_ms(300)
repl = UART.repl_uart()
repl.init({stream_baud}, 8, None, 1, read_buf_len=4096)
try:
    while True:
{process}
        lcd.display(img)
{send}
        if repl.any() and b'q' in repl.read():
            break
finally:
    _ = repl.write('@' + 'BYE' + NL)
    time.sleep_ms(800)
    repl.init({repl_baud}, 8, None, 1, read_buf_len=4096)
    time.sleep_ms(200)
    print('STREAM' + '_STOPPED')
"""

# Plain video: the PC does the detection (or none).
PLAIN_SETUP = """sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QVGA)
sensor.set_vflip({vflip})
sensor.set_hmirror({hmirror})
sensor.skip_frames(time=1500)"""

PLAIN_PROCESS = """        img = sensor.snapshot()"""

# On-camera AI: 'cam' configures the sensor itself.
AI_SETUP = """import cam
cam.ai_init({model})
if getattr(cam.huecam, '__aimodel', None) is None:
    print('AI' + '_FAILED')
    raise SystemExit"""

AI_PROCESS = """        img = cam.snapshot()
        cam.compute(img)
        o = cam.get_output()
        if o is not None and getattr(o, 'rect', None) is not None:
            cam.draw_rectangle(img, o.rect, color=(255, 64, 64), thickness=2)
            _ = repl.write('@F ' + str(o.idx) + ' ' + str(list(o.rect)) + ' ' + str(getattr(o, 'percent', '-')) + NL)
        else:
            _ = repl.write('@F -' + NL)"""

SEND_JPEG = """        _ = repl.write(img.compress(quality={quality}).to_bytes())"""

# Raw RGB565, every other row: needs no extra camera memory.
SEND_RAW = """        mv = memoryview(img.to_bytes())
        row = img.width() * 2
        _ = repl.write('@IMG ' + str(img.width()) + ' ' + str(img.height() // 2) + NL)
        for y in range(0, img.height(), 2):
            _ = repl.write(mv[y * row:(y + 1) * row])"""


def open_port(port, baud=REPL_BAUD, timeout=0.2):
    """Open the port without toggling DTR/RTS (toggling them resets the camera)."""
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.dtr = False
    ser.rts = False
    ser.open()
    if hasattr(ser, "set_buffer_size"):  # Windows only: avoid USB receive overruns
        ser.set_buffer_size(rx_size=1 << 20, tx_size=4096)
    return ser


def read_for(ser, seconds, until=()):
    """Read for up to `seconds`, stopping early when any marker in `until` shows up."""
    if isinstance(until, bytes):
        until = (until,)
    data = b""
    end = time.time() + seconds
    while time.time() < end:
        data += ser.read(4096)
        if any(marker in data for marker in until):
            break
    return data


def hardware_reset(ser, boot_wait=8.0):
    """Pulse RTS to reboot the camera into HUENIT OS."""
    ser.rts = True
    time.sleep(0.2)
    ser.rts = False
    read_for(ser, boot_wait)


def enter_repl(ser):
    """Interrupt whatever runs on the camera and return True if we get '>>>'."""
    ser.reset_input_buffer()
    for _ in range(2):
        ser.write(b"\r\x03\r\n")
        time.sleep(0.15)
    return b">>>" in read_for(ser, 1.0, until=b">>>")


def is_camera_port(port):
    """The camera answers Ctrl-C with a MicroPython prompt; the arm does not."""
    try:
        ser = open_port(port)
    except serial.SerialException:
        return False
    try:
        return enter_repl(ser)
    finally:
        ser.close()


def detect_camera_port():
    env_port = os.environ.get("HUENIT_CAM_PORT")
    if env_port:
        return env_port
    for p in list_ports.comports():
        if p.vid == HUENIT_VID and p.pid == HUENIT_PID:
            print(f"Probing {p.device}...")
            if is_camera_port(p.device):
                return p.device
    return None


def parse_face_line(meta):
    """Return the last face reported in `meta` as a dict, or None."""
    for line in reversed(meta.split(b"\n")):
        if line.startswith(b"@F -"):
            return None
        match = FACE_LINE.search(line)
        if match:
            try:
                rect = [float(v) for v in match.group(2).split(b",")]
                percent = match.group(3)
                return {
                    "idx": match.group(1).decode(),
                    "rect": [int(v) for v in rect[:4]],
                    "score": rect[5] if len(rect) > 5 else None,
                    "percent": float(percent) if percent and percent not in (b"-", b"None") else None,
                }
            except ValueError:
                return None
    return None


def decode_rgb565(payload, width, height):
    """Big-endian RGB565 bytes (K210 byte order) -> BGR image."""
    px = np.frombuffer(payload, dtype=">u2").reshape(height, width).astype(np.uint16)
    r = ((px >> 11) & 0x1F).astype(np.uint8) << 3
    g = ((px >> 5) & 0x3F).astype(np.uint8) << 2
    b = (px & 0x1F).astype(np.uint8) << 3
    return np.dstack([b, g, r])


class CameraStream:
    def __init__(self, port, quality=60, vflip=True, hmirror=True, ai_model=None):
        self.port = port
        self.quality = quality
        self.vflip = vflip
        self.hmirror = hmirror
        self.ai_model = ai_model  # None, 'face_detect' or a slot number
        self.raw = isinstance(ai_model, int)
        self.stream_baud = RAW_BAUD if self.raw else JPEG_BAUD
        self.ser = None
        self.latest = None
        self.latest_face = None
        self.frame_count = 0
        self.dropped = 0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None

    def _build_script(self):
        if self.ai_model is None:
            setup = PLAIN_SETUP.format(vflip=int(self.vflip), hmirror=int(self.hmirror))
            process = PLAIN_PROCESS
        else:
            setup = AI_SETUP.format(model=repr(self.ai_model))
            process = AI_PROCESS
        send = SEND_RAW if self.raw else SEND_JPEG.format(quality=self.quality)
        return CAMERA_SCRIPT.format(
            setup=setup,
            process=process,
            send=send,
            stream_baud=self.stream_baud,
            repl_baud=REPL_BAUD,
        )

    def start(self):
        self.ser = open_port(self.port)
        if not enter_repl(self.ser):
            print("Camera did not answer, resetting it...")
            hardware_reset(self.ser)
            if not enter_repl(self.ser):
                raise RuntimeError("Could not reach the camera MicroPython prompt.")

        self.ser.write(b"\x05")  # Ctrl-E: paste mode
        time.sleep(0.05)
        self.ser.write(self._build_script().encode("utf-8"))
        time.sleep(0.05)
        self.ser.write(b"\x04")  # Ctrl-D: run

        output = read_for(self.ser, 25.0, until=(READY_MARKER, AI_FAILED_MARKER))
        if AI_FAILED_MARKER in output:
            if isinstance(self.ai_model, int):
                raise RuntimeError(
                    f"AI model slot {self.ai_model} is empty. Train a Face Recognition model in "
                    "HUENIT OS (AI Models > Face Recognition) and save it to that slot."
                )
            raise RuntimeError(f"Could not load AI model {self.ai_model!r} on the camera.")
        if READY_MARKER not in output:
            tail = output[-400:].decode("utf-8", "replace")
            raise RuntimeError(f"Camera script did not start:\n{tail}")

        time.sleep(0.15)
        self.ser.baudrate = self.stream_baud
        self.ser.reset_input_buffer()

        self.thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.thread.start()

    def _publish(self, frame, face):
        with self.lock:
            self.latest = frame
            self.latest_face = face
            self.frame_count += 1

    def _next_jpeg(self, buffer):
        """Extract one JPEG frame. Returns (remaining_buffer, found)."""
        start = buffer.find(JPEG_START)
        if start < 0:
            return buffer[-256:], False  # may hold a metadata line or half a marker
        end = buffer.find(JPEG_END, start + 2)
        if end < 0:
            return (buffer[start - 256:] if start > 256 else buffer), False
        face = parse_face_line(buffer[:start]) if self.ai_model is not None else None
        frame = cv2.imdecode(np.frombuffer(buffer[start:end + 2], np.uint8), cv2.IMREAD_COLOR)
        if frame is not None:
            self._publish(frame, face)
        else:
            self.dropped += 1
        return buffer[end + 2:], True

    def _next_raw(self, buffer):
        """Extract one raw frame. Returns (remaining_buffer, found)."""
        match = RAW_HEADER.search(buffer)
        if not match:
            return buffer[-512:], False
        width, height = int(match.group(1)), int(match.group(2))
        start = match.end()
        if not (0 < width <= 640 and 0 < height <= 480):  # header-like bytes inside pixels
            return buffer[start:], True
        end = start + width * height * 2
        if len(buffer) < end + 2:
            return buffer, False
        # A complete frame is followed by the next "@F" line (or "@BYE").
        # Anything else means bytes were lost: drop it and resync.
        if buffer[end:end + 2] != b"@F" and buffer[end:end + 2] != b"@B":
            self.dropped += 1
            return buffer[start:], True
        face = parse_face_line(buffer[:match.start()])
        frame = decode_rgb565(buffer[start:end], width, height)
        frame = cv2.resize(frame, (width, height * 2), interpolation=cv2.INTER_LINEAR)
        self._publish(frame, face)
        return buffer[end:], True

    def _rx_loop(self):
        buffer = b""
        extract = self._next_raw if self.raw else self._next_jpeg
        while not self.stop_event.is_set():
            try:
                buffer += self.ser.read(16384)
            except serial.SerialException:
                break
            found = True
            while found:
                buffer, found = extract(buffer)

    def get_frame(self):
        with self.lock:
            return self.latest, self.latest_face, self.frame_count

    def stop(self, reset_to_os=True):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)
        if not self.ser:
            return
        try:
            stopped = True  # script never started streaming: still at 115200
            if self.thread:
                # Ask to stop until the camera confirms, then follow it to 115200.
                bye = b""
                end = time.time() + 5.0
                while BYE_MARKER not in bye and time.time() < end:
                    self.ser.write(b"q")
                    bye = bye[-16:] + read_for(self.ser, 0.3, until=BYE_MARKER)
                self.ser.baudrate = REPL_BAUD
                self.ser.reset_input_buffer()
                stopped = STOPPED_MARKER in read_for(self.ser, 3.0, until=STOPPED_MARKER)
            if reset_to_os:
                if stopped:
                    self.ser.write(b"import machine\r\nmachine.reset()\r\n")
                    time.sleep(0.3)
                else:
                    hardware_reset(self.ser, boot_wait=0)
        except serial.SerialException:
            pass
        finally:
            self.ser.close()


def load_face_detector():
    path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    detector = cv2.CascadeClassifier(path)
    if detector.empty():
        raise RuntimeError(f"Could not load face cascade: {path}")
    return detector


def draw_pc_faces(frame, detector):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 165, 255), 2)
    return len(faces)


def face_label(face, names, recognition):
    """Text to show above a face reported by the camera."""
    if not recognition:
        return f"face {face['score']:.0%}" if face["score"] is not None else "face"
    label = names.get(face["idx"], f"ID {face['idx']}")
    if face["percent"] is not None:
        label += f" {face['percent']:.0f}%"  # the camera reports 0-100
    return label


def parse_names(text):
    """'1=Manu,2=Marcos' -> {'1': 'Manu', '2': 'Marcos'}"""
    names = {}
    for item in (text or "").split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            names[key.strip()] = value.strip()
    return names


def parse_ai(value):
    if value in ("pc", "camera"):
        return value
    if value.isdigit() and 1 <= int(value) <= 5:
        return int(value)
    raise argparse.ArgumentTypeError("use pc, camera or a model slot from 1 to 5")


def main():
    parser = argparse.ArgumentParser(description="Show the HUENIT AI Camera on the PC with face detection.")
    parser.add_argument("--port", help="Camera serial port, e.g. COM6 (auto-detected if omitted)")
    parser.add_argument("--ai", type=parse_ai, default="pc",
                        help="Where faces are detected: pc (default), camera, or a trained model slot 1-5")
    parser.add_argument("--names", help='Names for trained IDs, e.g. "1=Manu,2=Marcos"')
    parser.add_argument("--quality", type=int, default=60, help="JPEG quality on the camera (10-95)")
    parser.add_argument("--scale", type=float, default=2.0, help="Window zoom factor")
    parser.add_argument("--no-detect", action="store_true", help="Only show video, no face detection")
    parser.add_argument("--no-flip", action="store_true", help="Disable vertical flip and mirror (pc mode)")
    parser.add_argument("--no-reset", action="store_true", help="Leave the camera in the REPL on exit")
    args = parser.parse_args()

    port = args.port or detect_camera_port()
    if not port:
        print("HUENIT AI Camera not found. Connect it by USB or use --port COM6.")
        sys.exit(2)

    mode = "none" if args.no_detect else args.ai
    ai_model = {"none": None, "pc": None, "camera": "face_detect"}.get(mode, mode)
    recognition = isinstance(mode, int)
    detector = load_face_detector() if mode == "pc" else None
    names = parse_names(args.names)

    stream = CameraStream(
        port,
        quality=max(10, min(95, args.quality)),
        vflip=not args.no_flip,
        hmirror=not args.no_flip,
        ai_model=ai_model,
    )

    mode_text = {"none": "video only", "pc": "faces detected on the PC",
                 "camera": "faces detected on the camera"}.get(mode, f"face recognition, model slot {mode}")
    print(f"Starting camera stream on {port} ({mode_text})...")
    if recognition:
        print("Recognition mode sends uncompressed video: expect about 2 fps.")
    window = "HUENIT AI Camera"
    frame = None
    try:
        stream.start()
        print("Streaming. Press Q or ESC in the video window to quit, S to save a snapshot.")
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)

        last_count, fps, fps_time = 0, 0.0, time.time()
        while True:
            frame, face, count = stream.get_frame()
            if frame is not None:
                frame = frame.copy()
                faces = draw_pc_faces(frame, detector) if detector else int(face is not None)

                now = time.time()
                if now - fps_time >= 1.0:
                    fps = (count - last_count) / (now - fps_time)
                    last_count, fps_time = count, now

                if args.scale != 1.0:
                    frame = cv2.resize(frame, None, fx=args.scale, fy=args.scale,
                                       interpolation=cv2.INTER_LINEAR)
                if face is not None:
                    x, y = int(face["rect"][0] * args.scale), int(face["rect"][1] * args.scale)
                    cv2.putText(frame, face_label(face, names, recognition), (x, max(20, y - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (64, 64, 255), 2)

                label = f"{fps:4.1f} fps"
                if mode != "none":
                    label += f" | faces: {faces}"
                cv2.putText(frame, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow(window, frame)

            key = cv2.waitKey(15) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("s") and frame is not None:
                name = time.strftime("huenit_snapshot_%Y%m%d_%H%M%S.jpg")
                cv2.imwrite(name, frame)
                print(f"Saved {name}")
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                break

    except KeyboardInterrupt:
        print("\nInterrupted.")
    except (RuntimeError, serial.SerialException) as e:
        print(f"ERROR: {e}")
    finally:
        print("Stopping camera...")
        stream.stop(reset_to_os=not args.no_reset)
        cv2.destroyAllWindows()
        if stream.dropped:
            print(f"({stream.dropped} corrupted frames were skipped)")


if __name__ == "__main__":
    main()
