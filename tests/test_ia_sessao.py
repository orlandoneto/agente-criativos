from app import ia_sessao


def test_sticky_texto_e_imagem():
    ia_sessao.reset()
    assert ia_sessao.fila_texto(["a", "b", "c"]) == ["a", "b", "c"]
    ia_sessao.lembrar_texto("b")
    assert ia_sessao.fila_texto(["a", "b", "c"]) == ["b", "a", "c"]

    ia_sessao.lembrar_imagem("hf")
    assert ia_sessao.fila_imagem(["gemini", "hf", "pexels"]) == ["hf", "gemini", "pexels"]

    ia_sessao.reset()
    assert ia_sessao.modelo_texto is None
    assert ia_sessao.provedor_imagem is None


def test_failover_gruda_modelo_na_sessao(monkeypatch):
    from app.gemini_client import _com_failover

    ia_sessao.reset()
    avisos: list[str] = []

    def fake(modelo: str) -> str:
        if modelo == "a":
            raise Exception("503 UNAVAILABLE high demand")
        return f"ok:{modelo}"

    monkeypatch.setattr("app.gemini_client._modelos_texto", lambda: ["a", "b-lite"])
    monkeypatch.setattr("app.gemini_client._esperar_retry", lambda *a, **k: None)
    monkeypatch.setattr("app.gemini_client._avisar", lambda m: avisos.append(m))

    assert _com_failover(fake) == "ok:b-lite"
    assert ia_sessao.modelo_texto == "b-lite"

    # Segunda chamada na mesma sessão: tenta sticky primeiro
    ordem: list[str] = []

    def fake2(modelo: str) -> str:
        ordem.append(modelo)
        return "ok2"

    # _modelos_texto real usa sticky — mock que respeita ia_sessao
    monkeypatch.setattr(
        "app.gemini_client._modelos_texto",
        lambda: ia_sessao.fila_texto(["a", "b-lite", "c"]),
    )
    assert _com_failover(fake2) == "ok2"
    assert ordem[0] == "b-lite"
