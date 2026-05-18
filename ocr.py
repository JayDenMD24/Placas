import re
import cv2
import numpy as np

try:
    import easyocr
except ImportError:
    raise ImportError("Instala easyocr: pip install easyocr")

PATTERNS = {
    "particular": re.compile(r"^[A-Z]{3}[0-9]{3}$"),
    "moto":       re.compile(r"^[A-Z]{3}[0-9]{2}[A-Z]$"),
    "diplomatica":re.compile(r"^CD[0-9]{4}$"),
}

CHAR_FIX = {
    "0": "O", "1": "I", "2": "Z", "4": "A", "5": "S",
    "6": "G", "7": "T", "8": "B", "9": "G",
    "O": "0", "I": "1", "B": "8", "S": "5",
    "G": "6", "Z": "2", "T": "7", "A": "4",
    "D": "0", "L": "1", "E": "8", "Q": "0",
    "U": "0", "V": "U", "H": "W",
}

def _is_likely_city(text: str) -> bool:
    if len(text) < 4:
        return False
    letters = sum(1 for c in text if c.isalpha())
    return letters >= 4 and letters == len(text)


def _fix_plate(text: str) -> str | None:
    clean = re.sub(r"[^A-Z0-9]", "", text.upper().strip())
    if not clean:
        return None

    candidates = [clean]
    if len(clean) > 6:
        for i in range(len(clean) - 5):
            candidates.append(clean[i:i+6])
    elif len(clean) == 5:
        candidates.append("0" + clean)
        candidates.append(clean + "0")

    letter_positions_by_type = {
        "particular": ([0, 1, 2], [3, 4, 5]),
        "moto":       ([0, 1, 2, 5], [3, 4]),
        "diplomatica":([0, 1], [2, 3, 4, 5]),
    }

    for cand in candidates:
        for pattern in PATTERNS.values():
            if pattern.match(cand) and not _is_likely_city(cand):
                return cand

    for cand in candidates:
        if len(cand) != 6:
            continue
        for tipo, pattern in PATTERNS.items():
            letter_pos, digit_pos = letter_positions_by_type[tipo]
            fixed = list(cand)
            changed = False
            for i, c in enumerate(cand):
                if i in letter_pos and c.isdigit():
                    fixed[i] = CHAR_FIX.get(c, c)
                    changed = True
                elif i in digit_pos and c.isalpha():
                    fixed[i] = CHAR_FIX.get(c, c)
                    changed = True
            if changed:
                result = "".join(fixed)
                if pattern.match(result) and not _is_likely_city(result):
                    return result

    return None


class PlateReader:
    def __init__(self):
        print("[OCR] Inicializando EasyOCR...")
        self.reader = easyocr.Reader(["en"], gpu=False)
        print("[OCR] Listo.")

    def read(self, img: np.ndarray) -> str:
        def _ocr(image):
            results = self.reader.readtext(image, detail=1, paragraph=False)
            if not results:
                return ""
            results.sort(key=lambda r: r[0][0][1])

            plates = []
            others = []
            for (bbox, text, conf) in results:
                fixed = _fix_plate(text)
                if fixed:
                    y_center = (bbox[0][1] + bbox[2][1]) / 2
                    plates.append((fixed, conf, y_center))
                else:
                    clean = re.sub(r"[^A-Z0-9]", "", text.upper())
                    if len(clean) >= 3 and conf > 0.3:
                        y_center = (bbox[0][1] + bbox[2][1]) / 2
                        others.append((clean, conf, y_center))

            if plates:
                plates.sort(key=lambda x: x[2])
                main_plate = plates[0][0]
                rest = [o[0] for o in others]
                if rest:
                    return f"{main_plate} {' '.join(rest)}"
                return main_plate
            if others:
                others.sort(key=lambda x: -x[1])
                return " ".join(o[0] for o in others)
            return ""

        img_h, img_w = img.shape[:2]
        if img_w < 300:
            scale = 300 / img_w
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        text = _ocr(gray)
        if not text and img_w < 300:
            text = _ocr(img)
        return text


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        reader = PlateReader()
        img = cv2.imread(sys.argv[1])
        print(f"Placa detectada: {reader.read(img)}")
