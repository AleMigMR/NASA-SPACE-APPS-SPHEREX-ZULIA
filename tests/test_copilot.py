"""
Pruebas del copiloto AstroAI sin red: proveedores simulados (Gemini / OpenAI). Ejecutar con:
    python -m pytest tests/        (o)        python tests/test_copilot.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SPHEREX_PREWARM", "0")
import spherex_engine as se  # noqa: E402

FAKE_GEMINI_KEY = "AIza-FAKE-TEST-KEY-not-real"
FAKE_OPENAI_KEY = "sk-test-FAKE-KEY-not-real"


class _Resp:
    def __init__(self, status: int, payload: dict):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload

    def json(self):
        return self._payload


class _FakeProvider:
    """Sustituye requests.get/post del motor y registra las llamadas."""

    def __init__(self, get_map, post_fn):
        self.get_map, self.post_fn, self.calls = get_map, post_fn, []

    def __enter__(self):
        self._g, self._p, self._env = se.requests.get, se.requests.post, dict(os.environ)
        for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GEMINI_MODEL", "OPENAI_MODEL"):
            os.environ.pop(k, None)
        self._dotenv = se._load_dotenv
        se._load_dotenv = lambda: None
        se._AI_MODEL_CACHE.clear()
        se._AI_BUSY_UNTIL.clear()

        def _get(url, *a, **k):
            self.calls.append(("GET", url, k.get("headers", {}), None))
            for frag, resp in self.get_map.items():
                if frag in url:
                    return resp
            return _Resp(404, {"error": {"message": "not found"}})

        def _post(url, *a, **k):
            self.calls.append(("POST", url, k.get("headers", {}), k.get("json")))
            return self.post_fn(url, k.get("json") or {})

        se.requests.get, se.requests.post = _get, _post
        return self

    def __exit__(self, *exc):
        se.requests.get, se.requests.post = self._g, self._p
        se._load_dotenv = self._dotenv
        os.environ.clear()
        os.environ.update(self._env)
        se._AI_MODEL_CACHE.clear()
        se._AI_BUSY_UNTIL.clear()


GEMINI_MODELS = _Resp(200, {"models": [
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
    {"name": "models/gemini-3-flash-preview", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash-preview-tts", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
]})


def _gemini_ok(url, body):
    return _Resp(200, {"candidates": [{"content": {"parts": [{"text": "Respuesta de prueba de Gemini."}]}, "finishReason": "STOP"}]})


def test_provider_detection_and_key_sanitising():
    assert se.ai_provider_for_key(FAKE_OPENAI_KEY) == "openai"
    assert se.ai_provider_for_key(FAKE_GEMINI_KEY) == "gemini"
    msg = se._sanitize_provider_message("Incorrect API key provided: sk-proj-**************0000. Key AIzaSyABCDEFGH123 invalid")
    assert "sk-" not in msg and "AIza" not in msg and "[clave]" in msg


def test_gemini_model_ranking_skips_non_text_models():
    ranked = se._rank_gemini_models(["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-flash-latest",
                                     "gemini-2.5-flash-preview-tts", "gemini-embedding-001", "gemini-2.0-flash-lite"])
    assert ranked[0] == "gemini-flash-latest" and ranked[1] == "gemini-2.5-flash"
    assert "gemini-2.5-flash-preview-tts" not in ranked and "gemini-embedding-001" not in ranked


def test_validate_gemini_key_ok_uses_header_not_url():
    with _FakeProvider({"/models": GEMINI_MODELS}, _gemini_ok) as fp:
        res = se.validate_ai_key(FAKE_GEMINI_KEY)
    assert res["ok"] and res["provider"] == "gemini" and res["model"] == "gemini-2.5-flash"
    for _, url, headers, _ in fp.calls:
        assert FAKE_GEMINI_KEY not in url and headers.get("x-goog-api-key") == FAKE_GEMINI_KEY
    assert FAKE_GEMINI_KEY not in str(res)


def test_validate_invalid_gemini_key_reports_reason():
    bad = _Resp(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT",
                                "details": [{"reason": "API_KEY_INVALID"}]}})
    with _FakeProvider({"/models": bad}, _gemini_ok):
        res = se.validate_ai_key(FAKE_GEMINI_KEY)
    assert not res["ok"] and res["reason"] == "invalid_key" and "no es válida" in res["message_es"]


def test_chat_with_gemini_returns_model_answer_and_sends_image():
    with _FakeProvider({"/models": GEMINI_MODELS}, _gemini_ok) as fp:
        res = se.answer_ai_chat("¿Qué se mueve aquí?", {"target_name": "Prueba"}, "es", FAKE_GEMINI_KEY, "data:image/jpeg;base64,AAAA", [])
    assert res["reply"] == "Respuesta de prueba de Gemini." and res["provider"] == "gemini" and "ai_error" not in res
    body = [c[3] for c in fp.calls if c[0] == "POST"][-1]
    parts = body["contents"][-1]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/jpeg" and parts[-1]["text"] == "¿Qué se mueve aquí?"


def test_chat_quota_error_is_reported_not_hidden():
    quota = lambda url, body: _Resp(429, {"error": {"code": 429, "message": "Resource has been exhausted", "status": "RESOURCE_EXHAUSTED"}})
    with _FakeProvider({"/models": GEMINI_MODELS}, quota):
        res = se.answer_ai_chat("Hola", {"target_name": "Prueba", "epochs": []}, "es", FAKE_GEMINI_KEY, None, [])
    assert res["provider"] is None and res["ai_error"]["reason"] == "quota"
    assert "429" in res["ai_error"]["message_es"] and res["reply"]


def test_missing_model_falls_back_to_next_one():
    def _post(url, body):
        if "gemini-2.5-flash:" in url:
            return _Resp(404, {"error": {"code": 404, "message": "models/gemini-2.5-flash is not found", "status": "NOT_FOUND"}})
        return _gemini_ok(url, body)
    with _FakeProvider({"/models": GEMINI_MODELS}, _post):
        res = se.answer_ai_chat("Hola", {"target_name": "Prueba"}, "es", FAKE_GEMINI_KEY, None, [])
    assert res["model"] == "gemini-3-flash-preview" and res["reply"] == "Respuesta de prueba de Gemini."


def test_openai_chat_and_reasoning_models_without_temperature():
    models = _Resp(200, {"data": [{"id": "gpt-5-mini"}, {"id": "text-embedding-3-small"}]})
    ok = lambda url, body: _Resp(200, {"choices": [{"message": {"content": "Respuesta de prueba de OpenAI."}}]})
    with _FakeProvider({"/models": models}, ok) as fp:
        res = se.answer_ai_chat("Hola", {"target_name": "Prueba"}, "es", FAKE_OPENAI_KEY, "data:image/jpeg;base64,AAAA", [])
    assert res["reply"] == "Respuesta de prueba de OpenAI." and res["model"] == "gpt-5-mini"
    body = [c[3] for c in fp.calls if c[0] == "POST"][-1]
    assert "temperature" not in body and body["messages"][-1]["content"][1]["type"] == "image_url"
    assert all(c[2].get("Authorization") == f"Bearer {FAKE_OPENAI_KEY}" for c in fp.calls)


def test_local_engine_handles_frontend_context():
    """El motor local acepta el contexto que envía la interfaz (sin label_es/ra/dec ni índice de época)."""
    ctx = {"target_name": "Prueba", "data_source": "SPHEREx L2b", "epochs": [{"date": "2025-05-05", "n_exp": 3, "mean_zodi": 0.2}],
           "candidates": [{"rank": 1, "label": "Movimiento confirmado (6.6″ ± 0.2″)", "verification": "confirmed_motion", "snr_diff": 40.0,
                           "psf_shift_arcsec": 6.6, "psf_shift_err_arcsec": 0.2, "notes": ["Coincide con el objetivo."]}],
           "target": {"expected_motion": {"arcsec": 6.5, "native_px": 1.06, "days": 500}}, "photometry_summary": {"n": 4}}
    with _FakeProvider({}, _gemini_ok):
        for q in ("¿Qué se mueve aquí?", "Hola", "¿Hay variabilidad real?", "Interpreta el espectro"):
            res = se.answer_ai_chat(q, ctx, "es", "", None, [])
            assert res["reply"] and res["provider"] is None and "ai_error" not in res


def test_overloaded_models_keep_valid_key_with_warning():
    busy = lambda url, body: _Resp(503, {"error": {"code": 503, "message": "This model is currently experiencing high demand.", "status": "UNAVAILABLE"}})
    with _FakeProvider({"/models": GEMINI_MODELS}, busy):
        res = se.validate_ai_key(FAKE_GEMINI_KEY)
    assert res["ok"] and res["warning"] and "503" in res["message_es"]


def test_validation_skips_busy_models_and_remembers_working_one():
    def _post(url, body):
        if "gemini-2.5-flash:" in url:
            return _Resp(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
        return _gemini_ok(url, body)
    with _FakeProvider({"/models": GEMINI_MODELS}, _post) as fp:
        res = se.validate_ai_key(FAKE_GEMINI_KEY)
        assert res["ok"] and not res.get("warning") and res["model"] == "gemini-3-flash-preview"
        chat = se.answer_ai_chat("Hola", {"target_name": "Prueba"}, "es", FAKE_GEMINI_KEY, None, [])
    assert chat["model"] == "gemini-3-flash-preview"
    assert "gemini-2.5-flash:" not in [c[1] for c in fp.calls if c[0] == "POST"][-1]


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            n += 1
            print("ok", name)
    print(f"{n} pruebas superadas")
