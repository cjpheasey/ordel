"""The user's own data: settings, favourites, category overrides, picture status."""
import copy
import json
import os
import re
import threading
import time
import uuid
from collections.abc import Iterable
from pathlib import Path

from .bridge import replace_file
from .categories import CATEGORIES, KEYS, resolve_category
from .reaper_db import Plugin, tidy_developer

DEFAULT_SETTINGS = {
    "theme": "ordel",
    "hotkey": "Ctrl+Shift+Space",
    "hide_after_add": False,
    "tile_size": 240,
    "last_view": "all",
    "window": None,
    "onboarded": False,
    "sidebar_mode": "categories",
    "toured": False,
    "accent": "theme",
    "picture_fit": "contain",
    "density": "comfortable",
    "corners": "rounded",
    "show_developer": True,
    "sort": "name",
    "projects_folder": "",  # where your REAPER projects live; counts how often each plugin is used
}
# Colours for categories you make yourself, in order; picked so they sit apart from the built-in ones.
CUSTOM_COLOURS = ["#F2A7C3", "#7FD1AE", "#F5B971", "#9DB4FF", "#C9A15A", "#E07A5F", "#81B29A", "#B8A1E3"]
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
CAPTURE_STATES = {"none", "ok", "failed", "custom", "crashed"}
CHOICES = {
    "theme": {"ordel", "graphite", "light", "glass"},
    "sidebar_mode": {"categories", "developers"},
    "accent": {"theme", "brass", "blue", "green", "orange", "pink", "purple"},
    "picture_fit": {"contain", "cover"},
    "density": {"comfortable", "compact"},
    "corners": {"rounded", "square"},
    "sort": {"name", "used"},
}


def _valid_setting(key: str, value) -> bool:
    """Settings arrive from the UI and from disk, so check each one's type before keeping it."""
    if key in CHOICES:
        return value in CHOICES[key]
    if key == "window":
        return value is None or (isinstance(value, dict) and all(
            isinstance(v, int) and not isinstance(v, bool) for v in value.values()))
    default = DEFAULT_SETTINGS[key]
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, type(default))


class Library:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self._plugins: dict[str, dict] = {}
        self._chains: dict[str, dict] = {}  # Ordel's extras per chain: order, return_track, hidden, ...
        self._categories: list[dict] = []  # categories the user made: key, label, color
        self._seen: list[str] | None = None  # plugin ids Ordel has already shown; None until first recorded
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            settings = data.get("settings", {})
            plugins = data.get("plugins", {})
            chains = data.get("chains", {})
            categories = data.get("categories")
            if isinstance(categories, list):
                self._categories = [c for c in categories if isinstance(c, dict) and {"key", "label", "color"} <= c.keys()]
            seen = data.get("seen")
            if isinstance(seen, list):
                self._seen = [s for s in seen if isinstance(s, str)]
            if isinstance(chains, dict):
                self._chains = {k: v for k, v in chains.items() if isinstance(v, dict)}
            if isinstance(settings, dict):
                self.settings.update({k: v for k, v in settings.items()
                                      if k in DEFAULT_SETTINGS and _valid_setting(k, v)})
            if isinstance(plugins, dict):
                self._plugins = {k: v for k, v in plugins.items() if isinstance(v, dict)}
        except (ValueError, AttributeError):
            # Keep the damaged file for recovery rather than silently overwriting it.
            os.replace(self.path, self.path.with_name(self.path.stem + ".corrupt.json"))

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "settings": self.settings, "plugins": self._plugins,
                                   "chains": self._chains, "seen": self._seen, "categories": self._categories},
                                  indent=1), encoding="utf-8")
        replace_file(tmp, self.path)

    def _set(self, plugin_id: str, **fields) -> None:
        with self._lock:
            self._plugins.setdefault(plugin_id, {}).update(fields)
            self._save()

    def update_settings(self, **kw) -> dict:
        with self._lock:
            self.settings.update({k: v for k, v in kw.items() if k in DEFAULT_SETTINGS and _valid_setting(k, v)})
            self._save()
            return dict(self.settings)

    def _clear(self, ids: Iterable[str], field: str) -> None:
        for other in ids:
            self._plugins.get(other, {}).pop(field, None)

    def set_favourite(self, plugin_id: str, on: bool, also: Iterable[str] = ()) -> None:
        """also: the plugin's other versions, cleared so the group shows what the user just chose."""
        with self._lock:
            self._clear(also, "favourite")
            self._set(plugin_id, favourite=bool(on))

    def set_category(self, plugin_id: str, key: str | None, also: Iterable[str] = ()) -> None:
        if key is not None and key not in KEYS and key not in {c["key"] for c in self._categories}:
            raise ValueError(f"unknown category {key!r}")
        with self._lock:
            self._clear(also, "category")
            self._set(plugin_id, category=key)

    # ---------- categories the user makes ----------

    def custom_categories(self) -> list[dict]:
        with self._lock:
            return [dict(c, custom=True) for c in self._categories]

    def _check_label(self, label: str, ignore_key: str | None = None) -> str:
        label = " ".join(str(label).split())
        if not 1 <= len(label) <= 40:
            raise ValueError("a category needs a name of up to 40 characters")
        taken = [c["label"] for c in CATEGORIES] + [c["label"] for c in self._categories if c["key"] != ignore_key]
        if label.lower() in (t.lower() for t in taken):
            raise ValueError(f"there's already a category called {label}")
        return label

    def add_category(self, label: str) -> dict:
        with self._lock:
            label = self._check_label(label)
            used = {c["color"] for c in self._categories}
            color = next((c for c in CUSTOM_COLOURS if c not in used), CUSTOM_COLOURS[len(self._categories) % len(CUSTOM_COLOURS)])
            category = {"key": "c-" + uuid.uuid4().hex[:8], "label": label, "color": color}
            self._categories.append(category)
            self._save()
            return dict(category, custom=True)

    def update_category(self, key: str, label: str | None = None, color: str | None = None) -> None:
        with self._lock:
            category = next((c for c in self._categories if c["key"] == key), None)
            if category is None:
                raise ValueError("only categories you made can be changed")
            if label is not None:
                category["label"] = self._check_label(label, ignore_key=key)
            if color is not None:
                if not _HEX.match(str(color)):
                    raise ValueError("not a colour")
                category["color"] = color
            self._save()

    def delete_category(self, key: str) -> None:
        """Its plugins go back to the category Ordel detected for them."""
        with self._lock:
            if not any(c["key"] == key for c in self._categories):
                raise ValueError("only categories you made can be deleted")
            self._categories = [c for c in self._categories if c["key"] != key]
            for record in self._plugins.values():
                if record.get("category") == key:
                    record.pop("category")
            self._save()

    def count_variant(self, group_id: str, variant_id: str) -> None:
        """Remember which version gets added, so double-click picks the usual one."""
        with self._lock:
            counts = self._plugins.setdefault(group_id, {}).setdefault("variants", {})
            counts[variant_id] = counts.get(variant_id, 0) + 1
            self._save()

    def mark_used(self, plugin_id: str) -> None:
        self._set(plugin_id, last_used=time.time())

    def set_capture(self, plugin_id: str, status: str) -> None:
        if status not in CAPTURE_STATES:
            raise ValueError(f"unknown capture status {status!r}")
        self._set(plugin_id, capture=status, shot=time.time())

    def seen(self) -> set[str] | None:
        with self._lock:
            return None if self._seen is None else set(self._seen)

    def mark_seen(self, ids: set[str]) -> None:
        with self._lock:
            known = set(self._seen or [])
            if self._seen is None or not ids <= known:
                self._seen = sorted(known | ids)
                self._save()

    def chain_meta(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._chains.items()}

    def set_chain_meta(self, chain_id: str, **fields) -> None:
        with self._lock:
            self._chains.setdefault(chain_id, {}).update(fields)
            self._save()

    def remove_chain_meta(self, chain_id: str) -> None:
        with self._lock:
            if self._chains.pop(chain_id, None) is not None:
                self._save()

    def prune_chain_meta(self, existing_ids: set[str]) -> None:
        """Forget extras of chain files that are gone; chains built in Ordel have no file to check."""
        with self._lock:
            gone = [k for k in self._chains if k.startswith("file:") and k not in existing_ids]
            for k in gone:
                del self._chains[k]
            if gone:
                self._save()

    def capture_status(self, plugin_id: str) -> str:
        return self._plugins.get(plugin_id, {}).get("capture", "none")

    def view(self, plugins: list[Plugin]) -> list[dict]:
        with self._lock:
            out = []
            for p in plugins:
                members = [p, *p.variants]
                states = [self._plugins.get(m.id, {}) for m in members]
                state = states[0]
                auto = resolve_category(p.reaper_tags, p.name, p.instrument)
                # The picture: the main version's, else the first version that has one.
                pictured = next((i for i, s in enumerate(states) if s.get("capture") in ("ok", "custom")), 0)
                counts = state.get("variants") or {}
                ids = {m.id for m in members}
                preferred = max((i for i in counts if i in ids), key=lambda i: counts[i], default=p.id)
                out.append({
                    "id": p.id, "name": p.name, "vendor": p.vendor, "developer": tidy_developer(p.vendor),
                    "format": p.format,
                    "instrument": p.instrument, "alternates": p.alternates,
                    "variants": [{"id": m.id, "label": m.variant,
                                  "shot": s.get("shot", 0) if s.get("capture") in ("ok", "custom") else 0}
                                 for m, s in zip(members, states)] if p.variants else [],
                    "preferred": preferred,
                    "category": next((s["category"] for s in states if s.get("category")), None) or auto,
                    "category_auto": auto,
                    "favourite": any(s.get("favourite", False) for s in states),
                    "last_used": max(s.get("last_used", 0) for s in states),
                    "capture": states[pictured].get("capture", "none"),
                    "shot": states[pictured].get("shot", 0),
                    "shot_id": members[pictured].id,
                })
            return out
