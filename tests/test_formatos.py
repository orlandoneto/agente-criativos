"""Fase 2, item 6: Stories/Reels 9x16, capa de Reels, carrossel (capa + slides), wizard e --badge -50%."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app import post_pipeline, post_render, wizard_post
from app.schemas import AdCarrosselIA, AdFeature, AdResult, HeadlinePart, LegendaResult, NewsResult, SlideCarrossel


def _chromium_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001
        return False


chromium = pytest.mark.skipif(not _chromium_ok(), reason="Chromium do Playwright não instalado")


def _ad(**kw):
    base = dict(pill="Ebook", headline_parts=[HeadlinePart(texto="Crie posts", destaque=True),
                HeadlinePart(texto="em 10 minutos")],
                features=[AdFeature(icone="zap", texto="Rápido"), AdFeature(icone="clock", texto="Fácil"),
                          AdFeature(icone="gift", texto="Grátis")], cta="Baixe agora", badge="Grátis")
    base.update(kw)
    return AdResult(**base)


def _news():
    return NewsResult(tag="Novidade", titulo="Instagram libera carrossel com 20 fotos", destaques=["20 fotos"],
                      apoio="Recurso chega ao Brasil")


def test_formatos_e_zonas_seguras():
    assert post_render.tamanho("9x16") == (1080, 1920) == post_render.tamanho("capa-reels")
    assert post_render.SAFE_ZONES["9x16"] == {"topo": 250, "base": 340}
    assert post_pipeline.safe_zone("4x5") is None and post_pipeline.safe_zone("capa-reels")["topo"] == 240


def test_html_9x16_respeita_zona_segura_no_css():
    news = post_render.html_news(_news(), formato="9x16")
    assert "top: 270px" in news and "bottom: 360px" in news and "max-height: 760px" in news
    ad = post_render.html_ad(_ad(), formato="9x16")
    assert "padding-top: 270px" in ad and "padding-bottom: 360px" in ad
    capa = post_render.html_ad(_ad(), formato="capa-reels")
    assert "padding-top: 260px" in capa and "padding-bottom: 260px" in capa
    assert "Arraste" in post_render.html_news(_news(), formato="carrossel")
    assert "Arraste" not in post_render.html_news(_news(), formato="4x5")


@chromium
@pytest.mark.parametrize("estilo,formato", [("news", "9x16"), ("ad", "9x16"), ("news", "capa-reels"),
                                            ("ad", "capa-reels")])
def test_png_9x16_tamanho_e_sem_texto_na_zona_segura(tmp_path, estilo, formato):
    conteudo = _news() if estilo == "news" else _ad()
    png, pre = post_pipeline.renderizar_post(estilo, formato, conteudo, tmp_path / "p.png",
                                             marca=post_render.Marca(handle="@minhamarca", nome="Minha Marca"))
    with Image.open(png) as img:
        assert img.size == (1080, 1920)
    assert pre["zona_segura"] == [] and pre["estouros"] == [], pre


def test_parse_slides_icone_opcional():
    sl = post_pipeline.parse_slides(["zap:Rápido *demais*|texto", "Hora: 10h|sem ícone", "  ", "Só título"])
    assert [s.icone for s in sl] == ["zap", "check", "check"]
    assert sl[1].titulo == "Hora: 10h" and sl[2].texto == ""
    assert post_render.partes_destaque("Rápido *demais*") == [{"texto": "Rápido", "hl": False},
                                                             {"texto": "demais", "hl": True}]


def test_html_slide_news_e_ad():
    sl = SlideCarrossel(titulo="Postar *sem constância*", texto="Explicação", icone="clock")
    news = post_render.html_slide(sl, numero=2, total=3, estilo="news", marca=post_render.Marca(handle="@x"))
    assert "02/03" in news and 'class="hl">sem constância' in news and "Arraste" in news
    ad = post_render.html_slide(sl, numero=3, total=3, estilo="ad", cta="Baixe", marca=post_render.Marca())
    assert 'data-icone="clock"' in ad and 'class="cta">Baixe' in ad and "Arraste" not in ad


def test_prompt_carrossel_pede_slides():
    p = post_pipeline.prompt_post("news", "minhamarca", "alcance", None, 3)
    assert '"slides"' in p and "exatamente 3 slides" in p


def test_gerar_carrossel_ia_usa_schema_com_slides(monkeypatch):
    from app import gemini_client

    leg = LegendaResult(gancho="g", corpo="c", cta="x", hashtags=["#a", "#b", "#c"])
    vistos = []

    def fake(prompt, schema):
        vistos.append(schema)
        return AdCarrosselIA(ad=_ad(), legenda=leg, slides=[SlideCarrossel(titulo=f"S{i}") for i in range(4)])

    monkeypatch.setattr(gemini_client, "gerar_json", fake)
    conteudo, legenda, slides = post_pipeline.gerar_carrossel_ia("ad", "minhamarca", "t", None, 2)
    assert vistos == [AdCarrosselIA] and [s.titulo for s in slides] == ["S0", "S1"]


@chromium
def test_cli_carrossel_manual_news(tmp_path):
    import gerar

    out = tmp_path / "car"
    code = gerar.main(["--estilo", "news", "--formato", "carrossel", "--titulo", "3 erros que matam seu alcance",
                       "--destaques", "matam seu alcance", "--slide", "Postar *sem constância*|Escolha 3 dias.",
                       "--slide", "Ignorar o *gancho*|Os primeiros 125 caracteres.", "--cta", "Salve",
                       "--marca", "minhamarca", "--sem-revisao", "--saida", str(out)])
    assert code == 0
    for n in (1, 2, 3):
        with Image.open(out / f"slide_{n:02d}.png") as img:
            assert img.size == (1080, 1350)
    meta = json.loads((out / "carrossel.json").read_text(encoding="utf-8"))
    assert meta["total"] == 3 and meta["arquivos"] == ["slide_01.png", "slide_02.png", "slide_03.png"]
    rel = json.loads((out / "slide_01.revisao.json").read_text(encoding="utf-8"))
    assert [s["slide"] for s in rel["slides_precheck"]] == [2, 3]


def test_cli_carrossel_manual_sem_slide_falha(capsys):
    import gerar

    assert gerar.main(["--estilo", "news", "--formato", "carrossel", "--titulo", "Oi", "--sem-revisao"]) == 1
    assert "--slide" in capsys.readouterr().out


@chromium
def test_cli_carrossel_ia_ad_uma_chamada(tmp_path, monkeypatch):
    import gerar

    leg = LegendaResult(gancho="g", corpo="c", cta="x", hashtags=["#a", "#b", "#c"])
    chamadas = []

    def fake(estilo, nicho, tema, kit=None, n=2):
        chamadas.append(n)
        return _ad(), leg, [SlideCarrossel(titulo="Um *dois*", texto="t", icone="zap") for _ in range(n)]

    monkeypatch.setattr(post_pipeline, "gerar_carrossel_ia", fake)
    out = tmp_path / "ad"
    code = gerar.main(["--estilo", "ad", "--formato", "carrossel", "--nicho", "minhamarca", "--tema", "ebook",
                       "--slides-n", "3", "--sem-revisao", "--saida", str(out)])
    assert code == 0 and chamadas == [3]
    assert (out / "slide_04.png").is_file() and (out / "legenda.md").is_file()


@chromium
def test_badge_comecando_com_traco(tmp_path):
    import gerar

    out = tmp_path / "b"
    code = gerar.main(["--estilo", "ad", "--headline", "*Mega* promo", "--features", "zap:A1; gift:B2; star:C3",
                       "--badge", "-50%", "--sem-revisao", "--saida", str(out)])
    assert code == 0
    assert json.loads((out / "post.json").read_text(encoding="utf-8"))["conteudo"]["badge"] == "-50%"


def test_juntar_valores_com_traco_nao_mexe_em_flags():
    import gerar

    assert gerar._juntar_valores_com_traco(["--badge", "-50%", "--pb", "--tag", "--sem-revisao"]) == \
        ["--badge=-50%", "--pb", "--tag", "--sem-revisao"]


def test_wizard_post_pergunta_estilo_formato_marca_tema():
    respostas = iter(["2", "5", "minhamarca", "ebook de design", "3", "n"])
    argv = wizard_post.coletar_post(lambda prompt: next(respostas))
    assert argv == ["--estilo", "ad", "--formato", "carrossel", "--nicho", "minhamarca", "--tema", "ebook de design",
                    "--buscar-fundo", "--marca", "minhamarca", "--slides-n", "3", "--sem-revisao"]
    padrao = iter(["", "9x16", "", "IA no design", ""])
    assert wizard_post.coletar_post(lambda p: next(padrao))[:6] == ["--estilo", "news", "--formato", "9x16",
                                                                     "--nicho", "minhamarca"]
    assert wizard_post.coletar_post(lambda p: "0") is None
    assert wizard_post.escolher_modo(lambda p: "1") == "post"
    assert wizard_post.escolher_modo(lambda p: "2") == "classico"


def test_gerar_sem_flags_abre_wizard_novo(monkeypatch):
    import gerar

    monkeypatch.setattr(wizard_post, "escolher_modo", lambda: "post")
    monkeypatch.setattr(wizard_post, "coletar_post",
                        lambda: ["--estilo", "news", "--formato", "9x16", "--nicho", "minhamarca", "--tema", "x"])
    recebido = {}
    monkeypatch.setattr(post_pipeline, "main_post", lambda args: recebido.update(vars(args)) or 0)
    assert gerar.main([]) == 0
    assert recebido["estilo"] == "news" and recebido["formato"] == "9x16" and recebido["tema"] == "x"
