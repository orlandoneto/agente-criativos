from app.plataformas import (
    expandir_escolhas,
    expandir_pacote,
    get_formato,
    get_plataforma,
    listar_plataformas,
    parse_escolha_formatos,
)


def test_plataformas_basicas():
    plats = listar_plataformas()
    ids = {p.id for p in plats}
    assert ids >= {"instagram", "tiktok", "facebook", "youtube"}


def test_get_plataforma_numero_e_alias():
    assert get_plataforma("1").id == "instagram"
    assert get_plataforma("ig").id == "instagram"
    assert get_plataforma("tiktok").nome == "TikTok"


def test_instagram_feed_nao_e_so_carrossel():
    ig = get_plataforma("instagram")
    assert ig is not None
    ids = [f.id for f in ig.formatos]
    assert "post_feed" in ids  # 1 arte + texto
    assert "carrossel_feed" in ids  # várias artes + texto
    post = get_formato(ig, "post_feed")
    assert post is not None and post.max_cenas == 1 and post.com_legenda
    carr = get_formato(ig, "carrossel_feed")
    assert carr is not None and carr.com_legenda and carr.max_cenas is None


def test_pacote_post_expande_arte_e_texto():
    ig = get_plataforma("instagram")
    post = get_formato(ig, "post_feed")
    assert post is not None
    jobs = expandir_pacote(post)
    assert [j.tipo for j in jobs] == ["legenda", "carrossel"]  # texto aquece sticky
    assert jobs[1].max_cenas == 1


def test_todo_expande_varios_jobs():
    ig = get_plataforma("instagram")
    assert ig is not None
    pacotes = parse_escolha_formatos("todo", ig)
    assert pacotes is not None
    jobs = expandir_escolhas(pacotes)
    tipos = {j.tipo for j in jobs}
    assert "bio" in tipos
    assert "legenda" in tipos
    assert "carrossel" in tipos
    assert len(jobs) > len(pacotes)  # pacotes com com_legenda incham
