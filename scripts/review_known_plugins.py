"""Writes a review page for the built-in plugin list: python scripts/review_known_plugins.py OUT.html

Rows matching a plugin in this PC's REAPER are marked. The page copies a plain list of changes to paste back.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio_hub.categories import CATEGORIES  # noqa: E402
from studio_hub.reaper_db import load_plugins  # noqa: E402
from studio_hub.subgroups import SUBGROUPS, _known, known_plugins  # noqa: E402

rows = known_plugins()
try:
    mine = load_plugins(Path(os.environ["APPDATA"]) / "REAPER")
except OSError:
    mine = []
for i, e in enumerate(rows):
    e["id"] = i
    e["yours"] = []
for p in mine:
    if hit := _known(p.name, p.vendor, rows):
        hit["yours"].append(p.name)

data = {"rows": rows, "groups": [{"key": c["key"], "label": c["label"]} for c in CATEGORIES], "subgroups": SUBGROUPS}
page = (Path(__file__).with_name("review_known_plugins.html").read_text(encoding="utf-8")
        .replace("/*DATA*/null", json.dumps(data)))
Path(sys.argv[1]).write_text(page, encoding="utf-8")
print(f"{len(rows)} entries, {sum(bool(r['yours']) for r in rows)} match your plugins -> {sys.argv[1]}")
