import asyncio
import base64
import io
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app import cloudflare_image as cf, image_gen, ia_sessao


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(cf, "CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setattr(cf, "CLOUDFLARE_API_TOKEN", "dummy-not-a-real-key")
    monkeypatch.setattr(cf, "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell")
    monkeypatch.setattr(cf, "_cooldown_until", 0.0)
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
    monkeypatch.setattr(cf.httpx, "AsyncClient", factory)


def test_schnell_prompt_only_json(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.content == b'{"prompt":"test"}'
        return httpx.Response(200, json={"success": True, "result": {
            "image": base64.b64encode(image_bytes()).decode()}})
    mock_client(monkeypatch, handler)
    data = cf.gerar_png_cloudflare("test")
    assert data.startswith(b"\x89PNG") and len(calls) == 1
    assert cf._TIMEOUT_SECONDS == 60.0


def test_binary_response(monkeypatch):
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=image_bytes("JPEG"),
                headers={"content-type": "image/jpeg"}))
    assert cf.gerar_png_cloudflare("test").startswith(b"\x89PNG")


def test_flux2_uses_multipart(monkeypatch):
    monkeypatch.setattr(cf, "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-2-dev")
    def handler(request):
        assert request.headers["content-type"].startswith("multipart/form-data;")
        assert b'name="prompt"' in request.content and b'name="width"' in request.content
        return httpx.Response(200, content=image_bytes())
    mock_client(monkeypatch, handler)
    assert cf.gerar_png_cloudflare("test").startswith(b"\x89PNG")


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_error_next_provider_once(monkeypatch, tmp_path, status):
    calls = []
    def handler(request):
        calls.append("cloudflare")
        return httpx.Response(status, headers={"retry-after": "120"})
    mock_client(monkeypatch, handler)
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["cloudflare", "gemini"])
    def next_provider(prompt, destination):
        calls.append("gemini")
        return image_gen.CenaResult(image_gen._salvar(destination, image_bytes()), "gemini", "mock")
    monkeypatch.setattr(image_gen, "_try_gemini", next_provider)
    result = image_gen.gerar_cena_com_provider("test", "title", "support", tmp_path / "out.png")
    assert result.provider == "gemini" and calls == ["cloudflare", "gemini"]
    assert f"HTTP {status}" in result.detail
    if status == 429:
        with pytest.raises(cf.CloudflareImageError, match="cooldown"):
            cf.gerar_png_cloudflare("test")
        assert calls == ["cloudflare", "gemini"]


@pytest.mark.parametrize("body", [b"", b"<html>error</html>", b'{"success":false}',
    b'{"result":{"image":"%%%"}}', b'{"result":{}}', b'{bad-json'])
def test_malformed_returns_failure(monkeypatch, tmp_path, body):
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=body,
                headers={"content-type": "application/json" if body.startswith(b"{") else "image/png"}))
    result = image_gen._try_cloudflare("test", tmp_path / "invalid.png")
    assert result.path is None and result.provider == "cloudflare"
    assert not (tmp_path / "invalid.png").exists()
    assert "dummy-not-a-real-key" not in result.detail


def test_network_failure(monkeypatch, tmp_path):
    def handler(request):
        raise httpx.ConnectError("network", request=request)
    mock_client(monkeypatch, handler)
    result = image_gen._try_cloudflare("test", tmp_path / "out.png")
    assert result.path is None and "ConnectError" in result.detail


def test_wall_clock_timeout(monkeypatch, tmp_path):
    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, content=image_bytes())
    mock_client(monkeypatch, handler)
    monkeypatch.setattr(cf, "_TIMEOUT_SECONDS", 0.01)
    result = image_gen._try_cloudflare("test", tmp_path / "out.png")
    assert result.path is None and "timeout" in result.detail


def test_success_through_app(monkeypatch, tmp_path):
    mock_client(monkeypatch, lambda request: httpx.Response(200, content=image_bytes()))
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["cloudflare", "gemini"])
    monkeypatch.setattr(image_gen, "_try_gemini", lambda *args: pytest.fail("unexpected paid fallback"))
    result = image_gen.gerar_cena_com_provider("test", "title", "support", tmp_path / "out.png")
    assert result.provider == "cloudflare" and result.path.is_file()
    assert ia_sessao.provedor_imagem == "cloudflare"


def test_cota_diaria_4006_cooldown_ate_meia_noite_utc(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, json={"success": False, "errors": [
            {"code": 4006, "message": "you have used up your daily free allocation of 10,000 neurons"}]})
    mock_client(monkeypatch, handler)
    with pytest.raises(cf.CloudflareImageError, match="cota diária"):
        cf.gerar_png_cloudflare("test")
    assert cf._cooldown_until - __import__("time").monotonic() >= 59
    with pytest.raises(cf.CloudflareImageError, match="cooldown"):
        cf.gerar_png_cloudflare("test")
    assert len(calls) == 1
