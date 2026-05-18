import os
import time
from fpdf import FPDF


def _sanitize(text):
    if not text:
        return ""
    return text.encode("latin-1", errors="replace").decode("latin-1")

def _wrap_text(pdf, text, w):
    text = _sanitize(text)
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        test = cur + (" " if cur else "") + word
        if pdf.get_string_width(test) < w - 1.5:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines if lines else [""]

def _fit_text(pdf, text, w):
    text = _sanitize(text)
    if not text:
        return ""
    fit = text
    while fit and pdf.get_string_width(fit) > w - 1.5:
        fit = fit[:-1]
    return fit

def _parse_val(v):
    if not v:
        return 0
    cleaned = v.replace("$", "").replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


class SIMITPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="L", format="A4")
        self.alias_nb_pages()
        self.set_auto_page_break(auto=False)

    def header(self):
        self.set_fill_color(20, 50, 110)
        self.rect(0, 0, 298, 22, "F")
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 4)
        self.cell(0, 7, "Federaci\u00f3n Colombiana de Municipios", align="C")
        self.set_font("Helvetica", "", 8)
        self.set_xy(10, 12)
        self.cell(0, 5, "SIMIT - Sistema Integrado de Informaci\u00f3n de Multas y Sanciones", align="C")
        # line moved to generate_pdf()

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"P\u00e1gina {self.page_no()}/{{nb}}     Generado por ALPR Colombia", align="C")


PAGE_W = 297
PAGE_H = 210
MARGIN = 10
HEADER_H = 28
COL_W = [8, 22, 48, 82, 24, 28, 32, 28]
TABLE_W = sum(COL_W)
TABLE_LEFT = (PAGE_W - TABLE_W) / 2
LINE_H = 3.0
ROW_MIN_H = 6
PAGE_BREAK_Y = PAGE_H - 20


def generate_pdf(plate: str, data: dict, save_path: str = None) -> str:
    downloads_path = save_path or os.path.join(os.path.dirname(__file__), "downloads")
    os.makedirs(downloads_path, exist_ok=True)
    file_path = os.path.join(downloads_path, f"simit_{plate}_{int(time.time())}.pdf")

    pdf = SIMITPDF()

    comparendos = data.get("comparendos", [])
    total_c = data.get("total_comparendos", 0)
    total_m = data.get("total_multas", 0)
    total_a = data.get("total_acuerdos", 0)
    total_pendiente = data.get("total_pendiente", 0)
    total_records = total_c + total_m + total_a
    total_val = sum(_parse_val(c.get("valor", "")) for c in comparendos)

    def draw_table_header():
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_fill_color(20, 50, 110)
        pdf.set_text_color(255, 255, 255)
        pdf.set_x(TABLE_LEFT)
        for i, h in enumerate(headers):
            pdf.cell(COL_W[i], 8, h, border=1, fill=True, align="C")
        pdf.ln()

    def start_row():
        pdf.set_x(TABLE_LEFT)

    def row_fits(h):
        return pdf.get_y() + h <= PAGE_BREAK_Y

    def do_page_break():
        pdf.add_page()
        pdf.set_y(HEADER_H + 4)
        draw_table_header()
        pdf.set_font("Helvetica", "", 6.5)

    headers = ["#", "Tipo", "No. Comparendo", "Infracci\u00f3n", "Fecha", "Valor", "Estado", "Secretar\u00eda"]
    col_aligns = ["C", "C", "L", "L", "C", "R", "C", "L"]

    # --- NO RECORDS PAGE ---
    if total_records == 0:
        pdf.add_page()
        pdf.ln(40)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(20, 50, 110)
        pdf.cell(0, 15, f"Placa: {plate}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(8)
        pdf.set_font("Helvetica", "", 16)
        pdf.set_text_color(0, 160, 70)
        pdf.cell(0, 12, "Sin comparendos ni multas registradas", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 160, 70)
        pdf.cell(0, 10, "Clasificaci\u00f3n: SIN REGISTROS", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(40)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 4, "Documento generado autom\u00e1ticamente por ALPR Colombia.", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 4, "Fuente: SIMIT - Federaci\u00f3n Colombiana de Municipios.", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.output(file_path)
        return file_path

    # --- PAGE 1: title + cards + table header ---
    pdf.add_page()
    pdf.set_y(28)

    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(20, 50, 110)
    pdf.cell(0, 10, "Estado de Cuenta", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    fecha = time.strftime("%d/%m/%Y %I:%M %p")
    pdf.cell(0, 5, f"Placa: {plate}    |    Fecha de consulta: {fecha}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 288, pdf.get_y())
    pdf.ln(4)

    # --- Cards ---
    card_w = 50
    card_h = 26
    gap = 6
    cards_total = 5 * card_w + 4 * gap
    card_start = (PAGE_W - cards_total) / 2
    cards_data = [
        ("Comparendos", str(total_c), (200, 130, 0)),
        ("Multas", str(total_m), (220, 100, 0)),
        ("Acuerdos", str(total_a), (50, 100, 180)),
        ("Total Registros", str(total_records), (20, 50, 110)),
        ("Total Adeudado", f"${total_pendiente:,}" if total_pendiente > 0 else "$0",
         (180, 30, 30) if total_pendiente > 0 else (0, 160, 70)),
    ]
    y_card = pdf.get_y()
    for i, (label, value, bg) in enumerate(cards_data):
        x = card_start + i * (card_w + gap)
        r, g, b = bg
        pdf.set_fill_color(r, g, b)
        pdf.rect(x, y_card, card_w, card_h, "F")
        pdf.set_xy(x, y_card + 3)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(card_w, 5, label, align="C")
        pdf.set_xy(x, y_card + 10)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(card_w, 9, value, align="C")

    pdf.set_y(y_card + card_h + 6)

    draw_table_header()

    # --- ROWS ---
    pdf.set_font("Helvetica", "", 6.5)

    for idx, c in enumerate(comparendos, 1):
        inf_lines = _wrap_text(pdf, c.get("infraccion", ""), COL_W[3])
        num_lines = max(1, len(inf_lines))
        row_h = max(ROW_MIN_H, num_lines * LINE_H + 2)

        if not row_fits(row_h):
            do_page_break()

        start_row()
        y0 = pdf.get_y()
        x0 = TABLE_LEFT

        # Background
        pdf.set_fill_color(242, 246, 255) if idx % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(180, 180, 180)
        pdf.rect(x0, y0, TABLE_W, row_h, "DF")

        # Multi-line infraction column
        cx = x0 + sum(COL_W[:3])
        pdf.set_text_color(0, 0, 0)
        for li, line in enumerate(inf_lines):
            pdf.set_xy(cx + 0.5, y0 + 1 + li * LINE_H)
            pdf.cell(COL_W[3] - 1, LINE_H, line, align="L")

        # Other columns
        col_txt = [
            str(idx),
            c.get("tipo", ""),
            _fit_text(pdf, c.get("numero", ""), COL_W[2]),
            None,
            c.get("fecha", "")[:10],
            c.get("valor", "") or "$0",
            _fit_text(pdf, c.get("estado", ""), COL_W[6]),
            _fit_text(pdf, c.get("secretaria", ""), COL_W[7]),
        ]

        for j, txt in enumerate(col_txt):
            if txt is None or j == 3:
                continue
            cxx = x0 + sum(COL_W[:j])
            if j == 6:
                raw = c.get("estado", "")
                pdf.set_text_color(180, 20, 20) if "pendiente" in raw.lower() else pdf.set_text_color(0, 120, 50)
            else:
                pdf.set_text_color(0, 0, 0)
            pdf.set_xy(cxx + 0.5, y0 + (row_h - LINE_H) / 2)
            pdf.cell(COL_W[j] - 1, LINE_H, txt, align=col_aligns[j])

        pdf.set_y(y0 + row_h)

    # --- Totals row ---
    if not row_fits(8):
        do_page_break()
    start_row()
    pdf.set_fill_color(225, 232, 245)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 8)
    tot_w = sum(COL_W[:5])
    pdf.cell(tot_w, 8, "TOTALES", border=1, fill=True, align="R")
    pdf.cell(COL_W[5], 8, f"${total_val:,}", border=1, fill=True, align="R")
    pdf.cell(sum(COL_W[6:]), 8, "", border=1, fill=True)
    pdf.ln(12)

    # --- Classification ---
    if total_records == 0:
        nivel = "SIN REGISTROS"
        color = (0, 160, 70)
    elif total_records <= 2:
        nivel = "CON REGISTROS"
        color = (180, 140, 0)
    else:
        nivel = "REGISTROS M\u00daLTIPLES"
        color = (180, 30, 30)

    pdf.set_draw_color(*color)
    pdf.set_line_width(0.8)
    pdf.line(TABLE_LEFT, pdf.get_y(), TABLE_LEFT + TABLE_W, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*color)
    pdf.cell(0, 8, f"Clasificaci\u00f3n: {nivel}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.line(TABLE_LEFT, pdf.get_y(), TABLE_LEFT + TABLE_W, pdf.get_y())
    pdf.ln(4)

    # --- Footer ---
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 4, "Documento generado autom\u00e1ticamente por ALPR Colombia.", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 4, "Fuente: SIMIT - Federaci\u00f3n Colombiana de Municipios.", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.output(file_path)
    print(f"[PDF] Generado localmente: {file_path}")
    return file_path
