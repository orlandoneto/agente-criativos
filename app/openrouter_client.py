"""OpenRouter free-only text/image transport; safe failover, never paid routes."""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import ssl
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime

import httpx
from PIL import Image

from app import ia_sessao
from app.config import OPENROUTER_API_KEY, OPENROUTER_IMAGE_MODELS, OPENROUTER_TEXT_MODELS

_BASE = "https://openrouter.ai/api/v1"
_TIMEOUT_SECONDS = 60.0
_TEXT_BUDGET_SECONDS = 180.0
_COOLDOWN_SECONDS = 120.0
_MAX_IMAGE_BYTES = 30 * 1024 * 1024
_catalog: list[dict] | None = None
_catalog_until = 0.0
_cooldown_until = 0.0


class OpenRouterUnavailable(Exception):
    """Diagnostics contain only status/types/model IDs, never remote bodies or keys."""


def _retry_after(value: str | None) -> float:
    try:
        return max(1.0, float(value))
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value or "")
            return max(1.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return _COOLDOWN_SECONDS


def _free_slug(model: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+:free", model))


def _zero(value) -> bool:
    try:
        return Decimal(str(value)) == 0
    except (ValueError, InvalidOperation):
        return False


def _eligible(entry: dict, modality: str) -> bool:
    pricing = entry.get("pricing") or {}
    return (_free_slug(entry.get("id", ""))
            and modality in entry.get("architecture", {}).get("output_modalities", [])
            and all(k in pricing and _zero(pricing[k]) for k in ("prompt", "completion"))
            and all(_zero(pricing.get(k, "0")) for k in ("request", "image_output")))


def _check_response(response: httpx.Response) -> None:
    global _cooldown_until
    if response.status_code == 429:
        _cooldown_until = time.monotonic() + _retry_after(response.headers.get("retry-after"))
    if not 200 <= response.status_code < 300:
        raise OpenRouterUnavailable(f"OpenRouter HTTP {response.status_code}")


def _check_ready() -> None:
    if not OPENROUTER_API_KEY:
        raise OpenRouterUnavailable("OpenRouter credentials missing")
    if time.monotonic() < _cooldown_until:
        raise OpenRouterUnavailable("OpenRouter rate-limit cooldown")


async def _request(model: str, prompt: str, image: bool, json_mode: bool,
                   max_tokens: int) -> dict:
    global _catalog, _catalog_until
    async with httpx.AsyncClient(verify=ssl.create_default_context(),
                                timeout=_TIMEOUT_SECONDS, follow_redirects=False) as client:
        if _catalog is None or time.monotonic() >= _catalog_until:
            response = await client.get(_BASE + "/models")
            _check_response(response)
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                raise OpenRouterUnavailable("OpenRouter catalog malformed")
            _catalog = data["data"]
            _catalog_until = time.monotonic() + 300.0
        entry = next((m for m in _catalog if m.get("id") == model), None)
        if not entry or not _eligible(entry, "image" if image else "text"):
            raise OpenRouterUnavailable("OpenRouter model not verified free/available")
        headers = {"Authorization": "Bearer " + OPENROUTER_API_KEY}
        if image:
            # Dedicated Image API: pin a current zero-price endpoint, never let
            # provider fallback silently select a paid endpoint.
            response = await client.get(_BASE + "/images/models/" + model + "/endpoints")
            _check_response(response)
            info = response.json()
            endpoints = info.get("endpoints", [])
            endpoint = next((e for e in endpoints if e.get("pricing")
                             and all(_zero(p.get("cost_usd")) for p in e["pricing"])
                             and e.get("provider_tag")), None)
            if not endpoint:
                raise OpenRouterUnavailable("OpenRouter no verified zero-price image endpoint")
            payload = {"model": model, "prompt": prompt, "n": 1,
                       "provider": {"only": [endpoint["provider_tag"]],
                                    "allow_fallbacks": False}}
            response = await client.post(_BASE + "/images", headers=headers, json=payload)
        else:
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "stream": False,
                       "provider": {"allow_fallbacks": False,
                                    "max_price": {"prompt": 0, "completion": 0}}}
            supported = entry.get("supported_parameters", [])
            if "reasoning" in supported:
                payload["reasoning"] = {"effort": "none"}
            if json_mode and "response_format" in supported:
                payload["response_format"] = {"type": "json_object"}
            response = await client.post(_BASE + "/chat/completions", headers=headers, json=payload)
        _check_response(response)
        data = response.json()
        if not isinstance(data, dict) or data.get("error"):
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                if str(data["error"].get("code")) == "429":
                    _set_quota_cooldown()
            raise OpenRouterUnavailable("OpenRouter response error")
        return data


def _set_quota_cooldown() -> None:
    global _cooldown_until
    _cooldown_until = time.monotonic() + _COOLDOWN_SECONDS


def _attempt(model: str, prompt: str, image=False, json_mode=False,
             max_tokens=4096, timeout=None) -> dict:
    _check_ready()
    if not _free_slug(model):
        raise OpenRouterUnavailable("OpenRouter paid/non-free model rejected locally")
    async def run():
        return await asyncio.wait_for(_request(model, prompt, image, json_mode, max_tokens),
                                      timeout=timeout or _TIMEOUT_SECONDS)
    try:
        return asyncio.run(run())
    except OpenRouterUnavailable:
        raise
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise OpenRouterUnavailable("OpenRouter timeout (60s deadline)") from exc
    except Exception as exc:
        raise OpenRouterUnavailable("OpenRouter " + type(exc).__name__) from exc


def modelos_texto() -> list[str]:
    if not OPENROUTER_API_KEY:
        return []
    names = ["openrouter/" + m for m in OPENROUTER_TEXT_MODELS if _free_slug(m)]
    return ia_sessao.fila_texto(names)


def _text_chain(prompt: str, validator, json_mode: bool, max_tokens: int):
    _check_ready()
    deadline = time.monotonic() + _TEXT_BUDGET_SECONDS
    errors = []
    for label in modelos_texto():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        model = label.removeprefix("openrouter/")
        try:
            payload = _attempt(model, prompt, json_mode=json_mode, max_tokens=max_tokens,
                               timeout=min(_TIMEOUT_SECONDS, remaining))
            choices = payload.get("choices") or []
            choice = choices[0] if choices else {}
            if choice.get("finish_reason") in {"error", "length", "content_filter"}:
                raise OpenRouterUnavailable("OpenRouter incomplete/filtered response")
            content = choice.get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip():
                raise OpenRouterUnavailable("OpenRouter empty/malformed text")
            result = validator(content.strip())
            ia_sessao.lembrar_texto(label)
            return result
        except Exception as exc:
            errors.append(str(exc) if isinstance(exc, OpenRouterUnavailable) else type(exc).__name__)
            if time.monotonic() < _cooldown_until:
                break  # Never try the same provider again after 429 in this request.
    raise OpenRouterUnavailable("OpenRouter unavailable: " + "; ".join(errors))


def gerar_texto_livre(prompt: str, max_tokens: int = 128) -> str:
    return _text_chain(prompt, lambda text: text, False, max_tokens)


def gerar_json_livre(prompt: str, schema):
    def parse(text):
        from app.gemini_client import _extrair_json
        return schema.model_validate(json.loads(_extrair_json(text)))
    request = prompt + "\nReturn ONLY valid JSON matching this schema:\n" + json.dumps(schema.model_json_schema())
    return _text_chain(request, parse, True, 4096)


def gerar_png_openrouter(prompt: str) -> bytes:
    _check_ready()
    if not OPENROUTER_IMAGE_MODELS:
        raise OpenRouterUnavailable("OpenRouter no verified free image model configured")
    errors = []
    for model in OPENROUTER_IMAGE_MODELS:
        try:
            payload = _attempt(model, prompt, image=True)
            images = payload.get("data") or []
            encoded = images[0].get("b64_json") if images else None
            if not isinstance(encoded, str) or not encoded:
                raise OpenRouterUnavailable("OpenRouter empty image")
            raw = base64.b64decode(encoded, validate=True)
            if not raw or len(raw) > _MAX_IMAGE_BYTES:
                raise OpenRouterUnavailable("OpenRouter empty/oversized image")
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                out = io.BytesIO()
                image.convert("RGBA" if "A" in image.getbands() else "RGB").save(out, "PNG")
                return out.getvalue()
        except Exception as exc:
            errors.append(str(exc) if isinstance(exc, OpenRouterUnavailable) else type(exc).__name__)
            if time.monotonic() < _cooldown_until:
                break
    raise OpenRouterUnavailable("OpenRouter image unavailable: " + "; ".join(errors))
