from app.resiliencia_ia import (
    CHECKPOINT_A_CADA,
    ESPERAS_SEGUNDOS,
    EsperaResultado,
    eh_saturacao_ou_cota,
    esperar_ia,
    gravar_campanha_pendente,
)


def test_detecta_saturacao():
    assert eh_saturacao_ou_cota("Gemini em alta demanda (503)")
    assert eh_saturacao_ou_cota("cota esgotada 429")
    assert not eh_saturacao_ou_cota("chave inválida")


def test_esperar_ia_interruptivel_pular(monkeypatch):
    """Simula Enter (pular) durante a espera — não trava minutos nos testes."""
    monkeypatch.setattr(
        "app.resiliencia_ia._sleep_interruptivel",
        lambda segs, sleep_fn=None: "pular",
    )
    assert CHECKPOINT_A_CADA == 5
    r = esperar_ia(1)
    assert isinstance(r, EsperaResultado)
    assert r.acao == "pular"


def test_esperar_ia_timeout_continuar(monkeypatch):
    monkeypatch.setattr(
        "app.resiliencia_ia._sleep_interruptivel",
        lambda segs, sleep_fn=None: "",
    )
    r = esperar_ia(1)
    assert r.acao == "continuar"
    assert r.segundos == 60
    # Ciclo se repete (tentativa 6 = mesma duração da 1)
    r6 = esperar_ia(6)
    assert r6.segundos == ESPERAS_SEGUNDOS[0]


def test_esperar_ia_tipografia(monkeypatch):
    monkeypatch.setattr(
        "app.resiliencia_ia._sleep_interruptivel",
        lambda segs, sleep_fn=None: "tipografia",
    )
    r = esperar_ia(2, permitir_tipografia=True)
    assert r.acao == "tipografia"
    r2 = esperar_ia(2, permitir_tipografia=False)
    assert r2.acao == "pular"  # tipografia não permitida → vira pular


def test_gravar_pendente(tmp_path, monkeypatch):
    import app.campanha as camp
    import app.resiliencia_ia as res

    monkeypatch.setattr(camp, "CAMPANHAS_DIR", tmp_path / "campanhas")
    monkeypatch.setattr(res, "pasta_campanha", camp.pasta_campanha)
    monkeypatch.setattr(res, "garantir_estrutura", camp.garantir_estrutura)

    path = gravar_campanha_pendente(
        "cobras_br",
        "teste_pend",
        tema="veneno",
        plataforma="instagram",
        jobs_ok=["legenda"],
        jobs_falha=["arte"],
        pastas_salvas=["C:/x"],
        motivo="503",
    )
    assert path is not None
    assert path.is_file()
    texto = path.read_text(encoding="utf-8")
    assert "pendente" in texto.lower()
    assert "503" in texto
    assert "legenda" in texto
