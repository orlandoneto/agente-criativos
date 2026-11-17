from app.cli_style import aviso, dim, erro, ok, titulo


def test_helpers_retornam_string():
    assert "pronto" in ok("pronto")
    assert "x" in dim("x")
    assert "Titulo" in titulo("Titulo")
    assert "atenção" in aviso("atenção")
    assert "falhou" in erro("falhou")
