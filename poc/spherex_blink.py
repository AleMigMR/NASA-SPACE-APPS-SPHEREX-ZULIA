"""
PoC v2: SPHEREx "blink" por epocas, con mascara por bits, reproyeccion y apilado.
Usa TAP directo (spherex.artifact JOIN spherex.plane) + lectura parcial desde AWS S3.

Uso:
    .venv\\Scripts\\python.exe poc\\spherex_blink.py --name WISE0855 --ra 133.79513 --dec -7.24515 --bands D5 D6 --size 0.15

Salida (poc/out/<name>/):
    epoch_XX.fits          mosaico apilado por epoca (grilla comun, norte arriba)
    blink.gif              animacion de epocas
    diff.png               epoca_ultima - epoca_primera (lo que se mueve queda +/-)
    frames.csv             metadatos de cada exposicion usada
"""
import argparse
import csv
import io
import os
import re
import warnings
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS, FITSFixedWarning
from reproject import reproject_interp

warnings.filterwarnings("ignore", category=FITSFixedWarning)

TAP = "https://irsa.ipac.caltech.edu/TAP/sync"
S3_BASE = "https://nasa-irsa-spherex.s3.us-east-1.amazonaws.com/"
IBE_BASE = "https://irsa.ipac.caltech.edu/"
PIX_ARCSEC = 6.15

# Bits que invalidan un pixel (de la cabecera FLAGS: MP_*). NO incluimos
# SOURCE (21) ni FULLSAMPLE (12): marcan fuentes reales / info, no defectos.
BAD_BITS = [0, 1, 2, 4, 6, 7, 9, 10, 11, 15, 17, 19]
BAD_MASK = sum(1 << b for b in BAD_BITS)


def tap(q):
    r = requests.get(TAP, params={"LANG": "ADQL", "FORMAT": "csv", "QUERY": q}, timeout=120)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def query_images(ra, dec, bands):
    bl = ",".join(f"'SPHEREx-{b}'" for b in bands)
    q = (
        "SELECT a.uri, p.obsid, p.datarelease, p.energy_bandpassname, "
        "p.time_bounds_lower AS t_min, p.time_exposure AS t_exptime "
        "FROM spherex.artifact a JOIN spherex.plane p ON a.planeid = p.planeid "
        f"WHERE 1 = CONTAINS(POINT('ICRS',{ra},{dec}), p.poly) "
        f"AND p.energy_bandpassname IN ({bl}) ORDER BY p.time_bounds_lower ASC"
    )
    rows = tap(q)
    for row in rows:
        m = re.search(r"level2_([^_]+_[^_]+_[^_]+_\d+)", row["uri"])
        row["obs_id"] = m.group(1) if m else row["obsid"]
    return rows


def fetch_s3(uri, ra, dec, size):
    """Lectura parcial (HTTP Range) del FITS en AWS: solo baja las filas necesarias
    de IMAGE/FLAGS/ZODI. ~3-4 s vs ~17 s del cutout IBE (que incluye la PSF de 5 MB)."""
    s3_key = uri.replace("ibe/data/spherex/", "")
    s3_url = S3_BASE + s3_key
    with fits.open(s3_url, use_fsspec=True, fsspec_kwargs={"block_size": 256 * 1024}) as h:
        w = WCS(h["IMAGE"].header)
        ny, nx = h["IMAGE"].shape
        x, y = w.world_to_pixel_values(ra, dec)
        r = int(np.ceil(size / 2 * 3600 / PIX_ARCSEC)) + 2
        x0, x1 = max(int(x) - r, 0), min(int(x) + r, nx)
        y0, y1 = max(int(y) - r, 0), min(int(y) + r, ny)
        img = h["IMAGE"].section[y0:y1, x0:x1].astype(np.float32)
        zod = h["ZODI"].section[y0:y1, x0:x1].astype(np.float32)
        flg = h["FLAGS"].section[y0:y1, x0:x1]
    return img - zod, flg, w[y0:y1, x0:x1]


def fetch_ibe(uri, ra, dec, size):
    url = f"{IBE_BASE}{uri}?center={ra},{dec}&size={size}"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    h = fits.open(io.BytesIO(r.content))
    img = h["IMAGE"].data.astype(np.float32) - h["ZODI"].data.astype(np.float32)
    return img, h["FLAGS"].data, WCS(h["IMAGE"].header)


def fetch(row, ra, dec, size):
    uri = row["uri"]
    try:
        img, flags, w = fetch_s3(uri, ra, dec, size)
    except Exception:
        img, flags, w = fetch_ibe(uri, ra, dec, size)
    img[(flags & BAD_MASK) != 0] = np.nan
    return row, img, w


def group_epochs(times, gap_days=25):
    """Agrupa MJDs en 'epocas' (SPHEREx vuelve a cada punto cada ~6 meses)."""
    order = np.argsort(times)
    groups, cur = [], [order[0]]
    for i in order[1:]:
        if times[i] - times[cur[-1]] > gap_days:
            groups.append(cur)
            cur = []
        cur.append(i)
    groups.append(cur)
    return groups


def target_wcs(ra, dec, size_deg, pix_arcsec=PIX_ARCSEC / 2):
    n = int(round(size_deg * 3600 / pix_arcsec))
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-pix_arcsec / 3600, pix_arcsec / 3600]
    return w, (n, n)


def stretch(d, lo=5, hi=99.5):
    v = d[np.isfinite(d)]
    if v.size == 0:
        return np.zeros_like(d)
    a, b = np.percentile(v, [lo, hi])
    x = np.clip((d - a) / (b - a + 1e-12), 0, 1)
    return np.arcsinh(10 * x) / np.arcsinh(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--ra", type=float, required=True)
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--size", type=float, default=0.12)
    ap.add_argument("--bands", nargs="+", default=["D5", "D6"])
    ap.add_argument("--max-per-epoch", type=int, default=16)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    out = os.path.join("poc", "out", a.name)
    os.makedirs(out, exist_ok=True)

    rows = query_images(a.ra, a.dec, a.bands)
    print(f"[{a.name}] {len(rows)} exposiciones en {a.bands}")
    times_all = np.array([float(r["t_min"]) for r in rows])
    groups_raw = group_epochs(times_all)

    # Seleccionar hasta max_per_epoch exposiciones por epoca para rapidez
    selected_rows = []
    for g in groups_raw:
        if len(g) > a.max_per_epoch:
            idx = np.linspace(0, len(g) - 1, a.max_per_epoch).astype(int)
            g = [g[i] for i in idx]
        for i in g:
            selected_rows.append(rows[i])

    with ThreadPoolExecutor(a.workers) as ex:
        res = [r for r in ex.map(lambda r: _safe(fetch, r, a.ra, a.dec, a.size), selected_rows) if r]
    print(f"  descargadas {len(res)}/{len(selected_rows)}")

    tw, shape = target_wcs(a.ra, a.dec, a.size)
    times = np.array([float(r[0]["t_min"]) for r in res])
    groups = group_epochs(times)
    print(f"  {len(groups)} epocas:", [Time(times[g].mean(), format="mjd").iso[:10] for g in groups])

    epochs = []
    with open(os.path.join(out, "frames.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["epoch", "obs_id", "band", "mjd", "date"])
        for k, g in enumerate(groups):
            stack = []
            for i in g:
                row, img, w = res[i]
                rp, _ = reproject_interp((img, w), tw, shape_out=shape)
                rp = rp - np.nanmedian(rp)
                stack.append(rp)
                wr.writerow([k, row["obs_id"], row["energy_bandpassname"], row["t_min"],
                             Time(float(row["t_min"]), format="mjd").iso[:19]])
            with np.errstate(all="ignore"):
                ep = np.nanmedian(np.array(stack), axis=0)
            mjd = times[g].mean()
            hdr = tw.to_header()
            hdr["MJD-AVG"] = mjd
            hdr["NEXP"] = len(g)
            fits.writeto(os.path.join(out, f"epoch_{k:02d}.fits"), ep.astype(np.float32), hdr, overwrite=True)
            epochs.append((mjd, ep, len(g)))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    allv = np.concatenate([e[1][np.isfinite(e[1])] for e in epochs])
    lo, hi = np.percentile(allv, [5, 99.6])

    fig, ax = plt.subplots(figsize=(5, 5.4))
    def draw(k):
        ax.clear()
        mjd, ep, n = epochs[k]
        x = np.clip((ep - lo) / (hi - lo), 0, 1)
        ax.imshow(np.arcsinh(10 * x) / np.arcsinh(10), origin="lower", cmap="inferno")
        c = shape[0] / 2
        ax.add_patch(plt.Circle((c, c), 6, fill=False, color="cyan", lw=1.0))
        ax.set_title(f"{a.name}  {'+'.join(a.bands)}\n{Time(mjd, format='mjd').iso[:10]}  ({n} exp)")
        ax.axis("off")
    anim = FuncAnimation(fig, draw, frames=len(epochs))
    anim.save(os.path.join(out, "blink.gif"), writer=PillowWriter(fps=1.5))
    plt.close(fig)

    if len(epochs) >= 2:
        d = epochs[-1][1] - epochs[0][1]
        s = np.nanpercentile(np.abs(d), 99.5)
        fig, axs = plt.subplots(1, 3, figsize=(13, 4.6))
        for axx, (t, im, cm, vmin, vmax) in zip(axs, [
            (Time(epochs[0][0], format="mjd").iso[:10], stretch(epochs[0][1]), "inferno", 0, 1),
            (Time(epochs[-1][0], format="mjd").iso[:10], stretch(epochs[-1][1]), "inferno", 0, 1),
            ("Diferencia (ultima - primera)", d, "RdBu_r", -s, s)]):
            axx.imshow(im, origin="lower", cmap=cm, vmin=vmin, vmax=vmax)
            axx.set_title(t)
            axx.axis("off")
        fig.suptitle(f"{a.name}  RA={a.ra:.4f} Dec={a.dec:.4f}  {'+'.join(a.bands)}")
        fig.tight_layout()
        fig.savefig(os.path.join(out, "diff.png"), dpi=110)
    print("  listo ->", out)


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        print("   fallo:", args[0].get("obs_id"), e)
        return None


if __name__ == "__main__":
    main()
