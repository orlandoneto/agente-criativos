"""Validação de limites Instagram — sem IA."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import (
    BIO_MAX_CHARS,
    CARROSSEL_SLIDES_DEFAULT,
    CARROSSEL_SLIDES_MAX,
    GANCHO_VISIBLE_CHARS,
    HASHTAGS_MAX,
    HASHTAGS_RECOMENDADAS,
    LEGENDA_MAX_CHARS,
)
from app.schemas import BioResult, CarrosselResult, LegendaResult


@dataclass
class ValidationResult:
    ok: bool
    erros: list[str] = field(default_factory=list)

    def merge(self, other: ValidationResult) -> ValidationResult:
        return ValidationResult(ok=self.ok and other.ok, erros=[*self.erros, *other.erros])


def validar_bio(result: BioResult) -> ValidationResult:
    erros: list[str] = []
    if len(result.variacoes) != 3:
        erros.append(f"Bio deve ter exatamente 3 variações (veio {len(result.variacoes)}).")
    for i, v in enumerate(result.variacoes, start=1):
        n = len(v.texto)
        if n > BIO_MAX_CHARS:
            erros.append(f"Bio {i}: {n} chars > {BIO_MAX_CHARS}.")
        if not v.texto.strip():
            erros.append(f"Bio {i}: texto vazio.")
    return ValidationResult(ok=not erros, erros=erros)


def validar_legenda(result: LegendaResult) -> ValidationResult:
    erros: list[str] = []
    completa = result.legenda_completa()
    n = len(completa)
    if n > LEGENDA_MAX_CHARS:
        erros.append(f"Legenda: {n} chars > {LEGENDA_MAX_CHARS}.")

    gancho = result.gancho.strip()
    if len(gancho) > GANCHO_VISIBLE_CHARS:
        erros.append(
            f"Gancho: {len(gancho)} chars > {GANCHO_VISIBLE_CHARS} "
            "(deve caber antes do 'mais')."
        )
    if not gancho:
        erros.append("Gancho vazio.")

    tags = result.hashtags
    if not (HASHTAGS_RECOMENDADAS[0] <= len(tags) <= HASHTAGS_RECOMENDADAS[1]):
        erros.append(
            f"Hashtags: use {HASHTAGS_RECOMENDADAS[0]}–{HASHTAGS_RECOMENDADAS[1]} "
            f"(veio {len(tags)})."
        )
    if len(tags) > HASHTAGS_MAX:
        erros.append(f"Hashtags: {len(tags)} > máximo absoluto {HASHTAGS_MAX}.")

    for h in tags:
        if " " in h.strip():
            erros.append(f"Hashtag inválida (espaço): {h}")

    return ValidationResult(ok=not erros, erros=erros)


def validar_carrossel(result: CarrosselResult) -> ValidationResult:
    erros: list[str] = []
    n = len(result.slides)
    lo, hi = CARROSSEL_SLIDES_DEFAULT
    if n > CARROSSEL_SLIDES_MAX:
        erros.append(f"Slides: {n} > máximo {CARROSSEL_SLIDES_MAX}.")
    if not (lo <= n <= hi):
        erros.append(f"Slides: use {lo}–{hi} (veio {n}).")

    for i, slide in enumerate(result.slides, start=1):
        if not slide.titulo.strip():
            erros.append(f"Slide {i}: título vazio.")
        if len(slide.titulo) > 120:
            erros.append(f"Slide {i}: título longo demais ({len(slide.titulo)} > 120).")
        if len(slide.apoio) > 180:
            erros.append(f"Slide {i}: apoio longo demais ({len(slide.apoio)} > 180).")

    return ValidationResult(ok=not erros, erros=erros).merge(validar_legenda(result.as_legenda()))
