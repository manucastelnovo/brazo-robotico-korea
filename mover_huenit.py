import sys
import time

HUENIT_SRC = r"C:\Program Files\Huenit robotics\resources\huenit_py\src"
sys.path.insert(0, HUENIT_SRC)

from python_protocol_cores.robot_blocks.robot import checkConnection, moveG0

print("=== HUENIT - PRUEBA DE MOVIMIENTO ===")

if not checkConnection():
    print("ERROR: HUENIT no responde.")
    sys.exit()

print("HUENIT conectado.")
print("El robot se movera en 3 segundos...")
time.sleep(3)

# Posición de prueba
moveG0(0, 200, 100)

print("Movimiento terminado.")