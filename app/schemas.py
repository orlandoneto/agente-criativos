"""Contratos JSON dos criativos (Pydantic v2)."""

from __future__ import annotations

import re as _re
import unicodedata as _ud

from pydantic import BaseModel, Field, field_validator, model_validator


class BioVariacao(BaseModel):
    texto: str = Field(..., description="Texto da bio, máx. 150 caracteres")
    foco: str = Field(default="", description="Dor, ganho, prova, etc.")


class BioResult(BaseModel):
    variacoes: list[BioVariacao] = Field(..., min_length=3, max_length=3)


class LegendaResult(BaseModel):
    gancho: str = Field(..., description="Abertura (priorizar ≤125 chars no início da legenda)")
    corpo: str = Field(..., description="Desenvolvimento PAS/AIDA")
    cta: str = Field(..., description="Chamada final")
    hashtags: list[str] = Field(..., min_length=3, max_length=5)
    estrutura: str = Field(default="PAS", description="PAS|AIDA|lista")

    @field_validator("hashtags")
    @classmethod
    def normalizar_hashtags(cls, valores: list[str]) -> list[str]:
        limpos: list[str] = []
        for h in valores:
            h = h.strip()
            if not h:
                continue
            if not h.startswith("#"):
                h = f"#{h}"
            limpos.append(h.replace(" ", ""))
        return limpos

    def legenda_completa(self) -> str:
        tags = " ".join(self.hashtags)
        partes = [self.gancho.strip(), "", self.corpo.strip(), "", self.cta.strip(), "", tags]
        return "\n".join(partes).strip()


class CarrosselSlide(BaseModel):
    titulo: str = Field(..., description="Texto principal na tela (curto)")
    apoio: str = Field(default="", description="Subtítulo opcional")
    nota_visual: str = Field(default="", description="Orientação de layout")
    prompt_imagem: str = Field(default="", description="Prompt EN opcional")


class CarrosselResult(BaseModel):
    # Faixa comercial 7–10 fica no validator (permite testar erros)
    slides: list[CarrosselSlide] = Field(..., min_length=1, max_length=20)
    gancho: str
    corpo: str
    cta: str
    hashtags: list[str] = Field(..., min_length=3, max_length=5)
    estrutura: str = Field(default="PAS")

    @field_validator("hashtags")
    @classmethod
    def normalizar_hashtags(cls, valores: list[str]) -> list[str]:
        return LegendaResult.normalizar_hashtags(valores)

    def as_legenda(self) -> LegendaResult:
        return LegendaResult(
            gancho=self.gancho,
            corpo=self.corpo,
            cta=self.cta,
            hashtags=self.hashtags,
            estrutura=self.estrutura,
        )


# ---------------------------------------------------------------------------
# Posts únicos Instagram (Fase 1): card de notícia e anúncio promocional
# ---------------------------------------------------------------------------

def _norm(texto: str) -> str:
    return _ud.normalize("NFC", texto or "").casefold()


def destaque_presente(titulo: str, destaque: str) -> bool:
    """True se `destaque` aparece no título como palavra/expressão inteira (sem diferenciar maiúsculas)."""
    d = _norm(destaque).strip()
    if not d:
        return False
    padrao = r"(?<!\w)" + _re.escape(d) + r"(?!\w)"
    return _re.search(padrao, _norm(titulo)) is not None


class NewsResult(BaseModel):
    """Card de notícia: foto + tarja + manchete com palavras destacadas."""

    tag: str = Field(default="Notícia", max_length=28, description="Texto da tarja vermelha (curto)")
    titulo: str = Field(..., min_length=3, max_length=120, description="Manchete (vira CAIXA ALTA)")
    destaques: list[str] = Field(default_factory=list, max_length=4,
                                 description="Palavras/expressões do título pintadas em cor")
    apoio: str = Field(default="", max_length=160, description="Linha de apoio opcional")
    prompt_imagem: str = Field(default="", description="Prompt EN da foto de fundo (opcional)")

    @field_validator("destaques")
    @classmethod
    def _limpar(cls, valores: list[str]) -> list[str]:
        return [v.strip() for v in valores if v and v.strip()]

    @model_validator(mode="after")
    def _destaques_no_titulo(self) -> "NewsResult":
        fora = [d for d in self.destaques if not destaque_presente(self.titulo, d)]
        if fora:
            raise ValueError(f"destaques fora do título: {fora}")
        return self


class HeadlinePart(BaseModel):
    texto: str = Field(..., min_length=1, max_length=60)
    destaque: bool = Field(default=False, description="True = amarelo; False = branco")


class AdFeature(BaseModel):
    icone: str = Field(default="check", description="Nome de ícone Lucide em assets/icons/lucide")
    texto: str = Field(..., min_length=2, max_length=48)

    @field_validator("icone")
    @classmethod
    def _icone_valido(cls, nome: str) -> str:
        from app.icones import normalizar_icone

        return normalizar_icone(nome)


class AdResult(BaseModel):
    """Anúncio elaborado: cena IA + pill + headline 2 cores + selo + benefícios + CTA."""

    pill: str = Field(..., min_length=2, max_length=36)
    headline_parts: list[HeadlinePart] = Field(..., min_length=1, max_length=4)
    badge: str = Field(default="", max_length=24, description="Selo redondo (ex.: GRÁTIS, -50%)")
    features: list[AdFeature] = Field(..., min_length=3, max_length=4)
    cta: str = Field(..., min_length=2, max_length=32)
    prompt_imagem: str = Field(default="", description="Prompt EN da cena de fundo (opcional)")

    def headline_texto(self) -> str:
        return " ".join(p.texto.strip() for p in self.headline_parts)


class NewsPostIA(BaseModel):
    """Resposta da IA de texto para um card de notícia (destaques filtrados depois)."""

    tag: str = "Notícia"
    titulo: str
    destaques: list[str] = Field(default_factory=list)
    apoio: str = ""
    prompt_imagem: str = ""
    legenda: LegendaResult

    def to_card(self) -> NewsResult:
        validos = [d for d in self.destaques if destaque_presente(self.titulo, d)][:4]
        return NewsResult(tag=self.tag[:28] or "Notícia", titulo=self.titulo[:120],
                          destaques=validos, apoio=self.apoio[:160], prompt_imagem=self.prompt_imagem)


class AdPostIA(BaseModel):
    ad: AdResult
    legenda: LegendaResult


# ---------------------------------------------------------------------------
# Carrossel no estilo novo (Fase 2): capa news/ad + N slides internos
# ---------------------------------------------------------------------------

class SlideCarrossel(BaseModel):
    """Slide interno do carrossel. `titulo` aceita *destaque* entre asteriscos."""

    titulo: str = Field(..., min_length=2, max_length=90)
    texto: str = Field(default="", max_length=240)
    icone: str = Field(default="check", description="Ícone Lucide (estilo ad)")

    @field_validator("icone")
    @classmethod
    def _icone_valido(cls, nome: str) -> str:
        from app.icones import normalizar_icone

        return normalizar_icone(nome or "check")


class NewsCarrosselIA(NewsPostIA):
    slides: list[SlideCarrossel] = Field(..., min_length=1, max_length=9)


class AdCarrosselIA(AdPostIA):
    slides: list[SlideCarrossel] = Field(..., min_length=1, max_length=9)
