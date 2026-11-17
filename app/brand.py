"""Extrai identidade visual do perfil.md do nicho."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.nicho_loader import carregar_nicho


@dataclass
class BrandColors:
    fundo: str = "#0F172A"
    texto: str = "#F8FAFC"
    destaque: str = "#38BDF8"
    nome: str = "Marca"


_HEX = re.compile(r"#([0-9A-Fa-f]{6})\b")


def carregar_brand(nicho: str) -> BrandColors:
    ctx = carregar_nicho(nicho, "carrossel")
    perfil = ctx.perfil
    hexes = _HEX.findall(perfil)
    # Ordem típica no perfil: Fundo, Texto, Destaque
    fundo = f"#{hexes[0]}" if len(hexes) >= 1 else "#0F172A"
    texto = f"#{hexes[1]}" if len(hexes) >= 2 else "#F8FAFC"
    destaque = f"#{hexes[2]}" if len(hexes) >= 3 else "#38BDF8"

    nome = "Marca"
    for linha in perfil.splitlines():
        if "**Nome:**" in linha:
            nome = linha.split("**Nome:**", 1)[-1].strip() or nome
            break

    return BrandColors(fundo=fundo, texto=texto, destaque=destaque, nome=nome)
