"""
Génère icon.png (1024×1024) aux couleurs de l'application,
puis le convertit en icon.icns via les outils macOS.
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent

PRIMARY      = (0, 153, 144)   # #009990
PRIMARY_DARK = (0, 125, 120)   # #007D78
WHITE        = (255, 255, 255)
SIZE         = 1024


def _draw_icon() -> Image.Image:
    img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fond rond avec dégradé simulé (deux ellipses superposées)
    margin = 40
    draw.ellipse([margin, margin, SIZE - margin, SIZE - margin],
                 fill=PRIMARY_DARK)
    draw.ellipse([margin + 20, margin + 20,
                  SIZE - margin - 20, SIZE - margin - 20],
                 fill=PRIMARY)

    # Anneau décoratif (cercle creux)
    r = SIZE // 2 - margin - 10
    cx = cy = SIZE // 2
    ring_w = 18
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=(255, 255, 255, 80), width=ring_w)

    # Lettre "D" + "T" (Digital Twin) en blanc, grandes
    text = "DT"
    font_size = 420
    font = None
    for candidate in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Arial.ttf",
    ]:
        if Path(candidate).exists():
            try:
                from PIL import ImageFont as _IF
                font = _IF.truetype(candidate, font_size)
                break
            except Exception:
                pass

    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (SIZE - tw) // 2 - bbox[0]
    ty = (SIZE - th) // 2 - bbox[1]
    draw.text((tx, ty), text, font=font, fill=WHITE)

    # Petit trait décoratif sous "DT"
    bar_y = ty + th + 30
    bar_w = int(tw * 0.6)
    bar_h = 18
    bx = (SIZE - bar_w) // 2
    draw.rounded_rectangle([bx, bar_y, bx + bar_w, bar_y + bar_h],
                            radius=9, fill=(255, 255, 255, 160))

    return img


def make_icns(png_path: Path, icns_path: Path) -> None:
    iconset = png_path.parent / "icon.iconset"
    iconset.mkdir(exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    img = Image.open(png_path).convert("RGBA")
    for s in sizes:
        resized = img.resize((s, s), Image.LANCZOS)
        resized.save(iconset / f"icon_{s}x{s}.png")
        if s <= 512:
            resized2 = img.resize((s * 2, s * 2), Image.LANCZOS)
            resized2.save(iconset / f"icon_{s}x{s}@2x.png")

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
        check=True,
    )
    shutil.rmtree(iconset)
    print(f"  → {icns_path} créé")


if __name__ == "__main__":
    png_path  = HERE / "icon.png"
    icns_path = HERE / "icon.icns"

    print("Génération de l'icône...")
    icon = _draw_icon()
    icon.save(png_path)
    print(f"  → {png_path} créé")

    print("Conversion en .icns...")
    make_icns(png_path, icns_path)
    print("Icône prête.")
