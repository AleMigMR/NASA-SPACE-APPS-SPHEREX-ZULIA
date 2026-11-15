"""
Validación científica de los objetivos de referencia del reto con datos reales de SPHEREx.

Para cada objetivo (Barnard, Eps Indi B, WISE 0855, RW Aur, R Dra):
  1. Propaga su astrometría (Gaia DR3 / literatura) a la fecha de cada exposición L2b.
  2. Mide fotometría ePSF forzada y el desplazamiento entre la posición medida y la predicha.
  3. Resume épocas, detecciones, saturación, candidatos verificados y la curva de luz por canal.
     En estrellas saturadas mide la posición con el centroide del núcleo saturado y compara el
     desplazamiento medido entre visitas con el predicho por el movimiento propio.
  4. Resume el espectro de 102 canales del cubo DR1 (saturación, contaminación, profundidad de bandas).

Uso (desde la raíz del repositorio, con IRSA accesible):
    python tools/validate_targets.py                 # todos los objetivos
    python tools/validate_targets.py WISE0855 Barnard
    python tools/validate_targets.py --json informe.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SPHEREX_PREWARM", "0")
import spherex_engine as se  # noqa: E402


def summarize_target(tid: str, max_per_epoch: int = 5) -> dict:
    t = se._TARGETS_BY_ID[tid]
    t0 = time.time()
    cube = se.build_sky_cube_and_spectrum(
        t["ra"], t["dec"], t["recommended_bands"], size_deg=t["recommended_fov"], max_per_epoch=max_per_epoch,
        release="all", gap_days=45.0, force_reproject=True, target_id=tid,
    )
    out: dict = {"id": tid, "name": t["name"], "elapsed_s": round(time.time() - t0, 1)}
    if "error" in cube:
        out["error"] = cube["error"]
        return out
    phot = cube.get("photometry", [])
    det = [p for p in phot if p["quality"] in ("good", "warning")]
    offs = [p["offset_arcsec"] for p in det if p.get("offset_arcsec") is not None]
    out.update({
        "data_mode": cube["data_mode"],
        "irsa_matching_exposures": cube.get("total_matching_irsa"),
        "epochs": [{"date": e["date"], "n_exp": e["n_exp"], "lam_um": [e.get("lam_min_um"), e.get("lam_max_um")],
                    "detections": e.get("n_target_detections"), "snr_median": e.get("target_snr_median")} for e in cube["epochs"]],
        "expected_motion": (cube.get("target") or {}).get("expected_motion"),
        "measured_motion": (cube.get("target") or {}).get("measured_motion"),
        "n_positions_saturated_core": sum(1 for p in phot if p.get("astrometry_method") == "saturated_core"),
        "median_offset_saturated_core_arcsec": (round(float(np.median([p["offset_arcsec"] for p in phot if p.get("astrometry_method") == "saturated_core"])), 2)
                                                if any(p.get("astrometry_method") == "saturated_core" for p in phot) else None),
        "n_measurements": len(phot),
        "n_detected": len(det),
        "n_saturated": sum(1 for p in phot if p["quality"] == "saturated"),
        "median_offset_measured_minus_predicted_arcsec": round(float(np.median(offs)), 2) if offs else None,
        "max_offset_arcsec": round(float(np.max(offs)), 2) if offs else None,
        "best_detection": max(det, key=lambda p: p["snr"]) if det else None,
        "light_curve_strongest_change": (cube.get("light_curve") or {}).get("strongest_change"),
        "candidates": [{"rank": c["rank"], "verification": c.get("verification"), "label": c["label_es"],
                        "psf_shift_arcsec": c.get("psf_shift_arcsec"), "match": (c.get("catalog_match") or {}).get("id")}
                       for c in cube.get("candidates", [])],
        "notes": [n["es"] for n in cube.get("notes", [])],
    })
    mid = 0.5 * (se.DR1_MJD_RANGE[0] + se.DR1_MJD_RANGE[1])
    ra_d, de_d = se.propagate_astrometry(t["astrometry"], mid)
    try:
        spec = se.dr1_point_spectrum(ra_d, de_d, t.get("object_kind", "generic"))
        out["dr1"] = {
            "n_saturated_channels": spec["n_saturated"],
            "contamination_warning": spec["contamination_warning"],
            "significant_neighbors": [n for n in (spec.get("neighbors") or []) if n.get("significant")],
            "band_depths": [(b["id"], b["tau"], b["tau_err"], b["significant"]) for b in spec["band_depths"]],
        }
    except Exception as exc:  # pragma: no cover - depende de la red
        out["dr1"] = {"error": str(exc)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*", default=["Barnard", "EpsIndiB", "WISE0855", "RW_Aur", "R_Dra"])
    ap.add_argument("--max-per-epoch", type=int, default=5)
    ap.add_argument("--json", help="Guardar el informe completo en este archivo JSON")
    args = ap.parse_args()
    report = []
    for tid in args.targets:
        print(f"\n=== {tid} ===", flush=True)
        res = summarize_target(tid, args.max_per_epoch)
        report.append(res)
        print(json.dumps(res, ensure_ascii=False, indent=1, default=float))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1, default=float)
        print(f"\nInforme guardado en {args.json}")


if __name__ == "__main__":
    main()
