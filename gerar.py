"""
CLI — Agente Criativos.
Abordagem A: cena Gemini Image + tipografia no template.

Uso simples (Cmder):  gerar
  → marca + perguntas (nicho, tipo, tema).

Flags (--nicho / --tipo / --tema) ainda funcionam para script.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from app.banner import print_banner
from app.config import (
    GEMINI_API_KEY,
    GEMINI_IMAGE_ENABLED,
    GEMINI_IMAGE_MODEL,
    GEMINI_MODEL,
    PROJECT_NAME,
    PROJECT_VERSION,
)
from app.pipeline import gerar_bio, gerar_carrossel, gerar_legenda
from app.plataformas import PLATAFORMA_IDS
from app.wizard import TIPOS, Brief, JobFormato, coletar_brief


def _invocado_como_gerar() -> bool:
    from pathlib import Path
    return Path(sys.argv[0]).name.lower().startswith("gerar")


def _aviso_apelido() -> None:
    if _invocado_como_gerar():
        print(
            "[aviso] O comando `gerar` ficou como apelido. Prefira `agente-criativos`.",
            file=sys.stderr,
        )


def _citar(arg: str) -> str:
    return f'"{arg}"' if (" " in arg or not arg) else arg


def _flag_foi_passada(argv: list[str], *nomes: str) -> bool:
    return any(a == n or a.startswith(f"{n}=") for a in argv for n in nomes)


# Flags de texto livre cujo valor pode começar com "-" (ex.: --badge -50%).
_FLAGS_VALOR_LIVRE = ("--badge", "--tag", "--pill", "--cta", "--apoio", "--titulo", "--headline", "--destaques",
                      "--features", "--tema", "--prompt-fundo", "--slide", "--contexto", "--ideia")


def _juntar_valores_com_traco(argv: list[str]) -> list[str]:
    """`--badge -50%` → `--badge=-50%` (o argparse acharia que -50% é outra opção)."""
    out: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _FLAGS_VALOR_LIVRE and i + 1 < len(argv) and argv[i + 1].startswith("-") \
                and not argv[i + 1].startswith("--"):
            out.append(f"{a}={argv[i + 1]}")
            i += 2
            continue
        out.append(a)
        i += 1
    return out


def main(argv: list[str] | None = None) -> int:
    argv = _juntar_valores_com_traco(list(sys.argv[1:] if argv is None else argv))
    _aviso_apelido()

    parser = argparse.ArgumentParser(
        description=f"{PROJECT_NAME} v{PROJECT_VERSION} — use `agente-criativos` (o antigo `gerar` continua como apelido)",
    )
    parser.add_argument("--ping", action="store_true", help="Testa só a conexão Gemini texto")
    parser.add_argument("--nicho", default=None, help="Slug do nicho (pula pergunta); para humano use só `gerar`")
    parser.add_argument(
        "--plataforma",
        default=None,
        choices=list(PLATAFORMA_IDS),
        help="instagram|tiktok|facebook|youtube (pula pergunta)",
    )
    parser.add_argument("--tipo", default=None, choices=list(TIPOS), help="bio|legenda|carrossel (pula pergunta)")
    parser.add_argument("--tema", default=None, help="Tema da campanha (pula pergunta)")
    parser.add_argument(
        "--contexto",
        default=None,
        help="Contexto livre extra (dev/robô); no wizard pergunta se faltar",
    )
    parser.add_argument(
        "--campanha",
        default=None,
        help="Slug da campanha → campanhas/<nicho>/<campanha>/",
    )
    parser.add_argument(
        "--ideia",
        default=None,
        help="Ideia central da skill de conteúdo → skill/ideia.md (opcional)",
    )
    parser.add_argument(
        "--imagens",
        default=None,
        help="Imagens da skill (; ou pasta) → skill/referencias/ (opcional)",
    )
    parser.add_argument(
        "--sem-imagem",
        action="store_true",
        help="Não chama Gemini Image (só tipografia / fallback)",
    )
    parser.add_argument(
        "--max-cenas",
        type=int,
        default=None,
        help="Máximo de cenas Gemini Image por carrossel (economiza cota)",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Monta MP4 9:16 (Reels/TikTok) com os slides — sem IA de vídeo",
    )
    parser.add_argument(
        "--video-segundos",
        type=float,
        default=None,
        help="Segundos por slide no MP4 (padrão: VIDEO_SEGUNDOS_POR_SLIDE)",
    )
    parser.add_argument(
        "--video-de",
        default="",
        help="Só monta MP4 a partir de uma pasta de job já gerada (02_resultado/slide_*.png)",
    )
    from app.post_pipeline import adicionar_flags

    adicionar_flags(parser)
    args = parser.parse_args(argv)

    print_banner()

    # Remontar vídeo de um job antigo não exige Gemini
    if args.video_de:
        from pathlib import Path

        from app.brand import carregar_brand
        from app.config import VIDEO_SEGUNDOS_POR_SLIDE
        from app.saver import anotar_video_no_resultado
        from app.video import montar_reels_mp4

        pasta = Path(args.video_de)
        if not pasta.is_absolute():
            from app.config import SAIDA_DIR

            pasta = SAIDA_DIR / args.video_de if not pasta.exists() else pasta
        resultado = pasta / "02_resultado" if (pasta / "02_resultado").is_dir() else pasta
        pngs = sorted(resultado.glob("slide_*.png"))
        if not pngs:
            print(f"ERRO: nenhum slide_*.png em {resultado}")
            return 1
        nicho_video = args.nicho or "exemplo_tech"
        brand = carregar_brand(nicho_video)
        segs = (
            VIDEO_SEGUNDOS_POR_SLIDE
            if args.video_segundos is None
            else args.video_segundos
        )
        print(f"Montando Reels/TikTok a partir de {len(pngs)} slides…")
        mp4 = montar_reels_mp4(
            pngs,
            resultado / "reels_tiktok.mp4",
            fundo_hex=brand.fundo,
            segundos_por_slide=max(0.5, float(segs)),
        )
        job = pasta if (pasta / "02_resultado").is_dir() else pasta.parent
        if (job / "02_resultado").is_dir():
            anotar_video_no_resultado(job, mp4, segundos_por_slide=segs)
        print(f"MP4: {mp4}")
        return 0

    # Post único Instagram (news/ad) — manual não precisa de chave nenhuma
    if args.estilo:
        from app.post_pipeline import main_post

        return main_post(args)

    # Wizard sem nenhuma flag: primeiro pergunta se é post no estilo novo (news/ad) ou o fluxo clássico.
    if not argv:
        from app.wizard_post import coletar_post, escolher_modo

        modo = escolher_modo()
        if modo is None:
            return 0
        if modo == "post":
            flags = coletar_post()
            if flags is None:
                return 0
            print(f"Comando equivalente: agente-criativos {' '.join(_citar(f) for f in flags)}")
            from app.post_pipeline import main_post

            return main_post(parser.parse_args(flags))

    if not GEMINI_API_KEY:
        print("ERRO: GEMINI_API_KEY ausente.")
        return 1

    if args.ping:
        from app.gemini_client import ping

        print(f"Modelo texto: {GEMINI_MODEL}")
        print("Ping Gemini…")
        try:
            texto = ping()
        except RuntimeError as exc:
            print(f"FALHA: {exc}")
            return 2
        print(f"Resposta: {texto}")
        return 0

    # Humano: `gerar` → wizard. Dev/robô: flags completas → Brief direto.
    falta_nicho = args.nicho is None
    falta_plataforma = args.plataforma is None
    falta_tipo = args.tipo is None
    falta_tema = not (args.tema or "").strip()
    falta_campanha = args.campanha is None
    if falta_nicho or falta_plataforma or falta_tipo or falta_tema or falta_campanha:
        brief = coletar_brief(
            nicho=args.nicho,
            tipo=args.tipo,
            tema=args.tema,
            contexto=args.contexto,
            campanha=args.campanha,
            ideia=args.ideia,
            imagens=args.imagens,
            plataforma=args.plataforma,
            sem_imagem=True if args.sem_imagem else None,
            max_cenas=args.max_cenas,
            video=True if args.video else None,
        )
        if brief is None:
            return 0
    else:
        from app.campanha import (
            garantir_estrutura,
            gravar_ideia,
            importar_referencias,
            parse_caminhos_imagens,
            slugify,
        )

        campanha = slugify(args.campanha)
        garantir_estrutura(args.nicho, campanha, tema=args.tema or "", contexto=args.contexto or "")
        if args.ideia and str(args.ideia).strip():
            gravar_ideia(args.nicho, campanha, str(args.ideia).strip())
        if args.imagens:
            importar_referencias(args.nicho, campanha, parse_caminhos_imagens(args.imagens))
        brief = Brief(
            nicho=args.nicho,
            tipo=args.tipo,
            tema=(args.tema or "").strip(),
            contexto=(args.contexto or "").strip(),
            campanha=campanha,
            plataforma=args.plataforma,
            formato=args.tipo,
            jobs=(
                JobFormato(
                    formato=args.tipo,
                    tipo=args.tipo,
                    video=bool(args.video),
                    label=args.tipo,
                ),
            ),
            sem_imagem=bool(args.sem_imagem),
            max_cenas=8 if args.max_cenas is None else max(0, args.max_cenas),
            video=bool(args.video),
        )

    # Flags explícitas na linha de comando sobrescrevem o wizard
    if _flag_foi_passada(argv, "--sem-imagem"):
        brief = replace(brief, sem_imagem=True)
    if _flag_foi_passada(argv, "--video"):
        brief = replace(
            brief,
            video=True,
            jobs=tuple(
                JobFormato(j.formato, j.tipo, True, j.label, j.max_cenas)
                if j.tipo == "carrossel"
                else j
                for j in brief.jobs_efetivos()
            ),
        )
    if args.max_cenas is not None:
        brief = replace(brief, max_cenas=max(0, args.max_cenas))

    from pathlib import Path

    from app import ia_sessao
    from app.cli_style import aviso, dim, erro, ok
    from app.config import IMAGE_CHAIN
    from app.gemini_client import _mensagem_api, rotacao_texto
    from app.job_cleanup import remover_pasta_job

    # Nova corrida: sticky limpo; se uma IA funcionar, os jobs seguintes usam ela
    ia_sessao.reset()

    texto_pedido = brief.texto_campanha()
    jobs = brief.jobs_efetivos()
    print(
        f"Nicho={brief.nicho}  Campanha={brief.campanha or '-'}  "
        f"Plataforma={brief.plataforma}  Jobs={len(jobs)}"
    )
    print(f"Tema={brief.tema}")
    if brief.contexto:
        print(f"Contexto={brief.contexto}")
    print(f"Texto preferido={GEMINI_MODEL}")

    # Lista a rotação ANTES de gerar
    fila_txt = rotacao_texto()
    print()
    print("Rotação de IAs nesta corrida:")
    print(dim("  Texto (ordem):"))
    for n, m in enumerate(fila_txt, start=1):
        print(f"    {n}. {m}")
    if not fila_txt:
        print(erro("    (nenhum modelo vivo — confira GEMINI_MODEL no .env)"))
    print(dim("  Imagem (ordem):"))
    for n, p in enumerate(IMAGE_CHAIN, start=1):
        print(f"    {n}. {p}" + (f" ({GEMINI_IMAGE_MODEL})" if p == "gemini" else ""))
    print(dim("  Saturado → fica tentando até dar certo ou você apertar s/q."))
    print(dim("  Enter=pular espera | s=tipografia | q=parar · manhã/pico pior, noite melhor."))

    def _rodar_job(job, *, forcar_sem_imagem: bool = False) -> Path:
        cenas_job = brief.max_cenas if job.max_cenas is None else job.max_cenas
        sem_img = brief.sem_imagem or forcar_sem_imagem
        if job.tipo == "bio":
            return gerar_bio(
                brief.nicho,
                texto_pedido,
                campanha=brief.campanha,
                plataforma=brief.plataforma,
                formato=job.formato,
            )
        if job.tipo == "legenda":
            return gerar_legenda(
                brief.nicho,
                texto_pedido,
                campanha=brief.campanha,
                plataforma=brief.plataforma,
                formato=job.formato,
            )
        return gerar_carrossel(
            brief.nicho,
            texto_pedido,
            com_imagens=not sem_img,
            max_cenas=max(0, int(cenas_job)),
            com_video=job.video,
            video_segundos=args.video_segundos,
            campanha=brief.campanha,
            plataforma=brief.plataforma,
            formato=job.formato,
        )

    from app.resiliencia_ia import (
        CHECKPOINT_A_CADA,
        eh_saturacao_ou_cota,
        esperar_ia,
        gravar_campanha_pendente,
        imprimir_contornos,
        tentar_ping,
    )

    salvos: list[Path] = []
    falhas: list[str] = []
    erros_msg: list[str] = []
    tipos_ok: set[str] = set()
    tipos_fail: set[str] = set()
    salvou_pendente = False
    forcar_tipografia = False

    for i, job in enumerate(jobs, start=1):
        print()
        print(f"[{i}/{len(jobs)}] {job.label} → {job.tipo}" + (" +vídeo" if job.video else ""))
        cenas_job = brief.max_cenas if job.max_cenas is None else job.max_cenas
        if job.tipo == "carrossel":
            print(
                f"Imagem={GEMINI_IMAGE_MODEL}  enabled={GEMINI_IMAGE_ENABLED and not (brief.sem_imagem or forcar_tipografia)}  "
                f"max_cenas={cenas_job}  video={job.video}"
            )
        if ia_sessao.modelo_texto:
            print(dim(f"  IA texto desta corrida: {ia_sessao.modelo_texto}"))
        if ia_sessao.provedor_imagem and job.tipo == "carrossel":
            print(dim(f"  IA imagem desta corrida: {ia_sessao.provedor_imagem}"))
        print("Gerando…")

        path: Path | None = None
        ultimo_erro: str = ""
        esperas_feitas = 0

        while True:
            try:
                path = _rodar_job(job, forcar_sem_imagem=forcar_tipografia)
                break
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = str(exc) if isinstance(exc, RuntimeError) else _mensagem_api(exc)
                print(dim(f"  ↻ {job.label}: {ultimo_erro}"))

                if not eh_saturacao_ou_cota(ultimo_erro):
                    # Erro definitivo (auth, etc.) — uma troca rápida e desiste
                    if esperas_feitas == 0:
                        print(dim("  ↻ tentando uma vez com outra IA…"))
                        esperas_feitas = -1  # marca retry único
                        continue
                    break

                esperas_feitas = max(0, esperas_feitas) + 1

                # Checkpoint a cada ciclo completo — salva campanha mas SEGUE tentando
                if brief.campanha and esperas_feitas % CHECKPOINT_A_CADA == 0:
                    gravar_campanha_pendente(
                        brief.nicho,
                        brief.campanha,
                        tema=brief.tema,
                        plataforma=brief.plataforma,
                        jobs_ok=[str(p) for p in salvos],
                        jobs_falha=[job.label],
                        pastas_salvas=[str(p) for p in salvos],
                        motivo=f"checkpoint após {esperas_feitas} tentativas: {ultimo_erro[:200]}",
                    )
                    print(dim("  → campanha salva (pendente.md); continuo tentando até s/q ou sucesso"))

                if esperas_feitas == 1 or esperas_feitas % CHECKPOINT_A_CADA == 1:
                    imprimir_contornos(sem_imagem_ja=brief.sem_imagem or forcar_tipografia)

                # Ping rápido; se ok, tenta de novo sem esperar
                if tentar_ping():
                    print(dim("  ↻ PING_OK — retentando o job…"))
                    continue

                # Espera interruptível: sem tecla → continua o loop de tentativas
                permitir_tipo = (
                    job.tipo == "carrossel"
                    and not brief.sem_imagem
                    and not forcar_tipografia
                )
                res_espera = esperar_ia(
                    esperas_feitas,
                    permitir_tipografia=permitir_tipo,
                )
                if res_espera.acao == "cancelar":
                    ultimo_erro = "cancelado pelo usuário durante a espera"
                    break
                if res_espera.acao == "tipografia":
                    forcar_tipografia = True
                    print(ok("  → tipografia ligada — retentando já"))
                # pular / continuar → tenta de novo (loop não para sozinho)
                continue

        if path is None:
            print(aviso(f"  Job sem entrega: {job.label}"))
            falhas.append(job.label)
            erros_msg.append(ultimo_erro)
            tipos_fail.add(job.tipo)
            print(dim(f"  → sigo para o próximo job ({i}/{len(jobs)})"))
            continue

        absoluto = path.resolve()
        resultado = absoluto / "02_resultado"
        print(ok(f"Pronto: {job.label}"))
        print(f"  Pasta : {absoluto}")
        if resultado.is_dir():
            print(f"  Entrega: {resultado}")
        print(f"  Link : {absoluto.as_uri()}")
        salvos.append(absoluto)
        tipos_ok.add(job.tipo)

    print()

    tipos_pedidos = {j.tipo for j in jobs}
    pacote_arte_texto = "carrossel" in tipos_pedidos and "legenda" in tipos_pedidos
    incompleto = pacote_arte_texto and tipos_fail and tipos_ok
    juntou = " | ".join(erros_msg) if erros_msg else ""
    saturado = eh_saturacao_ou_cota(juntou)

    # Após saturação com tentativas: SALVA campanha (não apaga entregas parciais)
    if falhas and saturado and brief.campanha:
        gravar_campanha_pendente(
            brief.nicho,
            brief.campanha,
            tema=brief.tema,
            plataforma=brief.plataforma,
            jobs_ok=[str(p) for p in salvos],
            jobs_falha=list(falhas),
            pastas_salvas=[str(p) for p in salvos],
            motivo=juntou[:300] or "IA free saturada",
        )
        salvou_pendente = True
        print(ok("Entregas parciais mantidas — campanha salva para retomar depois."))
        imprimir_contornos(sem_imagem_ja=brief.sem_imagem or forcar_tipografia)
    elif incompleto and not saturado:
        # Incompleto por outro motivo → limpa lixo
        print(aviso("Pacote incompleto — removendo entregas parciais…"))
        for p in list(salvos):
            if remover_pasta_job(p):
                print(dim(f"  removido: {p}"))
        salvos.clear()
        tipos_ok.clear()

    if salvos:
        print(ok(f"Concluído: {len(salvos)} pasta(s) ok"))
        for p in salvos:
            print(f"  · {p}")
            print(f"    {p.as_uri()}")

    if falhas or (incompleto and not salvou_pendente):
        esgotou = any(x in juntou.lower() for x in ("429", "cota", "esgotad"))
        if esgotou:
            print(erro("AVISO: cota da API esgotada. Tente à noite ou outro dia."))
        elif saturado:
            print(aviso("AVISO: IAs em alta demanda. Campanha salva — rode `gerar` de novo depois."))
        else:
            print(aviso("AVISO: não foi possível completar com as IAs disponíveis."))
        if salvou_pendente:
            print(dim(f"  Ver: campanhas/{brief.nicho}/{brief.campanha}/pendente.md"))
        return 2

    if not salvos:
        print(erro("Nenhum job concluído."))
        if brief.campanha:
            gravar_campanha_pendente(
                brief.nicho,
                brief.campanha,
                tema=brief.tema,
                plataforma=brief.plataforma,
                jobs_falha=list(falhas) or ["(todos)"],
                motivo=juntou[:300] or "nenhuma entrega",
            )
            imprimir_contornos(sem_imagem_ja=brief.sem_imagem or forcar_tipografia)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
