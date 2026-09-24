import pygame
import time

pygame.init()
pygame.joystick.init()

print("=== TEST LOGITECH F310 ===")

if pygame.joystick.get_count() == 0:
    print("ERROR: No se detecto ningun control.")
    input("ENTER para salir...")
    pygame.quit()
    raise SystemExit

pad = pygame.joystick.Joystick(0)
pad.init()

print("Control detectado:", pad.get_name())
print("Ejes:", pad.get_numaxes())
print("Botones:", pad.get_numbuttons())
print()
print("Mueve los sticks y presiona botones.")
print("CTRL+C para terminar.")
print()

try:
    while True:
        pygame.event.pump()

        axes = [
            round(pad.get_axis(i), 2)
            for i in range(pad.get_numaxes())
        ]

        buttons = [
            i
            for i in range(pad.get_numbuttons())
            if pad.get_button(i)
        ]

        print(
            f"\rAxes: {axes} | Buttons: {buttons}          ",
            end="",
            flush=True
        )

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nTest terminado.")

finally:
    pygame.quit()