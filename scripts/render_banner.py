"""Render assets/description_banner.svg geometry to assets/description_banner.jpg (640x360) with Pillow.
Mirrors the SVG; update both together. Needs Segoe UI (Windows) or pass FONT_REGULAR/FONT_BOLD env paths."""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H, S = 640, 360, 4
BOLD = os.environ.get("FONT_BOLD", r"C:\Windows\Fonts\segoeuib.ttf")
REG = os.environ.get("FONT_REGULAR", r"C:\Windows\Fonts\segoeui.ttf")

img = Image.new("RGB", (W * S, H * S), "#0f172a")
d = ImageDraw.Draw(img)


def rect(x, y, w, h, r, fill):
    d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], radius=r * S, fill=fill)


def text(x, baseline, s, size, font, fill, anchor="ls"):
    d.text(
        (x * S, baseline * S), s, font=ImageFont.truetype(font, size * S), fill=fill, anchor=anchor
    )


rect(60, 170, 56, 110, 8, "#38bdf8")
rect(132, 110, 56, 170, 8, "#fbbf24")
rect(204, 200, 56, 80, 8, "#a78bfa")
text(300, 168, "cpstands", 58, BOLD, "#f8fafc")
text(302, 208, "Live contest standings", 22, REG, "#94a3b8")
rect(302, 232, 118, 34, 17, "#1e293b")
text(361, 255, "Codeforces", 16, REG, "#38bdf8", "ms")
rect(430, 232, 84, 34, 17, "#1e293b")
text(472, 255, "kep.uz", 16, REG, "#fbbf24", "ms")
img.resize((W, H), Image.LANCZOS).save(
    ROOT / "assets" / "description_banner.jpg", "JPEG", quality=95, subsampling=0
)
print("description_banner.jpg written")
