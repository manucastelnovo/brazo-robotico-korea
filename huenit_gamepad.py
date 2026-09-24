#!/usr/bin/env python3

import os
import sys
import time
import math
import re
import threading

import pygame
import serial
from serial.tools import list_ports


# ============================================================
# CONFIGURACION HUENIT
# ============================================================

BAUD = 115200

CONTROL_HZ = 80

# Empezamos despacio por seguridad
MAX_SPEED_MM_S = 120.0

# Feedrate enviado mediante G1
FEED_MM_MIN = 1200

# Suavidad de aceleracion / frenado
RAMP_ALPHA = 0.16

# Ignorar movimientos extremadamente pequeños
MIN_STEP_MM = 0.002


# ============================================================
# CONFIGURACION LOGITECH F310
# ============================================================

DEADZONE = 0.15

# Mapeo esperado F310 en XInput
AXIS_X = 0       # Stick izquierdo horizontal
AXIS_Y = 1       # Stick izquierdo vertical
AXIS_Z = 3       # Stick derecho vertical

BUTTON_VAC_ON = 0      # A
BUTTON_VAC_OFF = 1     # B

BUTTON_SLOWER = 4      # LB
BUTTON_FASTER = 5      # RB

BUTTON_QUIT = 6        # BACK


# ============================================================
# COMANDOS HUENIT
# ============================================================

VAC_ON_CMD = "M1400 A1023"
VAC_OFF_CMD = "M1400 A0"


# ============================================================
# DETECTAR HUENIT
# ============================================================

def auto_detect_huenit_port():

    VID = 0x0403
    PID = 0x6015

    ports = list(list_ports.comports())

    if not ports:
        raise RuntimeError("No serial ports found.")

    candidates = []

    for p in ports:

        score = 0

        vid = getattr(p, "vid", None)
        pid = getattr(p, "pid", None)

        product = (getattr(p, "product", "") or "").lower()
        manufacturer = (getattr(p, "manufacturer", "") or "").lower()
        serial_number = (getattr(p, "serial_number", "") or "").upper()

        if "HUECAM" in serial_number:
            continue  # HUENIT AI Camera: same FTDI VID/PID, not the arm

        if vid == VID and pid == PID:
            score += 5

        if "huenit" in product or "huearm" in product:
            score += 3

        if "HUEARM" in serial_number:
            score += 2

        if "ftdi" in manufacturer:
            score += 1

        if score > 0:
            candidates.append((score, p.device))

    if not candidates:
        available = ", ".join(p.device for p in ports)

        raise RuntimeError(
            f"HUENIT not found. Available ports: {available}"
        )

    candidates.sort(key=lambda item: item[0], reverse=True)

    return candidates[0][1]


# ============================================================
# COMUNICACION SERIAL
# ============================================================

class GCodeIO:

    def __init__(self, port, baud):

        self.ser = serial.Serial(
            port,
            baud,
            timeout=0.02
        )

        time.sleep(1)


    def send(self, command):

        line = command.strip() + "\n"

        self.ser.write(
            line.encode("ascii", "ignore")
        )

        self.ser.flush()


    def close(self):

        try:
            self.ser.close()

        except:
            pass


# ============================================================
# DEADZONE DEL STICK
# ============================================================

def apply_deadzone(value):

    if abs(value) < DEADZONE:
        return 0.0

    # Reescala para que despues del deadzone empiece desde 0
    sign = 1 if value > 0 else -1

    value = (
        abs(value) - DEADZONE
    ) / (
        1.0 - DEADZONE
    )

    return sign * value


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("================================")
    print(" HUENIT + LOGITECH F310")
    print("================================")
    print()


    # --------------------------------------------------------
    # GAMEPAD
    # --------------------------------------------------------

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:

        print("ERROR: Logitech controller not detected.")

        return


    pad = pygame.joystick.Joystick(0)
    pad.init()

    print("Gamepad:", pad.get_name())


    # --------------------------------------------------------
    # HUENIT
    # --------------------------------------------------------

    try:

        port = auto_detect_huenit_port()

    except Exception as e:

        print()
        print("HUENIT not connected.")
        print(e)
        print()
        print("The gamepad was detected correctly.")
        print("Connect HUENIT later and run this script again.")

        pygame.quit()

        return


    print("HUENIT:", port)


    try:

        g = GCodeIO(port, BAUD)

    except Exception as e:

        print("Serial error:", e)

        pygame.quit()

        return


    print()
    print("CONTROLS")
    print("--------------------------------")
    print("Left stick       X / Y")
    print("Right stick      Z")
    print("A                Vacuum ON")
    print("B                Vacuum OFF")
    print("LB               Slower")
    print("RB               Faster")
    print("BACK             Exit")
    print("--------------------------------")
    print()


    # Relative positioning
    g.send("G90")
    time.sleep(0.1)

    g.send("G21")
    time.sleep(0.1)

    g.send("G91")
    time.sleep(0.1)


    # --------------------------------------------------------
    # VARIABLES
    # --------------------------------------------------------

    speed = MAX_SPEED_MM_S

    vx = 0.0
    vy = 0.0
    vz = 0.0

    residual_x = 0.0
    residual_y = 0.0
    residual_z = 0.0

    vacuum = False

    running = True

    last_time = time.time()

    previous_buttons = {}


    # --------------------------------------------------------
    # CONTROL LOOP
    # --------------------------------------------------------

    try:

        while running:

            pygame.event.pump()


            # ==================================================
            # READ STICKS
            # ==================================================

            x_input = apply_deadzone(
                pad.get_axis(AXIS_X)
            )

            y_input = apply_deadzone(
                -pad.get_axis(AXIS_Y)
            )

            z_input = apply_deadzone(
                -pad.get_axis(AXIS_Z)
            )


            # ==================================================
            # BUTTON EDGE DETECTION
            # ==================================================

            def pressed(button):

                current = bool(
                    pad.get_button(button)
                )

                previous = previous_buttons.get(
                    button,
                    False
                )

                previous_buttons[button] = current

                return current and not previous


            # Vacuum ON
            if pressed(BUTTON_VAC_ON):

                if not vacuum:

                    g.send(VAC_ON_CMD)

                    vacuum = True

                    print("\nVacuum ON")


            # Vacuum OFF
            if pressed(BUTTON_VAC_OFF):

                if vacuum:

                    g.send(VAC_OFF_CMD)

                    vacuum = False

                    print("\nVacuum OFF")


            # Slower
            if pressed(BUTTON_SLOWER):

                speed = max(
                    2.0,
                    speed * 0.75
                )

                print(
                    f"\nSpeed: {speed:.1f} mm/s"
                )


            # Faster
            if pressed(BUTTON_FASTER):

                speed = speed * 1.25
                print(
                    f"\nSpeed: {speed:.1f} mm/s"
                )


            # Exit
            if pressed(BUTTON_QUIT):

                running = False

                continue


            # ==================================================
            # TIMING
            # ==================================================

            now = time.time()

            dt = now - last_time

            period = 1.0 / CONTROL_HZ


            if dt < period:

                time.sleep(
                    period - dt
                )

                now = time.time()

                dt = now - last_time


            last_time = now


            # ==================================================
            # TARGET VELOCITY
            # ==================================================

            target_x = x_input * speed
            target_y = y_input * speed
            target_z = z_input * speed


            # Smooth acceleration
            vx += (
                target_x - vx
            ) * RAMP_ALPHA

            vy += (
                target_y - vy
            ) * RAMP_ALPHA

            vz += (
                target_z - vz
            ) * RAMP_ALPHA


            # ==================================================
            # DISTANCE FOR THIS FRAME
            # ==================================================

            dx = vx * dt + residual_x
            dy = vy * dt + residual_y
            dz = vz * dt + residual_z


            commands = []


            if abs(dx) >= MIN_STEP_MM:

                commands.append(
                    f"X{dx:.4f}"
                )

                residual_x = 0.0

            else:

                residual_x = dx


            if abs(dy) >= MIN_STEP_MM:

                commands.append(
                    f"Y{dy:.4f}"
                )

                residual_y = 0.0

            else:

                residual_y = dy


            if abs(dz) >= MIN_STEP_MM:

                commands.append(
                    f"Z{dz:.4f}"
                )

                residual_z = 0.0

            else:

                residual_z = dz


            # ==================================================
            # SEND G1
            # ==================================================

            if commands:

                command = (
                    "G1 "
                    + " ".join(commands)
                    + f" F{FEED_MM_MIN}"
                )

                g.send(command)


            # ==================================================
            # HUD
            # ==================================================

            print(
                f"\r"
                f"X:{x_input:+.2f} "
                f"Y:{y_input:+.2f} "
                f"Z:{z_input:+.2f} | "
                f"Speed:{speed:4.1f} mm/s | "
                f"Vac:{'ON ' if vacuum else 'OFF'}",
                end="",
                flush=True
            )


    # ========================================================
    # SHUTDOWN
    # ========================================================

    except KeyboardInterrupt:

        print("\nCTRL+C")


    finally:

        print()
        print("Stopping HUENIT...")


        try:

            # Stop queued movements
            g.send("M400")

            # Return to absolute coordinates
            g.send("G90")

            # Make sure vacuum is OFF
            if vacuum:
                g.send(VAC_OFF_CMD)

        except:
            pass


        g.close()

        pygame.quit()

        print("Disconnected.")
        print()


if __name__ == "__main__":
    main()