from app.brand import BrandColors, carregar_brand


def test_carregar_brand_saude_tem_cores():
    b = carregar_brand("saude")
    assert isinstance(b, BrandColors)
    assert b.fundo.startswith("#")
    assert len(b.fundo) == 7
    assert b.texto.startswith("#")
    assert b.destaque.startswith("#")
    assert b.nome
