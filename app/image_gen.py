"""Chaveador de cena (abordagem A): percorre IMAGE_CHAIN até obter uma imagem.

Toda saída vira PNG real (Pillow), sem EXIF, e ganha um `cena_XX.json` ao lado
com provedor, licença e — para fotos de banco (Pexels/Unsplash) — fotógrafo e URL
para atribuição.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import httpx

from app import gemini_client, ia_sessao
from app.config import (
    FEED_HEIGHT,
    FEED_WIDTH,
    GEMINI_IMAGE_ENABLED,
    GEMINI_IMAGE_MODEL,
    GEMINI_SSL_VERIFY,
    HF_IMAGE_MODEL,
    HF_TOKEN,
    IMAGE_CHAIN,
    PEXELS_API_KEY,
    UNSPLASH_ACCESS_KEY,
)

log = logging.getLogger(__name__)

UNSPLASH_UTM = "utm_source=agente_criativos&utm_medium=referral"

LICENCAS: dict[str, dict[str, str]] = {
    "pexels": {"licenca": "Pexels License", "licenca_url": "https://www.pexels.com/license/"},
    "unsplash": {"licenca": "Unsplash License", "licenca_url": "https://unsplash.com/license"},
    "pollinations": {"licenca": "Imagem gerada por IA (Pollinations)", "licenca_url": "https://pollinations.ai/"},
    "cloudflare": {"licenca": "Imagem gerada por IA (Workers AI / FLUX)", "licenca_url": ""},
    "aihorde": {"licenca": "Imagem gerada por IA (AI Horde)", "licenca_url": "https://aihorde.net/"},
    "openrouter": {"licenca": "Imagem gerada por IA (OpenRouter)", "licenca_url": ""},
    "gemini": {"licenca": "Imagem gerada por IA (Gemini)", "licenca_url": ""},
    "hf": {"licenca": "Imagem gerada por IA (Hugging Face)", "licenca_url": ""},
}


class ImagemInvalida(ValueError):
    """Bytes recebidos não decodificam como imagem."""


@dataclass
class CenaResult:
    path: Path | None
    provider: str
    detail: str = ""
    meta: dict = field(default_factory=dict)


def _montar_prompt_cena(prompt_usuario: str, titulo: str, apoio: str) -> str:
    base = (prompt_usuario or "").strip()
    if not base:
        base = (
            f"Photorealistic editorial Instagram photo illustrating: {titulo}. "
            f"{apoio}".strip()
        )
    return (
        f"{base}\n\n"
        "Requirements: vertical 4:5 composition, cinematic lighting, high detail, "
        "NO text, NO letters, NO watermark, NO logo, NO captions on the image. "
        "Leave some darker area in the lower third for typography overlay."
    )


def _query_stock(titulo: str, apoio: str, prompt_usuario: str) -> str:
    bruto = f"{titulo} {apoio} {prompt_usuario}"
    bruto = re.sub(r"[^a-zA-ZÀ-ÿ0-9\s]", " ", bruto)
    palavras = [p for p in bruto.split() if len(p) > 2][:8]
    return " ".join(palavras) or "health lifestyle"


def _ssl_verify() -> ssl.SSLContext | bool:
    """TLS verificado por padrão (CAs do sistema). Só desliga com GEMINI_SSL_VERIFY=false explícito."""
    if GEMINI_SSL_VERIFY:
        return ssl.create_default_context()
    log.warning("TLS sem verificação (GEMINI_SSL_VERIFY=false no .env) — use só em rede com MITM conhecido")
    return False


def _http() -> httpx.Client:
    return httpx.Client(verify=_ssl_verify(), timeout=180.0)


def normalizar_png(data: bytes) -> bytes:
    """Decodifica qualquer formato suportado pelo Pillow e reexporta PNG limpo (sem EXIF/metadados)."""
    from PIL import Image, ImageOps

    if not data:
        raise ImagemInvalida("vazio")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            transparente = img.mode in {"RGBA", "LA"} or (img.mode == "P" and "transparency" in img.info)
            modo = "RGBA" if transparente else "RGB"
            limpa = Image.new(modo, img.size)
            limpa.paste(img.convert(modo))
    except ImagemInvalida:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ImagemInvalida(f"bytes não são imagem ({type(exc).__name__})") from exc
    out = io.BytesIO()
    limpa.save(out, "PNG", optimize=True)
    return out.getvalue()


def _salvar(destino: Path, data: bytes) -> Path:
    """Grava sempre PNG real (converte JPEG/WebP etc.) e sem EXIF."""
    png = normalizar_png(data)
    destino = destino.with_suffix(".png")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(png)
    return destino


def salvar_meta(destino_png: Path, meta: dict) -> Path:
    """Grava cena_XX.json ao lado do PNG (atribuição/licença)."""
    path = destino_png.with_suffix(".json")
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _meta_base(provider: str, **extra) -> dict:
    meta = {"provider": provider, **LICENCAS.get(provider, {})}
    meta.update({k: v for k, v in extra.items() if v not in (None, "")})
    return meta


def _try_openrouter(prompt: str, destino: Path) -> CenaResult:
    from app.openrouter_client import OpenRouterUnavailable, gerar_png_openrouter

    try:
        return CenaResult(_salvar(destino, gerar_png_openrouter(prompt)), "openrouter", "ok",
                          _meta_base("openrouter", prompt=prompt))
    except Exception as exc:  # noqa: BLE001
        detail = str(exc) if isinstance(exc, (OpenRouterUnavailable, ImagemInvalida)) else type(exc).__name__
        return CenaResult(None, "openrouter", detail)


def _try_cloudflare(prompt: str, destino: Path) -> CenaResult:
    from app.cloudflare_image import CloudflareImageError, gerar_png_cloudflare

    try:
        return CenaResult(_salvar(destino, gerar_png_cloudflare(prompt)), "cloudflare", "ok",
                          _meta_base("cloudflare", prompt=prompt))
    except Exception as exc:  # noqa: BLE001
        detail = str(exc) if isinstance(exc, (CloudflareImageError, ImagemInvalida)) else type(exc).__name__
        return CenaResult(None, "cloudflare", detail)


def _try_aihorde(prompt: str, destino: Path) -> CenaResult:
    from app.aihorde_image import AiHordeImageError, gerar_png_aihorde

    try:
        return CenaResult(_salvar(destino, gerar_png_aihorde(prompt)), "aihorde", "ok",
                          _meta_base("aihorde", prompt=prompt))
    except Exception as exc:  # noqa: BLE001
        detail = str(exc) if isinstance(exc, (AiHordeImageError, ImagemInvalida)) else type(exc).__name__
        return CenaResult(None, "aihorde", detail)


def _try_gemini(prompt: str, destino: Path) -> CenaResult:
    if not GEMINI_IMAGE_ENABLED:
        return CenaResult(None, "gemini", "desabilitado")
    from google.genai import types

    try:
        client = gemini_client._client()
        resp = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
    except Exception as exc:  # noqa: BLE001
        return CenaResult(None, "gemini", str(exc)[:180])

    if not resp.candidates:
        return CenaResult(None, "gemini", "sem candidates")
    for part in resp.candidates[0].content.parts:
        inline = getattr(part, "inline_data", None)
        if not inline or not inline.data:
            continue
        data = inline.data
        if isinstance(data, str):
            data = base64.b64decode(data)
        try:
            return CenaResult(_salvar(destino, data), "gemini", "ok",
                              _meta_base("gemini", prompt=prompt, modelo=GEMINI_IMAGE_MODEL))
        except ImagemInvalida as exc:
            return CenaResult(None, "gemini", str(exc))
    return CenaResult(None, "gemini", "sem bytes de imagem")


def _try_hf(prompt: str, destino: Path) -> CenaResult:
    if not HF_TOKEN:
        return CenaResult(None, "hf", "HF_TOKEN ausente")
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "image/png",
    }
    attempts: list[tuple[str, dict]] = [
        (
            "https://router.huggingface.co/fal-ai/fal-ai/flux/schnell",
            {
                "prompt": prompt,
                "image_size": {"width": FEED_WIDTH, "height": FEED_HEIGHT},
                "num_images": 1,
            },
        ),
        (
            f"https://router.huggingface.co/hf-inference/models/{HF_IMAGE_MODEL}",
            {"inputs": prompt, "parameters": {"width": FEED_WIDTH, "height": FEED_HEIGHT}},
        ),
    ]
    last_err = "sem resposta"
    meta = _meta_base("hf", prompt=prompt, modelo=HF_IMAGE_MODEL)
    try:
        with _http() as client:
            for url, payload in attempts:
                r = client.post(url, headers=headers, json=payload)
                if r.status_code == 402:
                    return CenaResult(
                        None,
                        "hf",
                        "sem crédito no Inference Providers (PRO/pre-paid) — próximo da cadeia",
                    )
                if r.status_code >= 400:
                    last_err = f"HTTP {r.status_code}: {r.text[:120]}"
                    continue
                ctype = r.headers.get("content-type", "")
                if "json" in ctype:
                    data = r.json()
                    img_url = None
                    if isinstance(data, dict):
                        imgs = data.get("images") or []
                        if imgs and isinstance(imgs[0], dict):
                            img_url = imgs[0].get("url")
                        img_url = img_url or data.get("image") or data.get("url")
                    if not img_url:
                        last_err = f"json sem url: {str(data)[:120]}"
                        continue
                    img = client.get(img_url)
                    if img.status_code >= 400:
                        last_err = f"download fal HTTP {img.status_code}"
                        continue
                    return CenaResult(_salvar(destino, img.content), "hf", "ok (fal)", meta)
                if "image" in ctype or r.content.startswith(b"\x89PNG"):
                    return CenaResult(_salvar(destino, r.content), "hf", "ok", meta)
                last_err = f"resposta não-imagem ({ctype}): {r.text[:100]}"
            return CenaResult(None, "hf", last_err)
    except Exception as exc:  # noqa: BLE001
        return CenaResult(None, "hf", str(exc)[:180])


def _try_pollinations(prompt: str, destino: Path) -> CenaResult:
    q = quote(prompt[:800], safe="")
    url = (
        f"https://image.pollinations.ai/prompt/{q}"
        f"?width={FEED_WIDTH}&height={FEED_HEIGHT}&nologo=true&nofeed=true&enhance=true"
    )
    try:
        with _http() as client:
            r = client.get(url)
            if r.status_code >= 400:
                return CenaResult(None, "pollinations", f"HTTP {r.status_code}")
            ctype = r.headers.get("content-type", "").lower()
            if not ctype.startswith("image/"):
                return CenaResult(None, "pollinations", f"content-type não-imagem ({ctype or 'vazio'})")
            if len(r.content) < 1000:
                return CenaResult(None, "pollinations", "resposta muito pequena")
            return CenaResult(_salvar(destino, r.content), "pollinations", "ok",
                              _meta_base("pollinations", prompt=prompt))
    except ImagemInvalida as exc:
        return CenaResult(None, "pollinations", str(exc))
    except Exception as exc:  # noqa: BLE001
        return CenaResult(None, "pollinations", str(exc)[:180])


def _try_pexels(query: str, destino: Path) -> CenaResult:
    if not PEXELS_API_KEY:
        return CenaResult(None, "pexels", "PEXELS_API_KEY ausente")
    headers = {"Authorization": PEXELS_API_KEY}
    try:
        with _http() as client:
            r = client.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": query, "per_page": 1, "orientation": "portrait"},
            )
            if r.status_code >= 400:
                return CenaResult(None, "pexels", f"HTTP {r.status_code}: {r.text[:120]}")
            photos = (r.json() or {}).get("photos") or []
            if not photos:
                return CenaResult(None, "pexels", "nenhuma foto")
            photo = photos[0]
            src = photo.get("src", {})
            img_url = src.get("portrait") or src.get("large2x") or src.get("large")
            if not img_url:
                return CenaResult(None, "pexels", "url ausente")
            img = client.get(img_url)
            if img.status_code >= 400:
                return CenaResult(None, "pexels", f"download HTTP {img.status_code}")
            fotografo = photo.get("photographer", "")
            meta = _meta_base(
                "pexels",
                query=query,
                fotografo=fotografo,
                fotografo_url=photo.get("photographer_url", ""),
                foto_url=photo.get("url", ""),
                foto_id=photo.get("id"),
                atribuicao=f"Foto: {fotografo} / Pexels" if fotografo else "Foto: Pexels",
            )
            return CenaResult(_salvar(destino, img.content), "pexels", "ok", meta)
    except ImagemInvalida as exc:
        return CenaResult(None, "pexels", str(exc))
    except Exception as exc:  # noqa: BLE001
        return CenaResult(None, "pexels", str(exc)[:180])


def _try_unsplash(query: str, destino: Path) -> CenaResult:
    if not UNSPLASH_ACCESS_KEY:
        return CenaResult(None, "unsplash", "UNSPLASH_ACCESS_KEY ausente")
    headers = {
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
        "Accept-Version": "v1",
    }
    try:
        with _http() as client:
            r = client.get(
                "https://api.unsplash.com/search/photos",
                headers=headers,
                params={"query": query, "per_page": 1, "orientation": "portrait"},
            )
            if r.status_code >= 400:
                return CenaResult(None, "unsplash", f"HTTP {r.status_code}: {r.text[:120]}")
            results = (r.json() or {}).get("results") or []
            if not results:
                return CenaResult(None, "unsplash", "nenhuma foto")
            photo = results[0]
            urls = photo.get("urls") or {}
            img_url = urls.get("regular") or urls.get("full") or urls.get("small")
            if not img_url:
                return CenaResult(None, "unsplash", "url ausente")
            # Guidelines: disparar endpoint de download (não bloqueia se falhar)
            dl = (photo.get("links") or {}).get("download_location")
            if dl:
                try:
                    client.get(dl, headers=headers)
                except Exception:  # noqa: BLE001
                    pass
            img = client.get(img_url)
            if img.status_code >= 400:
                return CenaResult(None, "unsplash", f"download HTTP {img.status_code}")
            user = photo.get("user") or {}
            nome = user.get("name", "")
            perfil = (user.get("links") or {}).get("html", "")
            foto_url = (photo.get("links") or {}).get("html", "")
            meta = _meta_base(
                "unsplash",
                query=query,
                fotografo=nome,
                fotografo_url=f"{perfil}?{UNSPLASH_UTM}" if perfil else "",
                foto_url=f"{foto_url}?{UNSPLASH_UTM}" if foto_url else "",
                foto_id=photo.get("id"),
                atribuicao=f"Foto: {nome} / Unsplash" if nome else "Foto: Unsplash",
            )
            return CenaResult(_salvar(destino, img.content), "unsplash", "ok", meta)
    except ImagemInvalida as exc:
        return CenaResult(None, "unsplash", str(exc))
    except Exception as exc:  # noqa: BLE001
        return CenaResult(None, "unsplash", str(exc)[:180])


def gerar_cena_png(prompt_usuario: str, titulo: str, apoio: str, destino: Path) -> Path | None:
    """Compat: retorna só Path (usa chaveador)."""
    return gerar_cena_com_provider(prompt_usuario, titulo, apoio, destino).path


def _avisar_img(msg: str) -> None:
    print(f"  ↻ imagem: {msg}")


_PROMPT_PROVIDERS = {
    "openrouter": "_try_openrouter",
    "cloudflare": "_try_cloudflare",
    "gemini": "_try_gemini",
    "aihorde": "_try_aihorde",
    "hf": "_try_hf",
    "pollinations": "_try_pollinations",
}
_STOCK_PROVIDERS = {"pexels": "_try_pexels", "unsplash": "_try_unsplash"}


def gerar_cena_com_provider(
    prompt_usuario: str,
    titulo: str,
    apoio: str,
    destino: Path,
) -> CenaResult:
    """
    Percorre IMAGE_CHAIN até obter PNG.
    Sticky: provedor que já funcionou nesta corrida vai primeiro.
    Se um falha → troca e continua (não recomeça as cenas anteriores).
    """
    prompt = _montar_prompt_cena(prompt_usuario, titulo, apoio)
    stock_q = _query_stock(titulo, apoio, prompt_usuario)
    tentativas: list[str] = []
    cadeia = ia_sessao.fila_imagem(list(IMAGE_CHAIN))
    modulo = globals()

    for i, nome in enumerate(cadeia):
        if nome in _PROMPT_PROVIDERS:
            res = modulo[_PROMPT_PROVIDERS[nome]](prompt, destino)
        elif nome in _STOCK_PROVIDERS:
            res = modulo[_STOCK_PROVIDERS[nome]](stock_q, destino)
        else:
            tentativas.append(f"{nome}: desconhecido")
            continue

        if res.path:
            ia_sessao.lembrar_imagem(res.provider)
            if i > 0:
                _avisar_img(f"ok via {res.provider} — sigo com ele nas próximas cenas")
            log.info("Cena OK via %s", res.provider)
            res.detail = "ok | " + " → ".join(tentativas + [f"{res.provider}:ok"])
            meta = res.meta or _meta_base(res.provider)
            try:
                salvar_meta(res.path, meta)
            except OSError as exc:  # noqa: BLE001
                log.warning("Não gravei metadados da cena: %s", exc)
            return res

        tentativas.append(f"{res.provider}:{res.detail}")
        log.warning("Cena falhou (%s): %s", res.provider, res.detail)
        if i + 1 < len(cadeia):
            detalhe = (res.detail or "")[:60]
            _avisar_img(
                f"{res.provider} falhou ({detalhe}) → trocando para {cadeia[i + 1]} e continuo"
            )

    return CenaResult(None, "none", " | ".join(tentativas) or "cadeia vazia")
