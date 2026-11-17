"""
Sessão de IAs da corrida atual (`gerar`).

Quando uma IA funciona, as próximas etapas **continuam nela** (sticky).
Se falhar, o failover troca e o serviço segue **de onde parou** (próximo job / próxima cena).
"""

from __future__ import annotations

# Sticky da corrida (reset no início de cada `gerar`)
modelo_texto: str | None = None
provedor_imagem: str | None = None


def reset() -> None:
    global modelo_texto, provedor_imagem
    modelo_texto = None
    provedor_imagem = None


def lembrar_texto(modelo: str) -> None:
    global modelo_texto
    if modelo:
        modelo_texto = modelo


def lembrar_imagem(provedor: str) -> None:
    global provedor_imagem
    if provedor and provedor != "none":
        provedor_imagem = provedor


def fila_texto(base: list[str]) -> list[str]:
    """Modelo que já funcionou nesta corrida vai primeiro."""
    if not modelo_texto or modelo_texto not in base:
        return list(base)
    return [modelo_texto] + [m for m in base if m != modelo_texto]


def fila_imagem(base: list[str]) -> list[str]:
    """Provedor de imagem que já funcionou vai primeiro."""
    if not provedor_imagem or provedor_imagem not in base:
        return list(base)
    return [provedor_imagem] + [p for p in base if p != provedor_imagem]
