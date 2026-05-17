import os
import unicodedata
import re
import time
from typing import Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Instala beautifulsoup4: pip install beautifulsoup4")

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    raise ImportError("Instala playwright: pip install playwright && playwright install chromium")

CODIGOS_INFRACCION = {
    "A01": "Conducir un vehículo sin licencia de conducción",
    "A02": "Conducir un vehículo con licencia de conducción vencida",
    "A03": "Conducir un vehículo en estado de embriaguez o bajo efectos de sustancias psicoactivas",
    "A04": "Conducir un vehículo con licencia de conducción suspendida o cancelada",
    "A05": "No respetar las señales de tránsito",
    "B01": "Conducir un vehículo sin placas",
    "B02": "Conducir un vehículo con placas adulteradas o alteradas",
    "B03": "Conducir un vehículo con vidrios polarizados sin autorización",
    "C01": "Conducir un vehículo excediendo los límites de velocidad",
    "C02": "No detenerse ante una luz roja o semáforo en rojo",
    "C03": "Adelantar en lugares prohibidos",
    "C04": "Conducir un vehículo en sentido contrario",
    "C05": "Realizar maniobras peligrosas",
    "C06": "Conducir un vehículo sin guardar la distancia de seguridad",
    "C07": "No respetar los pasos de peatones",
    "C08": "Conducir un vehículo en estado de embriaguez o bajo efectos de sustancias psicoactivas",
    "C09": "No utilizar el cinturón de seguridad",
    "C10": "No utilizar el casco de seguridad",
    "C11": "Conducir un vehículo utilizando equipos de comunicación",
    "C12": "No respetar las normas de tránsito",
    "C13": "Conducir un vehículo con licencia de conducción diferente a la requerida",
    "C14": "Conducir un vehículo con la revisión técnico-mecánica vencida",
    "C15": "No portar el seguro obligatorio SOAT",
    "D01": "Guiar un vehículo sin haber tenido la licencia de conducción correspondiente",
    "D02": "Guiar un vehículo con licencia de conducción vencida",
    "D03": "Guiar un vehículo en estado de embriaguez o bajo efectos de sustancias psicoactivas",
    "D04": "Guiar un vehículo con licencia de conducción suspendida o cancelada",
    "D05": "No respetar las señales de tránsito",
    "D06": "No detenerse ante una luz roja o semáforo en rojo",
    "D07": "Conducir un vehículo excediendo los límites de velocidad",
    "D08": "Adelantar en lugares prohibidos",
    "D09": "Conducir un vehículo en sentido contrario",
    "D10": "Realizar maniobras peligrosas",
    "D11": "No respetar los pasos de peatones",
    "D12": "No utilizar el cinturón de seguridad",
    "D13": "No utilizar el casco de seguridad",
    "D14": "Conducir un vehículo utilizando equipos de comunicación",
    "D15": "No portar el seguro obligatorio SOAT",
    "E01": "No realizar la revisión técnico-mecánica en el plazo establecido",
    "E02": "No portar la licencia de tránsito",
    "E03": "No portar la licencia de conducción",
    "E04": "No portar el certificado de revisión técnico-mecánica",
    "E05": "No portar el SOAT",
    "F01": "No pagar el peaje",
    "F02": "No respetar las normas de estacionamiento",
    "F03": "Arrojar basura a la vía pública",
    "F04": "Realizar reparaciones en vía pública",
    "G01": "No cumplir con las normas de emisión de gases",
    "G02": "Conducir un vehículo con niveles de ruido excesivos",
    "H01": "No respetar las normas de tránsito establecidas para vehículos de servicio público",
    "H02": "El conductor que no porte la licencia de tránsito, además el vehículo será inmovilizado",
    "H03": "No contar con la revisión técnico-mecánica vigente para vehículos de servicio público",
    "H04": "No cumplir con las normas de emisión de gases para vehículos de servicio público",
    "H05": "No portar el SOAT para vehículos de servicio público",
    "H06": "No respetar las normas de estacionamiento para vehículos de servicio público",
    "H07": "Conducir un vehículo de servicio público sin tener la licencia de conducción correspondiente",
    "H08": "Conducir un vehículo de servicio público en estado de embriaguez o bajo efectos de sustancias psicoactivas",
    "H09": "No respetar las señales de tránsito para vehículos de servicio público",
    "H10": "Los conductores de vehículos no automotores que incurran en las infracciones establecidas en el presente código",
    "H11": "No cumplir con las normas de tránsito para vehículos de servicio público",
    "I01": "No cumplir con las normas de tránsito establecidas para vehículos de carga",
    "I02": "No cumplir con las normas de emisión de gases para vehículos de carga",
    "I03": "No portar el SOAT para vehículos de carga",
    "I04": "No respetar las normas de estacionamiento para vehículos de carga",
    "I05": "Conducir un vehículo de carga sin tener la licencia de conducción correspondiente",
    "I06": "Conducir un vehículo de carga en estado de embriaguez o bajo efectos de sustancias psicoactivas",
    "J01": "No cumplir con las normas de tránsito establecidas para vehículos de transporte escolar",
    "J02": "No cumplir con las normas de emisión de gases para vehículos de transporte escolar",
    "J03": "No portar el SOAT para vehículos de transporte escolar",
    "K01": "No cumplir con las normas de tránsito establecidas para motocicletas",
    "K02": "No utilizar el casco de seguridad para motocicletas",
    "K03": "Conducir una motocicleta con licencia de conducción diferente a la requerida",
    "K04": "No respetar las señales de tránsito para motocicletas",
    "K05": "Conducir una motocicleta en estado de embriaguez o bajo efectos de sustancias psicoactivas",
    "K06": "No portar el SOAT para motocicletas",
    "K07": "Conducir una motocicleta sin la revisión técnico-mecánica vigente",
    "L01": "No cumplir con las normas de tránsito establecidas para vehículos de transporte masivo",
    "L02": "No cumplir con las normas de emisión de gases para vehículos de transporte masivo",
    "L03": "No portar el SOAT para vehículos de transporte masivo",
    "M01": "No cumplir con las normas de tránsito establecidas para vehículos de transporte intermunicipal",
    "M02": "No cumplir con las normas de emisión de gases para vehículos de transporte intermunicipal",
    "M03": "No portar el SOAT para vehículos de transporte intermunicipal",
    "N01": "No cumplir con las normas de tránsito establecidas para vehículos de transporte internacional",
    "N02": "No cumplir con las normas de emisión de gases para vehículos de transporte internacional",
    "N03": "No portar el SOAT para vehículos de transporte intermunicipal",
}

SIMIT_URL = "https://www.fcm.org.co/simit/#/home-public"


def _crear_navegador():
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    return p, browser, context


def _consultar_en_pagina(page, plate: str) -> Optional[str]:
    """Navega SIMIT, consulta placa, retorna HTML de resultados o None."""
    page.goto(SIMIT_URL, timeout=60_000)
    page.wait_for_load_state("domcontentloaded", timeout=30_000)
    time.sleep(1.5)

    close_btn = page.query_selector("button.close.modal-info-close")
    if close_btn and close_btn.is_visible():
        close_btn.click()
        time.sleep(0.5)

    field = page.query_selector('input[placeholder*="identificaci" i]')
    if not field:
        inputs = page.query_selector_all("input:visible")
        for inp in inputs:
            if inp.get_attribute("placeholder"):
                field = inp
                break
    if not field:
        return None

    field.click()
    field.fill("")
    field.type(plate, delay=20)
    time.sleep(0.5)

    btn = page.query_selector("button.btn-primary.font-weight-bold")
    if not btn:
        btn = page.query_selector('button:has-text("Consultar")')
    if not btn:
        btns = page.query_selector_all("button:visible")
        for b in btns:
            if not b.inner_text().strip():
                btn = b
                break
    if not btn:
        return None

    btn.click()
    time.sleep(1.5)

    try:
        page.wait_for_function("""
            () => {
                const tables = document.querySelectorAll('table');
                for (const t of tables) {
                    const rows = t.querySelectorAll('tr');
                    if (rows.length < 2) continue;
                    const cells = rows[1].querySelectorAll('td');
                    for (const c of cells) {
                        const txt = (c.innerText || '').toLowerCase();
                        if (txt.includes('comparendo') || txt.includes('multa')) return true;
                    }
                }
                const body = document.body.innerText.toLowerCase();
                if (body.includes('no tienes comparendos')) {
                    const allCells = document.querySelectorAll('td');
                    if (allCells.length < 2) return true;
                }
                return false;
            }
        """, timeout=90_000)
    except Exception:
        pass

    return page.content()


class SIMITScraper:
    def __init__(self):
        pass

    def _normalize(self, s: str) -> str:
        return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower()

    def _parse_results(self, html: str, plate: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        data = {
            "placa": plate,
            "comparendos": [],
            "total_comparendos": 0,
            "total_multas": 0,
            "acuerdos": [],
            "total_acuerdos": 0,
            "total_pendiente": 0,
        }

        tables = soup.find_all("table")

        DEFAULT_COL_MAP = {"tipo": 0, "notificacion": 1, "infraccion": 4, "estado": 5, "valor": 6, "secretaria": 3}

        for table in tables:
            headers = [self._normalize(th.get_text(strip=True)) for th in table.find_all("th")]
            header_text = " ".join(headers)
            rows = table.find_all("tr")

            if len(rows) < 2:
                continue

            col_map = {}
            if headers:
                for i, h in enumerate(headers):
                    if "infraccion" in h or "codigo" in h or "descripcion" in h:
                        col_map["infraccion"] = i
                    elif "fecha" in h and "imposicion" not in h:
                        col_map["fecha"] = i
                    elif "valor" in h and "pagar" not in h:
                        col_map["valor"] = i
                    elif "estado" in h or "pendiente" in h:
                        col_map["estado"] = i
                    elif "tipo" in h or "comparendo" in h:
                        col_map["tipo"] = i
                    elif "secretaria" in h or "organismo" in h or "municipio" in h:
                        col_map["secretaria"] = i
                    elif "notificacion" in h:
                        col_map["notificacion"] = i

            if not col_map:
                sample = rows[1].find_all("td")
                if len(sample) >= 9:
                    col_map = dict(DEFAULT_COL_MAP)
                elif len(sample) >= 4:
                    col_map = {"tipo": 0, "infraccion": 1, "estado": 2, "valor": 3}

            registros = []
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue

                ti = col_map.get("tipo", 0)
                ei = col_map.get("infraccion", 4)
                sti = col_map.get("estado", 5)
                vi = col_map.get("valor", 6)
                si = col_map.get("secretaria", 3)

                cell_tipo = cells[ti].get_text("\n", strip=True) if ti < len(cells) else ""
                cell_inf = cells[ei] if ei < len(cells) else None
                cell_estado = cells[sti].get_text(strip=True) if sti < len(cells) else ""
                cell_valor = cells[vi].get_text(strip=True) if vi < len(cells) else ""
                cell_secretaria = cells[si].get_text(strip=True) if si < len(cells) else ""

                if not cell_tipo and not cell_estado:
                    continue

                tipo_texto = "Comparendo"
                fecha = ""
                numero = ""

                m_num = re.search(r"(\d+)", cell_tipo)
                if m_num:
                    numero = m_num.group(1)

                m_fec = re.search(r"(\d{2}/\d{2}/\d{4})", cell_tipo)
                if m_fec:
                    fecha = m_fec.group(1)

                if "multa" in cell_tipo.lower():
                    tipo_texto = "Multa"

                codigo = ""
                descripcion = ""
                if cell_inf:
                    span = cell_inf.find("span")
                    if span:
                        codigo = span.get_text(strip=True)
                        desc = span.get("data-content") or span.get("title") or ""
                        descripcion = desc.strip()
                    else:
                        codigo = cell_inf.get_text(strip=True)

                if codigo and descripcion:
                    infraccion_completa = f"{codigo} {descripcion}"
                elif codigo:
                    code_key = codigo.replace(".", "").replace("…", "").replace("...", "").strip()[:3]
                    if code_key in CODIGOS_INFRACCION:
                        infraccion_completa = f"{codigo} {CODIGOS_INFRACCION[code_key]}"
                    else:
                        infraccion_completa = codigo
                else:
                    infraccion_completa = ""

                estado = re.sub(r"No tiene curso.*$", "", cell_estado).strip()

                registros.append({
                    "tipo": tipo_texto,
                    "numero": numero,
                    "infraccion": infraccion_completa,
                    "fecha": fecha,
                    "valor": cell_valor.replace("\xa0", " ").strip(),
                    "estado": estado,
                    "secretaria": cell_secretaria,
                })

            if not registros:
                continue

            if any(k in header_text for k in ("acuerdo", "pago", "cuota")):
                data["acuerdos"] = registros
                data["total_acuerdos"] = len(registros)
            elif any(k in header_text for k in ("comparendo", "infraccion", "multa")):
                data["comparendos"] = registros
                data["total_comparendos"] = sum(1 for r in registros if r.get("tipo") == "Comparendo")
                data["total_multas"] = sum(1 for r in registros if r.get("tipo") == "Multa")
            else:
                data["comparendos"] = registros
                data["total_comparendos"] = sum(1 for r in registros if r.get("tipo") == "Comparendo")
                data["total_multas"] = sum(1 for r in registros if r.get("tipo") == "Multa")

        total_patterns = [
            r"total\s*(?:a\s*pagar|pendiente)?\s*[:\$]?\s*\$?\s*([\d\.,]+)",
            r"\$([\d\.,]+)\s*(?:total|pendiente)",
        ]
        body = soup.get_text(" ", strip=True)
        for pat in total_patterns:
            tm = re.search(pat, body, re.IGNORECASE)
            if tm:
                try:
                    val = tm.group(1).replace(".", "").replace(",", "")
                    data["total_pendiente"] = int(val)
                    break
                except ValueError:
                    pass

        return data

    def consult(self, plate: str) -> dict:
        plate = plate.upper().strip()
        print(f"[SIMIT] Consultando placa: {plate}")

        p, browser, context = _crear_navegador()
        page = context.new_page()
        try:
            html = _consultar_en_pagina(page, plate)
            if html is None:
                return {"error": "No se pudo completar la consulta", "placa": plate}
            data = self._parse_results(html, plate)
            return data
        except PlaywrightTimeout:
            return {"error": "Tiempo de espera agotado", "placa": plate}
        except Exception as e:
            return {"error": str(e), "placa": plate}
        finally:
            page.close()
            browser.close()
            p.stop()

    def download_pdf(self, plate: str, save_path: str = None) -> Optional[str]:
        plate = plate.upper().strip()
        print(f"[SIMIT] Descargando PDF para: {plate}")

        downloads_path = save_path or os.path.join(os.path.dirname(__file__), "downloads")
        os.makedirs(downloads_path, exist_ok=True)
        file_path = os.path.join(downloads_path, f"simit_{plate}_{int(time.time())}.pdf")

        p, browser, context = _crear_navegador()
        page = context.new_page()

        captured_url = {"value": None}

        def on_response(response):
            if response.url.endswith(".pdf") or "/pdf/" in response.url.lower():
                captured_url["value"] = response.url

        page.on("response", on_response)

        try:
            html = _consultar_en_pagina(page, plate)
            if html is None:
                return None

            # Verificar si la consulta trajo resultados
            preview = page.inner_text("body").lower()
            celdas = page.query_selector_all("td:first-child")
            tiene_datos = any("comparendo" in (c.inner_text() or "").lower() or "multa" in (c.inner_text() or "").lower() for c in celdas)
            if not tiene_datos and "no tienes comparendos" in preview:
                print(f"[SIMIT] Sin registros para {plate}, se omite PDF")
                return None

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)

            guardar = page.query_selector('a:has-text("Guardar estado")')
            if not guardar:
                guardar = page.query_selector('[data-target="#modal-estado-cuenta"]')
            if not guardar:
                print("[SIMIT] No se encontro boton Guardar estado")
                return None

            guardar.scroll_into_view_if_needed()
            guardar.click()

            try:
                page.wait_for_selector("#modal-estado-cuenta", timeout=10_000)
            except Exception:
                print("[SIMIT] Modal no aparecio")
                return None

            time.sleep(1)

            modal = page.query_selector("#modal-estado-cuenta")
            if not modal or not modal.is_visible():
                print("[SIMIT] Modal no visible")
                return None

            pdf_btn = modal.query_selector('a:has-text("Descargar PDF")')
            if not pdf_btn:
                pdf_btn = modal.query_selector('button:has-text("Descargar PDF")')
            if not pdf_btn:
                print("[SIMIT] No se encontro boton Descargar PDF en el modal")
                return None

            # Intentar 1: extraer href directo del link
            href = pdf_btn.get_attribute("href")
            if href and not href.startswith("#") and not href.startswith("javascript"):
                pdf_url = href if href.startswith("http") else f"https://www.fcm.org.co{href}"
                import requests
                try:
                    r = requests.get(pdf_url, timeout=30)
                    if r.status_code == 200 and len(r.content) > 1000:
                        with open(file_path, "wb") as f:
                            f.write(r.content)
                        print(f"[SIMIT] PDF descargado via href directo: {file_path}")
                        return file_path
                except Exception as e:
                    print(f"[SIMIT] Fallo descarga directa href: {e}")

            # Intentar 2: expect_download
            download = None
            try:
                with page.expect_download(timeout=60_000) as download_info:
                    pdf_btn.click()
                    time.sleep(2)
                download = download_info.value
            except Exception:
                pass

            if download:
                download.save_as(file_path)
                print(f"[SIMIT] PDF descargado via download event: {file_path}")
                return file_path

            # Intentar 3: nueva pestana
            try:
                new_page = context.pages[-1] if len(context.pages) > 1 else None
                if new_page:
                    new_page.wait_for_load_state(timeout=15_000)
                    pdf_url = new_page.url
                    import requests
                    r = requests.get(pdf_url, timeout=30)
                    if r.status_code == 200 and len(r.content) > 1000:
                        with open(file_path, "wb") as f:
                            f.write(r.content)
                        new_page.close()
                        print(f"[SIMIT] PDF descargado desde nueva pestanha: {file_path}")
                        return file_path
            except Exception as e:
                print(f"[SIMIT] Fallo captura nueva pestanha: {e}")

            # Intentar 4: URL capturada via on_response
            if captured_url["value"]:
                import requests
                try:
                    r = requests.get(captured_url["value"], timeout=30)
                    if r.status_code == 200 and len(r.content) > 1000:
                        with open(file_path, "wb") as f:
                            f.write(r.content)
                        print(f"[SIMIT] PDF descargado via response intercept: {file_path}")
                        return file_path
                except Exception as e:
                    print(f"[SIMIT] Fallo response intercept: {e}")

            print("[SIMIT] No se pudo descargar el PDF por ningun metodo")
            return None

        except PlaywrightTimeout:
            print("[SIMIT] Timeout descargando PDF")
            return None
        except Exception as e:
            print(f"[SIMIT] Error descargando PDF: {e}")
            return None
        finally:
            page.close()
            browser.close()
            p.stop()

    def classify(self, result: dict) -> str:
        total = result.get("total_comparendos", 0) + result.get("total_multas", 0) + result.get("total_acuerdos", 0)
        if total == 0:
            return "normal"
        elif total <= 2:
            return "atencion"
        else:
            return "peligroso"

    def close(self):
        pass


if __name__ == "__main__":
    import sys
    plate = sys.argv[1] if len(sys.argv) > 1 else "ABC123"
    scraper = SIMITScraper()
    result = scraper.consult(plate)
    nivel = scraper.classify(result)
    print(f"\n[SIMIT] Placa: {plate}")
    print(f"[SIMIT] Nivel: {nivel}")
    print(f"[SIMIT] Comparendos: {result.get('total_comparendos', 0)}")
    print(f"[SIMIT] Acuerdos de pago: {result.get('total_acuerdos', 0)}")
    print(f"[SIMIT] Total pendiente: ${result.get('total_pendiente', 0):,}")
    for c in result.get("comparendos", []):
        print(f"  C - {c}")
    for a in result.get("acuerdos", []):
        print(f"  A - {a}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
    scraper.close()
