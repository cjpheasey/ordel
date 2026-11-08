"""Builds Ordel's master logo files in brand/final/ (design-time only; the wordmark needs shapely).

python brand/build_final.py

Symbol: a 3x3 grid of rounded tiles; the centre tile is a ring, "the one in its place".
Small-size cut (32 px and below): the ring becomes a solid brass tile, because its hole closes up when tiny.
"""
import runpy
from pathlib import Path

from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union

HERE = Path(__file__).parent
OUT = HERE / "final"

INK, IVORY, BRASS, PAPER = "#14171F", "#ECE6D8", "#C9A15A", "#F4F2EE"

# Symbol grid on a 256 canvas: 3 cells of 62 with gaps of 18, centred.
CELL, GAP, RADIUS = 62, 18, 12
START = 128 - (3 * CELL + 2 * GAP) / 2   # 17
RING_OUT, RING_IN = 32, 14.5            # ring overshoots the tile edge by 1 so it doesn't look smaller than a square


def symbol_body(tiles: str, centre: str | None, small: bool = False) -> str:
    """centre=None leaves the middle slot empty: the one-colour small cut."""
    out = []
    for row in range(3):
        for col in range(3):
            x, y = START + col * (CELL + GAP), START + row * (CELL + GAP)
            if (row, col) != (1, 1):
                out.append(f'<rect x="{x:g}" y="{y:g}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{tiles}"/>')
    if centre is None:
        pass
    elif small:
        x = START + CELL + GAP
        out.append(f'<rect x="{x:g}" y="{x:g}" width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{centre}"/>')
    else:
        c, o, i = 128, RING_OUT, RING_IN
        out.append(f'<path fill-rule="evenodd" fill="{centre}" d="M{c - o} {c}a{o} {o} 0 1 0 {2 * o} 0a{o} {o} 0 1 0 {-2 * o} 0Z'
                   f'M{c - i} {c}a{i} {i} 0 1 0 {2 * i} 0a{i} {i} 0 1 0 {-2 * i} 0Z"/>')
    return "".join(out)


def svg(body: str, view: str = "0 0 256 256", title: str = "Ordel") -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"><title>{title}</title>{body}</svg>'


def app_icon_body(small: bool = False) -> str:
    """Rounded ink tile with the symbol inset, for the Windows icon and README."""
    inset = 0.72
    shift = 128 * (1 - inset)
    return (f'<rect width="256" height="256" rx="58" fill="{INK}"/>'
            f'<g transform="translate({shift:g} {shift:g}) scale({inset})">{symbol_body(IVORY, BRASS, small)}</g>')


# Wordmark geometry comes from the concept builder (letters built from circles and strokes).
# Plain letters: the e keeps its crossbar inside its own bowl, and the o carries the brass.
g = runpy.run_path(str(HERE / "build_concepts.py"))
to_path = g["to_path"]
o_letter, r_letter, d_letter, e_ring, l_letter, _long_crossbar = g["letters"]
ex0, _, ex1, _ = e_ring.bounds
e_bowl = g["circle"](g["cx"], g["cy"], g["R_OUT"])
e_bar = box(ex0 + g["S"] / 2, g["cy"] - g["S"] / 2, ex1, g["cy"] + g["S"] / 2).intersection(e_bowl)
rest_geom = unary_union([r_letter, d_letter, unary_union([e_ring, e_bar]), l_letter])
x0, y0, x1, y1 = unary_union([o_letter, rest_geom]).bounds
WORD_VIEW = (x0, y0, x1 - x0, y1 - y0)


def word_body(main: str, accent: str, dx: float = 0, dy: float = 0, scale: float = 1) -> str:
    parts = []
    for geom, colour in ((rest_geom, main), (o_letter, accent)):
        geom = affinity.scale(affinity.translate(geom, -x0, -y0), scale, scale, origin=(0, 0))
        parts.append(f'<path fill-rule="evenodd" fill="{colour}" d="{to_path(affinity.translate(geom, dx, dy))}"/>')
    return "".join(parts)


def lockups(main: str, tiles: str, centre: str, suffix: str) -> None:
    wh = WORD_VIEW[3]
    # Horizontal: symbol as tall as the word's ascenders, a tile-width gap, then the word.
    sym_size = wh * 1.08
    k = sym_size / 256
    gap = (CELL + GAP) * k
    word_x = sym_size + gap
    body = (f'<g transform="translate(0 {(wh - sym_size) / 2:g}) scale({k:g})">{symbol_body(tiles, centre)}</g>'
            + word_body(main, centre, dx=word_x))
    write(f"ordel-lockup-horizontal{suffix}.svg", svg(body, f"0 0 {word_x + WORD_VIEW[2]:g} {wh:g}"))
    # Stacked: symbol above, centred, word below.
    sym_size = WORD_VIEW[2] * 0.42
    k = sym_size / 256
    total_w = WORD_VIEW[2]
    body = (f'<g transform="translate({(total_w - sym_size) / 2:g} 0) scale({k:g})">{symbol_body(tiles, centre)}</g>'
            + word_body(main, centre, dy=sym_size + wh * 0.35))
    write(f"ordel-lockup-stacked{suffix}.svg", svg(body, f"0 0 {total_w:g} {sym_size + wh * 1.35:g}"))


def write(name: str, text: str) -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    write("ordel-symbol.svg", svg(symbol_body(INK, BRASS)))                    # on light backgrounds
    write("ordel-symbol-reversed.svg", svg(symbol_body(IVORY, BRASS)))         # on dark backgrounds
    write("ordel-symbol-small.svg", svg(symbol_body(INK, BRASS, small=True)))
    write("ordel-symbol-small-reversed.svg", svg(symbol_body(IVORY, BRASS, small=True)))
    write("ordel-symbol-black.svg", svg(symbol_body("#000", "#000")))
    write("ordel-symbol-small-black.svg", svg(symbol_body("#000", None)))
    write("ordel-symbol-white.svg", svg(symbol_body("#fff", "#fff")))
    write("ordel-app-icon.svg", svg(app_icon_body()))
    write("ordel-app-icon-small.svg", svg(app_icon_body(small=True)))
    view = f"0 0 {WORD_VIEW[2]:g} {WORD_VIEW[3]:g}"
    write("ordel-wordmark.svg", svg(word_body(INK, BRASS), view))
    write("ordel-wordmark-reversed.svg", svg(word_body(IVORY, BRASS), view))
    write("ordel-wordmark-black.svg", svg(word_body("#000", "#000"), view))
    lockups(INK, INK, BRASS, "")
    lockups(IVORY, IVORY, BRASS, "-reversed")
    print("wrote", len(list(OUT.glob("*.svg"))), "files to", OUT)
