"""Monta prompts a partir do nicho + tema."""

from __future__ import annotations

from app.nicho_loader import NichoContext


def _base(ctx: NichoContext, tema: str) -> str:
    return (
        "Você é copywriter sênior para redes sociais. Responda SOMENTE JSON válido "
        "(sem markdown fora do JSON).\n\n"
        f"## Perfil do nicho\n{ctx.perfil}\n\n"
        f"## Evitar\n{ctx.evitar}\n\n"
        f"## Exemplos aprovados (imite o estilo)\n{ctx.exemplos}\n\n"
        f"## Regras do formato\n{ctx.regra_tipo}\n\n"
        f"## Tema do pedido\n{tema.strip() or '(tema livre alinhado ao perfil)'}\n"
    )


def prompt_bio(ctx: NichoContext, tema: str) -> str:
    return (
        _base(ctx, tema)
        + "\nGere exatamente 3 bios.\n"
        "Schema JSON:\n"
        '{"variacoes":[{"texto":"...","foco":"dor|ganho|prova"},'
        '{"texto":"...","foco":"..."},{"texto":"...","foco":"..."}]}\n'
        "Cada texto ≤ 150 caracteres.\n"
    )


def prompt_legenda(ctx: NichoContext, tema: str) -> str:
    return (
        _base(ctx, tema)
        + "\nGere 1 legenda completa.\n"
        "Schema JSON:\n"
        '{"gancho":"...","corpo":"...","cta":"...","hashtags":["#a","#b","#c"],'
        '"estrutura":"PAS|AIDA"}\n'
        "Gancho ≤ 125 caracteres. 3 a 5 hashtags. Legenda total ≤ 2200 caracteres.\n"
    )


def prompt_carrossel(ctx: NichoContext, tema: str) -> str:
    return (
        _base(ctx, tema)
        + "\nGere 1 carrossel com 7 a 10 slides + legenda do post.\n"
        "Slide 1 = gancho forte. Meio = uma ideia cada. Último = CTA claro.\n"
        "Títulos CURTOS (cabem na arte 1080x1350). Apoio opcional, também curto.\n"
        "prompt_imagem: em INGLÊS, cena fotográfica/editorial completa "
        "(pessoa/ambiente/clima). PROIBIDO pedir texto, letras, logo ou watermark na imagem. "
        "Peça área inferior um pouco mais escura para overlay de tipografia.\n"
        "Schema JSON:\n"
        "{\n"
        '  "slides":[{"titulo":"...","apoio":"...","nota_visual":"...","prompt_imagem":"..."}],\n'
        '  "gancho":"...","corpo":"...","cta":"...","hashtags":["#a","#b","#c"],'
        '"estrutura":"PAS"\n'
        "}\n"
        "Gancho ≤ 125. 3–5 hashtags. Sem markdown fora do JSON.\n"
    )
