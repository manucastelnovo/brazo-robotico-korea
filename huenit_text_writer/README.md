# HUENIT Text Writer

Proyecto para escribir textos sencillos con HUENIT desde Python.

## Archivos

- `huenit_text_writer.py`: programa principal.
- `requirements.txt`: dependencia de Python.

## Preparación

```cmd
pip install -r requirements.txt
```

## Probar sin conectar HUENIT

```cmd
python huenit_text_writer.py "TEST" --dry-run
```

Esto muestra los G-code que se enviarían al robot.

## Cuando conectemos HUENIT

Detección automática:

```cmd
python huenit_text_writer.py "HOLA"
```

O indicando el puerto:

```cmd
python huenit_text_writer.py "HOLA" --port COM5
```

## Cambiar tamaño

```cmd
python huenit_text_writer.py "HOLA" --height 8
```

## Cambiar posición

```cmd
python huenit_text_writer.py "HOLA" --x 5 --y 220
```

## Valores iniciales

- Baudrate: 115200
- Velocidad: F1200
- Z arriba: -45
- Z dibujo: -56
- Coordenadas absolutas: G90
- Unidades: milímetros (G21)

No se ejecuta `G28`.

## Caracteres

A-Z, 0-9, espacio, guion y punto.

La fuente es vectorial: cada carácter está formado por trazos rectos G1.
