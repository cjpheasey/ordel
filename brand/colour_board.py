"""Colour study for the Ordel concepts: writes an HTML board (design-time only).

python brand/colour_board.py <output.html>
"""
import runpy
import sys
from pathlib import Path

from shapely.geometry import box
from shapely.ops import unary_union

g = runpy.run_path(str(Path(__file__).parent / "build_concepts.py"))
to_path = g["to_path"]

PALETTES = [
    ("Ink & Brass", "#14171F", "#ECE6D8", "#C9A15A", "Deep ink with warm ivory and one brass detail. Like engraved studio hardware."),
    ("Graphite & Coral", "#1C1C1E", "#F2F2F4", "#FF6A4D", "Neutral graphite, crisp white, a coral signal light. Modern and confident."),
    ("Midnight & Cyan", "#0E1A2B", "#E8EEF5", "#3FC1E0", "Midnight blue with a cool cyan accent. Calm, technical, trustworthy."),
    ("Forest & Cream", "#13261E", "#EFE8D8", "#E6B85C", "Racing green, cream and gold. Heritage British console warmth."),
    ("Paper & Cobalt", "#F4F2EE", "#1D1D1F", "#2F5BFF", "Light: warm paper, near-black and one cobalt accent. Editorial, clean."),
]

# A: the stripe pieces; the middle band (between the two gaps) is the accent.
a_all = g["o"].difference(g["cuts"])
band, gap, top = g["band"], g["gap"], g["top"]
mid = box(0, top + band + gap, 256, top + 2 * band + gap)
a_parts = (a_all.difference(mid), a_all.intersection(mid))
# B: eight tiles, the ring (index 4) is the accent.
b_parts = (unary_union([t for i, t in enumerate(g["tiles"]) if i != 4]), g["tiles"][4])
# C: the word, with the e-to-l crossbar as the accent.
letters = g["letters"]
c_parts = (unary_union(letters[:-1]).difference(letters[-1]), letters[-1])


def svg(parts, colours, view="0 0 256 256", size=None):
    attrs = f' width="{size}" height="{size}"' if size else ""
    paths = "".join(f'<path fill-rule="evenodd" fill="{c}" d="{to_path(p)}"/>' for p, c in zip(parts, colours))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"{attrs}>{paths}</svg>'


def icon(parts, bg, main, accent, size, pad=0.16):
    inner = svg(parts, (main, accent), size=None)
    return (f'<div style="width:{size}px;height:{size}px;border-radius:{size * 0.225:.0f}px;background:{bg};'
            f'padding:{size * pad:.0f}px;box-sizing:border-box;flex:none">{inner.replace("<svg ", "<svg width=\'100%\' height=\'100%\' ")}</div>')


def word_svg(main, accent, height):
    w = g["word"]
    from shapely import affinity
    x0, y0, x1, y1 = c_parts[0].union(c_parts[1]).bounds
    view = f"{x0 - 4:.1f} {y0 - 4:.1f} {x1 - x0 + 8:.1f} {y1 - y0 + 8:.1f}"
    return svg(c_parts, (main, accent), view).replace("<svg ", f"<svg height='{height}' ")


def wordmark_parts():
    # c_parts are in the build script's raw letter coordinates (before translation), so use them directly
    return c_parts


def cell(parts, name, bg, main, accent, is_word=False):
    big = (f'<div style="height:96px;display:flex;align-items:center;justify-content:center;background:{bg};'
           f'border-radius:16px;padding:0 18px">{word_svg(main, accent, 44)}</div>') if is_word else icon(parts, bg, main, accent, 96)
    small_parts = parts if not is_word else (g["ring"](0, 0, 50, 26), None)
    tray = "" if is_word else (
        f'<div style="display:flex;gap:10px;align-items:center;margin-top:10px">'
        f'<span style="background:#101012;padding:6px;border-radius:6px;display:flex;gap:8px">'
        f'{svg(parts, (main if bg != "#F4F2EE" else "#E8E8EC", accent), size=16)}{svg(parts, (main if bg != "#F4F2EE" else "#E8E8EC", accent), size=24)}</span>'
        f'<span style="background:#e8e8ec;padding:6px;border-radius:6px;display:flex;gap:8px">'
        f'{svg(parts, (bg if bg != "#F4F2EE" else "#1D1D1F", accent), size=16)}{svg(parts, (bg if bg != "#F4F2EE" else "#1D1D1F", accent), size=24)}</span></div>')
    return f'<div style="display:flex;flex-direction:column;align-items:flex-start">{big}{tray}<div style="font-size:12px;color:#9a9aa0;margin-top:6px">{name}</div></div>'


rows = []
for i, (pname, bg, main, accent, note) in enumerate(PALETTES):
    swatches = "".join(f'<b style="display:inline-block;width:16px;height:16px;border-radius:4px;background:{c};margin-right:4px;border:1px solid rgba(255,255,255,.15)"></b>' for c in (bg, main, accent))
    rows.append(f'''
<div class="option" data-choice="palette-{i + 1}" onclick="toggleSelect(this)" style="align-items:flex-start">
  <div class="letter">{i + 1}</div>
  <div class="content">
    <h3>{pname} <span style="margin-left:8px">{swatches}</span></h3>
    <p>{note}</p>
    <div style="display:flex;gap:28px;flex-wrap:wrap;margin-top:12px">
      {cell(a_parts, "A · Striped O", bg, main, accent)}
      {cell(b_parts, "B · O in its place", bg, main, accent)}
      {cell(None, "C · Wordmark", bg, main, accent, is_word=True)}
    </div>
  </div>
</div>''')

html = f'''<h2>Ordel concepts, in colour</h2>
<p class="subtitle">Minimal palettes: one base, one light, one accent on the detail that carries the idea. Each concept shown as an app icon, at tray size (16 and 24 px) on dark and light taskbars, and the wordmark on its own.</p>
<div class="options" data-multiselect>{"".join(rows)}
</div>
<p class="subtitle" style="margin-top:16px">Click any palettes you like (several is fine), and tell me which concept, or which mix of palette and concept, feels like Ordel.</p>'''
Path(sys.argv[1]).write_text(html, encoding="utf-8")
print("wrote", sys.argv[1])
