"""Post único Instagram (Fase 1): card de notícia e anúncio → HTML → PNG.

A IA de imagem só gera o FUNDO (sem texto). Toda tipografia é HTML/CSS com
fontes OFL embutidas — nítida, editável e sem letras tortas.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import TEMPLATES_DIR
from app.fontes import font_face_css
from app.icones import svg_inline
from app.renderer import _data_uri
from app.schemas import AdResult, NewsResult, SlideCarrossel, destaque_presente

FORMATOS: dict[str, tuple[int, int]] = {
    "4x5": (1080, 1350),  # feed retrato (recomendado)
    "1x1": (1080, 1080),  # feed quadrado (também serve no Facebook)
    "9x16": (1080, 1920),  # Stories / Reels (tela cheia)
    "capa-reels": (1080, 1920),  # capa de Reels: texto no miolo 3:4 que aparece no grid do perfil
    "carrossel": (1080, 1350),  # capa + N slides 4:5
}
ESTILOS = ("news", "ad")
# Zona segura (px sem texto-chave no topo/base) por formato; usada na pré-checagem.
# Stories/Reels: topo ~250 px (barra de perfil) e base ~340 px (legenda, botões, campo de resposta).
# Capa de Reels: o grid do perfil corta para 3:4 (1080x1440) no centro → 240 px em cima e embaixo.
SAFE_ZONES: dict[str, dict[str, int]] = {
    "9x16": {"topo": 250, "base": 340},
    "capa-reels": {"topo": 240, "base": 240},
}

CORES_DESTAQUE = {"amarelo": "#FFD60A", "vermelho": "#FF2D2D"}


@dataclass
class Marca:
    nome: str = "Marca"
    handle: str = ""
    destaque: str = "#FFD60A"
    fundo: str = "#0B0B0F"
    primaria: str = "#8B5CF6"
    texto: str = "#FFFFFF"
    tag: str = "#E10600"
    fonte_titulo: str = "Anton"
    fonte_corpo: str = "Montserrat"
    logo: Path | None = None
    cta_forma: str = "pilula"
    slug: str = ""

    def para_json(self) -> dict:
        d = dict(self.__dict__)
        d["logo"] = str(self.logo) if self.logo else None
        return d

    @classmethod
    def do_kit(cls, kit, handle: str | None = None) -> "Marca":
        return cls(nome=kit.nome, handle=normalizar_handle(handle or kit.handle), destaque=kit.cores.destaque,
                   fundo=kit.cores.fundo, primaria=kit.cores.primaria, texto=kit.cores.texto, tag=kit.cores.tag,
                   fonte_titulo=kit.fontes.titulo, fonte_corpo=kit.fontes.corpo, logo=kit.logo_path(),
                   cta_forma=kit.cta.forma, slug=kit.slug)


def _rgb(hexa: str) -> tuple[int, int, int]:
    h = hexa.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mistura(hexa: str, alvo: tuple[int, int, int], t: float) -> str:
    r, g, b = _rgb(hexa)
    return "#{:02X}{:02X}{:02X}".format(*(round(c + (a - c) * t) for c, a in zip((r, g, b), alvo)))


def cor_sobre(hexa: str) -> str:
    """Texto legível sobre a cor (escuro em cores claras, branco nas escuras)."""
    from app.revisao import _lum_rgb

    return "#1A1300" if _lum_rgb(*_rgb(hexa)) > 0.35 else "#FFFFFF"


def vars_marca(marca: Marca, cor_destaque: str | None = None) -> dict:
    """Variáveis de template derivadas do brand kit (cores, fontes, logo, CTA)."""
    hl = CORES_DESTAQUE.get(cor_destaque, cor_destaque) if cor_destaque else marca.destaque
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", hl or ""):
        hl = marca.destaque
    return {
        "cor_hl": hl,
        "hl1": _mistura(hl, (255, 255, 255), 0.45),
        "hl3": _mistura(hl, (0, 0, 0), 0.18),
        "on_hl": cor_sobre(hl),
        "cor_tag": marca.tag,
        "cor_texto": marca.texto,
        "fonte_titulo": marca.fonte_titulo,
        "fonte_corpo": marca.fonte_corpo,
        "logo_uri": _data_uri(marca.logo) if marca.logo else None,
        "cta_raio": "999px" if marca.cta_forma == "pilula" else "18px",
    }


def tamanho(formato: str) -> tuple[int, int]:
    try:
        return FORMATOS[formato]
    except KeyError as exc:
        raise ValueError(f"formato inválido: {formato!r} (use {', '.join(FORMATOS)})") from exc


def normalizar_handle(handle: str, nome: str = "") -> str:
    h = (handle or "").strip()
    if not h and nome:
        h = re.sub(r"[^a-z0-9_.]", "", nome.lower().replace(" ", ""))
    if not h:
        return ""
    return h if h.startswith("@") else f"@{h}"


def segmentos_destaque(titulo: str, destaques: list[str]) -> list[dict]:
    """Quebra o título em trechos {texto, hl}; hl=True nos destaques (palavra inteira, sem caixa)."""
    validos = [d.strip() for d in destaques if d and d.strip() and destaque_presente(titulo, d)]
    if not validos:
        return [{"texto": titulo, "hl": False}]
    validos.sort(key=len, reverse=True)
    padrao = re.compile(
        "|".join(r"(?<!\w)" + re.escape(d) + r"(?!\w)" for d in validos), re.IGNORECASE
    )
    out: list[dict] = []
    pos = 0
    for m in padrao.finditer(titulo):
        if m.start() > pos:
            out.append({"texto": titulo[pos:m.start()], "hl": False})
        out.append({"texto": m.group(0), "hl": True})
        pos = m.end()
    if pos < len(titulo):
        out.append({"texto": titulo[pos:], "hl": False})
    return out


def ler_atribuicao(fundo: Path | None) -> str:
    """Se o fundo veio de Pexels/Unsplash, o cena_XX.json ao lado tem o crédito."""
    if not fundo:
        return ""
    meta = fundo.with_suffix(".json")
    if not meta.is_file():
        return ""
    try:
        return str(json.loads(meta.read_text(encoding="utf-8")).get("atribuicao", ""))[:80]
    except (OSError, ValueError):
        return ""


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def html_news(
    card: NewsResult,
    *,
    formato: str = "4x5",
    fundo: Path | None = None,
    pb: bool = False,
    marca: Marca | None = None,
    cor_destaque: str | None = None,
    escurecer: bool = False,
) -> str:
    largura, altura = tamanho(formato)
    marca = marca or Marca()
    return _env().get_template("news_card.html").render(
        width=largura,
        height=altura,
        formato=formato,
        fontes_css=font_face_css(),
        fundo_uri=_data_uri(fundo),
        pb=pb,
        tag=card.tag.strip(),
        segmentos=segmentos_destaque(card.titulo.strip(), card.destaques),
        apoio=card.apoio.strip(),
        handle=marca.handle,
        nome=marca.nome,
        fundo_cor=marca.fundo,
        **vars_marca(marca, cor_destaque),
        safe=SAFE_ZONES.get(formato),
        arraste=formato == "carrossel",
        seta_svg=svg_inline("arrow-right", 30, 2.75),
        credito=ler_atribuicao(fundo),
        escurecer=escurecer,
    )


def html_ad(
    ad: AdResult,
    *,
    formato: str = "4x5",
    fundo: Path | None = None,
    mockup: Path | None = None,
    marca: Marca | None = None,
    escurecer: bool = False,
) -> str:
    largura, altura = tamanho(formato)
    marca = marca or Marca()
    features = [
        {"svg": svg_inline(f.icone, 34 if formato == "4x5" else 28), "texto": f.texto.strip(), "icone": f.icone}
        for f in ad.features
    ]
    return _env().get_template("ad_promo.html").render(
        width=largura,
        height=altura,
        formato=formato,
        fontes_css=font_face_css(),
        fundo_uri=_data_uri(fundo),
        mockup_uri=_data_uri(mockup),
        pill=ad.pill.strip(),
        partes=[{"texto": p.texto.strip(), "hl": p.destaque} for p in ad.headline_parts],
        badge=ad.badge.strip(),
        features=features,
        cta=ad.cta.strip(),
        seta_svg=svg_inline("arrow-right", 32 if formato == "1x1" else 40, 2.75),
        handle=marca.handle,
        nome=marca.nome,
        fundo_cor=marca.fundo,
        credito=ler_atribuicao(fundo),
        escurecer=escurecer,
        safe=SAFE_ZONES.get(formato),
        arraste=formato == "carrossel",
        **vars_marca(marca),
    )


def partes_destaque(texto: str) -> list[dict]:
    """`*amarelo* branco` → [{texto, hl}] (sem asteriscos = tudo branco)."""
    out = []
    for i, trecho in enumerate((texto or "").split("*")):
        t = " ".join(trecho.split())
        if t:
            out.append({"texto": t, "hl": i % 2 == 1})
    return out or [{"texto": texto, "hl": False}]


def html_slide(slide: SlideCarrossel, *, numero: int, total: int, estilo: str = "news",
               fundo: Path | None = None, marca: Marca | None = None, cta: str = "",
               cor_destaque: str | None = None) -> str:
    """Slide interno do carrossel (4:5) no estilo news ou ad, com o fundo da capa desfocado."""
    largura, altura = tamanho("carrossel")
    marca = marca or Marca()
    return _env().get_template("slide_carrossel.html").render(
        width=largura, height=altura, estilo=estilo, numero=numero, total=total,
        fontes_css=font_face_css(), fundo_uri=_data_uri(fundo), fundo_cor=marca.fundo,
        partes=partes_destaque(slide.titulo.strip()), texto=slide.texto.strip(),
        icone=slide.icone, icone_svg=svg_inline(slide.icone, 58, 2.25),
        handle=marca.handle, nome=marca.nome, cta=(cta or "").strip(), ultimo=numero == total,
        seta_svg=svg_inline("arrow-right", 30, 2.75),
        **vars_marca(marca, cor_destaque),
    )


def _renderizar(html: str, largura: int, altura: int, destino: Path, *, checar: bool,
                safe: dict | None) -> tuple[Path, dict]:
    from playwright.sync_api import sync_playwright

    destino.parent.mkdir(parents=True, exist_ok=True)
    pre: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": largura, "height": altura}, device_scale_factor=1)
            page.set_content(html, wait_until="load")
            page.wait_for_function("document.body.dataset.ready === '1'", timeout=15000)
            page.screenshot(path=str(destino), type="png", clip={"x": 0, "y": 0, "width": largura, "height": altura})
            if checar:
                from app.revisao import precheck_pagina

                pre = precheck_pagina(page, largura, altura, safe)
        finally:
            browser.close()
    return destino, pre


def render_html_png(html: str, largura: int, altura: int, destino: Path) -> Path:
    """Renderiza um HTML (com auto-ajuste JS do título) num PNG do tamanho exato do canvas."""
    return _renderizar(html, largura, altura, destino, checar=False, safe=None)[0]


def render_html_png_checado(html: str, largura: int, altura: int, destino: Path,
                            safe: dict | None = None) -> tuple[Path, dict]:
    """Igual a `render_html_png` + pré-checagem determinística (estouro, zona segura, contraste WCAG)."""
    return _renderizar(html, largura, altura, destino, checar=True, safe=safe)
