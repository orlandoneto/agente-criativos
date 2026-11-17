"""Wizard do post Instagram no estilo novo (Fase 2): pergunta news ou ad, formato, marca e tema.

Devolve a lista de flags equivalente (mesmo núcleo da CLI: `main_post`). Interface única:
o que o wizard pergunta é exatamente o que as flags aceitam.
"""

from __future__ import annotations

from typing import Callable

from app.cli_style import C, dim, paint, titulo

ESTILOS_MENU = (("news", "Card de notícia (foto real, tarja, manchete com destaque)"),
                ("ad", "Anúncio (cena IA, pílula, selo, benefícios, botão CTA)"))
FORMATOS_MENU = (("4x5", "Feed retrato 1080×1350 (recomendado)"),
                 ("1x1", "Feed quadrado 1080×1080 (também Facebook)"),
                 ("9x16", "Stories / Reels 1080×1920 (com zonas seguras)"),
                 ("capa-reels", "Capa de Reels 1080×1920 (texto no miolo do grid)"),
                 ("carrossel", "Carrossel: capa + slides 4:5"))

Perguntar = Callable[[str], str]


def _input(prompt: str) -> str:
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt) as exc:
        print()
        raise SystemExit(130) from exc


def _menu(perguntar: Perguntar, rotulo: str, opcoes: tuple[tuple[str, str], ...], padrao: int = 1) -> str | None:
    print(titulo(rotulo))
    for i, (_, desc) in enumerate(opcoes, start=1):
        print(f"  {paint(f'{i})', C.bold, C.cyan)} {desc}")
    print(f"  {paint('0', C.yellow)}) Sair")
    while True:
        raw = (perguntar(f"{paint('›', C.cyan)} Escolha {dim(f'[{padrao}]')}: ") or "").strip().lower()
        if raw in {"0", "q", "sair"}:
            return None
        if not raw:
            return opcoes[padrao - 1][0]
        ids = [o[0] for o in opcoes]
        if raw in ids:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(opcoes):
            return opcoes[int(raw) - 1][0]
        print(dim("  Opção inválida."))


def escolher_modo(perguntar: Perguntar = _input) -> str | None:
    """'post' (estilo novo news/ad) | 'classico' (bio/legenda/carrossel antigo) | None (sair)."""
    return _menu(perguntar, "O que vamos criar?", (
        ("post", "Post Instagram no estilo novo: news ou ad (feed, Stories/Reels, capa, carrossel)"),
        ("classico", "Fluxo clássico: bio, legenda ou carrossel antigo"),
    ))


def coletar_post(perguntar: Perguntar = _input) -> list[str] | None:
    """Pergunta estilo → formato → marca → tema (→ nº de slides) e devolve as flags do CLI."""
    from app.brand_kit import listar_marcas
    from app.wizard import listar_nichos

    estilo = _menu(perguntar, "Estilo", ESTILOS_MENU)
    if estilo is None:
        return None
    formato = _menu(perguntar, "Formato", FORMATOS_MENU)
    if formato is None:
        return None

    marcas = listar_marcas()
    nichos = listar_nichos()
    padrao = "minhamarca" if "minhamarca" in nichos else (nichos[0] if nichos else "")
    print(titulo("Marca / nicho"))
    if marcas:
        print(dim("  Com brand kit: " + ", ".join(marcas)))
    nicho = ""
    while not nicho:
        raw = (perguntar(f"{paint('›', C.cyan)} Slug {dim(f'[{padrao}]')}: ") or "").strip() or padrao
        if raw in nichos:
            nicho = raw
        else:
            print(dim(f"  Não achei '{raw}' em nichos/. Opções: {', '.join(nichos[:12])}…"))

    tema = ""
    while not tema:
        tema = (perguntar(f"{paint('›', C.cyan)} Tema do post (a IA grátis escreve o texto): ") or "").strip()

    argv = ["--estilo", estilo, "--formato", formato, "--nicho", nicho, "--tema", tema, "--buscar-fundo"]
    if nicho in marcas:
        argv += ["--marca", nicho]
    if formato == "carrossel":
        raw = (perguntar(f"{paint('›', C.cyan)} Quantos slides além da capa? {dim('[2]')}: ") or "").strip()
        n = int(raw) if raw.isdigit() and 1 <= int(raw) <= 9 else 2
        argv += ["--slides-n", str(n)]
    raw = (perguntar(f"{paint('›', C.cyan)} Revisão automática por IA de visão? (s/n) {dim('[s]')}: ") or "s")
    if raw.strip().lower() in {"n", "nao", "não", "no"}:
        argv.append("--sem-revisao")
    return argv
