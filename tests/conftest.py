import pytest


@pytest.fixture(autouse=True)
def _freellmapi_off_by_default(monkeypatch):
    """Existing tests must not hit the live 3003 instance even if .env has a key."""
    import app.freellmapi_client as fl

    monkeypatch.setattr(fl, "FREELLMAPI_API_KEY", "")
    monkeypatch.setattr(fl, "_cooldown_until", 0.0)
    yield


@pytest.fixture(autouse=True)
def _rede_paga_off_por_padrao(monkeypatch):
    """Nenhum teste fala com OpenRouter/Pexels/Unsplash/HF reais, mesmo com chaves no .env.

    Testes que exercitam esses provedores re-setam a chave com valor fictício + MockTransport.
    """
    import app.image_gen as ig
    import app.openrouter_client as router

    monkeypatch.setattr(router, "OPENROUTER_API_KEY", "")
    for nome in ("PEXELS_API_KEY", "UNSPLASH_ACCESS_KEY", "HF_TOKEN"):
        monkeypatch.setattr(ig, nome, "")
    yield


@pytest.fixture(autouse=True)
def _revisao_ia_offline(monkeypatch, tmp_path):
    """Nenhum teste chama IA de visão real; cooldown vai para tmp."""
    import app.revisao as rv

    monkeypatch.setattr(rv, "CACHE_COOLDOWN", tmp_path / "revisao_cooldown.json")
    monkeypatch.setattr(rv, "PROVEDORES_VISAO", [])
    yield
