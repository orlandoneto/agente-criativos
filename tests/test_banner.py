from app.banner import banner_text


def test_banner_tem_marca_e_versao():
    texto = banner_text(nome="Agente Criativos", versao="0.6.1")
    assert "*" in texto
    assert "/|\\" in texto
    assert "Agente Criativos" in texto
    assert "v0.6.1" in texto
