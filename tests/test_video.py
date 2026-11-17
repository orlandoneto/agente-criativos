"""Guarda: slideshow 9:16 a partir de PNG."""

from pathlib import Path

from PIL import Image

from app.video import montar_reels_mp4, slide_para_reels


def test_slide_para_reels_dimensoes(tmp_path: Path) -> None:
    src = tmp_path / "slide.png"
    Image.new("RGB", (1080, 1350), (20, 30, 40)).save(src)
    out = slide_para_reels(src, fundo_hex="#112233")
    assert out.size == (1080, 1920)


def test_montar_mp4(tmp_path: Path) -> None:
    pngs = []
    for i in range(2):
        p = tmp_path / f"slide_{i:02d}.png"
        Image.new("RGB", (1080, 1350), (i * 40, 80, 120)).save(p)
        pngs.append(p)
    dest = tmp_path / "reels_tiktok.mp4"
    montar_reels_mp4(pngs, dest, segundos_por_slide=0.5, fps=10)
    assert dest.exists()
    assert dest.stat().st_size > 1000
