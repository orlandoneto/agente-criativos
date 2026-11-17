"""Persiste criativos em saida/ — com camadas (fases → resultado)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.campanha import pasta_saida_job, slugify
from app.config import PROJECT_VERSION, SAIDA_DIR
from app.schemas import BioResult, CarrosselResult, LegendaResult


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _slug_tema(tema: str) -> str:
    return slugify(tema or "livre")[:40]


def nova_pasta_job(
    nicho: str,
    tipo: str,
    tema: str,
    *,
    campanha: str = "",
    plataforma: str = "",
    formato: str = "",
) -> Path:
    """
    Com campanha: campanhas/<nicho>/<campanha>/saida/<plataforma>/<formato>/...
    Sem campanha: saida/<stamp>_... (legado)
    """
    if (campanha or "").strip():
        pasta = pasta_saida_job(
            nicho,
            campanha,
            plataforma or "geral",
            formato or tipo,
            tema,
        )
        return pasta
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    pasta = SAIDA_DIR / f"{_stamp()}_{nicho}_{tipo}_{_slug_tema(tema)}"
    (pasta / "01_fases").mkdir(parents=True, exist_ok=True)
    (pasta / "02_resultado").mkdir(parents=True, exist_ok=True)
    return pasta


def _escrever_mapa(
    pasta: Path,
    nicho: str,
    tipo: str,
    tema: str,
    linhas_extra: list[str] | None = None,
    *,
    campanha: str = "",
    plataforma: str = "",
) -> None:
    linhas = [
        f"# Job — {tipo}",
        "",
        f"- Motor: {PROJECT_VERSION}",
        f"- Nicho: {nicho}",
        f"- Campanha: {campanha or '(legado saida/)'}",
        f"- Plataforma: {plataforma or '(n/d)'}",
        f"- Tema: {tema or '(livre)'}",
        "",
        "## Camadas",
        "",
        "1. `01_fases/` — textos intermediários (headline, copy, legenda) para revisar",
        "2. `02_resultado/` — entrega final (pronto para usar/postar)",
        "",
    ]
    if linhas_extra:
        linhas.extend(linhas_extra)
    (pasta / "LEIA-ME.md").write_text("\n".join(linhas), encoding="utf-8")


def salvar_bio(
    nicho: str,
    tema: str,
    result: BioResult,
    *,
    campanha: str = "",
    plataforma: str = "",
    formato: str = "bio",
) -> Path:
    pasta = nova_pasta_job(
        nicho, "bio", tema, campanha=campanha, plataforma=plataforma, formato=formato or "bio"
    )
    fases = pasta / "01_fases"
    resultado = pasta / "02_resultado"

    rascunho = [
        f"# Fase — bios (rascunho)",
        "",
        f"Tema: {tema or '(livre)'}",
        "",
    ]
    final = [
        f"# Resultado — bios",
        "",
        f"- Versão: {PROJECT_VERSION}",
        f"- Tema: {tema or '(livre)'}",
        "",
    ]
    for i, v in enumerate(result.variacoes, start=1):
        bloco = [
            f"## Opção {i} ({v.foco or 'geral'}) — {len(v.texto)}/150",
            "",
            v.texto,
            "",
        ]
        rascunho.extend(bloco)
        final.extend(bloco)

    (fases / "01_copy_bios.md").write_text("\n".join(rascunho), encoding="utf-8")
    (resultado / "bios.md").write_text("\n".join(final), encoding="utf-8")
    _escrever_mapa(
        pasta,
        nicho,
        "bio",
        tema,
        ["- Revisar: `01_fases/01_copy_bios.md`", "- Usar: `02_resultado/bios.md`", ""],
        campanha=campanha,
        plataforma=plataforma,
    )
    return pasta


def salvar_legenda(
    nicho: str,
    tema: str,
    result: LegendaResult,
    *,
    campanha: str = "",
    plataforma: str = "",
    formato: str = "texto",
) -> Path:
    pasta = nova_pasta_job(
        nicho,
        "legenda",
        tema,
        campanha=campanha,
        plataforma=plataforma,
        formato=formato or "texto",
    )
    fases = pasta / "01_fases"
    resultado = pasta / "02_resultado"
    completa = result.legenda_completa()

    (fases / "01_headline_gancho.md").write_text(
        "\n".join(
            [
                "# Fase — headline / gancho",
                "",
                f"**Gancho ({len(result.gancho)}/125):**",
                "",
                result.gancho,
                "",
            ]
        ),
        encoding="utf-8",
    )
    (fases / "02_copy_corpo.md").write_text(
        "\n".join(
            [
                "# Fase — copy (corpo + CTA)",
                "",
                f"Estrutura: {result.estrutura}",
                "",
                "## Corpo",
                "",
                result.corpo,
                "",
                "## CTA",
                "",
                result.cta,
                "",
                "## Hashtags",
                "",
                " ".join(result.hashtags),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (resultado / "legenda.md").write_text(
        "\n".join(
            [
                f"# Resultado — legenda",
                "",
                f"- Versão: {PROJECT_VERSION}",
                f"- Tema: {tema or '(livre)'}",
                f"- Total: {len(completa)}/2200",
                "",
                "## Prévia (colar no Instagram)",
                "",
                completa,
                "",
            ]
        ),
        encoding="utf-8",
    )
    _escrever_mapa(
        pasta,
        nicho,
        "legenda",
        tema,
        [
            "- `01_fases/01_headline_gancho.md`",
            "- `01_fases/02_copy_corpo.md`",
            "- `02_resultado/legenda.md`",
            "",
        ],
        campanha=campanha,
        plataforma=plataforma,
    )
    return pasta


def salvar_fases_carrossel(pasta: Path, result: CarrosselResult) -> None:
    fases = pasta / "01_fases"
    fases.mkdir(parents=True, exist_ok=True)

    headlines = [
        "# Fase 1 — Headlines (texto na arte)",
        "",
        "Revise títulos/subtítulos antes de olhar os PNGs.",
        "",
    ]
    for i, slide in enumerate(result.slides, start=1):
        headlines += [
            f"## Slide {i}",
            "",
            f"**Headline:** {slide.titulo}",
            "",
            f"**Apoio:** {slide.apoio or '—'}",
            "",
        ]
    (fases / "01_headlines.md").write_text("\n".join(headlines), encoding="utf-8")

    copy_slides = [
        "# Fase 2 — Copy dos slides (notas + prompts)",
        "",
    ]
    for i, slide in enumerate(result.slides, start=1):
        copy_slides += [
            f"## Slide {i}",
            "",
            f"- Título: {slide.titulo}",
            f"- Apoio: {slide.apoio or '—'}",
            f"- Nota visual: {slide.nota_visual or '—'}",
            f"- Prompt imagem: {slide.prompt_imagem or '—'}",
            "",
        ]
    (fases / "02_copy_slides.md").write_text("\n".join(copy_slides), encoding="utf-8")

    leg = result.as_legenda()
    (fases / "03_legenda.md").write_text(
        "\n".join(
            [
                "# Fase 3 — Legenda do post",
                "",
                f"Estrutura: {leg.estrutura}",
                "",
                "## Gancho",
                "",
                leg.gancho,
                "",
                "## Corpo",
                "",
                leg.corpo,
                "",
                "## CTA",
                "",
                leg.cta,
                "",
                "## Hashtags",
                "",
                " ".join(leg.hashtags),
                "",
                "## Prévia completa",
                "",
                leg.legenda_completa(),
                "",
            ]
        ),
        encoding="utf-8",
    )


def salvar_carrossel_em(
    pasta: Path,
    nicho: str,
    tema: str,
    result: CarrosselResult,
    pngs: list[Path],
    *,
    campanha: str = "",
    plataforma: str = "",
) -> Path:
    resultado = pasta / "02_resultado"
    resultado.mkdir(parents=True, exist_ok=True)
    salvar_fases_carrossel(pasta, result)

    legenda = result.as_legenda().legenda_completa()
    path = resultado / "conteudo.md"
    linhas = [
        f"# Resultado final — carrossel",
        "",
        f"- Versão motor: {PROJECT_VERSION}",
        f"- Nicho: {nicho}",
        f"- Tema: {tema or '(livre)'}",
        f"- Slides/PNGs: {len(result.slides)}/{len(pngs)}",
        "",
        "## Legenda (colar no Instagram)",
        "",
        legenda,
        "",
        "## PNGs nesta pasta",
        "",
    ]
    for p in pngs:
        linhas.append(f"- `{p.name}`")
    linhas += ["", "## Índice dos slides", ""]
    for i, slide in enumerate(result.slides, start=1):
        png_name = pngs[i - 1].name if i <= len(pngs) else "(sem png)"
        linhas += [
            f"### {i}. `{png_name}`",
            f"- {slide.titulo}",
            f"- {slide.apoio or '—'}",
            "",
        ]
    path.write_text("\n".join(linhas), encoding="utf-8")

    _escrever_mapa(
        pasta,
        nicho,
        "carrossel",
        tema,
        [
            "### Ordem de revisão",
            "1. `01_fases/01_headlines.md`",
            "2. `01_fases/02_copy_slides.md`",
            "3. `01_fases/03_legenda.md`",
            "4. `01_fases/04_cenas.md` + `01_fases/cenas/` (fotos Gemini)",
            "5. `02_resultado/slide_XX.png` — **cena + tipografia** (abordagem A)",
            "6. `02_resultado/reels_tiktok.mp4` — se gerou com `--video` (9:16 Reels/TikTok)",
            "",
        ],
        campanha=campanha,
        plataforma=plataforma,
    )
    return pasta


def anotar_video_no_resultado(
    pasta: Path,
    mp4: Path,
    *,
    segundos_por_slide: float,
) -> None:
    """Acrescenta o MP4 no conteudo.md do resultado."""
    path = pasta / "02_resultado" / "conteudo.md"
    extra = (
        f"\n## Vídeo Reels / TikTok\n\n"
        f"- Arquivo: `{mp4.name}` (1080×1920)\n"
        f"- {segundos_por_slide}s por slide · slideshow sem IA de vídeo\n"
        f"- Postar em Instagram Reels ou TikTok\n"
    )
    if path.exists():
        path.write_text(path.read_text(encoding="utf-8") + extra, encoding="utf-8")
    leia = pasta / "LEIA-ME.md"
    if leia.exists():
        leia.write_text(
            leia.read_text(encoding="utf-8")
            + f"\n- Vídeo: `02_resultado/{mp4.name}`\n",
            encoding="utf-8",
        )
