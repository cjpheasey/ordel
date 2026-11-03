"""Draws Ordel's app icons: a 3x3 grid of tiles with a brass ring as "the one in its place".

Same geometry as brand/build_final.py (the SVG masters). Sizes of 24 px and below use the small cut,
where the ring becomes a solid brass tile because its hole closes up when tiny.
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "studio_hub" / "assets"
INK, IVORY, BRASS = "#14171F", "#ECE6D8", "#C9A15A"
CELL, GAP, RADIUS, START = 62, 18, 12, 17       # on a 256 canvas
RING_OUT, RING_IN = 32, 14.5
SCALE = 8  # draw large, then downsample for smooth edges


def draw(size: int, tile: bool = True, tiles: str = IVORY, small: bool = False) -> Image.Image:
    big = size * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tile:  # rounded ink background, symbol inset to 72 %
        d.rounded_rectangle((0, 0, big - 1, big - 1), radius=58 * big / 256, fill=INK)
        k, offset = big / 256 * 0.72, big * 0.14
    else:
        k, offset = big / 256 * 256 / 222, -START * big / 256 * 256 / 222  # crop to the grid itself

    def px(v):
        return offset + v * k

    for row in range(3):
        for col in range(3):
            x, y = START + col * (CELL + GAP), START + row * (CELL + GAP)
            centre = (row, col) == (1, 1)
            if centre and not small:
                continue
            d.rounded_rectangle((px(x), px(y), px(x + CELL), px(y + CELL)), radius=RADIUS * k,
                                fill=BRASS if centre else tiles)
    if not small:
        c = px(128)
        d.ellipse((c - RING_OUT * k, c - RING_OUT * k, c + RING_OUT * k, c + RING_OUT * k), fill=BRASS)
        d.ellipse((c - RING_IN * k, c - RING_IN * k, c + RING_IN * k, c + RING_IN * k), fill=INK if tile else (0, 0, 0, 0))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(256).save(OUT / "icon.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw(n, small=n <= 24) for n in sizes]
    frames[-1].save(OUT / "icon.ico", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
    draw(64, tile=False, tiles=IVORY, small=True).save(OUT / "tray.png")        # dark taskbar
    draw(64, tile=False, tiles=INK, small=True).save(OUT / "tray-light.png")    # light taskbar
    print("wrote", OUT)
