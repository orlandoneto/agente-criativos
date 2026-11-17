"""Guarda o nome da marca Agente Criativos e o apelido da CLI."""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

import gerar
from app.config import PROJECT_NAME, PROJECT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_marca_e_versao():
    assert PROJECT_NAME == "Agente Criativos"
    # Versão do código = primeira entrada do CHANGELOG (não esquecer de atualizar os dois).
    topo = next(l for l in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if l.startswith("## ["))
    assert topo.startswith(f"## [{PROJECT_VERSION}]")


def test_script_agente_criativos_compila():
    py_compile.compile(str(ROOT / "agente-criativos.py"), doraise=True)


def test_aviso_quando_chamado_como_gerar(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(ROOT / "gerar.py")])
    assert gerar._invocado_como_gerar() is True
    gerar._aviso_apelido()
    err = capsys.readouterr().err
    assert "agente-criativos" in err


def test_sem_aviso_quando_chamado_como_agente_criativos(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(ROOT / "agente-criativos.py")])
    assert gerar._invocado_como_gerar() is False
    gerar._aviso_apelido()
    assert capsys.readouterr().err == ""
