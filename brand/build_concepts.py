"""Builds the Ordel logo concepts as clean SVG paths (design-time only; needs shapely).

python brand/build_concepts.py
"""
from pathlib import Path

from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

OUT = Path(__file__).parent / "concepts"
RES = 64  # segments per quarter circle: smooth curves without bloated files


def circle(x, y, r):
    return Point(x, y).buffer(r, quad_segs=RES)


def ring(x, y, outer, inner):
    return circle(x, y, outer).difference(circle(x, y, inner))


def rounded(x0, y0, x1, y1, r):
    return box(x0 + r, y0 + r, x1 - r, y1 - r).buffer(r, quad_segs=RES // 2)


def to_path(geom) -> str:
    """Shapely geometry -> one SVG path (outer rings + holes; fill-rule evenodd)."""
    polys = getattr(geom, "geoms", [geom])
    parts = []
    for p in polys:
        for ring_ in [p.exterior, *p.interiors]:
            pts = list(ring_.coords)[:-1]
            parts.append("M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z")
    return " ".join(parts)


def save(name, geom, view=(0, 0, 256, 256)):
    OUT.mkdir(exist_ok=True)
    vb = " ".join(f"{v:g}" for v in view)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">'
           f'<path fill-rule="evenodd" d="{to_path(geom)}"/></svg>')
    (OUT / name).write_text(svg)


# A · Striped O: a heavy ring cut by two horizontal gaps.
o = None  # built below, once the stripe sizes are known
gap = 16
band = (208 - 2 * gap) / 3  # three equal stripes
top = 128 - 104
cuts = unary_union([box(0, top + band, 256, top + band + gap), box(0, top + 2 * band + gap, 256, top + 2 * band + 2 * gap)])
o = ring(128, 128, 104, band / 2 + gap)  # the hole fits exactly between the two gaps
save("a-striped-o-v5.svg", o.difference(cuts))

# B · O in its place: a 3x3 grid of tiles, the centre-right one replaced by a ring.
cell, g = 62, 18
start = 128 - (3 * cell + 2 * g) / 2
tiles = []
for row in range(3):
    for col in range(3):
        x0, y0 = start + col * (cell + g), start + row * (cell + g)
        if (row, col) == (1, 1):
            tiles.append(ring(x0 + cell / 2, y0 + cell / 2, cell / 2, cell / 2 - 17))
        else:
            tiles.append(rounded(x0, y0, x0 + cell, y0 + cell, 12))
save("b-o-in-its-place-v2.svg", unary_union(tiles))

# C · Custom wordmark "ordel": monoline geometric letters; the e's crossbar runs on into the l.
X, S = 100, 24          # x-height, stroke
ASC = 150               # ascender height for d and l
R_OUT, R_IN = X / 2, X / 2 - S
base = 0                # baseline at y=0; letters drawn upward (negative y), then flipped into view
def o_at(x):            # bowl of o, d, e; x = left edge
    return ring(x + R_OUT, -R_OUT, R_OUT, R_IN)

import math
x = 0
letters = []
letters.append(o_at(x)); x += X + 12                                   # o (round sides sit closer)
stem = box(x, -X, x + S, 0)                                            # r: stem + shoulder arc
shoulder = ring(x + R_OUT, -R_OUT, R_OUT, R_IN).intersection(box(x, -X, x + R_OUT + 10, -R_OUT))
letters.append(unary_union([stem, shoulder])); x += R_OUT + 10 + 14
letters.append(unary_union([o_at(x), box(x + X - S, -ASC, x + X, 0)])); x += X + 14   # d
cx, cy = x + R_OUT, -R_OUT
reach = R_OUT + 6
wedge = Polygon([(cx, cy), (cx + reach, cy), (cx + reach, cy + reach * math.tan(math.radians(38)))])
letters.append(o_at(x).difference(wedge))                               # e: ring with lower-right aperture
l_x = x + X + 14
letters.append(box(l_x, -ASC, l_x + S, 0))                              # l
letters.append(box(x + R_IN * 0.2, cy - S / 2, l_x + 1, cy + S / 2))    # crossbar runs on into the l
word = unary_union(letters)
minx, miny, maxx, maxy = word.bounds
word = affinity.translate(word, -minx + 20, -miny + 20)
w, h = maxx - minx + 40, maxy - miny + 40
save("c-wordmark-v3.svg", word, (0, 0, w, h))
save("c-wordmark-symbol-v3.svg", affinity.scale(affinity.translate(o_at(0), 78, 178), 2.08, 2.08, origin=(128, 128)))
print("built", sorted(p.name for p in OUT.glob("*-v[23].svg")) + ["b-o-in-its-place-v1.svg"])


# Lockups: symbol beside the wordmark, symbol height matched to the wordmark's ascender height.
def lockup(symbol, name):
    sx0, sy0, sx1, sy1 = symbol.bounds
    wx0, wy0, wx1, wy1 = word.bounds
    scale = (wy1 - wy0) / (sy1 - sy0) * 1.1
    sym = affinity.scale(symbol, scale, scale, origin=(sx0, sy0))
    sym = affinity.translate(sym, wx0 - sx0, wy0 - sy0 - (wy1 - wy0) * 0.05)
    shift = sym.bounds[2] - sym.bounds[0] + 48
    both = unary_union([sym, affinity.translate(word, shift, 0)])
    b = both.bounds
    both = affinity.translate(both, -b[0] + 20, -b[1] + 20)
    save(name, both, (0, 0, b[2] - b[0] + 40, b[3] - b[1] + 40))


lockup(o.difference(cuts), "a-lockup.svg")
lockup(unary_union(tiles), "b-lockup.svg")
save("c-lockup.svg", word, (0, 0, w, h))
