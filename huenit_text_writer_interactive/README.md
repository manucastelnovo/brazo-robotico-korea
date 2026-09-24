# HUENIT Text Writer — versión interactiva

Esta versión permite ejecutar el programa y escribir el texto directamente en la terminal.

## Ejecutar usando el Python incluido con HUENIT

Desde PowerShell, dentro de esta carpeta:

```powershell
& "C:\Program Files\Huenit robotics\resources\huenit_py\huenit_env_win\python.exe" .\huenit_text_writer.py
```

El programa preguntará:

```text
¿Qué quieres escribir?: HOLA
Altura de letra en mm [10.0]:
Posición inicial X [5.0]:
Posición inicial Y [220.0]:
Espacio entre letras en mm [2.0]:

¿Probar sin mover el robot? [S/n]:
¿Continuar? [S/n]:
```

Pulsa ENTER para aceptar cualquier valor entre corchetes.

## Ahora, sin robot conectado

Responde `S` a:

```text
¿Probar sin mover el robot? [S/n]:
```

El programa generará los movimientos sin enviarlos al robot.

## Cuando HUENIT esté conectado

Responde `N` a la pregunta de prueba. El programa intentará detectar HUENIT automáticamente.

## Compatibilidad

También puedes seguir utilizándolo como antes:

```powershell
& "C:\Program Files\Huenit robotics\resources\huenit_py\huenit_env_win\python.exe" .\huenit_text_writer.py "TEST" --dry-run
```

## Caracteres disponibles

- A-Z
- 0-9
- Espacio
- Guion
- Punto

## Valores iniciales

- Z arriba: -45
- Z dibujo: -56
- Velocidad: F1200
- Altura de letra: 10 mm
- X inicial: 5
- Y inicial: 220

Antes de la primera prueba física conviene verificar nuevamente la posición del papel y las alturas Z.
