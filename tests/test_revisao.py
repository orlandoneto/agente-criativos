"""Revisão automática: pré-checagem determinística + IA de visão (mockada) + ciclo de novas tentativas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app import revisao as rv

NOTA_ALTA = dict(legibilidade=9, contraste=9, texto_cortado=10, fundo_qualidade=9, artefatos_ia=9, rostos_maos=10)
NOTA_BAIXA = dict(legibilidade=8, contraste=7, texto_cortado=10, fundo_qualidade=4, artefatos_ia=2, rostos_maos=10,
                  problemas=["letras falsas na tela do notebook"])


def _chromium_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001
        return False


chromium = pytest.mark.skipif(not _chromium_ok(), reason="Chromium do Playwright não instalado")


def test_razao_contraste_wcag():
    assert rv.razao_contraste(1.0, 0.0) == 21.0
    assert rv.razao_contraste(0.5, 0.5) == 1.0
    assert rv._lum_rgb(255, 255, 255) == pytest.approx(1.0)


def test_nota_ia_um_criterio_ruim_derruba():
    assert rv.NotasIA(**NOTA_ALTA).nota() >= 9
    baixa = rv.NotasIA(**NOTA_BAIXA)
    assert baixa.nota() == pytest.approx(4.5)  # min(6.83, 2 + 2.5)
    assert rv.NotasIA(**{**NOTA_ALTA, "problemas": "um só"}).problemas == ["um só"]


def test_nota_final_respeita_precheck():
    ia = rv.NotasIA(**NOTA_ALTA)
    assert rv.nota_final({"ok": True, "nota": 10}, ia) == ia.nota()
    assert rv.nota_final({"ok": False, "nota": 5.5}, ia) == 5.5
    assert rv.nota_final({"ok": True, "nota": 8}, None) == 8


def _html(corpo: str, fundo: str = "#000") -> str:
    return (f"<html><body style='margin:0;width:400px;height:600px;background:{fundo};font-family:sans-serif'>"
            f"{corpo}<script>document.body.dataset.ready='1'</script></body></html>")


@chromium
def test_precheck_contraste_estouro_e_zona_segura(tmp_path):
    from app.post_render import render_html_png_checado

    ok_html = _html("<h1 style='color:#fff;font-size:40px;margin:200px 20px'>Texto legível</h1>")
    _, pre = render_html_png_checado(ok_html, 400, 600, tmp_path / "a.png")
    assert pre["ok"] and pre["contraste_min"] > 15 and pre["textos"] == 1

    ruim = _html("<p style='color:#eee;font-size:14px;margin:200px 20px'>quase invisível</p>", fundo="#fff")
    _, pre = render_html_png_checado(ruim, 400, 600, tmp_path / "b.png")
    assert not pre["ok"] and pre["contraste_falhas"][0]["minimo"] == 4.5

    corta = _html("<div style='height:30px;overflow:hidden;margin:200px 20px;color:#fff;font-size:28px;width:200px'>"
                  "linha um linha dois linha três linha quatro</div>")
    _, pre = render_html_png_checado(corta, 400, 600, tmp_path / "c.png")
    assert pre["estouros"] and not pre["ok"]

    topo = _html("<h1 style='color:#fff;font-size:30px;margin:10px'>no topo</h1>"
                 "<small data-zona-livre style='color:#fff;position:absolute;bottom:4px'>crédito</small>")
    _, pre = render_html_png_checado(topo, 400, 600, tmp_path / "d.png", safe={"topo": 100, "base": 100})
    assert [z["texto"] for z in pre["zona_segura"]] == ["no topo"]


def _fake_render(pre=None):
    def render(fundo, dst: Path, escurecer: bool = False):
        dst.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (40, 50), "black").save(dst)
        return dst, dict(pre or {"ok": True, "nota": 10})
    return render


def _fake_fundo(provedores):
    chamadas = []

    def gerar(n, usados, pasta):
        chamadas.append(list(usados))
        f = pasta / "fundo.png"
        Image.new("RGB", (10, 10), "gray").save(f)
        return f, provedores[n - 1]
    return gerar, chamadas


def test_ciclo_refaz_com_proximo_provedor_ate_aprovar(tmp_path):
    notas = iter([rv.NotasIA(**NOTA_BAIXA), rv.NotasIA(**NOTA_ALTA)])
    gerar, chamadas = _fake_fundo(["aihorde", "pollinations", "pexels"])
    res = rv.ciclo_revisao(pasta=tmp_path, renderizar=_fake_render(), gerar_fundo=gerar,
                           revisor=lambda png, **k: (next(notas), "fake/vision", ""), log=lambda m: None)
    assert [t.numero for t in res.tentativas] == [1, 2]
    assert chamadas == [[], ["aihorde"]]  # 2ª tentativa sabe que aihorde já foi usado
    assert res.melhor.numero == 2 and not res.precisa_revisao and res.motivo_parada == "aprovado"
    destino = tmp_path / "post.png"
    rv.promover_melhor(res, destino)
    dados = json.loads((tmp_path / "post.revisao.json").read_text(encoding="utf-8"))
    assert dados["aprovado"] and dados["melhor_tentativa"] == 2 and len(dados["tentativas"]) == 2
    assert destino.is_file() and (tmp_path / "fundo.png").is_file()


def test_ciclo_entrega_melhor_e_marca_revisao_quando_tudo_baixo(tmp_path):
    seq = iter([4.0, 6.0, 5.0])

    def revisor(png, **k):
        v = next(seq)
        return rv.NotasIA(**{c: v for c in rv.CRITERIOS}), "fake", ""

    gerar, _ = _fake_fundo(["a", "b", "c"])
    res = rv.ciclo_revisao(pasta=tmp_path, renderizar=_fake_render(), gerar_fundo=gerar, revisor=revisor,
                           tentativas_extra=2, log=lambda m: None)
    assert len(res.tentativas) == 3 and res.melhor.numero == 2 and res.precisa_revisao
    assert res.motivo_parada == "tentativas esgotadas"


def test_ciclo_sem_ia_disponivel_para_e_marca_revisao(tmp_path):
    gerar, _ = _fake_fundo(["a", "b", "c"])
    res = rv.ciclo_revisao(pasta=tmp_path, renderizar=_fake_render(), gerar_fundo=gerar,
                           revisor=lambda png, **k: (None, "none", "gemini: 429"), log=lambda m: None)
    assert len(res.tentativas) == 1 and res.precisa_revisao
    assert res.motivo_parada == "IA de visão indisponível" and res.melhor.erro_ia == "gemini: 429"


def test_ciclo_sem_revisao_nao_chama_ia_e_nao_refaz(tmp_path):
    gerar, _ = _fake_fundo(["a", "b", "c"])
    res = rv.ciclo_revisao(pasta=tmp_path, renderizar=_fake_render(), gerar_fundo=gerar, revisao_ia=False,
                           revisor=lambda *a, **k: pytest.fail("não deveria chamar IA"), log=lambda m: None)
    assert len(res.tentativas) == 1 and res.melhor.aprovado and res.melhor.provedor_ia == "desligada"


def test_ciclo_fundo_fixo_nao_refaz_e_prazo_zero_nao_chama_ia(tmp_path):
    res = rv.ciclo_revisao(pasta=tmp_path, renderizar=_fake_render(), fundo_fixo=None, prazo_s=0,
                           revisor=lambda *a, **k: pytest.fail("prazo zero"), log=lambda m: None)
    assert len(res.tentativas) == 1 and "prazo" in res.melhor.erro_ia and res.precisa_revisao


def test_ciclo_precheck_ruim_reprova_mesmo_com_ia_boa(tmp_path):
    res = rv.ciclo_revisao(pasta=tmp_path, renderizar=_fake_render({"ok": False, "nota": 7}),
                           revisor=lambda png, **k: (rv.NotasIA(**NOTA_ALTA), "fake", ""), log=lambda m: None)
    assert not res.melhor.aprovado and res.melhor.nota == 7


def test_revisar_png_ia_cooldown_e_fallback(tmp_path, monkeypatch):
    png = tmp_path / "x.png"
    Image.new("RGB", (1000, 1250), "white").save(png)
    vistos = []

    def gemini(img, prompt, timeout):
        vistos.append("gemini")
        raise rv.VisaoIndisponivel("gemini: 503")

    def zai(img, prompt, timeout):
        vistos.append("zai")
        with Image.open(__import__("io").BytesIO(img)) as im:
            assert im.width == 768 and im.format == "JPEG"
        return rv.NotasIA(**NOTA_ALTA), "zai/glm-4.6v-flash"

    monkeypatch.setattr(rv, "PROVEDORES_VISAO", [("gemini", gemini), ("zai", zai)])
    notas, prov, erro = rv.revisar_png_ia(png)
    assert prov == "zai/glm-4.6v-flash" and vistos == ["gemini", "zai"] and notas.nota() >= 9

    vistos.clear()
    rv.marcar_cooldown("gemini", 60)
    assert rv.em_cooldown("gemini") > 50
    rv.revisar_png_ia(png)
    assert vistos == ["zai"]  # gemini em cooldown (persistido) é pulado

    rv.marcar_cooldown("zai", 60)
    notas, prov, erro = rv.revisar_png_ia(png)
    assert notas is None and "cooldown" in erro


def test_zai_sem_chave_e_indisponivel(monkeypatch):
    monkeypatch.setattr(rv, "ZAI_API_KEY", "")
    with pytest.raises(rv.VisaoIndisponivel, match="sem chave"):
        rv._revisar_zai(b"x", "p", 5)


def test_zai_429_marca_cooldown(monkeypatch):
    import httpx

    monkeypatch.setattr(rv, "ZAI_API_KEY", "fake")
    real = httpx.Client
    transporte = httpx.MockTransport(lambda req: httpx.Response(429, headers={"retry-after": "33"}))
    monkeypatch.setattr(rv.httpx, "Client", lambda **kw: real(transport=transporte, **kw))
    with pytest.raises(rv.VisaoIndisponivel, match="429"):
        rv._revisar_zai(b"x", "p", 5)
    assert 30 < rv.em_cooldown("zai") <= 33


def test_zai_resposta_ok(monkeypatch):
    import httpx

    monkeypatch.setattr(rv, "ZAI_API_KEY", "fake")
    corpo = {"choices": [{"message": {"content": "```json\n" + json.dumps(NOTA_ALTA) + "\n```"}}]}
    real = httpx.Client
    transporte = httpx.MockTransport(lambda req: httpx.Response(200, json=corpo))
    monkeypatch.setattr(rv.httpx, "Client", lambda **kw: real(transport=transporte, **kw))
    notas, prov = rv._revisar_zai(b"x", "p", 5)
    assert prov.startswith("zai/") and notas.legibilidade == 9


@chromium
def test_cli_revisao_refaz_fundo_e_grava_relatorio(tmp_path, monkeypatch):
    import gerar
    from app import image_gen, post_pipeline

    usados_por_tentativa = []

    def fake_cena(estilo, fonte, prompt, titulo, apoio, pasta, evitar=None):
        usados_por_tentativa.append(list(evitar or []))
        f = pasta / "fundo.png"
        Image.new("RGB", (540, 675), "#202030").save(f)
        prov = ["aihorde", "pollinations"][len(usados_por_tentativa) - 1]
        return image_gen.CenaResult(f, prov, "ok")

    notas = iter([rv.NotasIA(**NOTA_BAIXA), rv.NotasIA(**NOTA_ALTA)])
    monkeypatch.setattr(post_pipeline, "buscar_fundo_cena", fake_cena)
    monkeypatch.setattr(rv, "revisar_png_ia", lambda png, **k: (next(notas), "fake/vision", ""))
    out = tmp_path / "ad"
    code = gerar.main(["--estilo", "ad", "--headline", "*Crie posts* em 10 minutos", "--pill", "Ebook",
                       "--features", "zap:Rápido; clock:Fácil; gift:Grátis", "--cta", "Baixe agora",
                       "--buscar-fundo", "--saida", str(out)])
    assert code == 0
    assert usados_por_tentativa == [[], ["aihorde"]]
    rel = json.loads((out / "post.revisao.json").read_text(encoding="utf-8"))
    assert rel["aprovado"] and rel["melhor_tentativa"] == 2
    assert rel["tentativas"][0]["ia"]["artefatos_ia"] == 2
    post = json.loads((out / "post.json").read_text(encoding="utf-8"))
    assert post["revisao"]["nota_final"] >= 7 and "precheck" in post
    assert (out / "fundo.png").is_file() and (out / "tentativas" / "t1" / "post.png").is_file()


@chromium
def test_cli_sem_revisao(tmp_path, monkeypatch):
    import gerar

    monkeypatch.setattr(rv, "revisar_png_ia", lambda *a, **k: pytest.fail("--sem-revisao não chama IA"))
    out = tmp_path / "n"
    code = gerar.main(["--estilo", "news", "--titulo", "Teste curto", "--sem-revisao", "--saida", str(out)])
    assert code == 0
    rel = json.loads((out / "post.revisao.json").read_text(encoding="utf-8"))
    assert rel["revisao_ia"] is False and len(rel["tentativas"]) == 1


def test_ciclo_contraste_ruim_escurece_e_reaproveita_fundo_bom(tmp_path):
    pres = iter([{"ok": False, "nota": 8.5, "contraste_falhas": [{"ratio": 2.1}]}, {"ok": True, "nota": 10}])
    chamadas_render = []

    def render(fundo, dst, escurecer=False):
        chamadas_render.append((fundo, escurecer))
        Image.new("RGB", (40, 50), "black").save(dst)
        return dst, next(pres)

    gerar, chamadas_fundo = _fake_fundo(["aihorde", "pollinations"])
    boa_no_fundo = rv.NotasIA(**NOTA_ALTA)
    res = rv.ciclo_revisao(pasta=tmp_path, renderizar=render, gerar_fundo=gerar,
                           revisor=lambda png, **k: (boa_no_fundo, "fake", ""), log=lambda m: None)
    assert len(chamadas_fundo) == 1  # 2ª tentativa reaproveitou o fundo (sem gastar cota de imagem)
    assert chamadas_render[1] == (chamadas_render[0][0], True)
    assert res.melhor.numero == 2 and res.melhor.escurecido and res.melhor.aprovado


def test_com_prazo_corta_provedor_lento():
    import time as _t

    def lento(img, prompt, timeout):
        _t.sleep(5)

    lento.__name__ = "gemini_lento"
    inicio = _t.monotonic()
    with pytest.raises(rv.VisaoIndisponivel, match="timeout"):
        rv._com_prazo(lento, b"x", "p", 0.2)
    assert _t.monotonic() - inicio < 4


def test_gemini_visao_troca_de_modelo_no_503_e_cooldown_no_429(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "GEMINI_API_KEY", "fake")
    monkeypatch.setattr(rv, "GEMINI_MODELOS_VISAO", ("gemini-flash-latest", "gemini-flash-lite-latest"))
    tentados = []

    class Resp:
        text = json.dumps(NOTA_ALTA)

    class Modelos:
        def generate_content(self, model, contents, config):
            tentados.append(model)
            if model == "gemini-flash-latest":
                raise RuntimeError("503 UNAVAILABLE high demand")
            return Resp()

    class Cli:
        models = Modelos()

    monkeypatch.setattr(rv, "_cliente_gemini_visao", lambda t: Cli())
    notas, prov = rv._revisar_gemini(b"img", "p", 20)
    assert prov == "gemini/gemini-flash-lite-latest" and tentados == ["gemini-flash-latest", "gemini-flash-lite-latest"]

    class Modelos429:
        def generate_content(self, model, contents, config):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    Cli.models = Modelos429()
    with pytest.raises(rv.VisaoIndisponivel, match="429"):
        rv._revisar_gemini(b"img", "p", 20)
    assert rv.em_cooldown("gemini") > 100
