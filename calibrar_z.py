import sys
import time

HUENIT_SRC = r"C:\Program Files\Huenit robotics\resources\huenit_py\src"
sys.path.insert(0, HUENIT_SRC)

from python_protocol_cores.robot_blocks.robot import checkConnection, moveG0

# Punto XY que ya sabemos que está en nuestra zona de trabajo
X = 15
Y = 230

# Empezamos arriba
Z = -45

if not checkConnection():
    print("ERROR: HUENIT no responde")
    sys.exit()

print("=== CALIBRACION DE ALTURA Z ===")

# Ir al punto inicial
moveG0(X, Y, Z)

print(f"Posicion actual: Z = {Z}")
print()
print("ENTER = bajar 1 mm")
print("q + ENTER = terminar")

while True:

    opcion = input("> ").strip().lower()

    if opcion == "q":
        print(f"Calibracion terminada. Z seleccionado: {Z}")
        break

    Z -= 1

    print(f"Moviendo a Z = {Z}")
    moveG0(X, Y, Z)
    