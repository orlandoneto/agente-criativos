"""Post único Instagram: `gerar --estilo news|ad --formato 4x5|1x1 ...`.

Modo manual (texto nas flags) não gasta IA nenhuma. Modo IA (`--tema` sem
`--titulo`/`--headline`) usa a mesma rotação grátis de texto do resto do projeto
(FreeLLMAPI 3003 → OpenRouter free → Gemini free) numa ÚNICA chamada que traz arte + legenda.
"""

from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app import image_gen
from app.config import DATA_REGRAS, SAIDA_DIR
from app.post_render import (
    ESTILOS, FORMATOS, Marca, html_ad, html_news, normalizar_handle, render_html_png, render_html_png_checado, tamanho,
)
from app.schemas import (
    AdCarrosselIA, AdFeature, AdPostIA, AdResult, HeadlinePart, LegendaResult, NewsCarrosselIA, NewsPostIA, NewsResult,
    SlideCarrossel,
)

STOCK = ("pexels", "unsplash")


# ---------------------------------------------------------------- parsing de flags

def parse_lista(texto: str | None) -> list[str]:
    return [p.strip() for p in (texto or "").replace(";", ",").split(",") if p.strip()]


def parse_headline(texto: str) -> list[HeadlinePart]:
    """`*Texto amarelo* texto branco` → partes; asteriscos marcam destaque."""
    partes: list[HeadlinePart] = []
    for i, trecho in enumerate((texto or "").split("*")):
        t = " ".join(trecho.split())
        if t:
            partes.append(HeadlinePart(texto=t, destaque=i % 2 == 1))
    if not partes:
        raise ValueError("headline vazia")
    return partes


def parse_features(texto: str) -> list[AdFeature]:
    """`zap:Entrega imediata; gift:Bônus exclusivos` → features (ícone opcional)."""
    itens: list[AdFeature] = []
    for bloco in (texto or "").split(";"):
        bloco = bloco.strip()
        if not bloco:
            continue
        icone, sep, txt = bloco.partition(":")
        if not sep:
            icone, txt = "check", bloco
        itens.append(AdFeature(icone=icone.strip() or "check", texto=txt.strip()))
    return itens


def parse_slides(itens: list[str] | None) -> list[SlideCarrossel]:
    """`--slide "Título *destaque*|texto"` (repetível). Prefixo `icone:` opcional se for ícone Lucide."""
    from app.icones import icones_disponiveis

    conhecidos = set(icones_disponiveis())
    out: list[SlideCarrossel] = []
    for bruto in itens or []:
        bruto = (bruto or "").strip()
        if not bruto:
            continue
        icone = "check"
        cab, sep, resto = bruto.partition(":")
        if sep and cab.strip().lower() in conhecidos and "|" in resto + "|":
            icone, bruto = cab.strip().lower(), resto.strip()
        titulo, _, texto = bruto.partition("|")
        out.append(SlideCarrossel(titulo=titulo.strip(), texto=texto.strip(), icone=icone))
    return out


# ---------------------------------------------------------------- marca / fundo

def marca_de(nicho: str | None, handle: str | None, marca: str | None = None) -> Marca:
    """Brand kit (`nichos/<marca|nicho>/brand.yaml`) → Marca; sem kit, cai no perfil.md (legado)."""
    from app.brand_kit import carregar_brand_kit

    kit = carregar_brand_kit(marca or nicho)
    if kit is not None:
        return Marca.do_kit(kit, handle)
    if marca:
        raise ValueError(f"marca {marca!r} sem nichos/{marca}/brand.yaml")
    nome, fundo = "Marca", "#0B0B0F"
    if nicho:
        try:
            from app.brand import carregar_brand

            b = carregar_brand(nicho)
            nome, fundo = b.nome, b.fundo
        except FileNotFoundError:
            pass
    return Marca(nome=nome, handle=normalizar_handle(handle or "", "" if nome == "Marca" else nome), fundo=fundo)


def textos_do_post(conteudo: NewsResult | AdResult, legenda: LegendaResult | None = None) -> list[str]:
    """Todo texto que vai ao público (arte + legenda), para checar palavras proibidas."""
    if isinstance(conteudo, NewsResult):
        txt = [conteudo.tag, conteudo.titulo, conteudo.apoio]
    else:
        txt = [conteudo.pill, conteudo.headline_texto(), conteudo.badge, conteudo.cta,
               *(f.texto for f in conteudo.features)]
    if legenda is not None:
        txt += [legenda.gancho, legenda.corpo, legenda.cta, " ".join(legenda.hashtags)]
    return [t for t in txt if t]


def mesclar_hashtags(legenda: LegendaResult, padrao: list[str], limite: int = 5) -> LegendaResult:
    """Hashtags da marca primeiro, depois as da IA, sem repetir, até o limite do schema."""
    vistos: set[str] = set()
    out: list[str] = []
    for h in [*padrao, *legenda.hashtags]:
        if h.casefold() not in vistos:
            vistos.add(h.casefold())
            out.append(h)
    return legenda.model_copy(update={"hashtags": out[:limite]})


def cadeia_para(estilo: str, fonte: str, base: list[str]) -> list[str]:
    """news → foto real (Pexels/Unsplash) primeiro; ad → cena IA primeiro. `fonte` força."""
    preferir_stock = fonte == "stock" or (fonte == "auto" and estilo == "news")
    stock = [p for p in base if p in STOCK]
    ia = [p for p in base if p not in STOCK]
    return stock + ia if preferir_stock else ia + stock


@contextmanager
def _cadeia_temporaria(cadeia: list[str]):
    original = image_gen.IMAGE_CHAIN
    image_gen.IMAGE_CHAIN = cadeia
    try:
        yield
    finally:
        image_gen.IMAGE_CHAIN = original


def buscar_fundo(estilo: str, fonte: str, prompt: str, titulo: str, apoio: str, pasta: Path,
                 evitar: list[str] | None = None) -> tuple[Path | None, str]:
    res = buscar_fundo_cena(estilo, fonte, prompt, titulo, apoio, pasta, evitar=evitar)
    return res.path, res.detail


def buscar_fundo_cena(estilo: str, fonte: str, prompt: str, titulo: str, apoio: str, pasta: Path,
                      evitar: list[str] | None = None) -> "image_gen.CenaResult":
    """Busca o fundo. `evitar` = provedores já usados nesta peça → vão para o fim da fila (próximo provedor/seed)."""
    from app import ia_sessao

    cadeia = cadeia_para(estilo, fonte, list(image_gen.IMAGE_CHAIN))
    if evitar:
        cadeia = [p for p in cadeia if p not in evitar] + [p for p in cadeia if p in evitar]
        ia_sessao.provedor_imagem = None  # sticky não pode furar a troca
    with _cadeia_temporaria(cadeia):
        return image_gen.gerar_cena_com_provider(prompt, titulo, apoio, pasta / "fundo.png")


# ---------------------------------------------------------------- texto IA (grátis)

def _regras(nome: str) -> str:
    p = DATA_REGRAS / f"{nome}.md"
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def prompt_post(estilo: str, nicho: str, tema: str, kit=None, n_slides: int = 0) -> str:
    from app.nicho_loader import carregar_nicho

    ctx = carregar_nicho(nicho, "legenda")
    base = (
        "Você é editor sênior de social media para Instagram. Responda SOMENTE JSON válido.\n\n"
        + (kit.bloco_prompt() if kit is not None else "")
        + f"## Perfil do nicho\n{ctx.perfil}\n\n## Evitar\n{ctx.evitar}\n\n"
        f"## Exemplos aprovados\n{ctx.exemplos}\n\n## Regras de headline\n{_regras('headline')}\n\n"
        f"## Regras de legenda\n{ctx.regra_tipo}\n\n## Tema\n{tema.strip()}\n\n"
    )
    legenda = ('"legenda":{"gancho":"≤125 chars","corpo":"...","cta":"...",'
               '"hashtags":["#a","#b","#c"],"estrutura":"PAS"}')
    if n_slides:
        base += (
            f"CARROSSEL: a peça abaixo é a CAPA; gere também \"slides\": exatamente {n_slides} slides internos "
            "que desenvolvem o tema em sequência lógica (o último fecha com chamada para ação). Cada slide: "
            "titulo ≤ 60 chars com 1 trecho entre *asteriscos* para destaque; texto ≤ 200 chars, frases curtas; "
            "icone Lucide (zap, gift, clock, shield-check, star, rocket, users, book-open, palette, layout-grid, "
            "download, trending-up, heart, target, check). Inclua no JSON: "
            '"slides":[{"titulo":"...*destaque*...","texto":"...","icone":"check"}]\n\n'
        )
    if estilo == "news":
        return base + (
            "Gere 1 CARD DE NOTÍCIA (post único 1080x1350) + legenda.\n"
            "titulo: manchete forte, ≤ 70 caracteres, sem emoji. "
            "destaques: 1 a 2 palavras COPIADAS EXATAMENTE do titulo (as mais impactantes). "
            "tag: 1-2 palavras (ex.: URGENTE, NOVIDADE, ALERTA). apoio: 1 frase curta opcional. "
            "prompt_imagem: em INGLÊS, foto editorial realista do assunto, SEM texto/letras/logo.\n"
            '{"tag":"...","titulo":"...","destaques":["..."],"apoio":"...","prompt_imagem":"...",'
            + legenda + "}\n"
        )
    return base + (
        "Gere 1 ANÚNCIO (post único 1080x1350) + legenda.\n"
        "pill: rótulo curto (≤ 30 chars). headline_parts: 2-3 partes, alterne destaque true (amarelo) "
        "e false (branco), total ≤ 45 chars. badge: selo curto (GRÁTIS, -50%, NOVO) ou vazio. "
        "features: 3 ou 4 benefícios ≤ 40 chars com icone Lucide (zap, gift, clock, shield-check, star, "
        "rocket, users, book-open, palette, layout-grid, download, trending-up, heart, target). "
        "cta: verbo no imperativo ≤ 24 chars. prompt_imagem: em INGLÊS, cena 3D/fotográfica SEM texto.\n"
        '{"ad":{"pill":"...","headline_parts":[{"texto":"...","destaque":true},{"texto":"...","destaque":false}],'
        '"badge":"...","features":[{"icone":"zap","texto":"..."}],"cta":"...","prompt_imagem":"..."},'
        + legenda + "}\n"
    )


def _gerar_ia(estilo: str, nicho: str, tema: str, kit, n_slides: int):
    from app import gemini_client

    prompt = prompt_post(estilo, nicho, tema, kit, n_slides)
    if n_slides:
        schema = NewsCarrosselIA if estilo == "news" else AdCarrosselIA
    else:
        schema = NewsPostIA if estilo == "news" else AdPostIA

    def _extrair(r):
        conteudo = r.to_card() if estilo == "news" else r.ad
        return conteudo, r.legenda, list(getattr(r, "slides", []) or [])[: n_slides or None]

    r = gemini_client.gerar_json(prompt, schema)
    conteudo, legenda, slides = _extrair(r)
    if kit is not None:
        textos = textos_do_post(conteudo, legenda) + [t for sl in slides for t in (sl.titulo, sl.texto)]
        achadas = kit.proibidas_em(*textos)
        if achadas:
            print(f"  ↻ texto usou palavra proibida da marca ({', '.join(achadas)}) — pedindo correção…")
            r = gemini_client.corrigir_json(prompt, schema, [f"remova as palavras proibidas: {', '.join(achadas)}"], r)
            conteudo, legenda, slides = _extrair(r)
            textos = textos_do_post(conteudo, legenda) + [t for sl in slides for t in (sl.titulo, sl.texto)]
            achadas = kit.proibidas_em(*textos)
            if achadas:
                raise ValueError(f"a IA insistiu em palavras proibidas da marca: {', '.join(achadas)}")
        legenda = mesclar_hashtags(legenda, kit.hashtags_padrao)
    return conteudo, legenda, slides


def gerar_texto_ia(estilo: str, nicho: str, tema: str, kit=None) -> tuple[NewsResult | AdResult, LegendaResult]:
    """1 chamada de IA grátis (arte + legenda). Com brand kit: tom/CTA/hashtags no prompt e
    palavras proibidas conferidas — se aparecerem, pede 1 correção; se insistir, ValueError."""
    conteudo, legenda, _ = _gerar_ia(estilo, nicho, tema, kit, 0)
    return conteudo, legenda


def gerar_carrossel_ia(estilo: str, nicho: str, tema: str, kit=None, n_slides: int = 2):
    """Igual a `gerar_texto_ia`, mas a mesma chamada também traz `n_slides` slides internos."""
    return _gerar_ia(estilo, nicho, tema, kit, max(1, n_slides))


# ---------------------------------------------------------------- render + salvar

def pasta_saida(estilo: str, formato: str, titulo: str) -> Path:
    from app.campanha import slugify

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return SAIDA_DIR / "posts" / f"{stamp}_{estilo}_{formato}_{slugify(titulo)[:40]}"


def montar_html(estilo: str, formato: str, conteudo: NewsResult | AdResult, *, marca: Marca,
                fundo: Path | None = None, pb: bool = False, mockup: Path | None = None,
                cor_destaque: str | None = None, escurecer: bool = False) -> str:
    if estilo == "news":
        assert isinstance(conteudo, NewsResult)
        return html_news(conteudo, formato=formato, fundo=fundo, pb=pb, marca=marca, cor_destaque=cor_destaque,
                         escurecer=escurecer)
    assert isinstance(conteudo, AdResult)
    return html_ad(conteudo, formato=formato, fundo=fundo, mockup=mockup, marca=marca, escurecer=escurecer)


def safe_zone(formato: str) -> dict | None:
    """Zona segura do formato (px livres de texto-chave no topo/base) ou None."""
    from app.post_render import SAFE_ZONES

    return SAFE_ZONES.get(formato)


def renderizar_post(estilo: str, formato: str, conteudo: NewsResult | AdResult, destino_png: Path, *,
                    marca: Marca, fundo: Path | None = None, pb: bool = False, mockup: Path | None = None,
                    cor_destaque: str | None = None, escurecer: bool = False) -> tuple[Path, dict]:
    """HTML → PNG + pré-checagem determinística (sem IA). `escurecer` reforça o véu (contraste)."""
    if estilo not in ESTILOS:
        raise ValueError(f"estilo inválido: {estilo!r}")
    largura, altura = tamanho(formato)
    html = montar_html(estilo, formato, conteudo, marca=marca, fundo=fundo, pb=pb,
                       mockup=mockup, cor_destaque=cor_destaque, escurecer=escurecer)
    return render_html_png_checado(html, largura, altura, destino_png, safe=safe_zone(formato))


def salvar_extras(png: Path, estilo: str, formato: str, conteudo: NewsResult | AdResult, *, marca: Marca,
                  fundo: Path | None = None, pb: bool = False, mockup: Path | None = None,
                  legenda: LegendaResult | None = None, precheck: dict | None = None,
                  revisao: dict | None = None, proibidas: list[str] | None = None) -> None:
    largura, altura = tamanho(formato)
    pasta = png.parent
    dados = {
        "estilo": estilo, "formato": formato, "tamanho": [largura, altura],
        "conteudo": conteudo.model_dump(), "marca": marca.para_json(),
        "fundo": str(fundo) if fundo else None, "pb": pb,
        "mockup": str(mockup) if mockup else None,
    }
    if fundo and fundo.with_suffix(".json").is_file():
        dados["fundo_meta"] = json.loads(fundo.with_suffix(".json").read_text(encoding="utf-8"))
    if proibidas:
        dados["palavras_proibidas_encontradas"] = proibidas
    if precheck is not None:
        dados["precheck"] = {k: v for k, v in precheck.items() if k != "contraste"}
    if revisao is not None:
        dados["revisao"] = {k: revisao.get(k) for k in ("nota_final", "aprovado", "precisa_revisao", "limiar",
                                                         "motivo_parada", "melhor_tentativa")}
    (pasta / f"{png.stem}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    if legenda is not None:
        texto = legenda.legenda_completa()
        cred = (dados.get("fundo_meta") or {}).get("atribuicao")
        if cred:
            texto += f"\n\n📷 {cred}"
        (pasta / "legenda.md").write_text(texto + "\n", encoding="utf-8")


def gerar_post(estilo: str, formato: str, conteudo: NewsResult | AdResult, destino_png: Path, *,
               marca: Marca, fundo: Path | None = None, pb: bool = False, mockup: Path | None = None,
               cor_destaque: str | None = None, legenda: LegendaResult | None = None,
               salvar_extras: bool = True) -> Path:
    """Render único (sem IA de revisão). A pré-checagem determinística vai no post.json."""
    png, pre = renderizar_post(estilo, formato, conteudo, destino_png, marca=marca, fundo=fundo, pb=pb,
                               mockup=mockup, cor_destaque=cor_destaque)
    if salvar_extras:
        _salvar_extras(png, estilo, formato, conteudo, marca=marca, fundo=fundo, pb=pb, mockup=mockup,
                       legenda=legenda, precheck=pre)
    return png


_salvar_extras = salvar_extras


def renderizar_slides(estilo: str, slides: list[SlideCarrossel], pasta: Path, *, marca: Marca,
                      fundo: Path | None = None, cta: str = "", cor_destaque: str | None = None) -> list[tuple[Path, dict]]:
    """Slides internos (2..N+1) com o fundo da capa desfocado + pré-checagem de cada um."""
    from app.post_render import html_slide

    largura, altura = tamanho("carrossel")
    total = 1 + len(slides)
    out = []
    for i, sl in enumerate(slides, start=2):
        html = html_slide(sl, numero=i, total=total, estilo=estilo, fundo=fundo, marca=marca, cta=cta,
                          cor_destaque=cor_destaque)
        out.append(render_html_png_checado(html, largura, altura, pasta / f"slide_{i:02d}.png"))
    return out


def main_post(args) -> int:
    """Entrada do CLI para `--estilo`. Retorna exit code."""
    from app import ia_sessao

    estilo, formato = args.estilo, args.formato or "4x5"
    if formato not in FORMATOS:
        print(f"ERRO: --formato {formato} inválido (use {', '.join(FORMATOS)})")
        return 1
    ia_sessao.reset()
    from app.brand_kit import BrandKitInvalido, carregar_brand_kit

    slug_marca = getattr(args, "marca", None)
    try:
        marca = marca_de(args.nicho, args.handle, slug_marca)
        kit = carregar_brand_kit(slug_marca or args.nicho)
    except (BrandKitInvalido, ValueError) as exc:
        print(f"ERRO de marca: {exc}")
        return 1
    if kit is not None:
        print(f"Marca: {kit.nome} {marca.handle} (brand kit {kit.slug})")
    legenda: LegendaResult | None = None

    carrossel = formato == "carrossel"
    slides: list[SlideCarrossel] = []
    n_slides = max(1, min(9, int(getattr(args, "slides_n", None) or 2)))
    manual = bool(args.titulo) if estilo == "news" else bool(args.headline)
    try:
        if carrossel and manual:
            slides = parse_slides(getattr(args, "slide", None))
            if not slides:
                print('ERRO: carrossel manual precisa de pelo menos um --slide "Título *destaque*|texto".')
                return 1
        if manual:
            if estilo == "news":
                conteudo: NewsResult | AdResult = NewsResult(
                    tag=args.tag or "Notícia", titulo=args.titulo,
                    destaques=parse_lista(args.destaques), apoio=args.apoio or "")
            else:
                conteudo = AdResult(
                    pill=args.pill or "Oferta", headline_parts=parse_headline(args.headline),
                    badge=args.badge or "", features=parse_features(args.features or ""),
                    cta=args.cta or (kit.cta.texto_padrao if kit else "Saiba mais"))
        else:
            if not (args.tema or "").strip() or not args.nicho:
                print("ERRO: modo IA precisa de --nicho e --tema (ou passe --titulo/--headline para modo manual).")
                return 1
            if carrossel:
                print(f"Gerando texto com IA grátis (1 chamada: capa + {n_slides} slides + legenda)…")
                conteudo, legenda, slides = gerar_carrossel_ia(estilo, args.nicho, args.tema, kit, n_slides)
            else:
                print("Gerando texto com IA grátis (1 chamada: arte + legenda)…")
                conteudo, legenda = gerar_texto_ia(estilo, args.nicho, args.tema, kit)
    except ValueError as exc:
        print(f"ERRO de conteúdo: {exc}")
        return 1
    textos_slides = [t for sl in slides for t in (sl.titulo, sl.texto)]
    proibidas = kit.proibidas_em(*textos_do_post(conteudo, legenda), *textos_slides) if kit is not None else []
    if proibidas:
        print(f"AVISO: o texto tem palavras proibidas pela marca {kit.nome}: {', '.join(proibidas)} "
              "(modo manual: sigo, mas revise)")

    titulo_ref = conteudo.titulo if isinstance(conteudo, NewsResult) else conteudo.headline_texto()
    if args.saida and str(args.saida).lower().endswith(".png"):
        destino = Path(args.saida)
    else:
        pasta = Path(args.saida) if args.saida else pasta_saida(estilo, formato, titulo_ref)
        destino = pasta / ("slide_01.png" if carrossel else "post.png")
    destino.parent.mkdir(parents=True, exist_ok=True)

    mockup = Path(args.mockup) if args.mockup else None
    if mockup and not mockup.is_file():
        print(f"ERRO: --mockup não encontrado: {mockup}")
        return 1

    fundo: Path | None = None
    if args.fundo:
        origem = Path(args.fundo)
        if not origem.is_file():
            print(f"ERRO: --fundo não encontrado: {origem}")
            return 1
        fundo = destino.parent / f"fundo{origem.suffix.lower()}"
        if origem.resolve() != fundo.resolve():
            shutil.copyfile(origem, fundo)
            meta = origem.with_suffix(".json")
            if meta.is_file():
                shutil.copyfile(meta, fundo.with_suffix(".json"))

    gerar_fundo = None
    if not args.fundo and args.buscar_fundo:
        apoio = conteudo.apoio if isinstance(conteudo, NewsResult) else conteudo.pill
        prompt = getattr(args, "prompt_fundo", None) or conteudo.prompt_imagem
        if formato in ("9x16", "capa-reels") and prompt:
            prompt += ". Vertical 9:16 full-screen composition, main subject in the middle, calm top and bottom areas"

        def gerar_fundo(n: int, usados: list[str], pasta_t: Path):
            print(f"Buscando fundo ({args.fonte_fundo}){' — tentativa ' + str(n) if n > 1 else ''}…")
            res = buscar_fundo_cena(estilo, args.fonte_fundo, prompt, titulo_ref, apoio, pasta_t, evitar=usados)
            print(f"  fundo: {'ok via ' + res.provider if res.path else 'sem imagem (fallback gradiente)'}"
                  f" — {res.detail[:160]}")
            return res.path, res.provider

    from app import revisao as rv

    sem_revisao = bool(getattr(args, "sem_revisao", False))
    cor = getattr(args, "cor_destaque", None)

    def renderizar(f: Path | None, dst: Path, escurecer: bool = False):
        return renderizar_post(estilo, formato, conteudo, dst, marca=marca, fundo=f, pb=args.pb,
                               mockup=mockup, cor_destaque=cor, escurecer=escurecer)

    if not sem_revisao:
        print("Revisando (pré-checagem local + IA de visão grátis)…")
    res = rv.ciclo_revisao(
        pasta=destino.parent, renderizar=renderizar, gerar_fundo=gerar_fundo, fundo_fixo=fundo,
        limiar=float(getattr(args, "revisao_limiar", None) or rv.LIMIAR_PADRAO),
        tentativas_extra=int(rv.TENTATIVAS_PADRAO if getattr(args, "revisao_tentativas", None) is None
                             else args.revisao_tentativas),
        prazo_s=float(getattr(args, "revisao_prazo", None) or rv.PRAZO_PADRAO),
        revisao_ia=not sem_revisao, contexto=f"{estilo} {formato}: {titulo_ref}",
    )
    png = rv.promover_melhor(res, destino)
    melhor = res.melhor
    fundo_final = None
    for cand in sorted(destino.parent.glob("fundo.*")):
        if cand.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            fundo_final = cand
            break
    salvar_extras(png, estilo, formato, conteudo, marca=marca, fundo=fundo_final, pb=args.pb, mockup=mockup,
                  legenda=legenda, precheck=melhor.precheck if melhor else None, revisao=res.to_dict(),
                  proibidas=proibidas)
    if carrossel:
        cta_final = (conteudo.cta if isinstance(conteudo, AdResult) else (getattr(args, "cta", None)
                     or (kit.cta.texto_padrao if kit else "")))
        extras = renderizar_slides(estilo, slides, destino.parent, marca=marca, fundo=fundo_final,
                                   cta=cta_final, cor_destaque=cor)
        total = 1 + len(extras)
        rel_path = destino.parent / f"{destino.stem}.revisao.json"
        rel = json.loads(rel_path.read_text(encoding="utf-8"))
        rel["slides_precheck"] = [{"slide": i + 2, **{k: v for k, v in pre.items() if k != "contraste"}}
                                  for i, (_, pre) in enumerate(extras)]
        rel_path.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
        (destino.parent / "carrossel.json").write_text(json.dumps({
            "estilo": estilo, "total": total, "capa": destino.name,
            "slides": [sl.model_dump() for sl in slides], "arquivos": [destino.name] + [p.name for p, _ in extras],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        alertas = [i + 2 for i, (_, pre) in enumerate(extras) if not pre.get("ok", True)]
        print(f"Carrossel: {total} slides em {destino.parent}" + (f" — pré-checagem com alertas nos slides {alertas}"
                                                                   if alertas else ""))
    print(f"Pronto: {png.resolve()}")
    if legenda is not None:
        print(f"Legenda: {png.parent / 'legenda.md'}")
    if melhor:
        if sem_revisao:
            print(f"Pré-checagem: {'ok' if melhor.precheck.get('ok') else 'com alertas'} "
                  f"(contraste mín. {melhor.precheck.get('contraste_min')}) — revisão IA desligada (--sem-revisao)")
        else:
            selo = "APROVADO" if not res.precisa_revisao else "PRECISA REVISÃO"
            print(f"Revisão: nota {melhor.nota:.1f}/10 (limiar {res.limiar:g}) — {selo} · {res.motivo_parada}")
        print(f"Relatório: {png.parent / (png.stem + '.revisao.json')}")
    print("Revise antes de postar — o agente NÃO publica sozinho.")
    return 0


def adicionar_flags(parser) -> None:
    g = parser.add_argument_group("Post único Instagram (news/ad)")
    g.add_argument("--estilo", choices=list(ESTILOS), default=None, help="news = card de notícia; ad = anúncio")
    g.add_argument("--formato", choices=list(FORMATOS), default=None,
                   help="4x5 (1080x1350, padrão) | 1x1 | 9x16 (Stories/Reels 1080x1920) | capa-reels | carrossel (capa + slides 4:5)")
    g.add_argument("--slide", action="append", default=None,
                   help="[carrossel manual] 'Título *destaque*|texto' (repita; prefixo 'icone:' opcional no ad)")
    g.add_argument("--slides-n", type=int, default=None, help="[carrossel IA] quantos slides internos além da capa (padrão 2)")
    g.add_argument("--titulo", default=None, help="[news] manchete (modo manual)")
    g.add_argument("--destaques", default=None, help="[news] palavras do título em cor, separadas por vírgula")
    g.add_argument("--tag", default=None, help="[news] texto da tarja vermelha")
    g.add_argument("--apoio", default=None, help="[news] linha de apoio")
    g.add_argument("--pb", action="store_true", help="[news] foto em preto e branco")
    g.add_argument("--cor-destaque", default=None, help="[news] amarelo|vermelho|#HEX (padrão: destaque da marca)")
    g.add_argument("--headline", default=None, help="[ad] '*parte amarela* parte branca' (modo manual)")
    g.add_argument("--pill", default=None, help="[ad] rótulo da pílula")
    g.add_argument("--badge", default=None, help="[ad] selo redondo (ex.: GRÁTIS)")
    g.add_argument("--features", default=None, help="[ad] 'icone:texto; icone:texto' (3 a 4)")
    g.add_argument("--cta", default=None, help="[ad] texto do botão")
    g.add_argument("--mockup", default=None, help="[ad] PNG do produto (transparente de preferência)")
    g.add_argument("--handle", default=None, help="@ da marca no rodapé (sobrepõe o do brand kit)")
    g.add_argument("--marca", default=None, help="slug do brand kit em nichos/<slug>/brand.yaml (padrão: o --nicho)")
    g.add_argument("--fundo", default=None, help="imagem local de fundo (não gasta IA)")
    g.add_argument("--buscar-fundo", action="store_true", help="busca fundo na IMAGE_CHAIN (free)")
    g.add_argument("--prompt-fundo", default=None, help="prompt EN da cena (com --buscar-fundo); sem texto na imagem")
    g.add_argument("--fonte-fundo", choices=["auto", "stock", "ia"], default="auto",
                   help="auto: news→foto real, ad→cena IA")
    g.add_argument("--saida", default=None, help="pasta ou arquivo .png de saída")
    r = parser.add_argument_group("Revisão automática (pré-checagem + IA de visão grátis)")
    r.add_argument("--sem-revisao", action="store_true", help="desliga a revisão por IA e as novas tentativas")
    r.add_argument("--revisao-limiar", type=float, default=None, help="nota mínima 0-10 (padrão 7 ou REVISAO_LIMIAR)")
    r.add_argument("--revisao-tentativas", type=int, default=None,
                   help="quantas vezes refazer o fundo se a nota ficar baixa (padrão 2)")
    r.add_argument("--revisao-prazo", type=float, default=None, help="prazo total da revisão em segundos (padrão 240)")
