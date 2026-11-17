"""Modo conversa da CLI: pergunta o que falta (estilo entrevista simples)."""

from __future__ import annotations

from dataclasses import dataclass

from app.campanha import (
    garantir_estrutura,
    gravar_ideia,
    importar_referencias,
    parse_caminhos_imagens,
    slugify,
    tem_skill,
)
from app.cli_style import aviso, destaque, dim, erro, ok, paint, titulo, C
from app.config import NICHOS_DIR
from app.plataformas import (
    TIPOS_PIPELINE,
    FormatoPlataforma,
    Plataforma,
    expandir_escolhas,
    get_formato,
    get_plataforma,
    listar_plataformas,
    parse_escolha_formatos,
)

TIPOS = TIPOS_PIPELINE  # compat: bio | legenda | carrossel
NICHO_FALLBACK = "exemplo_tech"


class WizardCancel(Exception):
    """Usuário pediu sair (0 / sair / q) — não gera."""


def _eh_sair(raw: str) -> bool:
    return (raw or "").strip().lower() in {
        "0",
        "sair",
        "exit",
        "q",
        "quit",
        "cancelar",
        "cancela",
    }


@dataclass(frozen=True)
class JobFormato:
    """Um job do motor (pacote da rede pode virar 1 ou 2 jobs: arte + texto)."""

    formato: str
    tipo: str  # bio | legenda | carrossel
    video: bool = False
    label: str = ""
    max_cenas: int | None = None  # 1 = post único; None = usa o do brief


@dataclass(frozen=True)
class Brief:
    """Contrato único wizard / CLI flags / (futuro) API."""

    nicho: str
    tipo: str
    tema: str
    contexto: str = ""
    campanha: str = ""
    plataforma: str = "instagram"
    formato: str = ""  # id do formato (ou vários separados por vírgula)
    jobs: tuple[JobFormato, ...] = ()
    sem_imagem: bool = False
    max_cenas: int = 1
    video: bool = False

    def jobs_efetivos(self) -> tuple[JobFormato, ...]:
        if self.jobs:
            return self.jobs
        return (
            JobFormato(
                formato=self.formato or self.tipo,
                tipo=self.tipo,
                video=self.video,
                label=self.formato or self.tipo,
                max_cenas=None,
            ),
        )

    def texto_campanha(self) -> str:
        """Tema + contexto + plataforma alvo para o pipeline."""
        tema = (self.tema or "").strip()
        ctx = (self.contexto or "").strip()
        corpo = f"{tema} — {ctx}" if tema and ctx else (tema or ctx)
        plat = (self.plataforma or "").strip()
        fmts = ", ".join(j.formato for j in self.jobs_efetivos()) or self.formato or self.tipo
        if plat and corpo:
            return f"Plataforma alvo: {plat}. Formato: {fmts}. {corpo}"
        return corpo


def listar_nichos() -> list[str]:
    if not NICHOS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in NICHOS_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "perfil.md").is_file()
    )


def formatar_lista_nichos(nichos: list[str], colunas: int = 2) -> str:
    """Lista numerada; em 2 colunas quando a lista fica grande."""
    itens = [
        f"{paint(f'{i})', C.bold, C.cyan)} {slug}"
        for i, slug in enumerate(nichos, start=1)
    ]
    if len(itens) <= 8 or colunas < 2:
        return "\n".join(f"  {x}" for x in itens)
    # duas colunas alinhadas
    mid = (len(itens) + 1) // 2
    esq, dir_ = itens[:mid], itens[mid:]
    largura = max(len(_strip_ansi(x)) for x in esq) + 4
    linhas = []
    for i in range(mid):
        a = esq[i]
        b = dir_[i] if i < len(dir_) else ""
        pad = " " * max(1, largura - len(_strip_ansi(a)))
        linhas.append(f"  {a}{pad}{b}".rstrip())
    return "\n".join(linhas)


def _strip_ansi(texto: str) -> str:
    import re

    return re.sub(r"\033\[[0-9;]*m", "", texto)


def buscar_nichos(termo: str, nichos: list[str]) -> list[str]:
    """Filtra slugs que contêm o termo (ex.: cobra → cobras_br)."""
    t = (termo or "").strip().lower()
    if not t:
        return []
    return [n for n in nichos if t in n.lower()]


def resolver_nicho(raw: str, nichos: list[str]) -> str | None:
    t = (raw or "").strip()
    if not t:
        return None
    if t in nichos:
        return t
    if t.isdigit():
        i = int(t)
        if 1 <= i <= len(nichos):
            return nichos[i - 1]
    return None


def resolver_tipo(raw: str) -> str | None:
    """Resolve tipo do pipeline (legado / flags). Preferir fluxo por plataforma."""
    t = (raw or "").strip().lower()
    if not t:
        return None
    if t in TIPOS:
        return t
    if t.isdigit():
        i = int(t)
        if 1 <= i <= len(TIPOS):
            return TIPOS[i - 1]
    aliases = {
        "carousel": "carrossel",
        "post": "legenda",
        "caption": "legenda",
        "reels": "carrossel",
        "video": "carrossel",
    }
    return aliases.get(t)


def _mostrar_formatos(plat: Plataforma) -> None:
    print(titulo(f"O que você pode enviar no {plat.nome}"))
    print(dim("  ✓ gera agora   ·   ○ em breve (ainda não no motor)"))
    print()
    for i, fmt in enumerate(plat.formatos, start=1):
        if fmt.disponivel:
            badge = ok("✓")
        else:
            badge = dim("○")
        num = paint(f"{i})", C.bold, C.cyan)
        print(f"  {num} {badge} {fmt.label}")
        print(dim(f"       {fmt.descricao}"))
    print()
    print(f"  {paint('t', C.bold, C.green)}) Todos os ✓ disponíveis")
    print(f"  {paint('0', C.yellow)}) Sair  ·  {paint('v', C.yellow)}) Voltar (trocar plataforma)")
    print()
    print(dim("  Dica: t = tudo que dá pra gerar agora · ou 2 · ou 1,3"))
    print(dim("  Feed: escolha 1 imagem OU carrossel (os dois são post no feed)"))
    print()


def _escolher_plataforma_e_formatos(
    *,
    plataforma: str | None = None,
    tipo: str | None = None,
) -> tuple[Plataforma, list[FormatoPlataforma]]:
    """Humano: rede → lista do que pode enviar → um, vários ou todos (✓)."""
    plats = listar_plataformas()

    plat: Plataforma | None = get_plataforma(plataforma) if plataforma else None
    while plat is None:
        print(titulo("Plataforma"))
        print(dim("Escolha onde o criativo vai ser publicado."))
        for i, p in enumerate(plats, start=1):
            print(f"  {paint(str(i), C.bold, C.cyan)}) {p.nome}")
        print(f"  {paint('0', C.yellow)}) Sair")
        print()
        raw = _ask("Plataforma", "1")
        if _eh_sair(raw):
            raise WizardCancel()
        plat = get_plataforma(raw)
        if plat is None:
            print(erro("  Digite 1–4 (Instagram, TikTok, Facebook, YouTube) ou 0 sair."))
        else:
            print(ok(f"  → {plat.nome}"))
            print()

    # CLI com --tipo: um formato só
    if tipo:
        fmt = get_formato(plat, tipo)
        if fmt and fmt.pipeline:
            return plat, [fmt]

    while True:
        _mostrar_formatos(plat)
        raw = _ask("Escolha", "t")
        if _eh_sair(raw):
            raise WizardCancel()
        if raw.strip().lower() in {"v", "voltar"}:
            return _escolher_plataforma_e_formatos(plataforma=None, tipo=None)

        escolhidos = parse_escolha_formatos(raw, plat)
        if not escolhidos:
            print(erro("  Use t (todos), um número com ✓, ou vários: 1,2,4"))
            print(aviso("  Itens ○ (em breve) não entram — escolha só ✓."))
            continue

        nomes = ", ".join(f.label for f in escolhidos)
        print(ok(f"  → {len(escolhidos)} formato(s): {nomes}"))
        return plat, escolhidos


def _ask(prompt: str, default: str = "") -> str:
    sufixo = f" [{default}]" if default else ""
    try:
        valor = input(f"{paint('›', C.cyan)} {prompt}{dim(sufixo)}: ").strip()
    except EOFError as exc:
        raise SystemExit(130) from exc
    except KeyboardInterrupt as exc:
        print()
        raise SystemExit(130) from exc
    return valor or default


def _ask_sim_nao(prompt: str, default_sim: bool = True) -> bool:
    padrao = "s" if default_sim else "n"
    resp = _ask(f"{prompt} (s/n)", padrao).lower()
    if resp in {"s", "sim", "y", "yes"}:
        return True
    if resp in {"n", "nao", "não", "no"}:
        return False
    return default_sim


def _escolher_nicho_interativo(nichos: list[str]) -> tuple[str, str]:
    """
    Retorna (slug, contexto_inicial).
    1 lista · 2 buscar · 3 descrever · 0 sair
    """
    while True:
        print(titulo("Como quer escolher o nicho?"))
        print(f"  {paint('1', C.bold, C.cyan)}) Ver lista e escolher")
        print(f"  {paint('2', C.bold, C.cyan)}) Buscar por palavra  {dim('(ex.: cobra)')}")
        print(f"  {paint('3', C.bold, C.cyan)}) Descrever agora   {dim('(ainda sem perfil salvo)')}")
        print(f"  {paint('0', C.bold, C.yellow)}) Sair")
        print()

        modo = _ask("Opção", "1")
        if _eh_sair(modo):
            raise WizardCancel()
        if modo in {"1", "lista", "listar", "l"}:
            escolhido = _nicho_pela_lista(nichos)
            if escolhido is None:
                continue  # voltou / saiu da lista → menu de novo
            return escolhido, ""
        if modo in {"2", "buscar", "busca", "b", "termo"}:
            resultado = _nicho_por_termo(nichos)
            if resultado is None:
                continue
            return resultado
        if modo in {"3", "descrever", "novo", "livre", "d"}:
            resultado = _nicho_livre(nichos)
            if resultado is None:
                continue
            return resultado
        print(erro("  Digite 1, 2, 3 ou 0 para sair."))


def _nicho_pela_lista(nichos: list[str]) -> str | None:
    """None = voltar ao menu. WizardCancel = sair do gerar."""
    print()
    print(titulo("Nichos salvos"))
    print(formatar_lista_nichos(nichos))
    print(f"  {paint('0', C.bold, C.yellow)}) Sair")
    print(f"  {paint('v', C.bold, C.yellow)}) Voltar")
    print()
    while True:
        raw = _ask("Número do nicho (0=sair, v=voltar)", "1")
        if _eh_sair(raw):
            raise WizardCancel()
        if raw.strip().lower() in {"v", "voltar", "b", "back"}:
            return None
        hit = resolver_nicho(raw, nichos)
        if hit:
            print(ok(f"  → perfil: {hit}"))
            return hit
        print(erro(f"  Use 1–{len(nichos)}, ou 0 sair, ou v voltar."))


def _nicho_por_termo(nichos: list[str]) -> tuple[str, str] | None:
    print()
    print(dim("Palavra do perfil (ex.: saude). 0=sair · v=voltar"))
    while True:
        termo = _ask("Buscar")
        if _eh_sair(termo):
            raise WizardCancel()
        if termo.strip().lower() in {"v", "voltar"}:
            return None
        if not termo:
            print(aviso("  Digite uma palavra, v=voltar ou 0=sair."))
            continue
        hits = buscar_nichos(termo, nichos)
        if len(hits) == 1:
            print(ok(f"  → achou: {hits[0]}"))
            return hits[0], ""
        if len(hits) > 1:
            print(titulo("Vários perfis:"))
            print(formatar_lista_nichos(hits))
            print(f"  {paint('0', C.yellow)}) Sair  ·  {paint('v', C.yellow)}) Voltar")
            while True:
                raw = _ask("Número", "1")
                if _eh_sair(raw):
                    raise WizardCancel()
                if raw.strip().lower() in {"v", "voltar"}:
                    return None
                hit = resolver_nicho(raw, hits)
                if hit:
                    print(ok(f"  → perfil: {hit}"))
                    return hit, ""
                print(erro(f"  1–{len(hits)}, 0 sair, v voltar."))
        print(aviso(f"  Nenhum perfil com “{termo}”."))
        if _ask_sim_nao("Usar como descrição livre?", True):
            fallback = NICHO_FALLBACK if NICHO_FALLBACK in nichos else nichos[0]
            print(dim(f"  Perfil base: {fallback}"))
            print(ok(f"  → descrição: {termo}"))
            return fallback, termo
        print(dim("  Outra palavra, v=voltar ou 0=sair."))


def _nicho_livre(nichos: list[str]) -> tuple[str, str] | None:
    print()
    print(dim("Ex.: cobras do Brasil. 0=sair · v=voltar"))
    while True:
        desc = _ask("Descrição do nicho")
        if _eh_sair(desc):
            raise WizardCancel()
        if desc.strip().lower() in {"v", "voltar"}:
            return None
        if desc:
            fallback = NICHO_FALLBACK if NICHO_FALLBACK in nichos else nichos[0]
            print(dim(f"  Perfil base: {fallback}"))
            print(ok(f"  → descrição: {desc}"))
            return fallback, desc
        print(erro("  Escreva algo, ou 0 sair / v voltar."))


def coletar_brief(
    *,
    nicho: str | None = None,
    tipo: str | None = None,
    tema: str | None = None,
    contexto: str | None = None,
    campanha: str | None = None,
    ideia: str | None = None,
    imagens: str | None = None,
    plataforma: str | None = None,
    sem_imagem: bool | None = None,
    max_cenas: int | None = None,
    video: bool | None = None,
) -> Brief | None:
    """
    Pergunta só o que falta. Retorna None se o usuário cancelar na confirmação.
    """
    print(titulo("Montar criativo"))
    print(dim("Enter = aceitar o padrão entre colchetes."))
    print()

    nichos = listar_nichos()
    if not nichos:
        print(erro("ERRO: nenhum nicho em nichos/ (falta perfil.md)."))
        raise SystemExit(1)

    contexto_seed = ""
    if not nicho:
        try:
            nicho, contexto_seed = _escolher_nicho_interativo(nichos)
        except WizardCancel:
            print(aviso("Saindo. Nada foi gerado."))
            return None
        print()
    else:
        if nicho not in nichos:
            print(erro(f"Nicho “{nicho}” não existe. Use um de: {', '.join(nichos)}"))
            raise SystemExit(1)

    # Plataforma → o que pode enviar → um / vários / todos
    precisa_plataforma = plataforma is None or tipo is None
    fmts: list[FormatoPlataforma] = []
    if precisa_plataforma:
        try:
            plat, fmts = _escolher_plataforma_e_formatos(plataforma=plataforma, tipo=tipo)
        except WizardCancel:
            print(aviso("Saindo. Nada foi gerado."))
            return None
        print()
        plataforma = plat.id
    else:
        plat = get_plataforma(plataforma) or listar_plataformas()[0]
        plataforma = plat.id
        fmt = get_formato(plat, tipo or "bio")
        if fmt:
            fmts = [fmt]
        else:
            fmts = [
                FormatoPlataforma(
                    id=tipo or "bio",
                    label=tipo or "bio",
                    descricao="",
                    pipeline=resolver_tipo(tipo) or "bio",
                    disponivel=True,
                )
            ]

    tema = (tema or "").strip()
    if not tema:
        print(titulo("Tema"))
        while True:
            tema = _ask("Tema (ideia principal)")
            if tema:
                break
            print(erro("  Ex.: água pela manhã · promoção de terça"))
        print()

    if contexto is None:
        padrao_ctx = contexto_seed
        dica = "detalhe livre — Enter pula" if not padrao_ctx else "pode complementar"
        print(titulo("Contexto"))
        print(dim(f"  Ex.: cobras do Brasil, tom educativo. ({dica})"))
        extra = _ask("Contexto", padrao_ctx)
        contexto = extra.strip()
        print()
    else:
        contexto = (contexto or "").strip() or contexto_seed

    if campanha is None:
        print(titulo("Campanha (pasta)"))
        print(dim("  campanhas/<nicho>/<campanha>/skill + saida/<plataforma>/<formato>/"))
        while True:
            campanha_raw = _ask("Nome da campanha", slugify(tema)[:32] or "campanha")
            if campanha_raw.strip():
                campanha = slugify(campanha_raw)
                break
            print(erro("  Ex.: cobras_marco · agua_manha"))
        print()
    else:
        campanha = slugify(campanha) if str(campanha).strip() else ""

    if campanha:
        garantir_estrutura(nicho, campanha, tema=tema, contexto=contexto)
        print(ok(f"  → pasta: campanhas/{slugify(nicho)}/{campanha}/"))

        # Skill de CONTEÚDO (ideia + imagens) — opcional; senão usa só o nicho escolhido
        print(titulo("Skill de conteúdo (opcional)"))
        print(dim("  NÃO é skill do Cursor. É ideia central + imagens para acertar o criativo."))
        print(dim("  Se pular (n), gera só com perfil do nicho + tema/formatos escolhidos."))
        quer_skill = False
        if ideia is not None or imagens is not None:
            quer_skill = bool((ideia or "").strip() or (imagens or "").strip())
        else:
            quer_skill = _ask_sim_nao("Fornecer skill desta campanha (ideia + imagens)?", False)

        if quer_skill:
            if ideia is None:
                print(dim("  Cole a ideia central (1–5 frases). Enter vazio = só imagens."))
                ideia = _ask("Ideia central", "")
            if (ideia or "").strip():
                gravar_ideia(nicho, campanha, ideia.strip())
                print(ok("  → skill/ideia.md"))
            if imagens is None:
                print(dim("  Caminhos (; ,) ou pasta de imagens. Enter = pular."))
                imagens = _ask("Imagens / pasta", "")
            caminhos = parse_caminhos_imagens(imagens or "")
            if caminhos:
                salvos = importar_referencias(nicho, campanha, caminhos)
                print(ok(f"  → {len(salvos)} arquivo(s) em skill/referencias/"))
            if tem_skill(nicho, campanha):
                print(ok("  Skill de conteúdo pronta."))
            else:
                print(aviso("  Nenhuma ideia/imagem — seguindo só com o nicho."))
        else:
            print(dim("  Sem skill → nicho + tema."))
        print()

    specs = expandir_escolhas(fmts)
    jobs = tuple(
        JobFormato(
            formato=s.formato,
            tipo=s.tipo,
            video=s.video,
            label=s.label,
            max_cenas=s.max_cenas,
        )
        for s in specs
    )
    if not jobs:
        print(erro("Nenhum formato gerável selecionado."))
        return None
    print(dim(f"  Motor vai rodar {len(jobs)} job(s) (pacotes expandem arte + texto)."))
    print()

    usar_sem_imagem = bool(sem_imagem) if sem_imagem is not None else False
    cenas = 1 if max_cenas is None else max(0, int(max_cenas))
    precisa_arte = any(j.tipo == "carrossel" for j in jobs)

    if precisa_arte:
        print(titulo("Opções de arte (carrossel / reels / vídeo)"))
        print(dim("  Free Gemini satura de manhã/pico; à noite costuma ir melhor."))
        print(dim("  Só tipografia = `--sem-imagem` (menos carga; ainda usa Gemini no texto)."))
        if sem_imagem is None:
            usar_sem_imagem = not _ask_sim_nao("Gerar cenas com IA (gasta cota)?", True)
        if max_cenas is None and not usar_sem_imagem:
            raw = _ask("Máximo de cenas", "1")
            try:
                cenas = max(0, int(raw))
            except ValueError:
                cenas = 1
        # vídeo: jobs com forcar_video já ligam; demais carrossel perguntam uma vez
        if video is None and any(j.tipo == "carrossel" and not j.video for j in jobs):
            extra_vid = _ask_sim_nao("Nos carrosséis sem Reels, montar vídeo 9:16 também?", False)
            if extra_vid:
                jobs = tuple(
                    JobFormato(j.formato, j.tipo, True, j.label, j.max_cenas)
                    if j.tipo == "carrossel" and not j.video
                    else j
                    for j in jobs
                )
        print()

    if video is True:
        jobs = tuple(
            JobFormato(j.formato, j.tipo, True, j.label, j.max_cenas)
            if j.tipo == "carrossel"
            else j
            for j in jobs
        )

    print(destaque("Resumo"))
    print(f"  Nicho      : {ok(nicho)}")
    print(f"  Campanha   : {ok(campanha) if campanha else dim('(saida/ legado)')}")
    print(f"  Plataforma : {ok(plataforma)}")
    for j in jobs:
        print(f"  Formato     : {j.label} → motor {j.tipo}" + (" +vídeo" if j.video else ""))
    print(f"  Tema       : {tema}")
    print(f"  Contexto   : {contexto or dim('(nenhum)')}")
    if precisa_arte:
        print(f"  Imagem     : {'não' if usar_sem_imagem else f'sim (máx {cenas})'}")
    print()

    if not _ask_sim_nao("Gerar agora?", True):
        print(aviso("Cancelado."))
        return None

    primeiro = jobs[0]
    return Brief(
        nicho=nicho,
        tipo=primeiro.tipo,
        tema=tema,
        contexto=contexto,
        campanha=campanha or "",
        plataforma=plataforma or "instagram",
        formato=",".join(j.formato for j in jobs),
        jobs=jobs,
        sem_imagem=usar_sem_imagem,
        max_cenas=cenas,
        video=any(j.video for j in jobs),
    )
