import sys
import time

from huenit_arm import checkConnection, moveG0

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