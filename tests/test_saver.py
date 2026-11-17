from app.schemas import BioResult, BioVariacao
from app.saver import nova_pasta_job, salvar_bio


def test_nova_pasta_job_legado(tmp_path, monkeypatch):
    import app.saver as saver

    monkeypatch.setattr(saver, "SAIDA_DIR", tmp_path / "saida")
    pasta = nova_pasta_job("saude", "bio", "água")
    assert pasta.parent == tmp_path / "saida"
    assert (pasta / "01_fases").is_dir()
    assert (pasta / "02_resultado").is_dir()


def test_nova_pasta_job_campanha(tmp_path, monkeypatch):
    import app.campanha as camp
    import app.saver as saver

    monkeypatch.setattr(camp, "CAMPANHAS_DIR", tmp_path / "campanhas")
    monkeypatch.setattr(saver, "SAIDA_DIR", tmp_path / "saida")
    pasta = nova_pasta_job(
        "saude",
        "bio",
        "água",
        campanha="agua_manha",
        plataforma="instagram",
        formato="bio",
    )
    s = str(pasta).replace("\\", "/")
    assert "campanhas" in s
    assert "instagram" in s
    assert "bio" in s


def test_salvar_bio_escreve_arquivos(tmp_path, monkeypatch):
    import app.saver as saver

    monkeypatch.setattr(saver, "SAIDA_DIR", tmp_path / "saida")
    result = BioResult(
        variacoes=[
            BioVariacao(texto="a" * 20, foco="dor"),
            BioVariacao(texto="b" * 20, foco="ganho"),
            BioVariacao(texto="c" * 20, foco="prova"),
        ]
    )
    pasta = salvar_bio("saude", "tema teste", result)
    assert (pasta / "LEIA-ME.md").is_file()
    assert (pasta / "02_resultado").is_dir()
    assert any((pasta / "02_resultado").glob("*.md"))
