import os
import gc
import cv2
import threading
import re
import numpy as np
from detector import PlateDetector
from ocr import PlateReader
from simit_scraper import SIMITScraper

MODEL_PATH   = "models/plate_detector.pt"
CAMERA_INDEX = 1
FRAME_SKIP   = 3
CONFIDENCE   = 0.25
CLEAR_AFTER  = 60
IMGSZ        = 320
STABLE_COUNT = 10
MAX_CONSULTAS = 2
MAX_ENTRIES  = 30
GC_INTERVAL  = 30

PLATE_RE = re.compile(r"[A-Z]{3}\d{3}")

CLASIFICACION = {
    "normal":    {"color": (0, 200, 80),  "label": "NORMAL"},
    "atencion":  {"color": (0, 200, 255), "label": "PRECAUCION"},
    "peligroso": {"color": (0, 0, 255),   "label": "PELIGROSO"},
}

WINDOW_W = 1400
WINDOW_H = 720
CAM_W = 950
LIST_W = WINDOW_W - CAM_W
LIST_X = CAM_W
LIST_Y = 60
ENTRY_H = 88
PDF_BTN_W = 80
PDF_BTN_H = 26


class ALPRSystem:
    def __init__(self):
        print("[ALPR] Cargando modelos...")
        self.detector = PlateDetector(MODEL_PATH, confidence=CONFIDENCE)
        self.reader = PlateReader()
        self.simit = SIMITScraper()

        self.entries = {}
        self._ocr_text = ""
        self._ocr_working = False
        self._ocr_box_results = []
        self._sem = threading.Semaphore(MAX_CONSULTAS)
        self._click = None
        self._pdf_btns = []
        self._frame_count = 0
        self._boxes = []
        self._last_plate = ""

    def _get_plate_number(self, text):
        m = PLATE_RE.search(text.upper())
        return m.group(0) if m else None

    def _ocr_all_crops(self, crops):
        self._ocr_working = True
        results = []
        first_text = ""
        for crop in crops:
            text = self.reader.read(crop)
            plate_num = self._get_plate_number(text or "")
            results.append(plate_num)
            if not first_text and plate_num:
                first_text = plate_num
                print(f"[ALPR] {plate_num}")
        self._ocr_box_results = results
        if first_text:
            self._ocr_text = first_text
        self._ocr_working = False

    def _query_simit(self, plate, entry):
        entry["status"] = "consultando"
        try:
            result = self.simit.consult(plate)
            nivel = self.simit.classify(result)
            entry["result"] = result
            entry["nivel"] = nivel
            entry["status"] = "ok"
            c = result.get("total_comparendos", 0)
            m = result.get("total_multas", 0)
            a = result.get("total_acuerdos", 0)
            print(f"[SIMIT] {plate}: C={c} M={m} A={a} ${result.get('total_pendiente',0):,} — {nivel}")
        except Exception as e:
            entry["status"] = "error"
            print(f"[SIMIT] Error {plate}: {e}")
        finally:
            self._sem.release()

    def _download_pdf(self, plate, entry):
        entry["pdf_status"] = "descargando..."
        try:
            path = self.simit.download_pdf(plate)
            entry["pdf_path"] = path
            entry["pdf_status"] = "PDF listo" if path else "Error"
        except Exception:
            entry["pdf_status"] = "Error"

    def _mouse_cb(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._click = (x, y)

    def run(self):
        cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        cv2.namedWindow("ALPR Colombia")
        cv2.setMouseCallback("ALPR Colombia", self._mouse_cb)

        print("[ALPR] Iniciando camara... Q = salir")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            self._frame_count += 1

            if self._frame_count % FRAME_SKIP == 0:
                boxes, crops = self.detector.detect(frame, imgsz=IMGSZ)
                self._boxes = boxes or []
                if self._boxes and crops and not self._ocr_working:
                    t = threading.Thread(target=self._ocr_all_crops, args=(crops,), daemon=True)
                    t.start()

                plate_num = self._get_plate_number(self._ocr_text or "")
                self._last_plate = plate_num or ""

                if plate_num:
                    if plate_num not in self.entries:
                        self.entries[plate_num] = {
                            "stability": 0,
                            "last_seen": self._frame_count,
                            "status": "detectando",
                            "result": None,
                            "nivel": None,
                            "pdf_path": None,
                            "pdf_status": "",
                        }
                    e = self.entries[plate_num]
                    e["last_seen"] = self._frame_count
                    e["stability"] += 1

                    if e["stability"] >= STABLE_COUNT and e["status"] == "detectando":
                        if self._sem.acquire(blocking=False):
                            e["status"] = "consultando"
                            t = threading.Thread(target=self._query_simit, args=(plate_num, e), daemon=True)
                            t.start()
                        else:
                            e["status"] = "en_cola"

            # Procesar clicks en botones PDF
            if self._click:
                cx, cy = self._click
                self._click = None
                for bx, by, bw, bh, plate in self._pdf_btns:
                    if bx <= cx <= bx + bw and by <= cy <= by + bh:
                        e = self.entries.get(plate)
                        if e and e["status"] == "ok" and not e["pdf_status"]:
                            e["pdf_status"] = "iniciando..."
                            t = threading.Thread(target=self._download_pdf, args=(plate, e), daemon=True)
                            t.start()
                        break

            # Reintentar placas en cola cuando haya slot libre
            for plate, e in self.entries.items():
                if e["status"] == "en_cola" and self._sem.acquire(blocking=False):
                    e["status"] = "consultando"
                    t = threading.Thread(target=self._query_simit, args=(plate, e), daemon=True)
                    t.start()

            # Limpiar placas que nunca se estabilizaron
            stale = []
            for plate, e in self.entries.items():
                if e["stability"] < STABLE_COUNT and (self._frame_count - e["last_seen"]) > CLEAR_AFTER:
                    stale.append(plate)
            for plate in stale:
                del self.entries[plate]

            # Limitar cantidad maxima de entries
            if len(self.entries) > MAX_ENTRIES:
                sorted_entries = sorted(self.entries.items(), key=lambda x: x[1]["last_seen"])
                for plate, _ in sorted_entries[:len(self.entries) - MAX_ENTRIES]:
                    del self.entries[plate]

            # GC periodico
            if self._frame_count % GC_INTERVAL == 0:
                gc.collect()

            # Dibujar overlay en camera
            ocr_box_len = len(self._ocr_box_results)
            for i, (x1, y1, x2, y2, conf) in enumerate(self._boxes):
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 80), 2)
                plate_txt = self._ocr_box_results[i] if i < ocr_box_len and self._ocr_box_results[i] else (self._last_plate or '---')
                label = f"{plate_txt}  {conf:.0%}"
                cv2.rectangle(frame, (x1, y1 - 28), (x1 + len(label) * 11, y1), (0, 200, 80), -1)
                cv2.putText(frame, label, (x1 + 4, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

            # Panel completo (camera + lista)
            panel = np.full((WINDOW_H, WINDOW_W, 3), (15, 15, 15), dtype=np.uint8)
            panel[:, :CAM_W] = cv2.resize(frame, (CAM_W, WINDOW_H))

            self._pdf_btns = []
            y = LIST_Y
            cv2.putText(panel, "PLACAS DETECTADAS", (LIST_X + 20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2)
            y += 40

            for plate, e in sorted(self.entries.items(), key=lambda x: x[1]["last_seen"], reverse=True):
                if y + ENTRY_H > WINDOW_H - 10:
                    break

                by = y
                cv2.rectangle(panel, (LIST_X + 10, by), (LIST_X + LIST_W - 10, by + ENTRY_H), (30, 30, 30), -1)

                color = (100, 100, 100)
                status_text = e["status"]
                if e["status"] == "ok":
                    clr = CLASIFICACION.get(e["nivel"], CLASIFICACION["normal"])
                    color = clr["color"]
                    status_text = clr["label"]

                cv2.putText(panel, plate, (LIST_X + 20, by + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                cv2.putText(panel, status_text, (LIST_X + 180, by + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

                if e["status"] == "ok" and e["result"]:
                    r = e["result"]
                    stats = f"Comparendos:{r.get('total_comparendos',0)} Multas:{r.get('total_multas',0)} Acuerdos:{r.get('total_acuerdos',0)}"
                    cv2.putText(panel, stats, (LIST_X + 20, by + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                    total_val = r.get("total_pendiente", 0)
                    total_str = f"${total_val:,}" if total_val > 0 else "Sin deudas"
                    cv2.putText(panel, total_str, (LIST_X + 20, by + 62), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 255, 255) if total_val > 0 else (0, 200, 80), 1)

                    total_records = r.get("total_comparendos", 0) + r.get("total_multas", 0) + r.get("total_acuerdos", 0)
                    if total_records > 0:
                        bx = LIST_X + LIST_W - PDF_BTN_W - 20
                        self._pdf_btns.append((bx, by + 8, PDF_BTN_W, PDF_BTN_H, plate))
                        cv2.rectangle(panel, (bx, by + 8), (bx + PDF_BTN_W, by + 8 + PDF_BTN_H), (0, 120, 200), -1)
                        cv2.rectangle(panel, (bx, by + 8), (bx + PDF_BTN_W, by + 8 + PDF_BTN_H), (200, 200, 200), 1)

                        pdf_txt = e["pdf_status"] if e["pdf_status"] else "PDF"
                        size = cv2.getTextSize(pdf_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
                        px = bx + (PDF_BTN_W - size[0]) // 2
                        py = by + 8 + (PDF_BTN_H + size[1]) // 2
                        cv2.putText(panel, pdf_txt, (px, py), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

                elif e["status"] == "consultando":
                    cv2.putText(panel, "Consultando SIMIT...", (LIST_X + 20, by + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (200, 200, 0), 1)
                elif e["status"] == "en_cola":
                    cv2.putText(panel, "En espera (3 consultas max)...", (LIST_X + 20, by + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (150, 150, 150), 1)
                elif e["status"] == "error":
                    cv2.putText(panel, "Error en consulta", (LIST_X + 20, by + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 0, 200), 1)
                else:
                    cv2.putText(panel, f"Estabilizando... {e['stability']}/{STABLE_COUNT}", (LIST_X + 20, by + 44),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

                y += ENTRY_H + 6

            cv2.putText(panel, "Q: salir", (LIST_X + 20, WINDOW_H - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1)

            cv2.imshow("ALPR Colombia", panel)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()
        self.simit.close()


if __name__ == "__main__":
    ALPRSystem().run()
