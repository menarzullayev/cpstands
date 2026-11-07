"""Render assets/avatar.svg geometry to assets/avatar.jpg (640x640) with Pillow (4x supersampling).
Mirrors the SVG exactly: update both together. Requires Pillow (dev-only dependency)."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
S, OUT = 4, 640
K = OUT * S / 100
img = Image.new("RGB", (OUT * S, OUT * S), "#0f172a")
d = ImageDraw.Draw(img)
for x, y, w, h, color in [
    (18, 43, 20, 30, "#38bdf8"),
    (40, 27, 20, 46, "#fbbf24"),
    (62, 51, 20, 22, "#a78bfa"),
]:
    d.rounded_rectangle([x * K, y * K, (x + w) * K, (y + h) * K], radius=3 * K, fill=color)
img.resize((OUT, OUT), Image.LANCZOS).save(
    ROOT / "assets" / "avatar.jpg", "JPEG", quality=95, subsampling=0
)
print("avatar.jpg written")
