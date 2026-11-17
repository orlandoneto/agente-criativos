"""Marca de abertura da CLI (ASCII simples, seguro no Windows)."""

from __future__ import annotations

from app.config import PROJECT_NAME, PROJECT_VERSION


def banner_text(
    nome: str = PROJECT_NAME,
    versao: str = PROJECT_VERSION,
) -> str:
    """Bloco da marca — testável, sem print."""
    return "\n".join(
        [
            "",
            "      *",
            "     /|\\",
            "    * | *",
            "     \\|/",
            "      *",
            f"  {nome}",
            f"  v{versao}",
            "",
        ]
    )


def print_banner() -> None:
    print(banner_text(), end="")
