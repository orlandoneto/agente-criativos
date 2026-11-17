from app.wizard import (
    Brief,
    _eh_sair,
    buscar_nichos,
    formatar_lista_nichos,
    listar_nichos,
    resolver_nicho,
    resolver_tipo,
)


def test_eh_sair():
    assert _eh_sair("0")
    assert _eh_sair("sair")
    assert _eh_sair("Q")
    assert not _eh_sair("1")
    assert not _eh_sair("saude")


def test_listar_nichos_tem_exemplos():
    nichos = listar_nichos()
    assert "exemplo_tech" in nichos
    assert "saude" in nichos
    assert "cobras_br" in nichos
    assert len(nichos) >= 20


def test_formatar_lista_nichos_numerada():
    texto = formatar_lista_nichos(["saude", "exemplo_tech"])
    assert "1)" in texto and "saude" in texto
    assert "2)" in texto and "exemplo_tech" in texto
    grande = formatar_lista_nichos([f"n{i}" for i in range(1, 13)])
    assert "1)" in grande and "7)" in grande


def test_buscar_nichos_por_termo():
    nichos = ["exemplo_tech", "saude", "cobras_br"]
    assert buscar_nichos("cobra", nichos) == ["cobras_br"]
    assert buscar_nichos("tech", nichos) == ["exemplo_tech"]
    assert buscar_nichos("xyz", nichos) == []


def test_resolver_nicho_numero_ou_slug():
    nichos = ["exemplo_tech", "saude"]
    assert resolver_nicho("1", nichos) == "exemplo_tech"
    assert resolver_nicho("2", nichos) == "saude"
    assert resolver_nicho("saude", nichos) == "saude"
    assert resolver_nicho("cobras do brasil", nichos) is None


def test_resolver_tipo():
    assert resolver_tipo("bio") == "bio"
    assert resolver_tipo("2") == "legenda"
    assert resolver_tipo("3") == "carrossel"
    assert resolver_tipo("carousel") == "carrossel"
    assert resolver_tipo("") is None


def test_brief_texto_campanha_junta_contexto():
    b = Brief(nicho="saude", tipo="bio", tema="água", contexto="manhã, hábito", formato="bio")
    texto = b.texto_campanha()
    assert "água — manhã, hábito" in texto
    assert "instagram" in texto
    assert "bio" in texto
