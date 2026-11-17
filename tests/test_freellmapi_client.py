import json
import time

import httpx
import pytest
from pydantic import BaseModel

from app import freellmapi_client as fl, gemini_client, ia_sessao, openrouter_client as router


class Mini(BaseModel):
    x: int


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(fl, "FREELLMAPI_API_KEY", "dummy-not-a-real-secret")
    monkeypatch.setattr(fl, "FREELLMAPI_BASE_URL", "http://127.0.0.1:3003/v1")
    monkeypatch.setattr(fl, "FREELLMAPI_MODEL", "auto")
    monkeypatch.setattr(fl, "FREELLMAPI_TIMEOUT", 5.0)
    monkeypatch.setattr(fl, "FREELLMAPI_CONNECT_TIMEOUT", 0.5)
    monkeypatch.setattr(fl, "_cooldown_until", 0.0)
    monkeypatch.setattr(fl, "ensure_relay", lambda: False)
    monkeypatch.setattr(router, "OPENROUTER_API_KEY", "")
    ia_sessao.reset()
    yield
    ia_sessao.reset()


def transport(monkeypatch, handler):
    real = httpx.Client

    class FakeClient(real):
        def __init__(self, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(**kwargs)

    monkeypatch.setattr(fl.httpx, "Client", FakeClient)


def chat_response(text="PING_OK", model="groq/qwen/qwen3.8-27b"):
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        },
    )


def test_success_text_and_session(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body["model"])
        assert body["stream"] is False
        assert request.headers["authorization"].startswith("Bearer ")
        return chat_response()

    transport(monkeypatch, handler)
    assert fl.gerar_texto_livre("Responda exatamente: PING_OK", 128) == "PING_OK"
    assert calls == ["auto"]
    assert ia_sessao.modelo_texto == "freellmapi/groq/qwen/qwen3.8-27b"


def test_json_app_path_uses_3003_first(monkeypatch):
    def handler(request):
        return chat_response('{"x": 7}', model="google/gemini-3.6-flash")

    transport(monkeypatch, handler)
    monkeypatch.setattr(gemini_client, "_com_failover", lambda *a: pytest.fail("unexpected Gemini"))
    monkeypatch.setattr(router, "gerar_json_livre", lambda *a, **k: pytest.fail("unexpected OpenRouter"))
    assert gemini_client.gerar_json("test", Mini).x == 7
    assert ia_sessao.modelo_texto == "freellmapi/google/gemini-3.6-flash"


@pytest.mark.parametrize("status", [408, 500, 502, 503])
def test_error_falls_to_next_provider(monkeypatch, status):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(status, json={"error": {"message": "boom"}})

    transport(monkeypatch, handler)
    monkeypatch.setattr(router, "OPENROUTER_API_KEY", "dummy-or")
    monkeypatch.setattr(router, "gerar_texto_livre", lambda *a, **k: "OR_OK")
    monkeypatch.setattr(gemini_client, "_com_failover", lambda *a: pytest.fail("should stop at OpenRouter"))
    assert gemini_client.ping() == "OR_OK"
    assert seen and seen[0].endswith("/chat/completions")


def test_timeout_falls_to_fallback(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("slow")

    transport(monkeypatch, handler)
    monkeypatch.setattr(router, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(gemini_client, "_com_failover", lambda fn: "GEMINI_OK")
    assert gemini_client.ping() == "GEMINI_OK"


def test_429_cooldown_skips_3003_then_fallback(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429, headers={"retry-after": "120"}, json={"error": {"code": "429"}})

    transport(monkeypatch, handler)
    monkeypatch.setattr(router, "OPENROUTER_API_KEY", "dummy-or")
    monkeypatch.setattr(router, "gerar_texto_livre", lambda *a, **k: "OR_AFTER_429")
    assert gemini_client.ping() == "OR_AFTER_429"
    assert calls["n"] == 1
    # Second request must honor cooldown and not hit 3003 again.
    assert gemini_client.ping() == "OR_AFTER_429"
    assert calls["n"] == 1
    assert time.monotonic() < fl._cooldown_until


def test_forced_top_failure_is_gateway_problem_client_still_returns_text(monkeypatch):
    """The 3003 gateway is expected to skip a failing top model (incl. Groq peers)."""
    def handler(request):
        return chat_response("PING_OK", model="google/gemini-3.7-flash")

    transport(monkeypatch, handler)
    assert fl.gerar_texto_livre("Responda exatamente: PING_OK") == "PING_OK"
    assert ia_sessao.modelo_texto == "freellmapi/google/gemini-3.7-flash"


def test_missing_key_skips_without_network(monkeypatch):
    monkeypatch.setattr(fl, "FREELLMAPI_API_KEY", "")
    transport(monkeypatch, lambda request: pytest.fail("network must not be called"))
    monkeypatch.setattr(router, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(gemini_client, "_com_failover", lambda fn: "GEMINI_OK")
    assert gemini_client.ping() == "GEMINI_OK"
