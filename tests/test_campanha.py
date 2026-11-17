from pathlib import Path

from app.campanha import (
    garantir_estrutura,
    gravar_ideia,
    importar_referencias,
    ler_ideia,
    parse_caminhos_imagens,
    pasta_saida_job,
    slugify,
    tem_skill,
    texto_skill_para_prompt,
)


def test_slugify():
    assert slugify("Cobras do Brasil!") == "cobras_do_brasil"


def test_estrutura_cria_skill(tmp_path, monkeypatch):
    import app.campanha as mod
    import app.config as cfg

    monkeypatch.setattr(mod, "CAMPANHAS_DIR", tmp_path / "campanhas")
    monkeypatch.setattr(cfg, "CAMPANHAS_DIR", tmp_path / "campanhas")

    root = garantir_estrutura("saude", "agua_manha", tema="água")
    assert (root / "skill" / "referencias").is_dir()
    assert (root / "campanha.md").is_file()
    assert not tem_skill("saude", "agua_manha")
    job = pasta_saida_job("saude", "agua_manha", "instagram", "bio", "água")
    assert "instagram" in str(job)
    assert "bio" in str(job)
    assert (job / "01_fases").is_dir()


def test_ideia_e_skill_opcional(tmp_path, monkeypatch):
    import app.campanha as mod

    monkeypatch.setattr(mod, "CAMPANHAS_DIR", tmp_path / "campanhas")
    assert texto_skill_para_prompt("saude", "sem_nada") == ""
    gravar_ideia("saude", "com_ideia", "Hidratação de manhã, tom leve.")
    assert "Hidratação" in ler_ideia("saude", "com_ideia")
    assert tem_skill("saude", "com_ideia")
    bloco = texto_skill_para_prompt("saude", "com_ideia")
    assert "Skill de conteúdo" in bloco
    assert "Hidratação" in bloco


def test_importar_imagens_em_skill(tmp_path, monkeypatch):
    import app.campanha as mod

    monkeypatch.setattr(mod, "CAMPANHAS_DIR", tmp_path / "campanhas")
    img = tmp_path / "exemplo.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    salvos = importar_referencias("saude", "teste", [img])
    assert len(salvos) == 1
    assert "skill" in str(salvos[0]).replace("\\", "/")
    assert salvos[0].exists()
    assert tem_skill("saude", "teste")
    assert "exemplo.png" in texto_skill_para_prompt("saude", "teste")


def test_legado_referencias_na_raiz(tmp_path, monkeypatch):
    """Campanhas antigas com referencias/ na raiz ainda entram no prompt."""
    import app.campanha as mod

    monkeypatch.setattr(mod, "CAMPANHAS_DIR", tmp_path / "campanhas")
    root = tmp_path / "campanhas" / "saude" / "legado"
    refs = root / "referencias"
    refs.mkdir(parents=True)
    (refs / "old.jpg").write_bytes(b"x")
    assert tem_skill("saude", "legado")
    assert "old.jpg" in texto_skill_para_prompt("saude", "legado")


def test_parse_caminhos(tmp_path):
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.png"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    pasta = tmp_path / "lote"
    pasta.mkdir()
    (pasta / "c.webp").write_bytes(b"z")
    paths = parse_caminhos_imagens(f"{a};{b}")
    assert len(paths) == 2
    assert len(parse_caminhos_imagens(str(pasta))) == 1
