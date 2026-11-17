"""Fase 1 — posts únicos Instagram (news/ad): schemas, HTML, PNG, CLI."""

from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError

from app import fontes, icones, post_pipeline, post_render
from app.schemas import AdFeature, AdResult, HeadlinePart, LegendaResult, NewsPostIA, NewsResult

SNAP = Path(__file__).parent / "snapshots"


def _ad(n_feats: int = 4, **kw) -> AdResult:
    feats = [AdFeature(icone=i, texto=t) for i, t in
             [("zap", "Acesso imediato"), ("gift", "Bônus exclusivos"),
              ("shield-check", "Garantia de 7 dias"), ("users", "Comunidade VIP")][:n_feats]]
    base = dict(pill="Ebook gratuito", headline_parts=[HeadlinePart(texto="Domine o design", destaque=True),
                HeadlinePart(texto="em 7 dias")], badge="Grátis", features=feats, cta="Baixe agora")
    base.update(kw)
    return AdResult(**base)


def _news(**kw) -> NewsResult:
    base = dict(tag="Urgente", titulo="Calor extremo atinge 40 graus no Nordeste",
                destaques=["calor extremo", "40 graus"], apoio="Defesa Civil emite alerta laranja")
    base.update(kw)
    return NewsResult(**base)


def _sem_fontes(html: str) -> str:
    return re.sub(r"@font-face\{[^}]*\}", "@font-face{…}", html)


# ---------------------------------------------------------------- assets

def test_fontes_ofl_presentes_com_licenca():
    assert fontes.fontes_faltando() == []
    for lic in ("OFL-Anton.txt", "OFL-BebasNeue.txt", "OFL-Montserrat.txt"):
        assert "SIL OPEN FONT LICENSE" in (fontes.FONTS_DIR / lic).read_text(encoding="utf-8").upper()
    css = fontes.font_face_css()
    for fam in ("'Anton'", "'Bebas Neue'", "'Montserrat'"):
        assert f"font-family:{fam}" in css
    assert "font-weight:100 900" in css


def test_icones_lucide_licenca_e_normalizacao():
    assert "ISC" in (icones.ICONS_DIR / "LICENSE").read_text(encoding="utf-8")
    assert {"zap", "gift", "check", "arrow-right"} <= set(icones.icones_disponiveis())
    assert icones.normalizar_icone("Raio") == "zap"
    assert icones.normalizar_icone("shield_check") == "shield-check"
    assert icones.normalizar_icone("nao-existe") == "check"
    svg = icones.svg_inline("zap", 30)
    assert svg.startswith("<svg") and 'width="30"' in svg and "currentColor" in svg


# ---------------------------------------------------------------- schemas

def test_news_destaques_precisam_estar_no_titulo():
    assert _news().destaques == ["calor extremo", "40 graus"]
    with pytest.raises(ValidationError, match="fora do título"):
        _news(destaques=["chuva"])


def test_news_destaque_e_palavra_inteira_e_ignora_caixa():
    assert NewsResult(titulo="Ação em Marte", destaques=["AÇÃO", "marte"]).destaques
    with pytest.raises(ValidationError):
        NewsResult(titulo="Ação em Marte", destaques=["mar"])


def test_news_limites():
    with pytest.raises(ValidationError):
        NewsResult(titulo="x" * 121)
    with pytest.raises(ValidationError):
        NewsResult(titulo="abc def", destaques=["abc"] * 5)


def test_ad_result_contrato():
    ad = _ad()
    assert ad.headline_texto() == "Domine o design em 7 dias"
    with pytest.raises(ValidationError):
        _ad(n_feats=2)
    with pytest.raises(ValidationError):
        _ad(features=[AdFeature(texto=f"item {i}") for i in range(5)])
    assert AdFeature(icone="foguete", texto="Rápido").icone == "rocket"
    assert AdFeature(icone="inventado", texto="Rápido").icone == "check"


def test_news_post_ia_filtra_destaques_invalidos():
    leg = LegendaResult(gancho="g", corpo="c", cta="x", hashtags=["a", "b", "c"])
    r = NewsPostIA(titulo="Nova lei muda o trânsito", destaques=["lei", "inventado"], legenda=leg)
    card = r.to_card()
    assert card.destaques == ["lei"] and card.tag == "Notícia"


# ---------------------------------------------------------------- helpers

def test_segmentos_destaque():
    segs = post_render.segmentos_destaque("O calor extremo chegou", ["CALOR EXTREMO"])
    assert segs == [{"texto": "O ", "hl": False}, {"texto": "calor extremo", "hl": True},
                    {"texto": " chegou", "hl": False}]
    assert post_render.segmentos_destaque("Sem nada", []) == [{"texto": "Sem nada", "hl": False}]


def test_parse_headline_e_features():
    partes = post_pipeline.parse_headline("*Domine o design* em 7 dias")
    assert [(p.texto, p.destaque) for p in partes] == [("Domine o design", True), ("em 7 dias", False)]
    feats = post_pipeline.parse_features("zap:Entrega imediata; Sem ícone; gift: Bônus")
    assert [(f.icone, f.texto) for f in feats] == [("zap", "Entrega imediata"), ("check", "Sem ícone"), ("gift", "Bônus")]
    with pytest.raises(ValueError):
        post_pipeline.parse_headline("  ")


def test_handle_e_formatos():
    assert post_render.normalizar_handle("minhamarca") == "@minhamarca"
    assert post_render.normalizar_handle("", "Minha Marca") == "@minhamarca"
    assert post_render.tamanho("4x5") == (1080, 1350) and post_render.tamanho("1x1") == (1080, 1080)
    assert post_render.tamanho("9x16") == (1080, 1920) and post_render.tamanho("carrossel") == (1080, 1350)
    with pytest.raises(ValueError):
        post_render.tamanho("2x3")


def test_cadeia_para_prioriza_stock_no_news():
    base = ["cloudflare", "pollinations", "pexels", "unsplash"]
    assert post_pipeline.cadeia_para("news", "auto", base)[:2] == ["pexels", "unsplash"]
    assert post_pipeline.cadeia_para("ad", "auto", base)[0] == "cloudflare"
    assert post_pipeline.cadeia_para("ad", "stock", base)[0] == "pexels"


# ---------------------------------------------------------------- HTML estrutura / snapshot

def test_html_news_estrutura(tmp_path):
    foto = tmp_path / "fundo.png"
    Image.new("RGB", (40, 50), "gray").save(foto)
    foto.with_suffix(".json").write_text(json.dumps({"atribuicao": "Foto: Ana / Pexels"}), encoding="utf-8")
    html = post_render.html_news(_news(), formato="4x5", fundo=foto, pb=True,
                                 marca=post_render.Marca(nome="Minha Marca", handle="@minhamarca"), cor_destaque="vermelho")
    assert "--w: 1080px; --h: 1350px" in html
    assert '<span class="hl">Calor extremo</span>' in html and '<span class="hl">40 graus</span>' in html
    assert "grayscale(1)" in html and "data:image/png;base64," in html
    assert "Urgente" in html and "@minhamarca" in html and "Foto: Ana / Pexels" in html
    assert "--hl: #FF2D2D" in html and "font-family:'Anton'" in html


def test_html_news_escapa_texto():
    html = post_render.html_news(NewsResult(titulo="<script>alert(1)</script> agora"), formato="1x1")
    assert "<script>alert(1)" not in html and "&lt;script&gt;" in html
    assert "--w: 1080px; --h: 1080px" in html and "grayscale" not in html


def test_html_ad_estrutura(tmp_path):
    mock = tmp_path / "mock.png"
    Image.new("RGBA", (30, 40), (255, 0, 0, 128)).save(mock)
    html = post_render.html_ad(_ad(), formato="4x5", mockup=mock, marca=post_render.Marca(handle="@minhamarca"))
    assert html.count('class="feat"') == 4 and html.count("<svg") == 5  # 4 ícones + seta CTA
    assert "repeat(2, 1fr)" in html
    assert '<span class="hl">Domine o design</span>' in html
    assert 'class="badge">Grátis<' in html and "Baixe agora" in html
    assert '<img src="data:image/png;base64,' in html


def test_html_ad_3_features_em_linha():
    html = post_render.html_ad(_ad(n_feats=3, badge=""), formato="1x1")
    assert "repeat(3, 1fr)" in html and 'class="badge"' not in html


@pytest.mark.parametrize("nome,fazer", [
    ("news_4x5.html", lambda: post_render.html_news(_news(), formato="4x5",
                                                    marca=post_render.Marca(handle="@minhamarca"))),
    ("ad_4x5.html", lambda: post_render.html_ad(_ad(), formato="4x5", marca=post_render.Marca(handle="@minhamarca"))),
])
def test_snapshot_html(nome, fazer):
    atual = _sem_fontes(fazer()).replace("\r\n", "\n")
    alvo = SNAP / nome
    if os.getenv("UPDATE_SNAPSHOTS") == "1" or not alvo.exists():
        alvo.parent.mkdir(exist_ok=True)
        alvo.write_text(atual, encoding="utf-8", newline="\n")
    assert atual == alvo.read_text(encoding="utf-8").replace("\r\n", "\n")


# ---------------------------------------------------------------- PNG real (Playwright local)

def _chromium_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001
        return False


chromium = pytest.mark.skipif(not _chromium_ok(), reason="Chromium do Playwright não instalado")


@chromium
@pytest.mark.parametrize("estilo,formato", [("news", "4x5"), ("news", "1x1"), ("ad", "4x5"), ("ad", "1x1")])
def test_png_tamanho_exato(tmp_path, estilo, formato):
    conteudo = _news() if estilo == "news" else _ad()
    png = post_pipeline.gerar_post(estilo, formato, conteudo, tmp_path / "post.png",
                                   marca=post_render.Marca(handle="@teste"))
    with Image.open(png) as img:
        assert img.format == "PNG" and img.size == post_render.FORMATOS[formato]
    dados = json.loads((tmp_path / "post.json").read_text(encoding="utf-8"))
    assert dados["estilo"] == estilo and dados["formato"] == formato


@chromium
def test_fontes_carregam_e_titulo_cabe():
    from playwright.sync_api import sync_playwright

    longo = NewsResult(titulo="Uma manchete propositalmente longa para testar o ajuste automático do título no card",
                       destaques=["ajuste automático"], apoio="Linha de apoio em Montserrat")
    html = post_render.html_news(longo, formato="1x1", marca=post_render.Marca(handle="@teste"))
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page(viewport={"width": 1080, "height": 1080})
        page.set_content(html, wait_until="load")
        page.wait_for_function("document.body.dataset.ready === '1'")
        assert page.evaluate("document.fonts.check('40px Anton')")
        assert page.evaluate("document.fonts.check('800 40px Montserrat')")
        cabe = page.evaluate("(() => { const e = document.getElementById('titulo');"
                             " return e.offsetHeight <= parseFloat(e.dataset.maxh) && e.scrollWidth <= e.clientWidth + 1; })()")
        assert cabe
        page.set_content(post_render.html_news(NewsResult(titulo="Curto e grosso"), formato="4x5"), wait_until="load")
        page.wait_for_function("document.body.dataset.ready === '1'")
        assert float(page.evaluate("document.getElementById('titulo').dataset.fit")) >= 140  # título curto fica grande
        b.close()


@chromium
def test_cli_manual_news_sem_ia(tmp_path, monkeypatch):
    import gerar

    monkeypatch.setattr(post_pipeline, "gerar_texto_ia", lambda *a: pytest.fail("não deveria chamar IA"))
    foto = tmp_path / "foto.jpg"
    Image.new("RGB", (300, 400), "navy").save(foto, "JPEG")
    out = tmp_path / "saida"
    code = gerar.main(["--estilo", "news", "--formato", "1x1", "--titulo", "Teste de manchete",
                       "--destaques", "manchete", "--fundo", str(foto), "--handle", "minhamarca",
                       "--saida", str(out)])
    assert code == 0
    with Image.open(out / "post.png") as img:
        assert img.size == (1080, 1080)
    assert (out / "fundo.jpg").is_file()


@chromium
def test_cli_ia_ad_usa_uma_chamada_e_salva_legenda(tmp_path, monkeypatch):
    import gerar

    leg = LegendaResult(gancho="Gancho", corpo="Corpo", cta="Comente", hashtags=["#a", "#b", "#c"])
    chamadas = []

    def fake(estilo, nicho, tema, kit=None):
        chamadas.append((estilo, nicho, tema))
        assert kit is not None and kit.handle == "@minhamarca"  # brand kit da minhamarca chega ao gerador
        return _ad(), leg

    monkeypatch.setattr(post_pipeline, "gerar_texto_ia", fake)
    out = tmp_path / "ad"
    code = gerar.main(["--estilo", "ad", "--nicho", "minhamarca", "--tema", "ebook de design",
                       "--saida", str(out)])
    assert code == 0 and len(chamadas) == 1
    assert "#a #b #c" in (out / "legenda.md").read_text(encoding="utf-8")


def test_cli_ia_sem_tema_falha_cedo(tmp_path, capsys):
    args = SimpleNamespace(estilo="news", formato="4x5", nicho=None, handle=None, titulo=None, tema=None)
    assert post_pipeline.main_post(args) == 1
    assert "modo IA precisa" in capsys.readouterr().out


def test_prompt_post_pede_json_com_legenda():
    p = post_pipeline.prompt_post("news", "minhamarca", "IA no design")
    assert '"destaques"' in p and '"legenda"' in p and "COPIADAS EXATAMENTE" in p
    p2 = post_pipeline.prompt_post("ad", "minhamarca", "ebook")
    assert '"headline_parts"' in p2 and '"features"' in p2
