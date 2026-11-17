"""Revisão automática do criativo (Fase 2, item 2).

Duas camadas, nesta ordem:

1. **Pré-checagem determinística (grátis, local):** no próprio Playwright mede
   texto cortado/estourado no DOM, texto fora da zona segura (Stories/Reels) e o
   contraste WCAG de cada trecho de texto sobre o pedaço de fundo atrás dele.
2. **Revisão por IA de visão (free tier):** Gemini Flash (AI Studio, grátis) e,
   como reserva, GLM-4.6V-Flash (Z.ai, grátis). Devolve notas 0–10.

Se a nota final ficar abaixo do limiar (padrão 7), o pipeline gera outro fundo
(próximo provedor/seed) até N vezes (padrão 2), entrega a melhor tentativa e
marca `precisa_revisao`. Respeita cooldown de 429 por provedor (persistido em
.cache) e um prazo total. Nada aqui imprime chaves.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import httpx
from pydantic import BaseModel, Field, field_validator

from app.config import ROOT_DIR

CRITERIOS = ("legibilidade", "contraste", "texto_cortado", "fundo_qualidade", "artefatos_ia", "rostos_maos")

LIMIAR_PADRAO = float(os.getenv("REVISAO_LIMIAR", "7"))
TENTATIVAS_PADRAO = int(os.getenv("REVISAO_TENTATIVAS", "2"))
PRAZO_PADRAO = float(os.getenv("REVISAO_PRAZO", "480"))
TIMEOUT_VISAO = float(os.getenv("REVISAO_TIMEOUT", "35"))  # por modelo/provedor
GEMINI_MODELOS_VISAO = tuple(
    m.strip() for m in os.getenv("REVISAO_GEMINI_MODELS", "gemini-flash-latest,gemini-flash-lite-latest").split(",")
    if m.strip()
)
ZAI_API_KEY = os.getenv("ZAI_API_KEY", "")
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4").rstrip("/")
ZAI_MODELO_VISAO = os.getenv("REVISAO_ZAI_MODEL", "glm-4.6v-flash")

CACHE_COOLDOWN = ROOT_DIR / ".cache" / "revisao_cooldown.json"
COOLDOWN_429_PADRAO = 120.0


class VisaoIndisponivel(Exception):
    """Provedor de visão fora (sem chave, cooldown, 429, 5xx, timeout). Mensagem sem segredos."""


class NotasIA(BaseModel):
    """Contrato JSON que a IA de visão devolve (10 = perfeito, 0 = inaceitável)."""

    legibilidade: float = Field(..., ge=0, le=10)
    contraste: float = Field(..., ge=0, le=10)
    texto_cortado: float = Field(..., ge=0, le=10, description="10 = nenhum texto cortado/estourado")
    fundo_qualidade: float = Field(..., ge=0, le=10, description="10 = fundo nítido e bonito")
    artefatos_ia: float = Field(..., ge=0, le=10, description="10 = sem letras falsas/artefatos no fundo")
    rostos_maos: float = Field(..., ge=0, le=10, description="10 = sem pessoas ou todas naturais")
    problemas: list[str] = Field(default_factory=list)
    resumo: str = ""

    @field_validator("problemas", mode="before")
    @classmethod
    def _lista(cls, v):
        if isinstance(v, str):
            return [v] if v.strip() else []
        return [str(x) for x in (v or [])][:8]

    def nota(self) -> float:
        valores = [getattr(self, c) for c in CRITERIOS]
        media = sum(valores) / len(valores)
        # Um critério muito ruim derruba a nota (um texto cortado não é "média 8").
        return round(min(media, min(valores) + 2.5), 2)


@dataclass
class Tentativa:
    numero: int
    png: str
    fundo: str | None
    provedor_fundo: str
    precheck: dict
    ia: dict | None
    provedor_ia: str
    nota: float
    aprovado: bool
    erro_ia: str = ""
    escurecido: bool = False
    segundos: float = 0.0


@dataclass
class ResultadoRevisao:
    melhor: Tentativa | None
    tentativas: list[Tentativa] = field(default_factory=list)
    limiar: float = LIMIAR_PADRAO
    revisao_ia: bool = True
    motivo_parada: str = ""

    @property
    def precisa_revisao(self) -> bool:
        return self.melhor is None or not self.melhor.aprovado

    def to_dict(self) -> dict:
        return {
            "limiar": self.limiar,
            "revisao_ia": self.revisao_ia,
            "nota_final": self.melhor.nota if self.melhor else None,
            "aprovado": bool(self.melhor and self.melhor.aprovado),
            "precisa_revisao": self.precisa_revisao,
            "melhor_tentativa": self.melhor.numero if self.melhor else None,
            "motivo_parada": self.motivo_parada,
            "tentativas": [asdict(t) for t in self.tentativas],
        }


# ---------------------------------------------------------------- pré-checagem (determinística)

JS_COLETAR = r"""
(safe) => {
  const W = window.innerWidth, H = window.innerHeight;
  const textos = [], estouros = [], zona = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const clipa = (el) => { const cs = getComputedStyle(el);
    return ['hidden','clip','scroll','auto'].includes(cs.overflowX) || ['hidden','clip','scroll','auto'].includes(cs.overflowY); };
  while (walker.nextNode()) {
    const t = walker.currentNode;
    const txt = (t.textContent || '').trim();
    if (!txt) continue;
    const el = t.parentElement;
    if (!el || el.closest('script,style,[data-revisao-ignorar]')) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    const range = document.createRange(); range.selectNodeContents(t);
    const rs = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
    if (!rs.length) continue;
    const box = { x: Math.min(...rs.map(r => r.left)), y: Math.min(...rs.map(r => r.top)),
                  r: Math.max(...rs.map(r => r.right)), b: Math.max(...rs.map(r => r.bottom)) };
    const nome = (el.className && typeof el.className === 'string' ? el.className.split(' ')[0] : el.tagName.toLowerCase())
                 || el.tagName.toLowerCase();
    const peso = parseInt(cs.fontWeight) || 400;
    textos.push({ texto: txt.slice(0, 60), classe: nome, x: box.x, y: box.y, w: box.r - box.x, h: box.b - box.y,
                  cor: cs.color, fonte_px: parseFloat(cs.fontSize), peso, linhas: rs });
    // 1) fora do canvas
    let cortado = box.x < -1 || box.y < -1 || box.r > W + 1 || box.b > H + 1;
    // 2) cortado por um ancestral com overflow (line-clamp, max-height, caixas)
    let anc = el;
    while (!cortado && anc && anc !== document.body) {
      if (clipa(anc)) {
        const a = anc.getBoundingClientRect();
        for (const r of rs) {
          if (r.left < a.left - 2 || r.right > a.right + 2 || r.top < a.top - 2 || r.bottom > a.bottom + 2) { cortado = true; break; }
        }
      }
      anc = anc.parentElement;
    }
    if (cortado) estouros.push({ texto: txt.slice(0, 60), classe: nome });
    if (safe && !el.closest('[data-zona-livre]')) {
      if (box.y < safe.topo - 1 || box.b > H - safe.base + 1) zona.push({ texto: txt.slice(0, 60), classe: nome,
        topo: Math.round(box.y), base: Math.round(box.b) });
    }
  }
  return { textos, estouros, zona };
}
"""

CSS_SO_FUNDO = (
    "*{color:transparent!important;text-shadow:none!important;-webkit-text-stroke:0!important;"
    "caret-color:transparent!important}svg{visibility:hidden!important}"
)


def _parse_cor(css: str) -> tuple[float, float, float]:
    import re

    nums = [float(x) for x in re.findall(r"[\d.]+", css or "")][:3]
    return tuple(nums) if len(nums) == 3 else (255.0, 255.0, 255.0)  # type: ignore[return-value]


def _lum_rgb(r: float, g: float, b: float) -> float:
    def lin(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def razao_contraste(l1: float, l2: float) -> float:
    claro, escuro = max(l1, l2), min(l1, l2)
    return round((claro + 0.05) / (escuro + 0.05), 2)


def _mapa_luminancia(png_bytes: bytes):
    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as im:
        arr = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
    lin = np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def contraste_textos(textos: list[dict], fundo_png: bytes) -> list[dict]:
    """Contraste WCAG de cada texto contra o pior caso do fundo atrás dele (p90/p10)."""
    import numpy as np

    lum = _mapa_luminancia(fundo_png)
    alt, larg = lum.shape
    out: list[dict] = []
    for t in textos:
        x0, y0 = max(0, int(t["x"])), max(0, int(t["y"]))
        x1, y1 = min(larg, int(t["x"] + t["w"]) + 1), min(alt, int(t["y"] + t["h"]) + 1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        reg = lum[y0:y1, x0:x1]
        lt = _lum_rgb(*_parse_cor(t["cor"]))
        mediana = float(np.median(reg))
        pior = float(np.percentile(reg, 90 if lt >= mediana else 10))
        grande = t["fonte_px"] >= 24 or (t["fonte_px"] >= 18.66 and t["peso"] >= 700)
        minimo = 3.0 if grande else 4.5
        ratio = razao_contraste(lt, pior)
        out.append({"texto": t["texto"], "classe": t["classe"], "ratio": ratio, "minimo": minimo,
                    "ok": ratio >= minimo})
    return out


def resumir_precheck(coleta: dict, contraste: list[dict]) -> dict:
    falhas_c = [c for c in contraste if not c["ok"]]
    estouros = coleta.get("estouros", [])
    zona = coleta.get("zona", [])
    nota = 10.0 - 1.5 * len(falhas_c) - 3.0 * len(estouros) - 2.0 * len(zona)
    return {
        "ok": not falhas_c and not estouros and not zona,
        "nota": round(max(0.0, nota), 2),
        "contraste_min": min((c["ratio"] for c in contraste), default=None),
        "contraste_falhas": falhas_c,
        "contraste": contraste,
        "estouros": estouros,
        "zona_segura": zona,
        "textos": len(coleta.get("textos", [])),
    }


def precheck_pagina(page, largura: int, altura: int, safe: dict | None = None) -> dict:
    """Roda na página Playwright já renderizada (antes de fechar o browser)."""
    coleta = page.evaluate(JS_COLETAR, safe)
    page.add_style_tag(content=CSS_SO_FUNDO)
    fundo = page.screenshot(type="png", clip={"x": 0, "y": 0, "width": largura, "height": altura})
    return resumir_precheck(coleta, contraste_textos(coleta["textos"], fundo))


# ---------------------------------------------------------------- cooldown 429 (persistido)

def _ler_cooldowns() -> dict[str, float]:
    try:
        return {k: float(v) for k, v in json.loads(CACHE_COOLDOWN.read_text(encoding="utf-8")).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def em_cooldown(provedor: str) -> float:
    """Segundos restantes de cooldown (0 = livre)."""
    return max(0.0, _ler_cooldowns().get(provedor, 0.0) - time.time())


def marcar_cooldown(provedor: str, segundos: float) -> None:
    dados = {k: v for k, v in _ler_cooldowns().items() if v > time.time()}
    dados[provedor] = time.time() + max(1.0, segundos)
    try:
        CACHE_COOLDOWN.parent.mkdir(parents=True, exist_ok=True)
        CACHE_COOLDOWN.write_text(json.dumps(dados), encoding="utf-8")
    except OSError:
        pass


def _retry_after(valor: str | None) -> float:
    try:
        return max(1.0, float(valor))
    except (TypeError, ValueError):
        return COOLDOWN_429_PADRAO


# ---------------------------------------------------------------- IA de visão

PROMPT_VISAO = """Você é diretor de arte sênior revisando um criativo de Instagram ANTES de publicar.
A tipografia sobreposta (título, rótulos, botões, selo, @) é HTML intencional e está correta como texto;
avalie se ela está LEGÍVEL, com CONTRASTE e sem CORTES. Já letras/palavras que aparecem DENTRO da foto
de fundo (telas, placas, livros, logos inventados) são artefatos da IA e devem baixar `artefatos_ia`.
Seja exigente como uma big tech: em dúvida, nota menor.

Dê notas de 0 a 10 (10 = perfeito) e responda SOMENTE este JSON:
{"legibilidade":n,"contraste":n,"texto_cortado":n,"fundo_qualidade":n,"artefatos_ia":n,"rostos_maos":n,
 "problemas":["frase curta"],"resumo":"1 frase"}

- legibilidade: dá para ler tudo em 1 segundo no celular?
- contraste: texto destaca do fundo em todos os pontos?
- texto_cortado: 10 = nada cortado, encostado na borda ou sobreposto.
- fundo_qualidade: fundo nítido, bem composto, sem borrão/ruído/baixa resolução.
- artefatos_ia: 10 = fundo sem letras falsas, logos inventados, objetos deformados.
- rostos_maos: 10 = sem pessoas, ou rostos/mãos naturais (dedos certos, olhos simétricos).
"""


def _imagem_para_envio(png: Path, largura_max: int = 768) -> bytes:
    from PIL import Image

    with Image.open(png) as im:
        im = im.convert("RGB")
        if im.width > largura_max:
            im = im.resize((largura_max, round(im.height * largura_max / im.width)))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=88)
        return out.getvalue()


def _extrair_json(texto: str) -> dict:
    import re

    t = (texto or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("resposta sem JSON")
    return json.loads(t[a : b + 1])


def _cliente_gemini_visao(timeout: float):
    """Cliente próprio da revisão: sem re-tentativas do SDK (o 503 do Gemini re-tentava por minutos)
    e com timeout curto. TLS segue `GEMINI_SSL_VERIFY` (padrão verificado)."""
    import ssl

    from google import genai
    from google.genai import types

    from app.config import GEMINI_API_KEY, GEMINI_SSL_VERIFY

    http = httpx.Client(verify=ssl.create_default_context() if GEMINI_SSL_VERIFY else False, timeout=timeout)
    opcoes = types.HttpOptions(timeout=int(timeout * 1000), httpx_client=http)
    if hasattr(types, "HttpRetryOptions"):
        opcoes.retry_options = types.HttpRetryOptions(attempts=1)
    return genai.Client(api_key=GEMINI_API_KEY, http_options=opcoes)


def _revisar_gemini(img: bytes, prompt: str, timeout: float) -> tuple[NotasIA, str]:
    from app import gemini_client
    from app.config import GEMINI_API_KEY

    if not GEMINI_API_KEY:
        raise VisaoIndisponivel("gemini: sem chave")
    from google.genai import types

    ultimo = ""
    por_modelo = max(8.0, timeout / max(1, len(GEMINI_MODELOS_VISAO)))
    inicio = time.monotonic()
    for modelo in GEMINI_MODELOS_VISAO:
        resta = timeout - (time.monotonic() - inicio)
        if resta < 5:
            break
        orcamento = min(por_modelo, resta) if modelo != GEMINI_MODELOS_VISAO[-1] else resta

        def _uma(img_, prompt_, t_, modelo=modelo):
            resp = _cliente_gemini_visao(t_).models.generate_content(
                model=modelo,
                contents=[types.Part.from_bytes(data=img_, mime_type="image/jpeg"), prompt_],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
            )
            return NotasIA.model_validate(_extrair_json(resp.text or ""))

        _uma.__name__ = f"gemini/{modelo}"
        try:
            return _com_prazo(_uma, img, prompt, orcamento), f"gemini/{modelo}"
        except VisaoIndisponivel as exc:
            causa = exc.__cause__
            status = gemini_client._status_api(causa) if causa is not None else None
            if status == 429:
                marcar_cooldown("gemini", COOLDOWN_429_PADRAO)
                raise VisaoIndisponivel("gemini: 429 (cooldown)") from exc
            if isinstance(causa, (ValueError, json.JSONDecodeError)):
                ultimo = f"gemini/{modelo}: JSON inválido"
            else:
                ultimo = f"gemini/{modelo}: {status or exc}"
            continue
    raise VisaoIndisponivel(ultimo or "gemini: sem modelo")


def _revisar_zai(img: bytes, prompt: str, timeout: float) -> tuple[NotasIA, str]:
    if not ZAI_API_KEY:
        raise VisaoIndisponivel("zai: sem chave (ZAI_API_KEY)")
    b64 = base64.b64encode(img).decode("ascii")
    payload = {
        "model": ZAI_MODELO_VISAO,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]}],
    }
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as cli:
            r = cli.post(ZAI_BASE_URL + "/chat/completions", json=payload,
                         headers={"Authorization": "Bearer " + ZAI_API_KEY})
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise VisaoIndisponivel(f"zai: {type(exc).__name__}") from exc
    if r.status_code == 429:
        marcar_cooldown("zai", _retry_after(r.headers.get("retry-after")))
        raise VisaoIndisponivel("zai: 429 (cooldown)")
    if not 200 <= r.status_code < 300:
        raise VisaoIndisponivel(f"zai: HTTP {r.status_code}")
    try:
        conteudo = r.json()["choices"][0]["message"]["content"]
        if isinstance(conteudo, list):
            conteudo = "".join(p.get("text", "") for p in conteudo if isinstance(p, dict))
        return NotasIA.model_validate(_extrair_json(conteudo)), f"zai/{ZAI_MODELO_VISAO}"
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise VisaoIndisponivel("zai: JSON inválido") from exc


PROVEDORES_VISAO: list[tuple[str, Callable[[bytes, str, float], tuple[NotasIA, str]]]] = [
    ("gemini", _revisar_gemini),
    ("zai", _revisar_zai),
]


def _com_prazo(fn, img: bytes, prompt: str, timeout: float):
    """Prazo de relógio de verdade: o SDK do Gemini pode ficar re-tentando 503 por minutos.

    Roda numa thread daemon; se estourar, seguimos para o próximo provedor (a thread morre com o processo).
    """
    import queue
    import threading

    fila: queue.Queue = queue.Queue(maxsize=1)

    def alvo():
        try:
            fila.put(("ok", fn(img, prompt, timeout)))
        except BaseException as exc:  # noqa: BLE001
            fila.put(("erro", exc))

    threading.Thread(target=alvo, daemon=True, name="revisao-visao").start()
    try:
        tipo, valor = fila.get(timeout=timeout + 2)
    except queue.Empty as exc:
        raise VisaoIndisponivel(f"{getattr(fn, '__name__', 'visao')}: timeout {int(timeout)}s") from exc
    if tipo == "erro":
        if isinstance(valor, VisaoIndisponivel):
            raise valor
        raise VisaoIndisponivel(f"{type(valor).__name__}") from valor
    return valor


def revisar_png_ia(png: Path, *, prazo_s: float = 90.0, contexto: str = "") -> tuple[NotasIA | None, str, str]:
    """Pergunta às IAs de visão grátis, na ordem. Retorna (notas|None, provedor, erro)."""
    inicio = time.monotonic()
    img = _imagem_para_envio(png)
    prompt = PROMPT_VISAO + (f"\nContexto do criativo: {contexto}\n" if contexto else "")
    erros: list[str] = []
    for nome, fn in PROVEDORES_VISAO:
        resta = prazo_s - (time.monotonic() - inicio)
        if resta < 10:
            erros.append("prazo esgotado")
            break
        cd = em_cooldown(nome)
        if cd > 0:
            erros.append(f"{nome}: cooldown {int(cd)}s")
            continue
        try:
            orcamento = TIMEOUT_VISAO * (len(GEMINI_MODELOS_VISAO) if nome == "gemini" else 1)
            notas, provedor = _com_prazo(fn, img, prompt, min(orcamento, resta))
            return notas, provedor, ""
        except VisaoIndisponivel as exc:
            erros.append(str(exc))
    return None, "none", " | ".join(erros) or "nenhum provedor de visão"


def nota_final(precheck: dict, ia: NotasIA | None) -> float:
    if ia is None:
        return float(precheck.get("nota", 0.0))
    nota = ia.nota()
    if not precheck.get("ok", True):
        nota = min(nota, float(precheck.get("nota", 0.0)))
    return round(nota, 2)


# ---------------------------------------------------------------- ciclo gerar → revisar → refazer

GerarFundo = Callable[[int, list[str], Path], tuple[Path | None, str]]
Renderizar = Callable[..., tuple[Path, dict]]  # (fundo, destino, *, escurecer: bool) -> (png, precheck)


def ciclo_revisao(
    *,
    pasta: Path,
    renderizar: Renderizar,
    gerar_fundo: GerarFundo | None = None,
    fundo_fixo: Path | None = None,
    limiar: float = LIMIAR_PADRAO,
    tentativas_extra: int = TENTATIVAS_PADRAO,
    prazo_s: float = PRAZO_PADRAO,
    revisao_ia: bool = True,
    contexto: str = "",
    revisor: Callable[..., tuple[NotasIA | None, str, str]] | None = None,
    log: Callable[[str], None] = print,
) -> ResultadoRevisao:
    """Renderiza, revisa e — se a nota < limiar e houver como trocar o fundo — refaz.

    `gerar_fundo(numero, provedores_ja_usados, pasta_tentativa)` → (fundo|None, provedor).
    `renderizar(fundo, destino_png, escurecer=bool)` → (png, precheck).

    Estratégia de refação: se a tentativa anterior falhou em contraste, a próxima escurece o véu;
    se a IA aprovou o fundo (qualidade e artefatos ≥ 7) e o problema era só contraste, reaproveita o
    mesmo fundo (zero cota de imagem); senão pede outro fundo ao próximo provedor/seed.
    """
    revisor = revisor or revisar_png_ia
    inicio = time.monotonic()
    res = ResultadoRevisao(melhor=None, limiar=limiar, revisao_ia=revisao_ia)
    usados: list[str] = []
    max_tent = 1 + (max(0, tentativas_extra) if (gerar_fundo and revisao_ia) else 0)

    anterior: Tentativa | None = None
    for n in range(1, max_tent + 1):
        t0 = time.monotonic()
        dir_t = pasta / "tentativas" / f"t{n}"
        dir_t.mkdir(parents=True, exist_ok=True)
        provedor_fundo = "fixo" if fundo_fixo else "nenhum"
        fundo = fundo_fixo
        escurecer = bool(anterior and anterior.precheck.get("contraste_falhas"))
        reaproveitar = bool(
            anterior and escurecer and anterior.ia and anterior.fundo
            and anterior.ia.get("fundo_qualidade", 0) >= 7 and anterior.ia.get("artefatos_ia", 0) >= 7
        )
        if reaproveitar:
            fundo, provedor_fundo = Path(anterior.fundo), anterior.provedor_fundo
        elif gerar_fundo is not None:
            fundo, provedor_fundo = gerar_fundo(n, list(usados), dir_t)
            if provedor_fundo and provedor_fundo not in ("none", "nenhum"):
                usados.append(provedor_fundo)
        png, pre = renderizar(fundo, dir_t / "post.png", escurecer=escurecer)
        notas, prov_ia, erro_ia = (None, "desligada", "")
        if revisao_ia:
            resta = prazo_s - (time.monotonic() - inicio)
            if resta >= 10:
                notas, prov_ia, erro_ia = revisor(png, prazo_s=min(90.0, resta), contexto=contexto)
            else:
                prov_ia, erro_ia = "none", "prazo total esgotado"
        nota = nota_final(pre, notas)
        aprovado = nota >= limiar and bool(pre.get("ok", True)) and (notas is not None or not revisao_ia)
        t = Tentativa(numero=n, png=str(png), fundo=str(fundo) if fundo else None,
                      provedor_fundo=provedor_fundo, precheck=pre,
                      ia=notas.model_dump() if notas else None, provedor_ia=prov_ia,
                      nota=nota, aprovado=aprovado, erro_ia=erro_ia, escurecido=escurecer,
                      segundos=round(time.monotonic() - t0, 1))
        res.tentativas.append(t)
        anterior = t
        status = "aprovado" if aprovado else ("sem nota da IA" if revisao_ia and notas is None else "abaixo do limiar")
        log(f"  revisão t{n}: nota {nota:.1f}/10 ({status}; fundo={provedor_fundo}"
            + ("; véu reforçado" if escurecer else "") + f"; ia={prov_ia}"
            + (f"; {erro_ia[:90]}" if erro_ia else "") + ")")
        if res.melhor is None or t.nota > res.melhor.nota or (t.aprovado and not res.melhor.aprovado):
            res.melhor = t
        if aprovado:
            res.motivo_parada = "aprovado"
            break
        if not revisao_ia:
            res.motivo_parada = "revisão IA desligada"
            break
        if notas is None:
            res.motivo_parada = "IA de visão indisponível"
            break
        if time.monotonic() - inicio >= prazo_s:
            res.motivo_parada = "prazo total esgotado"
            break
    else:
        res.motivo_parada = res.motivo_parada or ("tentativas esgotadas" if max_tent > 1 else "sem como trocar o fundo")
    return res


def promover_melhor(res: ResultadoRevisao, destino_png: Path) -> Path:
    """Copia a melhor tentativa para `destino_png` (+ fundo.* ao lado) e grava revisao.json."""
    pasta = destino_png.parent
    if res.melhor is not None:
        shutil.copyfile(res.melhor.png, destino_png)
        if res.melhor.fundo and Path(res.melhor.fundo).is_file():
            f = Path(res.melhor.fundo)
            if f.parent != pasta:
                alvo = pasta / f"fundo{f.suffix.lower()}"
                shutil.copyfile(f, alvo)
                if f.with_suffix(".json").is_file():
                    shutil.copyfile(f.with_suffix(".json"), alvo.with_suffix(".json"))
    (pasta / f"{destino_png.stem}.revisao.json").write_text(
        json.dumps(res.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return destino_png
