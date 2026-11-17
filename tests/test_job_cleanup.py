from pathlib import Path

from app.job_cleanup import job_parece_completo, limpar_se_incompleto, remover_pasta_job


def test_remove_incompleto(tmp_path: Path):
    pasta = tmp_path / "job"
    (pasta / "01_fases").mkdir(parents=True)
    (pasta / "LEIA-ME.md").write_text("x", encoding="utf-8")
    assert not job_parece_completo(pasta)
    assert limpar_se_incompleto(pasta)
    assert not pasta.exists()


def test_nao_remove_completo(tmp_path: Path):
    pasta = tmp_path / "job_ok"
    (pasta / "01_fases").mkdir(parents=True)
    res = pasta / "02_resultado"
    res.mkdir()
    (res / "conteudo.md").write_text("ok", encoding="utf-8")
    assert job_parece_completo(pasta)
    assert not limpar_se_incompleto(pasta)
    assert pasta.exists()
    assert remover_pasta_job(pasta)  # remoção explícita ainda funciona
    assert not pasta.exists()
