# ALPR Colombia

Sistema de reconocimiento automático de placas vehiculares colombianas con consulta a la base de datos SIMIT.

## Requisitos

- Python 3.10+
- Cámara USB

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

Teclas:
- `Q` — Salir
- `↑/↓` — Desplazar lista de placas

## Estructura

```
main.py              — Orquestador principal
detector.py          — Detección de placas con YOLOv8
ocr.py               — Lectura OCR con EasyOCR + corrección posicional
simit_scraper.py     — Consulta automatizada al SIMIT (PoW captcha)
pdf_generator.py     — Generación de reportes PDF
models/
  plate_detector.pt  — Modelo fine-tuneado de YOLOv8
requirements.txt     — Dependencias
```

## Flujo

1. Captura video de cámara USB
2. Detecta placas con YOLOv8
3. Captura lotes de 15 frames con votación mayoritaria
4. Lee el texto con EasyOCR + corrección de caracteres
5. Consulta el SIMIT automáticamente
6. Muestra resultados en ventana OpenCV con clasificación por colores
7. Permite descargar reporte PDF por placa
