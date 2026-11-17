from pydantic import BaseModel

from app.gemini_client import (
    ClasseErro,
    _classificar_erro,
    _com_failover,
    _eh_sobrecarga,
    _mensagem_api,
    _modelo_bloqueado,
    _modelos_texto,
    _reordenar_fila,
    _status_api,
    gerar_json,
)


class _Mini(BaseModel):
    x: int


def test_mensagem_503_sem_traceback_tecnico():
    class Fake503(Exception):
        status = 503

    msg = _mensagem_api(Fake503("UNAVAILABLE high demand"))
    assert "503" in msg
    assert "gerar" in msg
    assert "Traceback" not in msg
    assert "Please try again" not in msg
    assert _status_api(Fake503("x")) == 503
    assert _eh_sobrecarga(Fake503("high demand"))
    assert _classificar_erro(Fake503("high demand")) == ClasseErro.SOBRECARGA


def test_mensagem_503_pelo_texto_sem_attr_status():
    bruto = (
        "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
        "'This model is currently experiencing high demand. Spikes in demand "
        "are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
    )
    msg = _mensagem_api(Exception(bruto))
    assert "503" in msg
    assert "alta demanda" in msg
    assert "Please try again" not in msg
    assert _classificar_erro(Exception(bruto)) == ClasseErro.SOBRECARGA
    assert _status_api(Exception(bruto)) == 503


def test_classificar_auth_e_modelo():
    class Fake401(Exception):
        code = 401

    assert _classificar_erro(Fake401("PERMISSION_DENIED")) == ClasseErro.AUTH
    assert _classificar_erro(Exception("model xyz is not found")) == ClasseErro.MODELO
    bruto_404 = (
        "404 NOT_FOUND. {'error': {'code': 404, 'message': "
        "'This model models/gemini-2.5-flash is no longer available to new users.'}}"
    )
    assert _classificar_erro(Exception(bruto_404)) == ClasseErro.MODELO
    msg = _mensagem_api(Exception(bruto_404))
    assert "404" in msg or "indisponível" in msg
    assert "Please update" not in msg
    assert "{" not in msg


def test_modelos_texto_prioriza_lite_latest_e_bloqueia_mortos():
    assert _modelo_bloqueado("gemini-2.5-flash")
    assert _modelo_bloqueado("gemini-2.0-flash")
    assert "gemini-2.5-flash" not in _modelos_texto()
    assert "gemini-2.0-flash" not in _modelos_texto()
    modelos = _modelos_texto()
    assert modelos
    assert modelos[0] == "gemini-flash-lite-latest" or "lite" in modelos[0]


def test_404_pula_modelo_e_continua(monkeypatch):
    avisos: list[str] = []

    def fake(modelo: str) -> str:
        if modelo == "morto-x":
            raise Exception("404 NOT_FOUND. This model is no longer available to new users.")
        return f"ok:{modelo}"

    monkeypatch.setattr(
        "app.gemini_client._modelos_texto",
        lambda: ["morto-x", "vivo-y"],
    )
    monkeypatch.setattr("app.gemini_client._esperar_retry", lambda *a, **k: None)
    monkeypatch.setattr("app.gemini_client._avisar", lambda m: avisos.append(m))
    monkeypatch.setattr("app.gemini_client._salvar_bloqueado_disco", lambda m: None)

    assert _com_failover(fake) == "ok:vivo-y"
    assert any("404" in a or "descontinuado" in a for a in avisos)


def test_ultimo_modelo_503_insiste(monkeypatch):
    """Único modelo vivo: 503 → várias tentativas antes de desistir."""
    chamadas = {"n": 0}
    avisos: list[str] = []

    def fake(modelo: str) -> str:
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise Exception("503 UNAVAILABLE high demand")
        return "ok"

    monkeypatch.setattr("app.gemini_client._modelos_texto", lambda: ["sozinho"])
    monkeypatch.setattr("app.gemini_client._esperar_retry", lambda *a, **k: None)
    monkeypatch.setattr("app.gemini_client._avisar", lambda m: avisos.append(m))
    monkeypatch.setattr("app.gemini_client.TENTATIVAS_ULTIMO", 5)

    assert _com_failover(fake) == "ok"
    assert chamadas["n"] == 3
    assert any("único modelo" in a for a in avisos)


def test_reordenar_prioriza_lite_latest_em_sobrecarga():
    fila = ["gemini-flash-latest", "gemini-flash-lite-latest"]
    ord_ = _reordenar_fila(fila, ClasseErro.SOBRECARGA)
    assert ord_[0] == "gemini-flash-lite-latest"


def test_modelos_texto_inclui_principal():
    modelos = _modelos_texto()
    assert len(modelos) >= 1
    assert modelos[0]


def test_failover_503_troca_modelo_na_hora(monkeypatch):
    avisos: list[str] = []
    chamadas: list[str] = []

    def fake_exec(modelo: str) -> str:
        chamadas.append(modelo)
        if modelo == "pesado":
            raise Exception("503 UNAVAILABLE. high demand")
        return f"ok:{modelo}"

    monkeypatch.setattr("app.gemini_client._modelos_texto", lambda: ["pesado", "leve-lite"])
    monkeypatch.setattr("app.gemini_client._esperar_retry", lambda *a, **k: None)
    monkeypatch.setattr("app.gemini_client._avisar", lambda m: avisos.append(m))

    out = _com_failover(fake_exec)
    assert out == "ok:leve-lite"
    assert chamadas == ["pesado", "leve-lite"]
    assert any("trocando" in a for a in avisos)


def test_gerar_json_retry_inteligente(monkeypatch):
    chamadas = {"n": 0}

    class FakeResp:
        text = '{"x": 1}'

    class FakeModels:
        def generate_content(self, **kwargs):
            chamadas["n"] += 1
            modelo = kwargs.get("model", "")
            if modelo == "a":
                raise Exception("503 UNAVAILABLE. high demand")
            return FakeResp()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr("app.gemini_client._client", lambda: FakeClient())
    monkeypatch.setattr("app.gemini_client._esperar_retry", lambda *a, **k: None)
    monkeypatch.setattr("app.gemini_client._avisar", lambda m: None)
    monkeypatch.setattr("app.gemini_client._modelos_texto", lambda: ["a", "b-lite"])

    out = gerar_json("prompt", _Mini)
    assert out.x == 1
    assert chamadas["n"] == 2


def test_gerar_json_esgota_modelos_mensagem_amiga(monkeypatch):
    class FakeModels:
        def generate_content(self, **kwargs):
            raise Exception(
                "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
                "'This model is currently experiencing high demand.', "
                "'status': 'UNAVAILABLE'}}"
            )

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr("app.gemini_client._client", lambda: FakeClient())
    monkeypatch.setattr("app.gemini_client._esperar_retry", lambda *a, **k: None)
    monkeypatch.setattr("app.gemini_client._avisar", lambda m: None)
    monkeypatch.setattr("app.gemini_client._modelos_texto", lambda: ["a", "b"])
    monkeypatch.setattr("app.gemini_client.TENTATIVAS_ULTIMO", 2)

    try:
        gerar_json("p", _Mini)
        assert False, "devia falhar"
    except RuntimeError as exc:
        msg = str(exc)
        assert "alta demanda" in msg
        assert "Please try again" not in msg
