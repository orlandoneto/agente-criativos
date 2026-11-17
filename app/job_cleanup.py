"""Remove jobs incompletos — não deixa lixo para o cliente."""

from __future__ import annotations

import shutil
from pathlib import Path


def job_parece_completo(pasta: Path) -> bool:
    """Tem entrega em 02_resultado com pelo menos um arquivo útil."""
    if not pasta.is_dir():
        return False
    res = pasta / "02_resultado"
    if not res.is_dir():
        return False
    uteis = [
        p
        for p in res.iterdir()
        if p.is_file() and p.suffix.lower() in {".md", ".png", ".jpg", ".jpeg", ".webp", ".mp4"}
    ]
    return len(uteis) > 0


def remover_pasta_job(pasta: Path | None, *, motivo: str = "") -> bool:
    """Apaga pasta de job incompleto. Retorna True se removeu."""
    if pasta is None:
        return False
    try:
        p = pasta.resolve()
    except OSError:
        return False
    if not p.is_dir():
        return False
    # Segurança: só apaga se parecer job do motor
    if not ((p / "01_fases").exists() or (p / "02_resultado").exists() or (p / "LEIA-ME.md").exists()):
        return False
    shutil.rmtree(p, ignore_errors=True)
    return not p.exists()


def limpar_se_incompleto(pasta: Path | None) -> bool:
    """Se a pasta existe e não está completa, remove."""
    if pasta is None or not pasta.exists():
        return False
    if job_parece_completo(pasta):
        return False
    return remover_pasta_job(pasta, motivo="incompleto")
