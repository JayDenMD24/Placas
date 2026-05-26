import os
import gc
import time
import cv2
import threading
import re
import numpy as np
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from detector import PlateDetector
from ocr import PlateReader
from simit_scraper import SIMITScraper

MODEL_PATH    = "models/plate_detector.pt"
CAMERA_INDEX  = 2
FRAME_SKIP    = 1
CONFIDENCE    = 0.70
IMGSZ         = 256
MAX_CONSULTAS = 2
GC_INTERVAL   = 60
BATCH_SIZE      = 15
BATCH_TIMEOUT   = 3.0
BATCH_COOLDOWN  = 5.0

SAVE_DIR = "captures"

PLATE_RE = re.compile(r"[A-Z]{3}\d{3}|[A-Z]{2}\d{4}|[A-Z]{3}\d{2}[A-Z]|CD\d{4}|\d{3}[A-Z]{3}")

TEXTOS_PLACA = {
    "BOGOTA", "MEDELLIN", "CALI", "BARRANQUILLA", "CARTAGENA",
    "BUCARAMANGA", "PEREIRA", "MANIZALES", "CUCUTA", "IBAGUE",
    "PASTO", "NEIVA", "VALLEDUPAR", "ARMENIA",
    "POPAYAN", "SINCELEJO", "MONTERIA", "QUIBDO", "TUNJA",
    "RIOHACHA", "FLORENCIA", "MOCOA", "LETICIA", "INIRIDA",
    "SANJOSE", "GUAVIARE", "MITU", "YOPAL", "VILLAVICENCIO",
    "COLOMBIA", "SANTAFE",
    "ANTIOQUIA", "CUNDINAMARCA", "SANTANDER", "BOYACA", "TOLIMA",
    "MAGDALENA", "NARINO", "CAUCA", "CESAR", "RISARALDA",
    "CALDAS", "SUCRE", "QUINDIO", "CHOCO", "ATLANTICO",
    "VALLE", "META", "HUILA", "CORDOBA", "LAGUAJIRA",
}

CLASIFICACION = {
    "normal":    {"color": (0, 200, 80),  "label": "SIN REGISTROS"},
    "atencion":  {"color": (0, 200, 255), "label": "CON REGISTROS"},
    "peligroso": {"color": (0, 0, 255),   "label": "REG. MULTIPLES"},
}

WINDOW_W = 1000
WINDOW_H = 600
CAM_W = 680
STATUS_H = 32
CAM_H = WINDOW_H - STATUS_H
LIST_W = WINDOW_W - CAM_W
LIST_X = CAM_W
LIST_Y = 50
ENTRY_H = 86
ENTRY_GAP = 5
PDF_BTN_W = 64
PDF_BTN_H = 22
SCROLL_W = 8


class ALPRSystem:
    def __init__(self):
        print("[ALPR] Cargando modelos...")
        self.detector = PlateDetector(MODEL_PATH, confidence=CONFIDENCE)
        self.reader = PlateReader()
        self.simit = SIMITScraper()

        self.entries = {}
        self._click = None
        self._pdf_btns = []
        self._frame_count = 0
        self._boxes = []
        self._batch = None
        self._batch_cooldown = 0.0
        self._scroll_offset = 0
        self._scrollbar_rect = None
        self._visible_count = 1

        self._simit_executor = ThreadPoolExecutor(max_workers=MAX_CONSULTAS, thread_name_prefix="simit")
        self._ocr_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")

        os.makedirs(SAVE_DIR, exist_ok=True)

    def _get_plate_number(self, text):
        if not text:
            return None
        upper = text.upper()
        m = PLATE_RE.search(upper)
        if not m:
            return None
        plate = m.group(0)
        digit_to_letter = str.maketrans("0123456789", "OIZASGTBCO")
        normalized = plate.translate(digit_to_letter)
        if normalized in TEXTOS_PLACA:
            print(f"[ALPR] Ignorando '{plate}' (parece texto de placa: {normalized})")
            return None
        return plate

    def _similar_plate(self, a, b):
        if a == b:
            return True
        if len(a) != len(b):
            return False
        return sum(1 for ca, cb in zip(a, b) if ca != cb) <= 1

    def _submit_batch(self):
        if self._batch is None or not self._batch["crops"]:
            return
        batch = self._batch
        self._batch = None
        self._batch_cooldown = time.time() + BATCH_COOLDOWN
        ts = int(time.time() * 1000)
        folder = os.path.join(SAVE_DIR, f"batch_{ts}")
        os.makedirs(folder, exist_ok=True)
        paths = []
        for i, crop in enumerate(batch["crops"]):
            path = os.path.join(folder, f"crop_{i:02d}.jpg")
            cv2.imwrite(path, crop)
            paths.append(path)
        print(f"[ALPR] Lote de {len(paths)} capturas en {folder}")
        self._ocr_executor.submit(self._process_batch, paths, folder)

    def _process_batch(self, paths, folder):
        votes = Counter()
        for path in paths:
            crop = cv2.imread(path)
            if crop is None:
                continue
            text = self.reader.read(crop)
            plate = self._get_plate_number(text or "")
            if plate:
                votes[plate] += 1

        if not votes:
            print(f"[ALPR] Votacion: sin placas validas en el lote")
        else:
            winner = votes.most_common(1)[0][0]
            total = sum(votes.values())
            print(f"[ALPR] Votacion: {dict(votes)} -> ganador: {winner} ({votes[winner]}/{total})")

            if winner not in self.entries:
                skip = False
                for existing in list(self.entries.keys()):
                    if self._similar_plate(winner, existing):
                        print(f"[ALPR] Ignorando {winner}: similar a {existing} (posible error OCR)")
                        skip = True
                        break
                if not skip:
                    print(f"[ALPR] Consultando SIMIT para {winner}")
                    self.entries[winner] = {
                        "last_seen": self._frame_count,
                        "status": "consultando",
                        "result": None,
                        "nivel": None,
                        "pdf_path": None,
                        "pdf_status": "",
                    }
                    self._simit_executor.submit(self._query_simit, winner, self.entries[winner])

        for f in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass

    def _query_simit(self, plate, entry):
        try:
            result = self.simit.consult(plate)
            if "error" in result:
                entry["status"] = "error"
                print(f"[SIMIT] Error {plate}: {result['error']}")
                return
            nivel = self.simit.classify(result)
            entry["result"] = result
            entry["nivel"] = nivel
            entry["status"] = "ok"
            c = result.get("total_comparendos", 0)
            m = result.get("total_multas", 0)
            a = result.get("total_acuerdos", 0)
            print(f"[SIMIT] {plate}: C={c} M={m} A={a} ${result.get('total_pendiente',0):,} -- {nivel}")
        except Exception as e:
            entry["status"] = "error"
            print(f"[SIMIT] Error {plate}: {e}")

    def _download_pdf(self, plate, entry):
        entry["pdf_status"] = "descargando..."
        try:
            path = self.simit.download_pdf(plate, result=entry.get("result"))
            entry["pdf_path"] = path
            if path:
                entry["pdf_status"] = "PDF listo"
                os.startfile(path)
            else:
                entry["pdf_status"] = "Error"
        except Exception:
            entry["pdf_status"] = "Error"

    def _mouse_cb(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if self._scrollbar_rect and self._scrollbar_rect[0] <= x <= self._scrollbar_rect[0] + SCROLL_W:
                sy, sh, total = self._scrollbar_rect[1], self._scrollbar_rect[2], self._scrollbar_rect[3]
                click_ratio = (y - sy) / sh if sh > 0 else 0
                max_offset = max(0, total - self._visible_count)
                self._scroll_offset = int(click_ratio * max_offset)
            else:
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

                if self._boxes and crops:
                    if self._batch is None:
                        if time.time() >= self._batch_cooldown:
                            best_idx = max(range(len(boxes)), key=lambda i: boxes[i][4])
                            self._batch = {"crops": [crops[best_idx]], "start": time.time()}
                    else:
                        best_idx = max(range(len(boxes)), key=lambda i: boxes[i][4])
                        self._batch["crops"].append(crops[best_idx])
                        if len(self._batch["crops"]) >= BATCH_SIZE:
                            self._submit_batch()

                elif self._batch is not None:
                    batch_age = time.time() - self._batch["start"]
                    if self._batch["crops"] and batch_age >= BATCH_TIMEOUT:
                        self._submit_batch()
                    elif not self._batch["crops"] and batch_age >= BATCH_TIMEOUT:
                        self._batch = None
                        self._batch_cooldown = 0.0

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

            if self._frame_count % GC_INTERVAL == 0:
                gc.collect()

            for x1, y1, x2, y2, conf in self._boxes:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 80), 2)
                label = f"  {conf:.0%}"
                cv2.rectangle(frame, (x1, y1 - 22), (x1 + 60, y1), (0, 200, 80), -1)
                cv2.putText(frame, label, (x1 + 4, y1 - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            try:
                panel = np.full((WINDOW_H, WINDOW_W, 3), (15, 15, 15), dtype=np.uint8)
            except MemoryError:
                gc.collect()
                continue

            panel[:CAM_H, :CAM_W] = cv2.resize(frame, (CAM_W, CAM_H))

            # --- Status bar under camera ---
            sy = CAM_H
            cv2.rectangle(panel, (0, sy), (CAM_W, sy + STATUS_H), (25, 25, 25), -1)

            if self._batch is not None and len(self._batch["crops"]) > 0:
                progress = min(len(self._batch["crops"]) / BATCH_SIZE, 1.0)
                bar_x, bar_y, bar_w = 8, sy + 7, 140
                bw = int(bar_w * progress)
                cv2.rectangle(panel, (bar_x, bar_y), (bar_x + bar_w, bar_y + 16), (50, 50, 50), -1)
                cv2.rectangle(panel, (bar_x, bar_y), (bar_x + bw, bar_y + 16), (0, 140, 255), -1)
                cv2.putText(panel, f"{len(self._batch['crops'])}/{BATCH_SIZE}",
                            (bar_x + 4, bar_y + 13), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

            if time.time() < self._batch_cooldown:
                remaining = self._batch_cooldown - time.time()
                cv2.putText(panel, f"Espera {remaining:.0f}s", (180, sy + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

            cv2.putText(panel, "Q: salir", (CAM_W - 70, sy + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

            # --- List panel ---
            self._pdf_btns = []
            y = LIST_Y
            cv2.putText(panel, "PLACAS DETECTADAS", (LIST_X + 15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 2)
            y += 35

            sorted_plates = sorted(self.entries.items(), key=lambda x: x[1]["last_seen"], reverse=True)
            total_entries = len(sorted_plates)
            list_top = y
            list_bottom = WINDOW_H - 10
            list_avail = list_bottom - list_top
            self._visible_count = max(1, list_avail // (ENTRY_H + ENTRY_GAP))

            max_offset = max(0, total_entries - self._visible_count)
            self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

            for idx in range(self._scroll_offset, min(total_entries, self._scroll_offset + self._visible_count)):
                plate, e = sorted_plates[idx]
                by = list_top + (idx - self._scroll_offset) * (ENTRY_H + ENTRY_GAP)
                if by + ENTRY_H > list_bottom:
                    break

                cv2.rectangle(panel, (LIST_X + 8, by), (LIST_X + LIST_W - SCROLL_W - 12, by + ENTRY_H), (30, 30, 30), -1)

                color = (100, 100, 100)
                status_text = e["status"]
                if e["status"] == "ok":
                    clr = CLASIFICACION.get(e["nivel"], CLASIFICACION["normal"])
                    color = clr["color"]
                    status_text = clr["label"]

                cv2.putText(panel, plate, (LIST_X + 15, by + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                sw = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                sx = LIST_X + LIST_W - SCROLL_W - PDF_BTN_W - 25 - sw[0]
                cv2.putText(panel, status_text, (sx, by + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                if e["status"] == "ok" and e["result"]:
                    r = e["result"]
                    stats = f"Comparendos:{r.get('total_comparendos',0)}  Multas:{r.get('total_multas',0)}"
                    cv2.putText(panel, stats, (LIST_X + 15, by + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1)
                    total_val = r.get("total_pendiente", 0)
                    acuerdos = r.get("total_acuerdos", 0)
                    cv2.putText(panel, f"Acuerdos:{acuerdos}", (LIST_X + 15, by + 68), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                                (180, 180, 180), 1)
                    total_str = f"${total_val:,}" if total_val > 0 else "Sin deudas"
                    total_color = (0, 255, 255) if total_val > 0 else (0, 200, 80)
                    cv2.putText(panel, total_str, (LIST_X + 160, by + 68), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                                total_color, 1)

                    total_records = r.get("total_comparendos", 0) + r.get("total_multas", 0) + r.get("total_acuerdos", 0)
                    if total_records > 0:
                        bx = LIST_X + LIST_W - SCROLL_W - PDF_BTN_W - 20
                        self._pdf_btns.append((bx, by + 4, PDF_BTN_W, PDF_BTN_H, plate))
                        cv2.rectangle(panel, (bx, by + 4), (bx + PDF_BTN_W, by + 4 + PDF_BTN_H), (0, 120, 200), -1)
                        cv2.rectangle(panel, (bx, by + 4), (bx + PDF_BTN_W, by + 4 + PDF_BTN_H), (200, 200, 200), 1)

                        pdf_txt = e["pdf_status"] if e["pdf_status"] else "PDF"
                        sz = cv2.getTextSize(pdf_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                        px = bx + (PDF_BTN_W - sz[0]) // 2
                        py = by + 4 + (PDF_BTN_H + sz[1]) // 2
                        cv2.putText(panel, pdf_txt, (px, py), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                elif e["status"] == "consultando":
                    cv2.putText(panel, "Consultando SIMIT...", (LIST_X + 15, by + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                (200, 200, 0), 1)
                elif e["status"] == "error":
                    cv2.putText(panel, "Error en consulta", (LIST_X + 15, by + 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                (0, 0, 200), 1)

            # --- Scrollbar ---
            sx = LIST_X + LIST_W - SCROLL_W
            sy_scroll = list_top
            sh = list_bottom - list_top
            cv2.rectangle(panel, (sx, sy_scroll), (sx + SCROLL_W, sy_scroll + sh), (40, 40, 40), -1)

            if total_entries > self._visible_count:
                thumb_h = max(16, int(sh * self._visible_count / total_entries))
                thumb_y = sy_scroll + int((sh - thumb_h) * self._scroll_offset / max_offset) if max_offset > 0 else sy_scroll
                cv2.rectangle(panel, (sx, thumb_y), (sx + SCROLL_W, thumb_y + thumb_h), (120, 120, 120), -1)
                self._scrollbar_rect = (sx, sy_scroll, sh, total_entries)
            else:
                self._scrollbar_rect = None

            cv2.imshow("ALPR Colombia", panel)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == 82 and self._scroll_offset > 0:
                self._scroll_offset -= 1
            elif key == 84:
                max_offset = max(0, total_entries - self._visible_count)
                if self._scroll_offset < max_offset:
                    self._scroll_offset += 1

        cap.release()
        cv2.destroyAllWindows()
        self._simit_executor.shutdown(wait=False)
        self._ocr_executor.shutdown(wait=False)
        self.simit.close()

        for entry in os.listdir(SAVE_DIR):
            path = os.path.join(SAVE_DIR, entry)
            try:
                if os.path.isdir(path):
                    for f in os.listdir(path):
                        os.remove(os.path.join(path, f))
                    os.rmdir(path)
                else:
                    os.remove(path)
            except OSError:
                pass
        print(f"[ALPR] Captures limpiadas: {SAVE_DIR}/")


if __name__ == "__main__":
    ALPRSystem().run()
