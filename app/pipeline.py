"""Pipeline: texto → cenas Gemini (A) → tipografia no template → resultado."""

from __future__ import annotations

from pathlib import Path

from app import gemini_client, prompt_builder, saver
from app.brand import carregar_brand
from app.config import IMAGE_CHAIN
from app.campanha import texto_skill_para_prompt
from app.image_gen import gerar_cena_com_provider
from app.nicho_loader import carregar_nicho
from app.renderer import render_carrossel_pngs
from app.schemas import BioResult, CarrosselResult, LegendaResult
from app.validator import validar_bio, validar_carrossel, validar_legenda
from app.video import montar_reels_mp4


def _tema_com_skill(nicho: str, tema: str, campanha: str) -> str:
    """Anexa skill de conteúdo da campanha, se existir; senão só o tema."""
    bloco = texto_skill_para_prompt(nicho, campanha) if campanha else ""
    if not bloco:
        return tema
    return f"{tema}\n\n{bloco}"


def gerar_bio(
    nicho: str,
    tema: str,
    *,
    campanha: str = "",
    plataforma: str = "",
    formato: str = "bio",
) -> Path:
    ctx = carregar_nicho(nicho, "bio")
    prompt = prompt_builder.prompt_bio(ctx, _tema_com_skill(nicho, tema, campanha))
    result = gemini_client.gerar_json(prompt, BioResult)
    check = validar_bio(result)
    if not check.ok:
        result = gemini_client.corrigir_json(prompt, BioResult, check.erros, result)
        check = validar_bio(result)
        if not check.ok:
            raise ValueError("Bio inválida após correção:\n- " + "\n- ".join(check.erros))
    return saver.salvar_bio(
        nicho, tema, result, campanha=campanha, plataforma=plataforma, formato=formato
    )


def gerar_legenda(
    nicho: str,
    tema: str,
    *,
    campanha: str = "",
    plataforma: str = "",
    formato: str = "texto",
) -> Path:
    ctx = carregar_nicho(nicho, "legenda")
    prompt = prompt_builder.prompt_legenda(ctx, _tema_com_skill(nicho, tema, campanha))
    result = gemini_client.gerar_json(prompt, LegendaResult)
    check = validar_legenda(result)
    if not check.ok:
        result = gemini_client.corrigir_json(prompt, LegendaResult, check.erros, result)
        check = validar_legenda(result)
        if not check.ok:
            raise ValueError("Legenda inválida após correção:\n- " + "\n- ".join(check.erros))
    return saver.salvar_legenda(
        nicho, tema, result, campanha=campanha, plataforma=plataforma, formato=formato
    )


def _gerar_cenas(
    result: CarrosselResult,
    pasta_cenas: Path,
    max_cenas: int,
    com_imagens: bool,
) -> tuple[list[Path | None], list[str]]:
    pasta_cenas.mkdir(parents=True, exist_ok=True)
    cenas: list[Path | None] = []
    log_linhas: list[str] = [
        "# Fase 4 — Cenas (chaveador)",
        "",
        "Ordem: **" + " → ".join(IMAGE_CHAIN) + "** → tipografia.",
        "Cada cena vira PNG limpo (sem EXIF) + `cena_XX.json` (provedor, licença, atribuição).",
        "A cena vem sem texto; o template coloca headline/selo.",
        "",
        f"- Pedido de cenas: {max_cenas if com_imagens else 0}",
        "",
    ]
    if not com_imagens:
        log_linhas.append("Imagens desligadas (`--sem-imagem`). Fallback tipográfico.")
        return [None] * len(result.slides), log_linhas

    ok = 0
    for i, slide in enumerate(result.slides, start=1):
        dest = pasta_cenas / f"cena_{i:02d}.png"
        if i > max_cenas:
            cenas.append(None)
            log_linhas.append(f"- Slide {i}: pulado (acima de --max-cenas={max_cenas})")
            continue
        # Continua de onde parou: cena já gerada nesta pasta não refaz
        if dest.is_file() and dest.stat().st_size > 0:
            cenas.append(dest)
            ok += 1
            log_linhas.append(f"- Slide {i}: reaproveitado `{dest.name}` (de onde parou)")
            print(f"  Cena {i}: já existia — pulando")
            continue
        print(f"  Cena {i}/{min(max_cenas, len(result.slides))}…")
        res = gerar_cena_com_provider(slide.prompt_imagem, slide.titulo, slide.apoio, dest)
        cenas.append(res.path)
        if res.path:
            ok += 1
            log_linhas.append(
                f"- Slide {i}: OK via **{res.provider}** → `{res.path.name}`"
            )
        else:
            log_linhas.append(
                f"- Slide {i}: FALHOU cadeia — tipografia sem foto ({res.detail[:200]})"
            )
    log_linhas += ["", f"**Cenas OK:** {ok}/{min(max_cenas, len(result.slides))}", ""]
    if ok == 0:
        log_linhas += [
            "> Nenhum provedor de imagem respondeu.",
            "> Confira HF_TOKEN / PEXELS_API_KEY / rede, ou use `--sem-imagem`.",
            "",
        ]
    return cenas, log_linhas


def gerar_carrossel(
    nicho: str,
    tema: str,
    *,
    com_imagens: bool = True,
    max_cenas: int = 8,
    com_video: bool = False,
    video_segundos: float | None = None,
    campanha: str = "",
    plataforma: str = "",
    formato: str = "carrossel",
) -> Path:
    from app.job_cleanup import limpar_se_incompleto

    pasta: Path | None = None
    try:
        ctx = carregar_nicho(nicho, "carrossel")
        prompt = prompt_builder.prompt_carrossel(ctx, _tema_com_skill(nicho, tema, campanha))
        result = gemini_client.gerar_json(prompt, CarrosselResult)
        check = validar_carrossel(result)
        if not check.ok:
            result = gemini_client.corrigir_json(prompt, CarrosselResult, check.erros, result)
            check = validar_carrossel(result)
            if not check.ok:
                raise ValueError("Carrossel inválido após correção:\n- " + "\n- ".join(check.erros))

        pasta = saver.nova_pasta_job(
            nicho,
            "carrossel",
            tema,
            campanha=campanha,
            plataforma=plataforma,
            formato=formato or "carrossel",
        )
        saver.salvar_fases_carrossel(pasta, result)

        pasta_cenas = pasta / "01_fases" / "cenas"
        cenas, log_cenas = _gerar_cenas(result, pasta_cenas, max_cenas, com_imagens)
        (pasta / "01_fases" / "04_cenas.md").write_text("\n".join(log_cenas), encoding="utf-8")

        brand = carregar_brand(nicho)
        selo = tema.strip()[:28] if tema.strip() else "Destaque"
        pngs = render_carrossel_pngs(
            result,
            brand,
            pasta / "02_resultado",
            cenas=cenas,
            selo=selo,
        )
        pasta = saver.salvar_carrossel_em(
            pasta, nicho, tema, result, pngs, campanha=campanha, plataforma=plataforma
        )

        if com_video and pngs:
            from app.config import VIDEO_SEGUNDOS_POR_SLIDE

            segs = VIDEO_SEGUNDOS_POR_SLIDE if video_segundos is None else video_segundos
            print(f"  Vídeo Reels/TikTok 9:16 ({segs}s/slide)…")
            mp4 = montar_reels_mp4(
                pngs,
                pasta / "02_resultado" / "reels_tiktok.mp4",
                fundo_hex=brand.fundo,
                segundos_por_slide=max(0.5, float(segs)),
            )
            saver.anotar_video_no_resultado(pasta, mp4, segundos_por_slide=segs)
            print(f"  MP4: {mp4}")
        return pasta
    except Exception:
        limpar_se_incompleto(pasta)
        raise
