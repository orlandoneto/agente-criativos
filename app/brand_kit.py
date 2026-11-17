"""Brand kit por marca (Fase 2, item 1): `nichos/<slug>/brand.yaml` validado com Pydantic.

Os templates (cores, fontes, logo, @, forma do CTA) e os prompts de IA (tom de voz,
palavras proibidas, hashtags padrão, estilo de CTA) leem daqui. Palavras proibidas
também são conferidas no texto gerado. Sem brand.yaml, cai no `perfil.md` (legado).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import NICHOS_DIR

ARQUIVO = "brand.yaml"
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class BrandKitInvalido(ValueError):
    """brand.yaml existe mas não passa na validação (mensagem amigável)."""


def _hex(v: str) -> str:
    v = (v or "").strip()
    if not _HEX.match(v):
        raise ValueError(f"cor inválida {v!r} (use #RRGGBB)")
    return v.upper()


class Cores(BaseModel):
    primaria: str = Field(..., description="Cor principal da marca")
    destaque: str = Field(..., description="Palavras destacadas, ícones, CTA")
    fundo: str = Field(..., description="Fundo quando não há foto")
    texto: str = "#FFFFFF"
    tag: str = Field("#E10600", description="Tarja do card de notícia")

    @field_validator("primaria", "destaque", "fundo", "texto", "tag")
    @classmethod
    def _cor(cls, v: str) -> str:
        return _hex(v)


class Fontes(BaseModel):
    titulo: str = "Anton"
    corpo: str = "Montserrat"

    @field_validator("titulo", "corpo")
    @classmethod
    def _embutida(cls, v: str) -> str:
        from app.fontes import FONTES

        familias = {f for f, _, _ in FONTES}
        if v not in familias:
            raise ValueError(f"fonte {v!r} não está embutida (use {', '.join(sorted(familias))})")
        return v


class CtaEstilo(BaseModel):
    texto_padrao: str = Field("Saiba mais", max_length=32)
    forma: Literal["pilula", "retangulo"] = "pilula"
    verbos: list[str] = Field(default_factory=list, description="Verbos preferidos no imperativo")
    regra: str = Field("", description="Orientação livre para a IA (ex.: 'sem urgência falsa')")


class BrandKit(BaseModel):
    nome: str = Field(..., min_length=1, max_length=40)
    handle: str = Field(..., description="@ da marca")
    cores: Cores
    fontes: Fontes = Field(default_factory=Fontes)
    logo: str | None = Field(None, description="Caminho relativo à pasta do nicho (PNG/SVG transparente)")
    tom_de_voz: str = Field("", max_length=600)
    palavras_proibidas: list[str] = Field(default_factory=list)
    hashtags_padrao: list[str] = Field(default_factory=list, max_length=5)
    cta: CtaEstilo = Field(default_factory=CtaEstilo)

    slug: str = Field("", exclude=True)
    pasta: Path | None = Field(None, exclude=True)

    @field_validator("handle")
    @classmethod
    def _handle(cls, v: str) -> str:
        h = (v or "").strip().lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", h):
            raise ValueError(f"handle inválido {v!r}")
        return "@" + h

    @field_validator("hashtags_padrao")
    @classmethod
    def _tags(cls, vs: list[str]) -> list[str]:
        out = []
        for v in vs:
            v = (v or "").strip().replace(" ", "")
            if v:
                out.append(v if v.startswith("#") else "#" + v)
        return out

    @field_validator("palavras_proibidas")
    @classmethod
    def _proibidas(cls, vs: list[str]) -> list[str]:
        return [v.strip() for v in vs if v and v.strip()]

    def logo_path(self) -> Path | None:
        if not self.logo or not self.pasta:
            return None
        p = (self.pasta / self.logo).resolve()
        return p if p.is_file() else None

    def proibidas_em(self, *textos: str) -> list[str]:
        return palavras_proibidas_em(self.palavras_proibidas, *textos)

    def bloco_prompt(self) -> str:
        """Trecho para os prompts de IA (tom, proibidas, CTA, hashtags)."""
        linhas = [f"## Marca\n- Nome: {self.nome} ({self.handle})"]
        if self.tom_de_voz:
            linhas.append(f"- Tom de voz: {self.tom_de_voz}")
        if self.palavras_proibidas:
            linhas.append("- PALAVRAS PROIBIDAS (nunca use, nem variações): " + ", ".join(self.palavras_proibidas))
        cta = f"- CTA: padrão \"{self.cta.texto_padrao}\""
        if self.cta.verbos:
            cta += "; verbos preferidos: " + ", ".join(self.cta.verbos)
        if self.cta.regra:
            cta += f"; {self.cta.regra}"
        linhas.append(cta)
        if self.hashtags_padrao:
            linhas.append("- Hashtags da marca (inclua): " + " ".join(self.hashtags_padrao))
        return "\n".join(linhas) + "\n\n"


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").casefold()


def palavras_proibidas_em(proibidas: list[str], *textos: str) -> list[str]:
    """Palavras/expressões proibidas presentes (palavra inteira, sem caixa nem acento)."""
    corpo = _sem_acento(" \n ".join(t for t in textos if t))
    achadas = []
    for p in proibidas:
        alvo = _sem_acento(p).strip()
        if alvo and re.search(r"(?<!\w)" + re.escape(alvo) + r"(?!\w)", corpo):
            achadas.append(p)
    return achadas


def caminho(slug: str) -> Path:
    return NICHOS_DIR / slug / ARQUIVO


def listar_marcas() -> list[str]:
    if not NICHOS_DIR.is_dir():
        return []
    return sorted(p.parent.name for p in NICHOS_DIR.glob(f"*/{ARQUIVO}"))


def carregar_brand_kit(slug: str | None) -> BrandKit | None:
    """None se a marca não tiver brand.yaml. BrandKitInvalido se o YAML estiver errado."""
    if not slug:
        return None
    arq = caminho(slug)
    if not arq.is_file():
        return None
    import yaml

    try:
        dados = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
        kit = BrandKit.model_validate(dados)
    except yaml.YAMLError as exc:
        raise BrandKitInvalido(f"{arq}: YAML inválido ({exc.__class__.__name__})") from exc
    except ValidationError as exc:
        erros = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
        raise BrandKitInvalido(f"{arq}: {erros}") from exc
    kit.slug, kit.pasta = slug, arq.parent
    return kit
