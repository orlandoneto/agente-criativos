"""Cliente Gemini (google-genai) com failover inteligente entre modelos."""

from __future__ import annotations

import json
import re
import ssl
import time
from enum import Enum
from typing import Callable, TypeVar

import httpx
from pydantic import BaseModel

from app import ia_sessao
from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_SSL_VERIFY, ROOT_DIR

T = TypeVar("T", bound=BaseModel)

_http_client: httpx.Client | None = None

TENTATIVAS_REDE = 2
# Último modelo vivo: em 503/cota insiste (não tem para quem trocar)
TENTATIVAS_ULTIMO = 5

CACHE_BLOQUEADOS = ROOT_DIR / ".cache" / "modelos_texto_bloqueados.txt"

# Confirmados 404 nesta conta / free (crescem em runtime + cache em disco)
MODELOS_TEXTO_BLOQUEADOS: set[str] = {
    "gemini-2.5-flash",
    "gemini-2.0-flash",  # 404 numa conta free (2026-11-05)
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
}

# Ordem: o que funciona no free primeiro
MODELOS_TEXTO_POOL = (
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
)


class ClasseErro(str, Enum):
    SOBRECARGA = "sobrecarga"
    COTA = "cota"
    MODELO = "modelo"
    AUTH = "auth"
    REDE = "rede"
    OUTRO = "outro"


def _carregar_bloqueados_disco() -> None:
    if not CACHE_BLOQUEADOS.is_file():
        return
    try:
        for ln in CACHE_BLOQUEADOS.read_text(encoding="utf-8").splitlines():
            nome = _nome_modelo(ln)
            if nome:
                MODELOS_TEXTO_BLOQUEADOS.add(nome)
    except OSError:
        pass


def _salvar_bloqueado_disco(modelo: str) -> None:
    nome = _nome_modelo(modelo)
    if not nome:
        return
    try:
        CACHE_BLOQUEADOS.parent.mkdir(parents=True, exist_ok=True)
        atuais: set[str] = set()
        if CACHE_BLOQUEADOS.is_file():
            atuais = {
                _nome_modelo(x)
                for x in CACHE_BLOQUEADOS.read_text(encoding="utf-8").splitlines()
                if x.strip()
            }
        if nome in atuais:
            return
        atuais.add(nome)
        CACHE_BLOQUEADOS.write_text("\n".join(sorted(atuais)) + "\n", encoding="utf-8")
    except OSError:
        pass


_carregar_bloqueados_disco()


def _client():
    global _http_client
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY ausente. Copie .env.example para .env e cole a chave do AI Studio."
        )
    from google import genai
    from google.genai import types

    if _http_client is None:
        _http_client = httpx.Client(
            verify=ssl.create_default_context() if GEMINI_SSL_VERIFY else False,
            timeout=90.0,
        )

    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(httpx_client=_http_client),
    )


def _nome_modelo(modelo: str) -> str:
    return (modelo or "").strip().removeprefix("models/")


def _modelo_bloqueado(modelo: str) -> bool:
    return _nome_modelo(modelo) in MODELOS_TEXTO_BLOQUEADOS


def _bloquear_modelo(modelo: str) -> None:
    nome = _nome_modelo(modelo)
    if not nome:
        return
    MODELOS_TEXTO_BLOQUEADOS.add(nome)
    _salvar_bloqueado_disco(nome)


def _modelos_texto() -> list[str]:
    """Preferido + pool vivo; sem 404; sticky da sessão na frente."""
    preferido = _nome_modelo(GEMINI_MODEL)
    if _modelo_bloqueado(preferido) or not preferido:
        preferido = next((m for m in MODELOS_TEXTO_POOL if not _modelo_bloqueado(m)), "gemini-flash-lite-latest")
    out: list[str] = []
    for m in (preferido, *MODELOS_TEXTO_POOL):
        nome = _nome_modelo(m)
        if not nome or _modelo_bloqueado(nome) or nome in out:
            continue
        out.append(nome)
    return ia_sessao.fila_texto(out)


def rotacao_texto() -> list[str]:
    """Fila viva de modelos de texto (para exibir ao cliente)."""
    from app.freellmapi_client import modelos_texto as modelos_freellmapi
    from app.openrouter_client import modelos_texto
    return ia_sessao.fila_texto(modelos_freellmapi() + modelos_texto() + _modelos_texto())


def rotacao_texto_planejada() -> list[str]:
    """Ordem canônica do pool (inclui bloqueados marcados)."""
    from app.freellmapi_client import modelos_texto as modelos_freellmapi
    from app.openrouter_client import modelos_texto
    from app.config import OPENROUTER_TEXT_MODELS
    configured = set(modelos_texto())
    return (
        modelos_freellmapi()
        + ["openrouter/" + m for m in OPENROUTER_TEXT_MODELS if "openrouter/" + m in configured]
        + list(MODELOS_TEXTO_POOL)
    )


def _status_api(exc: BaseException) -> int | None:
    for attr in ("code", "status_code", "status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    m = re.match(r"^\s*(\d{3})\b", str(exc))
    if m:
        return int(m.group(1))
    return None


def _classificar_erro(exc: BaseException) -> ClasseErro:
    status = _status_api(exc)
    texto = str(exc)
    low = texto.lower()

    if status in {401, 403} or "permission" in low or "api key" in low:
        return ClasseErro.AUTH
    if (
        status == 404
        or "not_found" in low
        or "not found" in low
        or "is not found" in low
        or "no longer available" in low
        or "not available to new users" in low
    ):
        return ClasseErro.MODELO
    if (
        status == 429
        or "RESOURCE_EXHAUSTED" in texto
        or '"code": 429' in texto
        or "'code': 429" in texto
    ):
        return ClasseErro.COTA
    if (
        status == 503
        or "UNAVAILABLE" in texto
        or "high demand" in low
        or '"code": 503' in texto
        or "'code': 503" in texto
    ):
        return ClasseErro.SOBRECARGA
    if (
        status in {408, 502, 504}
        or "timeout" in low
        or "timed out" in low
        or "connection" in low
        or isinstance(exc, (httpx.TimeoutException, httpx.TransportError))
    ):
        return ClasseErro.REDE
    return ClasseErro.OUTRO


def _eh_sobrecarga(exc: BaseException) -> bool:
    return _classificar_erro(exc) in {ClasseErro.SOBRECARGA, ClasseErro.COTA}


def _score_fallback(modelo: str, classe: ClasseErro) -> int:
    m = modelo.lower()
    s = 0
    if classe in {ClasseErro.SOBRECARGA, ClasseErro.COTA}:
        if "flash-lite-latest" in m:
            s -= 30  # o que tem funcionado nesta conta
        elif "lite" in m:
            s -= 20
        if "latest" in m and "lite" in m:
            s -= 5
    return s


def _reordenar_fila(fila: list[str], classe: ClasseErro) -> list[str]:
    return sorted(fila, key=lambda m: _score_fallback(m, classe))


def _esperar_retry(tentativa: int, classe: ClasseErro) -> None:
    if classe == ClasseErro.SOBRECARGA:
        segundos = min(1.5 * tentativa, 8.0)
    elif classe == ClasseErro.COTA:
        segundos = min(2.5 * tentativa, 10.0)
    else:
        segundos = min(1.2 * (2 ** (tentativa - 1)), 5.0)
    time.sleep(segundos)


def _avisar(msg: str) -> None:
    print(f"  ↻ {msg}")


def _mensagem_api(exc: BaseException) -> str:
    classe = _classificar_erro(exc)
    if classe == ClasseErro.AUTH:
        return "Chave Gemini inválida ou sem permissão. Confira GEMINI_API_KEY no .env."
    if classe == ClasseErro.MODELO:
        return (
            "Modelo Gemini indisponível (404). Use no .env: "
            "GEMINI_MODEL=gemini-flash-lite-latest"
        )
    if classe == ClasseErro.COTA:
        return (
            "Cota Gemini esgotada (429). Aguarde o reset da cota free "
            "ou GEMINI_MODEL=gemini-flash-lite-latest no .env."
        )
    if classe == ClasseErro.SOBRECARGA:
        return (
            "Gemini em alta demanda (503) — plano free saturado. "
            "Espere 1–2 min e rode `gerar` de novo (ou `gerar --ping`). "
            f"Modelo: {GEMINI_MODEL}."
        )
    if classe == ClasseErro.REDE:
        return "Falha de rede ao falar com o Gemini. Confira internet/VPN e tente de novo."
    curto = str(exc).split("\n", 1)[0]
    if len(curto) > 160:
        curto = curto[:157] + "…"
    return f"Falha na API Gemini: {curto}"


def _com_failover(executar: Callable[[str], T]) -> T:
    """
    Troca de IA com inteligência:
    - 404 → bloqueia modelo (memória + disco) e segue
    - 503/cota com outros na fila → troca
    - 503/cota no **último** modelo → insiste com backoff
    - sticky: o que funcionar gruda na corrida
    """
    fila = list(_modelos_texto())
    if not fila:
        raise RuntimeError(
            "Nenhum modelo Gemini disponível. Defina GEMINI_MODEL=gemini-flash-lite-latest no .env."
        )
    ultimo: BaseException | None = None
    tentativas_no_atual = 0

    while fila:
        modelo = fila[0]
        tentativas_no_atual += 1
        ultimo_da_fila = len(fila) == 1
        try:
            out = executar(modelo)
            anterior = ia_sessao.modelo_texto
            ia_sessao.lembrar_texto(modelo)
            if anterior != modelo:
                _avisar(f"ok em {modelo} — próximos jobs desta corrida seguem nele")
            return out
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
            classe = _classificar_erro(exc)

            if classe == ClasseErro.AUTH:
                raise RuntimeError(_mensagem_api(exc)) from exc

            if classe == ClasseErro.MODELO:
                _bloquear_modelo(modelo)
                _avisar(f"{modelo} (404/descontinuado) — bloqueado; próximo…")
                fila.pop(0)
                fila = [m for m in fila if not _modelo_bloqueado(m)]
                tentativas_no_atual = 0
                continue

            # Último modelo vivo: insiste em 503/cota/rede
            if ultimo_da_fila and classe in {
                ClasseErro.SOBRECARGA,
                ClasseErro.COTA,
                ClasseErro.REDE,
            }:
                if tentativas_no_atual < TENTATIVAS_ULTIMO:
                    _avisar(
                        f"{modelo} ({classe.value}) — único modelo vivo; "
                        f"tentativa {tentativas_no_atual}/{TENTATIVAS_ULTIMO}…"
                    )
                    _esperar_retry(tentativas_no_atual, classe)
                    continue
                break

            if classe == ClasseErro.REDE and tentativas_no_atual < TENTATIVAS_REDE:
                _avisar(
                    f"{modelo} rede instável (tentativa {tentativas_no_atual}/{TENTATIVAS_REDE})…"
                )
                _esperar_retry(tentativas_no_atual, classe)
                continue

            if classe == ClasseErro.OUTRO and not ultimo_da_fila:
                _avisar(f"{modelo} falhou ({classe.value}) → trocando de IA…")
                fila.pop(0)
                fila = _reordenar_fila(fila, classe)
                tentativas_no_atual = 0
                _esperar_retry(1, ClasseErro.REDE)
                continue

            # Há outros na fila → troca
            fila.pop(0)
            if not fila:
                break
            fila = _reordenar_fila(fila, classe)
            proximo = fila[0]
            motivo = {
                ClasseErro.SOBRECARGA: "alta demanda",
                ClasseErro.COTA: "cota",
                ClasseErro.REDE: "rede",
                ClasseErro.OUTRO: "erro",
            }.get(classe, classe.value)
            _avisar(f"{modelo} ({motivo}) → trocando para {proximo} e continuo")
            tentativas_no_atual = 0
            _esperar_retry(1, classe)

    raise RuntimeError(_mensagem_api(ultimo or RuntimeError("sem resposta")))


def _com_provedores(openrouter_fn, gemini_fn, freellmapi_fn=None):
    from app import freellmapi_client as fl
    from app import openrouter_client as router

    if freellmapi_fn and fl.disponivel():
        try:
            return freellmapi_fn()
        except fl.FreeLLMAPIUnavailable as exc:
            _avisar(f"FreeLLMAPI 3003 indisponível — caindo para provedores diretos ({exc})")

    if not router.OPENROUTER_API_KEY:
        return gemini_fn()
    sticky = ia_sessao.modelo_texto
    if sticky and not sticky.startswith("openrouter/") and not (sticky or "").startswith("freellmapi/"):
        try:
            return gemini_fn()
        except Exception as gemini_error:
            try:
                return openrouter_fn()
            except router.OpenRouterUnavailable:
                raise gemini_error
    try:
        return openrouter_fn()
    except router.OpenRouterUnavailable:
        return gemini_fn()


def ping() -> str:
    preferido = GEMINI_MODEL

    def _uma(modelo: str) -> str:
        client = _client()
        resp = client.models.generate_content(
            model=modelo,
            contents="Responda exatamente: PING_OK",
        )
        texto = (resp.text or "").strip()
        if modelo != preferido:
            return f"{texto}  (via {modelo})"
        return texto

    from app.freellmapi_client import gerar_texto_livre as gerar_texto_freellmapi
    from app.openrouter_client import gerar_texto_livre
    return _com_provedores(
        lambda: gerar_texto_livre("Responda exatamente: PING_OK", 128),
        lambda: _com_failover(_uma),
        lambda: gerar_texto_freellmapi("Responda exatamente: PING_OK", 128),
    )


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


def gerar_json(prompt: str, schema: type[T]) -> T:
    def _uma(modelo: str) -> T:
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
        )
        client = _client()
        resp = client.models.generate_content(
            model=modelo,
            contents=prompt,
            config=config,
        )
        bruto = resp.text or ""
        try:
            dados = json.loads(_extrair_json(bruto))
            return schema.model_validate(dados)
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Resposta do Gemini não é JSON válido: {exc}") from exc

    from app.freellmapi_client import gerar_json_livre as gerar_json_freellmapi
    from app.openrouter_client import gerar_json_livre
    return _com_provedores(
        lambda: gerar_json_livre(prompt, schema),
        lambda: _com_failover(_uma),
        lambda: gerar_json_freellmapi(prompt, schema),
    )


def corrigir_json(prompt_original: str, schema: type[T], erros: list[str], anterior: BaseModel) -> T:
    correcao = (
        f"{prompt_original}\n\n"
        "---\n"
        "A resposta anterior falhou na validação. Corrija e devolva JSON válido.\n"
        f"Erros:\n- " + "\n- ".join(erros) + "\n"
        f"JSON anterior:\n{anterior.model_dump_json(indent=2)}\n"
    )
    return gerar_json(correcao, schema)
