"""
Motor astrofísico y de datos de SPHEREx SkyChrono (NASA Space Apps Challenge 2026).

Principios de diseño (revisión de rigor científico, nov. 2026):
- Todo dato científico mostrado proviene de productos oficiales de SPHEREx (IRSA / AWS S3) o de
  catálogos oficiales (Gaia DR3, AllWISE, SIMBAD, JPL Horizons). Cuando un dato no existe o no es
  fiable (saturación, baja S/N, sin paralaje), se devuelve `None` y se explica por qué: nunca se
  rellena con valores inventados.
- Las posiciones de los objetivos de alto movimiento propio se propagan a la fecha de CADA
  exposición (astropy `apply_space_motion`) antes de medir su flujo.
- La fotometría usa el método del pipeline oficial (Suplemento Explicativo SPHEREx v2.1, sec. 3.3):
  ajuste forzado con la ePSF oficial de cada exposición, pesos 1/VARIANCE, máscara oficial de
  píxeles, ángulo sólido del píxel derivado del WCS con distorsión SIP y +3 % de error sistemático.
- La longitud de onda de cada medición sale de la tabla WCS-WAVE de la exposición en la posición
  del detector donde cayó la fuente (verificado contra los archivos CWAVE oficiales: error ≤ 5 % del
  ancho de banda).

Referencia principal: SPHEREx Explanatory Supplement v2.1 (2026-11-10),
https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import requests
from astropy import units as u
from astropy.coordinates import Distance, SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import FITSFixedWarning, WCS
from PIL import Image
from reproject import reproject_interp

warnings.filterwarnings("ignore", category=FITSFixedWarning)
warnings.filterwarnings("ignore", message=".*ERFA function.*")

# ---------------------------------------------------------------------------
# Servicios oficiales
# ---------------------------------------------------------------------------
TAP_URL = "https://irsa.ipac.caltech.edu/TAP/sync"
S3_BASE = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/"
IBE_BASE = "https://irsa.ipac.caltech.edu/"
# VizieR (ASU-TSV) con espejo de respaldo en CfA/Harvard
VIZIER_ASU_MIRRORS = [
    "https://vizier.cds.unistra.fr/viz-bin/asu-tsv",
    "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv",
]
# SIMBAD TAP con espejo de respaldo en CfA/Harvard
SIMBAD_TAP_MIRRORS = [
    "https://simbad.cds.unistra.fr/simbad/sim-tap/sync",
    "https://simbad.harvard.edu/simbad/sim-tap/sync",
]
TAP_TIMEOUT_S = float(os.environ.get("SPHEREX_TAP_TIMEOUT", "30"))
SIA_TIMEOUT_S = float(os.environ.get("SPHEREX_SIA_TIMEOUT", "60"))

PIX_SCALE_NATIVE = 6.15  # arcsec / píxel nativo (Suplemento, Tabla 2)
SOLID_ANGLE_SR = (PIX_SCALE_NATIVE / 206264.806247) ** 2  # ≈ 8.890e-10 sr (nominal; el real sale del WCS)
EXPTIME_S = 113.58  # s (Suplemento, Tabla 2)
SYSTEMATIC_FRAC = 0.03  # Suplemento sec. 3.3, Nota 1: 3 % sistemático en cuadratura
AB_ZP_UJY = 23.9  # m_AB = 23.9 − 2.5 log10(F/µJy)   (3631 Jy ↔ m_AB = 0)
MPC_OBS_CODE_SPHEREX = "288"  # Lista oficial de códigos de observatorio del MPC: "288 SPHEREx"

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
for _sub in ("tap", "cutouts", "catalogs", "cubes", "hips", "dr1spec"):
    os.makedirs(os.path.join(CACHE_DIR, _sub), exist_ok=True)


def _load_dotenv() -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#") and "=" in s:
                        k, v = s.split("=", 1)
                        v = v.strip()
                        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                            v = v[1:-1]  # GEMINI_API_KEY="..." también es válido
                        os.environ.setdefault(k.strip(), v)
        except Exception:
            pass


_load_dotenv()

# ---------------------------------------------------------------------------
# Bits oficiales de la extensión FLAGS (Suplemento v2.1, Tabla 16; coinciden con las claves
# MSKNnnnn de las cabeceras de los archivos L2b DR1). Los bits 3, 5, 8, 13, 16 y 18 no se usan.
# ---------------------------------------------------------------------------
FLAG_DEFINITIONS = [
    {"bit": 0, "name": "TRANSIENT", "label": "Transitorio detectado en la rampa SUR (rayo cósmico, satélite o inicio de blooming)", "label_en": "Transient detected during SUR (cosmic ray, satellite or bloom onset)", "color": "#ff4d6d"},
    {"bit": 1, "name": "OVERFLOW", "label": "Umbral de desbordamiento SUR (~mitad del pozo lleno): posible saturación", "label_en": "SUR overflow threshold (~half full well): possible saturation", "color": "#ff758f"},
    {"bit": 2, "name": "SUR_ERROR", "label": "Error de procesamiento a bordo (o transitorio/desborde temprano)", "label_en": "Onboard processing error (or early transient/overflow)", "color": "#ff8fa3"},
    {"bit": 6, "name": "NONFUNC", "label": "Píxel permanentemente inutilizable", "label_en": "Permanently unusable pixel", "color": "#7209b7"},
    {"bit": 7, "name": "DICHROIC", "label": "Baja eficiencia por el divisor dicroico (bandas 3–4)", "label_en": "Low efficiency due to the dichroic (bands 3–4)", "color": "#560bad"},
    {"bit": 9, "name": "MISSING_DATA", "label": "Datos perdidos a bordo / en la bajada", "label_en": "Onboard data lost", "color": "#480ca8"},
    {"bit": 10, "name": "HOT", "label": "Píxel caliente en esta exposición", "label_en": "Hot pixel in this exposure", "color": "#f72585"},
    {"bit": 11, "name": "COLD", "label": "Señal anómalamente baja en esta exposición", "label_en": "Anomalously low signal in this exposure", "color": "#4cc9f0"},
    {"bit": 12, "name": "FULLSAMPLE", "label": "Historial completo de muestras disponible (informativo)", "label_en": "Full sample history available (informational)", "color": "#90e0ef"},
    {"bit": 14, "name": "PHANMISS", "label": "Corrección de píxeles fantasma no aplicada", "label_en": "Phantom correction was not applied", "color": "#b8c0ff"},
    {"bit": 15, "name": "NONLINEAR", "label": "Corrección de no linealidad no fiable", "label_en": "Nonlinearity correction not reliable", "color": "#f8961e"},
    {"bit": 17, "name": "PERSIST", "label": "Carga persistente por encima del umbral", "label_en": "Persistent charge above threshold", "color": "#f9c74f"},
    {"bit": 19, "name": "OUTLIER", "label": "Marcado por el módulo de detección de outliers", "label_en": "Flagged by Detect Outlier Pixels", "color": "#f9844a"},
    {"bit": 20, "name": "CROSSTALK", "label": "Afectado por diafonía (crosstalk) eléctrica", "label_en": "Affected by electrical crosstalk", "color": "#ff9e00"},
    {"bit": 21, "name": "SOURCE", "label": "Píxel asociado a una fuente catalogada (informativo, NO se enmascara)", "label_en": "Pixel mapped to a known source (informational, NOT masked)", "color": "#00f5d4"},
    {"bit": 22, "name": "GHOST", "label": "Fantasma óptico de una fuente brillante en la exposición", "label_en": "Optical ghost from a bright source in the exposure", "color": "#b5179e"},
    {"bit": 23, "name": "GHOST_FPA", "label": "Fantasma de una fuente en otro detector (sin uso en DR1)", "label_en": "Ghost from a source on another detector (unused in DR1)", "color": "#9d4edd"},
    {"bit": 24, "name": "GHOST_EXT", "label": "Fantasma de una fuente fuera del campo", "label_en": "Ghost from a source outside the field of view", "color": "#c77dff"},
    {"bit": 25, "name": "STREAK", "label": "Traza (satélite / objeto en órbita terrestre)", "label_en": "Streak (Earth-orbiting object)", "color": "#ff007f"},
    {"bit": 26, "name": "BLOOM", "label": "Blooming: carga desbordada de una fuente brillante saturada", "label_en": "Blooming: charge spill from a bright saturated source", "color": "#ff5400"},
    {"bit": 27, "name": "SNOWBALL", "label": "Evento 'snowball' (rayo cósmico muy energético)", "label_en": "Snowball event (very energetic cosmic ray)", "color": "#e0aaff"},
    {"bit": 28, "name": "HALO", "label": "Halo de un transitorio cercano", "label_en": "Halo of a nearby transient", "color": "#48cae4"},
    {"bit": 29, "name": "SATELLITE_HALO", "label": "Halo de una traza de satélite", "label_en": "Halo of a satellite streak", "color": "#ff6b6b"},
]
_FLAG_BIT = {f["name"]: f["bit"] for f in FLAG_DEFINITIONS}


def _mask_of(names: Sequence[str]) -> int:
    return int(sum(1 << _FLAG_BIT[n] for n in names))


# Píxeles rechazados al construir imágenes (misma lista que usa el equipo SPHEREx para el cubo DR1,
# Suplemento sec. 2.5). OVERFLOW, SOURCE y OUTLIER se conservan.
DISPLAY_REJECT_NAMES = (
    "TRANSIENT", "SUR_ERROR", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD", "PHANMISS",
    "NONLINEAR", "PERSIST", "CROSSTALK", "STREAK", "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO",
)
DISPLAY_REJECT_MASK = _mask_of(DISPLAY_REJECT_NAMES)
BAD_MASK = DISPLAY_REJECT_MASK  # alias histórico

# Máscara oficial para el ajuste fotométrico (Suplemento sec. 3.3, "Flags for masking pixels for photometry")
PHOT_MASK_NAMES = (
    "SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "NONLINEAR", "PERSIST",
    "BLOOM", "SNOWBALL", "HALO", "SATELLITE_HALO",
)
PHOT_MASK = _mask_of(PHOT_MASK_NAMES)

# Aviso CONTAINS_BAD_PIXEL del pipeline L3 (radio 2.5 píxeles nativos, Suplemento sec. 3.3)
PHOT_WARN_NAMES = (
    "TRANSIENT", "OVERFLOW", "SUR_ERROR", "NONFUNC", "DICHROIC", "MISSING_DATA", "HOT", "COLD",
    "NONLINEAR", "CROSSTALK", "GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "PERSIST", "BLOOM",
    "SNOWBALL", "HALO", "SATELLITE_HALO",
)
PHOT_WARN_MASK = _mask_of(PHOT_WARN_NAMES)
SATURATION_MASK = _mask_of(("OVERFLOW", "NONLINEAR", "BLOOM"))


def flag_names(bits: int) -> List[str]:
    return [f["name"] for f in FLAG_DEFINITIONS if (int(bits) >> f["bit"]) & 1]


# DOIs oficiales (verificados en doi.org, nov. 2026)
IRSA_DOIS = {
    "DR1_SPECTRAL_IMAGES": "10.26131/IRSA678",
    "DR1_ALLSKY_CUBE": "10.26131/IRSA679",
    "QR3_SPECTRAL_IMAGES": "10.26131/IRSA662",
    "SPLICES": "10.26131/IRSA554",
}

# Bandas oficiales (Suplemento v2.1, Tabla 2): rango y resolución de diseño
DETECTOR_INFO = {
    "D1": {"name": "SPHEREx-D1", "lmin": 0.744, "lmax": 1.116, "R": 39, "channel": "SWIR", "molecules": "Continuo estelar; He I 1.083 µm (luminiscencia atmosférica)"},
    "D2": {"name": "SPHEREx-D2", "lmin": 1.099, "lmax": 1.651, "R": 41, "channel": "SWIR", "molecules": "H₂O 1.4 µm; CH₄ 1.6 µm (atmósferas frías)"},
    "D3": {"name": "SPHEREx-D3", "lmin": 1.636, "lmax": 2.421, "R": 41, "channel": "SWIR", "molecules": "H₂O 1.9 µm; CH₄ 2.2 µm; CO 2.3 µm"},
    "D4": {"name": "SPHEREx-D4", "lmin": 2.423, "lmax": 3.822, "R": 35, "channel": "MWIR", "molecules": "H₂O 2.7–3.1 µm (gas o hielo); CH₄ 3.3 µm; PAH 3.29 µm"},
    "D5": {"name": "SPHEREx-D5", "lmin": 3.809, "lmax": 4.420, "R": 112, "channel": "MWIR", "molecules": "Ventana de 4 µm; CO₂ 4.27 µm (gas o hielo)"},
    "D6": {"name": "SPHEREx-D6", "lmin": 4.412, "lmax": 5.002, "R": 128, "channel": "MWIR", "molecules": "CO 4.67 µm (gas o hielo); pico de enanas Y"},
}

# Época de visualización: posición a la que se centran los objetivos de alto movimiento propio.
# DR1 cubre MJD 60789.75–61174.49 (2025-04-24 → 2026-05-14) y QR3 continúa desde 2026-05-16.
DISPLAY_EPOCH_JYEAR = 2026.0
DR1_MJD_RANGE = (60789.75076, 61174.49276)  # properties oficiales del cubo DR1 (t_min, t_max)


# ---------------------------------------------------------------------------
# Objetivos oficiales del reto (astrometría verificada en SIMBAD/Gaia, nov. 2026)
# `astrometry` = posición a la época `epoch_jyear` + movimiento propio + paralaje (+ VR).
# ---------------------------------------------------------------------------
CHALLENGE_TARGETS: List[Dict[str, Any]] = [
    {
        "id": "ObservableUniverse",
        "name": "🌌 Universo Observable",
        "subtitle": "Vista 360° del cubo oficial SPHEREx DR1",
        "subtitle_en": "360° view of the official SPHEREx DR1 cube",
        "category": "Panorama Global 360°",
        "is_allsky": True,
        "ra": 133.75976,
        "dec": -7.24219,
        "pm_ra": 0.0,
        "pm_dec": 0.0,
        "recommended_bands": ["D6"],
        "recommended_fov": 0.10,
        "science_note": (
            "Mosaico de cielo completo construido por el equipo SPHEREx con >1.2 millones de imágenes DR1 "
            "(102 canales, 0.75–5.0 µm, píxeles de 12.9″). Es una co-adición estática: no contiene información "
            "temporal. Haz doble clic en cualquier punto para abrir las exposiciones multi-época L2b de esa zona."
        ),
        "science_note_en": (
            "All-sky mosaic built by the SPHEREx team from >1.2 million DR1 images (102 channels, 0.75–5.0 µm, "
            "12.9″ pixels). It is a static co-add with no time information. Double-click anywhere to open the "
            "multi-epoch L2b exposures of that area."
        ),
    },
    {
        "id": "WISE0855",
        "name": "WISE 0855−0714",
        "subtitle": "Enana marrón Y más fría conocida (~250–285 K) a 2.28 pc, 8.15″/año",
        "subtitle_en": "Coldest known Y brown dwarf (~250–285 K) at 2.28 pc, 8.15″/yr",
        "category": "Enana Marrón (Alto Mov. Propio)",
        "ra_prompt": "08h55m10.831s",
        "dec_prompt": "-07d14m42.53s",
        "prompt_epoch_note": "Coordenadas del enunciado NASA = posición AllWISE (época ≈ 2010.6). En 2026 el objeto está ~2.1′ al oeste.",
        "prompt_epoch_note_en": "NASA prompt coordinates = AllWISE position (epoch ≈ 2010.6). By 2026 the object is ~2.1′ to the west.",
        "astrometry": {
            "ra_deg": 133.81890825, "dec_deg": -7.247048, "epoch_jyear": 2000.0,
            "pmra_masyr": -8123.7, "pmdec_masyr": 673.2, "parallax_mas": 439.0, "parallax_err_mas": 2.4,
            "rv_kms": None, "ref": "Kirkpatrick et al. 2021, ApJS 253, 7 (vía SIMBAD)",
        },
        "distance_pc": 2.278, "distance_ref": "π = 439.0 ± 2.4 mas (Kirkpatrick et al. 2021)",
        "sptype": "Y (Y2–≥Y4)", "sptype_ref": "Leggett et al. 2015 (Y2, SIMBAD); Kirkpatrick et al. 2021 (≥Y4)",
        "teff_k_lit": "≈250–285 K", "teff_ref": "Luhman 2014; Luhman et al. 2024 (JWST/NIRSpec)",
        "object_kind": "brown_dwarf",
        "recommended_bands": ["D6"],
        "recommended_fov": 0.10,
        "science_note": (
            "Enana marrón de tipo Y, la más fría conocida. Prácticamente invisible por debajo de ~3.5 µm por la "
            "absorción de CH₄ y H₂O gaseosos de su atmósfera; emite casi toda su energía en la ventana de 4–5 µm "
            "(detectores D5–D6, W2 = 13.7 mag → ~0.55 mJy). Es débil para SPHEREx: espera S/N bajo por exposición. "
            "Se mueve 8.15″/año (1.3 píxeles nativos por año). Su posición se propaga a la fecha de cada exposición."
        ),
        "science_note_en": (
            "Y-type brown dwarf, the coldest known. Nearly invisible below ~3.5 µm because of gaseous CH₄ and H₂O "
            "absorption in its atmosphere; it emits most of its energy in the 4–5 µm window (D5–D6, W2 = 13.7 mag → "
            "~0.55 mJy). It is faint for SPHEREx: expect low per-exposure S/N. It moves 8.15″/yr (1.3 native pixels "
            "per year). Its position is propagated to the date of every exposure."
        ),
    },
    {
        "id": "Barnard",
        "name": "Barnard's Star",
        "subtitle": "Estrella de mayor movimiento propio (10.39″/año) a 1.83 pc",
        "subtitle_en": "Highest proper-motion star (10.39″/yr) at 1.83 pc",
        "category": "Estrella Cercana (Alto Mov. Propio)",
        "ra_prompt": "17h57m48.50s",
        "dec_prompt": "+04d41m36.1s",
        "prompt_epoch_note": "Posición J2000 (Gaia DR3 propagada). Entre 2000 y 2026 se desplazó ~4.5′ hacia el norte.",
        "prompt_epoch_note_en": "J2000 position (propagated Gaia DR3). It moved ~4.5′ north between 2000 and 2026.",
        "astrometry": {
            "ra_deg": 269.4520769586187, "dec_deg": 4.693364966576667, "epoch_jyear": 2000.0,
            "pmra_masyr": -801.551, "pmdec_masyr": 10362.394, "parallax_mas": 546.9759, "parallax_err_mas": 0.0401,
            "rv_kms": -110.11, "ref": "Gaia DR3 (Gaia Collaboration 2023), vía SIMBAD",
        },
        "distance_pc": 1.8282, "distance_ref": "π = 546.976 ± 0.040 mas (Gaia DR3)",
        "sptype": "M4V", "sptype_ref": "SIMBAD",
        "teff_k_lit": "≈3200 K", "teff_ref": "Literatura (enana M4V)",
        "object_kind": "star",
        "saturates": True,
        "recommended_bands": ["D1", "D2", "D3"],
        "recommended_fov": 0.12,
        "science_note": (
            "Enana roja M4V a 1.83 pc. Avanza 10.39″/año hacia el norte (~1.7 píxeles nativos por año), así que el "
            "desplazamiento entre las visitas de SPHEREx es visible en modo Blink/Diferencia. Es tan brillante "
            "(J ≈ 5.2) que satura SPHEREx en todas las bandas: su posición es útil, pero su flujo no es fiable."
        ),
        "science_note_en": (
            "M4V red dwarf at 1.83 pc. It moves 10.39″/yr northward (~1.7 native pixels per year), so the shift "
            "between SPHEREx visits is visible in Blink/Difference mode. It is so bright (J ≈ 5.2) that it saturates "
            "SPHEREx in every band: its position is useful, but its flux is not reliable."
        ),
    },
    {
        "id": "EpsIndiB",
        "name": "Epsilon Indi Ba/Bb",
        "subtitle": "Binaria de enanas marrones T1 + T6 a 3.64 pc (4.69″/año)",
        "subtitle_en": "T1 + T6 binary brown dwarf at 3.64 pc (4.69″/yr)",
        "category": "Par de Enanas Marrones",
        "ra_prompt": "22h04m10.60s",
        "dec_prompt": "-56d46m58.2s",
        "prompt_epoch_note": "Posición J2000 (Gaia DR3 propagada). La pareja Ba/Bb (0.7″) no se resuelve con píxeles de 6.15″.",
        "prompt_epoch_note_en": "J2000 position (propagated Gaia DR3). The Ba/Bb pair (0.7″) is unresolved with 6.15″ pixels.",
        "astrometry": {
            "ra_deg": 331.04414658852124, "dec_deg": -56.782844195116105, "epoch_jyear": 2000.0,
            "pmra_masyr": 3981.977, "pmdec_masyr": -2466.832, "parallax_mas": 270.658, "parallax_err_mas": 0.690,
            "rv_kms": None, "ref": "Gaia DR3 (fotocentro de Ba+Bb), vía SIMBAD",
        },
        "distance_pc": 3.6385, "distance_ref": "Distancia del sistema: π(ε Ind A) = 274.843 mas (Gaia DR3)",
        "sptype": "T1 + T6", "sptype_ref": "SIMBAD",
        "teff_k_lit": "Ba ≈1300 K, Bb ≈900 K", "teff_ref": "King et al. 2010",
        "object_kind": "brown_dwarf",
        "recommended_bands": ["D2", "D3", "D5", "D6"],
        "recommended_fov": 0.12,
        "science_note": (
            "Par de enanas marrones de metano (T1 + T6) que orbita la estrella ε Indi A (6.7′ al oeste). Comparten "
            "su movimiento propio (4.69″/año, ~0.8 píxeles/año). Su espectro muestra absorción de CH₄ y H₂O gaseosos "
            "(1.1–1.7 y 3.3 µm) y la ventana brillante de ~4 µm; no es hielo."
        ),
        "science_note_en": (
            "Pair of methane brown dwarfs (T1 + T6) orbiting the star ε Indi A (6.7′ to the west). They share its "
            "proper motion (4.69″/yr, ~0.8 pixels/yr). Their spectrum shows gaseous CH₄ and H₂O absorption "
            "(1.1–1.7 and 3.3 µm) and the bright ~4 µm window; it is not ice."
        ),
    },
    {
        "id": "RW_Aur",
        "name": "RW Aurigae",
        "subtitle": "Binaria joven T Tauri con oscurecimientos por polvo, a ~156 pc",
        "subtitle_en": "Young T Tauri binary with dusty dimming events, at ~156 pc",
        "category": "Estrella Variable Joven (T Tauri)",
        "ra_prompt": "05h07m49.46s",
        "dec_prompt": "+30d24m04.3s",
        "prompt_epoch_note": "Posición de RW Aur A (Gaia DR3, época 2016.0). B está a 1.4″ (no resuelta).",
        "prompt_epoch_note_en": "RW Aur A position (Gaia DR3, epoch 2016.0). B lies 1.4″ away (unresolved).",
        "astrometry": {
            "ra_deg": 76.95608119553, "dec_deg": 30.40120458910, "epoch_jyear": 2016.0,
            "pmra_masyr": 2.641, "pmdec_masyr": -27.398, "parallax_mas": 6.4062, "parallax_err_mas": 0.0441,
            "rv_kms": None, "ref": "Gaia DR3 source 156430822114424576 (RW Aur A; RUWE 1.50)",
        },
        "distance_pc": 156.1, "distance_ref": "π = 6.406 ± 0.044 mas (Gaia DR3, RW Aur A)",
        "sptype": "K1/5e + K5e", "sptype_ref": "SIMBAD",
        "teff_k_lit": None, "teff_ref": None,
        "object_kind": "variable",
        "saturates": True,
        "recommended_bands": ["D2", "D3", "D4", "D5"],
        "recommended_fov": 0.12,
        "science_note": (
            "Sistema binario pre-secuencia principal con un disco perturbado por marea. Desde 2010 sufre "
            "oscurecimientos ópticos profundos por polvo, con variaciones también en el infrarrojo. Es brillante "
            "(K ≈ 7): varios canales de SPHEREx marcan OVERFLOW en su núcleo, así que revisa los avisos de calidad "
            "antes de interpretar su curva de luz."
        ),
        "science_note_en": (
            "Pre-main-sequence binary with a tidally perturbed disk. Since 2010 it has shown deep optical dimming "
            "events caused by dust, with infrared variations as well. It is bright (K ≈ 7): several SPHEREx channels "
            "flag OVERFLOW at its core, so check the quality warnings before interpreting its light curve."
        ),
    },
    {
        "id": "R_Dra",
        "name": "R Draconis",
        "subtitle": "Gigante roja variable tipo Mira (P ≈ 245.6 d)",
        "subtitle_en": "Mira-type pulsating red giant (P ≈ 245.6 d)",
        "category": "Estrella Variable Pulsante (Mira)",
        "ra_prompt": "16h32m40.17s",
        "dec_prompt": "+66d45m18.0s",
        "prompt_epoch_note": "Posición Gaia DR3 (época 2016.0). Movimiento propio despreciable a escala SPHEREx.",
        "prompt_epoch_note_en": "Gaia DR3 position (epoch 2016.0). Proper motion negligible at SPHEREx scale.",
        "astrometry": {
            "ra_deg": 248.16737836729, "dec_deg": 66.75500674547, "epoch_jyear": 2016.0,
            "pmra_masyr": -20.643, "pmdec_masyr": 6.149, "parallax_mas": 1.2509, "parallax_err_mas": 0.0648,
            "rv_kms": None, "ref": "Gaia DR3 source 1648328016354496384 (RUWE 1.30)",
        },
        "distance_pc": 799.0, "distance_ref": "1/π con π = 1.251 ± 0.065 mas (Gaia DR3); paralajes de Miras: usar con cautela",
        "sptype": "M4.5–6e", "sptype_ref": "SIMBAD",
        "teff_k_lit": None, "teff_ref": None,
        "object_kind": "variable",
        "saturates": True,
        "recommended_bands": ["D1", "D2", "D3", "D4"],
        "recommended_fov": 0.12,
        "science_note": (
            "Gigante AGB tipo Mira que pulsa cada ~245.6 días (GCVS) a ~8.6° del Polo Norte Eclíptico, una zona que "
            "SPHEREx visita con frecuencia. Es muy brillante en el infrarrojo y SATURA SPHEREx: en DR1 su núcleo no "
            "tiene píxeles válidos. Su variación puede apreciarse en el Blink, pero sus flujos no son fiables."
        ),
        "science_note_en": (
            "Mira-type AGB giant pulsating every ~245.6 days (GCVS), ~8.6° from the North Ecliptic Pole, an area "
            "SPHEREx revisits often. It is very bright in the infrared and SATURATES SPHEREx: its core has no valid "
            "pixels in DR1. Its variation can be seen in Blink, but its fluxes are not reliable."
        ),
    },
]
_TARGETS_BY_ID = {t["id"]: t for t in CHALLENGE_TARGETS}


def _jyear_to_mjd(jyear: float) -> float:
    return float(Time(jyear, format="jyear").mjd)


def propagate_astrometry(astrom: Dict[str, Any], mjd: float) -> Tuple[float, float]:
    """
    Propaga (RA, Dec) de una astrometría (posición + movimiento propio + paralaje + VR) a la fecha `mjd`
    con `SkyCoord.apply_space_motion` (incluye aceleración de perspectiva). No incluye la paralaje
    anual (≤ 0.55″ para estos objetos, < 0.1 píxel nativo).
    """
    pmra = float(astrom.get("pmra_masyr") or 0.0)
    pmdec = float(astrom.get("pmdec_masyr") or 0.0)
    ra0 = float(astrom["ra_deg"])
    dec0 = float(astrom["dec_deg"])
    if abs(pmra) < 1e-9 and abs(pmdec) < 1e-9:
        return ra0, dec0
    plx = astrom.get("parallax_mas")
    kw: Dict[str, Any] = {}
    if plx is not None and float(plx) > 0.01:
        kw["distance"] = Distance(parallax=float(plx) * u.mas)
        kw["radial_velocity"] = float(astrom.get("rv_kms") or 0.0) * u.km / u.s
    c = SkyCoord(
        ra=ra0 * u.deg, dec=dec0 * u.deg,
        pm_ra_cosdec=pmra * u.mas / u.yr, pm_dec=pmdec * u.mas / u.yr,
        obstime=Time(float(astrom.get("epoch_jyear", 2000.0)), format="jyear"), frame="icrs", **kw,
    )
    n = c.apply_space_motion(new_obstime=Time(float(mjd), format="mjd"))
    return float(n.ra.deg) % 360.0, float(n.dec.deg)


def target_display_position(t: Dict[str, Any]) -> Tuple[float, float]:
    astrom = t.get("astrometry")
    if not astrom:
        return float(t.get("ra", 0.0)), float(t.get("dec", 0.0))
    return propagate_astrometry(astrom, _jyear_to_mjd(DISPLAY_EPOCH_JYEAR))


def _finalize_reference_targets() -> None:
    """Calcula la posición de visualización (época 2026.0) y los campos de compatibilidad."""
    for t in CHALLENGE_TARGETS:
        astrom = t.get("astrometry")
        if not astrom:
            continue
        ra_d, dec_d = target_display_position(t)
        t["ra"] = round(ra_d, 6)
        t["dec"] = round(dec_d, 6)
        t["display_epoch"] = DISPLAY_EPOCH_JYEAR
        t["pm_ra"] = astrom.get("pmra_masyr", 0.0)
        t["pm_dec"] = astrom.get("pmdec_masyr", 0.0)
        t["parallax_mas"] = astrom.get("parallax_mas")
        ra_j, dec_j = propagate_astrometry(astrom, _jyear_to_mjd(2000.0))
        t["ra_j2000"] = round(ra_j, 6)
        t["dec_j2000"] = round(dec_j, 6)


_finalize_reference_targets()


def get_target_astrometry(target_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not target_id:
        return None
    t = _TARGETS_BY_ID.get(target_id)
    return dict(t["astrometry"]) if t and t.get("astrometry") else None


# ---------------------------------------------------------------------------
# Hitos del visor 360° (coordenadas verificadas en SIMBAD / JPL Horizons, nov. 2026).
# `dist_pc` y `teff` solo se dan para estrellas con medidas publicadas; para campos, nebulosas
# y galaxias valen None (no tienen una "temperatura" ni una distancia única que mostrar).
# ---------------------------------------------------------------------------
ALLSKY_LANDMARKS = [
    {"id": "NEP_DEEP", "name": "SPHEREx NEP Deep Field (Polo Norte Eclíptico)", "ra": 270.0000, "dec": 66.5607, "dist_pc": None, "teff": None, "stype": "Campo profundo de SPHEREx (Polo Norte Eclíptico)", "stype_en": "SPHEREx deep field (North Ecliptic Pole)", "pm_ra": 0.0, "pm_dec": 0.0},
    {"id": "SEP_DEEP", "name": "Polo Sur Eclíptico (cerca del campo profundo SEP)", "ra": 90.0000, "dec": -66.5607, "dist_pc": None, "teff": None, "stype": "Polo Sur Eclíptico; el campo profundo SEP está ligeramente desplazado del polo", "stype_en": "South Ecliptic Pole; the SEP deep field is slightly offset from the pole", "pm_ra": 0.0, "pm_dec": 0.0},
    {"id": "POLARIS", "name": "Polaris (α UMi · Polo Norte)", "ra": 37.9546, "dec": 89.2641, "dist_pc": 132.6, "teff": 6015, "stype": "Supergigante cefeida F7Ib", "stype_en": "F7Ib Cepheid supergiant", "pm_ra": 44.48, "pm_dec": -11.85},
    {"id": "SIGMA_OCT", "name": "σ Octantis (Polo Sur Celeste)", "ra": 317.1953, "dec": -88.9565, "dist_pc": 90.1, "teff": 7300, "stype": "Subgigante F0IV (δ Scuti)", "stype_en": "F0IV subgiant (δ Scuti)", "pm_ra": 26.32, "pm_dec": 4.72},
    {"id": "SGR_A", "name": "Sgr A* (Centro Galáctico)", "ra": 266.4168, "dec": -29.0078, "dist_pc": 8178.0, "teff": None, "stype": "Agujero negro supermasivo / centro galáctico (8.18 kpc, GRAVITY 2019)", "stype_en": "Supermassive black hole / Galactic centre (8.18 kpc, GRAVITY 2019)", "pm_ra": -3.16, "pm_dec": -5.59},
    {"id": "PROXIMA", "name": "Proxima Centauri", "ra": 217.4290, "dec": -62.6795, "dist_pc": 1.301, "teff": 3042, "stype": "Enana roja M5.5Ve (estrella más cercana)", "stype_en": "M5.5Ve red dwarf (nearest star)", "pm_ra": -3781.7, "pm_dec": 769.5},
    {"id": "LUHMAN16", "name": "Luhman 16AB (WISE 1049−5319)", "ra": 162.3288, "dec": -53.3195, "dist_pc": 1.996, "teff": 1350, "stype": "Binaria de enanas marrones L7.5 + T0.5", "stype_en": "L7.5 + T0.5 binary brown dwarf", "pm_ra": -2759.0, "pm_dec": 354.0},
    {"id": "WOLF359", "name": "Wolf 359 (CN Leonis)", "ra": 164.1203, "dec": 7.0147, "dist_pc": 2.408, "teff": 2800, "stype": "Enana roja M6.5Ve", "stype_en": "M6.5Ve red dwarf", "pm_ra": -3842.0, "pm_dec": -2725.0},
    {"id": "TRAPPIST1", "name": "TRAPPIST-1 (2MASS J2306−0502)", "ra": 346.6223, "dec": -5.0414, "dist_pc": 12.43, "teff": 2566, "stype": "Enana ultrafría M8V (7 exoplanetas)", "stype_en": "M8V ultracool dwarf (7 exoplanets)", "pm_ra": 930.9, "pm_dec": -479.4},
    {"id": "SIRIUS", "name": "Sirius A/B (α CMa)", "ra": 101.2872, "dec": -16.7161, "dist_pc": 2.637, "teff": 9940, "stype": "Binaria A1V + enana blanca DA2", "stype_en": "A1V + DA2 white dwarf binary", "pm_ra": -546.0, "pm_dec": -1223.1},
    {"id": "VEGA", "name": "Vega (α Lyrae)", "ra": 279.2347, "dec": 38.7837, "dist_pc": 7.68, "teff": 9602, "stype": "Estrella A0Va con disco de escombros", "stype_en": "A0Va star with debris disk", "pm_ra": 200.94, "pm_dec": 286.23},
    {"id": "BETELGEUSE", "name": "Betelgeuse (α Orionis)", "ra": 88.7929, "dec": 7.4071, "dist_pc": 168.0, "teff": 3600, "stype": "Supergigante roja M1–M2 Ia–Iab", "stype_en": "M1–M2 Ia–Iab red supergiant", "pm_ra": 27.54, "pm_dec": 11.30},
    {"id": "M42_ORION", "name": "Nebulosa de Orión (M42)", "ra": 83.8201, "dec": -5.3876, "dist_pc": None, "teff": None, "stype": "Región HII y nube molecular (~400 pc)", "stype_en": "HII region and molecular cloud (~400 pc)", "pm_ra": 0.0, "pm_dec": 0.0},
    {"id": "M31_AND", "name": "Galaxia de Andrómeda (M31)", "ra": 10.6847, "dec": 41.2688, "dist_pc": None, "teff": None, "stype": "Galaxia espiral del Grupo Local (~0.78 Mpc)", "stype_en": "Local Group spiral galaxy (~0.78 Mpc)", "pm_ra": 0.0, "pm_dec": 0.0},
    {"id": "LMC_30DOR", "name": "Gran Nube de Magallanes (30 Doradus)", "ra": 84.6762, "dec": -69.1009, "dist_pc": None, "teff": None, "stype": "Región de formación estelar extragaláctica (~50 kpc)", "stype_en": "Extragalactic star-forming region (~50 kpc)", "pm_ra": 0.0, "pm_dec": 0.0},
    {"id": "SPLICES_ELIAS16", "name": "Elias 16 (estándar de hielos tras la nube de Tauro)", "ra": 69.9119, "dec": 26.1907, "dist_pc": 285.0, "teff": None, "stype": "Gigante K1III de fondo; su luz atraviesa la nube de Tauro (hielos H₂O/CO₂/CO)", "stype_en": "Background K1III giant seen through the Taurus cloud (H₂O/CO₂/CO ices)", "pm_ra": 20.33, "pm_dec": -28.80},
    {"id": "COMET_3I_ATLAS", "name": "3I/ATLAS (C/2025 N1) · posición 2025-08-08", "ra": 248.0824, "dec": -16.9638, "dist_pc": None, "teff": None, "stype": "3er objeto interestelar. Posición geocéntrica JPL Horizons del 2025-08-08 00:00 UTC (SPHEREx lo observó del 1 al 15 de agosto de 2025). Se mueve ~1°/día: no es una posición fija.", "stype_en": "3rd interstellar object. JPL Horizons geocentric position on 2025-08-08 00:00 UTC (SPHEREx observed it on 1–15 Aug 2025). It moves ~1°/day: not a fixed position.", "pm_ra": 0.0, "pm_dec": 0.0},
]

def _finalize_landmarks() -> None:
    """Las coordenadas de los hitos estelares están en J2000: se propagan linealmente a la época de visualización."""
    dt = DISPLAY_EPOCH_JYEAR - 2000.0
    for lm in ALLSKY_LANDMARKS:
        lm["ra_j2000"], lm["dec_j2000"] = lm["ra"], lm["dec"]
        pmra, pmdec = float(lm.get("pm_ra") or 0.0), float(lm.get("pm_dec") or 0.0)
        if abs(pmra) > 0 or abs(pmdec) > 0:
            cosd = max(np.cos(np.deg2rad(lm["dec"])), 1e-6)
            lm["ra"] = round(float((lm["ra"] + pmra * dt / (3.6e6 * cosd)) % 360.0), 6)
            lm["dec"] = round(lm["dec"] + pmdec * dt / 3.6e6, 6)


_finalize_landmarks()

CUSTOM_TARGETS_FILE = os.path.join(CACHE_DIR, "custom_targets.json")
_CUBE_RESP_CACHE: Dict[str, Dict[str, Any]] = {}


_PROTECTED_TARGET_KEYS = (
    "astrometry", "ra", "dec", "pm_ra", "pm_dec", "ra_j2000", "dec_j2000", "ra_prompt", "dec_prompt", "display_epoch",
    "parallax_mas", "distance_pc", "distance_ref", "sptype", "sptype_ref", "teff_k_lit", "teff_ref", "object_kind",
    "saturates", "prompt_epoch_note", "prompt_epoch_note_en", "is_allsky", "category",
)


def get_all_targets() -> List[Dict[str, Any]]:
    """Objetivos oficiales (aplicando ediciones o bajas) más los personalizados."""
    custom: List[Dict[str, Any]] = []
    if os.path.exists(CUSTOM_TARGETS_FILE):
        try:
            with open(CUSTOM_TARGETS_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
        except Exception:
            custom = []
    custom_by_id = {c.get("id"): c for c in custom if isinstance(c, dict) and c.get("id")}
    official_ids = {t["id"] for t in CHALLENGE_TARGETS}
    merged: List[Dict[str, Any]] = []
    for t in CHALLENGE_TARGETS:
        override = custom_by_id.get(t["id"])
        if override and override.get("_deleted"):
            continue
        if override:
            # La astrometría y los datos físicos oficiales nunca se sobrescriben desde la UI (ni con ediciones
            # guardadas por versiones anteriores de la app): solo nombre, textos, bandas y campo de visión.
            protected = {k: t[k] for k in _PROTECTED_TARGET_KEYS if k in t}
            merged.append({**t, **override, **protected, "custom": False})
        else:
            merged.append(dict(t))
    extra = [c for c in custom if isinstance(c, dict) and c.get("id") not in official_ids and not c.get("_deleted")]
    return merged + extra


def add_custom_target(data: Dict[str, Any]) -> Dict[str, Any]:
    """Agrega un objetivo personalizado o edita los textos de uno existente."""
    edit_id = (data.get("id") or "").strip()
    name = (data.get("name") or "").strip() or "Objetivo Personalizado"
    q_ra = str(data.get("query") or data.get("ra") or "").strip()
    q_dec = str(data.get("dec") or "").strip()
    official_match = _TARGETS_BY_ID.get(edit_id)
    if official_match and official_match.get("astrometry"):
        resolved = {"ra": official_match["ra"], "dec": official_match["dec"], "pm_ra": official_match["pm_ra"], "pm_dec": official_match["pm_dec"]}
    elif q_ra and not q_dec:
        resolved = parse_coordinates(q_ra, None)
    else:
        resolved = parse_coordinates(q_ra or name, q_dec or None)
    ra_val = float(resolved["ra"])
    dec_val = float(resolved["dec"])
    bands = data.get("bands") or data.get("recommended_bands") or ["D1", "D2", "D3", "D4"]
    if isinstance(bands, str):
        bands = [b.strip().upper() for b in bands.split(",") if b.strip()]
    fov = float(data.get("fov") or data.get("recommended_fov") or 0.10)
    subtitle = (data.get("subtitle") or "").strip() or f"RA {ra_val:.4f}°, Dec {dec_val:.4f}° (Personalizado)"
    subtitle_en = (data.get("subtitle_en") or "").strip() or subtitle
    tid = edit_id if edit_id else f"CUSTOM_{int(time.time() * 1000) % 1000000}"
    new_tgt: Dict[str, Any] = {
        "id": tid,
        "custom": not bool(official_match),
        "is_allsky": bool(official_match.get("is_allsky")) if official_match else False,
        "name": name,
        "subtitle": subtitle,
        "subtitle_en": subtitle_en,
        "category": official_match.get("category", "Personalizado") if official_match else "Personalizado",
        "ra": round(ra_val, 6),
        "dec": round(dec_val, 6),
        "ra_prompt": f"{ra_val:.5f}",
        "dec_prompt": f"{dec_val:.5f}",
        "pm_ra": float(resolved.get("pm_ra") or 0.0),
        "pm_dec": float(resolved.get("pm_dec") or 0.0),
        "recommended_bands": bands,
        "recommended_fov": fov,
        "science_note": (data.get("science_note") or "").strip()
        or (official_match.get("science_note") if official_match else "")
        or f"Objetivo guardado en RA {ra_val:.4f}°, Dec {dec_val:.4f}° (ICRS, época {DISPLAY_EPOCH_JYEAR}).",
        "science_note_en": (data.get("science_note_en") or "").strip()
        or (official_match.get("science_note_en") if official_match else "")
        or f"Saved target at RA {ra_val:.4f}°, Dec {dec_val:.4f}° (ICRS, epoch {DISPLAY_EPOCH_JYEAR}).",
    }
    if resolved.get("astrometry") and not official_match:
        new_tgt["astrometry"] = resolved["astrometry"]
    custom: List[Dict[str, Any]] = []
    if os.path.exists(CUSTOM_TARGETS_FILE):
        try:
            with open(CUSTOM_TARGETS_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
        except Exception:
            custom = []
    custom = [c for c in custom if isinstance(c, dict) and c.get("id") != tid]
    custom.append(new_tgt)
    with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(custom, f, ensure_ascii=False, indent=2)
    if official_match:
        return {**official_match, **new_tgt, **{k: official_match[k] for k in ("astrometry", "ra", "dec") if k in official_match}}
    return new_tgt


def delete_custom_target(target_id: str) -> bool:
    """Elimina un objetivo (oficial o personalizado) o restaura los predeterminados."""
    if target_id == "__RESTORE_DEFAULTS__":
        if os.path.exists(CUSTOM_TARGETS_FILE):
            try:
                os.remove(CUSTOM_TARGETS_FILE)
            except Exception:
                pass
        return True
    custom: List[Dict[str, Any]] = []
    if os.path.exists(CUSTOM_TARGETS_FILE):
        try:
            with open(CUSTOM_TARGETS_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
        except Exception:
            custom = []
    new_custom = [c for c in custom if isinstance(c, dict) and c.get("id") != target_id]
    if target_id in _TARGETS_BY_ID:
        new_custom.append({"id": target_id, "_deleted": True})
    try:
        with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_custom, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Resolución de coordenadas y nombres (Sesame/SIMBAD) con propagación de movimiento propio
# ---------------------------------------------------------------------------
def _resolve_name_sesame(name: str) -> Optional[Dict[str, Any]]:
    """Resuelve un nombre con Sesame (SIMBAD) y devuelve posición J2000, movimiento propio y paralaje."""
    from urllib.parse import quote

    for base in ("https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?", "https://vizier.cfa.harvard.edu/viz-bin/nph-sesame/-oxp/SNV?"):
        try:
            r = requests.get(base + quote(name), timeout=12)
            if not r.ok or "<jradeg>" not in r.text:
                continue
            t = r.text

            def _g(tag: str) -> Optional[str]:
                m = re.search(rf"<{tag}>([^<]+)</{tag}>", t)
                return m.group(1).strip() if m else None

            plx_m = re.search(r"<plx>\s*<v>([^<]+)</v>(?:<e>([^<]+)</e>)?", t)
            vel_m = re.search(r"<Vel>\s*<v>([^<]+)</v>", t)
            return {
                "ra_deg": float(_g("jradeg")),
                "dec_deg": float(_g("jdedeg")),
                "epoch_jyear": 2000.0,
                "pmra_masyr": float(_g("pmRA") or 0.0),
                "pmdec_masyr": float(_g("pmDE") or 0.0),
                "parallax_mas": float(plx_m.group(1)) if plx_m else None,
                "parallax_err_mas": float(plx_m.group(2)) if plx_m and plx_m.group(2) else None,
                "rv_kms": float(vel_m.group(1)) if vel_m else None,
                "ref": "SIMBAD vía Sesame (" + (_g("refPos") or "s/ref") + ")",
                "oname": _g("oname") or name,
                "otype": _g("otype"),
                "sptype": _g("spType"),
            }
        except Exception:
            continue
    return None


def _match_reference_by_coords(ra: float, dec: float, tol_arcsec: float = 15.0) -> Optional[Tuple[Dict[str, Any], float]]:
    """¿Coinciden unas coordenadas con un objetivo de referencia en alguna época entre 2000 y 2027 (p. ej. las del enunciado NASA)?"""
    c0 = SkyCoord(ra * u.deg, dec * u.deg)
    for t in CHALLENGE_TARGETS:
        astrom = t.get("astrometry")
        if not astrom or abs(float(astrom["dec_deg"]) - dec) > 0.2:
            continue
        best_ep, best_sep = None, tol_arcsec
        for ep in np.arange(2000.0, 2027.01, 0.1):
            r_t, d_t = propagate_astrometry(astrom, _jyear_to_mjd(float(ep)))
            sep = float(c0.separation(SkyCoord(r_t * u.deg, d_t * u.deg)).arcsec)
            if sep <= best_sep:
                best_ep, best_sep = float(ep), sep
        if best_ep is not None:
            return t, best_ep
    return None


def parse_coordinates(query_or_ra: str, dec_str: Optional[str] = None, epoch_yr: float = DISPLAY_EPOCH_JYEAR) -> Dict[str, Any]:
    """
    Convierte coordenadas (decimales, sexagesimales) o un nombre a RA/Dec ICRS.
    Coordenadas numéricas: se interpretan tal cual (sin movimiento propio).
    Nombres: se resuelven con Sesame/SIMBAD y se propagan a `epoch_yr` con su movimiento propio.
    """
    q = (query_or_ra or "").strip()
    d = (dec_str or "").strip()
    if not q:
        raise ValueError("Consulta vacía")

    ql = q.lower()
    for tgt in list(get_all_targets()) + ALLSKY_LANDMARKS:
        if ql in (str(tgt["id"]).lower(), str(tgt["name"]).lower()) or (len(ql) >= 4 and str(tgt["name"]).lower().startswith(ql)):
            out = {
                "ra": tgt["ra"],
                "dec": tgt["dec"],
                "ra_j2000": tgt.get("ra_j2000", tgt["ra"]),
                "dec_j2000": tgt.get("dec_j2000", tgt["dec"]),
                "pm_ra": tgt.get("pm_ra", 0.0),
                "pm_dec": tgt.get("pm_dec", 0.0),
                "resolved_name": tgt["name"],
                "epoch": epoch_yr,
                "preset_id": tgt["id"],
            }
            if tgt.get("astrometry"):
                out["astrometry"] = tgt["astrometry"]
            return out

    def _plain(ra_v: float, dec_v: float, label: str) -> Dict[str, Any]:
        ref = _match_reference_by_coords(ra_v, dec_v)
        if ref is not None:
            t, ep = ref
            return {
                "ra": t["ra"], "dec": t["dec"], "ra_j2000": t.get("ra_j2000"), "dec_j2000": t.get("dec_j2000"),
                "pm_ra": t.get("pm_ra", 0.0), "pm_dec": t.get("pm_dec", 0.0), "parallax_mas": t.get("parallax_mas"),
                "resolved_name": f"{t['name']} ({label})", "epoch": epoch_yr, "preset_id": t["id"], "astrometry": t["astrometry"],
                "note": f"Coordenadas reconocidas como {t['name']} en la época ≈{ep:.1f}; se usa su posición propagada a {epoch_yr}.",
                "note_en": f"Coordinates recognised as {t['name']} at epoch ≈{ep:.1f}; its position propagated to {epoch_yr} is used.",
            }
        return {
            "ra": ra_v, "dec": dec_v, "ra_j2000": ra_v, "dec_j2000": dec_v,
            "pm_ra": 0.0, "pm_dec": 0.0, "resolved_name": label, "epoch": epoch_yr,
            "note": "Coordenadas tomadas tal cual (sin movimiento propio).",
            "note_en": "Coordinates taken as given (no proper motion).",
        }

    if d:
        try:
            return _plain(float(q), float(d), f"RA {float(q):.4f}°, Dec {float(d):.4f}°")
        except ValueError:
            pass
        try:
            c = SkyCoord(f"{q} {d}", frame="icrs")
        except Exception:
            c = SkyCoord(q, d, unit=(u.hourangle, u.deg), frame="icrs")
        return _plain(float(c.ra.deg), float(c.dec.deg), f"{q} {d}")

    parts = re.split(r"[\s,]+", q)
    if len(parts) == 2:
        try:
            ra_v, dec_v = float(parts[0]), float(parts[1])
            return _plain(ra_v, dec_v, f"{ra_v:.4f}, {dec_v:.4f}")
        except ValueError:
            try:
                c = SkyCoord(q, frame="icrs")
                return _plain(float(c.ra.deg), float(c.dec.deg), q)
            except Exception:
                pass

    astrom = _resolve_name_sesame(q)
    if astrom:
        ra_p, dec_p = propagate_astrometry(astrom, _jyear_to_mjd(epoch_yr))
        return {
            "ra": round(ra_p, 6),
            "dec": round(dec_p, 6),
            "ra_j2000": round(astrom["ra_deg"], 6),
            "dec_j2000": round(astrom["dec_deg"], 6),
            "pm_ra": astrom["pmra_masyr"],
            "pm_dec": astrom["pmdec_masyr"],
            "parallax_mas": astrom.get("parallax_mas"),
            "resolved_name": astrom.get("oname", q),
            "sptype": astrom.get("sptype"),
            "epoch": epoch_yr,
            "astrometry": {k: astrom[k] for k in ("ra_deg", "dec_deg", "epoch_jyear", "pmra_masyr", "pmdec_masyr", "parallax_mas", "parallax_err_mas", "rv_kms", "ref")},
        }

    c = SkyCoord.from_name(q)
    return _plain(float(c.ra.deg), float(c.dec.deg), q)


# ---------------------------------------------------------------------------
# Descubrimiento de exposiciones (IRSA TAP)
# ---------------------------------------------------------------------------
_TAP_STATUS: Dict[str, Any] = {"ok": None, "error": None, "t": 0.0, "via": None, "tap_fail_t": 0.0, "sia_fail_t": 0.0}
SERVICE_RETRY_S = 120.0  # tras un fallo de TAP o SIA no se vuelve a esperar ese servicio durante 2 minutos


def query_spherex_exposures(
    ra: float,
    dec: float,
    bands: Optional[List[str]] = None,
    release: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Exposiciones L2b cuyo polígono contiene (ra, dec): caché local → IRSA TAP (spherex.artifact ⋈ spherex.plane)
    → IRSA SIA → lista oficial guardada en `data/spherex_exposure_index/` (solo objetivos del reto). Cachea en disco
    solo respuestas en vivo. Si nada está disponible devuelve [] y deja constancia en `_TAP_STATUS` (la UI lo
    comunica en vez de inventar datos).
    """
    key_str = f"tap_v2_{ra:.4f}_{dec:.4f}"
    cache_file = os.path.join(CACHE_DIR, "tap", f"{key_str}.json")
    all_rows: Optional[List[Dict[str, Any]]] = None
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                all_rows = json.load(f)
        except Exception:
            all_rows = None

    if all_rows is None:
        # Reutilizar una consulta cercana (≤ 0.05°): cada exposición cubre 3.5° × 3.5°, y luego se
        # comprueba la cobertura real con el WCS de cada archivo.
        tap_dir = os.path.join(CACHE_DIR, "tap")
        best_file, best_dist = None, 999.0
        for fname in os.listdir(tap_dir):
            m_tap = re.match(r"tap_v2_([-\d.]+)_([-\d.]+)\.json$", fname)
            if m_tap:
                try:
                    c_ra, c_dec = float(m_tap.group(1)), float(m_tap.group(2))
                    dist = float(np.hypot(((ra - c_ra + 180.0) % 360.0 - 180.0) * np.cos(np.deg2rad(dec)), dec - c_dec))
                    if dist < best_dist:
                        best_dist, best_file = dist, os.path.join(tap_dir, fname)
                except Exception:
                    pass
        if best_file and best_dist <= 0.05:
            try:
                with open(best_file, "r", encoding="utf-8") as f:
                    all_rows = json.load(f)
            except Exception:
                all_rows = None

    if all_rows is None:
        # Descubrimiento: IRSA TAP y, si falla, IRSA SIA (método de los tutoriales oficiales). Un servicio que acaba
        # de fallar no se vuelve a esperar durante SERVICE_RETRY_S (cortacircuito), para no bloquear cada consulta.
        now = time.time()
        errors: List[str] = []
        if now - float(_TAP_STATUS.get("tap_fail_t") or 0.0) >= SERVICE_RETRY_S:
            all_rows, tap_err = _query_tap_exposures(ra, dec)
            if all_rows is None:
                _TAP_STATUS["tap_fail_t"] = time.time()
                errors.append("TAP: " + str(tap_err))
            else:
                _TAP_STATUS["via"] = "TAP"
        else:
            errors.append("TAP: falló hace menos de 2 min (no se reintenta todavía)")
        if all_rows is None:
            if now - float(_TAP_STATUS.get("sia_fail_t") or 0.0) >= SERVICE_RETRY_S:
                all_rows = _query_sia_exposures(ra, dec)
                if all_rows is None:
                    _TAP_STATUS["sia_fail_t"] = time.time()
                    errors.append("SIA: sin respuesta válida")
                else:
                    _TAP_STATUS["via"] = "SIA"
            else:
                errors.append("SIA: falló hace menos de 2 min (no se reintenta todavía)")
        snap_info = None
        if all_rows is None:
            # Último respaldo: lista OFICIAL de exposiciones guardada en el proyecto para los objetivos del reto
            # (respuesta real de IRSA SIA). Las imágenes se siguen leyendo en vivo desde AWS S3.
            snap = _query_snapshot_exposures(ra, dec)
            if snap is not None:
                all_rows, snap_info = snap
        if all_rows is None:
            _TAP_STATUS.update({"ok": False, "error": " · ".join(errors), "t": time.time(), "snapshot": None})
            return []
        if snap_info is not None:
            _TAP_STATUS.update({"ok": True, "via": "snapshot", "snapshot": snap_info, "error": " · ".join(errors), "t": time.time()})
        else:
            _TAP_STATUS.update({"ok": True, "error": (" · ".join(errors) or None), "t": time.time(), "snapshot": None})
            if all_rows:  # una respuesta vacía no se cachea: puede cambiar con nuevas versiones de datos
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(all_rows, f)
                except Exception:
                    pass
    else:
        _TAP_STATUS.update({"ok": True, "error": None, "via": "caché"})

    filtered = all_rows
    if bands:
        band_set = {b.upper().replace("SPHEREX-", "") for b in bands}
        filtered = [r for r in filtered if r["band"].upper() in band_set]
    if release and release.lower() != "all":
        filtered = [r for r in filtered if (r.get("release") or "").lower() == release.lower()]
    return filtered


SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "spherex_exposure_index")
SNAPSHOT_MATCH_DEG = 0.3  # cada exposición cubre 3.5° × 3.5°; la cobertura real se comprueba luego con el WCS
_SNAPSHOTS: Optional[List[Dict[str, Any]]] = None


def _load_exposure_snapshots() -> List[Dict[str, Any]]:
    """Listas oficiales de exposiciones L2b (respuestas de IRSA SIA) incluidas en el proyecto para los objetivos del reto."""
    global _SNAPSHOTS
    if _SNAPSHOTS is not None:
        return _SNAPSHOTS
    snaps: List[Dict[str, Any]] = []
    if os.path.isdir(SNAPSHOT_DIR):
        for fn in sorted(os.listdir(SNAPSHOT_DIR)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(SNAPSHOT_DIR, fn), "r", encoding="utf-8") as f:
                    d = json.load(f)
                cols = d["columns"]
                rows = []
                for vals in d["rows"]:
                    r = dict(zip(cols, vals))
                    r["band_full"] = f"SPHEREx-{r['band']}"
                    r["date_iso"] = Time(float(r["t_min"]), format="mjd").isot[:19] if r.get("t_min") else ""
                    r.setdefault("exptime", EXPTIME_S)
                    rows.append(r)
                snaps.append({"target_id": d.get("target_id"), "ra": float(d["ra"]), "dec": float(d["dec"]),
                              "date_utc": (d.get("query") or {}).get("date_utc"), "rows": rows})
            except Exception:
                continue
    _SNAPSHOTS = snaps
    return snaps


def _query_snapshot_exposures(ra: float, dec: float) -> Optional[Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    """Exposiciones de la lista guardada más cercana (≤ SNAPSHOT_MATCH_DEG), o None si no hay ninguna aplicable."""
    best, best_d = None, 999.0
    for snap in _load_exposure_snapshots():
        d = float(np.hypot(((ra - snap["ra"] + 180.0) % 360.0 - 180.0) * np.cos(np.deg2rad(dec)), dec - snap["dec"]))
        if d < best_d:
            best, best_d = snap, d
    if best is None or best_d > SNAPSHOT_MATCH_DEG:
        return None
    info = {"target_id": best["target_id"], "date_utc": best["date_utc"], "sep_deg": round(best_d, 4), "n_rows": len(best["rows"])}
    return [dict(r) for r in best["rows"]], info


def _query_tap_exposures(ra: float, dec: float) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Exposiciones L2b cuyo polígono contiene (ra, dec) vía IRSA TAP (spherex.artifact ⋈ spherex.plane)."""
    q = (
        "SELECT a.uri, p.obsid, p.datarelease, p.energy_bandpassname, "
        "p.time_bounds_lower AS t_min, p.time_exposure AS t_exptime, "
        "p.energy_bounds_lower AS em_min, p.energy_bounds_upper AS em_max "
        "FROM spherex.artifact a "
        "JOIN spherex.plane p ON a.planeid = p.planeid "
        f"WHERE 1 = CONTAINS(POINT('ICRS', {ra:.6f}, {dec:.6f}), p.poly) "
        "ORDER BY p.time_bounds_lower ASC"
    )
    try:
        r = requests.get(TAP_URL, params={"LANG": "ADQL", "FORMAT": "csv", "QUERY": q}, timeout=TAP_TIMEOUT_S)
        r.raise_for_status()
        if not r.text.startswith("uri"):
            raise RuntimeError("Respuesta TAP inesperada")
        rows: List[Dict[str, Any]] = []
        for row in csv.DictReader(io.StringIO(r.text)):
            uri = row.get("uri", "")
            if not uri.endswith(".fits"):
                continue
            m = re.search(r"level2_([^_]+_[^_]+_[^_]+_\d+)", uri)
            band_full = row.get("energy_bandpassname", "")
            t_min = float(row["t_min"]) if row.get("t_min") else 0.0
            rows.append({
                "obs_id": m.group(1) if m else row.get("obsid", ""),
                "uri": uri,
                "release": (row.get("datarelease") or "").lower(),
                "band": band_full.replace("SPHEREx-", ""),
                "band_full": band_full,
                "t_min": t_min,
                "date_iso": Time(t_min, format="mjd").isot[:19] if t_min else "",
                "exptime": float(row["t_exptime"]) if row.get("t_exptime") else EXPTIME_S,
            })
        return rows, None
    except Exception as exc:  # IRSA caído o lento: no se inventa nada
        return None, str(exc)[:200]


SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
SIA_COLLECTIONS = ("spherex_dr1", "spherex_dr1_deep", "spherex_qr3", "spherex_qr3_deep")


def _query_sia_exposures(ra: float, dec: float) -> Optional[List[Dict[str, Any]]]:
    """Lista de exposiciones L2b vía IRSA SIA v2 (método de los tutoriales oficiales de IRSA). None si falla."""
    params: List[Tuple[str, str]] = [("POS", f"CIRCLE {ra:.6f} {dec:.6f} 0.0005"), ("RESPONSEFORMAT", "CSV")]
    params += [("COLLECTION", c) for c in SIA_COLLECTIONS]
    try:
        r = requests.get(SIA_URL, params=params, timeout=SIA_TIMEOUT_S)
        if not r.ok or "access_url" not in r.text[:4000]:
            return None
        out: List[Dict[str, Any]] = []
        for row in csv.DictReader(io.StringIO(r.text)):
            url = row.get("access_url", "")
            if ".fits" not in url:
                continue
            uri = url.split("irsa.ipac.caltech.edu/", 1)[-1].split("?")[0]
            m = re.search(r"level2_([^_]+_[^_]+_[^_]+_\d+)", uri)
            band = (row.get("energy_bandpassname") or "").replace("SPHEREx-", "")
            if not band:
                mb = re.search(r"_\d(D\d)_spx", uri)
                band = mb.group(1) if mb else ""
            t_min = float(row["t_min"]) if row.get("t_min") else 0.0
            coll = (row.get("obs_collection") or "").lower()
            rel = "dr1" if "dr1" in coll else ("qr3" if "qr3" in coll else coll.replace("spherex_", ""))
            out.append({"obs_id": m.group(1) if m else row.get("obs_id", ""), "uri": uri, "release": rel, "band": band,
                        "band_full": f"SPHEREx-{band}", "t_min": t_min, "date_iso": Time(t_min, format="mjd").isot[:19] if t_min else "",
                        "exptime": float(row["t_exptime"]) if row.get("t_exptime") else EXPTIME_S})
        return sorted(out, key=lambda x: x["t_min"])
    except Exception:
        return None


def eval_wcs_wave(X: np.ndarray, Y: np.ndarray, V: np.ndarray, x_raw: float, y_raw: float) -> Tuple[float, float]:
    """
    Interpolación bilineal de la tabla WCS-WAVE (coordenadas FITS 1-based del detector) →
    (longitud de onda central, ancho de banda) en µm. Verificado contra CWAVE/CBAND oficiales.
    """
    ix = int(np.clip(np.searchsorted(X, x_raw) - 1, 0, len(X) - 2))
    iy = int(np.clip(np.searchsorted(Y, y_raw) - 1, 0, len(Y) - 2))
    tx = float(np.clip((x_raw - X[ix]) / (X[ix + 1] - X[ix]), 0.0, 1.0))
    ty = float(np.clip((y_raw - Y[iy]) / (Y[iy + 1] - Y[iy]), 0.0, 1.0))
    v00, v10, v01, v11 = V[iy, ix], V[iy, ix + 1], V[iy + 1, ix], V[iy + 1, ix + 1]
    val = (1 - tx) * (1 - ty) * v00 + tx * (1 - ty) * v10 + (1 - tx) * ty * v01 + tx * ty * v11
    return float(val[0]), float(val[1])


# ---------------------------------------------------------------------------
# Recortes L2b (AWS S3 HTTP Range → IRSA IBE) con metadatos para fotometría y astrometría
# ---------------------------------------------------------------------------
_HTTP_POOL = requests.Session()
_HTTP_POOL.mount("https://", requests.adapters.HTTPAdapter(pool_connections=24, pool_maxsize=24))
_CUT_META_KEYS = ("mjd_avg", "psf_fwhm", "detector", "x0_det", "y0_det", "sc_start", "sc_end", "vsc_start", "vsc_end", "t_span_s")


def _hdr_meta(hdr: fits.Header) -> Dict[str, Any]:
    def _f(k: str, default: float = np.nan) -> float:
        try:
            return float(hdr.get(k, default))
        except Exception:
            return default

    meta = {
        "mjd_avg": _f("MJD-AVG", _f("MJD-OBS")),
        "mjd_beg": _f("MJD-BEG", _f("MJD-OBS")),
        "mjd_end": _f("MJD-END", np.nan),
        "psf_fwhm": _f("PSF_FWHM"),
        "detector": int(hdr.get("DETECTOR", 0) or 0),
        "sc_start": [_f("X_SC_START"), _f("Y_SC_START"), _f("Z_SC_START")],
        "sc_end": [_f("X_SC_END"), _f("Y_SC_END"), _f("Z_SC_END")],
        "vsc_start": [_f("VX_SC_START"), _f("VY_SC_START"), _f("VZ_SC_START")],
        "vsc_end": [_f("VX_SC_END"), _f("VY_SC_END"), _f("VZ_SC_END")],
    }
    if np.isfinite(meta["mjd_end"]) and np.isfinite(meta["mjd_beg"]):
        meta["t_span_s"] = (meta["mjd_end"] - meta["mjd_beg"]) * 86400.0
    else:
        meta["t_span_s"] = float(hdr.get("TELAPSE", EXPTIME_S) or EXPTIME_S)
    return meta


def _read_epsf_row(url: str, data_offset: int, row_len: int, det: int, x_det: float, y_det: float) -> Optional[np.ndarray]:
    """Lee por HTTP Range la fila de la ePSF oficial (33×33, 5× sobremuestreada) de la zona que contiene (x_det, y_det)."""
    nx_z, ny_z = (11, 41) if det == 3 else (21, 21)
    bx = int(np.clip(x_det // (2040.0 / nx_z), 0, nx_z - 1))
    by = int(np.clip(y_det // (2040.0 / ny_z), 0, ny_z - 1))
    for row_idx in (by * nx_z + bx, bx * ny_z + by):
        try:
            b0 = data_offset + row_idx * row_len
            r = _HTTP_POOL.get(url, headers={"Range": f"bytes={b0}-{b0 + row_len - 1}"}, timeout=20)
            if r.status_code not in (200, 206) or len(r.content) != row_len:
                continue
            raw = r.content
            xc, yc, xw, yw = np.frombuffer(raw[8:24], ">f4")
            if abs(x_det - xc) <= 0.51 * xw + 1 and abs(y_det - yc) <= 0.51 * yw + 1:
                psf = np.frombuffer(raw[40:40 + 1089 * 8], ">f8").reshape(33, 33).astype(np.float64)
                if np.isfinite(psf).all() and psf.sum() > 0:
                    return psf
        except Exception:
            continue
    return None


def _epsf_from_table(tbl: Any, x_det: float, y_det: float) -> Optional[np.ndarray]:
    try:
        xc = np.asarray(tbl["XCENTER"], float)
        yc = np.asarray(tbl["YCENTER"], float)
        i = int(np.argmin((xc - x_det) ** 2 + (yc - y_det) ** 2))
        psf = np.asarray(tbl["EPSF"][i], dtype=np.float64).reshape(33, 33)
        return psf if np.isfinite(psf).all() and psf.sum() > 0 else None
    except Exception:
        return None


def _cut_from_npz(d: Any, row: Dict[str, Any], source: str) -> Dict[str, Any]:
    hdr = fits.Header.fromstring(str(d["header_str"]))
    meta = json.loads(str(d["meta_json"]))
    return {
        "row": row,
        "img": d["img"].astype(np.float32),
        "zodi": float(d["zodi_med"]),
        "flags": d["flags"].astype(np.int64),
        "var": d["var"].astype(np.float32),
        "wcs": WCS(hdr),
        "wave_tab": (d["wave_x"], d["wave_y"], d["wave_v"]),
        "psf": d["psf"] if d["psf"].size == 1089 else None,
        "meta": meta,
        "source": source,
    }


def fetch_cutout_cached(row: Dict[str, Any], ra: float, dec: float, size_deg: float) -> Optional[Dict[str, Any]]:
    """
    Devuelve el recorte nativo (IMAGE−ZODI, FLAGS, VARIANCE, WCS TAN-SIP, tabla WCS-WAVE, ePSF y
    metadatos de cabecera) de una exposición L2b. Orden: caché en disco → AWS S3 (HTTP Range) → IRSA IBE.
    """
    uri = row["uri"]
    obs_id = row["obs_id"]
    band = row["band"]
    cid = hashlib.md5(f"{uri}_{ra:.4f}_{dec:.4f}_{size_deg:.3f}".encode()).hexdigest()[:16]
    cpath = os.path.join(CACHE_DIR, "cutouts", f"{obs_id}_{band}_{cid}_r2.npz")

    if os.path.exists(cpath):
        try:
            with np.load(cpath, allow_pickle=False) as d:
                return _cut_from_npz(d, row, "cache")
        except Exception:
            pass

    s3_key = uri.replace("ibe/data/spherex/", "")
    s3_url = S3_BASE + s3_key
    try:
        with fits.open(s3_url, use_fsspec=True, fsspec_kwargs={"block_size": 256 * 1024}) as h:
            hdr_full = h["IMAGE"].header
            w_full = WCS(hdr_full)
            ny, nx = h["IMAGE"].shape
            x_det, y_det = [float(v) for v in w_full.world_to_pixel_values(ra, dec)]
            r_pix = int(np.ceil(size_deg * 0.78 * 3600.0 / PIX_SCALE_NATIVE)) + 10
            x0, x1 = max(int(round(x_det)) - r_pix, 0), min(int(round(x_det)) + r_pix, nx)
            y0, y1 = max(int(round(y_det)) - r_pix, 0), min(int(round(y_det)) + r_pix, ny)
            if x1 - x0 < 12 or y1 - y0 < 12:
                return None
            img_raw = h["IMAGE"].section[y0:y1, x0:x1].astype(np.float32)
            zod_raw = h["ZODI"].section[y0:y1, x0:x1].astype(np.float32)
            flg_raw = h["FLAGS"].section[y0:y1, x0:x1].astype(np.int64)
            var_raw = h["VARIANCE"].section[y0:y1, x0:x1].astype(np.float32)
            wtbl = h["WCS-WAVE"].data
            X_w, Y_w, V_w = (wtbl["X"][0].astype(float), wtbl["Y"][0].astype(float), wtbl["VALUES"][0].astype(float))
            meta = _hdr_meta(hdr_full)
            meta["x0_det"], meta["y0_det"] = int(x0), int(y0)
            psf = None
            try:
                e = h["EPSF"]
                psf = _read_epsf_row(s3_url, int(e._data_offset), int(e.header["NAXIS1"]), meta["detector"], x_det, y_det)
            except Exception:
                psf = None
        w_sub = w_full[y0:y1, x0:x1]
        hdr_sub = w_sub.to_header(relax=True)
        img_clean = img_raw - zod_raw
        zodi_med = float(np.nanmedian(zod_raw))
        np.savez_compressed(
            cpath, img=img_clean, zodi_med=zodi_med, flags=flg_raw, var=var_raw,
            header_str=hdr_sub.tostring(), wave_x=X_w, wave_y=Y_w, wave_v=V_w,
            psf=psf if psf is not None else np.zeros(1), meta_json=json.dumps(meta),
        )
        return {
            "row": row, "img": img_clean, "zodi": zodi_med, "flags": flg_raw, "var": var_raw,
            "wcs": w_sub, "wave_tab": (X_w, Y_w, V_w), "psf": psf, "meta": meta, "source": "aws_s3",
        }
    except Exception:
        pass

    # Respaldo: servicio de recortes IBE de IRSA
    ibe_url = f"{IBE_BASE}{uri}?center={ra},{dec}&size={min(size_deg * 1.45, 0.5):.4f}"
    r = requests.get(ibe_url, timeout=90)
    r.raise_for_status()
    with fits.open(io.BytesIO(r.content)) as h:
        hdr = h["IMAGE"].header
        img_raw = h["IMAGE"].data.astype(np.float32)
        zod_raw = h["ZODI"].data.astype(np.float32) if "ZODI" in h else np.zeros_like(img_raw)
        flg_raw = h["FLAGS"].data.astype(np.int64)
        var_raw = h["VARIANCE"].data.astype(np.float32) if "VARIANCE" in h else np.full_like(img_raw, np.nan)
        w_sub = WCS(hdr)
        meta = _hdr_meta(hdr)
        # Desplazamiento del recorte en el detector a partir del WCS alternativo 'A' (píxeles activos 0-based)
        try:
            wa = WCS(hdr, key="A")
            ox, oy = wa.pixel_to_world_values(0.0, 0.0)
            meta["x0_det"], meta["y0_det"] = int(round(float(ox))), int(round(float(oy)))
        except Exception:
            meta["x0_det"], meta["y0_det"] = 0, 0
        if "WCS-WAVE" in h:
            wtbl = h["WCS-WAVE"].data
            X_w, Y_w, V_w = (wtbl["X"][0].astype(float), wtbl["Y"][0].astype(float), wtbl["VALUES"][0].astype(float))
        else:
            X_w = Y_w = V_w = np.zeros(1)
        xc, yc = [float(v) for v in w_sub.world_to_pixel_values(ra, dec)]
        psf = _epsf_from_table(h["EPSF"].data, xc + meta["x0_det"], yc + meta["y0_det"]) if "EPSF" in h else None
    img_clean = img_raw - zod_raw
    zodi_med = float(np.nanmedian(zod_raw))
    np.savez_compressed(
        cpath, img=img_clean, zodi_med=zodi_med, flags=flg_raw, var=var_raw,
        header_str=w_sub.to_header(relax=True).tostring(), wave_x=X_w, wave_y=Y_w, wave_v=V_w,
        psf=psf if psf is not None else np.zeros(1), meta_json=json.dumps(meta),
    )
    return {
        "row": row, "img": img_clean, "zodi": zodi_med, "flags": flg_raw, "var": var_raw, "wcs": w_sub,
        "wave_tab": (X_w, Y_w, V_w), "psf": psf, "meta": meta, "source": "irsa_ibe",
    }


def _safe_fetch(row: Dict[str, Any], ra: float, dec: float, size_deg: float) -> Optional[Dict[str, Any]]:
    try:
        return fetch_cutout_cached(row, ra, dec, size_deg)
    except Exception:
        return None


def cut_wavelength_at(cut: Dict[str, Any], ra: float, dec: float) -> Tuple[float, float, float, float]:
    """λ y Δλ (µm) en la posición del detector donde cae (ra, dec) en esta exposición; también (x, y) del recorte."""
    x, y = [float(v) for v in cut["wcs"].world_to_pixel_values(ra, dec)]
    X_w, Y_w, V_w = cut["wave_tab"]
    if np.size(X_w) < 2:
        return float("nan"), float("nan"), x, y
    x_det = x + float(cut["meta"].get("x0_det", 0))
    y_det = y + float(cut["meta"].get("y0_det", 0))
    lam, bw = eval_wcs_wave(np.asarray(X_w), np.asarray(Y_w), np.asarray(V_w), x_det + 1.0, y_det + 1.0)
    return lam, bw, x, y


DET_NPIX = 2040          # tamaño de la matriz activa de cada detector H2RG en las imágenes L2b
LVF_EDGE_MARGIN_PX = 32  # margen del borde del detector donde la respuesta del LVF y la calibración no son fiables


def lvf_edge_reason(cut: Dict[str, Any], x: float, y: float, lam: float) -> Optional[str]:
    """
    'edge' si la fuente cae a < LVF_EDGE_MARGIN_PX del borde del detector; 'lambda' si su λ está fuera del rango
    nominal del detector (extremos del filtro LVF, p. ej. 5.006 µm en D6). En esos casos el flujo no se usa
    para afirmar variabilidad (validado: una medición en D6 a 5.006 µm daba ×4.8 el flujo real de una estrella).
    """
    x_det = x + float(cut["meta"].get("x0_det", 0))
    y_det = y + float(cut["meta"].get("y0_det", 0))
    m = LVF_EDGE_MARGIN_PX
    if x_det < m or y_det < m or x_det > DET_NPIX - 1 - m or y_det > DET_NPIX - 1 - m:
        return "edge"
    info = DETECTOR_INFO.get(str(cut["row"].get("band", "")))
    if info and np.isfinite(lam) and not (info["lmin"] <= lam <= info["lmax"]):
        return "lambda"
    return None


# ---------------------------------------------------------------------------
# Fotometría forzada con la ePSF oficial (Suplemento v2.1 sec. 3.3 y 4.2.3)
# ---------------------------------------------------------------------------
def _bilinear_sample(arr: np.ndarray, fy: np.ndarray, fx: np.ndarray) -> np.ndarray:
    ny, nx = arr.shape
    fx = np.clip(fx, 0.0, nx - 1.000001)
    fy = np.clip(fy, 0.0, ny - 1.000001)
    x0 = np.floor(fx).astype(int)
    y0 = np.floor(fy).astype(int)
    tx = fx - x0
    ty = fy - y0
    return (
        arr[y0, x0] * (1 - tx) * (1 - ty) + arr[y0, x0 + 1] * tx * (1 - ty)
        + arr[y0 + 1, x0] * (1 - tx) * ty + arr[y0 + 1, x0 + 1] * tx * ty
    )


def psf_native_model(psf: Optional[np.ndarray], xs: np.ndarray, ys: np.ndarray, x0: float, y0: float, fwhm_px: float) -> np.ndarray:
    """
    Respuesta por píxel nativo de una fuente puntual en (x0, y0).
    - Con ePSF oficial (33×33, 5× sobremuestreada, centro en el índice 16): muestreo bilineal y
      normalización de la red nativa a flujo total unidad.
    - Sin ePSF: gaussiana con FWHM = PSF_FWHM de la cabecera, integrada por píxel (normalizada).
    """
    if psf is not None and psf.shape == (33, 33):
        fx = 16.0 + 5.0 * (xs - x0)
        fy = 16.0 + 5.0 * (ys - y0)
        inside = (fx >= 0) & (fx <= 32) & (fy >= 0) & (fy <= 32)
        m = np.where(inside, _bilinear_sample(psf, fy, fx), 0.0)
        norm = float(psf[1::5, 1::5].sum())
        return m / norm if norm > 0 else m
    sig = max(float(fwhm_px), 0.6) / 2.3548
    g = np.exp(-((xs - x0) ** 2 + (ys - y0) ** 2) / (2.0 * sig ** 2))
    return g / (2.0 * np.pi * sig ** 2)


def pixel_solid_angle_sr(w: WCS, x: float, y: float) -> float:
    """Ángulo sólido del píxel en (x, y) con el Jacobiano del WCS completo (incluye la distorsión SIP)."""
    try:
        (r1, r2), (d1, d2) = w.pixel_to_world_values([x - 0.5, x + 0.5], [y, y])
        (r3, r4), (d3, d4) = w.pixel_to_world_values([x, x], [y - 0.5, y + 0.5])
        c = np.cos(np.radians(0.5 * (d1 + d2)))
        dra1 = ((r2 - r1 + 180.0) % 360.0) - 180.0
        dra2 = ((r4 - r3 + 180.0) % 360.0) - 180.0
        a = np.radians(dra1 * c)
        b = np.radians(d2 - d1)
        cc = np.radians(dra2 * c)
        dd = np.radians(d4 - d3)
        om = abs(a * dd - cc * b)
        return float(om) if np.isfinite(om) and om > 0 else SOLID_ANGLE_SR
    except Exception:
        return SOLID_ANGLE_SR


def _wls_flux(img: np.ndarray, var: np.ndarray, good: np.ndarray, P: np.ndarray, extra: Optional[List[np.ndarray]] = None) -> Optional[Tuple[float, float, float, float, int]]:
    """
    Mínimos cuadrados ponderados (pesos 1/VARIANCE): datos = F·P + Σ F_k·P_k + B. Las P_k son fuentes vecinas
    (posición fija de Gaia) ajustadas a la vez para que no contaminen el flujo del objetivo (como Tractor en
    modo forzado). Devuelve (F, σF, B, χ²ν, n).
    """
    n = int(good.sum())
    if n < 6 or float(P[good].sum()) < 0.25:
        return None
    cols = [P[good]] + [Pk[good] for Pk in (extra or []) if float(Pk[good].sum()) > 0.05] + [np.ones(n)]
    A = np.stack(cols, axis=1)
    if n <= A.shape[1] + 2:
        return None
    wv = 1.0 / var[good]
    ATA = A.T @ (A * wv[:, None])
    try:
        cov = np.linalg.inv(ATA)
    except np.linalg.LinAlgError:
        return None
    th = cov @ (A.T @ (img[good] * wv))
    res = img[good] - A @ th
    chi2 = float(np.sum(res ** 2 * wv) / max(n - A.shape[1], 1))
    return float(th[0]), float(np.sqrt(max(cov[0, 0], 0.0))), float(th[-1]), chi2, n


def _saturated_core_astrometry(out: Dict[str, Any], st_flg: np.ndarray, xs: np.ndarray, ys: np.ndarray, x: float, y: float, w: WCS) -> None:
    """
    Posición de una estrella saturada: centroide de los píxeles con OVERFLOW (bit 1) a ≤ 4 px de la posición
    predicha. El flujo no es medible, pero la mancha saturada está centrada en la estrella (validado con
    Barnard en 28 exposiciones L2b: mediana 0.2 px). Solo se usa para astrometría, nunca para fotometría.
    """
    m = (np.hypot(xs - x, ys - y) <= 4.0) & ((st_flg & (1 << 1)) != 0)
    n = int(m.sum())
    if n < 2:
        return
    cx, cy = float(xs[m].mean()), float(ys[m].mean())
    try:
        rr_m, dd_m = w.pixel_to_world_values(cx, cy)
    except Exception:
        return
    out["ra_meas"], out["dec_meas"] = round(float(rr_m), 6), round(float(dd_m), 6)
    out["offset_arcsec"] = round(float(np.hypot(cx - x, cy - y) * PIX_SCALE_NATIVE), 2)
    out["astrometry_method"] = "saturated_core"
    out["n_saturated_px"] = n


def forced_photometry_cut(cut: Dict[str, Any], ra: float, dec: float, fit_position: bool = True, neighbors: Optional[List[Tuple[float, float]]] = None) -> Dict[str, Any]:
    """
    Fotometría PSF forzada en una exposición nativa L2b en (ra, dec):
    flujo (µJy) con error (VARIANCE + 3 % sistemático), S/N, magnitud AB (o límite superior 3σ),
    banderas oficiales en r ≤ 2.5 px, aviso de saturación y desplazamiento medido del centroide.
    """
    img = cut["img"]
    var = cut["var"]
    flg = cut["flags"]
    w = cut["wcs"]
    lam, bw, x, y = cut_wavelength_at(cut, ra, dec)
    ny, nx = img.shape
    out: Dict[str, Any] = {
        "obs_id": cut["row"]["obs_id"], "band": cut["row"]["band"], "release": cut["row"].get("release"),
        "mjd": round(float(cut["meta"].get("mjd_avg", cut["row"].get("t_min", 0.0))), 6),
        "date_iso": Time(float(cut["meta"].get("mjd_avg", cut["row"].get("t_min", 0.0))), format="mjd").isot[:19],
        "wavelength_um": round(lam, 4) if np.isfinite(lam) else None,
        "bandwidth_um": round(bw, 4) if np.isfinite(bw) else None,
        "ra_pred": round(float(ra), 6), "dec_pred": round(float(dec), 6),
        "psf_fwhm_arcsec": round(float(cut["meta"].get("psf_fwhm", np.nan)), 2) if np.isfinite(cut["meta"].get("psf_fwhm", np.nan)) else None,
        "psf_model": "ePSF oficial" if cut.get("psf") is not None else "Gaussiana (PSF_FWHM de cabecera)",
        "flux_ujy": None, "err_ujy": None, "snr": None, "ab_mag": None, "ab_mag_err": None, "upper_limit_ujy": None,
        "quality": "no_coverage", "flags": [], "chi2_red": None, "offset_arcsec": None, "n_pix": 0,
    }
    if not (3 <= x < nx - 3 and 3 <= y < ny - 3):
        return out
    r = 6
    xi, yi = int(round(x)), int(round(y))
    ys0, ys1 = max(0, yi - r), min(ny, yi + r + 1)
    xs0, xs1 = max(0, xi - r), min(nx, xi + r + 1)
    st_img = img[ys0:ys1, xs0:xs1].astype(np.float64)
    st_var = var[ys0:ys1, xs0:xs1].astype(np.float64)
    st_flg = flg[ys0:ys1, xs0:xs1].astype(np.int64)
    ys, xs = np.mgrid[ys0:ys1, xs0:xs1]
    fwhm_px = float(cut["meta"].get("psf_fwhm", 7.5) or 7.5) / PIX_SCALE_NATIVE
    psf = cut.get("psf")
    good = np.isfinite(st_img) & np.isfinite(st_var) & (st_var > 0) & ((st_flg & PHOT_MASK) == 0)
    rr = np.hypot(xs - x, ys - y)
    near = rr <= 2.5
    warn_bits = int(np.bitwise_or.reduce(st_flg[near].ravel())) if np.any(near) else 0
    out["flags"] = [n for n in flag_names(warn_bits & PHOT_WARN_MASK)]
    core = rr <= 1.2
    core_lost = int(np.sum(core & ~good))
    saturated = bool((warn_bits & SATURATION_MASK) or core_lost >= 2)

    extra: List[np.ndarray] = []
    for (ra_n, dec_n) in neighbors or []:
        try:
            xn, yn = [float(v) for v in w.world_to_pixel_values(ra_n, dec_n)]
        except Exception:
            continue
        if xs0 - 3 <= xn <= xs1 + 2 and ys0 - 3 <= yn <= ys1 + 2 and np.hypot(xn - x, yn - y) >= 0.25:
            extra.append(psf_native_model(psf, xs, ys, xn, yn, fwhm_px))
    out["n_deblended"] = len(extra)
    best_dx, best_dy = 0.0, 0.0
    if fit_position:
        best_chi = None
        for dx in np.arange(-1.5, 1.501, 0.25):
            for dy in np.arange(-1.5, 1.501, 0.25):
                res = _wls_flux(st_img, st_var, good, psf_native_model(psf, xs, ys, x + dx, y + dy, fwhm_px), extra)
                if res is not None and res[0] > 0 and (best_chi is None or res[3] < best_chi):
                    best_chi, best_dx, best_dy = res[3], dx, dy
    P_t = psf_native_model(psf, xs, ys, x, y, fwhm_px)
    res = _wls_flux(st_img, st_var, good, P_t, extra)
    if saturated:
        _saturated_core_astrometry(out, st_flg, xs, ys, x, y, w)
    if res is None:
        # Sin píxeles válidos suficientes: si el núcleo tiene OVERFLOW/NONLINEAR/BLOOM es una estrella saturada
        out["quality"] = "saturated" if saturated else "masked"
        return out
    F, sF, B, chi2, n = res
    # Métrica oficial de calidad del ajuste (Suplemento sec. 3.3, Nota 2): ⟨|p − m|/σ⟩ en r ≤ 2.5 px
    model = F * P_t + B
    fq_mask = good & near
    fit_quality = float(np.mean(np.abs(st_img[fq_mask] - model[fq_mask]) / np.sqrt(st_var[fq_mask]))) if np.any(fq_mask) else float("nan")
    om = pixel_solid_angle_sr(w, x, y)
    f_ujy = F * om * 1e12  # (MJy/sr)·sr = MJy → µJy
    stat_ujy = sF * om * 1e12
    err_ujy = float(np.hypot(stat_ujy, SYSTEMATIC_FRAC * abs(f_ujy)))
    snr = f_ujy / err_ujy if err_ujy > 0 else 0.0
    out.update({
        "flux_ujy": round(f_ujy, 2), "err_ujy": round(err_ujy, 2), "snr": round(snr, 2),
        "chi2_red": round(chi2, 2), "fit_quality": round(fit_quality, 2) if np.isfinite(fit_quality) else None,
        "n_pix": n, "pix_solid_angle_sr": float(f"{om:.4e}"), "bg_mjy_sr": round(B, 5),
    })
    if snr >= 3.0 and f_ujy > 0:
        out["ab_mag"] = round(AB_ZP_UJY - 2.5 * np.log10(f_ujy), 3)
        out["ab_mag_err"] = round(1.0857 / snr, 3)
    else:
        out["upper_limit_ujy"] = round(max(f_ujy, 0.0) + 3.0 * err_ujy, 2)
    if fit_position and snr >= 5.0 and not saturated:
        off = np.hypot(best_dx, best_dy) * PIX_SCALE_NATIVE
        out["offset_arcsec"] = round(float(off), 2)
        try:
            rr_m, dd_m = w.pixel_to_world_values(x + best_dx, y + best_dy)
            out["ra_meas"], out["dec_meas"] = round(float(rr_m), 6), round(float(dd_m), 6)
            out["astrometry_method"] = "epsf"
        except Exception:
            pass
    edge = lvf_edge_reason(cut, x, y, lam)
    out["lvf_edge"] = edge
    if saturated:
        out["quality"] = "saturated"
    elif snr < 3.0:
        out["quality"] = "non_detection"
    elif edge:
        # Borde del detector o λ fuera del rango nominal: flujo poco fiable (se muestra, pero no cuenta para variabilidad)
        out["quality"] = "warning"
    elif (np.isfinite(fit_quality) and fit_quality > 3.0 * max(1.0, abs(snr) / 30.0)) or out["flags"]:
        # Para fuentes muy brillantes el residuo está dominado por el error sistemático de la PSF (~3 %)
        out["quality"] = "warning"
    else:
        out["quality"] = "good"
    return out


def fit_source_position(cut: Dict[str, Any], ra_guess: float, dec_guess: float, neighbors: Optional[List[Tuple[float, float]]] = None, search_px: float = 1.5) -> Optional[Dict[str, Any]]:
    """
    Centroide por ajuste de ePSF (búsqueda en dos etapas: paso 0.25 px y luego 0.05 px) alrededor de una posición
    inicial. Devuelve RA/Dec medidas, flujo, S/N y la incertidumbre de posición aproximada (FWHM / (2.35·S/N)).
    """
    img, var, flg, w = cut["img"], cut["var"], cut["flags"], cut["wcs"]
    try:
        x0, y0 = [float(v) for v in w.world_to_pixel_values(ra_guess, dec_guess)]
    except Exception:
        return None
    ny, nx = img.shape
    if not (4 <= x0 < nx - 4 and 4 <= y0 < ny - 4):
        return None
    r = 6
    xi, yi = int(round(x0)), int(round(y0))
    ys0, ys1 = max(0, yi - r), min(ny, yi + r + 1)
    xs0, xs1 = max(0, xi - r), min(nx, xi + r + 1)
    st_img = img[ys0:ys1, xs0:xs1].astype(np.float64)
    st_var = var[ys0:ys1, xs0:xs1].astype(np.float64)
    st_flg = flg[ys0:ys1, xs0:xs1].astype(np.int64)
    ys, xs = np.mgrid[ys0:ys1, xs0:xs1]
    good = np.isfinite(st_img) & np.isfinite(st_var) & (st_var > 0) & ((st_flg & PHOT_MASK) == 0)
    fwhm_px = float(cut["meta"].get("psf_fwhm", 7.5) or 7.5) / PIX_SCALE_NATIVE
    psf = cut.get("psf")
    extra = []
    for (ra_n, dec_n) in neighbors or []:
        try:
            xn, yn = [float(v) for v in w.world_to_pixel_values(ra_n, dec_n)]
        except Exception:
            continue
        if xs0 - 3 <= xn <= xs1 + 2 and ys0 - 3 <= yn <= ys1 + 2 and np.hypot(xn - x0, yn - y0) >= 0.8:
            extra.append(psf_native_model(psf, xs, ys, xn, yn, fwhm_px))
    best = None
    for step, half in ((0.25, search_px), (0.05, 0.3)):
        cx, cy = (x0, y0) if best is None else (best[0], best[1])
        for dx in np.arange(-half, half + 1e-9, step):
            for dy in np.arange(-half, half + 1e-9, step):
                res = _wls_flux(st_img, st_var, good, psf_native_model(psf, xs, ys, cx + dx, cy + dy, fwhm_px), extra)
                if res is not None and res[0] > 0 and (best is None or res[3] < best[2]):
                    best = (cx + dx, cy + dy, res[3], res[0], res[1])
    if best is None:
        return None
    xb, yb, chi2, F, sF = best
    om = pixel_solid_angle_sr(w, xb, yb)
    f_ujy = F * om * 1e12
    err = float(np.hypot(sF * om * 1e12, SYSTEMATIC_FRAC * abs(f_ujy)))
    snr = f_ujy / err if err > 0 else 0.0
    rr, dd = [float(v) for v in w.pixel_to_world_values(xb, yb)]
    lam, bw, _, _ = cut_wavelength_at(cut, rr, dd)
    sat_bits = int(np.bitwise_or.reduce(st_flg[np.hypot(xs - xb, ys - yb) <= 2.5].ravel())) & SATURATION_MASK
    return {"ra": rr, "dec": dd, "flux_ujy": f_ujy, "err_ujy": err, "snr": snr, "wavelength_um": lam,
            "pos_err_arcsec": float(max(fwhm_px * PIX_SCALE_NATIVE / (2.35 * max(snr, 1.0)), 0.05 * PIX_SCALE_NATIVE)),
            "saturated": bool(sat_bits), "mjd": float(cut["meta"].get("mjd_avg") or cut["row"]["t_min"]),
            "lvf_edge": lvf_edge_reason(cut, xb, yb, lam), "obs_id": cut["row"].get("obs_id")}


# ---------------------------------------------------------------------------
# Agrupación temporal y grilla común
# ---------------------------------------------------------------------------
def group_exposures_into_epochs(rows: List[Dict[str, Any]], gap_days: float = 20.0, max_span_days: Optional[float] = None) -> List[List[Dict[str, Any]]]:
    """
    Agrupa exposiciones ordenadas en épocas separadas por más de `gap_days` días. En zonas de cobertura
    continua (polos eclípticos) los grupos largos se dividen en ventanas de `max_span_days`.
    """
    if not rows:
        return []
    if max_span_days is None:
        max_span_days = max(20.0, gap_days * 0.7)
    sorted_rows = sorted(rows, key=lambda r: r["t_min"])
    groups: List[List[Dict[str, Any]]] = [[sorted_rows[0]]]
    for r in sorted_rows[1:]:
        if r["t_min"] - groups[-1][-1]["t_min"] > gap_days:
            groups.append([r])
        else:
            groups[-1].append(r)
    out: List[List[Dict[str, Any]]] = []
    for g in groups:
        if g[-1]["t_min"] - g[0]["t_min"] <= 1.5 * max_span_days:
            out.append(g)
            continue
        start = g[0]["t_min"]
        cur: List[Dict[str, Any]] = []
        for r in g:
            if cur and r["t_min"] - start > max_span_days:
                out.append(cur)
                cur, start = [r], r["t_min"]
            else:
                cur.append(r)
        if cur:
            out.append(cur)
    return out


def _select_band_balanced(grp: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    """Hasta `k` exposiciones por época, repartidas entre detectores y espaciadas en el tiempo."""
    if len(grp) <= k:
        return list(grp)
    by_band: Dict[str, List[Dict[str, Any]]] = {}
    for r in sorted(grp, key=lambda x: x["t_min"]):
        by_band.setdefault(r["band"], []).append(r)
    bands_sorted = sorted(by_band)
    quota = {b: 0 for b in bands_sorted}
    remaining = k
    while remaining > 0 and any(quota[b] < len(by_band[b]) for b in bands_sorted):
        for b in bands_sorted:
            if remaining <= 0:
                break
            if quota[b] < len(by_band[b]):
                quota[b] += 1
                remaining -= 1
    picked: List[Dict[str, Any]] = []
    for b in bands_sorted:
        lst = by_band[b]
        if quota[b] <= 0:
            continue
        idx = sorted(set(np.linspace(0, len(lst) - 1, quota[b]).round().astype(int).tolist()))
        picked.extend(lst[i] for i in idx)
    return sorted(picked, key=lambda x: x["t_min"])


_CUBE_MEMO: "Dict[str, Dict[str, Any]]" = {}
_CUBE_MEMO_ORDER: List[str] = []
MAX_EPOCHS = 8


def make_common_wcs(ra: float, dec: float, size_deg: float, oversample: float = 2.0) -> Tuple[WCS, Tuple[int, int], float]:
    """Grilla tangencial común (Norte arriba, Este a la izquierda), muestreada a 6.15″/oversample."""
    pix_arcsec = PIX_SCALE_NATIVE / oversample
    raw_n = round(size_deg * 3600.0 / pix_arcsec)
    n = int(np.clip(raw_n, 36, 180))
    if n % 2 == 1:
        n += 1
    if raw_n > 180 or raw_n < 36:
        pix_arcsec = float((size_deg * 3600.0) / n)
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [n / 2.0 + 0.5, n / 2.0 + 0.5]
    w.wcs.cdelt = [-pix_arcsec / 3600.0, pix_arcsec / 3600.0]
    return w, (n, n), pix_arcsec


# ---------------------------------------------------------------------------
# Reporte astrométrico IAU MPC (formato de 80 columnas para observaciones desde satélite)
# Especificación: https://www.minorplanetcenter.net/iau/info/SatelliteObs.html
# ---------------------------------------------------------------------------
def _mpc_date_field(mjd_utc: float) -> str:
    t = Time(float(mjd_utc), format="mjd", scale="utc")
    ymd = t.ymdhms
    day_frac = float(ymd.day) + (float(ymd.hour) * 3600.0 + float(ymd.minute) * 60.0 + float(ymd.second)) / 86400.0
    return f"{int(ymd.year):04d} {int(ymd.month):02d} {day_frac:09.6f}"  # 17 caracteres (col. 16–32)


def _mpc_ra_dec_fields(ra_deg: float, dec_deg: float) -> Tuple[str, str]:
    c = SkyCoord(ra=float(ra_deg) * u.deg, dec=float(dec_deg) * u.deg)
    h, m, s = c.ra.hms
    if round(s, 2) >= 60.0:
        s, m = 0.0, m + 1
    if m >= 60:
        m, h = 0, (h + 1) % 24
    ra_s = f"{int(h):02d} {int(m):02d} {s:05.2f}".ljust(12)  # col. 33–44
    sign = "+" if dec_deg >= 0 else "-"
    d_abs = abs(float(dec_deg))
    dd = int(d_abs)
    mm_tot = (d_abs - dd) * 60.0
    mm = int(mm_tot)
    ss = (mm_tot - mm) * 60.0
    if round(ss, 1) >= 60.0:
        ss, mm = 0.0, mm + 1
    if mm >= 60:
        mm, dd = 0, dd + 1
    dec_s = f"{sign}{dd:02d} {mm:02d} {ss:04.1f}".ljust(12)  # col. 45–56
    return ra_s, dec_s


def _mpc_vector_field(v_km: float) -> str:
    """Componente del vector geocéntrico en km: signo en la primera columna y punto decimal en la 7.ª (|v| < 100 000 km)."""
    sign = "+" if v_km >= 0 else "-"
    return f"{sign}{abs(v_km):10.4f}"  # 11 caracteres


def format_mpc_satellite_obs(desig: str, mjd_utc_mid: float, ra_deg: float, dec_deg: float, sc_pos_km: Sequence[float], obs_code: str = MPC_OBS_CODE_SPHEREX) -> List[str]:
    """
    Dos registros de 80 columnas para una observación desde satélite ("S" en col. 15 y "s" en col. 15
    con el vector geocéntrico en km, sistema ecuatorial J2000). La magnitud se deja en blanco porque
    el formato de 80 columnas no tiene códigos de banda para los canales de 0.75–5 µm de SPHEREx.
    """
    d = re.sub(r"[^A-Za-z0-9]", "", desig or "SPX0001")[:7].upper().ljust(7)
    c1_12 = (" " * 5 + d)[:12]
    date = _mpc_date_field(mjd_utc_mid)
    ra_s, dec_s = _mpc_ra_dec_fields(ra_deg, dec_deg)
    code = (obs_code or MPC_OBS_CODE_SPHEREX)[:3].rjust(3)
    line1 = c1_12 + " " + " " + "S" + date + ra_s + dec_s + " " * 9 + " " * 6 + " " * 6 + code
    x, y, z = [float(v) for v in sc_pos_km]
    line2 = (
        c1_12 + " " + " " + "s" + date + "1" + " "
        + _mpc_vector_field(x) + " " + _mpc_vector_field(y) + " " + _mpc_vector_field(z)
        + " " * 8 + code
    )
    return [line1[:80].ljust(80), line2[:80].ljust(80)]


def spacecraft_position_mid(meta: Dict[str, Any]) -> Optional[List[float]]:
    """Posición geocéntrica de SPHEREx a mitad de exposición: interpolación de Hermite con posiciones y velocidades de inicio y fin."""
    try:
        p0 = np.array(meta["sc_start"], float)
        p1 = np.array(meta["sc_end"], float)
        v0 = np.array(meta["vsc_start"], float)
        v1 = np.array(meta["vsc_end"], float)
        T = float(meta.get("t_span_s") or EXPTIME_S)
        if not (np.all(np.isfinite(p0)) and np.all(np.isfinite(p1))):
            return None
        if not (np.all(np.isfinite(v0)) and np.all(np.isfinite(v1))):
            return list(0.5 * (p0 + p1))
        return list(0.5 * (p0 + p1) + (T / 8.0) * (v0 - v1))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# HEALPix NESTED (Górski et al. 2005) — algoritmo de referencia de HEALPix C++ `ang2pix_nest_z_phi`.
# Corrección nov. 2026: la versión anterior recortaba jp/jm a 4·nside−1 y fallaba en ~12 % del cielo
# (RA 270°–360°, |Dec| < 41.8°). Validado contra astropy-healpix en 200 000 puntos aleatorios.
# ---------------------------------------------------------------------------
def _interleave_bits(ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
    res = np.zeros_like(ix)
    for b in range(16):
        res |= ((ix >> b) & 1) << (2 * b)
        res |= ((iy >> b) & 1) << (2 * b + 1)
    return res


def ang2pix_nest_vec(nside: int, ra_deg: np.ndarray, dec_deg: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Devuelve (face_num, ix, iy) HEALPix NESTED para cualquier grilla (RA, Dec)."""
    order = int(round(np.log2(nside)))
    z = np.sin(np.deg2rad(np.asarray(dec_deg, dtype=np.float64)))
    za = np.abs(z)
    tt = np.mod(2.0 * np.deg2rad(np.mod(np.asarray(ra_deg, dtype=np.float64), 360.0)) / np.pi, 4.0)
    # Región ecuatorial
    temp1 = nside * (0.5 + tt)
    temp2 = nside * (z * 0.75)
    jp = (temp1 - temp2).astype(np.int64)
    jm = (temp1 + temp2).astype(np.int64)
    ifp = jp >> order
    ifm = jm >> order
    f_eq = np.where(ifp == ifm, ifp | 4, np.where(ifp < ifm, ifp, ifm + 8))
    ix_eq = jm & (nside - 1)
    iy_eq = nside - (jp & (nside - 1)) - 1
    # Casquetes polares
    ntt = np.minimum(tt.astype(np.int64), 3)
    tp = tt - ntt
    tmp = nside * np.sqrt(3.0 * np.maximum(1.0 - za, 0.0))
    jp_p = np.minimum((tp * tmp).astype(np.int64), nside - 1)
    jm_p = np.minimum(((1.0 - tp) * tmp).astype(np.int64), nside - 1)
    f_pol = np.where(z >= 0, ntt, ntt + 8)
    ix_pol = np.where(z >= 0, nside - jm_p - 1, jp_p)
    iy_pol = np.where(z >= 0, nside - jp_p - 1, jm_p)
    eq = za <= (2.0 / 3.0)
    return np.where(eq, f_eq, f_pol), np.where(eq, ix_eq, ix_pol), np.where(eq, iy_eq, iy_pol)


def ang2pix_nest_scalar(nside: int, ra_deg: float, dec_deg: float) -> int:
    """Índice HEALPix NESTED de (RA, Dec) ICRS en grados (p. ej. ra=60.8109955, dec=51.3404038, nside=32 → 445)."""
    f, ix, iy = ang2pix_nest_vec(nside, np.array([ra_deg]), np.array([dec_deg]))
    return int(f[0] * nside * nside + _interleave_bits(ix, iy)[0])


# ---------------------------------------------------------------------------
# Cubo All-Sky oficial SPHEREx DR1 (DOI 10.26131/IRSA679): HiPS PNG (visualización) y FITS (ciencia)
# ---------------------------------------------------------------------------
IRSA_SPHEREX_HIPS_URL = "https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube"
S3_DR1_HIPS5_CUBE_BASE = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/dr1/hips5_cube/hips_20261026"
IBE_DR1_HIPS5_CUBE_BASE = "https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/hips5_cube/hips_20261026"
DR1_TILE_NPIX = 512
DR1_PIX_ARCSEC = 12.88  # hips_pixel_scale oficial = 0.0035786°
DR1_PIX_SR = 4.0 * np.pi / (12.0 * 4 ** 14)  # píxel HEALPix de orden 14 (área igual): 3.901e-9 sr
DR1_PLANE_BYTES = DR1_TILE_NPIX * DR1_TILE_NPIX * 4
DR1_IMAGE_OFFSET = 8640  # verificado en las cabeceras oficiales
# Desplazamientos medidos en un archivo oficial (los datos se rellenan a múltiplos de 2880 bytes);
# se recalculan por tesela con `_dr1_offsets` y estos valores solo son el respaldo.
DR1_DEFAULT_OFFSETS = {"IMAGE": 8640, "NHITS": 106971840, "FLAGS": 213940800}

# Canales nominales (data_cube_crval3_arr oficial). Los índices 50 y 51 (canal 17 de D3 y canal 1 de D4) están vacíos en DR1.
SPHEREX_DR1_WAVELENGTHS_UM: List[float] = [
    0.753, 0.771, 0.790, 0.809, 0.828, 0.848, 0.868, 0.889, 0.910, 0.932, 0.955, 0.978, 1.001, 1.025, 1.050, 1.075, 1.102,
    1.113, 1.139, 1.167, 1.195, 1.224, 1.254, 1.284, 1.315, 1.346, 1.378, 1.412, 1.446, 1.481, 1.517, 1.554, 1.592, 1.631,
    1.656, 1.695, 1.735, 1.775, 1.818, 1.861, 1.905, 1.949, 1.995, 2.041, 2.089, 2.139, 2.189, 2.240, 2.292, 2.345, 2.399,
    2.445, 2.506, 2.575, 2.646, 2.719, 2.794, 2.871, 2.951, 3.033, 3.118, 3.204, 3.293, 3.383, 3.476, 3.570, 3.667, 3.768,
    3.833, 3.867, 3.901, 3.935, 3.970, 4.005, 4.040, 4.076, 4.112, 4.148, 4.184, 4.220, 4.257, 4.294, 4.331, 4.368, 4.405,
    4.435, 4.467, 4.500, 4.533, 4.566, 4.600, 4.635, 4.669, 4.704, 4.739, 4.773, 4.808, 4.843, 4.879, 4.915, 4.951, 4.988,
]
DR1_BLANK_CHANNELS = (50, 51)
BAND_TO_DR1_CHANNELS: Dict[str, List[int]] = {
    "D1": list(range(0, 17)),
    "D2": list(range(17, 34)),
    "D3": list(range(34, 50)),
    "D4": list(range(52, 68)),
    "D5": list(range(68, 85)),
    "D6": list(range(85, 102)),
}
_DR1_CHANNEL_TABLE: Optional[List[Dict[str, Any]]] = None


def _dr1_tile_urls(ipix: int) -> Tuple[str, str]:
    dirid = (ipix // 10000) * 10000
    return (
        f"{S3_DR1_HIPS5_CUBE_BASE}/Norder5/Dir{dirid}/Npix{ipix}_cube.fits",
        f"{IBE_DR1_HIPS5_CUBE_BASE}/Norder5/Dir{dirid}/Npix{ipix}_cube.fits",
    )


def _range_get(urls: Sequence[str], b0: int, b1: int, timeout: float = 20.0) -> Optional[bytes]:
    for u_try in urls:
        try:
            r = _HTTP_POOL.get(u_try, headers={"Range": f"bytes={b0}-{b1}"}, timeout=timeout)
            if r.status_code in (200, 206) and len(r.content) == (b1 - b0 + 1):
                return r.content
        except Exception:
            continue
    return None


def dr1_channel_table() -> List[Dict[str, Any]]:
    """Tabla oficial SPECTRAL_CHANNELS del cubo DR1 (λ central, bordes, R y ancho de banda por canal)."""
    global _DR1_CHANNEL_TABLE
    if _DR1_CHANNEL_TABLE is not None:
        return _DR1_CHANNEL_TABLE
    cpath = os.path.join(CACHE_DIR, "dr1spec", "spectral_channels.json")
    if os.path.exists(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                _DR1_CHANNEL_TABLE = json.load(f)
                return _DR1_CHANNEL_TABLE
        except Exception:
            pass
    rows: List[Dict[str, Any]] = []
    try:
        url = _dr1_tile_urls(10226)[0]
        with fits.open(url, use_fsspec=True, fsspec_kwargs={"block_size": 64 * 1024}) as h:
            d = h["SPECTRAL_CHANNELS"].data
            for i, r in enumerate(d):
                rows.append({
                    "ch": i, "detector": int(r["DETECTOR"]), "subchan": int(r["SUBCHAN"]),
                    "wavelength_um": float(r["WAVELENGTH"]), "wl_min_um": float(r["WL_MIN"]), "wl_max_um": float(r["WL_MAX"]),
                    "R": float(r["R"]), "bandwidth_um": float(r["BANDWIDTH"]),
                })
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(rows, f)
    except Exception:
        rows = [
            {"ch": i, "detector": i // 17 + 1, "subchan": i % 17 + 1, "wavelength_um": lam,
             "wl_min_um": lam * (1 - 0.5 / DETECTOR_INFO[f"D{i // 17 + 1}"]["R"]), "wl_max_um": lam * (1 + 0.5 / DETECTOR_INFO[f"D{i // 17 + 1}"]["R"]),
             "R": float(DETECTOR_INFO[f"D{i // 17 + 1}"]["R"]), "bandwidth_um": lam / DETECTOR_INFO[f"D{i // 17 + 1}"]["R"]}
            for i, lam in enumerate(SPHEREX_DR1_WAVELENGTHS_UM)
        ]
    _DR1_CHANNEL_TABLE = rows
    return rows


def dr1_channel_for_wavelength(lam_um: float) -> Optional[int]:
    if lam_um is None or not np.isfinite(lam_um):
        return None
    tbl = dr1_channel_table()
    best = min(tbl, key=lambda r: abs(r["wavelength_um"] - lam_um))
    return int(best["ch"])


_ALLSKY_EQUIRECT_LUT: Optional[Tuple[np.ndarray, np.ndarray]] = None
_ALLSKY_PNG_MEMO: Dict[str, bytes] = {}


def _get_allsky_equirect_lut(width: int = 1440, height: int = 720) -> Tuple[np.ndarray, np.ndarray]:
    """Tabla de índices (fila, columna) hacia el sprite oficial Norder3/Allsky.png (27 × 29 teselas de 64×64)."""
    global _ALLSKY_EQUIRECT_LUT
    if _ALLSKY_EQUIRECT_LUT is not None:
        return _ALLSKY_EQUIRECT_LUT
    ra_1d = np.linspace(0.0, 360.0, width, endpoint=False)
    dec_1d = np.linspace(89.95, -89.95, height)
    ra_g, dec_g = np.meshgrid(ra_1d, dec_1d)
    face, ix, iy = ang2pix_nest_vec(512, ra_g, dec_g)
    ix_t = ix >> 6
    iy_t = iy >> 6
    res_t = np.zeros_like(ix_t)
    for b in range(3):
        res_t |= ((ix_t >> b) & 1) << (2 * b)
        res_t |= ((iy_t >> b) & 1) << (2 * b + 1)
    tile_idx = face * 64 + res_t
    sub_r = ix & 63
    sub_c = iy & 63
    allsky_row = (tile_idx // 27) * 64 + sub_r
    allsky_col = (tile_idx % 27) * 64 + sub_c
    _ALLSKY_EQUIRECT_LUT = (allsky_row.astype(np.int32), allsky_col.astype(np.int32))
    return _ALLSKY_EQUIRECT_LUT


def _fetch_official_allsky_sprite(ch: int) -> np.ndarray:
    """Descarga y cachea el sprite oficial Norder3/Allsky_{ch}.png (PNG de visualización, estiramiento asinh 0–40 MJy/sr)."""
    ch_clamped = int(np.clip(ch, 0, 101))
    if ch_clamped in DR1_BLANK_CHANNELS:
        ch_clamped = 52
    cpath = os.path.join(CACHE_DIR, "hips", f"spherex_dr1_allsky_ch{ch_clamped:03d}.png")
    raw_bytes: Optional[bytes] = None
    if os.path.exists(cpath):
        try:
            with open(cpath, "rb") as f:
                raw_bytes = f.read()
        except Exception:
            raw_bytes = None
    if not raw_bytes:
        fname = "Allsky.png" if ch_clamped == 0 else f"Allsky_{ch_clamped}.png"
        r = _HTTP_POOL.get(f"{IRSA_SPHEREX_HIPS_URL}/Norder3/{fname}", timeout=20)
        r.raise_for_status()
        raw_bytes = r.content
        try:
            with open(cpath, "wb") as f:
                f.write(raw_bytes)
        except Exception:
            pass
    im = Image.open(io.BytesIO(raw_bytes)).convert("L")
    return np.array(im, dtype=np.uint8)


def get_official_spherex_allsky_equirect_png(channel_spec: str = "rgb_dr1") -> bytes:
    """
    Mapa equirectangular 360°×180° (1440×720) del cubo All-Sky oficial DR1 (solo visualización:
    los PNG HiPS tienen un estiramiento fijo asinh de 0–40 MJy/sr). `rgb_dr1` = R 4.669 µm (canal 92),
    G 3.293 µm (canal 62, PAH) y B 0.910 µm (canal 8); o cualquier canal `chN`.
    """
    key = (channel_spec or "rgb_dr1").strip().lower()
    if key in _ALLSKY_PNG_MEMO:
        return _ALLSKY_PNG_MEMO[key]
    disk_cache = os.path.join(CACHE_DIR, "hips", f"equirect_v2_{key}.png")
    if os.path.exists(disk_cache):
        try:
            with open(disk_cache, "rb") as f:
                b_out = f.read()
            _ALLSKY_PNG_MEMO[key] = b_out
            return b_out
        except Exception:
            pass
    r_lut, c_lut = _get_allsky_equirect_lut(1440, 720)
    if key == "rgb_dr1":
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_b = ex.submit(_fetch_official_allsky_sprite, 8)
            f_g = ex.submit(_fetch_official_allsky_sprite, 62)
            f_r = ex.submit(_fetch_official_allsky_sprite, 92)
            sp_b = f_b.result()[r_lut, c_lut]
            sp_g = f_g.result()[r_lut, c_lut]
            sp_r = f_r.result()[r_lut, c_lut]
        im_out = Image.fromarray(np.stack([sp_r, sp_g, sp_b], axis=-1).astype(np.uint8), mode="RGB")
    else:
        m = re.search(r"(\d+)", key)
        ch_num = int(m.group(1)) if m else 62
        sp = _fetch_official_allsky_sprite(ch_num)[r_lut, c_lut]
        im_out = Image.fromarray(sp, mode="L").convert("RGB")
    buf = io.BytesIO()
    im_out.save(buf, format="PNG", optimize=False)
    b_out = buf.getvalue()
    _ALLSKY_PNG_MEMO[key] = b_out
    try:
        with open(disk_cache, "wb") as f:
            f.write(b_out)
    except Exception:
        pass
    return b_out


def fetch_official_hips_tile_bytes(channel: int, tail_path: str) -> Tuple[bytes, str]:
    """Proxy HiPS oficial para Aladin Lite v3 (reescribe `Npix{p}.png` → `Npix{p}_{canal}.png`)."""
    ch_clamped = int(np.clip(channel, 0, 101))
    if ch_clamped in DR1_BLANK_CHANNELS:
        ch_clamped = 52
    clean_tail = tail_path.lstrip("/")
    if ".." in clean_tail:
        raise ValueError("Ruta HiPS no válida")
    if clean_tail == "properties":
        lam_um = SPHEREX_DR1_WAVELENGTHS_UM[ch_clamped]
        props = (
            "creator_did          = ivo://IPAC/P/SPHEREx/DR1/cube\n"
            f"obs_title            = SPHEREx DR1 All-Sky Cube (frame {ch_clamped}: {lam_um:.3f} um)\n"
            "hips_version         = 1.4\n"
            "hips_frame           = equatorial\n"
            "hips_order           = 5\n"
            "hips_order_min       = 0\n"
            "hips_tile_width      = 512\n"
            "hips_tile_format     = png\n"
            "dataproduct_type     = image\n"
            "moc_sky_fraction     = 1.000000\n"
        )
        return props.encode("utf-8"), "text/plain; charset=utf-8"
    if ch_clamped > 0 and clean_tail.endswith(".png"):
        if clean_tail.endswith("Allsky.png"):
            clean_tail = clean_tail[:-10] + f"Allsky_{ch_clamped}.png"
        else:
            m_npix = re.match(r"^(.*Npix\d+)\.png$", clean_tail)
            if m_npix:
                clean_tail = f"{m_npix.group(1)}_{ch_clamped}.png"
    safe_cache_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", f"ch{ch_clamped}_{clean_tail}")
    cpath = os.path.join(CACHE_DIR, "hips", safe_cache_name)
    if os.path.exists(cpath):
        try:
            with open(cpath, "rb") as f:
                return f.read(), "image/png" if clean_tail.endswith(".png") else "application/octet-stream"
        except Exception:
            pass
    r = _HTTP_POOL.get(f"{IRSA_SPHEREX_HIPS_URL}/{clean_tail}", timeout=15)
    r.raise_for_status()
    if clean_tail.endswith(".png"):
        try:
            with open(cpath, "wb") as f:
                f.write(r.content)
        except Exception:
            pass
    ctype = "image/png" if clean_tail.endswith(".png") else r.headers.get("Content-Type", "application/octet-stream")
    return r.content, ctype


_DR1_WCS_CACHE: Dict[int, WCS] = {}


def _fetch_dr1_hpx5_header_and_wcs(ipix: int) -> Tuple[fits.Header, WCS]:
    """Cabecera IMAGE (bytes 2880–8639) del cubo `Npix{ipix}_cube.fits` y su WCS celeste (RA---HPX / DEC--HPX)."""
    hdr_cache = os.path.join(CACHE_DIR, "cutouts", f"dr1_hpx5_Npix{ipix}_hdr.txt")
    raw_str: Optional[str] = None
    if os.path.exists(hdr_cache):
        try:
            with open(hdr_cache, "r", encoding="utf-8") as f:
                raw_str = f.read()
        except Exception:
            raw_str = None
    if not raw_str:
        content = _range_get(_dr1_tile_urls(ipix), 2880, DR1_IMAGE_OFFSET - 1, timeout=12)
        if content:
            raw_str = content.decode("ascii", errors="ignore")
            try:
                with open(hdr_cache, "w", encoding="utf-8") as f:
                    f.write(raw_str)
            except Exception:
                pass
    if not raw_str:
        raise RuntimeError(f"No se pudo leer la cabecera DR1 de Npix{ipix}")
    h1 = fits.Header.fromstring(raw_str)
    if int(h1.get("NPIX", ipix)) != int(ipix):
        raise RuntimeError(f"Cabecera DR1 inconsistente: NPIX={h1.get('NPIX')} ≠ {ipix}")
    # El eje 3 (WAVE-TAB) necesita la HDUList; para el WCS celeste se eliminan sus claves.
    for k in list(h1.keys()):
        if re.match(r"^(CTYPE|CUNIT|CRPIX|CDELT|CRVAL|CNAME|NAXIS)3$", k) or re.match(r"^(PV|PS)3_\d+$", k) or re.match(r"^PC(3_\d|\d_3)$", k):
            del h1[k]
    h1["NAXIS"] = 2
    h1["WCSAXES"] = 2
    w = WCS(h1)
    _DR1_WCS_CACHE[ipix] = w
    return h1, w


def _fetch_dr1_hpx5_plane_cached(ipix: int, ch: int) -> np.ndarray:
    """Plano IMAGE completo (512×512 float32, MJy/sr) de un canal del cubo DR1, por HTTP Range y con caché en disco."""
    ch_valid = int(np.clip(ch, 0, 101))
    if ch_valid in DR1_BLANK_CHANNELS:
        raise ValueError("Canal dicroico vacío en DR1")
    cpath = os.path.join(CACHE_DIR, "cutouts", f"dr1_hpx5_Npix{ipix}_ch{ch_valid:03d}.npy")
    if os.path.exists(cpath):
        try:
            return np.load(cpath)
        except Exception:
            pass
    b0 = DR1_IMAGE_OFFSET + ch_valid * DR1_PLANE_BYTES
    raw = _range_get(_dr1_tile_urls(ipix), b0, b0 + DR1_PLANE_BYTES - 1, timeout=25)
    if not raw:
        raise RuntimeError(f"No se pudo leer el plano DR1 Npix{ipix} canal {ch_valid}")
    arr = np.frombuffer(raw, dtype=">f4").astype(np.float32).reshape((DR1_TILE_NPIX, DR1_TILE_NPIX))
    try:
        np.save(cpath, arr)
    except Exception:
        pass
    return arr


def _dr1_tiles_covering(ra: float, dec: float, size_deg: float) -> List[int]:
    half = 0.5 * size_deg * 1.45
    cosd = max(np.cos(np.deg2rad(dec)), 0.05)
    pts = [(ra, dec)]
    for dx in (-half, 0.0, half):
        for dy in (-half, 0.0, half):
            pts.append(((ra + dx / cosd) % 360.0, float(np.clip(dec + dy, -89.999, 89.999))))
    return sorted({ang2pix_nest_scalar(32, p[0], p[1]) for p in pts})


def build_dr1_static_image(ra: float, dec: float, bands: List[str], common_wcs: WCS, shape: Tuple[int, int]) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
    """
    Imagen estática DR1 (media de 4 canales por banda pedida) reproyectada a la grilla común, cubriendo
    las teselas HEALPix necesarias. No tiene información temporal: es UNA sola imagen.
    """
    norm_bands = [b for b in bands if b in BAND_TO_DR1_CHANNELS] or ["D1"]
    chans: List[int] = []
    for b in norm_bands:
        cl = BAND_TO_DR1_CHANNELS[b]
        chans.extend(cl[i] for i in np.linspace(1, len(cl) - 2, 4).round().astype(int))
    tiles = _dr1_tiles_covering(ra, dec, float(abs(common_wcs.wcs.cdelt[1]) * shape[0]))
    stack: List[np.ndarray] = []
    for ipix in tiles:
        try:
            _, w_hpx = _fetch_dr1_hpx5_header_and_wcs(ipix)
        except Exception:
            continue
        for ch in chans:
            try:
                plane = _fetch_dr1_hpx5_plane_cached(ipix, ch)
                rp, fp = reproject_interp((plane, w_hpx), common_wcs, shape_out=shape, order="bilinear")
                rp = np.where(fp > 0, rp, np.nan)
                stack.append(rp.astype(np.float32))
            except Exception:
                continue
    if not stack:
        return None, {"tiles": tiles, "channels": chans}
    with np.errstate(all="ignore"):
        img = np.nanmean(np.array(stack), axis=0).astype(np.float32)
    lams = [SPHEREX_DR1_WAVELENGTHS_UM[c] for c in chans]
    return img, {"tiles": tiles, "channels": chans, "wavelengths_um": lams}


# ---------------------------------------------------------------------------
# Espectro DR1 de 102 canales en una posición (fotometría de apertura sobre el cubo oficial)
# ---------------------------------------------------------------------------
BAND_FEATURES = [
    {"id": "H2O_3.0", "label": "H₂O 3.0 µm", "band": (2.95, 3.15), "cont": ((2.20, 2.40), (3.75, 3.95))},
    {"id": "CH4_3.3", "label": "CH₄ 3.3 µm", "band": (3.27, 3.37), "cont": ((2.20, 2.40), (3.75, 3.95))},
    {"id": "CO2_4.27", "label": "CO₂ 4.27 µm", "band": (4.24, 4.31), "cont": ((4.10, 4.18), (4.36, 4.42))},
    {"id": "CO_4.67", "label": "CO 4.67 µm", "band": (4.64, 4.70), "cont": ((4.50, 4.58), (4.76, 4.86))},
]

FEATURE_INTERPRETATION = {
    "brown_dwarf": ("Absorción de GAS molecular en la atmósfera de la enana marrón (no es hielo).", "Molecular GAS absorption in the brown-dwarf atmosphere (not ice)."),
    "star": ("Absorción de gas en la fotosfera estelar fría (no es hielo).", "Gas absorption in the cool stellar photosphere (not ice)."),
    "variable": ("Bandas moleculares de gas en la atmósfera/envoltura estelar; cambian con la pulsación o el oscurecimiento (no es hielo).", "Molecular gas bands in the stellar atmosphere/envelope; they change with pulsation or dimming (not ice)."),
    "generic": ("Profundidad APARENTE de banda. Puede deberse a hielo (fuente tras una nube molecular o protoestrella) o a gas en una atmósfera fría: hace falta contexto para decidir.", "APPARENT band depth. It may come from ice (source behind a molecular cloud or protostar) or from gas in a cool atmosphere: context is needed to decide."),
}


_DR1_OFFSETS_CACHE: Dict[int, Dict[str, int]] = {}


def _dr1_offsets(ipix: int) -> Dict[str, int]:
    """Desplazamientos en bytes de los datos IMAGE/NHITS/FLAGS de una tesela (leídos de sus cabeceras y cacheados)."""
    if ipix in _DR1_OFFSETS_CACHE:
        return _DR1_OFFSETS_CACHE[ipix]
    cpath = os.path.join(CACHE_DIR, "dr1spec", f"offsets_{ipix}.json")
    if os.path.exists(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                _DR1_OFFSETS_CACHE[ipix] = json.load(f)
                return _DR1_OFFSETS_CACHE[ipix]
        except Exception:
            pass
    offs = dict(DR1_DEFAULT_OFFSETS)
    try:
        with fits.open(_dr1_tile_urls(ipix)[0], use_fsspec=True, fsspec_kwargs={"block_size": 32 * 1024}) as h:
            for name in ("IMAGE", "NHITS", "FLAGS"):
                offs[name] = int(h[name]._data_offset)
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(offs, f)
    except Exception:
        pass
    _DR1_OFFSETS_CACHE[ipix] = offs
    return offs


def _dr1_read_rows(ipix: int, offset: int, dtype: str, ch: int, y0: int, y1: int) -> Optional[np.ndarray]:
    b0 = offset + ch * DR1_PLANE_BYTES + y0 * DR1_TILE_NPIX * 4
    b1 = offset + ch * DR1_PLANE_BYTES + (y1 + 1) * DR1_TILE_NPIX * 4 - 1
    raw = _range_get(_dr1_tile_urls(ipix), b0, b1, timeout=20)
    if raw is None:
        return None
    return np.frombuffer(raw, dtype=dtype).reshape((y1 - y0 + 1, DR1_TILE_NPIX))


def compute_band_depths(points: List[Dict[str, Any]], object_kind: str = "generic") -> List[Dict[str, Any]]:
    """
    Profundidad aparente τ = −ln(F_banda / F_continuo) con un continuo de LEY DE POTENCIAS (recta en
    log F – log λ) ajustado a ventanas a ambos lados de la banda. Requiere ≥2 puntos válidos (S/N ≥ 3, no
    saturados) en cada ventana y ≥1 en la banda; si no, devuelve `tau = None` con el motivo. Un τ negativo
    significativo indica que la banda está POR ENCIMA del continuo interpolado (pico de la SED o emisión):
    no es absorción y se informa como tal.
    """
    interp = FEATURE_INTERPRETATION.get(object_kind, FEATURE_INTERPRETATION["generic"])
    good = [p for p in points if p.get("flux_ujy") is not None and p.get("snr") is not None and p["snr"] >= 3 and p.get("quality") not in ("saturated", "masked", "no_coverage")]
    out: List[Dict[str, Any]] = []
    for feat in BAND_FEATURES:
        b_lo, b_hi = feat["band"]
        (c1a, c1b), (c2a, c2b) = feat["cont"]
        inb = [p for p in good if b_lo <= p["wavelength_um"] <= b_hi]
        c1 = [p for p in good if c1a <= p["wavelength_um"] <= c1b]
        c2 = [p for p in good if c2a <= p["wavelength_um"] <= c2b]
        entry: Dict[str, Any] = {"id": feat["id"], "label": feat["label"], "band_um": [b_lo, b_hi], "tau": None, "tau_err": None, "significant": False,
                                 "n_band": len(inb), "n_cont": len(c1) + len(c2), "interpretation_es": interp[0], "interpretation_en": interp[1]}
        if len(inb) < 1 or len(c1) < 2 or len(c2) < 2:
            entry["reason_es"] = "Muestreo insuficiente (se necesitan ≥2 puntos fiables en cada ventana de continuo y ≥1 en la banda)."
            entry["reason_en"] = "Insufficient sampling (≥2 reliable points in each continuum window and ≥1 in the band are needed)."
            out.append(entry)
            continue
        cont = [p for p in (c1 + c2) if p["flux_ujy"] > 0]
        inb = [p for p in inb if p["flux_ujy"] > 0]
        if len(cont) < 4 or not inb:
            entry["reason_es"] = "Flujos no positivos en el continuo o en la banda: no se puede calcular τ."
            entry["reason_en"] = "Non-positive continuum or band fluxes: τ cannot be computed."
            out.append(entry)
            continue
        # Continuo de ley de potencias (recta en log F – log λ): una SED estelar sin absorción da τ ≈ 0.
        # (Un continuo lineal en F sobrestima el continuo de una cola de Rayleigh–Jeans y crearía bandas falsas.)
        x_c = np.log([p["wavelength_um"] for p in cont])
        y_c = np.log([p["flux_ujy"] for p in cont])
        e_c = np.array([p["err_ujy"] / p["flux_ujy"] for p in cont])
        wgt = 1.0 / np.maximum(e_c, 1e-4) ** 2
        A = np.stack([np.ones_like(x_c), x_c], axis=1)
        cov = np.linalg.inv(A.T @ (A * wgt[:, None]))
        coef = cov @ (A.T @ (y_c * wgt))
        y_b = np.log([p["flux_ujy"] for p in inb])
        e_b = np.array([p["err_ujy"] / p["flux_ujy"] for p in inb])
        wb = 1.0 / np.maximum(e_b, 1e-4) ** 2
        lnfb = float(np.sum(y_b * wb) / np.sum(wb))
        slnfb = float(np.sqrt(1.0 / np.sum(wb)))
        xb = float(np.sum(np.log([p["wavelength_um"] for p in inb]) * wb) / np.sum(wb))
        vec = np.array([1.0, xb])
        lnfc = float(vec @ coef)
        slnfc = float(np.sqrt(max(vec @ cov @ vec, 0.0)))
        fb, fc = float(np.exp(lnfb)), float(np.exp(lnfc))
        tau = lnfc - lnfb
        # Piso sistemático de 0.04 en τ (calibración relativa entre canales y forma real del continuo)
        tau_err = float(np.sqrt(slnfb ** 2 + slnfc ** 2 + 0.04 ** 2))
        entry.update({"tau": round(float(tau), 3), "tau_err": round(tau_err, 3), "f_band_ujy": round(fb, 2), "f_cont_ujy": round(fc, 2),
                      "significant": bool(tau >= 3 * tau_err), "above_continuum": bool(tau <= -3 * tau_err), "continuum": "power_law"})
        if entry["above_continuum"]:
            entry["reason_es"] = ("La banda está por encima del continuo de ley de potencias (τ < 0 a ≥3σ): la forma real de la SED "
                                  "entre las ventanas no es una ley de potencias (p. ej. el pico de 4 µm de las enanas T). No indica absorción.")
            entry["reason_en"] = ("The band lies above the power-law continuum (τ < 0 at ≥3σ): the real SED shape between the windows "
                                  "is not a power law (e.g. the 4 µm peak of T dwarfs). It does not indicate absorption.")
        out.append(entry)
    return out


def dr1_neighbors(ra: float, dec: float, radius_arcsec: float = 30.0, self_tol_arcsec: float = 2.0) -> Optional[List[Dict[str, Any]]]:
    """Fuentes Gaia DR3 (MAST, propagadas a la época media de DR1) dentro de la apertura DR1, excluyendo la propia fuente."""
    j_mid = float(Time(0.5 * (DR1_MJD_RANGE[0] + DR1_MJD_RANGE[1]), format="mjd").jyear)
    # Radio amplio: una estrella de alto movimiento propio puede estar a >100″ de su posición Gaia de 2016
    rows = _gaia_dr3_mast(ra, dec, (radius_arcsec + 240.0) / 3600.0)
    if rows is None:
        return None
    out = []
    self_g = None
    for g in rows:
        ra_e, de_e = _propagate_linear(g["ra"], g["dec"], g["pmra"], g["pmdec"], 2016.0, j_mid)
        sep = float(np.hypot(((ra_e - ra + 180) % 360 - 180) * np.cos(np.deg2rad(dec)), de_e - dec) * 3600.0)
        if sep <= self_tol_arcsec and g.get("gmag") is not None:
            self_g = g["gmag"] if self_g is None else min(self_g, g["gmag"])
        elif sep <= radius_arcsec:
            out.append({"id": g["id"], "gmag": g.get("gmag"), "sep_arcsec": round(sep, 1)})
    # Significativa: ≥ 10 % del brillo óptico de la propia fuente (o G < 20.5 si la fuente no está en Gaia)
    lim = (self_g + 2.5) if self_g is not None else 20.5
    for n in out:
        n["significant"] = bool(n.get("gmag") is not None and n["gmag"] < lim)
    return sorted(out, key=lambda r: r["sep_arcsec"])


def dr1_point_spectrum(ra: float, dec: float, object_kind: str = "generic", r_ap_px: float = 2.0) -> Dict[str, Any]:
    """
    Espectro de 0.75–5.0 µm en (ra, dec) a partir del cubo All-Sky DR1 oficial (102 canales, co-adición
    de 2025-04-24 a 2026-05-14). Fotometría de apertura (r = 2 px = 25.8″) con fondo en anillo de
    4–7 px, ángulo sólido HEALPix exacto, y banderas/NHITS del cubo para detectar saturación.
    Es un espectro promediado en el tiempo: no sirve para variabilidad.
    """
    ipix = ang2pix_nest_scalar(32, ra, dec)
    ckey = hashlib.md5(f"dr1spec_v6_{ra:.5f}_{dec:.5f}_{r_ap_px:.1f}".encode()).hexdigest()[:16]
    cpath = os.path.join(CACHE_DIR, "dr1spec", f"{ckey}.json")
    if os.path.exists(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached["band_depths"] = compute_band_depths(cached.get("channels", []), object_kind)
            return cached
        except Exception:
            pass
    _, w_hpx = _fetch_dr1_hpx5_header_and_wcs(ipix)
    xf, yf = [float(v) for v in w_hpx.world_to_pixel_values(ra, dec)]
    if not (0 <= xf < DR1_TILE_NPIX and 0 <= yf < DR1_TILE_NPIX):
        raise RuntimeError("La posición no cae dentro de la tesela DR1 calculada")
    yi = int(round(yf))
    r_out = 7
    y0 = max(0, yi - r_out - 1)
    y1 = min(DR1_TILE_NPIX - 1, yi + r_out + 1)
    edge = (xf < r_out + 1) or (xf > DR1_TILE_NPIX - r_out - 2) or (yf < r_out + 1) or (yf > DR1_TILE_NPIX - r_out - 2)
    tbl = dr1_channel_table()
    offs = _dr1_offsets(ipix)

    def _one(ch: int) -> Dict[str, Any]:
        info = tbl[ch]
        base = {"ch": ch, "detector": info["detector"], "subchan": info["subchan"], "wavelength_um": round(info["wavelength_um"], 4),
                "wl_min_um": round(info["wl_min_um"], 4), "wl_max_um": round(info["wl_max_um"], 4), "bandwidth_um": round(info["bandwidth_um"], 4),
                "R": info["R"], "band": f"D{info['detector']}", "flux_ujy": None, "err_ujy": None, "snr": None, "quality": "blank", "flags": []}
        if ch in DR1_BLANK_CHANNELS:
            return base
        img = _dr1_read_rows(ipix, offs["IMAGE"], ">f4", ch, y0, y1)
        yc0, yc1 = max(0, yi - 1), min(DR1_TILE_NPIX - 1, yi + 1)
        yn0, yn1 = max(0, yi - 4), min(DR1_TILE_NPIX - 1, yi + 4)
        nh = _dr1_read_rows(ipix, offs["NHITS"], ">i4", ch, yn0, yn1)
        fl = _dr1_read_rows(ipix, offs["FLAGS"], ">i4", ch, yc0, yc1)
        if img is None:
            base["quality"] = "fetch_error"
            return base
        img = img.astype(np.float64)
        yy, xx = np.mgrid[y0:y1 + 1, 0:DR1_TILE_NPIX]
        d = np.hypot(xx - xf, yy - yf)
        ap = d <= r_ap_px
        an = (d >= 4.0) & (d <= 7.0) & np.isfinite(img)
        core = (d <= 1.0)
        n_ap_nan = int(np.sum(ap & ~np.isfinite(img)))
        if np.sum(an) < 10:
            base["quality"] = "masked"
            return base
        bg = float(np.median(img[an]))
        sig_pix = float(1.4826 * np.median(np.abs(img[an] - bg)))
        apv = ap & np.isfinite(img)
        n_ap = int(np.sum(apv))
        flux = float(np.sum(img[apv] - bg)) * DR1_PIX_SR * 1e12
        stat = sig_pix * np.sqrt(max(n_ap, 1)) * DR1_PIX_SR * 1e12
        err = float(np.hypot(stat, SYSTEMATIC_FRAC * abs(flux)))
        core_nan = int(np.sum(core & ~np.isfinite(img)))
        bits = 0
        nh_min = None
        nh_dip = False
        xc0, xc1 = max(0, int(round(xf)) - 1), min(DR1_TILE_NPIX, int(round(xf)) + 2)
        if fl is not None:
            bits = int(np.bitwise_or.reduce(fl[:, xc0:xc1].ravel()))
        if nh is not None:
            yyn, xxn = np.mgrid[yn0:yn1 + 1, 0:DR1_TILE_NPIX]
            dn = np.hypot(xxn - xf, yyn - yf)
            core_nh = nh[dn <= 1.0]
            ring_nh = nh[(dn >= 3.0) & (dn <= 4.5)]
            if core_nh.size:
                nh_min = int(np.min(core_nh))
                # Si el núcleo recibió muchas menos entradas que su entorno, el cubo rechazó píxeles saturados de la fuente
                if ring_nh.size and float(np.median(ring_nh)) > 0 and nh_min < 0.6 * float(np.median(ring_nh)):
                    nh_dip = True
        snr = flux / err if err > 0 else 0.0
        quality = "good"
        if core_nan > 0 or (nh_min is not None and nh_min == 0):
            quality = "saturated"
        elif bits & (1 << _FLAG_BIT["OVERFLOW"]):
            quality = "warning"
        elif snr < 3:
            quality = "non_detection"
        base.update({"flux_ujy": round(flux, 2), "err_ujy": round(err, 2), "snr": round(snr, 2), "quality": quality,
                     "flags": flag_names(bits), "nhits_min": nh_min, "nhits_dip": nh_dip, "n_ap_nan": n_ap_nan, "bg_mjy_sr": round(bg, 5)})
        if snr >= 3 and flux > 0 and quality != "saturated":
            base["ab_mag"] = round(AB_ZP_UJY - 2.5 * np.log10(flux), 3)
        else:
            base["upper_limit_ujy"] = round(max(flux, 0.0) + 3 * err, 2)
        return base

    with ThreadPoolExecutor(max_workers=12) as ex:
        channels = list(ex.map(_one, range(102)))
    # Una caída de NHITS en el núcleo indica rechazo de píxeles saturados SOLO si el mismo detector muestra
    # saturación en otros canales (OVERFLOW o núcleo vacío en ≥ 3 canales); si no, es una variación de cobertura.
    for det in range(1, 7):
        det_ch = [c for c in channels if c.get("detector") == det]
        n_sat_ev = sum(1 for c in det_ch if c["quality"] == "saturated" or "OVERFLOW" in c.get("flags", []))
        for c in det_ch:
            if c.get("nhits_dip") and c["quality"] in ("good", "warning", "non_detection"):
                c["quality"] = "saturated" if n_sat_ev >= 3 else "warning"
    n_sat = sum(1 for c in channels if c["quality"] == "saturated")
    neigh = dr1_neighbors(ra, dec, radius_arcsec=r_ap_px * DR1_PIX_ARCSEC + 4.0)
    bright_neigh = [n for n in (neigh or []) if n.get("significant")]
    result = {
        "ra": round(ra, 6), "dec": round(dec, 6), "tile_npix": ipix, "tile_px": [round(xf, 2), round(yf, 2)],
        "aperture_arcsec": round(r_ap_px * DR1_PIX_ARCSEC, 1), "pixel_arcsec": DR1_PIX_ARCSEC,
        "time_span_mjd": list(DR1_MJD_RANGE), "edge_of_tile": bool(edge),
        "channels": channels, "n_saturated": n_sat,
        "neighbors": neigh, "contamination_warning": bool(bright_neigh),
        "source": "SPHEREx DR1 All-Sky Spectral Cube (DOI 10.26131/IRSA679), AWS S3 nasa-irsa-spherex/dr1/hips5_cube",
        "notes_es": [
            "Co-adición de un año: no contiene información temporal.",
            "Apertura de 25.8″: puede incluir estrellas vecinas en campos densos.",
        ] + (["La fuente está saturada en %d canales (núcleo sin datos válidos o rechazados): esos flujos no son fiables." % n_sat] if n_sat else [])
        + (["Hay %d fuente(s) Gaia dentro de la apertura (la más cercana a %.1f″, G = %.1f): el flujo incluye su contribución." % (len(bright_neigh), bright_neigh[0]["sep_arcsec"], bright_neigh[0]["gmag"])] if bright_neigh else []),
        "notes_en": [
            "One-year co-add: it has no time information.",
            "25.8″ aperture: it may include neighbouring stars in crowded fields.",
        ] + (["The source is saturated in %d channels (core without valid or rejected data): those fluxes are not reliable." % n_sat] if n_sat else [])
        + (["There are %d Gaia source(s) inside the aperture (nearest at %.1f″, G = %.1f): the flux includes their contribution." % (len(bright_neigh), bright_neigh[0]["sep_arcsec"], bright_neigh[0]["gmag"])] if bright_neigh else []),
    }
    try:
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump(result, f)
    except Exception:
        pass
    result["band_depths"] = compute_band_depths(channels, object_kind)
    return result


# ---------------------------------------------------------------------------
# Catálogos externos (Gaia DR3 y AllWISE vía VizieR ASU, con espejo de respaldo)
# ---------------------------------------------------------------------------
def _vizier_asu(source: str, ra: float, dec: float, radius_deg: float, cols: str, max_rows: int = 200, sort: Optional[str] = None, timeout: float = 12.0) -> Optional[List[Dict[str, str]]]:
    params = {"-source": source, "-c": f"{ra:.6f} {dec:+.6f}", "-c.rd": f"{radius_deg:.5f}", "-out": cols, "-out.max": str(max_rows)}
    if sort:
        params["-sort"] = sort
    for base in VIZIER_ASU_MIRRORS:
        try:
            r = requests.get(base, params=params, timeout=timeout)
            if not r.ok:
                continue
            lines = [ln for ln in r.text.splitlines() if ln and not ln.startswith("#")]
            if len(lines) < 3:
                return []
            header = [h.strip() for h in lines[0].split("\t")]
            rows: List[Dict[str, str]] = []
            for ln in lines[3:]:
                vals = ln.split("\t")
                if len(vals) != len(header):
                    continue
                rows.append({h: v.strip() for h, v in zip(header, vals)})
            return rows
        except Exception:
            continue
    return None


def _fnum(s: Optional[str]) -> Optional[float]:
    try:
        v = float(s)
        return v if np.isfinite(v) else None
    except Exception:
        return None


def _gaia_dr3_mast(ra: float, dec: float, radius_deg: float) -> Optional[List[Dict[str, Any]]]:
    """Gaia DR3 desde MAST (recurso oficial indicado por la NASA para el reto). Posiciones en la época 2016.0."""
    req = {"service": "Mast.Catalogs.GaiaDR3.Cone", "params": {"ra": float(ra), "dec": float(dec), "radius": float(radius_deg)},
           "format": "json", "pagesize": 2000, "page": 1}
    try:
        r = requests.post("https://mast.stsci.edu/api/v0/invoke", data={"request": json.dumps(req)}, timeout=25)
        if not r.ok:
            return None
        d = r.json()
        if d.get("status") != "COMPLETE":
            return None
        out = []
        for row in d.get("data", []):
            if row.get("ra") is None or row.get("dec") is None:
                continue
            out.append({"id": f"Gaia DR3 {row.get('source_id')}", "ra": float(row["ra"]), "dec": float(row["dec"]), "epoch": 2016.0,
                        "pmra": float(row.get("pmra") or 0.0), "pmdec": float(row.get("pmdec") or 0.0),
                        "plx": _fnum(row.get("parallax")), "plx_err": _fnum(row.get("parallax_error")),
                        "gmag": _fnum(row.get("phot_g_mean_mag")), "bprp": _fnum(row.get("bp_rp")), "ruwe": _fnum(row.get("ruwe"))})
        out.sort(key=lambda g: g["gmag"] if g["gmag"] is not None else 99.0)
        return out[:400]
    except Exception:
        return None


def _allwise_gator(ra: float, dec: float, radius_deg: float) -> Optional[List[Dict[str, str]]]:
    """AllWISE desde IRSA Gator (formato IPAC), respaldo cuando VizieR no responde."""
    try:
        r = requests.get("https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query", params={
            "catalog": "allwise_p3as_psd", "spatial": "cone", "objstr": f"{ra:.6f} {dec:+.6f}", "radius": f"{radius_deg * 3600.0:.1f}",
            "radunit": "arcsec", "outfmt": "1", "selcols": "designation,ra,dec,w1mpro,w2mpro,w3mpro,pmra,pmdec"}, timeout=30)
        if not r.ok or "|" not in r.text:
            return None
        lines = [ln for ln in r.text.splitlines() if ln.strip() and not ln.startswith("\\")]
        hdr = [h.strip() for h in lines[0].strip("|").split("|")]
        rows = []
        for ln in lines:
            if ln.startswith("|"):
                continue
            vals = ln.split()
            if len(vals) < 8:
                continue
            d = dict(zip(hdr, vals))
            rows.append({"AllWISE": d.get("designation", ""), "RAJ2000": d.get("ra"), "DEJ2000": d.get("dec"), "W1mag": d.get("w1mpro"),
                         "W2mag": d.get("w2mpro"), "W3mag": d.get("w3mpro"), "pmRA": d.get("pmra"), "pmDE": d.get("pmdec")})
        return rows
    except Exception:
        return None


def fetch_catalog_sources(ra: float, dec: float, radius_deg: float) -> Dict[str, Any]:
    """Fuentes Gaia DR3 (época 2016.0) y AllWISE (época ≈ 2010.5) en el campo, con caché en disco."""
    ckey = f"catv2_{ra:.4f}_{dec:.4f}_{radius_deg:.3f}"
    cfile = os.path.join(CACHE_DIR, "catalogs", f"{ckey}.json")
    if os.path.exists(cfile):
        try:
            with open(cfile, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    gaia_mast = _gaia_dr3_mast(ra, dec, radius_deg)
    gaia_rows = None if gaia_mast is not None else _vizier_asu("I/355/gaiadr3", ra, dec, radius_deg, "Source,RA_ICRS,DE_ICRS,pmRA,pmDE,Plx,e_Plx,Gmag,BP-RP,RUWE", 300, "Gmag")
    wise_rows = _vizier_asu("II/328/allwise", ra, dec, radius_deg, "AllWISE,RAJ2000,DEJ2000,W1mag,W2mag,W3mag,pmRA,pmDE", 300, "W2mag")
    if wise_rows is None:
        wise_rows = _allwise_gator(ra, dec, radius_deg)
    gaia = list(gaia_mast or [])
    for r in gaia_rows or []:
        ra_g, de_g = _fnum(r.get("RA_ICRS")), _fnum(r.get("DE_ICRS"))
        if ra_g is None or de_g is None:
            continue
        gaia.append({"id": f"Gaia DR3 {r.get('Source', '')}", "ra": ra_g, "dec": de_g, "epoch": 2016.0,
                     "pmra": _fnum(r.get("pmRA")) or 0.0, "pmdec": _fnum(r.get("pmDE")) or 0.0,
                     "plx": _fnum(r.get("Plx")), "plx_err": _fnum(r.get("e_Plx")), "gmag": _fnum(r.get("Gmag")),
                     "bprp": _fnum(r.get("BP-RP")), "ruwe": _fnum(r.get("RUWE"))})
    wise = []
    for r in wise_rows or []:
        ra_w, de_w = _fnum(r.get("RAJ2000")), _fnum(r.get("DEJ2000"))
        if ra_w is None or de_w is None:
            continue
        w1, w2 = _fnum(r.get("W1mag")), _fnum(r.get("W2mag"))
        wise.append({"id": f"AllWISE {r.get('AllWISE', '')}", "ra": ra_w, "dec": de_w, "epoch": 2010.5, "w1": w1, "w2": w2,
                     "w3": _fnum(r.get("W3mag")), "w1_w2": round(w1 - w2, 2) if (w1 is not None and w2 is not None) else None,
                     "pmra": _fnum(r.get("pmRA")) or 0.0, "pmdec": _fnum(r.get("pmDE")) or 0.0})
    data = {"gaia": gaia, "allwise": wise, "ok": (gaia_mast is not None or gaia_rows is not None) and wise_rows is not None,
            "gaia_service": "MAST (Gaia DR3)" if gaia_mast is not None else ("VizieR I/355" if gaia_rows is not None else None)}
    if data["ok"]:
        try:
            with open(cfile, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass
    return data


def _propagate_linear(ra: float, dec: float, pmra: float, pmdec: float, epoch_from: float, epoch_to: float) -> Tuple[float, float]:
    dt = epoch_to - epoch_from
    cosd = max(np.cos(np.deg2rad(dec)), 1e-6)
    return (ra + pmra * dt / (3.6e6 * cosd)) % 360.0, dec + pmdec * dt / 3.6e6


def query_external_catalogs(ra: float, dec: float, fov_deg: float, wcs_info: Dict[str, Any], epoch_jyear: float = DISPLAY_EPOCH_JYEAR) -> Dict[str, Any]:
    """Proyecta Gaia DR3 (propagada a `epoch_jyear`) y AllWISE (posición de catálogo, época ≈ 2010.5) sobre la grilla."""
    radius_deg = float(min(max(fov_deg * 0.75, 0.03), 0.6))
    cat = fetch_catalog_sources(ra, dec, radius_deg)
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = wcs_info["crval"]
    w.wcs.crpix = wcs_info["crpix"]
    w.wcs.cdelt = wcs_info["cdelt"]
    gaia_proj = []
    for g in cat.get("gaia", []):
        ra_e, de_e = _propagate_linear(g["ra"], g["dec"], g["pmra"], g["pmdec"], 2016.0, epoch_jyear)
        ra_f, de_f = _propagate_linear(g["ra"], g["dec"], g["pmra"], g["pmdec"], 2016.0, epoch_jyear + 10.0)
        px, py = w.world_to_pixel_values(ra_e, de_e)
        px_f, py_f = w.world_to_pixel_values(ra_f, de_f)
        gaia_proj.append({**g, "ra_epoch": round(ra_e, 6), "dec_epoch": round(de_e, 6), "px": round(float(px), 2), "py": round(float(py), 2),
                          "px_10yr": round(float(px_f), 2), "py_10yr": round(float(py_f), 2), "epoch_shown": epoch_jyear})
    wise_proj = []
    for ws in cat.get("allwise", []):
        px, py = w.world_to_pixel_values(ws["ra"], ws["dec"])
        wise_proj.append({**ws, "px": round(float(px), 2), "py": round(float(py), 2)})
    return {"gaia": gaia_proj, "allwise": wise_proj, "ok": bool(cat.get("ok")),
            "note_es": "Gaia DR3 propagada a la época %.2f; AllWISE en su posición de catálogo (≈2010.5)." % epoch_jyear,
            "note_en": "Gaia DR3 propagated to epoch %.2f; AllWISE at its catalogue position (≈2010.5)." % epoch_jyear}


# ---------------------------------------------------------------------------
# Detección de candidatos en la imagen de diferencia (dipolos de movimiento o variables)
# ---------------------------------------------------------------------------
def detect_candidates(epoch_arrays: List[np.ndarray], common_wcs: WCS, pix_arcsec: float, coverage: Optional[List[np.ndarray]] = None) -> List[Dict[str, Any]]:
    """
    Escanea ΔI = E_última − E_primera con un umbral robusto (σ_MAD) y clasifica cada pico como
    dipolo (par positivo/negativo separado 1.3–7.5 px con desplazamiento del máximo) o como cambio
    de brillo estacionario. Solo usa píxeles con datos reales en ambas épocas. Son CANDIDATOS: el
    nivel de significancia no es una probabilidad y requieren verificación.
    """
    if len(epoch_arrays) < 2:
        return []
    first = epoch_arrays[0]
    last = epoch_arrays[-1]
    diff = last - first
    mean_stack = np.mean(epoch_arrays, axis=0)
    ny, nx = diff.shape
    margin = 6
    valid = np.isfinite(diff)
    if coverage is not None and len(coverage) >= 2:
        valid &= (coverage[0] >= 0.5) & (coverage[-1] >= 0.5)
    interior = np.zeros_like(valid)
    interior[margin:-margin, margin:-margin] = True
    samp = diff[valid & interior]
    if len(samp) < 50:
        return []
    lo_q, hi_q = np.percentile(samp, [12.0, 88.0])
    bg_sample = samp[(samp >= lo_q) & (samp <= hi_q)]
    med = float(np.median(bg_sample))
    mad = float(np.median(np.abs(bg_sample - med)))
    sigma = max(1.4826 * mad, 1e-6)
    work = np.where(valid & interior, diff - med, 0.0)
    candidates: List[Dict[str, Any]] = []
    used_mask = np.zeros((ny, nx), dtype=bool)
    yy, xx = np.ogrid[:ny, :nx]
    for rank in range(1, 5):
        abs_work = np.where(used_mask, 0.0, np.abs(work))
        iy, ix = np.unravel_index(int(np.argmax(abs_work)), abs_work.shape)
        val = float(work[iy, ix])
        snr_diff = abs(val) / sigma
        if snr_diff < 5.0:
            break
        y0, y1 = max(margin, iy - 7), min(ny - margin, iy + 8)
        x0, x1 = max(margin, ix - 7), min(nx - margin, ix + 8)
        sub = work[y0:y1, x0:x1]
        opp_y_rel, opp_x_rel = np.unravel_index(int(np.argmin(sub) if val > 0 else np.argmax(sub)), sub.shape)
        opp_y, opp_x = y0 + int(opp_y_rel), x0 + int(opp_x_rel)
        opp_val = float(work[opp_y, opp_x])
        dist_px = float(np.hypot(opp_x - ix, opp_y - iy))
        lobe_ratio = min(abs(val), abs(opp_val)) / max(abs(val), abs(opp_val), 1e-12)
        is_dipole = (val * opp_val < 0) and (abs(opp_val) / sigma >= 3.0) and (1.3 <= dist_px <= 7.5) and (lobe_ratio >= 0.3)
        px_now, py_now = (int(ix), int(iy)) if val > 0 else (int(opp_x), int(opp_y))
        px_old, py_old = (int(opp_x), int(opp_y)) if val > 0 else (int(ix), int(iy))
        f_sub = first[y0:y1, x0:x1]
        l_sub = last[y0:y1, x0:x1]
        f_ymax, f_xmax = np.unravel_index(int(np.nanargmax(f_sub)), f_sub.shape)
        l_ymax, l_xmax = np.unravel_index(int(np.nanargmax(l_sub)), l_sub.shape)
        centroid_shift_px = float(np.hypot(l_xmax - f_xmax, l_ymax - f_ymax))
        if centroid_shift_px < 1.0:
            is_dipole = False
        if not is_dipole:
            px_now, py_now = px_old, py_old = int(ix), int(iy)
        used_mask |= ((xx - px_now) ** 2 + (yy - py_now) ** 2) <= 8 ** 2
        used_mask |= ((xx - px_old) ** 2 + (yy - py_old) ** 2) <= 8 ** 2
        ra_c, dec_c = common_wcs.pixel_to_world_values(px_now, py_now)
        ra_o, dec_o = common_wcs.pixel_to_world_values(px_old, py_old)
        shift_arcsec = round(float(SkyCoord(ra_c * u.deg, dec_c * u.deg).separation(SkyCoord(ra_o * u.deg, dec_o * u.deg)).arcsec), 2) if is_dipole else 0.0
        base_flux = float(mean_stack[py_now, px_now])
        var_pct = round(abs(val) / base_flux * 100.0, 1) if base_flux > 5 * sigma else None
        sign = "+" if val > 0 else "−"
        candidates.append({
            "rank": rank,
            "type": "dipole" if is_dipole else "variable",
            "label_es": f"Dipolo (~{shift_arcsec}″)" if is_dipole else (f"Cambio de brillo ({sign}{var_pct}%)" if var_pct is not None else f"Cambio de brillo ({sign})"),
            "label_en": f"Dipole (~{shift_arcsec}″)" if is_dipole else (f"Brightness change ({sign}{var_pct}%)" if var_pct is not None else f"Brightness change ({sign})"),
            "px": px_now, "py": py_now, "px_old": px_old, "py_old": py_old,
            "ra": round(float(ra_c), 6), "dec": round(float(dec_c), 6),
            "ra_old": round(float(ra_o), 6), "dec_old": round(float(dec_o), 6),
            "snr_diff": round(min(snr_diff, 999.9), 1),
            "delta_sb": round(val, 5),
            "shift_arcsec": shift_arcsec,
            "var_pct": var_pct,
            "lobe_ratio": round(lobe_ratio, 2),
        })
    return candidates


# ---------------------------------------------------------------------------
# Fuentes del campo: detección + identificación con catálogos (sin inventar tipos ni distancias)
# ---------------------------------------------------------------------------
def recognize_celestial_objects(
    coadd: np.ndarray, common_wcs: WCS, pix_arcsec: float, mean_mjd: float,
    catalogs: Dict[str, Any], ref_tracks: List[Dict[str, Any]], max_objects: int = 12, coarse: bool = False,
) -> List[Dict[str, Any]]:
    """
    Detecta picos ≥ 5σ en la co-adición y los identifica por posición con (1) los objetivos de referencia
    (posición propagada), (2) Gaia DR3 propagada a la época media y (3) AllWISE. La distancia solo se da
    si existe paralaje fiable (π/σπ ≥ 5) o una distancia publicada; en otro caso es None.
    """
    from scipy.ndimage import maximum_filter, uniform_filter

    img = np.nan_to_num(coadd, nan=0.0)
    ny, nx = img.shape
    sm = uniform_filter(img, size=2)
    med_bg = float(np.median(sm))
    sigma_bg = max(1.4826 * float(np.median(np.abs(sm - med_bg))), 1e-6)
    is_peak = (sm == maximum_filter(sm, size=7)) & (sm > med_bg + 5.0 * sigma_bg)
    m = 4
    is_peak[:m, :] = is_peak[-m:, :] = False
    is_peak[:, :m] = is_peak[:, -m:] = False
    pys, pxs = np.where(is_peak)
    peaks = sorted([(int(x), int(y), float(sm[y, x] - med_bg)) for y, x in zip(pys, pxs)], key=lambda t: t[2], reverse=True)[:max_objects]
    epoch_j = float(Time(mean_mjd, format="mjd").jyear)
    gaia = []
    for g in catalogs.get("gaia", []):
        ra_e, de_e = _propagate_linear(g["ra"], g["dec"], g["pmra"], g["pmdec"], 2016.0, epoch_j)
        gaia.append((g, ra_e, de_e))
    wise = [(ws, ws["ra"], ws["dec"]) for ws in catalogs.get("allwise", [])]

    def _nearest(lst: List[Tuple[Dict[str, Any], float, float]], ra0: float, de0: float, rmax: float) -> Tuple[Optional[Dict[str, Any]], float]:
        best, bd = None, rmax
        for item, ra_i, de_i in lst:
            dd = float(np.hypot(((ra_i - ra0 + 180) % 360 - 180) * np.cos(np.deg2rad(de0)), de_i - de0) * 3600.0)
            if dd < bd:
                best, bd = item, dd
        return best, bd

    out: List[Dict[str, Any]] = []
    for idx, (px, py, pk) in enumerate(peaks):
        r_deg, d_deg = [float(v) for v in common_wcs.pixel_to_world_values(px, py)]
        obj: Dict[str, Any] = {
            "id": f"OBJ_{idx + 1}", "rank": idx + 1, "px": px, "py": py, "ra": round(r_deg % 360.0, 6), "dec": round(d_deg, 6),
            "peak_sb_mjy_sr": round(pk, 4), "flux_ujy": None, "ab_mag": None,
            "gmag": None, "w1": None, "w2": None, "parallax_mas": None, "parallax_err_mas": None,
            "dist_pc": None, "dist_ly": None, "dist_au": None, "dist_method_es": None, "dist_method_en": None,
            "teff_k": None, "xyz_pc": None, "match_sep_arcsec": None,
        }
        ref_hit = None
        for tr in ref_tracks:
            dd = float(np.hypot(((tr["ra"] - r_deg + 180) % 360 - 180) * np.cos(np.deg2rad(d_deg)), tr["dec"] - d_deg) * 3600.0)
            if dd <= (14.0 if coarse else 8.0):
                ref_hit = (tr, dd)
                break
        # Radios de identificación: 4″ con píxeles L2b de 6.15″; 8″ con la co-adición DR1 (píxeles de 12.9″)
        g_hit, g_sep = _nearest(gaia, r_deg, d_deg, 8.0 if coarse else 4.0)
        w_hit, w_sep = _nearest(wise, r_deg, d_deg, 8.0 if coarse else 4.0)
        if ref_hit:
            t = _TARGETS_BY_ID.get(ref_hit[0]["id"], {})
            obj.update({
                "name": t.get("name", ref_hit[0]["id"]), "obj_class": "reference_target", "color": "#38bdf8",
                "spectral_type_es": f"{t.get('sptype', '')} · objetivo de referencia NASA".strip(" ·"),
                "spectral_type_en": f"{t.get('sptype', '')} · NASA reference target".strip(" ·"),
                "match_sep_arcsec": round(ref_hit[1], 2), "teff_k": t.get("teff_k_lit"),
            })
            if t.get("distance_pc"):
                obj["dist_pc"] = float(t["distance_pc"])
                obj["dist_method_es"] = t.get("distance_ref")
                obj["dist_method_en"] = t.get("distance_ref")
            astrom = t.get("astrometry") or {}
            obj["parallax_mas"] = astrom.get("parallax_mas")
            obj["parallax_err_mas"] = astrom.get("parallax_err_mas")
        elif g_hit:
            obj.update({"name": g_hit["id"], "obj_class": "gaia_source", "color": "#a5b4fc", "gmag": g_hit.get("gmag"),
                        "parallax_mas": g_hit.get("plx"), "parallax_err_mas": g_hit.get("plx_err"), "match_sep_arcsec": round(g_sep, 2),
                        "spectral_type_es": f"Fuente Gaia DR3 (G = {g_hit['gmag']:.2f})" if g_hit.get("gmag") is not None else "Fuente Gaia DR3",
                        "spectral_type_en": f"Gaia DR3 source (G = {g_hit['gmag']:.2f})" if g_hit.get("gmag") is not None else "Gaia DR3 source"})
            plx, eplx = g_hit.get("plx"), g_hit.get("plx_err")
            if plx is not None and eplx and eplx > 0 and plx / eplx >= 5.0:
                obj["dist_pc"] = round(1000.0 / plx, 2 if plx > 10 else 1)
                obj["dist_method_es"] = f"1/π, π = {plx:.3f} ± {eplx:.3f} mas (Gaia DR3)"
                obj["dist_method_en"] = f"1/π, π = {plx:.3f} ± {eplx:.3f} mas (Gaia DR3)"
            if w_hit:
                obj["w1"], obj["w2"] = w_hit.get("w1"), w_hit.get("w2")
        elif w_hit:
            obj.update({"name": w_hit["id"], "obj_class": "wise_source", "color": "#fbbf24", "w1": w_hit.get("w1"), "w2": w_hit.get("w2"),
                        "match_sep_arcsec": round(w_sep, 2),
                        "spectral_type_es": "Fuente AllWISE sin contrapartida Gaia (sin paralaje)",
                        "spectral_type_en": "AllWISE source without Gaia counterpart (no parallax)"})
        else:
            obj.update({"name": f"SPX J{r_deg:08.4f}{d_deg:+08.4f}", "obj_class": "unidentified", "color": "#94a3b8",
                        "spectral_type_es": "Sin identificar" + ("" if catalogs.get("ok") else " (catálogos no disponibles)"),
                        "spectral_type_en": "Unidentified" + ("" if catalogs.get("ok") else " (catalogues unavailable)")})
        if obj["dist_pc"]:
            dpc = float(obj["dist_pc"])
            obj["dist_ly"] = round(dpc * 3.26156, 2 if dpc < 50 else 1)
            obj["dist_au"] = round(dpc * 206264.806, 0)
            ra_r, de_r = np.deg2rad(r_deg), np.deg2rad(d_deg)
            obj["xyz_pc"] = [round(float(dpc * np.cos(de_r) * np.cos(ra_r)), 4), round(float(dpc * np.cos(de_r) * np.sin(ra_r)), 4), round(float(dpc * np.sin(de_r)), 4)]
        out.append(obj)
    return out


# ---------------------------------------------------------------------------
# Construcción del cubo multi-época (pipeline principal)
# ---------------------------------------------------------------------------
_RELEASE_PRIORITY = {"dr1": 0, "qr3": 1, "qr2": 2, "qr1": 3}


def _dedupe_releases(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Una misma observación puede estar en varias versiones (QR2, DR1…): se conserva solo la mejor."""
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in rows:
        k = (r["obs_id"], r["band"])
        cur = best.get(k)
        if cur is None or _RELEASE_PRIORITY.get(r.get("release", ""), 9) < _RELEASE_PRIORITY.get(cur.get("release", ""), 9):
            best[k] = r
    return sorted(best.values(), key=lambda r: r["t_min"])


def _inpaint_for_display(img: np.ndarray, bad: np.ndarray) -> np.ndarray:
    """Rellena píxeles enmascarados SOLO para visualización con la media de vecinos válidos (5×5)."""
    from scipy.ndimage import uniform_filter

    valid = ~bad & np.isfinite(img)
    num = uniform_filter(np.where(valid, img, 0.0).astype(np.float64), size=5)
    den = uniform_filter(valid.astype(np.float64), size=5)
    out = img.astype(np.float64).copy()
    fill = ~valid
    with np.errstate(invalid="ignore", divide="ignore"):
        out[fill] = np.where(den[fill] > 0.05, num[fill] / den[fill], np.nan)
    return out.astype(np.float32)


def _reference_targets_in_field(ra: float, dec: float, size_deg: float) -> List[Dict[str, Any]]:
    out = []
    half = 0.75 * size_deg
    for t in CHALLENGE_TARGETS:
        if not t.get("astrometry"):
            continue
        dd = float(np.hypot(((t["ra"] - ra + 180) % 360 - 180) * np.cos(np.deg2rad(dec)), t["dec"] - dec))
        if dd <= half:
            out.append(t)
    return out


def build_sky_cube_and_spectrum(
    ra: float,
    dec: float,
    bands: List[str],
    size_deg: float = 0.12,
    max_per_epoch: int = 5,
    release: str = "all",
    gap_days: float = 45.0,
    force_reproject: bool = False,
    target_id: Optional[str] = None,
    user_astrometry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    1. Busca exposiciones L2b en IRSA TAP y elimina duplicados entre versiones.
    2. Agrupa en épocas (≤ 8) y elige hasta `max_per_epoch` exposiciones por época repartidas por banda.
    3. Descarga recortes nativos (S3 HTTP Range / IBE) con ePSF y metadatos.
    4. Para el objetivo (posición propagada a la fecha de CADA exposición) mide fotometría PSF forzada.
    5. Construye imágenes de época (mediana) para el blink, con mapa de cobertura real.
    6. Detecta candidatos en la diferencia, identifica fuentes con catálogos y resume la calidad de datos.
    Si IRSA no responde o no hay exposiciones, devuelve UNA imagen estática del cubo DR1 y lo indica.
    """
    t0 = time.time()
    norm_bands = sorted({b.upper().replace("SPHEREX-", "") for b in (bands or ["D1", "D2", "D3", "D4"])}) or ["D6"]
    astrom = user_astrometry or get_target_astrometry(target_id)
    tgt_obj = _TARGETS_BY_ID.get(target_id) if target_id else None
    if astrom:
        # Un objetivo que no cae dentro del campo pedido se ignora (no se mide un objeto en otra zona del cielo)
        ra_chk, dec_chk = propagate_astrometry(astrom, _jyear_to_mjd(DISPLAY_EPOCH_JYEAR))
        sep_deg = float(SkyCoord(ra * u.deg, dec * u.deg).separation(SkyCoord(ra_chk * u.deg, dec_chk * u.deg)).deg)
        if sep_deg > 0.75 * size_deg + 0.02:
            astrom, tgt_obj, target_id, user_astrometry = None, None, None, None
    astrom_key = json.dumps(astrom, sort_keys=True) if astrom else ""
    cube_hash = hashlib.md5(
        f"cube_v6_{ra:.4f}_{dec:.4f}_{','.join(norm_bands)}_{size_deg:.3f}_{max_per_epoch}_{release}_{gap_days:.1f}_{target_id}_{astrom_key}".encode()
    ).hexdigest()[:16]
    cube_cache_path = os.path.join(CACHE_DIR, "cubes", f"cube_{cube_hash}.json")
    if not force_reproject:
        if cube_hash in _CUBE_RESP_CACHE:
            cached = dict(_CUBE_RESP_CACHE[cube_hash])
            cached["elapsed_sec"] = round(time.time() - t0, 3)
            return cached
        if os.path.exists(cube_cache_path):
            try:
                with open(cube_cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                _CUBE_RESP_CACHE[cube_hash] = cached
                out_c = dict(cached)
                out_c["elapsed_sec"] = round(time.time() - t0, 3)
                return out_c
            except Exception:
                pass

    common_wcs, shape, pix_arcsec = make_common_wcs(ra, dec, size_deg, oversample=2.0)
    ny, nx = shape
    notes: List[Dict[str, str]] = []

    all_rows = query_spherex_exposures(ra, dec, bands=norm_bands, release=release)
    tap_ok = bool(_TAP_STATUS.get("ok"))
    all_rows = _dedupe_releases(all_rows) if all_rows else []
    all_cov = query_spherex_exposures(ra, dec, bands=None, release="all") if tap_ok else []
    all_cov = _dedupe_releases(all_cov) if all_cov else []

    selected_rows: List[Dict[str, Any]] = []
    if all_rows:
        raw_groups = group_exposures_into_epochs(all_rows, gap_days=gap_days)
        if len(raw_groups) > MAX_EPOCHS:
            keep_idx = sorted(set(np.linspace(0, len(raw_groups) - 1, MAX_EPOCHS).round().astype(int).tolist()))
            raw_groups = [raw_groups[i] for i in keep_idx]
        for ep_id, grp in enumerate(raw_groups):
            for r in _select_band_balanced(grp, max_per_epoch):
                selected_rows.append({**r, "epoch_id": ep_id})
    valid_cuts: List[Dict[str, Any]] = []
    if selected_rows:
        with ThreadPoolExecutor(max_workers=16) as ex:
            fetched = list(ex.map(lambda r: _safe_fetch(r, ra, dec, size_deg), selected_rows))
        valid_cuts = [c for c in fetched if c is not None]

    def _target_radec(mjd: float) -> Tuple[float, float]:
        if astrom:
            return propagate_astrometry(astrom, mjd)
        return ra, dec

    refs_in_field = _reference_targets_in_field(ra, dec, size_deg)
    cat_radius = float(min(max(size_deg * 0.75, 0.03), 0.6))
    catalogs = fetch_catalog_sources(ra, dec, cat_radius) if valid_cuts else {"gaia": [], "allwise": [], "ok": False}

    def _neighbors_at(mjd: float, ra_t: float, dec_t: float) -> List[Tuple[float, float]]:
        """Fuentes Gaia a < 20″ del objetivo (propagadas a la fecha), excluida la propia fuente (< 1.5″)."""
        jy = float(Time(mjd, format="mjd").jyear)
        out_n = []
        cosd = np.cos(np.deg2rad(dec_t))
        for g in catalogs.get("gaia", []):
            if g.get("gmag") is not None and g["gmag"] > 20.5:
                continue
            if abs(g["dec"] - dec_t) > 0.02:
                continue
            ra_e, de_e = _propagate_linear(g["ra"], g["dec"], g["pmra"], g["pmdec"], 2016.0, jy)
            sep = float(np.hypot(((ra_e - ra_t + 180) % 360 - 180) * cosd, de_e - dec_t) * 3600.0)
            if 1.5 < sep <= 20.0:
                out_n.append((ra_e, de_e))
        return out_n

    # ---------------- Fotometría del objetivo por exposición + reproyección para visualización
    def _process(cut: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mjd = float(cut["meta"].get("mjd_avg") or cut["row"]["t_min"])
        ra_t, dec_t = _target_radec(mjd)
        phot = forced_photometry_cut(cut, ra_t, dec_t, fit_position=True, neighbors=_neighbors_at(mjd, ra_t, dec_t))
        flags = cut["flags"]
        bad = ((flags & DISPLAY_REJECT_MASK) != 0) | ~np.isfinite(cut["img"])
        disp = _inpaint_for_display(cut["img"], bad)
        try:
            rp_img, fp = reproject_interp((disp, cut["wcs"]), common_wcs, shape_out=shape, order="bilinear")
            rp_valid, _ = reproject_interp(((~bad).astype(np.float32), cut["wcs"]), common_wcs, shape_out=shape, order="nearest-neighbor")
            rp_flg_f, _ = reproject_interp((flags.astype(np.float64), cut["wcs"]), common_wcs, shape_out=shape, order="nearest-neighbor")
        except Exception:
            return None
        rp_img = np.where(fp > 0, rp_img, np.nan)
        cov = np.nan_to_num(rp_valid, nan=0.0)
        rp_flg = np.nan_to_num(rp_flg_f, nan=0.0).astype(np.int64)
        bg = float(np.nanmedian(rp_img)) if np.any(np.isfinite(rp_img)) else 0.0
        return {
            "cut": cut, "row": cut["row"], "mjd": mjd, "rp_img": (rp_img - bg).astype(np.float32), "cov": cov.astype(np.float32),
            "rp_flg": rp_flg, "phot": phot, "bad_frac": float(np.mean(bad)) * 100.0, "zodi": cut["zodi"],
        }

    items: List[Dict[str, Any]] = []
    if valid_cuts:
        with ThreadPoolExecutor(max_workers=8) as rex:
            items = [it for it in rex.map(_process, valid_cuts) if it is not None]

    data_mode = "l2b" if items else "none"
    epochs_out: List[Dict[str, Any]] = []
    epoch_arrays: List[np.ndarray] = []
    coverage_arrays: List[np.ndarray] = []
    photometry: List[Dict[str, Any]] = []
    target_track: List[Dict[str, Any]] = []

    if items:
        by_ep: Dict[int, List[Dict[str, Any]]] = {}
        for it in items:
            by_ep.setdefault(int(it["row"].get("epoch_id", 0)), []).append(it)
        epoch_groups = [sorted(by_ep[k], key=lambda x: x["mjd"]) for k in sorted(by_ep)]
        with np.errstate(all="ignore"):
            global_coadd = np.nanmedian(np.array([it["rp_img"] for it in items]), axis=0).astype(np.float32)
        for idx_ep, grp in enumerate(epoch_groups):
            stack = np.array([g["rp_img"] for g in grp], dtype=np.float32)
            cov = np.mean(np.array([g["cov"] for g in grp]), axis=0).astype(np.float32)
            with np.errstate(all="ignore"):
                ep_med = np.nanmedian(stack, axis=0).astype(np.float32)
            nan_m = ~np.isfinite(ep_med)
            ep_img = np.where(nan_m, np.where(np.isfinite(global_coadd), global_coadd, 0.0), ep_med).astype(np.float32)
            cov = np.where(nan_m, 0.0, cov).astype(np.float32)
            flg_or = np.bitwise_or.reduce([g["rp_flg"] for g in grp]).astype(np.int64)
            mjds = [g["mjd"] for g in grp]
            mjd_mean = float(np.mean(mjds))
            ra_t, dec_t = _target_radec(mjd_mean)
            tx, ty = [float(v) for v in common_wcs.world_to_pixel_values(ra_t, dec_t)]
            target_track.append({"epoch_index": idx_ep, "mjd": round(mjd_mean, 5), "ra": round(ra_t, 6), "dec": round(dec_t, 6), "px": round(tx, 2), "py": round(ty, 2)})
            yy, xx = np.ogrid[:ny, :nx]
            r2 = (xx - tx) ** 2 + (yy - ty) ** 2
            ap_m = r2 <= 2.5 ** 2
            ann_m = (r2 >= 6.0 ** 2) & (r2 <= 10.0 ** 2) & (cov >= 0.5)
            if np.any(ap_m) and np.sum(ann_m) > 10:
                bg_ep = float(np.median(ep_img[ann_m]))
                peak_ep = float(np.max(ep_img[ap_m]) - bg_ep)
                rms_ep = float(1.4826 * np.median(np.abs(ep_img[ann_m] - bg_ep)))
            else:
                peak_ep, rms_ep = float("nan"), float("nan")
            flag_counts = {}
            for fdef in FLAG_DEFINITIONS:
                cnt = int(np.sum((flg_or & (1 << fdef["bit"])) != 0))
                if cnt > 0:
                    flag_counts[fdef["name"]] = cnt
            ep_phot = [g["phot"] for g in grp]
            photometry.extend({**p, "epoch_index": idx_ep} for p in ep_phot)
            lams = [p["wavelength_um"] for p in ep_phot if p.get("wavelength_um")]
            n_det = sum(1 for p in ep_phot if p["quality"] in ("good", "warning"))
            det_snr = [p["snr"] for p in ep_phot if p["quality"] in ("good", "warning") and p.get("snr")]
            epoch_arrays.append(ep_img)
            coverage_arrays.append(cov)
            epochs_out.append({
                "index": idx_ep,
                "mjd": round(mjd_mean, 4),
                "date": Time(mjd_mean, format="mjd").iso[:10],
                "mjd_min": round(min(mjds), 4),
                "mjd_max": round(max(mjds), 4),
                "n_exp": len(grp),
                "bands": sorted({g["row"]["band"] for g in grp}),
                "lam_min_um": round(min(lams), 3) if lams else None,
                "lam_max_um": round(max(lams), 3) if lams else None,
                "peak_sb_mjy_sr": round(peak_ep, 4) if np.isfinite(peak_ep) else None,
                "rms_mjy_sr": round(rms_ep, 5) if np.isfinite(rms_ep) else None,
                "snr": round(peak_ep / rms_ep, 2) if (np.isfinite(peak_ep) and np.isfinite(rms_ep) and rms_ep > 0) else None,
                "n_target_detections": n_det,
                "target_snr_median": round(float(np.median(det_snr)), 1) if det_snr else None,
                "coverage_frac": round(float(np.mean(cov >= 0.5)), 3),
                "mean_zodi": round(float(np.mean([g["zodi"] for g in grp])), 4),
                "flag_counts": flag_counts,
                "data_b64": base64.b64encode(ep_img.astype(np.float32).tobytes()).decode("ascii"),
                "flags_b64": base64.b64encode(flg_or.astype(np.int32).tobytes()).decode("ascii"),
                "cov_b64": base64.b64encode(np.clip(cov * 255.0, 0, 255).astype(np.uint8).tobytes()).decode("ascii"),
                "exposures": [
                    {
                        "obs_id": g["row"]["obs_id"], "band": g["row"]["band"], "release": g["row"].get("release"),
                        "mjd": round(g["mjd"], 6), "date_iso": Time(g["mjd"], format="mjd").isot[:19],
                        "wavelength_um": g["phot"].get("wavelength_um"), "bandwidth_um": g["phot"].get("bandwidth_um"),
                        "psf_fwhm_arcsec": g["phot"].get("psf_fwhm_arcsec"), "zodi": round(g["zodi"], 4),
                        "bad_pct": round(g["bad_frac"], 2), "source": g["cut"]["source"],
                        "flux_ujy": g["phot"].get("flux_ujy"), "err_ujy": g["phot"].get("err_ujy"), "snr": g["phot"].get("snr"),
                        "quality": g["phot"].get("quality"), "lvf_edge": g["phot"].get("lvf_edge"),
                    }
                    for g in grp
                ],
            })

    # ---------------- Sin datos multi-época: imagen estática del cubo DR1
    if not epochs_out:
        try:
            dr1_img, dr1_info = build_dr1_static_image(ra, dec, norm_bands, common_wcs, shape)
        except Exception:
            dr1_img, dr1_info = None, {}
        if dr1_img is not None:
            data_mode = "dr1_static"
            cov = np.isfinite(dr1_img).astype(np.float32)
            bg = float(np.nanmedian(dr1_img))
            ep_img = np.where(np.isfinite(dr1_img), dr1_img - bg, 0.0).astype(np.float32)
            mjd_mid = 0.5 * (DR1_MJD_RANGE[0] + DR1_MJD_RANGE[1])
            ra_t, dec_t = _target_radec(mjd_mid)
            tx, ty = [float(v) for v in common_wcs.world_to_pixel_values(ra_t, dec_t)]
            target_track.append({"epoch_index": 0, "mjd": round(mjd_mid, 5), "ra": round(ra_t, 6), "dec": round(dec_t, 6), "px": round(tx, 2), "py": round(ty, 2)})
            epoch_arrays.append(ep_img)
            coverage_arrays.append(cov)
            epochs_out.append({
                "index": 0, "mjd": round(mjd_mid, 4), "date": "DR1 2025-04-24 → 2026-05-14",
                "mjd_min": DR1_MJD_RANGE[0], "mjd_max": DR1_MJD_RANGE[1], "n_exp": 0, "bands": norm_bands,
                "lam_min_um": round(min(dr1_info.get("wavelengths_um", [0])), 3), "lam_max_um": round(max(dr1_info.get("wavelengths_um", [0])), 3),
                "peak_sb_mjy_sr": None, "rms_mjy_sr": None, "snr": None, "n_target_detections": 0,
                "coverage_frac": round(float(np.mean(cov)), 3), "mean_zodi": 0.0, "flag_counts": {},
                "data_b64": base64.b64encode(ep_img.tobytes()).decode("ascii"),
                "flags_b64": base64.b64encode(np.zeros(shape, dtype=np.int32).tobytes()).decode("ascii"),
                "cov_b64": base64.b64encode((cov * 255).astype(np.uint8).tobytes()).decode("ascii"),
                "exposures": [], "is_static_dr1": True,
                "dr1_channels": dr1_info.get("channels", []), "dr1_tiles": dr1_info.get("tiles", []),
            })
            notes.append({"level": "warn",
                          "es": "Sin exposiciones L2b disponibles" + (" (IRSA no responde)" if not tap_ok else "") + ": se muestra UNA imagen estática del cubo DR1 (co-adición de un año, píxeles de 12.9″). No hay blink, diferencia ni curva de luz reales." + (" La app reintentará IRSA automáticamente en unos 2 minutos." if not tap_ok else ""),
                          "en": "No L2b exposures available" + (" (IRSA is not responding)" if not tap_ok else "") + ": showing ONE static image from the DR1 cube (one-year co-add, 12.9″ pixels). There is no real blink, difference or light curve." + (" The app will retry IRSA automatically in about 2 minutes." if not tap_ok else "")})
        else:
            return {"error": ("IRSA TAP no responde y no se pudo leer el cubo DR1." if not tap_ok else "No hay datos SPHEREx en esta posición."),
                    "tap_status": dict(_TAP_STATUS)}

    # ---------------- Estadística global de visualización
    all_vals = np.concatenate([a[c >= 0.5].ravel() for a, c in zip(epoch_arrays, coverage_arrays)]) if epoch_arrays else np.zeros(1)
    if all_vals.size < 50:
        all_vals = np.concatenate([a.ravel() for a in epoch_arrays])
    p01, p05, p50, p95, p995 = [float(x) for x in np.percentile(all_vals, [1.0, 5.0, 50.0, 95.0, 99.5])]
    sky_clip = all_vals[(all_vals >= p05) & (all_vals <= np.percentile(all_vals, 85.0))]
    sky_med = float(np.median(sky_clip)) if sky_clip.size else p50
    sky_sigma = max(1.4826 * float(np.median(np.abs(sky_clip - sky_med))) if sky_clip.size else 0.01, 1e-6)

    candidates = detect_candidates(epoch_arrays, common_wcs, pix_arcsec, coverage_arrays) if data_mode == "l2b" else []
    mean_mjd = float(np.mean([e["mjd"] for e in epochs_out]))
    if not catalogs.get("gaia") and not catalogs.get("allwise"):
        catalogs = fetch_catalog_sources(ra, dec, cat_radius)
    ref_tracks = []
    for t in refs_in_field:
        ra_r, de_r = propagate_astrometry(t["astrometry"], mean_mjd)
        ref_tracks.append({"id": t["id"], "ra": ra_r, "dec": de_r})
    with np.errstate(all="ignore"):
        coadd = np.nanmean(np.array(epoch_arrays), axis=0)
    recognized = recognize_celestial_objects(coadd, common_wcs, pix_arcsec, mean_mjd, catalogs, ref_tracks, coarse=(data_mode == "dr1_static"))
    _annotate_candidates(candidates, catalogs, refs_in_field, epochs_out, common_wcs, pix_arcsec)
    _verify_candidates_with_psf(candidates, items, epochs_out, catalogs)
    _order = {"confirmed_motion": 0, "confirmed_variability": 1, "unverified": 2, "not_confirmed": 3}
    candidates.sort(key=lambda c: (_order.get(c.get("verification", "unverified"), 2), -c["snr_diff"]))
    for i, c in enumerate(candidates, start=1):
        c["rank"] = i

    # ---------------- Objetivo, movimiento esperado y resumen fotométrico
    target_info = None
    if astrom:
        t_meta = tgt_obj or {}
        motion = None
        if len(target_track) >= 2:
            a0, a1 = target_track[0], target_track[-1]
            sep = float(SkyCoord(a0["ra"] * u.deg, a0["dec"] * u.deg).separation(SkyCoord(a1["ra"] * u.deg, a1["dec"] * u.deg)).arcsec)
            motion = {"arcsec": round(sep, 2), "native_px": round(sep / PIX_SCALE_NATIVE, 2), "days": round(a1["mjd"] - a0["mjd"], 1)}
        target_info = {
            "measured_motion": _measured_target_motion(photometry, astrom),
            "id": target_id, "name": t_meta.get("name") or (user_astrometry or {}).get("name") or "Objetivo",
            "astrometry": astrom, "distance_pc": t_meta.get("distance_pc"), "distance_ref": t_meta.get("distance_ref"),
            "sptype": t_meta.get("sptype"), "teff_k_lit": t_meta.get("teff_k_lit"), "teff_ref": t_meta.get("teff_ref"),
            "object_kind": t_meta.get("object_kind", "generic"), "saturates": bool(t_meta.get("saturates")),
            "prompt_epoch_note": t_meta.get("prompt_epoch_note"), "prompt_epoch_note_en": t_meta.get("prompt_epoch_note_en"),
            "expected_motion": motion,
        }
    good_phot = [p for p in photometry if p["quality"] in ("good", "warning")]
    sat_phot = [p for p in photometry if p["quality"] == "saturated"]
    if photometry and len(sat_phot) >= max(1, len(photometry) // 2):
        notes.append({"level": "warn", "es": f"El objetivo aparece saturado en {len(sat_phot)} de {len(photometry)} exposiciones: su flujo no es fiable (la posición sí).",
                      "en": f"The target appears saturated in {len(sat_phot)} of {len(photometry)} exposures: its flux is not reliable (its position is)."})
    if not tap_ok and data_mode != "l2b":
        notes.append({"level": "warn", "es": "IRSA (TAP y SIA) no respondió: " + str(_TAP_STATUS.get("error") or "sin detalle"), "en": "IRSA (TAP and SIA) did not respond: " + str(_TAP_STATUS.get("error") or "no detail")})
    elif tap_ok and _TAP_STATUS.get("via") == "SIA":
        notes.append({"level": "info", "es": "Exposiciones obtenidas con el servicio SIA de IRSA (TAP no respondió).", "en": "Exposures retrieved with the IRSA SIA service (TAP did not respond)."})
    elif tap_ok and _TAP_STATUS.get("via") == "snapshot":
        snap_d = str((_TAP_STATUS.get("snapshot") or {}).get("date_utc") or "")[:10]
        notes.append({"level": "info",
                      "es": f"IRSA no responde: se usa la lista oficial de exposiciones de este objetivo guardada en el proyecto (consulta IRSA SIA del {snap_d}). Las imágenes L2b se leen en vivo desde AWS S3.",
                      "en": f"IRSA is not responding: using this target's official exposure list stored in the project (IRSA SIA query of {snap_d}). The L2b images are read live from AWS S3."})

    light_curve = build_light_curve(photometry)
    quality = _build_data_quality(items, epochs_out, photometry, all_rows, tap_ok, data_mode)
    mpc = _build_mpc_report(candidates, items, epochs_out, target_info)

    band_summary = {}
    for d_key, d_info in DETECTOR_INFO.items():
        band_summary[d_key] = {**d_info, "count": (sum(1 for r in all_cov if r["band"] == d_key) if tap_ok else None)}

    result_payload = {
        "ra": ra, "dec": dec, "fov_deg": size_deg, "shape": [ny, nx], "pix_scale_arcsec": round(pix_arcsec, 4),
        "wcs": {"crval": [ra, dec], "crpix": [nx / 2.0 + 0.5, ny / 2.0 + 0.5], "cdelt": [-pix_arcsec / 3600.0, pix_arcsec / 3600.0]},
        "stats": {"p01": p01, "p05": p05, "p50": p50, "p95": p95, "p995": p995, "sky_med": round(sky_med, 6), "sky_sigma": round(sky_sigma, 6)},
        "data_mode": data_mode,
        "data_source": {"l2b": "SPHEREx L2b (IRSA / AWS S3)", "dr1_static": "SPHEREx DR1 All-Sky Cube (co-adición estática)"}.get(data_mode, "—"),
        "notes": notes,
        "tap_status": {"ok": tap_ok, "error": _TAP_STATUS.get("error"), "via": _TAP_STATUS.get("via"), "snapshot": _TAP_STATUS.get("snapshot")},
        "retry_after_s": (int(SERVICE_RETRY_S) + 5) if (data_mode != "l2b" and not tap_ok) else None,
        "requested_bands": norm_bands, "release": release,
        "total_matching_irsa": len(all_rows), "total_all_bands_irsa": len(all_cov) if tap_ok else None,
        "used_exposures": len(items),
        "epochs": epochs_out,
        "target": target_info,
        "target_track": target_track,
        "reference_targets_in_field": [{"id": t["id"], "name": t["name"]} for t in refs_in_field],
        "photometry": photometry,
        "spectrum": sorted([p for p in photometry if p.get("wavelength_um")], key=lambda s: s["wavelength_um"]),
        "light_curve": light_curve,
        "band_summary": band_summary,
        "flag_definitions": FLAG_DEFINITIONS,
        "masks": {"display_reject": list(DISPLAY_REJECT_NAMES), "photometry": list(PHOT_MASK_NAMES)},
        "candidates": candidates,
        "recognized_objects": recognized,
        "catalogs_ok": bool(catalogs.get("ok")),
        "data_quality": quality,
        "mpc_report": mpc["lines"],
        "mpc_info": mpc,
        "photometry_summary": {"n": len(photometry), "n_detected": len(good_phot), "n_saturated": len(sat_phot),
                               "median_snr": round(float(np.median([p["snr"] for p in good_phot])), 2) if good_phot else None},
        "dois": IRSA_DOIS,
    }
    result_payload["math_telemetry"] = _build_equations(result_payload)
    result_payload["elapsed_sec"] = round(time.time() - t0, 2)
    result_payload["ai_analysis_es"] = generate_ai_preliminary_analysis(result_payload, lang="es")
    result_payload["ai_analysis_en"] = generate_ai_preliminary_analysis(result_payload, lang="en")

    memo_key = f"{ra:.4f}_{dec:.4f}_{size_deg:.3f}_{','.join(norm_bands)}"
    _CUBE_MEMO[memo_key] = {
        "rows": [it["row"] for it in items], "fetch_args": (ra, dec, size_deg), "shape": shape, "pix_arcsec": pix_arcsec,
        "wcs": common_wcs, "target_track": target_track, "astrometry": astrom, "target_id": target_id,
    }
    if memo_key in _CUBE_MEMO_ORDER:
        _CUBE_MEMO_ORDER.remove(memo_key)
    _CUBE_MEMO_ORDER.append(memo_key)
    while len(_CUBE_MEMO_ORDER) > 8:
        _CUBE_MEMO.pop(_CUBE_MEMO_ORDER.pop(0), None)

    if data_mode == "l2b":
        _CUBE_RESP_CACHE[cube_hash] = result_payload
        try:
            with open(cube_cache_path, "w", encoding="utf-8") as f:
                json.dump(result_payload, f)
        except Exception:
            pass
    return result_payload


SATCORE_SYS_ARCSEC = 0.7  # sistemático por eje y por visita del centroide del núcleo saturado (dispersión entre 8 visitas de R Dra)


def _measured_target_motion(photometry: List[Dict[str, Any]], astrom: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Desplazamiento MEDIDO del objetivo entre la primera y la última visita (grupos separados > 30 d) a partir de las
    posiciones medidas (ePSF o núcleo saturado), comparado con el predicho por la astrometría de catálogo entre las
    mismas fechas. Error de cada visita = error estándar de sus exposiciones y, para el núcleo saturado, un sistemático
    de SATCORE_SYS_ARCSEC por eje (la forma de la mancha saturada cambia con la orientación de la nave). Con ≥3 visitas
    se ajusta un movimiento lineal ponderado a todas ellas; con 2, se restan sus medias.
    """
    pts = sorted([p for p in photometry if p.get("ra_meas") is not None and p.get("mjd")], key=lambda p: p["mjd"])
    if len(pts) < 4:
        return None
    visits: List[List[Dict[str, Any]]] = [[pts[0]]]
    for p in pts[1:]:
        if p["mjd"] - visits[-1][-1]["mjd"] > 30.0:
            visits.append([p])
        else:
            visits[-1].append(p)
    ra_ref, dec_ref = pts[0]["ra_meas"], pts[0]["dec_meas"]
    cosd = float(np.cos(np.deg2rad(dec_ref)))

    def _off(p: Dict[str, Any]) -> Tuple[float, float]:
        return (((p["ra_meas"] - ra_ref + 180.0) % 360.0 - 180.0) * cosd * 3600.0, (p["dec_meas"] - dec_ref) * 3600.0)

    # Dispersión por exposición combinada (para visitas con una sola exposición)
    res_x: List[float] = []
    res_y: List[float] = []
    for v in visits:
        if len(v) >= 2:
            o = np.array([_off(p) for p in v])
            res_x += list(o[:, 0] - o[:, 0].mean())
            res_y += list(o[:, 1] - o[:, 1].mean())
    n_multi = sum(1 for v in visits if len(v) >= 2)
    dof = len(res_x) - n_multi
    pooled = (float(np.sqrt(np.sum(np.square(res_x)) / dof)), float(np.sqrt(np.sum(np.square(res_y)) / dof))) if dof > 0 else None

    vstats = []
    for v in visits:
        o = np.array([_off(p) for p in v])
        n = len(v)
        if n >= 2:
            ex, ey = float(np.std(o[:, 0], ddof=1) / np.sqrt(n)), float(np.std(o[:, 1], ddof=1) / np.sqrt(n))
        elif pooled:
            ex, ey = pooled
        else:
            continue
        sysf = SATCORE_SYS_ARCSEC if any(p.get("astrometry_method") == "saturated_core" for p in v) else 0.0
        vstats.append({"t": float(np.mean([p["mjd"] for p in v])), "x": float(o[:, 0].mean()), "y": float(o[:, 1].mean()),
                       "ex": float(np.hypot(ex, sysf)), "ey": float(np.hypot(ey, sysf)), "n": n})
    if len(vstats) < 2 or vstats[-1]["t"] - vstats[0]["t"] < 30.0:
        return None
    t0, t1 = vstats[0]["t"], vstats[-1]["t"]
    chi2_red = None
    if len(vstats) == 2:
        a, b = vstats
        dra, dde = b["x"] - a["x"], b["y"] - a["y"]
        era, ede = float(np.hypot(a["ex"], b["ex"])), float(np.hypot(a["ey"], b["ey"]))
    else:
        tt = np.array([v["t"] for v in vstats]) - t0
        span = t1 - t0
        fits = []
        chi = 0.0
        for key, ekey in (("x", "ex"), ("y", "ey")):
            yv = np.array([v[key] for v in vstats])
            wv = 1.0 / np.array([v[ekey] for v in vstats]) ** 2
            A = np.stack([np.ones_like(tt), tt], axis=1)
            cov = np.linalg.inv(A.T @ (A * wv[:, None]))
            coef = cov @ (A.T @ (yv * wv))
            chi += float(np.sum((yv - A @ coef) ** 2 * wv))
            fits.append((coef[1] * span, float(np.sqrt(cov[1, 1])) * span))
        (dra, era), (dde, ede) = fits
        chi2_red = round(chi / max(2 * (len(vstats) - 2), 1), 2)
    sep = float(np.hypot(dra, dde))
    err = float(np.sqrt((dra / sep) ** 2 * era ** 2 + (dde / sep) ** 2 * ede ** 2)) if sep > 0 else float(np.hypot(era, ede))
    pr0, pd0 = propagate_astrometry(astrom, t0)
    pr1, pd1 = propagate_astrometry(astrom, t1)
    p_dra = ((pr1 - pr0 + 180.0) % 360.0 - 180.0) * np.cos(np.deg2rad(0.5 * (pd0 + pd1))) * 3600.0
    p_dde = (pd1 - pd0) * 3600.0
    # Acuerdo con la predicción: diferencia vectorial en unidades de σ
    diff_sigma = float(np.hypot((dra - p_dra) / max(era, 1e-3), (dde - p_dde) / max(ede, 1e-3)))
    methods = sorted({p.get("astrometry_method", "epsf") for p in pts})
    return {
        "arcsec": round(sep, 2), "err_arcsec": round(err, 2),
        "pa_deg": round(float(np.degrees(np.arctan2(dra, dde)) % 360.0), 1),
        "dra_arcsec": round(float(dra), 2), "ddec_arcsec": round(float(dde), 2),
        "err_dra_arcsec": round(float(era), 2), "err_ddec_arcsec": round(float(ede), 2),
        "predicted_arcsec": round(float(np.hypot(p_dra, p_dde)), 2),
        "predicted_pa_deg": round(float(np.degrees(np.arctan2(p_dra, p_dde)) % 360.0), 1),
        "diff_sigma": round(diff_sigma, 1), "chi2_red": chi2_red,
        "days": round(t1 - t0, 1), "n_visits": len(vstats), "n_first": vstats[0]["n"], "n_last": vstats[-1]["n"], "methods": methods,
        "sys_floor_arcsec": SATCORE_SYS_ARCSEC if "saturated_core" in methods else 0.0,
        "date_first": Time(t0, format="mjd").isot[:10], "date_last": Time(t1, format="mjd").isot[:10],
    }


def build_light_curve(photometry: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Curva de luz honesta: SPHEREx mide cada exposición a una λ distinta (filtro LVF), así que los puntos
    se agrupan por canal DR1 (misma λ). La variabilidad solo se evalúa dentro de un mismo canal.
    """
    usable = [p for p in photometry if p.get("wavelength_um") and p.get("flux_ujy") is not None and p["quality"] in ("good", "warning") and not p.get("lvf_edge")]
    by_ch: Dict[int, List[Dict[str, Any]]] = {}
    for p in usable:
        ch = dr1_channel_for_wavelength(p["wavelength_um"])
        if ch is not None:
            by_ch.setdefault(ch, []).append(p)
    tbl = dr1_channel_table()
    series = []
    best = None
    for ch, pts in sorted(by_ch.items()):
        pts = sorted(pts, key=lambda q: q["mjd"])
        entry = {"ch": ch, "wavelength_um": tbl[ch]["wavelength_um"], "band": f"D{tbl[ch]['detector']}",
                 "points": [{"mjd": q["mjd"], "flux_ujy": q["flux_ujy"], "err_ujy": q["err_ujy"], "epoch_index": q.get("epoch_index"), "obs_id": q["obs_id"]} for q in pts]}
        if len({q.get("epoch_index") for q in pts}) >= 2:
            f = np.array([q["flux_ujy"] for q in pts])
            e = np.array([q["err_ujy"] for q in pts])
            wm = float(np.sum(f / e ** 2) / np.sum(1 / e ** 2))
            chi2 = float(np.sum(((f - wm) / e) ** 2) / max(len(f) - 1, 1))
            i_max, i_min = int(np.argmax(f)), int(np.argmin(f))
            dsig = float((f[i_max] - f[i_min]) / np.hypot(e[i_max], e[i_min]))
            entry.update({"chi2_red_const": round(chi2, 2), "max_change_sigma": round(dsig, 2),
                          "max_ratio": round(float(f[i_max] / f[i_min]), 3) if f[i_min] > 0 else None})
            if best is None or dsig > best["max_change_sigma"]:
                best = {"ch": ch, "wavelength_um": entry["wavelength_um"], "max_change_sigma": round(dsig, 2), "max_ratio": entry.get("max_ratio")}
        series.append(entry)
    return {"series": series, "strongest_change": best, "n_points": len(usable),
            "note_es": "Cada serie agrupa mediciones a la misma λ (canal DR1). No compares puntos de colores distintos como si fueran variabilidad.",
            "note_en": "Each series groups measurements at the same λ (DR1 channel). Do not compare points of different colours as if they were variability."}


def _annotate_candidates(cands: List[Dict[str, Any]], catalogs: Dict[str, Any], refs: List[Dict[str, Any]], epochs: List[Dict[str, Any]], common_wcs: WCS, pix_arcsec: float) -> None:
    """Compara cada candidato con Gaia DR3 y con el movimiento predicho de los objetivos de referencia."""
    if not cands or len(epochs) < 2:
        return
    mjd0, mjd1 = epochs[0]["mjd"], epochs[-1]["mjd"]
    dt_yr = max((mjd1 - mjd0) / 365.25, 1e-3)
    j0 = float(Time(mjd0, format="mjd").jyear)
    j1 = float(Time(mjd1, format="mjd").jyear)
    for c in cands:
        c["notes_es"], c["notes_en"] = [], []
        if c["type"] == "dipole":
            c["pm_arcsec_yr"] = round(c["shift_arcsec"] / dt_yr, 2)
            dx = c["px"] - c["px_old"]
            dy = c["py"] - c["py_old"]
            c["pa_deg"] = round(float(np.rad2deg(np.arctan2(-dx, dy)) % 360.0), 1)  # Norte arriba, Este a la izquierda
            if c["shift_arcsec"] < PIX_SCALE_NATIVE:
                c["notes_es"].append("Desplazamiento menor que 1 píxel nativo (6.15″): la medida es aproximada.")
                c["notes_en"].append("Shift smaller than 1 native pixel (6.15″): the measurement is approximate.")
        else:
            c["pm_arcsec_yr"] = None
            c["pa_deg"] = None
        match = None
        for t in refs:
            ra0, de0 = propagate_astrometry(t["astrometry"], mjd0)
            ra1, de1 = propagate_astrometry(t["astrometry"], mjd1)
            d_now = SkyCoord(c["ra"] * u.deg, c["dec"] * u.deg).separation(SkyCoord(ra1 * u.deg, de1 * u.deg)).arcsec
            if d_now <= 9.0:
                pred = float(SkyCoord(ra0 * u.deg, de0 * u.deg).separation(SkyCoord(ra1 * u.deg, de1 * u.deg)).arcsec)
                match = {"kind": "reference_target", "id": t["id"], "name": t["name"], "sep_arcsec": round(float(d_now), 2), "predicted_shift_arcsec": round(pred, 2)}
                if c["type"] == "dipole":
                    ok = abs(c["shift_arcsec"] - pred) <= max(0.5 * pred, 0.5 * PIX_SCALE_NATIVE)
                    c["consistent_with_catalog_motion"] = bool(ok)
                    c["notes_es"].append(f"Coincide con {t['name']}: desplazamiento predicho {pred:.1f}″, medido {c['shift_arcsec']:.1f}″ ({'consistente' if ok else 'no consistente'}).")
                    c["notes_en"].append(f"Matches {t['name']}: predicted shift {pred:.1f}″, measured {c['shift_arcsec']:.1f}″ ({'consistent' if ok else 'not consistent'}).")
                else:
                    c["notes_es"].append(f"Coincide con {t['name']} (movimiento predicho entre épocas: {pred:.1f}″).")
                    c["notes_en"].append(f"Matches {t['name']} (predicted motion between epochs: {pred:.1f}″).")
                break
        if match is None:
            for g in catalogs.get("gaia", []):
                ra_e, de_e = _propagate_linear(g["ra"], g["dec"], g["pmra"], g["pmdec"], 2016.0, j1)
                d = float(np.hypot(((ra_e - c["ra"] + 180) % 360 - 180) * np.cos(np.deg2rad(c["dec"])), de_e - c["dec"]) * 3600.0)
                if d <= 6.0:
                    pm_tot = float(np.hypot(g["pmra"], g["pmdec"])) / 1000.0
                    match = {"kind": "gaia", "id": g["id"], "sep_arcsec": round(d, 2), "gmag": g.get("gmag"), "pm_total_arcsec_yr": round(pm_tot, 3)}
                    pred = pm_tot * (j1 - j0)
                    c["notes_es"].append(f"Coincide con {g['id']} (G={g.get('gmag')}); su movimiento propio predice {pred:.2f}″ entre épocas.")
                    c["notes_en"].append(f"Matches {g['id']} (G={g.get('gmag')}); its proper motion predicts {pred:.2f}″ between epochs.")
                    if c["type"] == "dipole" and pred < 0.5 * PIX_SCALE_NATIVE:
                        c["notes_es"].append("Una estrella con movimiento tan pequeño no produce un dipolo real: probablemente es un residuo (PSF o λ distinta entre épocas).")
                        c["notes_en"].append("A star with such small motion cannot produce a real dipole: this is probably a residual (different PSF or λ between epochs).")
                        c["likely_artifact"] = True
                    break
        c["catalog_match"] = match
        if c["type"] == "variable":
            c["notes_es"].append("Las épocas pueden tener λ distintas dentro de la banda: confirma la variabilidad en la curva de luz por canal.")
            c["notes_en"].append("Epochs may have different λ within the band: confirm variability in the per-channel light curve.")


def _verify_candidates_with_psf(cands: List[Dict[str, Any]], items: List[Dict[str, Any]], epochs: List[Dict[str, Any]], catalogs: Dict[str, Any]) -> None:
    """
    La imagen de diferencia solo PROPONE ubicaciones: con píxeles de 6.15″ (PSF submuestreada) el pico de una estrella
    cambia mucho con la fase subpíxel y con la λ. Cada candidato se verifica midiendo, exposición por exposición,
    centroide y flujo con la ePSF oficial:
      - movimiento: desplazamiento de centroides entre la primera y la última época ≥ 3σ y ≥ 0.3 píxeles nativos;
      - variabilidad: cambio de flujo ≥ 5σ entre mediciones a la MISMA λ (mismo canal DR1) en épocas distintas, en
        al menos 2 pares independientes con el mismo signo, sin mediciones saturadas ni en el borde del detector/LVF.
    """
    if not cands or len(epochs) < 2:
        for c in cands:
            c["verification"] = "unverified"
        return
    first_ids = {e["obs_id"] for e in epochs[0]["exposures"]}
    last_ids = {e["obs_id"] for e in epochs[-1]["exposures"]}
    by_id = {it["row"]["obs_id"]: it for it in items}
    for c in cands[:4]:
        meas_first, meas_last = [], []
        for oid in first_ids:
            it = by_id.get(oid)
            if it:
                m = fit_source_position(it["cut"], c["ra_old"], c["dec_old"])
                if m and m["snr"] >= 5:
                    meas_first.append(m)
        for oid in last_ids:
            it = by_id.get(oid)
            if it:
                m = fit_source_position(it["cut"], c["ra"], c["dec"])
                if m and m["snr"] >= 5:
                    meas_last.append(m)
        # Las mediciones con OVERFLOW/NONLINEAR/BLOOM no sirven para verificar: alrededor de una estrella saturada el
        # ajuste cae en el núcleo o en el blooming, cuya forma cambia con la orientación de la nave entre visitas y
        # produce "movimientos" de varios segundos de arco que no son reales (validado con RW Aur y R Dra).
        n_sat = sum(1 for m in meas_first + meas_last if m["saturated"])
        meas_first = [m for m in meas_first if not m["saturated"]]
        meas_last = [m for m in meas_last if not m["saturated"]]
        c["n_psf_saturated"] = n_sat
        if n_sat and (not meas_first or not meas_last):
            is_ref = (c.get("catalog_match") or {}).get("kind") == "reference_target"
            if is_ref:
                c["verification"] = "unverified"
                c["label_es"] = "Estrella saturada: su movimiento se mide con el núcleo saturado"
                c["label_en"] = "Saturated star: its motion is measured from the saturated core"
            else:
                c["verification"] = "not_confirmed"
                c["likely_artifact"] = True
                c["label_es"] = "Artefacto de estrella saturada (OVERFLOW/BLOOM)"
                c["label_en"] = "Saturated-star artifact (OVERFLOW/BLOOM)"
            c["notes_es"] = c.get("notes_es", []) + [f"{n_sat} mediciones caen en píxeles saturados o con blooming: no se usan para verificar movimiento ni variabilidad."]
            c["notes_en"] = c.get("notes_en", []) + [f"{n_sat} measurements fall on saturated or bloomed pixels: they are not used to verify motion or variability."]
            continue
        c["n_psf_first"], c["n_psf_last"] = len(meas_first), len(meas_last)
        if not meas_first or not meas_last:
            c["verification"] = "unverified"
            c["notes_es"] = c.get("notes_es", []) + ["No hay S/N ≥ 5 en las exposiciones individuales para verificar con la ePSF."]
            c["notes_en"] = c.get("notes_en", []) + ["No S/N ≥ 5 in individual exposures to verify with the ePSF."]
            continue

        def _mean_pos(ms: List[Dict[str, Any]]) -> Tuple[float, float, float]:
            wts = np.array([1.0 / m["pos_err_arcsec"] ** 2 for m in ms])
            ra_m = float(np.sum([m["ra"] for m in ms] * wts) / wts.sum())
            de_m = float(np.sum([m["dec"] for m in ms] * wts) / wts.sum())
            return ra_m, de_m, float(1.0 / np.sqrt(wts.sum()))

        r0, d0, e0 = _mean_pos(meas_first)
        r1, d1, e1 = _mean_pos(meas_last)
        shift = float(SkyCoord(r0 * u.deg, d0 * u.deg).separation(SkyCoord(r1 * u.deg, d1 * u.deg)).arcsec)
        s_err = float(np.hypot(e0, e1))
        c["psf_shift_arcsec"] = round(shift, 2)
        c["psf_shift_err_arcsec"] = round(s_err, 2)
        moving = shift >= max(3.0 * s_err, 0.3 * PIX_SCALE_NATIVE)
        flux_change = None
        pairs = []
        for a in meas_first:
            ca = dr1_channel_for_wavelength(a["wavelength_um"])
            if a.get("lvf_edge") or a["saturated"]:
                continue
            for b in meas_last:
                if b.get("lvf_edge") or b["saturated"]:
                    continue
                if ca is not None and ca == dr1_channel_for_wavelength(b["wavelength_um"]):
                    sig = abs(b["flux_ujy"] - a["flux_ujy"]) / float(np.hypot(a["err_ujy"], b["err_ujy"]))
                    pairs.append((sig, a, b))
                    if flux_change is None or sig > flux_change["sigma"]:
                        flux_change = {"sigma": round(sig, 1), "ratio": round(b["flux_ujy"] / a["flux_ujy"], 3) if a["flux_ujy"] > 0 else None, "wavelength_um": round(a["wavelength_um"], 3)}
        # Pares independientes (sin repetir exposición) con cambio ≥ 5σ y el mismo signo: una sola medición anómala
        # (rayo cósmico, borde del filtro) no basta para afirmar variabilidad.
        used_a, used_b, n_up, n_down = set(), set(), 0, 0
        for sig, a, b in sorted(pairs, key=lambda q: -q[0]):
            if sig < 5 or id(a) in used_a or id(b) in used_b:
                continue
            used_a.add(id(a)); used_b.add(id(b))
            if b["flux_ujy"] > a["flux_ujy"]:
                n_up += 1
            else:
                n_down += 1
        if flux_change is not None:
            flux_change["n_pairs_5sigma"] = max(n_up, n_down)
            flux_change["consistent"] = (n_up == 0 or n_down == 0)
        c["psf_flux_change"] = flux_change
        if moving:
            c["verification"] = "confirmed_motion"
            c["type"] = "dipole"
            dt_yr = max((meas_last[0]["mjd"] - meas_first[0]["mjd"]) / 365.25, 1e-3)
            c["pm_arcsec_yr"] = round(shift / dt_yr, 2)
            c["label_es"] = f"Movimiento confirmado ({shift:.1f}″ ± {s_err:.1f}″)"
            c["label_en"] = f"Confirmed motion ({shift:.1f}″ ± {s_err:.1f}″)"
        elif flux_change and flux_change["sigma"] >= 5 and flux_change.get("n_pairs_5sigma", 0) >= 2 and flux_change.get("consistent"):
            c["verification"] = "confirmed_variability"
            c["type"] = "variable"
            c["label_es"] = f"Variabilidad confirmada a {flux_change['wavelength_um']} µm (×{flux_change['ratio']}, {flux_change['sigma']}σ, {flux_change['n_pairs_5sigma']} pares)"
            c["label_en"] = f"Confirmed variability at {flux_change['wavelength_um']} µm (×{flux_change['ratio']}, {flux_change['sigma']}σ, {flux_change['n_pairs_5sigma']} pairs)"
        elif flux_change and flux_change["sigma"] >= 5:
            c["verification"] = "unverified"
            c["label_es"] = f"Posible variabilidad a {flux_change['wavelength_um']} µm ({flux_change['sigma']}σ en un solo par)"
            c["label_en"] = f"Possible variability at {flux_change['wavelength_um']} µm ({flux_change['sigma']}σ in a single pair)"
            c["notes_es"] = c.get("notes_es", []) + ["Un solo par de mediciones a igual λ supera 5σ: hace falta otra medición independiente para confirmarlo."]
            c["notes_en"] = c.get("notes_en", []) + ["Only one same-λ pair exceeds 5σ: another independent measurement is needed to confirm it."]
        else:
            c["verification"] = "not_confirmed"
            c["likely_artifact"] = True
            c["label_es"] = "No confirmado (residuo de PSF/λ)"
            c["label_en"] = "Not confirmed (PSF/λ residual)"
            reason_es = f"La ePSF no muestra desplazamiento (medido {shift:.2f}″ ± {s_err:.2f}″)" + (
                f" ni cambio de flujo a igual λ ({flux_change['sigma']}σ)." if flux_change else " y no hay mediciones a la misma λ en ambas épocas para evaluar variabilidad.")
            reason_en = f"The ePSF shows no shift (measured {shift:.2f}″ ± {s_err:.2f}″)" + (
                f" and no same-λ flux change ({flux_change['sigma']}σ)." if flux_change else " and there are no same-λ measurements in both epochs to assess variability.")
            c["notes_es"] = c.get("notes_es", []) + [reason_es]
            c["notes_en"] = c.get("notes_en", []) + [reason_en]
    for c in cands[4:]:
        c["verification"] = "unverified"


def _build_data_quality(items: List[Dict[str, Any]], epochs: List[Dict[str, Any]], photometry: List[Dict[str, Any]], rows: List[Dict[str, Any]], tap_ok: bool, data_mode: str) -> Dict[str, Any]:
    tot: Dict[str, int] = {}
    for ep in epochs:
        for k, v in ep.get("flag_counts", {}).items():
            tot[k] = tot.get(k, 0) + int(v)
    n_epsf = sum(1 for it in items if it["cut"].get("psf") is not None)
    he_hits = sum(1 for p in photometry if p.get("wavelength_um") and p.get("bandwidth_um") and abs(p["wavelength_um"] - 1.083) <= p["bandwidth_um"])
    sat = sum(1 for p in photometry if p["quality"] == "saturated")
    zodi = [it["zodi"] for it in items]
    snap_d = str((_TAP_STATUS.get("snapshot") or {}).get("date_utc") or "")[:10]
    via = {"TAP": "TAP", "SIA": "SIA", "caché": "caché local de una consulta TAP/SIA",
           "snapshot": f"lista oficial guardada, consulta SIA del {snap_d}"}.get(str(_TAP_STATUS.get("via")), "TAP/SIA")
    via_en = {"TAP": "TAP", "SIA": "SIA", "caché": "local cache of a TAP/SIA query",
              "snapshot": f"stored official list, SIA query of {snap_d}"}.get(str(_TAP_STATUS.get("via")), "TAP/SIA")
    checks = [
        {"id": "source", "status": data_mode.upper(), "title_es": "Origen de los datos", "title_en": "Data origin",
         "metric": f"{len(items)} exp L2b" if data_mode == "l2b" else "DR1 estático",
         "metric_en": f"{len(items)} L2b exp" if data_mode == "l2b" else "Static DR1",
         "desc_es": (f"IRSA ({via}): {len(rows)} exposiciones encontradas en las bandas pedidas.") if tap_ok else "IRSA (TAP y SIA) no respondió.",
         "desc_en": (f"IRSA ({via_en}): {len(rows)} exposures found in the requested bands.") if tap_ok else "IRSA (TAP and SIA) did not respond."},
        {"id": "zodi", "status": "SUBTRACTED" if zodi else "N/A", "title_es": "Luz zodiacal (extensión ZODI)", "title_en": "Zodiacal light (ZODI layer)",
         "metric": f"{np.mean(zodi):.3f} MJy/sr" if zodi else "—",
         "desc_es": "Modelo oficial restado píxel a píxel en cada exposición. La línea atmosférica de He I (1.083 µm) y la auroral NO se modelan.",
         "desc_en": "Official model subtracted pixel by pixel in each exposure. The atmospheric He I (1.083 µm) and auroral lines are NOT modelled."},
        {"id": "masked", "status": "MASKED", "title_es": "Píxeles rechazados (lista oficial del cubo DR1)", "title_en": "Rejected pixels (official DR1 cube list)",
         "metric": f"{np.mean([it['bad_frac'] for it in items]):.2f} %" if items else "—",
         "desc_es": "Se rechazan " + ", ".join(DISPLAY_REJECT_NAMES) + ". SOURCE, OVERFLOW y OUTLIER se conservan.",
         "desc_en": "Rejected: " + ", ".join(DISPLAY_REJECT_NAMES) + ". SOURCE, OVERFLOW and OUTLIER are kept."},
        {"id": "epsf", "status": "OFFICIAL" if items and n_epsf == len(items) else ("PARTIAL" if n_epsf else "GAUSSIAN"), "title_es": "PSF para fotometría", "title_en": "PSF used for photometry",
         "metric": f"{n_epsf}/{len(items)} ePSF oficial" if items else "—",
         "metric_en": f"{n_epsf}/{len(items)} official ePSF" if items else "—",
         "desc_es": "ePSF oficial de la zona del detector (5× sobremuestreada). Si no está disponible se usa una gaussiana con el PSF_FWHM de la cabecera.",
         "desc_en": "Official ePSF of the detector zone (5× oversampled). If unavailable, a Gaussian with the header PSF_FWHM is used."},
        {"id": "saturation", "status": "WARN" if sat else "OK", "title_es": "Saturación del objetivo", "title_en": "Target saturation",
         "metric": f"{sat}/{len(photometry)} exp" if photometry else "—",
         "desc_es": "Exposiciones con OVERFLOW/NONLINEAR/BLOOM o núcleo sin datos en r ≤ 1.2 px: su flujo no es fiable.",
         "desc_en": "Exposures with OVERFLOW/NONLINEAR/BLOOM or a core without data within r ≤ 1.2 px: their flux is not reliable."},
        {"id": "streaks", "status": "INFO", "title_es": "Satélites y artefactos", "title_en": "Satellites and artifacts",
         "metric": f"STREAK {tot.get('STREAK', 0)} · SAT_HALO {tot.get('SATELLITE_HALO', 0)} · BLOOM {tot.get('BLOOM', 0)} · SNOWBALL {tot.get('SNOWBALL', 0)} px",
         "desc_es": "Recuento de píxeles marcados por el pipeline oficial en la grilla común (unión de cada época).",
         "desc_en": "Count of pixels flagged by the official pipeline on the common grid (union per epoch)."},
        {"id": "dichroic", "status": "INFO", "title_es": "Borde dicroico y He I", "title_en": "Dichroic edge and He I",
         "metric": f"DICHROIC {tot.get('DICHROIC', 0)} px · He I {he_hits} exp",
         "desc_es": "Los canales 50–51 del cubo DR1 están vacíos. Las mediciones cerca de 1.083 µm pueden estar contaminadas por He I atmosférico.",
         "desc_en": "DR1 cube channels 50–51 are blank. Measurements near 1.083 µm may be contaminated by atmospheric He I."},
    ]
    return {"checks": checks, "flag_totals": tot}


def _build_mpc_report(cands: List[Dict[str, Any]], items: List[Dict[str, Any]], epochs: List[Dict[str, Any]], target_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Solo genera registros MPC para candidatos dipolares SIN contrapartida estelar (Gaia u objetivo de referencia),
    con astrometría medida en cada exposición (S/N ≥ 5) y la posición geocéntrica de SPHEREx de la cabecera FITS.
    """
    base = {"lines": [], "eligible": False, "obs_code": MPC_OBS_CODE_SPHEREX,
            "disclaimer_es": "El MPC solo acepta astrometría de objetos del Sistema Solar y exige verificación y un observador registrado. Estos registros son un borrador técnico.",
            "disclaimer_en": "The MPC only accepts astrometry of Solar System objects and requires verification and a registered observer. These records are a technical draft."}
    if target_info and target_info.get("object_kind") in ("brown_dwarf", "star", "variable"):
        base["reason_es"] = "El objetivo es una estrella o enana marrón: el MPC no registra astrometría estelar."
        base["reason_en"] = "The target is a star or brown dwarf: the MPC does not record stellar astrometry."
        return base
    elig = [c for c in cands if c.get("verification") == "confirmed_motion" and not c.get("catalog_match")]
    if not elig:
        base["reason_es"] = "No hay candidatos en movimiento sin contrapartida estelar conocida."
        base["reason_en"] = "There are no moving candidates without a known stellar counterpart."
        return base
    c = elig[0]
    lines: List[str] = []
    first_ids = {e["obs_id"] for e in epochs[0]["exposures"]}
    last_ids = {e["obs_id"] for e in epochs[-1]["exposures"]}
    for it in items:
        oid = it["row"]["obs_id"]
        if oid in first_ids:
            ra_g, de_g = c["ra_old"], c["dec_old"]
        elif oid in last_ids:
            ra_g, de_g = c["ra"], c["dec"]
        else:
            continue
        ph = forced_photometry_cut(it["cut"], ra_g, de_g, fit_position=True)
        sc = spacecraft_position_mid(it["cut"]["meta"])
        if ph.get("snr") and ph["snr"] >= 5 and ph.get("ra_meas") is not None and sc is not None:
            lines.extend(format_mpc_satellite_obs(f"SPX{c['rank']:04d}", float(it["cut"]["meta"]["mjd_avg"]), ph["ra_meas"], ph["dec_meas"], sc))
    base.update({"lines": lines, "eligible": bool(lines), "candidate_rank": c["rank"]})
    if not lines:
        base["reason_es"] = "El candidato no alcanza S/N ≥ 5 en las exposiciones individuales."
        base["reason_en"] = "The candidate does not reach S/N ≥ 5 in individual exposures."
    return base


def _build_equations(cube: Dict[str, Any]) -> Dict[str, Any]:
    """Ecuaciones implementadas con su valor en vivo (ES/EN), calculado solo con datos del cubo actual."""
    ps = cube.get("photometry_summary", {})
    good = [p for p in cube.get("photometry", []) if p["quality"] in ("good", "warning")]
    best = max(good, key=lambda p: p["snr"]) if good else None
    eps = cube.get("epochs", [])
    zodi = np.mean([e["mean_zodi"] for e in eps]) if eps else 0.0
    cands = cube.get("candidates", [])
    tgt = cube.get("target") or {}
    mot = tgt.get("expected_motion")
    meas = tgt.get("measured_motion")
    if best:
        psf_es = f"F = {best['flux_ujy']:.1f} ± {best['err_ujy']:.1f} µJy (S/N {best['snr']:.1f}, λ = {best['wavelength_um']} µm)"
        psf_en = psf_es
    else:
        psf_es, psf_en = "Sin detecciones con S/N ≥ 3", "No detections with S/N ≥ 3"
    if best and best.get("ab_mag"):
        ab_es = ab_en = f"m_AB = {best['ab_mag']} ± {best['ab_mag_err']} · Ω_pix = {best.get('pix_solid_angle_sr', SOLID_ANGLE_SR):.3e} sr"
    else:
        ab_es, ab_en = f"Ω_pix nominal = {SOLID_ANGLE_SR:.3e} sr", f"Nominal Ω_pix = {SOLID_ANGLE_SR:.3e} sr"
    lvf_es = f"{ps.get('n', 0)} mediciones · {ps.get('n_detected', 0)} detecciones · {ps.get('n_saturated', 0)} saturadas"
    lvf_en = f"{ps.get('n', 0)} measurements · {ps.get('n_detected', 0)} detections · {ps.get('n_saturated', 0)} saturated"
    if mot:
        pm_es = f"Predicho entre la 1.ª y la última época: {mot['arcsec']}″ = {mot['native_px']} px nativos"
        pm_en = f"Predicted between the first and last epoch: {mot['arcsec']}″ = {mot['native_px']} native px"
        if meas:
            pm_es += (f" · Medido por SPHEREx ({meas['n_visits']} visitas): {meas['arcsec']} ± {meas['err_arcsec']}″ (AP {meas['pa_deg']}°) frente a "
                      f"{meas['predicted_arcsec']}″ (AP {meas['predicted_pa_deg']}°) en {meas['days']} d; diferencia {meas['diff_sigma']}σ")
            pm_en += (f" · Measured by SPHEREx ({meas['n_visits']} visits): {meas['arcsec']} ± {meas['err_arcsec']}″ (PA {meas['pa_deg']}°) vs "
                      f"{meas['predicted_arcsec']}″ (PA {meas['predicted_pa_deg']}°) in {meas['days']} d; difference {meas['diff_sigma']}σ")
    else:
        pm_es, pm_en = "Sin movimiento propio asociado", "No associated proper motion"
    if cands:
        dip_es = f"#1: {cands[0]['snr_diff']}σ ({cands[0]['label_es']})"
        dip_en = f"#1: {cands[0]['snr_diff']}σ ({cands[0].get('label_en', cands[0]['label_es'])})"
    else:
        sig = cube.get("stats", {}).get("sky_sigma", 0)
        dip_es, dip_en = f"σ_cielo = {sig:.4f} MJy/sr", f"σ_sky = {sig:.4f} MJy/sr"
    eqs = [
        {"id": "eq_zodi", "title_es": "1. Resta de luz zodiacal y máscara oficial", "title_en": "1. Zodiacal-light subtraction and official mask",
         "formula": "I(x,y) = IMAGE − ZODI ;  píxel rechazado si FLAGS ∧ M_oficial ≠ 0",
         "formula_en": "I(x,y) = IMAGE − ZODI ;  pixel rejected if FLAGS ∧ M_official ≠ 0",
         "live_value": f"⟨ZODI⟩ = {zodi:.3f} MJy/sr", "live_value_en": f"⟨ZODI⟩ = {zodi:.3f} MJy/sr"},
        {"id": "eq_psf", "title_es": "2. Fotometría PSF forzada (método del pipeline SPHEREx)", "title_en": "2. Forced PSF photometry (SPHEREx pipeline method)",
         "formula": "d_j = F·P_eff(x_j − x⋆) + B ;  θ = (AᵀWA)⁻¹AᵀWd ,  W = 1/VARIANCE",
         "formula_en": "d_j = F·P_eff(x_j − x⋆) + B ;  θ = (AᵀWA)⁻¹AᵀWd ,  W = 1/VARIANCE",
         "live_value": psf_es, "live_value_en": psf_en},
        {"id": "eq_abmag", "title_es": "3. Flujo y magnitud AB", "title_en": "3. Flux and AB magnitude",
         "formula": "F_µJy = F·Ω_pix·10¹² ;  σ² = σ_stat² + (0.03F)² ;  m_AB = 23.9 − 2.5·log₁₀ F_µJy",
         "formula_en": "F_µJy = F·Ω_pix·10¹² ;  σ² = σ_stat² + (0.03F)² ;  m_AB = 23.9 − 2.5·log₁₀ F_µJy",
         "live_value": ab_es, "live_value_en": ab_en},
        {"id": "eq_lvf", "title_es": "4. Longitud de onda en la posición de la fuente (WCS-WAVE)", "title_en": "4. Wavelength at the source position (WCS-WAVE)",
         "formula": "λ(x,y) = Σ w_ij(t_x,t_y)·V(i,j)  (tabla oficial, error ≤ 5 % del ancho de banda)",
         "formula_en": "λ(x,y) = Σ w_ij(t_x,t_y)·V(i,j)  (official table, error ≤ 5 % of the bandwidth)",
         "live_value": lvf_es, "live_value_en": lvf_en},
        {"id": "eq_pm", "title_es": "5. Propagación de la posición (movimiento propio)", "title_en": "5. Position propagation (proper motion)",
         "formula": "(α, δ)(t) = apply_space_motion(α₀, δ₀, μ_α*, μ_δ, ϖ, v_r; t₀ → t)",
         "formula_en": "(α, δ)(t) = apply_space_motion(α₀, δ₀, μ_α*, μ_δ, ϖ, v_r; t₀ → t)",
         "live_value": pm_es, "live_value_en": pm_en},
        {"id": "eq_dipole", "title_es": "6. Imagen de diferencia y significancia", "title_en": "6. Difference image and significance",
         "formula": "ΔI = E_n − E_1 ;  σ_MAD = 1.4826·med|ΔI − med ΔI| ;  umbral 5σ",
         "formula_en": "ΔI = E_n − E_1 ;  σ_MAD = 1.4826·med|ΔI − med ΔI| ;  5σ threshold",
         "live_value": dip_es, "live_value_en": dip_en},
    ]
    return {"equations": eqs, "dois": IRSA_DOIS}


def prewarm_reference_targets_async() -> None:
    """Precalcula en segundo plano los cubos y espectros DR1 de los objetivos de referencia."""

    def _worker() -> None:
        for tgt in CHALLENGE_TARGETS:
            if not tgt.get("astrometry"):
                continue
            try:
                build_sky_cube_and_spectrum(
                    ra=float(tgt["ra"]), dec=float(tgt["dec"]),
                    bands=list(tgt.get("recommended_bands", ["D1", "D2", "D3", "D4"])),
                    size_deg=float(tgt.get("recommended_fov", 0.10)), max_per_epoch=5, release="all", gap_days=45.0,
                    target_id=tgt["id"],
                )
            except Exception:
                pass
            try:
                ra_d, de_d = propagate_astrometry(tgt["astrometry"], 0.5 * (DR1_MJD_RANGE[0] + DR1_MJD_RANGE[1]))
                dr1_point_spectrum(ra_d, de_d, tgt.get("object_kind", "generic"))
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()


def extract_point_spectrum(ra: float, dec: float, bands: List[str], size_deg: float, px: int, py: int) -> Dict[str, Any]:
    """
    Fotometría PSF forzada por exposición en el píxel (px, py) donde hizo clic el usuario. Si el clic cae
    sobre la posición predicha de un objetivo de referencia, se usa su astrometría (con movimiento propio).
    """
    norm_b = sorted({b.upper().replace("SPHEREX-", "") for b in (bands or ["D1", "D2", "D3", "D4"])})
    memo_key = f"{ra:.4f}_{dec:.4f}_{size_deg:.3f}_{','.join(norm_b)}"
    memo = _CUBE_MEMO.get(memo_key)
    if not memo:
        try:
            build_sky_cube_and_spectrum(ra, dec, norm_b, size_deg=size_deg, max_per_epoch=5, gap_days=45.0)
            memo = _CUBE_MEMO.get(memo_key)
        except Exception:
            memo = None
    if not memo or not memo.get("rows"):
        return {"spectrum": [], "px": px, "py": py, "error": "Sin exposiciones L2b en memoria para este campo."}
    ny, nx = memo["shape"]
    wcs: WCS = memo["wcs"]
    px_c = int(np.clip(px, 0, nx - 1))
    py_c = int(np.clip(py, 0, ny - 1))
    ra_pt, dec_pt = [float(v) for v in wcs.pixel_to_world_values(px_c, py_c)]
    astrom = None
    for tr in memo.get("target_track", []):
        if np.hypot(tr["px"] - px_c, tr["py"] - py_c) <= 3.0 and memo.get("astrometry"):
            astrom = memo["astrometry"]
            break
    fra, fdec, fsize = memo["fetch_args"]
    pts: List[Dict[str, Any]] = []
    for row in memo["rows"]:
        cut = _safe_fetch(row, fra, fdec, fsize)
        if cut is None:
            continue
        mjd = float(cut["meta"].get("mjd_avg") or row["t_min"])
        r_t, d_t = propagate_astrometry(astrom, mjd) if astrom else (ra_pt, dec_pt)
        pts.append(forced_photometry_cut(cut, r_t, d_t, fit_position=True))
    pts = [p for p in pts if p.get("wavelength_um")]
    good = [p for p in pts if p["quality"] in ("good", "warning")]
    best = max(good, key=lambda p: p["snr"]) if good else None
    return {
        "px": px_c, "py": py_c, "ra": round(ra_pt, 6), "dec": round(dec_pt, 6),
        "uses_target_astrometry": bool(astrom),
        "spectrum": sorted(pts, key=lambda s: s["wavelength_um"]),
        "light_curve": build_light_curve(pts),
        "best": best,
        "flux_ujy": best["flux_ujy"] if best else None,
        "ab_mag": best["ab_mag"] if best else None,
        "fwhm_arcsec": best.get("psf_fwhm_arcsec") if best else None,
        "fit_ql": best["quality"] if best else None,
    }


def render_animated_gif_bytes(cube_data: Dict[str, Any], label: str = "SPHEREx") -> bytes:
    """GIF animado de las épocas (estiramiento asinh común a todas las épocas)."""
    ny, nx = cube_data["shape"]
    lo = cube_data["stats"]["p05"]
    hi = max(cube_data["stats"]["p995"], lo + 1e-6)
    scale = 4
    frames_pil: List[Image.Image] = []
    for ep in cube_data["epochs"]:
        arr = np.frombuffer(base64.b64decode(ep["data_b64"]), dtype=np.float32).reshape((ny, nx))
        arr_up = np.flipud(arr)
        x = np.clip((arr_up - lo) / (hi - lo), 0.0, 1.0)
        v = np.arcsinh(10.0 * x) / np.arcsinh(10.0)
        r = np.clip(v * 1.45, 0.0, 1.0) * 255
        g = np.clip((v - 0.25) * 1.35, 0.0, 1.0) * 255
        b = np.clip(0.18 + 0.82 * (v ** 0.65) * (1.0 - 0.5 * v) + (v ** 3) * 0.5, 0.0, 1.0) * 255
        rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
        frames_pil.append(Image.fromarray(rgb, mode="RGB").resize((nx * scale, ny * scale), resample=Image.NEAREST))
    buf = io.BytesIO()
    if len(frames_pil) == 1:
        frames_pil[0].save(buf, format="GIF")
    else:
        frames_pil[0].save(buf, format="GIF", save_all=True, append_images=frames_pil[1:], duration=600, loop=0)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Análisis automático y copiloto (solo con datos medidos; nunca inventa valores)
# ---------------------------------------------------------------------------
def generate_ai_preliminary_analysis(cube: Dict[str, Any], lang: str = "es") -> Dict[str, Any]:
    """Resumen automático construido exclusivamente con las mediciones del cubo."""
    en = lang == "en"
    epochs = cube.get("epochs", [])
    tgt = cube.get("target") or {}
    ps = cube.get("photometry_summary", {})
    cands = cube.get("candidates", [])
    lc = cube.get("light_curve", {}) or {}
    title = tgt.get("name") or (f"Sky patch RA {cube['ra']:.4f}°, Dec {cube['dec']:.4f}°" if en else f"Parche celeste RA {cube['ra']:.4f}°, Dec {cube['dec']:.4f}°")
    bullets: List[str] = []
    if cube.get("data_mode") == "dr1_static":
        bullets.append("🗺️ **Static DR1 data:** no multi-epoch L2b exposures were available; the image is a one-year co-add without time information." if en
                       else "🗺️ **Datos DR1 estáticos:** no hubo exposiciones L2b multi-época; la imagen es una co-adición de un año sin información temporal.")
    elif epochs:
        bullets.append((f"📡 **Coverage:** {len(epochs)} epochs from {cube.get('used_exposures', 0)} L2b exposures ({epochs[0]['date']} → {epochs[-1]['date']})."
                        if en else f"📡 **Cobertura:** {len(epochs)} épocas con {cube.get('used_exposures', 0)} exposiciones L2b ({epochs[0]['date']} → {epochs[-1]['date']})."))
    mot = tgt.get("expected_motion")
    if mot:
        bullets.append((f"🧭 **Expected motion (catalogue astrometry):** {mot['arcsec']}″ between the first and last epoch ({mot['native_px']} native pixels in {mot['days']} days)."
                        if en else f"🧭 **Movimiento esperado (astrometría de catálogo):** {mot['arcsec']}″ entre la primera y la última época ({mot['native_px']} píxeles nativos en {mot['days']} días)."))
    meas = tgt.get("measured_motion")
    if meas:
        how_en = "saturated-core centroids" if meas.get("methods") == ["saturated_core"] else "ePSF positions"
        how_es = "centroides del núcleo saturado" if meas.get("methods") == ["saturated_core"] else "posiciones ePSF"
        agree_en = "consistent with the catalogue" if meas["diff_sigma"] < 3 else "NOT consistent with the catalogue"
        agree_es = "consistente con el catálogo" if meas["diff_sigma"] < 3 else "NO consistente con el catálogo"
        bullets.append((f"📏 **Motion measured by SPHEREx ({how_en}, {meas['n_visits']} visits):** {meas['arcsec']} ± {meas['err_arcsec']}″ at PA {meas['pa_deg']}° between {meas['date_first']} and {meas['date_last']}; the catalogue predicts {meas['predicted_arcsec']}″ at PA {meas['predicted_pa_deg']}° ({agree_en}, {meas['diff_sigma']}σ)."
                        if en else f"📏 **Movimiento medido por SPHEREx ({how_es}, {meas['n_visits']} visitas):** {meas['arcsec']} ± {meas['err_arcsec']}″ con AP {meas['pa_deg']}° entre {meas['date_first']} y {meas['date_last']}; el catálogo predice {meas['predicted_arcsec']}″ con AP {meas['predicted_pa_deg']}° ({agree_es}, {meas['diff_sigma']}σ)."))
    if ps.get("n"):
        bullets.append((f"🎯 **Target photometry:** {ps['n_detected']} of {ps['n']} exposures with S/N ≥ 3" + (f" (median S/N {ps['median_snr']})" if ps.get("median_snr") else "") + (f"; {ps['n_saturated']} saturated." if ps.get("n_saturated") else ".")
                        if en else f"🎯 **Fotometría del objetivo:** {ps['n_detected']} de {ps['n']} exposiciones con S/N ≥ 3" + (f" (S/N mediana {ps['median_snr']})" if ps.get("median_snr") else "") + (f"; {ps['n_saturated']} saturadas." if ps.get("n_saturated") else ".")))
    sc = lc.get("strongest_change")
    if sc:
        bullets.append((f"📈 **Same-λ variability:** largest change at {sc['wavelength_um']} µm: {sc['max_change_sigma']}σ (max/min ratio {sc.get('max_ratio')})."
                        if en else f"📈 **Variabilidad a λ fija:** el mayor cambio está en {sc['wavelength_um']} µm: {sc['max_change_sigma']}σ (razón máx/mín {sc.get('max_ratio')})."))
    if cands:
        conf = [c for c in cands if str(c.get("verification", "")).startswith("confirmed")]
        n_rej = sum(1 for c in cands if c.get("verification") == "not_confirmed")
        if conf:
            c = conf[0]
            note = (c.get("notes_en") if en else c.get("notes_es")) or []
            bullets.append((f"🚩 **Verified candidate:** {c['label_en']}. " if en else f"🚩 **Candidato verificado:** {c['label_es']}. ") + (" ".join(note[:2])))
        if n_rej:
            bullets.append((f"🧪 {n_rej} difference-image peak(s) were NOT confirmed by per-exposure ePSF photometry (pixel-phase/λ residuals)."
                            if en else f"🧪 {n_rej} pico(s) de la imagen de diferencia NO se confirmaron con la fotometría ePSF por exposición (residuos de fase de píxel/λ)."))
    for n in cube.get("notes", [])[:2]:
        bullets.append("⚠️ " + (n["en"] if en else n["es"]))
    tip = ("💡 Open the per-channel light curve and the DR1 spectrum: compare only points at the same wavelength."
           if en else "💡 Revisa la curva de luz por canal y el espectro DR1: compara solo puntos a la misma longitud de onda.")
    return {"title": title, "bullets": bullets, "tip": tip, "candidates_count": len(cands)}


_AI_RULES_ES = (
    "REGLAS DE RIGOR (obligatorias):\n"
    "1. Usa SOLO los números de la telemetría. Si un dato no aparece (distancia, temperatura, tipo espectral, flujo), di que no está disponible: no lo estimes ni lo inventes.\n"
    "2. Distingue hielo de gas: en enanas marrones y estrellas frías las bandas de H₂O, CH₄, CO y CO₂ son de GAS atmosférico.\n"
    "3. Un candidato del detector es una hipótesis, no un descubrimiento; la significancia σ no es una probabilidad.\n"
    "4. SPHEREx mide cada exposición a una λ distinta: no confundas cambios espectrales con variabilidad.\n"
    "5. Si la fuente está saturada, su flujo no es fiable.\n"
    "6. No saludes ni repitas presentaciones; responde directo.\n"
)
_AI_RULES_EN = (
    "RIGOR RULES (mandatory):\n"
    "1. Use ONLY the numbers in the telemetry. If a value is missing (distance, temperature, spectral type, flux), say it is unavailable: do not estimate or invent it.\n"
    "2. Distinguish ice from gas: in brown dwarfs and cool stars the H₂O, CH₄, CO and CO₂ bands are atmospheric GAS.\n"
    "3. A detector candidate is a hypothesis, not a discovery; σ significance is not a probability.\n"
    "4. SPHEREx measures each exposure at a different λ: do not confuse spectral changes with variability.\n"
    "5. If the source is saturated, its flux is not reliable.\n"
    "6. Do not greet or repeat introductions; answer directly.\n"
)


# ---------------------------------------------------------------------------
# Proveedores de IA (opcional): validación de la clave, elección del modelo y errores visibles
# ---------------------------------------------------------------------------
_AI_MODEL_CACHE: Dict[str, Dict[str, Any]] = {}   # huella SHA-256 de la clave → proveedor y modelos (nunca la clave)
_AI_CACHE_TTL_S = 3600.0
_AI_KEY_PATTERN = re.compile(r"(sk-[A-Za-z0-9_\-\*\.]{3,}|AIza[0-9A-Za-z_\-]{6,})")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_PREFERRED_MODELS = ("gpt-4.1-mini", "gpt-4o-mini", "gpt-5-mini", "gpt-4.1", "gpt-4o", "gpt-5")
_AI_BUSY_UNTIL: Dict[str, float] = {}  # modelo → hasta cuándo se considera saturado (503/429/tiempo agotado)
_AI_BUSY_S = 90.0


def _ai_by_availability(ranked: List[str]) -> List[str]:
    """Primero los modelos que no fallaron por saturación en los últimos _AI_BUSY_S segundos (sin descartar ninguno)."""
    now = time.time()
    return [m for m in ranked if _AI_BUSY_UNTIL.get(m, 0.0) <= now] + [m for m in ranked if _AI_BUSY_UNTIL.get(m, 0.0) > now]


def _ai_mark_busy(model: str, err: Optional[Dict[str, Any]]) -> None:
    if err and (err.get("status") in (429, 500, 502, 503, 504) or err.get("reason") == "network"):
        _AI_BUSY_UNTIL[model] = time.time() + _AI_BUSY_S


def ai_provider_for_key(key: str) -> str:
    """Las claves de OpenAI empiezan por 'sk-' (incluidas las 'sk-proj-'); el resto se trata como clave de Google Gemini."""
    return "openai" if (key or "").strip().startswith("sk-") else "gemini"


def _key_fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _sanitize_provider_message(msg: Any) -> str:
    """Mensaje de error del proveedor sin fragmentos de la clave (OpenAI incluye sus últimos caracteres)."""
    return _AI_KEY_PATTERN.sub("[clave]", str(msg or "")).strip()[:220]


def _provider_error(provider: str, status: Optional[int], payload: Any = None, exc: Optional[BaseException] = None) -> Dict[str, Any]:
    name = "Google Gemini" if provider == "gemini" else "OpenAI"
    detail, reason = "", "error"
    if isinstance(payload, dict):
        err = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        detail = _sanitize_provider_message(err.get("message"))
        code = str(err.get("code") or err.get("status") or "")
        details = err.get("details") or []
        reasons = " ".join(str(d.get("reason", "")) for d in details if isinstance(d, dict))
        if "API_KEY_INVALID" in reasons or code == "invalid_api_key" or (status in (401,) and provider == "openai"):
            reason = "invalid_key"
        elif status == 403:
            reason = "permission"
        elif status == 404:
            reason = "model_not_found"
        elif status == 429 or "insufficient_quota" in code or "RESOURCE_EXHAUSTED" in code:
            reason = "quota"
    elif exc is not None:
        reason = "network"
        detail = ("tiempo de espera agotado" if "Timeout" in type(exc).__name__ else "sin conexión") + f" ({type(exc).__name__})"
    if status == 400 and provider == "gemini" and reason == "error" and "API key" in detail:
        reason = "invalid_key"
    es = {"invalid_key": f"{name} rechazó la clave: no es válida.",
          "permission": f"{name} rechazó el acceso (403): la clave no tiene permiso para esta API.",
          "model_not_found": f"{name} no encontró el modelo solicitado (404).",
          "quota": f"La clave es válida, pero {name} indica que no hay cuota o se superó el límite de uso (429).",
          "network": f"No se pudo conectar con {name}. Inténtalo de nuevo en unos segundos.",
          "error": f"{name} devolvió un error" + (f" ({status})" if status else "") + "."}[reason]
    en = {"invalid_key": f"{name} rejected the key: it is not valid.",
          "permission": f"{name} denied access (403): the key has no permission for this API.",
          "model_not_found": f"{name} could not find the requested model (404).",
          "quota": f"The key is valid, but {name} reports no quota or the usage limit was exceeded (429).",
          "network": f"Could not connect to {name}. Try again in a few seconds.",
          "error": f"{name} returned an error" + (f" ({status})" if status else "") + "."}[reason]
    if detail:
        es += f" Detalle: {detail}"
        en += f" Detail: {detail}"
    return {"ok": False, "provider": provider, "status": status, "reason": reason, "message_es": es, "message_en": en}


def _rank_gemini_models(names: List[str]) -> List[str]:
    """Modelos Gemini de texto ordenados: GEMINI_MODEL, alias estable 'flash-latest', Flash estables y luego preview."""
    skip = ("tts", "image", "embedding", "live", "audio", "computer-use", "robotics", "-exp", "learnlm", "aqa", "veo", "imagen",
            "transcribe", "banana", "customtools", "tuning")
    usable = [n for n in names if n.startswith("gemini") and not any(k in n for k in skip)]

    def _ver(n: str) -> float:
        m = re.match(r"gemini-(\d+(?:\.\d+)?)", n)
        return float(m.group(1)) if m else 0.0

    pref = (os.environ.get("GEMINI_MODEL") or "").strip()
    ranked: List[str] = [pref] if pref in usable else []
    for alias in ("gemini-flash-latest",):
        if alias in usable and alias not in ranked:
            ranked.append(alias)
    flash = [n for n in usable if "flash" in n and "lite" not in n and n not in ranked]
    flash.sort(key=lambda n: ("preview" in n, -_ver(n), len(n)))
    ranked += flash
    lite = sorted([n for n in usable if "flash" in n and "lite" in n and n not in ranked], key=lambda n: ("preview" in n, -_ver(n)))
    ranked += lite
    ranked += sorted([n for n in usable if n not in ranked], key=lambda n: ("preview" in n, -_ver(n)))
    return ranked


def _list_provider_models(provider: str, key: str) -> Tuple[Optional[List[str]], Optional[Dict[str, Any]]]:
    ranked, err = _list_provider_models_once(provider, key)
    if err and err.get("reason") == "network":
        time.sleep(1.0)
        ranked, err = _list_provider_models_once(provider, key)
    return ranked, err


def _list_provider_models_once(provider: str, key: str) -> Tuple[Optional[List[str]], Optional[Dict[str, Any]]]:
    try:
        if provider == "gemini":
            r = requests.get(f"{GEMINI_API_BASE}/models", params={"pageSize": 200}, headers={"x-goog-api-key": key}, timeout=20)
            if not r.ok:
                return None, _provider_error(provider, r.status_code, _safe_json(r))
            names = [m.get("name", "").split("/", 1)[-1] for m in r.json().get("models", [])
                     if "generateContent" in (m.get("supportedGenerationMethods") or [])]
            return _rank_gemini_models(names), None
        r = requests.get(f"{OPENAI_API_BASE}/models", headers={"Authorization": f"Bearer {key}"}, timeout=20)
        if not r.ok:
            return None, _provider_error(provider, r.status_code, _safe_json(r))
        ids = {m.get("id", "") for m in r.json().get("data", [])}
        pref = (os.environ.get("OPENAI_MODEL") or "").strip()
        ranked = ([pref] if pref in ids else []) + [m for m in OPENAI_PREFERRED_MODELS if m in ids and m != pref]
        return ranked or ["gpt-4o-mini"], None
    except Exception as exc:  # red caída o proveedor inaccesible
        return None, _provider_error(provider, None, exc=exc)


def _safe_json(r: Any) -> Any:
    try:
        return r.json()
    except Exception:
        return None


def _gemini_generate(key: str, model: str, sys_prompt: str, contents: List[Dict[str, Any]], max_tokens: int,
                     timeout: float = 50.0) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    # La clave va en la cabecera x-goog-api-key (nunca en la URL: evita que quede en registros o errores)
    try:
        r = requests.post(f"{GEMINI_API_BASE}/models/{model}:generateContent",
                          headers={"Content-Type": "application/json", "x-goog-api-key": key},
                          json={"systemInstruction": {"parts": [{"text": sys_prompt}]}, "contents": contents,
                                "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens}},
                          timeout=timeout)
    except Exception as exc:
        return None, _provider_error("gemini", None, exc=exc)
    if not r.ok:
        return None, _provider_error("gemini", r.status_code, _safe_json(r))
    data = _safe_json(r) or {}
    cands = data.get("candidates") or []
    if not cands:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        err = _provider_error("gemini", 200, None)
        err["message_es"] = "Google Gemini no devolvió respuesta" + (f" (bloqueo: {block})." if block else ".")
        err["message_en"] = "Google Gemini returned no answer" + (f" (blocked: {block})." if block else ".")
        return None, err
    parts = (cands[0].get("content") or {}).get("parts") or []
    ans = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not ans:
        err = _provider_error("gemini", 200, None)
        err["message_es"] = f"Google Gemini terminó sin texto (motivo: {cands[0].get('finishReason', '—')})."
        err["message_en"] = f"Google Gemini finished without text (reason: {cands[0].get('finishReason', '—')})."
        return None, err
    return ans, None


def _openai_chat(key: str, model: str, messages: List[Dict[str, Any]], max_tokens: int,
                 timeout: float = 50.0) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    body: Dict[str, Any] = {"model": model, "messages": messages, "max_completion_tokens": max_tokens}
    if not (model.startswith("gpt-5") or re.match(r"^o\d", model)):
        body["temperature"] = 0.2  # los modelos de razonamiento solo admiten la temperatura por defecto
    try:
        r = requests.post(f"{OPENAI_API_BASE}/chat/completions",
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body, timeout=timeout)
    except Exception as exc:
        return None, _provider_error("openai", None, exc=exc)
    if not r.ok:
        return None, _provider_error("openai", r.status_code, _safe_json(r))
    try:
        ans = (r.json()["choices"][0]["message"].get("content") or "").strip()
    except Exception:
        ans = ""
    if not ans:
        err = _provider_error("openai", 200, None)
        err["message_es"], err["message_en"] = "OpenAI terminó sin texto.", "OpenAI finished without text."
        return None, err
    return ans, None


def _resolve_ai_key(api_key: Optional[str]) -> Tuple[str, str]:
    """Clave de la interfaz (sesión del navegador) o, si no hay, la del servidor (.env). Devuelve (clave, origen)."""
    _load_dotenv()
    k = (api_key or "").strip()
    if k:
        return k, "browser"
    k = (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    return k, ("server" if k else "none")


def ai_server_key_status() -> Dict[str, Any]:
    """Indica si el servidor tiene una clave en .env/entorno (sin revelarla)."""
    key, origin = _resolve_ai_key(None)
    return {"server_key": bool(key), "provider": ai_provider_for_key(key) if key else None}


def validate_ai_key(api_key: Optional[str] = None, use_server_key: bool = False) -> Dict[str, Any]:
    """
    Comprueba la clave con el proveedor: lista los modelos disponibles para esa clave, elige el más adecuado y hace
    una consulta mínima (verifica también la cuota). Nunca devuelve la clave ni fragmentos de ella.
    """
    key, origin = _resolve_ai_key(None if use_server_key else api_key)
    if not key:
        return {"ok": False, "provider": None, "reason": "empty", "message_es": "No hay clave para comprobar.", "message_en": "There is no key to check."}
    provider = ai_provider_for_key(key)
    name = "Google Gemini" if provider == "gemini" else "OpenAI"
    ranked, err = _list_provider_models(provider, key)
    if err:
        return err
    if not ranked:
        return {"ok": False, "provider": provider, "reason": "no_models",
                "message_es": f"La clave es válida, pero {name} no ofrece modelos de texto para ella.",
                "message_en": f"The key is valid, but {name} offers no text models for it."}
    last_err = None
    t_end = time.time() + 60.0
    for model in _ai_by_availability(ranked)[:6]:
        remaining = t_end - time.time()
        if remaining < 5.0:
            break
        if provider == "gemini":
            ans, err = _gemini_generate(key, model, "Responde solo: OK", [{"role": "user", "parts": [{"text": "ping"}]}], 256, timeout=min(20.0, remaining))
        else:
            ans, err = _openai_chat(key, model, [{"role": "user", "content": "Reply only: OK"}], 256, timeout=min(20.0, remaining))
        # Un 200 sin texto (p. ej. modelo de razonamiento con pocos tokens) también confirma clave, modelo y cuota
        if ans is not None or (err and err.get("status") == 200):
            _AI_MODEL_CACHE[_key_fingerprint(key)] = {"provider": provider, "ranked": [model] + [m for m in ranked if m != model], "t": time.time()}
            return {"ok": True, "provider": provider, "provider_label": name, "model": model, "origin": origin,
                    "message_es": f"Conectado a {name} · modelo {model}. El copiloto usará esta IA.",
                    "message_en": f"Connected to {name} · model {model}. The copilot will use this AI."}
        last_err = err
        _ai_mark_busy(model, err)
        if err and err.get("reason") in ("invalid_key", "permission"):
            break
    if last_err and (last_err.get("status") in (429, 500, 502, 503, 504) or last_err.get("reason") in ("quota", "model_not_found", "network")):
        # La lista de modelos ya confirmó la clave: el fallo es de capacidad o cuota del proveedor, no de la clave
        _AI_MODEL_CACHE[_key_fingerprint(key)] = {"provider": provider, "ranked": ranked, "t": time.time()}
        return {"ok": True, "warning": True, "provider": provider, "provider_label": name, "model": ranked[0], "origin": origin,
                "message_es": f"Clave válida: {name} la aceptó, pero ahora mismo sus modelos están saturados o sin cuota "
                              f"({last_err.get('status') or 'tiempo de espera agotado'}). El copiloto la usará y probará otros modelos en cada pregunta.",
                "message_en": f"Valid key: {name} accepted it, but its models are overloaded or out of quota right now "
                              f"({last_err.get('status') or 'timeout'}). The copilot will use it and try other models on each question."}
    return last_err or _provider_error(provider, None)


def _ai_models_for(key: str) -> Tuple[str, List[str], Optional[Dict[str, Any]]]:
    provider = ai_provider_for_key(key)
    cached = _AI_MODEL_CACHE.get(_key_fingerprint(key))
    if cached and time.time() - cached["t"] < _AI_CACHE_TTL_S:
        return provider, cached["ranked"], None
    ranked, err = _list_provider_models(provider, key)
    if err:
        if err.get("reason") == "network":
            default = ["gemini-flash-latest", "gemini-flash-lite-latest"] if provider == "gemini" else ["gpt-4o-mini", "gpt-4.1-mini"]
            return provider, default, err
        return provider, [], err
    _AI_MODEL_CACHE[_key_fingerprint(key)] = {"provider": provider, "ranked": ranked, "t": time.time()}
    return provider, ranked, None


def answer_ai_chat(
    message: str,
    context: Dict[str, Any],
    lang: str = "es",
    api_key: Optional[str] = None,
    image_b64: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Copiloto multimodal (Gemini u OpenAI) con la telemetría medida. Sin clave usa el motor determinista local. Si el
    proveedor falla, responde el motor local y devuelve `ai_error` para que la interfaz lo muestre (nunca en silencio).
    """
    msg = (message or "").strip()
    key, origin = _resolve_ai_key(api_key)
    hist = history or []
    en = lang == "en"
    q_low = msg.lower()
    wants_concise = any(w in q_low for w in ["breve", "resum", "corto", "concis", "short", "brief", "quick", "una linea", "solo dime", "just tell"]) or (
        len(msg) < 42 and not any(w in q_low for w in ["analiz", "analyz", "profund", "deep", "explica", "explain", "detall", "detail", "espectro", "spectr"])
    )
    ai_error: Optional[Dict[str, Any]] = None
    if key:
        telemetry_summary = json.dumps(context, ensure_ascii=False, default=str)[:60000]
        depth = ("Responde en 60–160 palabras." if wants_concise else "Responde con detalle (300–700 palabras), con subtítulos y viñetas.") if not en else (
            "Answer in 60–160 words." if wants_concise else "Answer in detail (300–700 words) with headings and bullets.")
        sys_prompt = (
            ("Eres AstroAI Copilot, astrofísico especialista en el telescopio espacial SPHEREx (102 canales LVF, 0.75–5.0 µm, píxeles de 6.15″). "
             if not en else "You are AstroAI Copilot, an astrophysicist specialised in the SPHEREx space telescope (102 LVF channels, 0.75–5.0 µm, 6.15″ pixels). ")
            + (_AI_RULES_EN if en else _AI_RULES_ES) + depth
            + ("\nIdioma: " + ("inglés" if en else "español"))
            + "\n\nTELEMETRÍA MEDIDA (JSON):\n" + telemetry_summary
        )
        max_tokens = 2048 if wants_concise else 8192
        provider, ranked, ai_error = _ai_models_for(key)
        name = "Google" if provider == "gemini" else "OpenAI"
        img_data = image_b64.split(",", 1)[-1].strip() if image_b64 and "," in image_b64 else None
        t_end = time.time() + 80.0
        for model in _ai_by_availability(ranked)[:5]:
            remaining = t_end - time.time()
            if remaining < 8.0:
                break
            call_timeout = min(50.0, remaining)
            if provider == "gemini":
                contents: List[Dict[str, Any]] = []
                for h_turn in hist[-8:]:
                    t_txt = (h_turn.get("text") or "").strip()
                    if not t_txt:
                        continue
                    g_role = "model" if h_turn.get("role") in ("model", "bot", "assistant") else "user"
                    if not contents and g_role == "model":
                        continue
                    if contents and contents[-1]["role"] == g_role:
                        contents[-1]["parts"][0]["text"] += "\n" + t_txt
                    else:
                        contents.append({"role": g_role, "parts": [{"text": t_txt}]})
                user_parts: List[Dict[str, Any]] = []
                if img_data:
                    mime = "image/jpeg" if "image/jpeg" in (image_b64 or "")[:40] else "image/png"
                    user_parts.append({"inline_data": {"mime_type": mime, "data": img_data}})
                user_parts.append({"text": msg})
                if contents and contents[-1]["role"] == "user":
                    contents[-1]["parts"].extend(user_parts)
                else:
                    contents.append({"role": "user", "parts": user_parts})
                ans, err = _gemini_generate(key, model, sys_prompt, contents, max_tokens, timeout=call_timeout)
            else:
                oa_msgs: List[Dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
                for h_turn in hist[-8:]:
                    if h_turn.get("text"):
                        oa_msgs.append({"role": "assistant" if h_turn.get("role") in ("model", "bot", "assistant") else "user", "content": h_turn["text"]})
                user_content: Any = msg
                if img_data:
                    user_content = [{"type": "text", "text": msg}, {"type": "image_url", "image_url": {"url": image_b64, "detail": "low"}}]
                oa_msgs.append({"role": "user", "content": user_content})
                ans, err = _openai_chat(key, model, oa_msgs, max_tokens, timeout=call_timeout)
                if err and img_data and err.get("status") == 400:
                    oa_msgs[-1] = {"role": "user", "content": msg}  # modelo sin visión: se reintenta solo con texto
                    ans, err = _openai_chat(key, model, oa_msgs, max_tokens, timeout=call_timeout)
            if ans:
                fp = _key_fingerprint(key)
                if fp in _AI_MODEL_CACHE:
                    _AI_MODEL_CACHE[fp]["ranked"] = [model] + [m for m in _AI_MODEL_CACHE[fp]["ranked"] if m != model]
                vision = (" + visión" if not en else " + vision") if img_data else ""
                return {"reply": ans, "engine": f"{name} {model}{vision} + telemetría SPHEREx" if not en else f"{name} {model}{vision} + SPHEREx telemetry",
                        "provider": provider, "model": model, "key_origin": origin}
            ai_error = err
            _ai_mark_busy(model, err)
            if err and err.get("reason") in ("invalid_key", "permission"):
                break
    reply = _expert_astrophysics_response(msg, context, lang)
    out = {"reply": reply, "engine": "Motor local determinista (sin IA generativa)" if not en else "Local deterministic engine (no generative AI)",
           "provider": None, "model": None, "key_origin": origin}
    if ai_error:
        out["ai_error"] = {k: ai_error.get(k) for k in ("provider", "status", "reason", "message_es", "message_en")}
    return out


def _expert_astrophysics_response(msg: str, ctx: Dict[str, Any], lang: str) -> str:
    """Respuestas deterministas basadas solo en la telemetría recibida."""
    en = lang == "en"
    q = (msg or "").lower()
    name = ctx.get("target_name") or ("the current field" if en else "el campo actual")
    epochs = ctx.get("epochs", []) or []
    cands = ctx.get("candidates", []) or []
    ps = ctx.get("photometry_summary", {}) or {}
    tgt = ctx.get("target", {}) or {}
    mot = tgt.get("expected_motion") if isinstance(tgt, dict) else None
    lines: List[str] = []
    if any(w in q for w in ["muev", "movimiento", "dipolo", "desplaz", "planeta", "candidat", "move", "moving", "dipole", "shift", "planet", "candidate"]):
        if mot:
            lines.append((f"Catalogue astrometry predicts a shift of **{mot['arcsec']}″** ({mot['native_px']} native pixels) between the first and last epoch of {name}."
                          if en else f"La astrometría de catálogo predice un desplazamiento de **{mot['arcsec']}″** ({mot['native_px']} píxeles nativos) entre la primera y la última época de {name}."))
        meas_m = tgt.get("measured_motion") if isinstance(tgt, dict) else None
        if meas_m:
            lines.append((f"SPHEREx itself measures **{meas_m['arcsec']} ± {meas_m['err_arcsec']}″** (PA {meas_m['pa_deg']}°) between {meas_m['date_first']} and {meas_m['date_last']}, against {meas_m['predicted_arcsec']}″ predicted for those dates."
                          if en else f"SPHEREx mide **{meas_m['arcsec']} ± {meas_m['err_arcsec']}″** (AP {meas_m['pa_deg']}°) entre {meas_m['date_first']} y {meas_m['date_last']}, frente a {meas_m['predicted_arcsec']}″ predichos para esas fechas."))
        if cands:
            for c in cands[:4]:
                notes_l = (c.get("notes_en") if en else c.get("notes_es")) or c.get("notes") or []
                notes = " ".join(notes_l) if isinstance(notes_l, list) else str(notes_l)
                label = c.get("label") or (c.get("label_en") if en else c.get("label_es")) or c.get("verification") or ""
                pos = f" · RA {c['ra']}°, Dec {c['dec']}°" if c.get("ra") is not None and c.get("dec") is not None else ""
                shift = f" · ePSF {c['psf_shift_arcsec']}″ ± {c.get('psf_shift_err_arcsec')}″" if c.get("psf_shift_arcsec") is not None else ""
                lines.append(f"- **#{c.get('rank', '?')}** {label} · {c.get('snr_diff', '—')}σ{shift}{pos}. {notes}".rstrip())
            lines.append("A candidate is a hypothesis: confirm it in Blink/Difference mode and against Gaia." if en else "Un candidato es una hipótesis: confírmalo en modo Blink/Diferencia y contra Gaia.")
        else:
            lines.append("No ≥5σ difference-image candidates in this field." if en else "No hay candidatos ≥5σ en la imagen de diferencia de este campo.")
        if "planet" in q or "planeta" in q:
            lines.append(("Note: 'Planet X/Nine' is hypothetical and undetected. At ~500 AU its parallactic motion would be ~7″/day, so between visits 6 months apart it would leave a 0.1° field; it must be searched for within a single visit."
                          if en else "Nota: el 'Planeta X/Nueve' es hipotético y no se ha detectado. A ~500 UA su movimiento paraláctico sería de ~7″/día, así que entre visitas separadas 6 meses saldría de un campo de 0.1°: hay que buscarlo dentro de una misma visita."))
        return "\n".join(lines)
    if any(w in q for w in ["espectr", "banda", "lvf", "onda", "molecul", "agua", "metano", "hielo", "spectr", "band", "wavelength", "water", "methane", "ice"]):
        lines.append((f"{ps.get('n', 0)} measurements of {name}: {ps.get('n_detected', 0)} with S/N ≥ 3 and {ps.get('n_saturated', 0)} saturated. Each SPHEREx exposure samples one wavelength set by the LVF position."
                      if en else f"{ps.get('n', 0)} mediciones de {name}: {ps.get('n_detected', 0)} con S/N ≥ 3 y {ps.get('n_saturated', 0)} saturadas. Cada exposición de SPHEREx mide una sola λ, fijada por la posición en el filtro LVF."))
        lines.append(("In brown dwarfs and cool stars, H₂O/CH₄/CO/CO₂ bands are atmospheric gas, not ice. Ice bands appear in background stars behind molecular clouds and in protostars."
                      if en else "En enanas marrones y estrellas frías, las bandas de H₂O/CH₄/CO/CO₂ son de gas atmosférico, no de hielo. El hielo aparece en estrellas de fondo tras nubes moleculares y en protoestrellas."))
        return "\n".join(lines)
    if any(w in q for w in ["curva", "luz", "variab", "brillo", "pulsa", "eclips", "light", "curve", "bright"]):
        sc = (ctx.get("light_curve") or {}).get("strongest_change")
        if sc:
            lam_sc = round(float(sc["wavelength_um"]), 3) if sc.get("wavelength_um") is not None else "—"
            verdict_en = "significant (≥5σ)" if (sc.get("max_change_sigma") or 0) >= 5 else "not significant (<5σ)"
            verdict_es = "significativo (≥5σ)" if (sc.get("max_change_sigma") or 0) >= 5 else "no significativo (<5σ)"
            lines.append((f"Largest same-wavelength change: {sc['max_change_sigma']}σ at {lam_sc} µm (ratio {sc.get('max_ratio')}): {verdict_en}."
                          if en else f"Mayor cambio a la misma λ: {sc['max_change_sigma']}σ en {lam_sc} µm (razón {sc.get('max_ratio')}): {verdict_es}."))
        else:
            lines.append("There are not enough same-wavelength measurements in different epochs to assess variability." if en else "No hay suficientes mediciones a la misma λ en épocas distintas para evaluar la variabilidad.")
        if ps.get("n_saturated"):
            lines.append("Saturated exposures were excluded: their fluxes are not reliable." if en else "Se excluyeron las exposiciones saturadas: sus flujos no son fiables.")
        return "\n".join(lines)
    ep_lines = [f"- E{e.get('index', i) + 1} {e.get('date', '—')}: {e.get('n_exp', 0)} exp, λ {e.get('lam_min_um')}–{e.get('lam_max_um')} µm, ZODI {e.get('mean_zodi', '—')} MJy/sr"
                for i, e in enumerate(epochs)]
    head = f"### {name}\n" + (f"Data: {ctx.get('data_source', '—')}\n" if en else f"Datos: {ctx.get('data_source', '—')}\n")
    return head + ("\n".join(ep_lines) if ep_lines else ("No epochs." if en else "Sin épocas."))
