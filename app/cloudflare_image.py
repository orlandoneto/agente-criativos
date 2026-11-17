"""Cloudflare image transport only; other image providers stay unchanged."""
from __future__ import annotations

import asyncio
import base64
import io
import re
import ssl
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone

import httpx
from PIL import Image

from app.config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_IMAGE_MODEL

_TIMEOUT_SECONDS = 60.0
_MAX_IMAGE_BYTES = 30 * 1024 * 1024
_cooldown_until = 0.0


class CloudflareImageError(Exception):
    """Safe diagnostic: never include credentials or upstream response bodies."""


def _retry_after(value: str | None) -> float:
    try:
        return max(0.0, float(value))
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value or "")
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 120.0


async def _request(prompt: str) -> httpx.Response:
    async def send() -> httpx.Response:
        # System CA trust, including Windows roots. Never inherit Gemini verify=False.
        async with httpx.AsyncClient(
            verify=ssl.create_default_context(), timeout=_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            url = ("https://api.cloudflare.com/client/v4/accounts/"
                   + CLOUDFLARE_ACCOUNT_ID + "/ai/run/" + CLOUDFLARE_IMAGE_MODEL)
            headers = {"Authorization": "Bearer " + CLOUDFLARE_API_TOKEN}
            if CLOUDFLARE_IMAGE_MODEL.startswith("@cf/black-forest-labs/flux-2-"):
                # FLUX.2 requires multipart; use a small 4:5 image, not JSON.
                fields = {"prompt": (None, prompt), "width": (None, "512"),
                          "height": (None, "640")}
                return await client.post(url, headers=headers, files=fields)
            # Tested Schnell contract is prompt-only. No size/steps/seed extras.
            return await client.post(url, headers=headers, json={"prompt": prompt})
    # Wall-clock request/body deadline, not just a per-chunk idle timeout.
    return await asyncio.wait_for(send(), timeout=_TIMEOUT_SECONDS)


def _segundos_ate_meia_noite_utc() -> float:
    agora = datetime.now(timezone.utc)
    amanha = (agora + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
    return max(60.0, (amanha - agora).total_seconds())


def _cota_diaria_esgotada(response: httpx.Response) -> bool:
    """Workers AI free: erro 4006 = 10.000 neurons/dia usados (zera 00:00 UTC). Lê só o código."""
    try:
        erros = response.json().get("errors") or []
        return any(isinstance(e, dict) and e.get("code") == 4006 for e in erros)
    except Exception:  # noqa: BLE001
        return False


def gerar_png_cloudflare(prompt: str) -> bytes:
    global _cooldown_until
    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ACCOUNT_ID:
        raise CloudflareImageError("Cloudflare credentials missing")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", CLOUDFLARE_ACCOUNT_ID):
        raise CloudflareImageError("Cloudflare account ID invalid")
    if not re.fullmatch(r"@cf/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", CLOUDFLARE_IMAGE_MODEL):
        raise CloudflareImageError("Cloudflare model ID invalid")
    if time.monotonic() < _cooldown_until:
        raise CloudflareImageError("Cloudflare rate-limit cooldown")
    try:
        response = asyncio.run(_request(prompt))
        if response.status_code == 429:
            if _cota_diaria_esgotada(response):
                _cooldown_until = time.monotonic() + _segundos_ate_meia_noite_utc()
                raise CloudflareImageError("Cloudflare cota diária grátis esgotada (zera 00:00 UTC = 21:00 BRT)")
            _cooldown_until = time.monotonic() + _retry_after(response.headers.get("retry-after"))
        if not 200 <= response.status_code < 300:
            raise CloudflareImageError(f"Cloudflare HTTP {response.status_code}")
        raw = response.content
        if "json" in response.headers.get("content-type", "").lower() or raw.lstrip().startswith(b"{"):
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("success") is False or payload.get("errors"):
                raise CloudflareImageError("Cloudflare response error")
            result = payload.get("result", payload)
            image = result.get("image") if isinstance(result, dict) else None
            if not isinstance(image, str) or not image:
                raise CloudflareImageError("Cloudflare empty image")
            if image.startswith("data:image/") and ";base64," in image:
                image = image.split(";base64,", 1)[1]
            raw = base64.b64decode(image, validate=True)
        if not raw or len(raw) > _MAX_IMAGE_BYTES:
            raise CloudflareImageError("Cloudflare empty/oversized image")
        # Reject malformed/HTML payloads and normalize real image bytes to PNG.
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            out = io.BytesIO()
            image.convert("RGBA" if "A" in image.getbands() else "RGB").save(out, "PNG")
            return out.getvalue()
    except CloudflareImageError:
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise CloudflareImageError("Cloudflare timeout (60s deadline)") from exc
    except Exception as exc:
        raise CloudflareImageError("Cloudflare " + type(exc).__name__) from exc
