import os
import re
import time
import hashlib
import json
import threading
from typing import Optional

import requests

from pdf_generator import generate_pdf

QXCAPTCHA_URL = "https://qxcaptcha.fcm.org.co"
CONSULTA_API = "https://consultasimit.fcm.org.co/simit/microservices/estado-cuenta-simit/estadocuenta/consulta"

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


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _solve_pow(question: str, time_val: int, difficulty: int = 1) -> list:
    results = []
    nonce = 1
    for _ in range(difficulty):
        while True:
            nonce += 1
            v = {"question": question, "time": time_val, "nonce": nonce}
            h = hashlib.sha256(json.dumps(v, separators=(",", ":")).encode()).hexdigest()
            if h.startswith("0000") and _is_prime(nonce):
                results.append(v)
                break
            if nonce % 500 == 0:
                time.sleep(0)
    return results


class SIMITScraper:
    def __init__(self):
        pass

    def _parse_api_response(self, data: dict, plate: str) -> dict:
        multas = data.get("multas", [])
        result = {
            "placa": plate,
            "comparendos": [],
            "total_comparendos": 0,
            "total_multas": 0,
            "acuerdos": [],
            "total_acuerdos": 0,
            "total_pendiente": 0,
        }

        for m in multas:
            infs = m.get("infracciones", [])
            codigo = infs[0].get("codigoInfraccion", "") if infs else ""
            desc = infs[0].get("descripcionInfraccion", "") if infs else ""

            if codigo and desc:
                infraccion_completa = f"{codigo} {desc}"
            elif codigo:
                ck = codigo.replace(".", "").strip()[:3]
                infraccion_completa = f"{codigo} {CODIGOS_INFRACCION.get(ck, '')}"
            else:
                infraccion_completa = ""

            fecha = (m.get("fechaComparendo") or "").strip()[:10]

            entry = {
                "tipo": "Comparendo" if m.get("comparendo", True) else "Multa",
                "numero": m.get("numeroComparendo", "") or "",
                "infraccion": infraccion_completa,
                "codigo_infraccion": codigo,
                "fecha": fecha,
                "valor": f"${m.get('valorPagar', 0):,.0f}" if m.get('valorPagar') is not None else "",
                "estado": m.get("estadoComparendo", "") or m.get("estadoCartera", "") or "",
                "secretaria": m.get("organismoTransito", "") or "",
            }
            result["comparendos"].append(entry)

        result["total_comparendos"] = len([m for m in multas if m.get("comparendo", True)])
        result["total_multas"] = len([m for m in multas if not m.get("comparendo", True)])
        result["total_pendiente"] = sum((m.get("valorPagar") or 0) for m in multas)

        return result

    def consult(self, plate: str) -> dict:
        plate = plate.upper().strip()
        print(f"[SIMIT] Consultando placa: {plate}")

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

        try:
            session.get(f"{QXCAPTCHA_URL}/captcha.js",
                        headers={"Referer": "https://www.fcm.org.co/"}, timeout=15)

            resp = session.post(f"{QXCAPTCHA_URL}/api.php",
                                data={"endpoint": "question"},
                                headers={"Referer": "https://www.fcm.org.co/"}, timeout=15)
            resp.raise_for_status()
            q_data = resp.json()
            question = q_data["data"]["question"]
            time_val = int(time.time())

            cap_results = _solve_pow(question, time_val, difficulty=1)

            body = {
                "filtro": plate,
                "reCaptchaDTO": {
                    "response": json.dumps(cap_results, separators=(",", ":")),
                    "consumidor": "1",
                }
            }

            api_resp = requests.post(
                CONSULTA_API,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": "https://www.fcm.org.co",
                    "Referer": "https://www.fcm.org.co/",
                },
                timeout=120
            )

            if api_resp.status_code != 200:
                return {"error": f"API respondió {api_resp.status_code}", "placa": plate}

            api_data = api_resp.json()
            if not api_data.get("multas"):
                print(f"[SIMIT] Sin registros para {plate}")
                return {
                    "placa": plate,
                    "comparendos": [],
                    "total_comparendos": 0,
                    "total_multas": 0,
                    "acuerdos": [],
                    "total_acuerdos": 0,
                    "total_pendiente": 0,
                }

            return self._parse_api_response(api_data, plate)

        except requests.RequestException as e:
            return {"error": str(e), "placa": plate}
        except Exception as e:
            return {"error": str(e), "placa": plate}

    def download_pdf(self, plate: str, save_path: str = None, result: dict = None) -> Optional[str]:
        plate = plate.upper().strip()
        data = result if result else {"placa": plate, "comparendos": [], "total_comparendos": 0, "total_multas": 0, "acuerdos": [], "total_acuerdos": 0, "total_pendiente": 0}
        return generate_pdf(plate, data, save_path=save_path)



    def classify(self, result: dict) -> str:
        total = result.get("total_comparendos", 0) + result.get("total_multas", 0) + result.get("total_acuerdos", 0)
        if total == 0:
            return "normal"
        elif total <= 2:
            return "atencion"
        else:
            return "peligroso"

    def classify_label(self, result: dict) -> str:
        total = result.get("total_comparendos", 0) + result.get("total_multas", 0) + result.get("total_acuerdos", 0)
        if total == 0:
            return "SIN REGISTROS"
        elif total <= 2:
            return "CON REGISTROS"
        else:
            return "REGISTROS M\u00daLTIPLES"

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
    print(f"[SIMIT] Multas: {result.get('total_multas', 0)}")
    print(f"[SIMIT] Acuerdos de pago: {result.get('total_acuerdos', 0)}")
    print(f"[SIMIT] Total pendiente: ${result.get('total_pendiente', 0):,}")
    for c in result.get("comparendos", []):
        print(f"  - {c}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
