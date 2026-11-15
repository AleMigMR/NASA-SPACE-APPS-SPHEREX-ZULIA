"""
Servidor web y API científica de SPHEREx SkyChrono (NASA Space Apps Challenge 2026).
Delegación Zuliana de Astronomía.

Ejecución:
    python app.py          (Windows: .venv\\Scripts\\python.exe app.py)
Abre en el navegador:
    http://localhost:8050
"""
from __future__ import annotations

import asyncio
import math
import os
import traceback
from typing import Any, Dict, Optional

from aiohttp import web

import spherex_engine as se

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

DOC_FILES = {
    "es": ("📘 Documentación Integral SPHEREx SkyChrono (ES)", "SPHEREx_SkyChrono_Documentation_ES.md"),
    "en": ("📘 SPHEREx SkyChrono Complete Documentation (EN)", "SPHEREx_SkyChrono_Documentation_EN.md"),
}


def _parse_bands(request: web.Request, default: str = "D5,D6") -> list:
    bands_str = request.query.get("bands") or request.query.get("band") or default
    bands = [(f"D{b.strip()}" if b.strip().isdigit() else b.strip().upper()) for b in bands_str.split(",") if b.strip()]
    return [b for b in bands if b in se.DETECTOR_INFO] or ["D6"]


def _parse_user_astrometry(request: web.Request) -> Optional[Dict[str, Any]]:
    """Astrometría opcional de un objeto resuelto por nombre (posición + movimiento propio en mas/año)."""
    q = request.query
    if not (q.get("pmra") or q.get("pmdec")):
        return None
    try:
        pmra = float(q.get("pmra", "0"))
        pmdec = float(q.get("pmdec", "0"))
        if abs(pmra) < 1e-6 and abs(pmdec) < 1e-6:
            return None
        astrom = {
            "ra_deg": float(q["ast_ra"]) if q.get("ast_ra") else float(q.get("ra", "0")),
            "dec_deg": float(q["ast_dec"]) if q.get("ast_dec") else float(q.get("dec", "0")),
            "epoch_jyear": float(q.get("ast_epoch", str(se.DISPLAY_EPOCH_JYEAR))),
            "pmra_masyr": pmra,
            "pmdec_masyr": pmdec,
            "parallax_mas": float(q["plx"]) if q.get("plx") else None,
            "rv_kms": None,
            "ref": q.get("ast_ref", "SIMBAD vía Sesame"),
        }
        return astrom
    except (TypeError, ValueError):
        return None


def _error(status: int, msg: str, **extra: Any) -> web.Response:
    return web.json_response({"error": msg, **extra}, status=status)


async def handle_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def handle_targets(request: web.Request) -> web.Response:
    return web.json_response({
        "targets": se.get_all_targets(),
        "landmarks": se.ALLSKY_LANDMARKS,
        "detectors": se.DETECTOR_INFO,
        "flags": se.FLAG_DEFINITIONS,
        "irsa_dois": se.IRSA_DOIS,
        "display_epoch": se.DISPLAY_EPOCH_JYEAR,
    })


async def handle_add_target(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        new_tgt = await asyncio.to_thread(se.add_custom_target, body)
        return web.json_response({"added": new_tgt, "target": new_tgt, "targets": se.get_all_targets()})
    except Exception as e:
        return _error(400, f"No se pudo guardar el objetivo: {e}")


async def handle_delete_target(request: web.Request) -> web.Response:
    tid = request.query.get("id", "").strip()
    if not tid:
        return _error(400, "ID requerido")
    ok = await asyncio.to_thread(se.delete_custom_target, tid)
    return web.json_response({"deleted": ok, "targets": se.get_all_targets()})


async def handle_point_spectrum(request: web.Request) -> web.Response:
    try:
        ra = float(request.query.get("ra", "0"))
        dec = float(request.query.get("dec", "0"))
        fov = float(request.query.get("fov", "0.10"))
        bands = _parse_bands(request)
        px = int(request.query.get("px", request.query.get("gx", "0")))
        py = int(request.query.get("py", request.query.get("gy", "0")))
        res = await asyncio.to_thread(se.extract_point_spectrum, ra, dec, bands, fov, px, py)
        return web.json_response(res)
    except Exception as e:
        traceback.print_exc()
        return web.json_response({"error": f"No se pudo extraer el espectro: {type(e).__name__}", "spectrum": []}, status=200)


async def handle_dr1_spectrum(request: web.Request) -> web.Response:
    """Espectro de 102 canales del cubo All-Sky DR1 en una posición (o en la posición propagada de un objetivo)."""
    try:
        target_id = request.query.get("target_id", "").strip() or None
        kind = request.query.get("kind", "generic")
        ra_q = float(request.query.get("ra", "nan"))
        dec_q = float(request.query.get("dec", "nan"))
        astrom = se.get_target_astrometry(target_id) or _parse_user_astrometry(request)
        ra, dec = ra_q, dec_q
        if astrom:
            mid = 0.5 * (se.DR1_MJD_RANGE[0] + se.DR1_MJD_RANGE[1])
            ra_t, dec_t = se.propagate_astrometry(astrom, mid)
            # Si se pidió una posición explícita lejos del objetivo, manda la posición pedida
            far = (ra_q == ra_q) and (dec_q == dec_q) and abs(dec_t - dec_q) + abs(((ra_t - ra_q + 180) % 360 - 180) * max(abs(math.cos(math.radians(dec_q))), 1e-3)) > 0.2
            if far:
                astrom = None
            else:
                ra, dec = ra_t, dec_t
                if target_id and target_id in se._TARGETS_BY_ID:
                    kind = se._TARGETS_BY_ID[target_id].get("object_kind", kind)
        if not (ra == ra and dec == dec):
            return _error(400, "Faltan ra/dec o un objetivo válido")
        res = await asyncio.to_thread(se.dr1_point_spectrum, ra, dec, kind)
        res["used_target_astrometry"] = bool(astrom)
        return web.json_response(res)
    except Exception as e:
        traceback.print_exc()
        return _error(502, f"No se pudo leer el cubo DR1: {type(e).__name__}")


async def handle_resolve(request: web.Request) -> web.Response:
    q = request.query.get("q", "").strip()
    dec = request.query.get("dec", "").strip()
    epoch = float(request.query.get("epoch", str(se.DISPLAY_EPOCH_JYEAR)))
    if not q:
        return _error(400, "Debe ingresar coordenadas (RA/Dec) o el nombre de un objeto.")
    try:
        res = await asyncio.to_thread(se.parse_coordinates, q, dec or None, epoch)
        return web.json_response(res)
    except Exception as e:
        return _error(400, f"No se pudo resolver '{q}': {e}")


async def handle_cube(request: web.Request) -> web.Response:
    try:
        ra = float(request.query.get("ra", "0"))
        dec = float(request.query.get("dec", "0"))
        fov = max(0.03, min(float(request.query.get("fov", "0.10")), 2.50))
        bands = _parse_bands(request)
        max_per_epoch = max(2, min(int(request.query.get("max_per_epoch", "5")), 30))
        gap_days = float(request.query.get("gap_days", "45"))
        release = request.query.get("release", "all")
        target_id = request.query.get("target_id", "").strip() or None
        if target_id and target_id not in se._TARGETS_BY_ID:
            target_id = None
        user_astrom = None if target_id else _parse_user_astrometry(request)
        res = await asyncio.to_thread(
            se.build_sky_cube_and_spectrum, ra, dec, bands, fov, max_per_epoch, release, gap_days,
            False, target_id, user_astrom,
        )
        if "error" in res:
            return web.json_response(res, status=404)
        return web.json_response(res)
    except Exception as e:
        traceback.print_exc()
        return _error(500, f"Error construyendo el cubo: {type(e).__name__}")


async def handle_catalogs(request: web.Request) -> web.Response:
    try:
        ra = float(request.query.get("ra", "0"))
        dec = float(request.query.get("dec", "0"))
        fov = float(request.query.get("fov", "0.10"))
        epoch = float(request.query.get("epoch", str(se.DISPLAY_EPOCH_JYEAR)))
        _, shape, pix_arcsec = se.make_common_wcs(ra, dec, fov, oversample=2.0)
        ny, nx = shape
        wcs_info = {"crval": [ra, dec], "crpix": [nx / 2.0 + 0.5, ny / 2.0 + 0.5], "cdelt": [-pix_arcsec / 3600.0, pix_arcsec / 3600.0]}
        res = await asyncio.to_thread(se.query_external_catalogs, ra, dec, fov, wcs_info, epoch)
        return web.json_response(res)
    except Exception as e:
        return web.json_response({"error": f"Catálogos no disponibles: {type(e).__name__}", "gaia": [], "allwise": []}, status=200)


async def handle_gif(request: web.Request) -> web.Response:
    try:
        ra = float(request.query.get("ra", "0"))
        dec = float(request.query.get("dec", "0"))
        fov = float(request.query.get("fov", "0.10"))
        bands = _parse_bands(request)
        max_per_epoch = int(request.query.get("max_per_epoch", "5"))
        gap_days = float(request.query.get("gap_days", "45"))
        target_id = request.query.get("target_id", "").strip() or None
        if target_id and target_id not in se._TARGETS_BY_ID:
            target_id = None
        cube = await asyncio.to_thread(
            se.build_sky_cube_and_spectrum, ra, dec, bands, fov, max_per_epoch, "all", gap_days, False, target_id,
            None if target_id else _parse_user_astrometry(request),
        )
        if "error" in cube:
            return web.json_response(cube, status=404)
        gif_bytes = await asyncio.to_thread(se.render_animated_gif_bytes, cube)
        fname = f"spherex_blink_{ra:.3f}_{dec:.3f}_{'-'.join(bands)}.gif"
        return web.Response(body=gif_bytes, content_type="image/gif", headers={"Content-Disposition": f'attachment; filename="{fname}"'})
    except Exception as e:
        traceback.print_exc()
        return _error(500, f"No se pudo generar el GIF: {type(e).__name__}")


async def handle_ai_chat(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        res = await asyncio.to_thread(
            se.answer_ai_chat,
            body.get("message", ""),
            body.get("context", {}),
            body.get("lang", "es"),
            body.get("api_key", ""),
            body.get("image_b64", None),
            body.get("history", []),
        )
        return web.json_response(res)
    except Exception as e:
        # Nunca se devuelve el texto de la excepción: podría contener datos de la petición
        traceback.print_exc()
        return web.json_response({"error": type(e).__name__, "reply": "Error interno del copiloto."}, status=500)


async def handle_docs(request: web.Request) -> web.Response:
    raw_id = (request.query.get("lang") or request.query.get("id") or "es").strip().lower()
    doc_id = "en" if raw_id == "en" or raw_id.endswith("_en") else "es"
    title, fname = DOC_FILES[doc_id]
    fpath = os.path.join(DOCS_DIR, fname)
    content = ""
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
    return web.json_response({
        "id": doc_id,
        "lang": doc_id,
        "title": title,
        "filename": f"docs/{fname}",
        "content": content,
        "available": [{"id": k, "title": v[0], "filename": f"docs/{v[1]}"} for k, v in DOC_FILES.items()],
    })


async def handle_spherex_allsky_map(request: web.Request) -> web.Response:
    """Mapa equirectangular 360°×180° (1440×720) del cubo All-Sky oficial SPHEREx DR1 (solo visualización)."""
    ch_spec = request.query.get("channel", "rgb_dr1").strip()
    try:
        png_bytes = await asyncio.to_thread(se.get_official_spherex_allsky_equirect_png, ch_spec)
        return web.Response(body=png_bytes, content_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        return _error(502, f"No se pudo leer el mapa DR1: {type(e).__name__}")


async def handle_spherex_hips_tile(request: web.Request) -> web.Response:
    """Proxy HiPS oficial para que Aladin Lite v3 navegue cualquiera de los 102 canales del cubo DR1."""
    try:
        ch_str = request.match_info.get("channel", "62")
        ch_num = int("".join(c for c in ch_str if c.isdigit()) or "62")
        tail = request.match_info.get("tail", "properties")
        body_bytes, ctype = await asyncio.to_thread(se.fetch_official_hips_tile_bytes, ch_num, tail)
        return web.Response(body=body_bytes, content_type=ctype.split(";")[0], headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        })
    except Exception as e:
        return web.Response(text=f"HiPS no disponible: {type(e).__name__}", status=404)


async def _on_startup(app: web.Application) -> None:
    if os.environ.get("SPHEREX_PREWARM", "1") != "0":
        se.prewarm_reference_targets_async()


def create_app() -> web.Application:
    app = web.Application()
    app.on_startup.append(_on_startup)
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/targets", handle_targets)
    app.router.add_post("/api/targets", handle_add_target)
    app.router.add_delete("/api/targets", handle_delete_target)
    app.router.add_get("/api/resolve", handle_resolve)
    app.router.add_get("/api/cube", handle_cube)
    app.router.add_get("/api/point_spectrum", handle_point_spectrum)
    app.router.add_get("/api/dr1_spectrum", handle_dr1_spectrum)
    app.router.add_get("/api/catalogs", handle_catalogs)
    app.router.add_get("/api/gif", handle_gif)
    app.router.add_post("/api/ai/chat", handle_ai_chat)
    app.router.add_get("/api/docs", handle_docs)
    app.router.add_get("/api/spherex-allsky-map", handle_spherex_allsky_map)
    app.router.add_get("/api/hips/spherex/{channel}/{tail:.*}", handle_spherex_hips_tile)
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)
    app.router.add_static("/static", STATIC_DIR)
    app.router.add_static("/docs", DOCS_DIR)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8050"))
    print(f"=== SPHEREx SkyChrono Web Server iniciando en http://localhost:{port} ===")
    web.run_app(create_app(), host="0.0.0.0", port=port)
