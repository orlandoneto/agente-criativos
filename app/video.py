"""Monta MP4 9:16 (Reels / TikTok) a partir dos PNGs do carrossel — sem IA de vídeo."""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image

from app.config import (
    REELS_HEIGHT,
    REELS_WIDTH,
    VIDEO_FPS,
    VIDEO_SEGUNDOS_POR_SLIDE,
)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "#0F172A").lstrip("#")
    if len(h) != 6:
        return (15, 23, 42)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def slide_para_reels(
    png: Path,
    *,
    fundo_hex: str = "#0F172A",
    width: int = REELS_WIDTH,
    height: int = REELS_HEIGHT,
) -> Image.Image:
    """Centraliza o PNG 4:5 no canvas 9:16 (barras na cor da marca)."""
    canvas = Image.new("RGB", (width, height), _hex_to_rgb(fundo_hex))
    slide = Image.open(png).convert("RGB")
    # cabe na largura; se ainda passar da altura, reduz
    scale = min(width / slide.width, height / slide.height)
    new_w = max(1, int(slide.width * scale))
    new_h = max(1, int(slide.height * scale))
    slide = slide.resize((new_w, new_h), Image.Resampling.LANCZOS)
    x = (width - new_w) // 2
    y = (height - new_h) // 2
    canvas.paste(slide, (x, y))
    return canvas


def montar_reels_mp4(
    pngs: list[Path],
    destino: Path,
    *,
    fundo_hex: str = "#0F172A",
    segundos_por_slide: float = VIDEO_SEGUNDOS_POR_SLIDE,
    fps: int = VIDEO_FPS,
) -> Path:
    """
    Slideshow vertical 1080×1920 para Instagram Reels e TikTok.
    Sem IA: só junta os slides já renderizados.
    """
    if not pngs:
        raise ValueError("Nenhum PNG para montar o vídeo")
    destino.parent.mkdir(parents=True, exist_ok=True)
    frames_por_slide = max(1, int(round(fps * segundos_por_slide)))

    writer = imageio.get_writer(
        str(destino),
        fps=fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    )
    try:
        for png in pngs:
            frame = slide_para_reels(png, fundo_hex=fundo_hex)
            arr = np.asarray(frame)
            for _ in range(frames_por_slide):
                writer.append_data(arr)
    finally:
        writer.close()
    return destino
