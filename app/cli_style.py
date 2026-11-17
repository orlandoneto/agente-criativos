"""Cores ANSI simples para o wizard (Cmder / Windows Terminal)."""

from __future__ import annotations

import os
import sys


def _enable_windows_ansi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:  # noqa: BLE001
        pass


_enable_windows_ansi()

_NO_COLOR = os.getenv("NO_COLOR", "").strip() != "" or not sys.stdout.isatty()


class C:
    reset = "\033[0m"
    dim = "\033[2m"
    bold = "\033[1m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    magenta = "\033[35m"
    red = "\033[31m"
    white = "\033[97m"


def paint(texto: str, *codes: str) -> str:
    if _NO_COLOR or not codes:
        return texto
    return f"{''.join(codes)}{texto}{C.reset}"


def titulo(texto: str) -> str:
    return paint(texto, C.bold, C.cyan)


def ok(texto: str) -> str:
    return paint(texto, C.green)


def aviso(texto: str) -> str:
    return paint(texto, C.yellow)


def dim(texto: str) -> str:
    return paint(texto, C.dim)


def destaque(texto: str) -> str:
    return paint(texto, C.bold, C.magenta)


def erro(texto: str) -> str:
    return paint(texto, C.red)
