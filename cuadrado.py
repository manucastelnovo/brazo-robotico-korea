import sys
import time

from huenit_arm import checkConnection, moveG0

# ALTURAS
Z_ARRIBA = -45
Z_DIBUJO = -56

# CUADRADO 30 x 30 mm
A = (0, 215)
B = (30, 215)
C = (30, 245)
D = (0, 245)

print("=== CUADRADO HUENIT ===")

if not checkConnection():
    print("ERROR: HUENIT no responde")
    sys.exit()

print("HUENIT conectado")

# 1. Posicionarse encima del punto inicial
print("Posicionando en A...")
moveG0(A[0], A[1], Z_ARRIBA)
time.sleep(1)

# 2. Bajar el lapiz
print("Bajando lapiz...")
moveG0(A[0], A[1], Z_DIBUJO)
time.sleep(0.5)

# 3. Dibujar los cuatro lados
print("Lado 1: A -> B")
moveG0(B[0], B[1], Z_DIBUJO)

print("Lado 2: B -> C")
moveG0(C[0], C[1], Z_DIBUJO)

print("Lado 3: C -> D")
moveG0(D[0], D[1], Z_DIBUJO)

print("Lado 4: D -> A")
moveG0(A[0], A[1], Z_DIBUJO)

# 4. Levantar el lapiz
print("Levantando lapiz...")
moveG0(A[0], A[1], Z_ARRIBA)

print("=== TERMINADO ===")