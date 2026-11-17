"""Ícones SVG inline (Lucide, licença ISC — assets/icons/lucide/LICENSE)."""

from __future__ import annotations

import re
from functools import lru_cache

from app.config import ROOT_DIR

ICONS_DIR = ROOT_DIR / "assets" / "icons" / "lucide"
ICONE_PADRAO = "check"

# Apelidos em PT-BR que a IA de texto costuma usar → nome Lucide
APELIDOS = {
    "raio": "zap", "rapido": "zap", "rápido": "zap", "velocidade": "zap",
    "escudo": "shield-check", "seguranca": "shield-check", "segurança": "shield-check",
    "relogio": "clock", "relógio": "clock", "tempo": "clock",
    "estrela": "star", "crescimento": "trending-up", "grafico": "trending-up",
    "pessoas": "users", "comunidade": "users", "presente": "gift", "bonus": "gift", "bônus": "gift",
    "foguete": "rocket", "coracao": "heart", "coração": "heart", "brilho": "sparkles",
    "alvo": "target", "livro": "book-open", "ebook": "book-open", "celular": "smartphone",
    "desconto": "badge-percent", "premio": "award", "prêmio": "award", "entrega": "truck",
    "cadeado": "lock", "design": "palette", "paleta": "palette", "baixar": "download",
    "templates": "layout-grid", "imagem": "image", "foto": "camera", "chat": "message-circle",
    "agenda": "calendar-check", "calendario": "calendar-check",
}


@lru_cache(maxsize=1)
def icones_disponiveis() -> tuple[str, ...]:
    if not ICONS_DIR.is_dir():
        return (ICONE_PADRAO,)
    return tuple(sorted(p.stem for p in ICONS_DIR.glob("*.svg")))


def normalizar_icone(nome: str) -> str:
    """Nome livre → ícone existente (desconhecido vira `check`, nunca quebra o render)."""
    n = (nome or "").strip().lower().replace("_", "-").replace(" ", "-")
    n = APELIDOS.get(n, n)
    return n if n in icones_disponiveis() else ICONE_PADRAO


@lru_cache(maxsize=64)
def svg_inline(nome: str, tamanho: int = 36, traco: float = 2.25) -> str:
    """SVG pronto para inline no HTML (cor = currentColor)."""
    path = ICONS_DIR / f"{normalizar_icone(nome)}.svg"
    if not path.is_file():
        return ""
    svg = path.read_text(encoding="utf-8")
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"\s+", " ", svg).strip()
    svg = re.sub(r'\swidth="[^"]*"', f' width="{tamanho}"', svg, count=1)
    svg = re.sub(r'\sheight="[^"]*"', f' height="{tamanho}"', svg, count=1)
    svg = re.sub(r'\sstroke-width="[^"]*"', f' stroke-width="{traco}"', svg, count=1)
    return svg.replace("<svg ", '<svg aria-hidden="true" ', 1)
