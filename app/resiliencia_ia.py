"""Espera + retenta quando a IA free satura; sugere contornos; salva campanha pendente."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.campanha import garantir_estrutura, pasta_campanha, slugify
from app.cli_style import aviso, dim, ok
from app.config import PROJECT_VERSION

# Ciclo de esperas (~1–5 min). Repete até o usuário escolher s/q ou dar certo.
ESPERAS_SEGUNDOS = (60, 90, 120, 150, 180)
# A cada N ciclos grava pendente.md (checkpoint) mas NÃO para sozinho
CHECKPOINT_A_CADA = len(ESPERAS_SEGUNDOS)
MAX_ESPERAS = CHECKPOINT_A_CADA  # compat testes / mensagens


@dataclass
class EsperaResultado:
    """Resultado de uma espera interruptível."""

    acao: str  # continuar | pular | tipografia | cancelar
    segundos: int = 0


def eh_saturacao_ou_cota(msg: str) -> bool:
    m = (msg or "").lower()
    return any(
        x in m
        for x in (
            "503",
            "alta demanda",
            "sobrecarga",
            "429",
            "cota",
            "esgotad",
            "resource_exhausted",
            "unavailable",
        )
    )


def imprimir_contornos(*, sem_imagem_ja: bool = False) -> None:
    """Sugestões práticas para o cliente (tipografia, ping, horário)."""
    print(aviso("Contornos enquanto a IA free está saturada:"))
    if not sem_imagem_ja:
        print(dim("  1) Só tipografia (menos carga): tecla s agora, ou `--sem-imagem` depois"))
    print(dim("  2) Ping: o motor tenta sozinho; ou `gerar --ping`"))
    print(dim("  3) Horário: free satura de manhã/pico; à noite costuma ir melhor."))
    print(dim("  4) Auto: fica tentando até dar certo ou você apertar s / q."))
    print(dim("     Enter=pular esta espera | s=tipografia | q=parar este job"))


def _ler_tecla_win() -> str | None:
    import msvcrt

    if not msvcrt.kbhit():
        return None
    ch = msvcrt.getwch()
    # setas etc. vêm com prefixo \x00 ou \xe0 + segundo byte
    if ch in ("\x00", "\xe0"):
        msvcrt.getwch()
        return None
    return ch


def _sleep_interruptivel(segs: int, *, sleep_fn=time.sleep) -> str:
    """
    Espera até `segs` segundos, mas o usuário pode digitar:
      Enter → pular | s → tipografia | q → cancelar
    Retorna: '' (timeout) | pular | tipografia | cancelar
    """
    print(
        dim(
            f"  Aguardando até {segs}s — digite agora: "
            "Enter=pular espera | s=só tipografia | q=cancelar job"
        )
    )
    if not sys.stdin.isatty():
        sleep_fn(segs)
        return ""

    # Windows: msvcrt (Cmder / cmd) — não trava o teclado
    if sys.platform == "win32":
        for remaining in range(segs, 0, -1):
            if remaining == segs or remaining % 10 == 0 or remaining <= 5:
                print(dim(f"  … {remaining}s restantes (Enter / s / q)   "), end="\r", flush=True)
            fim = time.time() + 1.0
            while time.time() < fim:
                ch = _ler_tecla_win()
                if ch is None:
                    sleep_fn(0.05)
                    continue
                print()  # limpa linha do countdown
                if ch in ("\r", "\n"):
                    print(ok("  → espera pulada"))
                    return "pular"
                low = ch.lower()
                if low == "s":
                    print(ok("  → tipografia"))
                    return "tipografia"
                if low == "q":
                    print(aviso("  → job cancelado"))
                    return "cancelar"
                # ignora outras teclas
        print()
        return ""

    # Unix: select no stdin
    import select

    for remaining in range(segs, 0, -1):
        if remaining == segs or remaining % 10 == 0 or remaining <= 5:
            print(dim(f"  … {remaining}s restantes (Enter / s / q)   "), end="\r", flush=True)
        pronto, _, _ = select.select([sys.stdin], [], [], 1.0)
        if not pronto:
            continue
        linha = sys.stdin.readline().strip().lower()
        print()
        if linha in {"", "p", "pular"}:
            print(ok("  → espera pulada"))
            return "pular"
        if linha in {"s", "sim", "tipografia"}:
            print(ok("  → tipografia"))
            return "tipografia"
        if linha in {"q", "sair", "cancelar"}:
            print(aviso("  → job cancelado"))
            return "cancelar"
    print()
    return ""


def esperar_ia(
    tentativa: int,
    *,
    permitir_tipografia: bool = True,
    sleep_fn=time.sleep,
) -> EsperaResultado:
    """
    Espera interruptível. O ciclo de segundos se repete (60…180…60…).
    Só para se o usuário apertar s/q (ou Enter para pular esta espera).
    """
    idx = (max(1, tentativa) - 1) % len(ESPERAS_SEGUNDOS)
    segs = int(ESPERAS_SEGUNDOS[idx])
    print(
        aviso(
            f"IA saturada — espera {segs}s (tentativa #{tentativa}). "
            "Continua sozinho até você escolher."
        )
    )
    print(dim("  Digite agora: Enter=pular | s=tipografia | q=parar"))
    print(dim("  Free satura de manhã/pico; à noite costuma ir melhor."))
    if not permitir_tipografia:
        print(dim("  (tipografia já ativa — Enter pula | q cancela)"))

    acao_raw = _sleep_interruptivel(segs, sleep_fn=sleep_fn)
    if acao_raw == "tipografia" and not permitir_tipografia:
        acao_raw = "pular"
    if acao_raw in {"pular", "tipografia", "cancelar"}:
        return EsperaResultado(acao=acao_raw, segundos=0)
    return EsperaResultado(acao="continuar", segundos=segs)


def tentar_ping() -> bool:
    """True se PING_OK (ou texto contendo PING)."""
    try:
        from app.gemini_client import ping

        print(dim("  ↻ ping Gemini…"))
        texto = ping()
        print(dim(f"  ↻ ping: {texto}"))
        return "PING" in (texto or "").upper()
    except Exception as exc:  # noqa: BLE001
        print(dim(f"  ↻ ping falhou: {exc}"))
        return False


def gravar_campanha_pendente(
    nicho: str,
    campanha: str,
    *,
    tema: str = "",
    plataforma: str = "",
    jobs_ok: list[str] | None = None,
    jobs_falha: list[str] | None = None,
    pastas_salvas: list[str] | None = None,
    motivo: str = "",
) -> Path | None:
    """Marca a campanha como pendente (não apaga entregas)."""
    if not (campanha or "").strip():
        return None
    garantir_estrutura(nicho, campanha, tema=tema)
    root = pasta_campanha(nicho, campanha)
    path = root / "pendente.md"
    linhas = [
        f"# Campanha pendente — {slugify(campanha)}",
        "",
        f"- Atualizado: {datetime.now().isoformat(timespec='seconds')}",
        f"- Motor: {PROJECT_VERSION}",
        f"- Nicho: `{slugify(nicho)}`",
        f"- Plataforma: {plataforma or '(n/d)'}",
        f"- Tema: {tema or '(n/d)'}",
        f"- Motivo: {motivo or 'IA free saturada após 5 esperas'}",
        "",
        "## Status",
        "",
        "A campanha foi **salva**. Rode `gerar` de novo com o mesmo nicho/campanha.",
        "Sugestões: `--sem-imagem`, `gerar --ping`, tentar à noite.",
        "",
        "## Jobs ok",
        "",
    ]
    for j in jobs_ok or []:
        linhas.append(f"- {j}")
    if not jobs_ok:
        linhas.append("- (nenhum nesta corrida)")
    linhas += ["", "## Jobs pendentes / falha", ""]
    for j in jobs_falha or []:
        linhas.append(f"- {j}")
    if not jobs_falha:
        linhas.append("- (nenhum)")
    linhas += ["", "## Pastas salvas", ""]
    for p in pastas_salvas or []:
        linhas.append(f"- `{p}`")
    if not pastas_salvas:
        linhas.append("- (nenhuma)")
    linhas.append("")
    path.write_text("\n".join(linhas), encoding="utf-8")
    print(ok(f"Campanha salva como pendente: {path}"))
    return path
