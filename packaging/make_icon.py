"""Draws Mise's icon: three tiles in Ocean colours (indigo, blue, cyan) with a knob in the fourth slot.

Large sizes sit on a rounded graphite tile; small sizes (taskbar, tray) drop it so the mark fills the space.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "studio_hub" / "assets"
BG = "#232326"
DARK = {"tiles": ("#5E5CE6", "#0A84FF", "#64D2FF"), "knob": "#F2F2F4", "pointer": "#232326"}
LIGHT = {"tiles": ("#4d4bbd", "#086cd1", "#52acd1"), "knob": "#1D1D1F", "pointer": "#F2F2F4"}  # for light taskbars
TILES = ((26, 26), (63, 26), (26, 63))  # top-left corners in 120-unit icon space; each tile is 31 x 31
SCALE = 8  # draw large, then downsample for smooth edges


def draw(size: int, tile: bool = True, palette: dict = DARK, pointer: bool = True) -> Image.Image:
    big = size * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tile:
        d.rounded_rectangle((0, 0, big - 1, big - 1), radius=27 * big / 120, fill=BG)
        origin, span = 0, 120
    else:
        origin, span = 24, 72  # crop to the mark itself
    s = big / span

    def xy(x, y):
        return (x - origin) * s, (y - origin) * s

    for (x, y), colour in zip(TILES, palette["tiles"]):
        d.rounded_rectangle((*xy(x, y), *xy(x + 31, y + 31)), radius=8 * s, fill=colour)
    cx, cy, r = 78.5, 78.5, 15.5
    d.ellipse((*xy(cx - r, cy - r), *xy(cx + r, cy + r)), fill=palette["knob"])
    if pointer:
        w = 4.5 * s
        d.line((*xy(cx, cy), *xy(83, 67)), fill=palette["pointer"], width=round(w))
        for px, py in ((cx, cy), (83, 67)):
            d.ellipse((*xy(px - 2.25, py - 2.25), *xy(px + 2.25, py + 2.25)), fill=palette["pointer"])
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(256).save(OUT / "icon.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw(n, tile=n >= 48, pointer=n >= 24) for n in sizes]
    frames[-1].save(OUT / "icon.ico", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
    draw(64, tile=False).save(OUT / "tray.png")
    draw(64, tile=False, palette=LIGHT).save(OUT / "tray-light.png")
    print("wrote", OUT)
