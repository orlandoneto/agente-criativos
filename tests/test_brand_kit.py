"""Brand kit (nichos/<slug>/brand.yaml): validação, templates, prompts e palavras proibidas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import brand_kit, post_pipeline, post_render
from app.schemas import AdFeature, AdPostIA, AdResult, HeadlinePart, LegendaResult

KIT_OK = """
nome: Loja Teste
handle: lojateste
cores: {primaria: "#112233", destaque: "#00ff88", fundo: "#000000"}
fontes: {titulo: Bebas Neue, corpo: Montserrat}
logo: logo.png
tom_de_voz: leve e direto
palavras_proibidas: [milagre, só hoje, garantido]
hashtags_padrao: [lojateste, "#promo"]
cta: {texto_padrao: Compre já, forma: retangulo, verbos: [Compre]}
"""


@pytest.fixture
def nichos(tmp_path, monkeypatch):
    monkeypatch.setattr(brand_kit, "NICHOS_DIR", tmp_path)
    return tmp_path


def _kit(nichos: Path, texto: str = KIT_OK, slug: str = "loja", logo: bool = True):
    d = nichos / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "brand.yaml").write_text(texto, encoding="utf-8")
    if logo:
        from PIL import Image

        Image.new("RGBA", (120, 40), (255, 0, 0, 255)).save(d / "logo.png")
    return brand_kit.carregar_brand_kit(slug)


def test_kit_minhamarca_padrao_do_repo():
    kit = brand_kit.carregar_brand_kit("minhamarca")
    assert kit.handle == "@minhamarca" and kit.cores.destaque == "#FFD60A"
    assert kit.fontes.titulo == "Anton" and "#minhamarca" in kit.hashtags_padrao
    assert "minhamarca" in brand_kit.listar_marcas()
    assert brand_kit.carregar_brand_kit("academia") is None  # sem brand.yaml → legado


def test_kit_valida_e_normaliza(nichos):
    kit = _kit(nichos)
    assert kit.handle == "@lojateste" and kit.cores.destaque == "#00FF88"
    assert kit.hashtags_padrao == ["#lojateste", "#promo"]
    assert kit.logo_path() == (nichos / "loja" / "logo.png").resolve()


@pytest.mark.parametrize("troca,erro", [
    ('destaque: "#00ff88"', 'destaque: "amarelo"'),
    ("titulo: Bebas Neue", "titulo: Comic Sans"),
    ("handle: lojateste", "handle: 'loja teste!'"),
])
def test_kit_invalido_mensagem_amigavel(nichos, troca, erro):
    with pytest.raises(brand_kit.BrandKitInvalido, match="brand.yaml"):
        _kit(nichos, KIT_OK.replace(troca, erro))


def test_kit_yaml_quebrado(nichos):
    with pytest.raises(brand_kit.BrandKitInvalido, match="YAML"):
        _kit(nichos, "nome: [sem fechar")


def test_palavras_proibidas_sem_caixa_acento_palavra_inteira():
    proib = ["milagre", "só hoje", "garantido"]
    assert brand_kit.palavras_proibidas_em(proib, "Um MILAGRE!", "promo SO HOJE") == ["milagre", "só hoje"]
    assert brand_kit.palavras_proibidas_em(proib, "Garanta o seu", "milagres") == []


def test_bloco_prompt_e_prompt_post(nichos):
    kit = _kit(nichos)
    bloco = kit.bloco_prompt()
    assert "PALAVRAS PROIBIDAS" in bloco and "milagre" in bloco and "#promo" in bloco and "Compre já" in bloco
    p = post_pipeline.prompt_post("ad", "minhamarca", "ebook", kit)
    assert p.index("## Marca") < p.index("## Perfil do nicho") and "leve e direto" in p


def test_marca_de_usa_kit_handle_sobrepoe_e_slug_inexistente(nichos):
    _kit(nichos)
    m = post_pipeline.marca_de(None, None, "loja")
    assert m.handle == "@lojateste" and m.destaque == "#00FF88" and m.fonte_titulo == "Bebas Neue"
    assert m.cta_forma == "retangulo" and m.logo is not None
    assert post_pipeline.marca_de(None, "outro", "loja").handle == "@outro"
    with pytest.raises(ValueError, match="brand.yaml"):
        post_pipeline.marca_de(None, None, "nao_existe")


def _ad(**kw):
    base = dict(pill="Oferta", headline_parts=[HeadlinePart(texto="Promo", destaque=True), HeadlinePart(texto="boa")],
                features=[AdFeature(texto="Rápido"), AdFeature(texto="Fácil"), AdFeature(texto="Barato")], cta="Compre")
    base.update(kw)
    return AdResult(**base)


def test_templates_usam_cores_fontes_logo_e_cta_do_kit(nichos):
    m = post_render.Marca.do_kit(_kit(nichos))
    html = post_render.html_ad(_ad(), marca=m)
    assert "--amarelo: #00FF88" in html and "'Bebas Neue', 'Anton'" in html
    assert 'class="logo" src="data:image/png;base64,' in html and "border-radius: 18px" in html
    news = post_render.html_news(post_pipeline.NewsResult(titulo="Teste de título"), marca=m)
    assert "--hl: #00FF88" in news and 'class="logo"' in news
    assert "--hl: #FF2D2D" in post_render.html_news(post_pipeline.NewsResult(titulo="Teste"), marca=m,
                                                    cor_destaque="vermelho")
    assert post_render.cor_sobre("#FFD60A") == "#1A1300" and post_render.cor_sobre("#112233") == "#FFFFFF"


def test_gerar_texto_ia_corrige_proibidas_e_mescla_hashtags(nichos, monkeypatch):
    from app import gemini_client

    kit = _kit(nichos)
    leg = LegendaResult(gancho="Só hoje!", corpo="c", cta="Compre", hashtags=["#a", "#promo", "#b"])
    ruim = AdPostIA(ad=_ad(pill="Milagre"), legenda=leg)
    bom = AdPostIA(ad=_ad(), legenda=leg.model_copy(update={"gancho": "Chegou"}))
    correcoes = []
    monkeypatch.setattr(gemini_client, "gerar_json", lambda prompt, schema: ruim)
    monkeypatch.setattr(gemini_client, "corrigir_json",
                        lambda prompt, schema, erros, anterior: correcoes.append(erros) or bom)
    conteudo, legenda = post_pipeline.gerar_texto_ia("ad", "minhamarca", "promo", kit)
    assert len(correcoes) == 1 and "milagre" in correcoes[0][0] and "só hoje" in correcoes[0][0]
    assert conteudo.pill == "Oferta" and legenda.hashtags == ["#lojateste", "#promo", "#a", "#b"]

    monkeypatch.setattr(gemini_client, "corrigir_json", lambda *a: ruim)
    with pytest.raises(ValueError, match="insistiu"):
        post_pipeline.gerar_texto_ia("ad", "minhamarca", "promo", kit)


def test_cli_marca_inexistente_falha(capsys):
    import gerar

    assert gerar.main(["--estilo", "news", "--titulo", "Oi", "--marca", "nao_existe", "--sem-revisao"]) == 1
    assert "ERRO de marca" in capsys.readouterr().out


def test_cli_manual_avisa_proibida_e_registra(tmp_path, capsys, monkeypatch):
    import gerar

    monkeypatch.setattr(post_pipeline, "renderizar_post", lambda *a, **k: _fake_png(a[3]))
    out = tmp_path / "n"
    code = gerar.main(["--estilo", "news", "--titulo", "Resultado garantido em 7 dias", "--marca", "minhamarca",
                       "--sem-revisao", "--saida", str(out)])
    assert code == 0 and "palavras proibidas" in capsys.readouterr().out
    dados = json.loads((out / "post.json").read_text(encoding="utf-8"))
    assert dados["palavras_proibidas_encontradas"] == ["garantido"] and dados["marca"]["handle"] == "@minhamarca"


def _fake_png(dst: Path):
    from PIL import Image

    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (10, 10)).save(dst)
    return dst, {"ok": True, "nota": 10}
