import asyncio
import base64
import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app import aihorde_image as horde, image_gen, ia_sessao

REQUEST_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
STATUS_URL = f"https://aihorde.net/api/v2/generate/status/{REQUEST_ID}"
CHECK_URL = f"https://aihorde.net/api/v2/generate/check/{REQUEST_ID}"
ASYNC_URL = "https://aihorde.net/api/v2/generate/async"
IMAGE_URL = "https://aihorde.net/fake-r2/scene.png"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(horde, "AIHORDE_API_KEY", "dummy-not-a-real-key")
    monkeypatch.setattr(horde, "AIHORDE_CLIENT_AGENT", "agente-criativos:1.0:anonymous")
    monkeypatch.setattr(horde, "_cooldown_until", 0.0)
    monkeypatch.setattr(horde, "_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(image_gen, "_avisar_img", lambda msg: None)
    ia_sessao.reset()
    yield
    ia_sessao.reset()


def image_bytes(fmt="PNG"):
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(out, fmt)
    return out.getvalue()


def mock_client(monkeypatch, handler):
    real = httpx.AsyncClient

    def factory(**kwargs):
        assert kwargs["verify"] is not False
        assert kwargs["follow_redirects"] is False
        return real(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(horde.httpx, "AsyncClient", factory)


def test_success_payload_and_app(monkeypatch, tmp_path):
    calls = []
    png = image_bytes()

    def handler(request):
        calls.append(f"{request.method} {request.url.path}")
        api_call = request.url.path.startswith("/api/v2/generate/")
        if api_call:
            assert request.headers.get("Client-Agent") == "agente-criativos:1.0:anonymous"
        if request.url.path.endswith("/generate/async"):
            assert request.headers.get("apikey") == "dummy-not-a-real-key"
            import json
            payload = json.loads(request.content)
            assert payload["nsfw"] is False
            assert payload["censor_nsfw"] is True
            assert payload["r2"] is True
            assert payload["params"]["width"] == 512
            assert payload["params"]["height"] == 640
            assert payload["params"]["steps"] == 16
            assert payload["params"]["n"] == 1
            return httpx.Response(202, json={"id": REQUEST_ID, "kudos": 1.5})
        if str(request.url) == CHECK_URL:
            return httpx.Response(200, json={"done": True, "finished": 1, "waiting": 0, "faulted": False, "is_possible": True})
        if str(request.url) == STATUS_URL and request.method == "GET":
            return httpx.Response(200, json={"done": True, "generations": [{"img": IMAGE_URL, "censored": False}]})
        if str(request.url) == IMAGE_URL:
            assert "apikey" not in request.headers
            return httpx.Response(200, content=png, headers={"content-type": "image/png"})
        return httpx.Response(404)

    mock_client(monkeypatch, handler)
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["aihorde", "gemini"])
    monkeypatch.setattr(image_gen, "_try_gemini", lambda *args: pytest.fail("unexpected paid fallback"))
    result = image_gen.gerar_cena_com_provider("test", "title", "support", tmp_path / "out.png")
    assert result.provider == "aihorde" and result.path.is_file()
    assert result.path.read_bytes().startswith(b"\x89PNG")
    assert horde._TIMEOUT_SECONDS == 60.0
    assert ia_sessao.provedor_imagem == "aihorde"
    assert "POST /api/v2/generate/async" in calls
    assert "GET /api/v2/generate/check/" + REQUEST_ID in calls
    assert "GET /api/v2/generate/status/" + REQUEST_ID in calls
    assert "DELETE /api/v2/generate/status/" + REQUEST_ID not in calls


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_error_next_provider_once(monkeypatch, tmp_path, status):
    calls = []

    def handler(request):
        calls.append("aihorde")
        return httpx.Response(status, headers={"retry-after": "120"})

    mock_client(monkeypatch, handler)
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["aihorde", "gemini"])

    def next_provider(prompt, destination):
        calls.append("gemini")
        return image_gen.CenaResult(image_gen._salvar(destination, image_bytes()), "gemini", "mock")

    monkeypatch.setattr(image_gen, "_try_gemini", next_provider)
    result = image_gen.gerar_cena_com_provider("test", "title", "support", tmp_path / "out.png")
    assert result.provider == "gemini" and calls == ["aihorde", "gemini"]
    assert f"HTTP {status}" in result.detail
    assert "dummy-not-a-real-key" not in result.detail
    if status == 429:
        with pytest.raises(horde.AiHordeImageError, match="cooldown"):
            horde.gerar_png_aihorde("test")
        assert calls == ["aihorde", "gemini"]


def test_wall_clock_timeout_cancels_and_next(monkeypatch, tmp_path):
    calls = []

    async def handler(request):
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/generate/async"):
            return httpx.Response(202, json={"id": REQUEST_ID, "kudos": 1})
        if request.url.path.endswith("/check/" + REQUEST_ID):
            await asyncio.sleep(1)
            return httpx.Response(200, json={"done": False, "waiting": 1, "is_possible": True})
        if request.method == "DELETE" and request.url.path.endswith("/status/" + REQUEST_ID):
            return httpx.Response(200, json={"generations": []})
        return httpx.Response(404)

    mock_client(monkeypatch, handler)
    monkeypatch.setattr(horde, "_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["aihorde", "gemini"])

    def next_provider(prompt, destination):
        calls.append("NEXT")
        return image_gen.CenaResult(image_gen._salvar(destination, image_bytes()), "gemini", "mock")

    monkeypatch.setattr(image_gen, "_try_gemini", next_provider)
    result = image_gen.gerar_cena_com_provider("test", "title", "support", tmp_path / "out.png")
    assert result.provider == "gemini"
    assert "timeout" in result.detail
    assert "POST /api/v2/generate/async" in calls
    assert "DELETE /api/v2/generate/status/" + REQUEST_ID in calls
    assert calls.count("NEXT") == 1
    assert "dummy-not-a-real-key" not in result.detail


def test_network_failure(monkeypatch, tmp_path):
    def handler(request):
        raise httpx.ConnectError("network", request=request)

    mock_client(monkeypatch, handler)
    result = image_gen._try_aihorde("test", tmp_path / "out.png")
    assert result.path is None and "ConnectError" in result.detail
    assert "dummy-not-a-real-key" not in result.detail


@pytest.mark.parametrize(
    "body",
    [
        {"id": "not-a-uuid"},
        "x",
    ],
)
def test_malformed_submit(monkeypatch, tmp_path, body):
    mock_client(monkeypatch, lambda request: httpx.Response(202, json=body))
    result = image_gen._try_aihorde("test", tmp_path / "invalid.png")
    assert result.path is None and result.provider == "aihorde"
    assert not (tmp_path / "invalid.png").exists()
    assert "dummy-not-a-real-key" not in result.detail


def test_faulted_moves_on(monkeypatch, tmp_path):
    def handler(request):
        if request.url.path.endswith("/generate/async"):
            return httpx.Response(202, json={"id": REQUEST_ID})
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"done": False, "faulted": True, "is_possible": True})

    mock_client(monkeypatch, handler)
    result = image_gen._try_aihorde("test", tmp_path / "out.png")
    assert result.path is None and "faulted" in result.detail


def test_censored_moves_on(monkeypatch, tmp_path):
    def handler(request):
        if request.url.path.endswith("/generate/async"):
            return httpx.Response(202, json={"id": REQUEST_ID})
        if "/check/" in request.url.path:
            return httpx.Response(200, json={"done": True, "faulted": False, "is_possible": True})
        if request.method == "GET" and "/status/" in request.url.path:
            return httpx.Response(
                200,
                json={"done": True, "generations": [{"img": IMAGE_URL, "censored": True}]},
            )
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    mock_client(monkeypatch, handler)
    result = image_gen._try_aihorde("test", tmp_path / "out.png")
    assert result.path is None and "censored" in result.detail
    assert not (tmp_path / "out.png").exists()


def test_missing_key(monkeypatch, tmp_path):
    monkeypatch.setattr(horde, "AIHORDE_API_KEY", "")
    result = image_gen._try_aihorde("test", tmp_path / "out.png")
    assert result.path is None and "credentials" in result.detail
