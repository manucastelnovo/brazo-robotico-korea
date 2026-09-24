import sys
import time

HUENIT_SRC = r"C:\Program Files\Huenit robotics\resources\huenit_py\src"
sys.path.insert(0, HUENIT_SRC)

from python_protocol_cores.robot_blocks.robot import checkConnection, moveG0

if not checkConnection():
    print("HUENIT no responde")
    sys.exit()

print("HUENIT conectado")

# Punto A
moveG0(0, 200, 100)
time.sleep(1)

# Punto B
moveG0(30, 200, 100)
time.sleep(1)

# Volver al punto A
moveG0(0, 200, 100)

print("Secuencia terminada")