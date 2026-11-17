"""
Campanhas + skill de CONTEÚDO (não é skill do Cursor/agente de código).

campanhas/<nicho>/<campanha>/
  campanha.md
  skill/
    ideia.md           ← ideia central (texto) — opcional
    referencias/       ← imagens exemplo — opcional
    evitar.md          ← erros só desta campanha — opcional
  saida/<plataforma>/<formato>/<job>/

Sem skill → motor usa só nicho (perfil/exemplos/evitar) + tema escolhido.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.config import CAMPANHAS_DIR, PROJECT_VERSION

EXT_IMG = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def slugify(texto: str) -> str:
    s = (texto or "campanha").strip().lower()
    for a, b in (
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
        ("ã", "a"),
        ("õ", "o"),
        ("ç", "c"),
    ):
        s = s.replace(a, b)
    out = "".join(c if c.isalnum() else "_" for c in s)
    while "__" in out:
        out = out.replace("__", "_")
    return (out.strip("_") or "campanha")[:48]


def pasta_campanha(nicho: str, campanha: str) -> Path:
    return CAMPANHAS_DIR / slugify(nicho) / slugify(campanha)


def pasta_skill(nicho: str, campanha: str) -> Path:
    return pasta_campanha(nicho, campanha) / "skill"


def pasta_referencias(nicho: str, campanha: str) -> Path:
    """Prefer skill/referencias; aceita legado referencias/ na raiz da campanha."""
    skill_refs = pasta_skill(nicho, campanha) / "referencias"
    legado = pasta_campanha(nicho, campanha) / "referencias"
    if skill_refs.is_dir():
        return skill_refs
    if legado.is_dir():
        return legado
    return skill_refs


def garantir_estrutura(nicho: str, campanha: str, *, tema: str = "", contexto: str = "") -> Path:
    """Cria árvore da campanha (com skill/ vazia). Retorna raiz."""
    root = pasta_campanha(nicho, campanha)
    skill = root / "skill"
    refs = skill / "referencias"
    saida = root / "saida"
    refs.mkdir(parents=True, exist_ok=True)
    saida.mkdir(parents=True, exist_ok=True)
    keep = refs / ".gitkeep"
    if not keep.exists():
        keep.write_text("", encoding="utf-8")

    meta = root / "campanha.md"
    if not meta.exists():
        meta.write_text(
            "\n".join(
                [
                    f"# Campanha — {slugify(campanha)}",
                    "",
                    f"- Nicho: `{slugify(nicho)}`",
                    f"- Criada: {datetime.now().isoformat(timespec='seconds')}",
                    f"- Motor: {PROJECT_VERSION}",
                    f"- Tema: {tema or '(definir)'}",
                    f"- Contexto: {contexto or '(nenhum)'}",
                    "",
                    "## Pastas",
                    "",
                    "- `skill/ideia.md` — ideia central (skill de **conteúdo**, opcional)",
                    "- `skill/referencias/` — imagens exemplo de estilo (opcional)",
                    "- `skill/evitar.md` — erros só desta campanha (opcional)",
                    "- `saida/<plataforma>/<formato>/` — entregas geradas",
                    "",
                    "> Sem skill → gera só com o perfil do nicho + tema escolhido.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return root


def gravar_ideia(nicho: str, campanha: str, ideia: str) -> Path:
    """Grava/atualiza skill/ideia.md. Retorna path."""
    garantir_estrutura(nicho, campanha)
    path = pasta_skill(nicho, campanha) / "ideia.md"
    texto = (ideia or "").strip()
    path.write_text(
        "\n".join(
            [
                f"# Ideia central — {slugify(campanha)}",
                "",
                texto or "(vazia)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def ler_ideia(nicho: str, campanha: str) -> str:
    path = pasta_skill(nicho, campanha) / "ideia.md"
    if not path.is_file():
        return ""
    bruto = path.read_text(encoding="utf-8").strip()
    # remove título markdown simples
    linhas = [ln for ln in bruto.splitlines() if not ln.startswith("# ")]
    return "\n".join(linhas).strip()


def ler_evitar_campanha(nicho: str, campanha: str) -> str:
    path = pasta_skill(nicho, campanha) / "evitar.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def listar_referencias(nicho: str, campanha: str) -> list[Path]:
    refs = pasta_referencias(nicho, campanha)
    if not refs.is_dir():
        return []
    return sorted(p for p in refs.iterdir() if p.is_file() and p.suffix.lower() in EXT_IMG)


def parse_caminhos_imagens(raw: str) -> list[Path]:
    """Aceita caminhos separados por ; ou vírgula; também uma pasta."""
    if not (raw or "").strip():
        return []
    partes = []
    for chunk in raw.replace(",", ";").split(";"):
        chunk = chunk.strip().strip('"').strip("'")
        if chunk:
            partes.append(Path(chunk))
    out: list[Path] = []
    for p in partes:
        if p.is_dir():
            out.extend(sorted(x for x in p.iterdir() if x.is_file() and x.suffix.lower() in EXT_IMG))
        elif p.is_file() and p.suffix.lower() in EXT_IMG:
            out.append(p)
    vistos: set[str] = set()
    unicos: list[Path] = []
    for p in out:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in vistos:
            continue
        vistos.add(key)
        unicos.append(p)
    return unicos


def importar_referencias(nicho: str, campanha: str, caminhos: list[Path]) -> list[Path]:
    """Copia imagens para skill/referencias/."""
    garantir_estrutura(nicho, campanha)
    dest_dir = pasta_skill(nicho, campanha) / "referencias"
    dest_dir.mkdir(parents=True, exist_ok=True)
    salvos: list[Path] = []
    for src in caminhos:
        if not src.is_file():
            continue
        dest = dest_dir / src.name
        if dest.exists() and dest.resolve() != src.resolve():
            stem, suf = dest.stem, dest.suffix
            n = 2
            while dest.exists():
                dest = dest_dir / f"{stem}_{n}{suf}"
                n += 1
        if not dest.exists():
            shutil.copy2(src, dest)
        salvos.append(dest)
    return salvos


def pasta_saida_job(
    nicho: str,
    campanha: str,
    plataforma: str,
    formato: str,
    tema: str,
) -> Path:
    root = garantir_estrutura(nicho, campanha, tema=tema)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    pasta = (
        root
        / "saida"
        / slugify(plataforma or "geral")
        / slugify(formato or "job")
        / f"{stamp}_{slugify(tema)}"
    )
    (pasta / "01_fases").mkdir(parents=True, exist_ok=True)
    (pasta / "02_resultado").mkdir(parents=True, exist_ok=True)
    return pasta


def tem_skill(nicho: str, campanha: str) -> bool:
    if not campanha:
        return False
    return bool(ler_ideia(nicho, campanha) or listar_referencias(nicho, campanha))


def texto_skill_para_prompt(nicho: str, campanha: str) -> str:
    """Bloco da skill de conteúdo para o Gemini. Vazio se não houver skill."""
    if not campanha:
        return ""
    ideia = ler_ideia(nicho, campanha)
    refs = listar_referencias(nicho, campanha)
    evitar = ler_evitar_campanha(nicho, campanha)
    if not ideia and not refs and not evitar:
        return ""

    partes = [
        "## Skill de conteúdo desta campanha",
        "(Pacote de ensino: ideia + referências visuais. Não é fine-tune.)",
        "",
    ]
    if ideia:
        partes += ["### Ideia central", ideia, ""]
    if refs:
        nomes = ", ".join(p.name for p in refs[:20])
        extra = f" (+{len(refs) - 20} mais)" if len(refs) > 20 else ""
        partes += [
            f"### Imagens de referência ({len(refs)})",
            f"Arquivos em `skill/referencias/`: {nomes}{extra}",
            "Imite estilo (cores, clima, composição); não copie marca d'água nem rosto específico.",
            "",
        ]
    if evitar:
        partes += ["### Evitar nesta campanha", evitar, ""]
    return "\n".join(partes)


# compat nome antigo
def texto_refs_para_prompt(nicho: str, campanha: str) -> str:
    return texto_skill_para_prompt(nicho, campanha)
