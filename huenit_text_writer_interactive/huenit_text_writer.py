"""
HUENIT Text Writer
Escribe texto sencillo con HUENIT usando una fuente vectorial de trazos.

Uso:
    python huenit_text_writer.py "HOLA"
    python huenit_text_writer.py "TEST 123" --port COM5
    python huenit_text_writer.py "HOLA" --dry-run

Dependencia:
    pip install pyserial
"""

import argparse
import os
import re
import sys
import time
import threading
from queue import Queue, Empty

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Falta pyserial. Instala con: pip install pyserial")
    sys.exit(1)

BAUD = 115200
FEED_MM_MIN = 1200

# Calibración confirmada anteriormente
Z_ARRIBA = -45.0
Z_DIBUJO = -56.0

# Punto de inicio y tamaño por defecto
X_INICIO = 5.0
Y_INICIO = 220.0
ALTURA_LETRA = 10.0
ESPACIO_LETRAS = 2.0
ESPACIO_PALABRAS = 5.0

HUENIT_VID = 0x0403
HUENIT_PID = 0x6015

# Fuente vectorial normalizada.
# Cada carácter contiene uno o más trazos.
# Coordenadas: x=0..1, y=0..1
FONT = {
    "A": [[(0,0),(0.5,1),(1,0)],[(0.2,0.4),(0.8,0.4)]],
    "B": [[(0,0),(0,1),(0.65,1),(1,0.8),(0.65,0.55),(0,0.55)],
          [(0.65,0.55),(1,0.3),(0.65,0),(0,0)]],
    "C": [[(1,0.9),(0.75,1),(0.2,1),(0,0.8),(0,0.2),(0.2,0),(0.75,0),(1,0.1)]],
    "D": [[(0,0),(0,1),(0.6,1),(1,0.75),(1,0.25),(0.6,0),(0,0)]],
    "E": [[(1,1),(0,1),(0,0),(1,0)],[(0,0.5),(0.75,0.5)]],
    "F": [[(0,0),(0,1),(1,1)],[(0,0.5),(0.75,0.5)]],
    "G": [[(1,0.85),(0.75,1),(0.2,1),(0,0.8),(0,0.2),(0.2,0),(0.8,0),(1,0.2),(1,0.5),(0.55,0.5)]],
    "H": [[(0,0),(0,1)],[(1,0),(1,1)],[(0,0.5),(1,0.5)]],
    "I": [[(0,1),(1,1)],[(0.5,1),(0.5,0)],[(0,0),(1,0)]],
    "J": [[(0,1),(1,1),(1,0.2),(0.8,0),(0.25,0),(0,0.2)]],
    "K": [[(0,0),(0,1)],[(1,1),(0,0.45),(1,0)]],
    "L": [[(0,1),(0,0),(1,0)]],
    "M": [[(0,0),(0,1),(0.5,0.45),(1,1),(1,0)]],
    "N": [[(0,0),(0,1),(1,0),(1,1)]],
    "O": [[(0.2,0),(0,0.2),(0,0.8),(0.2,1),(0.8,1),(1,0.8),(1,0.2),(0.8,0),(0.2,0)]],
    "P": [[(0,0),(0,1),(0.7,1),(1,0.8),(1,0.6),(0.7,0.45),(0,0.45)]],
    "Q": [[(0.2,0),(0,0.2),(0,0.8),(0.2,1),(0.8,1),(1,0.8),(1,0.2),(0.8,0),(0.2,0)],[(0.6,0.3),(1,0)]],
    "R": [[(0,0),(0,1),(0.7,1),(1,0.8),(1,0.6),(0.7,0.45),(0,0.45)],[(0.55,0.45),(1,0)]],
    "S": [[(1,0.85),(0.75,1),(0.2,1),(0,0.8),(0.2,0.55),(0.8,0.45),(1,0.2),(0.8,0),(0.2,0),(0,0.15)]],
    "T": [[(0,1),(1,1)],[(0.5,1),(0.5,0)]],
    "U": [[(0,1),(0,0.2),(0.2,0),(0.8,0),(1,0.2),(1,1)]],
    "V": [[(0,1),(0.5,0),(1,1)]],
    "W": [[(0,1),(0.2,0),(0.5,0.55),(0.8,0),(1,1)]],
    "X": [[(0,1),(1,0)],[(1,1),(0,0)]],
    "Y": [[(0,1),(0.5,0.5),(1,1)],[(0.5,0.5),(0.5,0)]],
    "Z": [[(0,1),(1,1),(0,0),(1,0)]],
    "0": [[(0.2,0),(0,0.2),(0,0.8),(0.2,1),(0.8,1),(1,0.8),(1,0.2),(0.8,0),(0.2,0)],[(0.2,0.2),(0.8,0.8)]],
    "1": [[(0.25,0.75),(0.5,1),(0.5,0)],[(0.2,0),(0.8,0)]],
    "2": [[(0,0.75),(0.2,1),(0.8,1),(1,0.8),(1,0.6),(0,0),(1,0)]],
    "3": [[(0,0.9),(0.2,1),(0.8,1),(1,0.8),(0.7,0.5),(1,0.25),(0.8,0),(0.2,0),(0,0.1)]],
    "4": [[(0.8,0),(0.8,1),(0,0.35),(1,0.35)]],
    "5": [[(1,1),(0,1),(0,0.55),(0.75,0.55),(1,0.35),(1,0.2),(0.8,0),(0.2,0),(0,0.15)]],
    "6": [[(0.9,0.85),(0.7,1),(0.25,1),(0,0.7),(0,0.2),(0.2,0),(0.75,0),(1,0.2),(1,0.45),(0.75,0.6),(0,0.55)]],
    "7": [[(0,1),(1,1),(0.35,0)]],
    "8": [[(0.2,0.5),(0,0.7),(0.2,1),(0.8,1),(1,0.7),(0.8,0.5),(0.2,0.5),(0,0.25),(0.2,0),(0.8,0),(1,0.25),(0.8,0.5)]],
    "9": [[(1,0.45),(0.25,0.45),(0,0.6),(0,0.8),(0.25,1),(0.8,1),(1,0.8),(1,0.2),(0.75,0),(0.2,0),(0.05,0.15)]],
    "-": [[(0.15,0.5),(0.85,0.5)]],
    ".": [[(0.45,0),(0.55,0)]],
}

class GCodeIO:
    def __init__(self, port, baud=BAUD):
        self.ser = serial.Serial(port, baud, timeout=0.02)
        self.rx = Queue()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.thread.start()

    def _rx_loop(self):
        while not self.stop_event.is_set():
            try:
                raw = self.ser.readline()
                if raw:
                    self.rx.put(raw.decode("utf-8", "ignore").strip())
            except Exception:
                break

    def send(self, line, wait_ok=True, timeout=5.0):
        line = line.strip()
        print(">>", line)
        self.ser.write((line + "\n").encode("ascii", "ignore"))
        self.ser.flush()
        if not wait_ok:
            return
        end = time.time() + timeout
        while time.time() < end:
            try:
                response = self.rx.get(timeout=0.05)
                print("<<", response)
                if re.search(r"\bok\b", response, re.I):
                    return
            except Empty:
                pass
        raise TimeoutError(f"HUENIT no respondió 'ok' a: {line}")

    def close(self):
        self.stop_event.set()
        try:
            self.ser.close()
        except Exception:
            pass

def detect_port():
    env_port = os.environ.get("HUENIT_PORT")
    if env_port:
        return env_port

    # La cámara AI de HUENIT usa el mismo chip FTDI (mismo VID/PID).
    # El número de serie los distingue: "..._HUEARMA" (brazo) y "..._HUECAMA" (cámara).
    ports = [p for p in list_ports.comports()
             if "HUECAM" not in (p.serial_number or "").upper()]

    for p in ports:
        if "HUEARM" in (p.serial_number or "").upper():
            return p.device

    for p in ports:
        if p.vid == HUENIT_VID and p.pid == HUENIT_PID:
            return p.device

    for p in ports:
        text = f"{p.description} {p.product or ''} {p.serial_number or ''}".lower()
        if "huenit" in text or "huearm" in text:
            return p.device

    return None

class TextWriter:
    def __init__(self, io=None, dry_run=False, feed=FEED_MM_MIN):
        self.io = io
        self.dry_run = dry_run
        self.feed = feed

    def send(self, command):
        if self.dry_run:
            print("DRY >>", command)
        else:
            self.io.send(command)

    def move(self, x=None, y=None, z=None, feed=None):
        parts = ["G1"]
        if x is not None:
            parts.append(f"X{x:.2f}")
        if y is not None:
            parts.append(f"Y{y:.2f}")
        if z is not None:
            parts.append(f"Z{z:.2f}")
        parts.append(f"F{feed or self.feed}")
        self.send(" ".join(parts))

    def pen_up(self):
        self.move(z=Z_ARRIBA)

    def pen_down(self):
        self.move(z=Z_DIBUJO)

    def draw_text(self, text, x0=X_INICIO, y0=Y_INICIO,
                  height=ALTURA_LETRA, spacing=ESPACIO_LETRAS):
        text = text.upper()
        width = height * 0.65
        cursor_x = x0

        self.send("G90")
        self.send("G21")
        self.pen_up()

        for ch in text:
            if ch == " ":
                cursor_x += width + ESPACIO_PALABRAS
                continue

            strokes = FONT.get(ch)
            if strokes is None:
                print(f"[AVISO] Carácter no soportado: {ch!r}")
                cursor_x += width + spacing
                continue

            for stroke in strokes:
                if len(stroke) < 2:
                    continue

                sx = cursor_x + stroke[0][0] * width
                sy = y0 + stroke[0][1] * height

                self.pen_up()
                self.move(x=sx, y=sy)
                self.pen_down()

                for px, py in stroke[1:]:
                    x = cursor_x + px * width
                    y = y0 + py * height
                    self.move(x=x, y=y)

                self.pen_up()

            cursor_x += width + spacing

        self.pen_up()
        self.send("M400")
        print("Texto terminado.")

def ask_float(prompt, default):
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return float(default)
        try:
            return float(value.replace(",", "."))
        except ValueError:
            print("Introduce un número válido.")

def ask_yes_no(prompt, default=True):
    suffix = "[S/n]" if default else "[s/N]"
    while True:
        value = input(f"{prompt} {suffix}: ").strip().lower()
        if not value:
            return default
        if value in ("s", "si", "sí", "y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("Responde S o N.")

def interactive_mode():
    print("=" * 52)
    print("              HUENIT TEXT WRITER")
    print("=" * 52)
    print("Escribe textos sencillos con HUENIT.")
    print()

    while True:
        text = input("¿Qué quieres escribir?: ").strip()
        if text:
            break
        print("El texto no puede estar vacío.")

    height = ask_float("Altura de letra en mm", ALTURA_LETRA)
    x = ask_float("Posición inicial X", X_INICIO)
    y = ask_float("Posición inicial Y", Y_INICIO)
    spacing = ask_float("Espacio entre letras en mm", ESPACIO_LETRAS)

    print()
    print("Texto :", text.upper())
    print(f"Altura: {height:g} mm")
    print(f"Inicio: X{x:g} Y{y:g}")
    print()

    dry_run = ask_yes_no("¿Probar sin mover el robot?", True)

    if not ask_yes_no("¿Continuar?", True):
        print("Cancelado.")
        return

    io = None
    try:
        if not dry_run:
            port = detect_port()
            if not port:
                print()
                print("No se encontró HUENIT conectado.")
                print("Conecta el robot o ejecuta nuevamente en modo de prueba.")
                return
            print(f"\nConectando a HUENIT en {port} @ {BAUD} baud...")
            io = GCodeIO(port)
            time.sleep(1.0)

        print("\nIniciando...\n")
        writer = TextWriter(io=io, dry_run=dry_run, feed=FEED_MM_MIN)
        writer.draw_text(text, x, y, height, spacing)

    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        if io:
            try:
                io.send("M400", timeout=10)
            except Exception:
                pass
            io.close()

def command_line_mode():
    parser = argparse.ArgumentParser(description="Escribe texto con HUENIT.")
    parser.add_argument("text", help="Texto a escribir")
    parser.add_argument("--port", help="Puerto serial, por ejemplo COM5")
    parser.add_argument("--x", type=float, default=X_INICIO)
    parser.add_argument("--y", type=float, default=Y_INICIO)
    parser.add_argument("--height", type=float, default=ALTURA_LETRA)
    parser.add_argument("--spacing", type=float, default=ESPACIO_LETRAS)
    parser.add_argument("--feed", type=int, default=FEED_MM_MIN)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    io = None
    try:
        if not args.dry_run:
            port = args.port or detect_port()
            if not port:
                print("No se encontró HUENIT. Usa --port COM5 o --dry-run.")
                return
            print(f"Conectando a HUENIT en {port} @ {BAUD} baud...")
            io = GCodeIO(port)
            time.sleep(1.0)

        writer = TextWriter(io=io, dry_run=args.dry_run, feed=args.feed)
        writer.draw_text(args.text, args.x, args.y, args.height, args.spacing)
    finally:
        if io:
            try:
                io.send("M400", timeout=10)
            except Exception:
                pass
            io.close()

def main():
    # Sin argumentos = interfaz interactiva.
    # Con argumentos = conserva compatibilidad con el proyecto anterior.
    if len(sys.argv) == 1:
        interactive_mode()
    else:
        command_line_mode()

if __name__ == "__main__":
    main()
