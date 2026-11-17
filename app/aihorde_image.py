"""AI Horde image transport only; other image providers stay unchanged."""
from __future__ import annotations

import asyncio
import io
import re
import ssl
import time
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from PIL import Image

from app.config import AIHORDE_API_KEY, AIHORDE_CLIENT_AGENT

_TIMEOUT_SECONDS = 60.0
_POLL_INTERVAL = 1.0
_CANCEL_TIMEOUT = 5.0
_MAX_IMAGE_BYTES = 30 * 1024 * 1024
_API_BASE = "https://aihorde.net/api/v2"
_WIDTH = 512
_HEIGHT = 640
_STEPS = 16
_cooldown_until = 0.0
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class AiHordeImageError(Exception):
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


def _headers() -> dict[str, str]:
    return {
        "apikey": AIHORDE_API_KEY,
        "Client-Agent": AIHORDE_CLIENT_AGENT,
        "Accept": "application/json",
    }


def _payload(prompt: str) -> dict:
    return {
        "prompt": prompt,
        "params": {
            "width": _WIDTH,
            "height": _HEIGHT,
            "steps": _STEPS,
            "n": 1,
            "sampler_name": "k_euler_a",
            "cfg_scale": 7.5,
            "hires_fix": False,
        },
        "nsfw": False,
        "censor_nsfw": True,
        "r2": True,
        "trusted_workers": False,
        "slow_workers": True,
        "shared": False,
        "replacement_filter": True,
    }


def _png_from_bytes(raw: bytes) -> bytes:
    if not raw or len(raw) > _MAX_IMAGE_BYTES:
        raise AiHordeImageError("AI Horde empty/oversized image")
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        out = io.BytesIO()
        image.convert("RGBA" if "A" in image.getbands() else "RGB").save(out, "PNG")
        return out.getvalue()


def _image_host_ok(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    return host == "aihorde.net" or host.endswith(".aihorde.net") or host.endswith(".r2.dev") or "r2.cloudflarestorage.com" in host


async def _cancel(client: httpx.AsyncClient, request_id: str) -> None:
    try:
        await asyncio.wait_for(
            client.delete(
                f"{_API_BASE}/generate/status/{request_id}",
                headers=_headers(),
            ),
            timeout=_CANCEL_TIMEOUT,
        )
    except Exception:
        return


async def _download_image(client: httpx.AsyncClient, img: str) -> bytes:
    if img.startswith("http://") or img.startswith("https://"):
        if not _image_host_ok(img):
            raise AiHordeImageError("AI Horde unexpected image host")
        response = await client.get(img, headers={"Accept": "image/*"}, follow_redirects=True)
        if not 200 <= response.status_code < 300:
            raise AiHordeImageError(f"AI Horde download HTTP {response.status_code}")
        return _png_from_bytes(response.content)
    # r2=false fallback: base64 webp/png
    import base64

    raw = img
    if raw.startswith("data:image/") and ";base64," in raw:
        raw = raw.split(";base64,", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise AiHordeImageError("AI Horde invalid image payload") from exc
    return _png_from_bytes(data)


async def _run(prompt: str) -> bytes:
    request_id: str | None = None
    finished = False
    # System CA trust, including Windows roots. Never inherit Gemini verify=False.
    async with httpx.AsyncClient(
        verify=ssl.create_default_context(),
        timeout=_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        try:
            submitted = await client.post(
                f"{_API_BASE}/generate/async",
                headers=_headers(),
                json=_payload(prompt),
            )
            if submitted.status_code == 429:
                global _cooldown_until
                _cooldown_until = time.monotonic() + _retry_after(
                    submitted.headers.get("retry-after")
                )
            if submitted.status_code not in {200, 202}:
                raise AiHordeImageError(f"AI Horde HTTP {submitted.status_code}")
            body = submitted.json()
            if not isinstance(body, dict):
                raise AiHordeImageError("AI Horde malformed submit")
            request_id = str(body.get("id") or "")
            if not _UUID_RE.fullmatch(request_id):
                request_id = None
                raise AiHordeImageError("AI Horde missing request id")

            while True:
                check = await client.get(
                    f"{_API_BASE}/generate/check/{request_id}",
                    headers=_headers(),
                )
                if check.status_code == 429:
                    _cooldown_until = time.monotonic() + _retry_after(
                        check.headers.get("retry-after")
                    )
                    raise AiHordeImageError("AI Horde HTTP 429")
                if not 200 <= check.status_code < 300:
                    raise AiHordeImageError(f"AI Horde HTTP {check.status_code}")
                status = check.json()
                if not isinstance(status, dict):
                    raise AiHordeImageError("AI Horde malformed check")
                if status.get("faulted"):
                    raise AiHordeImageError("AI Horde request faulted")
                if status.get("is_possible") is False:
                    raise AiHordeImageError("AI Horde no eligible workers")
                if status.get("done"):
                    break
                await asyncio.sleep(_POLL_INTERVAL)

            result = await client.get(
                f"{_API_BASE}/generate/status/{request_id}",
                headers=_headers(),
            )
            if not 200 <= result.status_code < 300:
                raise AiHordeImageError(f"AI Horde HTTP {result.status_code}")
            payload = result.json()
            if not isinstance(payload, dict):
                raise AiHordeImageError("AI Horde malformed status")
            generations = payload.get("generations") or []
            if not generations or not isinstance(generations, list):
                raise AiHordeImageError("AI Horde empty generations")
            item = generations[0]
            if not isinstance(item, dict):
                raise AiHordeImageError("AI Horde malformed generation")
            if item.get("censored") is True:
                raise AiHordeImageError("AI Horde image censored")
            img = item.get("img")
            if not isinstance(img, str) or not img:
                raise AiHordeImageError("AI Horde empty image")
            png = await _download_image(client, img)
            finished = True
            return png
        finally:
            if request_id and not finished:
                await _cancel(client, request_id)


async def _request(prompt: str) -> bytes:
    return await asyncio.wait_for(_run(prompt), timeout=_TIMEOUT_SECONDS)


def gerar_png_aihorde(prompt: str) -> bytes:
    global _cooldown_until
    if not AIHORDE_API_KEY:
        raise AiHordeImageError("AI Horde credentials missing")
    if AIHORDE_API_KEY.strip() in {"0000000000", "00000000000000000000000000000000"}:
        raise AiHordeImageError("AI Horde anonymous key refused")
    if not AIHORDE_CLIENT_AGENT or "\n" in AIHORDE_CLIENT_AGENT or "\r" in AIHORDE_CLIENT_AGENT:
        raise AiHordeImageError("AI Horde client agent invalid")
    if time.monotonic() < _cooldown_until:
        raise AiHordeImageError("AI Horde rate-limit cooldown")
    try:
        return asyncio.run(_request(prompt))
    except AiHordeImageError:
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise AiHordeImageError("AI Horde timeout (60s deadline)") from exc
    except Exception as exc:
        raise AiHordeImageError("AI Horde " + type(exc).__name__) from exc
