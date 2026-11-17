"""Renderiza slides HTML → PNG (abordagem A: cena + tipografia)."""

from __future__ import annotations

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.brand import BrandColors
from app.config import FEED_HEIGHT, FEED_WIDTH, TEMPLATES_DIR
from app.schemas import CarrosselResult


def _titulo_size(texto: str) -> int:
    n = len(texto)
    if n <= 36:
        return 68
    if n <= 60:
        return 56
    if n <= 90:
        return 46
    return 38


def _data_uri(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    raw = path.read_bytes()
    mime = "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif path.suffix.lower() == ".webp":
        mime = "image/webp"
    elif path.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def render_carrossel_pngs(
    result: CarrosselResult,
    brand: BrandColors,
    pasta: Path,
    cenas: list[Path | None] | None = None,
    selo: str = "Criativo",
    largura: int = FEED_WIDTH,
    altura: int = FEED_HEIGHT,
) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("carrossel_slide.html")
    total = len(result.slides)
    cenas = cenas or [None] * total

    from playwright.sync_api import sync_playwright

    paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": largura, "height": altura},
            device_scale_factor=1,
        )
        for i, slide in enumerate(result.slides, start=1):
            cena = cenas[i - 1] if i - 1 < len(cenas) else None
            html = template.render(
                width=largura,
                height=altura,
                fundo=brand.fundo,
                texto=brand.texto,
                destaque=brand.destaque,
                nome=brand.nome,
                selo=selo[:28],
                indice=i,
                total=total,
                titulo=slide.titulo.strip(),
                apoio=slide.apoio.strip(),
                titulo_size=_titulo_size(slide.titulo.strip()),
                cena_data_uri=_data_uri(cena),
            )
            page.set_content(html, wait_until="load")
            out = pasta / f"slide_{i:02d}.png"
            page.screenshot(path=str(out), type="png")
            paths.append(out)
        browser.close()
    return paths
