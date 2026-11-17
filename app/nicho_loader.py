"""Carrega perfil, evitar e exemplos de um nicho."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import DATA_REGRAS, NICHOS_DIR


@dataclass
class NichoContext:
    slug: str
    perfil: str
    evitar: str
    exemplos: str
    regra_tipo: str


def _ler(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def carregar_nicho(slug: str, tipo: str) -> NichoContext:
    pasta = NICHOS_DIR / slug
    if not pasta.is_dir():
        raise FileNotFoundError(f"Nicho não encontrado: {pasta}")

    exemplos_dir = pasta / "exemplos"
    blocos: list[str] = []
    if exemplos_dir.is_dir():
        for arq in sorted(exemplos_dir.glob("*.md")):
            texto = _ler(arq)
            if texto:
                blocos.append(f"### {arq.name}\n{texto}")

    regra_path = DATA_REGRAS / f"{tipo}.md"
    regra = _ler(regra_path)
    if not regra:
        raise FileNotFoundError(f"Regra ausente para tipo '{tipo}': {regra_path}")

    return NichoContext(
        slug=slug,
        perfil=_ler(pasta / "perfil.md"),
        evitar=_ler(pasta / "evitar.md"),
        exemplos="\n\n".join(blocos) if blocos else "(sem exemplos ainda)",
        regra_tipo=regra,
    )
