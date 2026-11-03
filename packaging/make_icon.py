"""Draws Mise's icon: three plugin cards fanned in category colours, the front one a knob with its value ring lit."""
import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "studio_hub" / "assets"
BG, CYAN, ORANGE, GREEN, KNOB, LIGHT = "#232326", "#64D2FF", "#FF9F0A", "#30D158", "#1c3d26", "#f2f2f4"
SCALE = 8  # draw large, then downsample for smooth edges


def _card(size: int, box, radius, fill, angle, centre, detail=None) -> Image.Image:
    """One rounded card on its own layer, rotated about `centre` (all in 120-unit icon space)."""
    s = size * SCALE / 120
    layer = Image.new("RGBA", (size * SCALE,) * 2, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s), radius=radius * s, fill=fill)
    if detail:
        detail(d, s)
    return layer.rotate(-angle, center=(centre[0] * s, centre[1] * s), resample=Image.BICUBIC)


def _knob(full: bool):
    def draw(d: ImageDraw.ImageDraw, s: float) -> None:
        cx, cy = 62, 66
        if full:
            r, w = 13, 3.2
            ring = (cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s
            d.arc(ring, 138, 402, fill=KNOB, width=round(w * s))   # track, open at the bottom
            d.arc(ring, 138, 280, fill=LIGHT, width=round(w * s))  # value, about two thirds up
            k, pw = 7.5, 2.6
        else:
            k, pw = 12, 4.4
        d.ellipse(((cx - k) * s, (cy - k) * s, (cx + k) * s, (cy + k) * s), fill=KNOB)
        a = math.radians(285)
        tip = cx + math.cos(a) * (k - 0.6), cy + math.sin(a) * (k - 0.6)
        d.line((cx * s, cy * s, tip[0] * s, tip[1] * s), fill=LIGHT, width=round(pw * s))
        for x, y in ((cx, cy), tip):
            d.ellipse(((x - pw / 2) * s, (y - pw / 2) * s, (x + pw / 2) * s, (y + pw / 2) * s), fill=LIGHT)
    return draw


def draw(size: int, full: bool = True) -> Image.Image:
    big = size * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, big - 1, big - 1), radius=27 * big / 120, fill=BG)
    if full:
        img.alpha_composite(_card(size, (29, 31, 87, 75), 8, CYAN, -12, (58, 53)))
    img.alpha_composite(_card(size, (31, 37, 89, 81), 8, ORANGE, -2 if full else -8, (60, 59)))
    img.alpha_composite(_card(size, (33, 44, 91, 88), 8, GREEN, 8, (62, 66), _knob(full)))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw(256).save(OUT / "icon.png")
    # Small sizes drop the back card and the value ring so the mark stays clean.
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw(n, full=n >= 48) for n in sizes]
    frames[-1].save(OUT / "icon.ico", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
    print("wrote", OUT)
