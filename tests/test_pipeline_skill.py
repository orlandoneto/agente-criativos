"""Pipeline anexa skill ao tema sem chamar Gemini."""

from app.pipeline import _tema_com_skill


def test_tema_sem_campanha_inalterado():
    assert _tema_com_skill("saude", "só tema", "") == "só tema"


def test_tema_com_skill_anexa_ideia(tmp_path, monkeypatch):
    import app.campanha as camp
    import app.pipeline as pipe

    monkeypatch.setattr(camp, "CAMPANHAS_DIR", tmp_path / "campanhas")
    camp.gravar_ideia("saude", "job_skill", "Ideia central da skill.")
    out = pipe._tema_com_skill("saude", "tema base", "job_skill")
    assert "tema base" in out
    assert "Ideia central da skill" in out
    assert "Skill de conteúdo" in out


def test_tema_campanha_vazia_sem_skill(tmp_path, monkeypatch):
    import app.campanha as camp
    import app.pipeline as pipe

    monkeypatch.setattr(camp, "CAMPANHAS_DIR", tmp_path / "campanhas")
    camp.garantir_estrutura("saude", "vazia")
    assert pipe._tema_com_skill("saude", "tema", "vazia") == "tema"
