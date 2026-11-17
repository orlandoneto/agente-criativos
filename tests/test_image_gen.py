"""Chaveador de imagem: ordem, sticky, cada _try_* sem rede, PNG limpo e atribuição."""

from __future__ import annotations

import io
import json
import random
import ssl
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from app import ia_sessao, image_gen


def jpeg_com_exif() -> bytes:
    img = Image.new("RGB", (16, 20), "red")
    exif = Image.Exif()
    exif[0x010F] = "CameraFake"  # Make
    exif[0x8825] = {2: (1.0, 2.0, 3.0)}  # GPS
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif)
    return out.getvalue()


def png_bytes(size=(12, 15), color="blue") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    monkeypatch.setattr(image_gen, "_avisar_img", lambda msg: None)
    monkeypatch.setattr(image_gen, "GEMINI_SSL_VERIFY", True)
    ia_sessao.reset()
    yield
    ia_sessao.reset()


def mock_http(monkeypatch, handler, chamadas: list | None = None):
    real = httpx.Client

    def factory(**kwargs):
        if chamadas is not None:
            chamadas.append(dict(kwargs))
        kwargs.pop("verify", None)
        return real(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(image_gen, "_http", lambda: factory(verify=image_gen._ssl_verify(), timeout=5))


def fake_try(nome: str, ok: bool, registro: list):
    def _f(arg, destino):
        registro.append(nome)
        if ok:
            return image_gen.CenaResult(image_gen._salvar(destino, png_bytes()), nome, "mock")
        return image_gen.CenaResult(None, nome, "falhou")
    return _f


# ---------- TLS ----------

def test_ssl_verificado_por_padrao(monkeypatch):
    ctx = image_gen._ssl_verify()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_ssl_opt_out_explicito(monkeypatch):
    monkeypatch.setattr(image_gen, "GEMINI_SSL_VERIFY", False)
    assert image_gen._ssl_verify() is False


def test_config_default_ssl_true(monkeypatch):
    import importlib

    import app.config as cfg

    monkeypatch.delenv("GEMINI_SSL_VERIFY", raising=False)
    monkeypatch.delenv("IMAGE_CHAIN", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    try:
        assert importlib.reload(cfg).GEMINI_SSL_VERIFY is True
        assert "cloudflare" in cfg.IMAGE_CHAIN and cfg.IMAGE_CHAIN[0] == "cloudflare"
    finally:
        monkeypatch.undo()
        importlib.reload(cfg)


# ---------- ordem e sticky ----------

def test_ordem_da_cadeia(monkeypatch, tmp_path):
    reg: list[str] = []
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["cloudflare", "pollinations", "pexels"])
    monkeypatch.setattr(image_gen, "_try_cloudflare", fake_try("cloudflare", False, reg))
    monkeypatch.setattr(image_gen, "_try_pollinations", fake_try("pollinations", False, reg))
    monkeypatch.setattr(image_gen, "_try_pexels", fake_try("pexels", True, reg))
    res = image_gen.gerar_cena_com_provider("p", "t", "a", tmp_path / "cena_01.png")
    assert reg == ["cloudflare", "pollinations", "pexels"]
    assert res.provider == "pexels" and res.path.is_file()
    assert "cloudflare:falhou" in res.detail


def test_provedor_desconhecido_e_pulado(monkeypatch, tmp_path):
    reg: list[str] = []
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["xpto", "pollinations"])
    monkeypatch.setattr(image_gen, "_try_pollinations", fake_try("pollinations", True, reg))
    res = image_gen.gerar_cena_com_provider("p", "t", "a", tmp_path / "c.png")
    assert res.provider == "pollinations" and "xpto: desconhecido" in res.detail


def test_cadeia_toda_falha(monkeypatch, tmp_path):
    reg: list[str] = []
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["cloudflare", "pexels"])
    monkeypatch.setattr(image_gen, "_try_cloudflare", fake_try("cloudflare", False, reg))
    monkeypatch.setattr(image_gen, "_try_pexels", fake_try("pexels", False, reg))
    res = image_gen.gerar_cena_com_provider("p", "t", "a", tmp_path / "c.png")
    assert res.path is None and res.provider == "none"


def test_sticky_provider(monkeypatch, tmp_path):
    reg: list[str] = []
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["cloudflare", "pollinations"])
    monkeypatch.setattr(image_gen, "_try_cloudflare", fake_try("cloudflare", False, reg))
    monkeypatch.setattr(image_gen, "_try_pollinations", fake_try("pollinations", True, reg))
    image_gen.gerar_cena_com_provider("p", "t", "a", tmp_path / "c1.png")
    assert ia_sessao.provedor_imagem == "pollinations"
    reg.clear()
    image_gen.gerar_cena_com_provider("p", "t", "a", tmp_path / "c2.png")
    assert reg == ["pollinations"]  # não tenta cloudflare de novo


def test_stock_recebe_query_curta(monkeypatch, tmp_path):
    visto = {}

    def fake(q, destino):
        visto["q"] = q
        return image_gen.CenaResult(None, "pexels", "x")

    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["pexels"])
    monkeypatch.setattr(image_gen, "_try_pexels", fake)
    image_gen.gerar_cena_com_provider("", "Água pela manhã!", "3 motivos", tmp_path / "c.png")
    assert "Requirements" not in visto["q"] and "Água" in visto["q"]


# ---------- PNG real, sem EXIF, metadados ----------

def test_salvar_converte_jpeg_para_png_sem_exif(tmp_path):
    out = image_gen._salvar(tmp_path / "cena_01.png", jpeg_com_exif())
    raw = out.read_bytes()
    assert raw.startswith(b"\x89PNG")
    with Image.open(out) as img:
        assert img.format == "PNG" and img.size == (16, 20)
        assert not img.getexif()
        assert "exif" not in img.info


def test_salvar_rejeita_lixo(tmp_path):
    with pytest.raises(image_gen.ImagemInvalida):
        image_gen._salvar(tmp_path / "x.png", b"<html>not an image</html>")
    assert not (tmp_path / "x.png").exists()


def test_salvar_forca_extensao_png(tmp_path):
    out = image_gen._salvar(tmp_path / "cena.jpg", jpeg_com_exif())
    assert out.suffix == ".png"


def test_meta_json_gravado_ao_lado(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["pollinations"])
    monkeypatch.setattr(image_gen, "_try_pollinations", fake_try("pollinations", True, []))
    res = image_gen.gerar_cena_com_provider("p", "t", "a", tmp_path / "cena_03.png")
    meta = json.loads((tmp_path / "cena_03.json").read_text(encoding="utf-8"))
    assert res.path.name == "cena_03.png"
    assert meta["provider"] == "pollinations" and "licenca" in meta


# ---------- cada provedor (MockTransport, sem rede) ----------

def test_pollinations_ok(monkeypatch, tmp_path):
    chamadas: list = []
    out = io.BytesIO()
    Image.frombytes("RGB", (60, 75), random.Random(1).randbytes(60 * 75 * 3)).save(out, "PNG")
    big = out.getvalue()
    mock_http(monkeypatch, lambda r: httpx.Response(200, content=big, headers={"content-type": "image/jpeg"}), chamadas)
    res = image_gen._try_pollinations("prompt", tmp_path / "c.png")
    assert res.path and res.meta["provider"] == "pollinations"
    assert isinstance(chamadas[0]["verify"], ssl.SSLContext)


def test_pollinations_rejeita_html(monkeypatch, tmp_path):
    mock_http(monkeypatch, lambda r: httpx.Response(200, content=b"x" * 5000, headers={"content-type": "text/html"}))
    res = image_gen._try_pollinations("prompt", tmp_path / "c.png")
    assert res.path is None and "não-imagem" in res.detail


def test_pollinations_rejeita_bytes_corrompidos(monkeypatch, tmp_path):
    mock_http(monkeypatch, lambda r: httpx.Response(200, content=b"\x00" * 5000, headers={"content-type": "image/png"}))
    res = image_gen._try_pollinations("prompt", tmp_path / "c.png")
    assert res.path is None and "imagem" in res.detail


def test_pollinations_http_erro(monkeypatch, tmp_path):
    mock_http(monkeypatch, lambda r: httpx.Response(429))
    assert image_gen._try_pollinations("p", tmp_path / "c.png").detail == "HTTP 429"


def test_pexels_sem_chave(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "PEXELS_API_KEY", "")
    assert image_gen._try_pexels("q", tmp_path / "c.png").detail == "PEXELS_API_KEY ausente"


def test_pexels_salva_atribuicao(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "PEXELS_API_KEY", "dummy-not-real")

    def handler(req: httpx.Request):
        if req.url.host == "api.pexels.com":
            assert req.headers["Authorization"] == "dummy-not-real"
            return httpx.Response(200, json={"photos": [{
                "id": 42, "url": "https://www.pexels.com/photo/x-42/",
                "photographer": "Ana Foto", "photographer_url": "https://www.pexels.com/@ana",
                "src": {"portrait": "https://images.pexels.com/42.jpeg"}}]})
        return httpx.Response(200, content=jpeg_com_exif(), headers={"content-type": "image/jpeg"})

    mock_http(monkeypatch, handler)
    monkeypatch.setattr(image_gen, "IMAGE_CHAIN", ["pexels"])
    res = image_gen.gerar_cena_com_provider("", "tema", "", tmp_path / "cena_01.png")
    assert res.path.read_bytes().startswith(b"\x89PNG")
    meta = json.loads((tmp_path / "cena_01.json").read_text(encoding="utf-8"))
    assert meta["fotografo"] == "Ana Foto"
    assert meta["fotografo_url"] == "https://www.pexels.com/@ana"
    assert meta["foto_url"].endswith("x-42/")
    assert meta["licenca"] == "Pexels License" and meta["licenca_url"]
    assert "Ana Foto" in meta["atribuicao"]


def test_pexels_sem_fotos(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "PEXELS_API_KEY", "dummy")
    mock_http(monkeypatch, lambda r: httpx.Response(200, json={"photos": []}))
    assert image_gen._try_pexels("q", tmp_path / "c.png").detail == "nenhuma foto"


def test_unsplash_salva_atribuicao_e_dispara_download(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "UNSPLASH_ACCESS_KEY", "dummy-not-real")
    vistos: list[str] = []

    def handler(req: httpx.Request):
        vistos.append(str(req.url))
        if req.url.path == "/search/photos":
            return httpx.Response(200, json={"results": [{
                "id": "abc",
                "urls": {"regular": "https://images.unsplash.com/abc.jpg"},
                "links": {"html": "https://unsplash.com/photos/abc",
                          "download_location": "https://api.unsplash.com/photos/abc/download"},
                "user": {"name": "Bia Lente", "links": {"html": "https://unsplash.com/@bia"}}}]})
        if req.url.path.endswith("/download"):
            return httpx.Response(200, json={"url": "x"})
        return httpx.Response(200, content=png_bytes(), headers={"content-type": "image/png"})

    mock_http(monkeypatch, handler)
    res = image_gen._try_unsplash("q", tmp_path / "c.png")
    assert res.path is not None
    assert any(v.endswith("/download") for v in vistos)
    assert res.meta["fotografo"] == "Bia Lente"
    assert "utm_source=" in res.meta["fotografo_url"] and "utm_source=" in res.meta["foto_url"]
    assert res.meta["licenca"] == "Unsplash License"


def test_unsplash_http_erro(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "UNSPLASH_ACCESS_KEY", "dummy")
    mock_http(monkeypatch, lambda r: httpx.Response(401, text="bad"))
    assert image_gen._try_unsplash("q", tmp_path / "c.png").detail.startswith("HTTP 401")


def test_hf_sem_token(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "HF_TOKEN", "")
    assert image_gen._try_hf("p", tmp_path / "c.png").detail == "HF_TOKEN ausente"


def test_hf_402_pula(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "HF_TOKEN", "dummy")
    mock_http(monkeypatch, lambda r: httpx.Response(402))
    assert "sem crédito" in image_gen._try_hf("p", tmp_path / "c.png").detail


def test_hf_imagem_direta(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "HF_TOKEN", "dummy")
    mock_http(monkeypatch, lambda r: httpx.Response(200, content=png_bytes(), headers={"content-type": "image/png"}))
    res = image_gen._try_hf("p", tmp_path / "c.png")
    assert res.path and res.provider == "hf"


def test_gemini_desabilitado(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "GEMINI_IMAGE_ENABLED", False)
    assert image_gen._try_gemini("p", tmp_path / "c.png").detail == "desabilitado"


def test_gemini_inline_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "GEMINI_IMAGE_ENABLED", True)
    part = SimpleNamespace(inline_data=SimpleNamespace(data=jpeg_com_exif()))
    resp = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **k: resp))
    monkeypatch.setattr(image_gen.gemini_client, "_client", lambda: client)
    res = image_gen._try_gemini("p", tmp_path / "c.png")
    assert res.path and res.path.read_bytes().startswith(b"\x89PNG")


def test_gemini_erro_api(monkeypatch, tmp_path):
    monkeypatch.setattr(image_gen, "GEMINI_IMAGE_ENABLED", True)

    def boom():
        raise RuntimeError("429 quota")

    monkeypatch.setattr(image_gen.gemini_client, "_client", boom)
    assert "429" in image_gen._try_gemini("p", tmp_path / "c.png").detail


def test_cloudflare_wrapper(monkeypatch, tmp_path):
    import app.cloudflare_image as cf

    monkeypatch.setattr(cf, "gerar_png_cloudflare", lambda prompt: jpeg_com_exif())
    res = image_gen._try_cloudflare("p", tmp_path / "c.png")
    assert res.path and res.meta["provider"] == "cloudflare"


def test_cloudflare_bytes_invalidos(monkeypatch, tmp_path):
    import app.cloudflare_image as cf

    monkeypatch.setattr(cf, "gerar_png_cloudflare", lambda prompt: b"garbage")
    res = image_gen._try_cloudflare("p", tmp_path / "c.png")
    assert res.path is None and "imagem" in res.detail


def test_aihorde_wrapper(monkeypatch, tmp_path):
    import app.aihorde_image as horde

    monkeypatch.setattr(horde, "gerar_png_aihorde", lambda prompt: png_bytes())
    assert image_gen._try_aihorde("p", tmp_path / "c.png").provider == "aihorde"


def test_openrouter_wrapper_falha(monkeypatch, tmp_path):
    import app.openrouter_client as orc

    def boom(prompt):
        raise orc.OpenRouterUnavailable("sem modelo grátis")

    monkeypatch.setattr(orc, "gerar_png_openrouter", boom)
    res = image_gen._try_openrouter("p", tmp_path / "c.png")
    assert res.path is None and "grátis" in res.detail
