"""
Regenera las listas oficiales de exposiciones L2b de los objetivos del reto (respaldo para cuando IRSA no responde).

Para cada objetivo consulta IRSA SIA (colecciones spherex_dr1, spherex_dr1_deep, spherex_qr3 y spherex_qr3_deep,
el método de los tutoriales oficiales) en su posición de 2026.0 y guarda la respuesta en
data/spherex_exposure_index/<ID>.json con la fecha de la consulta. Solo contiene metadatos (nombre de cada
exposición, ruta, versión, banda y fecha); las imágenes FITS se siguen leyendo en vivo desde AWS S3.

Uso (desde la raíz del repositorio, con IRSA accesible):
    python tools/refresh_exposure_index.py                 # los cinco objetivos
    python tools/refresh_exposure_index.py Barnard WISE0855
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SPHEREX_PREWARM", "0")
import spherex_engine as se  # noqa: E402

COLUMNS = ["obs_id", "uri", "release", "band", "t_min", "exptime"]


def write_index(tid: str, rows: list, date_utc: str) -> str:
    t = se._TARGETS_BY_ID[tid]
    rows = sorted(rows, key=lambda r: r["t_min"])
    head = {
        "target_id": tid, "name": t["name"], "ra": round(t["ra"], 6), "dec": round(t["dec"], 6),
        "query": {"service": "IRSA SIA v2", "url": se.SIA_URL, "pos": f"CIRCLE {t['ra']:.6f} {t['dec']:.6f} 0.0005",
                  "collections": list(se.SIA_COLLECTIONS), "date_utc": date_utc},
        "note_es": "Respuesta real de IRSA SIA (lista de exposiciones L2b que cubren el objetivo). SkyChrono la usa solo si IRSA TAP y SIA no responden; las imágenes se leen en vivo desde AWS S3.",
        "note_en": "Real IRSA SIA response (list of L2b exposures covering the target). SkyChrono uses it only if IRSA TAP and SIA do not respond; the images are read live from AWS S3.",
        "columns": COLUMNS,
    }
    data_rows = [[r["obs_id"], r["uri"], r.get("release"), r["band"], round(float(r["t_min"]), 6), float(r.get("exptime") or se.EXPTIME_S)]
                 for r in rows]
    os.makedirs(se.SNAPSHOT_DIR, exist_ok=True)
    path = os.path.join(se.SNAPSHOT_DIR, f"{tid}.json")
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(json.dumps(head, ensure_ascii=False, indent=1)[:-2])
        f.write(',\n "rows": [\n' + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in data_rows) + "\n ]\n}\n")
    with open(path, "r", encoding="utf-8") as f:
        json.load(f)  # validación
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", default=["Barnard", "EpsIndiB", "WISE0855", "RW_Aur", "R_Dra"])
    ap.add_argument("--retries", type=int, default=3, help="Intentos por objetivo si IRSA no responde (90 s entre intentos)")
    args = ap.parse_args()
    for tid in args.targets:
        t = se._TARGETS_BY_ID[tid]
        for attempt in range(1, args.retries + 1):
            rows = se._query_sia_exposures(t["ra"], t["dec"])
            if rows:
                path = write_index(tid, rows, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                print(f"{tid}: {len(rows)} exposiciones → {os.path.relpath(path)}", flush=True)
                break
            print(f"{tid}: IRSA SIA no respondió (intento {attempt}/{args.retries})", flush=True)
            if attempt < args.retries:
                time.sleep(90)


if __name__ == "__main__":
    main()
