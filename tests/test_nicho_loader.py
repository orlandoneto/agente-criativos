import pytest

from app.nicho_loader import carregar_nicho


def test_carregar_nicho_saude_bio():
    ctx = carregar_nicho("saude", "bio")
    assert ctx.slug == "saude"
    assert ctx.perfil
    assert "150" in ctx.regra_tipo or "bio" in ctx.regra_tipo.lower()
    assert "exemplos" in ctx.exemplos.lower() or len(ctx.exemplos) > 10


def test_carregar_nicho_inexistente():
    with pytest.raises(FileNotFoundError):
        carregar_nicho("nicho_que_nao_existe_xyz", "bio")


def test_carregar_tipo_sem_regra():
    with pytest.raises(FileNotFoundError):
        carregar_nicho("saude", "tipo_fantasma_xyz")
