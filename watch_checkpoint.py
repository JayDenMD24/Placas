import json
import os
import shutil
import time

import gdown


# === CONFIGURACION ===
# Copia el FOLDER_ID de la carpeta compartida en Google Drive
# La URL se ve asi: https://drive.google.com/drive/folders/ABC123XXX
# El FOLDER_ID es la parte despues de "folders/"
DRIVE_FOLDER_ID = "1Vaqi9Mc0zZCc_0X4JpX4EWP_l1m_eK6V"

# Cada cuantos segundos revisar Drive
POLL_INTERVAL = 120

# Donde guardar la copia local de los checkpoints
CACHE_DIR = os.path.join(os.path.dirname(__file__), "drive_cache")

# Donde copiar best.pt cuando se actualice
MODEL_DST = os.path.join(os.path.dirname(__file__), "models", "plate_detector.pt")
# =====================


def read_progress():
    path = os.path.join(CACHE_DIR, "progress.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"epoch": 0}


def sync():
    os.makedirs(CACHE_DIR, exist_ok=True)
    # Borrar progress.json local para forzar re-descarga
    prog_local = os.path.join(CACHE_DIR, "progress.json")
    if os.path.exists(prog_local):
        os.remove(prog_local)
    gdown.download_folder(id=DRIVE_FOLDER_ID, output=CACHE_DIR, quiet=True)


def main():
    if not DRIVE_FOLDER_ID:
        print("=" * 60)
        print("  ERROR: DRIVE_FOLDER_ID vacio.")
        print("  1. Abre: https://drive.google.com/drive/folders/")
        print(" 2. Busca la carpeta 'alpr_colombia_checkpoints'")
        print(" 3. Copia el ID de la URL (despues de 'folders/')")
        print(" 4. PEGALO en DRIVE_FOLDER_ID en watch_checkpoint.py")
        print(" 5. Asegurate que la carpeta tenga permiso:")
        print("    'Cualquier persona con el enlace puede ver'")
        print("=" * 60)
        return

    print(f"[CHECKPOINT] Monitoreando: carpeta {DRIVE_FOLDER_ID}")
    print(f"[CHECKPOINT] Poll cada {POLL_INTERVAL}s")
    print(f"[CHECKPOINT] Modelo -> {MODEL_DST}")
    print()

    sync()
    progress = read_progress()
    last_epoch = progress.get("epoch", 0)
    print(f"[CHECKPOINT] Epoch inicial: {last_epoch}")

    if last_epoch > 0 or not os.path.exists(MODEL_DST):
        best_src = os.path.join(CACHE_DIR, "best.pt")
        if os.path.exists(best_src):
            os.makedirs(os.path.dirname(MODEL_DST), exist_ok=True)
            shutil.copy2(best_src, MODEL_DST)
            print(f"[CHECKPOINT] Modelo copiado: {MODEL_DST}")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            sync()
            progress = read_progress()
            epoch = progress.get("epoch", 0)
            if epoch > last_epoch or not os.path.exists(MODEL_DST):
                last_epoch = max(last_epoch, epoch)
                best_src = os.path.join(CACHE_DIR, "best.pt")
                if os.path.exists(best_src):
                    os.makedirs(os.path.dirname(MODEL_DST), exist_ok=True)
                    shutil.copy2(best_src, MODEL_DST)
                    info = (
                        f"mAP50: {progress.get('map50', '?')}  |  "
                        f"mAP50-95: {progress.get('map50_95', '?')}  |  "
                        f"Precision: {progress.get('precision', '?')}  |  "
                        f"Recall: {progress.get('recall', '?')}"
                    )
                    print(
                        f"[CHECKPOINT] Epoca {epoch} detectada -> modelo actualizado."
                    )
                    print(f"             {info}")
            elif epoch == 0 and last_epoch == 0:
                print("[CHECKPOINT] Esperando primera epoca...")
        except Exception as e:
            print(f"[CHECKPOINT] Error: {e}")


if __name__ == "__main__":
    main()
