"""Draws the app icon: four category-coloured tiles on a graphite rounded square."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "studio_hub" / "assets"
COLORS = ["#30D158", "#FF9F0A", "#64D2FF", "#BF5AF2"]


def draw(size: int) -> Image.Image:
    s = size * 4  # draw large, then downsample for smooth edges
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.225), fill="#232326")
    pad, gap = int(s * 0.22), int(s * 0.06)
    tile = (s - 2 * pad - gap) // 2
    for i, color in enumerate(COLORS):
        x = pad + (i % 2) * (tile + gap)
        y = pad + (i // 2) * (tile + gap)
        d.rounded_rectangle((x, y, x + tile, y + tile), radius=int(tile * 0.24), fill=color)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(256).save(OUT / "icon.png")
    draw(256).save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", OUT)
