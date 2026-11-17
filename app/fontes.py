"""Fontes OFL embutidas (assets/fontes) → @font-face com data URI (Playwright offline)."""

from __future__ import annotations

import base64
from functools import lru_cache

from app.config import ROOT_DIR

FONTS_DIR = ROOT_DIR / "assets" / "fonts"

# (família CSS, arquivo, peso CSS)
FONTES: tuple[tuple[str, str, str], ...] = (
    ("Anton", "Anton-Regular.ttf", "400"),
    ("Bebas Neue", "BebasNeue-Regular.ttf", "400"),
    ("Montserrat", "Montserrat-Variable.ttf", "100 900"),
)


def fontes_faltando() -> list[str]:
    return [arq for _, arq, _ in FONTES if not (FONTS_DIR / arq).is_file()]


@lru_cache(maxsize=1)
def font_face_css() -> str:
    blocos: list[str] = []
    for familia, arquivo, peso in FONTES:
        path = FONTS_DIR / arquivo
        if not path.is_file():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        blocos.append(
            "@font-face{"
            f"font-family:'{familia}';"
            f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
            f"font-weight:{peso};font-style:normal;font-display:block;"
            "}"
        )
    return "\n".join(blocos)
