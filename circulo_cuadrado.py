import sys
import time
import math

from huenit_arm import checkConnection, moveG0


# ==========================================
# CONFIGURACION
# ==========================================

Z_ARRIBA = -45.0
Z_DIBUJO = -56.0

# Centro del dibujo
CENTRO_X = 15
CENTRO_Y = 230

# Radio del circulo
RADIO = 20

# Cantidad de segmentos del circulo
SEGMENTOS = 40


# ==========================================
# FUNCIONES
# ==========================================

def levantar(x, y):
    moveG0(x, y, Z_ARRIBA)


def bajar(x, y):
    moveG0(x, y, Z_DIBUJO)


def mover_dibujando(x, y):
    moveG0(x, y, Z_DIBUJO)


# ==========================================
# CONEXION
# ==========================================

print("=== CIRCULO + CUADRADO ===")

if not checkConnection():
    print("ERROR: HUENIT no responde")
    sys.exit()

print("HUENIT conectado")


# ==========================================
# DIBUJAR CIRCULO
# ==========================================

print("Dibujando circulo...")

# Punto inicial del circulo
inicio_x = CENTRO_X + RADIO
inicio_y = CENTRO_Y

levantar(inicio_x, inicio_y)
time.sleep(0.5)

bajar(inicio_x, inicio_y)

# Aproximamos el circulo con pequeños segmentos
for i in range(1, SEGMENTOS + 1):

    angulo = 2 * math.pi * i / SEGMENTOS

    x = CENTRO_X + RADIO * math.cos(angulo)
    y = CENTRO_Y + RADIO * math.sin(angulo)

    mover_dibujando(x, y)

levantar(inicio_x, inicio_y)

print("Circulo terminado")


# ==========================================
# CUADRADO INSCRITO
# ==========================================

print("Dibujando cuadrado...")

# Para un cuadrado inscrito:
# distancia del centro al vertice = RADIO

d = RADIO / math.sqrt(2)

A = (CENTRO_X - d, CENTRO_Y - d)
B = (CENTRO_X + d, CENTRO_Y - d)
C = (CENTRO_X + d, CENTRO_Y + d)
D = (CENTRO_X - d, CENTRO_Y + d)


# Ir al primer vertice
levantar(A[0], A[1])
time.sleep(0.5)

bajar(A[0], A[1])

# Dibujar los cuatro lados
mover_dibujando(B[0], B[1])
mover_dibujando(C[0], C[1])
mover_dibujando(D[0], D[1])
mover_dibujando(A[0], A[1])

# Levantar lapiz
levantar(A[0], A[1])


print("============================")
print("DIBUJO TERMINADO")
print("============================")
