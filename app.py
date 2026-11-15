"""
Servidor Web Público y API Científica para el reto SPHEREx (NASA Space Apps Challenge).
Delegación Zuliana de Astronomía.

Ejecución:
    .\.venv\Scripts\python.exe app.py
Abre en el navegador:
    http://localhost:8050
"""
from __future__ import annotations

import asyncio
import os
import traceback
from aiohttp import web

import spherex_engine as se

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

DOC_FILES = {
    "es": ("📘 Documentación Integral SPHEREx SkyChrono (ES)", "SPHEREx_SkyChrono_Documentation_ES.md"),
    "en": ("📘 SPHEREx SkyChrono Complete Documentation (EN)", "SPHEREx_SkyChrono_Documentation_EN.md"),
}


async def handle_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def handle_targets(request: web.Request) -> web.Response:
    return web.json_response({
        "targets": se.get_all_targets(),
        "landmarks": se.ALLSKY_LANDMARKS,
        "detectors": se.DETECTOR_INFO,
        "flags": se.FLAG_DEFINITIONS,
        "irsa_dois": se.IRSA_DOIS,
    })


async def handle_add_target(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        new_tgt = await asyncio.to_thread(se.add_custom_target, body)
        return web.json_response({"added": new_tgt, "target": new_tgt, "targets": se.get_all_targets()})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def handle_delete_target(request: web.Request) -> web.Response:
    tid = request.query.get("id", "").strip()
    if not tid:
        return web.json_response({"error": "ID requerido"}, status=400)
    ok = await asyncio.to_thread(se.delete_custom_target, tid)
    return web.json_response({"deleted": ok, "targets": se.get_all_targets()})


async def handle_point_spectrum(request: web.Request) -> web.Response:
    try:
        cube_hash = request.query.get("cube_hash", "").strip()
        if cube_hash and cube_hash in se._CUBE_RESP_CACHE:
            c_cached = se._CUBE_RESP_CACHE[cube_hash]
            ra = float(c_cached.get("ra", 133.79513))
            dec = float(c_cached.get("dec", -7.24515))
            fov = float(c_cached.get("fov_deg", 0.10))
            bands = list(c_cached.get("requested_bands", ["D5", "D6"]))
        else:
            ra = float(request.query.get("ra", "133.79513"))
            dec = float(request.query.get("dec", "-7.24515"))
            fov = float(request.query.get("fov", "0.10"))
            bands_str = request.query.get("bands", "D5,D6")
            bands = [b.strip().upper() for b in bands_str.split(",") if b.strip()]
        px = int(request.query.get("px", request.query.get("gx", "39")))
        py = int(request.query.get("py", request.query.get("gy", "39")))
        res = await asyncio.to_thread(se.extract_point_spectrum, ra, dec, bands, fov, px, py)
        return web.json_response(res)
    except Exception as e:
        return web.json_response({"error": str(e), "spectrum": []}, status=200)


async def handle_resolve(request: web.Request) -> web.Response:
    q = request.query.get("q", "").strip()
    dec = request.query.get("dec", "").strip()
    epoch = float(request.query.get("epoch", "2025.5"))
    if not q:
        return web.json_response({"error": "Debe ingresar coordenadas (RA/Dec) o el nombre de un objeto."}, status=400)
    try:
        res = await asyncio.to_thread(se.parse_coordinates, q, dec or None, epoch)
        return web.json_response(res)
    except Exception as e:
        return web.json_response({"error": f"No se pudo resolver '{q}': {e}"}, status=400)


async def handle_cube(request: web.Request) -> web.Response:
    try:
        ra = float(request.query.get("ra", "133.79513"))
        dec = float(request.query.get("dec", "-7.24515"))
        fov = float(request.query.get("fov", "0.10"))
        fov = max(0.03, min(fov, 2.50))
        bands_str = request.query.get("bands") or request.query.get("band") or "D5,D6"
        bands = [
            (f"D{b.strip()}" if b.strip().isdigit() else b.strip().upper())
            for b in bands_str.split(",")
            if b.strip()
        ]
        if not bands:
            bands = ["D5", "D6"]
        max_per_epoch = int(request.query.get("max_per_epoch", "5"))
        max_per_epoch = max(2, min(max_per_epoch, 30))
        gap_days = float(request.query.get("gap_days", "45"))
        release = request.query.get("release", "all")

        res = await asyncio.to_thread(
            se.build_sky_cube_and_spectrum,
            ra,
            dec,
            bands,
            fov,
            max_per_epoch,
            release,
            gap_days,
        )
        if "error" in res:
            return web.json_response(res, status=404)
        return web.json_response(res)
    except Exception as e:
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)


async def handle_catalogs(request: web.Request) -> web.Response:
    try:
        ra = float(request.query.get("ra", "133.79513"))
        dec = float(request.query.get("dec", "-7.24515"))
        fov = float(request.query.get("fov", "0.10"))
        _, shape, pix_arcsec = se.make_common_wcs(ra, dec, fov, oversample=2.0)
        ny, nx = shape
        wcs_info = {
            "crval": [ra, dec],
            "crpix": [nx / 2.0 + 0.5, ny / 2.0 + 0.5],
            "cdelt": [-pix_arcsec / 3600.0, pix_arcsec / 3600.0],
        }
        res = await asyncio.to_thread(se.query_external_catalogs, ra, dec, fov, wcs_info)
        return web.json_response(res)
    except Exception as e:
        return web.json_response({"error": str(e), "gaia": [], "allwise": []}, status=200)


async def handle_gif(request: web.Request) -> web.Response:
    try:
        ra = float(request.query.get("ra", "133.79513"))
        dec = float(request.query.get("dec", "-7.24515"))
        fov = float(request.query.get("fov", "0.10"))
        bands_str = request.query.get("bands") or request.query.get("band") or "D5,D6"
        bands = [
            (f"D{b.strip()}" if b.strip().isdigit() else b.strip().upper())
            for b in bands_str.split(",")
            if b.strip()
        ]
        max_per_epoch = int(request.query.get("max_per_epoch", "5"))
        gap_days = float(request.query.get("gap_days", "45"))

        cube = await asyncio.to_thread(
            se.build_sky_cube_and_spectrum,
            ra,
            dec,
            bands,
            fov,
            max_per_epoch,
            "all",
            gap_days,
        )
        if "error" in cube:
            return web.json_response(cube, status=404)
        gif_bytes = await asyncio.to_thread(se.render_animated_gif_bytes, cube)
        fname = f"spherex_blink_{ra:.3f}_{dec:.3f}_{'-'.join(bands)}.gif"
        return web.Response(
            body=gif_bytes,
            content_type="image/gif",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_ai_chat(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        message = body.get("message", "")
        context = body.get("context", {})
        lang = body.get("lang", "es")
        api_key = body.get("api_key", "")
        image_b64 = body.get("image_b64", None)
        history = body.get("history", [])
        res = await asyncio.to_thread(
            se.answer_ai_chat, message, context, lang, api_key, image_b64, history
        )
        return web.json_response(res)
    except Exception as e:
        return web.json_response({"error": str(e), "reply": f"Error: {e}"}, status=500)


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
    """Devuelve el mapa equirectangular 360°×180° (1440×720) construido del Cubo All-Sky Oficial SPHEREx DR1 de IRSA."""
    ch_spec = request.query.get("channel", "rgb_dr1").strip()
    try:
        png_bytes = await asyncio.to_thread(se.get_official_spherex_allsky_equirect_png, ch_spec)
        return web.Response(
            body=png_bytes,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_spherex_hips_tile(request: web.Request) -> web.Response:
    """Proxy IVOA HiPS oficial para que Aladin Lite v3 navegue cualquiera de los 102 canales del Cubo All-Sky SPHEREx DR1."""
    try:
        ch_str = request.match_info.get("channel", "62")
        ch_num = int("".join(c for c in ch_str if c.isdigit()) or "62")
        tail = request.match_info.get("tail", "properties")
        body_bytes, ctype = await asyncio.to_thread(se.fetch_official_hips_tile_bytes, ch_num, tail)
        return web.Response(
            body=body_bytes,
            content_type=ctype,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=86400",
            },
        )
    except Exception as e:
        return web.Response(text=str(e), status=404)


async def _on_startup(app: web.Application) -> None:
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
