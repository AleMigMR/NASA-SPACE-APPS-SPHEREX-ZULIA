"""
Prueba de concepto: pipeline SPHEREx -> GIF "blink" de un parche de cielo.

Uso:
    .venv\\Scripts\\python.exe poc\\spherex_poc.py --ra 133.79513 --dec -7.24515 --size 0.1 --band D6

Pasos:
 1. Consulta TAP (IRSA) a spherex.obscore -> lista de imagenes que contienen (ra, dec).
 2. Para cada imagen pide un recorte (cutout) al servidor IBE de IRSA:
        <url_fits>?center=<ra>,<dec>&size=<deg>
    (asi no se descargan los ~70 MB de cada imagen completa).
 3. Lee IMAGE / FLAGS / ZODI del FITS multi-extension, resta zodiacal, enmascara flags.
 4. Agrupa por "visita" (epoca) y apila (mediana) -> mejor S/N.
 5. Reproyecta todas las epocas a una grilla comun y genera un GIF animado.
"""
import argparse
import io
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests
from astropy.io import fits
from astropy.wcs import WCS
from astropy.time import Time

TAP = "https://irsa.ipac.caltech.edu/TAP/sync"
IBE_DATA = "https://irsa.ipac.caltech.edu/ibe/data/"


def query_images(ra, dec, band=None, collection=None):
    where = f"CONTAINS(POINT('ICRS',{ra},{dec}), s_region)=1"
    if band:
        where += f" AND energy_bandpassname='SPHEREx-{band}'"
    if collection:
        where += f" AND obs_collection='{collection}'"
    q = (
        "SELECT obs_id, obs_collection, energy_bandpassname, t_min, t_exptime, "
        "em_min, em_max, access_url "
        f"FROM spherex.obscore WHERE {where} ORDER BY t_min"
    )
    r = requests.get(TAP, params={"LANG": "ADQL", "FORMAT": "csv", "QUERY": q}, timeout=120)
    r.raise_for_status()
    lines = r.text.strip().splitlines()
    hdr = lines[0].split(",")
    rows = [dict(zip(hdr, ln.split(","))) for ln in lines[1:]]
    return rows


def datalink_to_fits_path(access_url):
    """Convierte la URL datalink en la ruta IBE del FITS (sin parsear VOTable completo)."""
    # ID=ivo://irsa.ipac/spherex_qr2?2025W19_1B_0116_1/D6
    r = requests.get(access_url, timeout=60)
    r.raise_for_status()
    txt = r.text
    key = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
    i = txt.find(key)
    if i < 0:
        return None
    j = txt.find("<", i)
    return txt[i:j]


def fetch_cutout(fits_url, ra, dec, size_deg):
    url = f"{fits_url}?center={ra},{dec}&size={size_deg}"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return fits.open(io.BytesIO(r.content))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ra", type=float, required=True)
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--size", type=float, default=0.1, help="lado del recorte en grados")
    ap.add_argument("--band", default="D6", help="D1..D6 (detector)")
    ap.add_argument("--max", type=int, default=12, help="max. imagenes a bajar (prueba)")
    ap.add_argument("--out", default="poc/out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rows = query_images(a.ra, a.dec, a.band)
    print(f"{len(rows)} imagenes SPHEREx-{a.band} cubren el punto")
    if not rows:
        sys.exit(0)
    for r_ in rows[:3]:
        print("  ", r_["obs_id"], Time(float(r_["t_min"]), format="mjd").iso)

    # Muestreo uniforme en el tiempo para la prueba
    idx = np.linspace(0, len(rows) - 1, min(a.max, len(rows))).astype(int)
    sel = [rows[i] for i in idx]

    def work(row):
        fits_url = datalink_to_fits_path(row["access_url"])
        hdul = fetch_cutout(fits_url, a.ra, a.dec, a.size)
        return row, hdul

    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(work, sel))

    row0, h0 = results[0]
    print("\nExtensiones del FITS recortado:")
    h0.info()

    frames, times = [], []
    for row, hd in results:
        img = hd["IMAGE"].data.astype(float)
        flags = hd["FLAGS"].data
        zodi = hd["ZODI"].data if "ZODI" in hd else 0
        clean = img - zodi
        clean[flags != 0] = np.nan  # mascara simple; luego refinar por bits
        frames.append((clean, WCS(hd["IMAGE"].header)))
        times.append(float(row["t_min"]))
        hd.writeto(os.path.join(a.out, f"{row['obs_id']}_{a.band}.fits"), overwrite=True)

    # GIF rapido (sin reproyeccion todavia: solo para ver que el pipeline funciona)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation, PillowWriter

        fig, ax = plt.subplots(figsize=(4, 4))
        def draw(k):
            ax.clear()
            d, w = frames[k]
            v = d[np.isfinite(d)]
            lo, hi = np.percentile(v, [1, 99.5]) if v.size else (0, 1)
            ax.imshow(d, origin="lower", cmap="gray", vmin=lo, vmax=hi)
            ax.set_title(Time(times[k], format="mjd").iso[:10])
            ax.axis("off")
        anim = FuncAnimation(fig, draw, frames=len(frames))
        gif = os.path.join(a.out, f"blink_{a.band}.gif")
        anim.save(gif, writer=PillowWriter(fps=2))
        print("GIF:", gif)
    except Exception as e:
        print("No se pudo generar GIF:", e)


if __name__ == "__main__":
    main()
