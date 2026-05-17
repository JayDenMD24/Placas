"""
detector.py — Detección de placas con YOLOv8
"""

from pathlib import Path
import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError("Instala ultralytics: pip install ultralytics")


class PlateDetector:
    """Detecta y recorta placas vehiculares usando YOLOv8."""

    def __init__(self, model_path: str, confidence: float = 0.6):
        model_path = Path(model_path)

        if not model_path.exists():
            print(f"[Detector] Modelo no encontrado en {model_path}.")
            print("[Detector] Descargando yolov8n como base (sin fine-tuning)...")
            # Se usa como detector genérico hasta tener el modelo entrenado
            self.model = YOLO("yolov8n.pt")
            self.use_generic = True
        else:
            self.model = YOLO(str(model_path))
            self.use_generic = False

        self.confidence = confidence

    def detect(self, frame: np.ndarray, imgsz: int = 320) -> tuple[list, list]:
        """
        Detecta placas en un frame.
        imgsz: tamaño de inferencia (menor = más rápido, 320 recomendado para CPU)
        Retorna:
            boxes: lista de (x1, y1, x2, y2, conf)
            crops: imágenes recortadas de cada placa
        """
        results = self.model(frame, conf=self.confidence, verbose=False, imgsz=imgsz)
        boxes  = []
        crops  = []

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])

                # Si es modelo genérico, filtrar solo clase 'car' y recortar
                # la parte inferior donde suele estar la placa
                if self.use_generic:
                    cls = int(box.cls[0])
                    if cls not in [2, 5, 7]:  # car, bus, truck
                        continue
                    h = y2 - y1
                    y1 = y2 - int(h * 0.25)  # último 25% del vehículo

                # Asegurar coordenadas válidas
                h_frame, w_frame = frame.shape[:2]
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(w_frame, x2); y2 = min(h_frame, y2)

                if x2 > x1 and y2 > y1:
                    boxes.append((x1, y1, x2, y2, conf))
                    crops.append(frame[y1:y2, x1:x2].copy())

        return boxes, crops
