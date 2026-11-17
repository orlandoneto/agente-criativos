"""
Catálogo canônico: o que é possível enviar em cada rede.

O wizard NÃO inventa formato na hora — lista daqui.
`todo` / `t` = todos os itens com disponivel=True (o motor já sabe o pacote).

Pacote = às vezes 1 job (bio) ou arte + texto (post/carrossel/reels).
Feed ≠ só carrossel: pode ser 1 arte ou várias.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatoPlataforma:
    id: str
    label: str
    descricao: str
    """Pipeline principal: bio | legenda | carrossel | None se só ○."""
    pipeline: str | None
    disponivel: bool
    forcar_video: bool = False
    """Se setado, força max-cenas nesse job (1 = post único no feed)."""
    max_cenas: int | None = None
    """Gera também a legenda/texto que acompanha a arte (pacote completo)."""
    com_legenda: bool = False


@dataclass(frozen=True)
class JobSpec:
    """Job já expandido a partir de um pacote da plataforma."""

    formato: str
    tipo: str
    label: str
    video: bool = False
    max_cenas: int | None = None


@dataclass(frozen=True)
class Plataforma:
    id: str
    nome: str
    formatos: tuple[FormatoPlataforma, ...]


# --- Catálogos: o que a rede aceita publicar (visão produto) ---

PLATAFORMAS: tuple[Plataforma, ...] = (
    Plataforma(
        id="instagram",
        nome="Instagram",
        formatos=(
            FormatoPlataforma(
                "bio",
                "Bio do perfil",
                "Texto embaixo do @ — até 150 caracteres",
                "bio",
                True,
            ),
            FormatoPlataforma(
                "post_feed",
                "Feed — 1 imagem + texto",
                "Post simples no feed: uma arte 4:5 + legenda (não é carrossel)",
                "carrossel",
                True,
                max_cenas=1,
                com_legenda=True,
            ),
            FormatoPlataforma(
                "carrossel_feed",
                "Feed — carrossel + texto",
                "Post no feed com várias artes (slides) 4:5 + legenda",
                "carrossel",
                True,
                com_legenda=True,
            ),
            FormatoPlataforma(
                "reels",
                "Reels (vídeo + texto)",
                "MP4 9:16 (slideshow) + texto/descrição da publicação",
                "carrossel",
                True,
                forcar_video=True,
                com_legenda=True,
            ),
            FormatoPlataforma(
                "stories",
                "Stories",
                "Frame vertical 9:16 + texto curto",
                None,
                False,
            ),
            FormatoPlataforma(
                "so_texto",
                "Só o texto (legenda)",
                "Se você já tem a arte e quer só o texto do post",
                "legenda",
                True,
            ),
        ),
    ),
    Plataforma(
        id="tiktok",
        nome="TikTok",
        formatos=(
            FormatoPlataforma(
                "bio",
                "Bio do perfil",
                "Texto curto do perfil",
                "bio",
                True,
            ),
            FormatoPlataforma(
                "video",
                "Vídeo 9:16 + texto",
                "Slideshow MP4 + descrição da publicação",
                "carrossel",
                True,
                forcar_video=True,
                com_legenda=True,
            ),
            FormatoPlataforma(
                "fotos",
                "Sequência de fotos + texto",
                "Várias imagens + descrição",
                "carrossel",
                True,
                com_legenda=True,
            ),
            FormatoPlataforma(
                "so_texto",
                "Só a descrição (texto)",
                "Texto da publicação sem gerar arte",
                "legenda",
                True,
            ),
        ),
    ),
    Plataforma(
        id="facebook",
        nome="Facebook",
        formatos=(
            FormatoPlataforma(
                "bio",
                "Sobre / intro da página",
                "Texto de apresentação",
                "bio",
                True,
            ),
            FormatoPlataforma(
                "post_feed",
                "Feed — 1 imagem + texto",
                "Post simples no feed: uma arte + legenda",
                "carrossel",
                True,
                max_cenas=1,
                com_legenda=True,
            ),
            FormatoPlataforma(
                "carrossel_feed",
                "Feed — carrossel + texto",
                "Post no feed com várias artes + legenda",
                "carrossel",
                True,
                com_legenda=True,
            ),
            FormatoPlataforma(
                "reels",
                "Reels (vídeo + texto)",
                "Vídeo curto 9:16 + texto",
                "carrossel",
                True,
                forcar_video=True,
                com_legenda=True,
            ),
            FormatoPlataforma("stories", "Stories", "Frame vertical", None, False),
            FormatoPlataforma(
                "so_texto",
                "Só o texto do post",
                "Legenda sem gerar arte",
                "legenda",
                True,
            ),
        ),
    ),
    Plataforma(
        id="youtube",
        nome="YouTube",
        formatos=(
            FormatoPlataforma(
                "bio",
                "Texto do canal (About)",
                "Apresentação curta do canal",
                "bio",
                True,
            ),
            FormatoPlataforma(
                "descricao",
                "Descrição do vídeo",
                "Texto longo da descrição",
                "legenda",
                True,
            ),
            FormatoPlataforma(
                "community",
                "Post Community (arte + texto)",
                "Slide de apoio + texto",
                "carrossel",
                True,
                max_cenas=1,
                com_legenda=True,
            ),
            FormatoPlataforma("thumbnail", "Thumbnail", "Capa 16:9 — motor ainda não", None, False),
            FormatoPlataforma("roteiro", "Roteiro falado", "Script — motor ainda não", None, False),
        ),
    ),
)

PLATAFORMA_IDS = tuple(p.id for p in PLATAFORMAS)
TIPOS_PIPELINE = ("bio", "legenda", "carrossel")


def listar_plataformas() -> tuple[Plataforma, ...]:
    return PLATAFORMAS


def get_plataforma(raw: str | None) -> Plataforma | None:
    if not raw:
        return None
    key = raw.strip().lower()
    aliases = {
        "ig": "instagram",
        "insta": "instagram",
        "fb": "facebook",
        "face": "facebook",
        "yt": "youtube",
        "you": "youtube",
        "tt": "tiktok",
    }
    key = aliases.get(key, key)
    if key.isdigit():
        i = int(key)
        if 1 <= i <= len(PLATAFORMAS):
            return PLATAFORMAS[i - 1]
    for p in PLATAFORMAS:
        if p.id == key or p.nome.lower() == key:
            return p
    return None


def get_formato(plat: Plataforma, raw: str) -> FormatoPlataforma | None:
    t = (raw or "").strip().lower()
    if not t:
        return None
    if t.isdigit():
        i = int(t)
        if 1 <= i <= len(plat.formatos):
            fmt = plat.formatos[i - 1]
            return fmt if fmt.disponivel else None
        return None
    aliases = {
        "legenda": "so_texto",
        "caption": "so_texto",
        "post": "post_feed",
        "feed": "post_feed",
        "carrossel": "carrossel_feed",
        "carousel": "carrossel_feed",
    }
    t = aliases.get(t, t)
    for f in plat.formatos:
        if f.id == t and f.disponivel:
            return f
    for f in plat.formatos:
        if f.disponivel and f.pipeline == t:
            return f
    return None


def formatos_disponiveis(plat: Plataforma) -> list[FormatoPlataforma]:
    return [f for f in plat.formatos if f.disponivel]


def expandir_pacote(fmt: FormatoPlataforma) -> list[JobSpec]:
    """Pacote da rede → jobs do motor (arte e/ou texto).

    Texto/legenda vem **antes** da arte quando o pacote tem os dois:
    aquece o sticky de IA no job leve; a arte segue no modelo que funcionou.
    """
    if not fmt.disponivel or not fmt.pipeline:
        return []
    jobs: list[JobSpec] = []
    if fmt.com_legenda and fmt.pipeline != "legenda":
        jobs.append(
            JobSpec(
                formato=f"{fmt.id}_texto",
                tipo="legenda",
                label=f"Texto/legenda — {fmt.label}",
                video=False,
                max_cenas=None,
            )
        )
    jobs.append(
        JobSpec(
            formato=fmt.id,
            tipo=fmt.pipeline,
            label=fmt.label,
            video=fmt.forcar_video,
            max_cenas=fmt.max_cenas,
        )
    )
    return jobs


def expandir_escolhas(fmts: list[FormatoPlataforma]) -> list[JobSpec]:
    """Vários pacotes → lista de jobs (sem duplicar o mesmo formato id)."""
    out: list[JobSpec] = []
    vistos: set[str] = set()
    for fmt in fmts:
        for job in expandir_pacote(fmt):
            key = f"{job.formato}:{job.tipo}:{job.video}:{job.max_cenas}"
            if key in vistos:
                continue
            vistos.add(key)
            out.append(job)
    return out


def parse_escolha_formatos(raw: str, plat: Plataforma) -> list[FormatoPlataforma] | None:
    """
    'todo' / 't' → todos os ✓ (catálogo já sabe o pacote completo).
    '1,3' → vários pacotes · '2' → um.
    """
    import re

    t = (raw or "").strip().lower()
    if not t:
        return None
    if t in {"todo", "todos", "t", "a", "all", "*"}:
        return formatos_disponiveis(plat)

    partes = [p for p in re.split(r"[\s,;]+", t) if p]
    escolhidos: list[FormatoPlataforma] = []
    vistos: set[str] = set()
    for parte in partes:
        fmt: FormatoPlataforma | None = None
        if parte.isdigit():
            i = int(parte)
            if 1 <= i <= len(plat.formatos):
                cand = plat.formatos[i - 1]
                if not cand.disponivel:
                    return None
                fmt = cand
        else:
            fmt = get_formato(plat, parte)
        if fmt is None:
            return None
        if fmt.id not in vistos:
            vistos.add(fmt.id)
            escolhidos.append(fmt)
    return escolhidos or None
