import sys
import time

HUENIT_SRC = r"C:\Program Files\Huenit robotics\resources\huenit_py\src"
sys.path.insert(0, HUENIT_SRC)

from python_protocol_cores.robot_blocks.robot import checkConnection, moveG0

# Punto de calibración
X = 15
Y = 230

# Cambia este valor por tu Z aproximado
Z = -60.0

PASO = 0.2

if not checkConnection():
    print("ERROR: HUENIT no responde")
    sys.exit()

print("=== CALIBRACION FINA Z ===")

moveG0(X, Y, Z)

print(f"Z actual = {Z:.1f}")
print()
print("ENTER = bajar 0.2 mm")
print("u + ENTER = subir 0.2 mm")
print("q + ENTER = terminar")

while True:

    opcion = input("> ").strip().lower()

    if opcion == "q":
        print()
        print(f"Z FINAL = {Z:.1f}")
        break

    elif opcion == "u":
        Z += PASO
        print(f"Subiendo -> Z = {Z:.1f}")

    else:
        Z -= PASO
        print(f"Bajando -> Z = {Z:.1f}")

    moveG0(X, Y, Z)