from app.schemas import BioResult, BioVariacao, LegendaResult
from app.validator import validar_bio, validar_legenda


def test_bio_ok():
    r = BioResult(
        variacoes=[
            BioVariacao(texto="a" * 50, foco="dor"),
            BioVariacao(texto="b" * 50, foco="ganho"),
            BioVariacao(texto="c" * 50, foco="prova"),
        ]
    )
    assert validar_bio(r).ok


def test_bio_estoura():
    r = BioResult(
        variacoes=[
            BioVariacao(texto="x" * 151, foco="dor"),
            BioVariacao(texto="ok", foco="ganho"),
            BioVariacao(texto="ok", foco="prova"),
        ]
    )
    v = validar_bio(r)
    assert not v.ok
    assert any("151" in e or "150" in e for e in v.erros)


def test_legenda_ok():
    r = LegendaResult(
        gancho="Você perde horas em planilha?",
        corpo="Isso drena a equipe e atrasa entrega.",
        cta="Salva e fala comigo no link da bio.",
        hashtags=["#pme", "#tech", "#processos"],
        estrutura="PAS",
    )
    assert validar_legenda(r).ok


def test_legenda_gancho_longo():
    r = LegendaResult(
        gancho="x" * 126,
        corpo="corpo",
        cta="cta",
        hashtags=["#a", "#b", "#c"],
    )
    v = validar_legenda(r)
    assert not v.ok
