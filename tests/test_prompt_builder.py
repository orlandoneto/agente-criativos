from app.nicho_loader import NichoContext
from app.prompt_builder import prompt_bio, prompt_carrossel, prompt_legenda


def _ctx() -> NichoContext:
    return NichoContext(
        slug="teste",
        perfil="Perfil X",
        evitar="Evitar Y",
        exemplos="Exemplo Z",
        regra_tipo="Regra bio",
    )


def test_prompt_bio_inclui_contexto_e_schema():
    p = prompt_bio(_ctx(), "água de manhã")
    assert "Perfil X" in p
    assert "Evitar Y" in p
    assert "água de manhã" in p
    assert "variacoes" in p
    assert "JSON" in p


def test_prompt_legenda_e_carrossel():
    ctx = _ctx()
    leg = prompt_legenda(ctx, "tema")
    assert "gancho" in leg and "hashtags" in leg
    car = prompt_carrossel(ctx, "tema")
    assert "slides" in car and "prompt_imagem" in car
    assert "PROIBIDO" in car or "texto" in car.lower()
