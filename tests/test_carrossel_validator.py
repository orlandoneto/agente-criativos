from app.schemas import CarrosselResult, CarrosselSlide
from app.validator import validar_carrossel


def _slides(n: int) -> list[CarrosselSlide]:
    return [
        CarrosselSlide(titulo=f"Titulo {i}", apoio="Apoio curto", nota_visual="centro")
        for i in range(1, n + 1)
    ]


def test_carrossel_ok():
    r = CarrosselResult(
        slides=_slides(7),
        gancho="Gancho curto?",
        corpo="Corpo do post.",
        cta="Comente PROCESSO.",
        hashtags=["#pme", "#tech", "#site"],
    )
    assert validar_carrossel(r).ok


def test_carrossel_poucos_slides():
    r = CarrosselResult(
        slides=_slides(3),
        gancho="Gancho",
        corpo="Corpo",
        cta="CTA",
        hashtags=["#a", "#b", "#c"],
    )
    assert not validar_carrossel(r).ok
