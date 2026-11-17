"""Cliente do FreeLLMAPI-criativos em 127.0.0.1:3003. Sem impressão de chaves."""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from pydantic import BaseModel

from app import ia_sessao
from app.config import (
    FREELLMAPI_API_KEY,
    FREELLMAPI_BASE_URL,
    FREELLMAPI_CONNECT_TIMEOUT,
    FREELLMAPI_MODEL,
    FREELLMAPI_TIMEOUT,
)

_COOLDOWN_SECONDS = 120.0
_cooldown_until = 0.0
_T = BaseModel


class FreeLLMAPIUnavailable(Exception):
    """Diagnósticos só com status/tipo/modelo, nunca corpos remotos ou chaves."""


def disponivel() -> bool:
    return bool(FREELLMAPI_API_KEY and FREELLMAPI_BASE_URL)


def modelos_texto() -> list[str]:
    if not disponivel():
        return []
    return ia_sessao.fila_texto(["freellmapi/" + (FREELLMAPI_MODEL or "auto")])


def _retry_after(value: str | None) -> float:
    try:
        return max(1.0, float(value))
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value or "")
            return max(1.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return _COOLDOWN_SECONDS


def _set_cooldown(seconds: float | None = None) -> None:
    global _cooldown_until
    _cooldown_until = time.monotonic() + (seconds if seconds is not None else _COOLDOWN_SECONDS)


def _check_ready() -> None:
    if not disponivel():
        raise FreeLLMAPIUnavailable("FreeLLMAPI credentials missing")
    if time.monotonic() < _cooldown_until:
        raise FreeLLMAPIUnavailable("FreeLLMAPI rate-limit cooldown")


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=float(FREELLMAPI_CONNECT_TIMEOUT),
        read=float(FREELLMAPI_TIMEOUT),
        write=30.0,
        pool=5.0,
    )


def _base() -> str:
    return FREELLMAPI_BASE_URL.rstrip("/")


def ensure_relay() -> bool:
    """Sobe o relay Windows 127.0.0.1:3003 se a porta estiver fechada. No-op no WSL."""
    if sys.platform != "win32":
        return False
    host, port = _endpoint()
    if _port_open(host, port, 0.4):
        return False
    starter = Path.home() / "freellmapi-criativos-relay" / "start-relay.cmd"
    if not starter.is_file():
        return False
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", str(starter)],
            cwd=str(starter.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
        )
    except OSError:
        return False
    for _ in range(20):
        time.sleep(0.25)
        if _port_open(host, port, 0.4):
            return True
    return False


def _endpoint() -> tuple[str, int]:
    from urllib.parse import urlparse
    parsed = urlparse(_base() if "://" in _base() else "http://" + _base())
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


def _port_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _request(prompt: str, max_tokens: int, json_mode: bool) -> dict:
    _check_ready()
    payload = {
        "model": FREELLMAPI_MODEL or "auto",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": "Bearer " + FREELLMAPI_API_KEY, "Content-Type": "application/json"}
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=_timeout(), follow_redirects=False) as client:
                response = client.post(_base() + "/chat/completions", headers=headers, json=payload)
            if response.status_code == 429:
                _set_cooldown(_retry_after(response.headers.get("retry-after")))
                raise FreeLLMAPIUnavailable("FreeLLMAPI HTTP 429")
            if not 200 <= response.status_code < 300:
                raise FreeLLMAPIUnavailable(f"FreeLLMAPI HTTP {response.status_code}")
            data = response.json()
            if not isinstance(data, dict) or data.get("error"):
                if isinstance(data, dict) and isinstance(data.get("error"), dict):
                    if str(data["error"].get("code")) == "429":
                        _set_cooldown()
                        raise FreeLLMAPIUnavailable("FreeLLMAPI HTTP 429")
                raise FreeLLMAPIUnavailable("FreeLLMAPI response error")
            return data
        except FreeLLMAPIUnavailable:
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last_exc = exc
            if attempt == 0 and ensure_relay():
                continue
            raise FreeLLMAPIUnavailable("FreeLLMAPI connection failed") from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise FreeLLMAPIUnavailable("FreeLLMAPI timeout") from exc
        except Exception as exc:
            raise FreeLLMAPIUnavailable("FreeLLMAPI " + type(exc).__name__) from exc
    raise FreeLLMAPIUnavailable("FreeLLMAPI connection failed") from last_exc


def _extract_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    choice = choices[0] if choices else {}
    if choice.get("finish_reason") in {"error", "content_filter"}:
        raise FreeLLMAPIUnavailable("FreeLLMAPI incomplete/filtered response")
    content = (choice.get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    texto = (content or "").strip()
    if not texto:
        raise FreeLLMAPIUnavailable("FreeLLMAPI empty response")
    return texto


def _lembrar(payload: dict) -> None:
    model = payload.get("model") or (FREELLMAPI_MODEL or "auto")
    ia_sessao.lembrar_texto("freellmapi/" + str(model).removeprefix("freellmapi/"))


def gerar_texto_livre(prompt: str, max_tokens: int = 4096) -> str:
    payload = _request(prompt, max_tokens, json_mode=False)
    texto = _extract_text(payload)
    _lembrar(payload)
    return texto


def _extrair_json(texto: str) -> str:
    texto = texto.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", texto)
    if fence:
        return fence.group(1).strip()
    start = texto.find("{")
    end = texto.rfind("}")
    if start >= 0 and end > start:
        return texto[start : end + 1]
    return texto


def gerar_json_livre(prompt: str, schema: type[_T]) -> _T:
    payload = _request(prompt, 4096, json_mode=True)
    bruto = _extract_text(payload)
    try:
        dados = json.loads(_extrair_json(bruto))
        out = schema.model_validate(dados)
    except (json.JSONDecodeError, ValueError) as exc:
        raise FreeLLMAPIUnavailable("FreeLLMAPI response is not valid JSON") from exc
    _lembrar(payload)
    return out
