"""The user's own data: settings, favourites, category overrides, picture status."""
import copy
import json
import os
import threading
import time
from pathlib import Path

from .categories import KEYS, resolve_category
from .reaper_db import Plugin

DEFAULT_SETTINGS = {
    "theme": "graphite",
    "hotkey": "Ctrl+Shift+Space",
    "hide_after_add": True,
    "tile_size": 200,
    "last_view": "all",
    "window": None,
    "onboarded": False,
}
CAPTURE_STATES = {"none", "ok", "failed", "custom", "crashed"}
THEMES = {"graphite", "light", "glass"}


def _valid_setting(key: str, value) -> bool:
    """Settings arrive from the UI and from disk, so check each one's type before keeping it."""
    if key == "theme":
        return value in THEMES
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
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            settings = data.get("settings", {})
            plugins = data.get("plugins", {})
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
        tmp.write_text(json.dumps({"version": 1, "settings": self.settings, "plugins": self._plugins},
                                  indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def _set(self, plugin_id: str, **fields) -> None:
        with self._lock:
            self._plugins.setdefault(plugin_id, {}).update(fields)
            self._save()

    def update_settings(self, **kw) -> dict:
        with self._lock:
            self.settings.update({k: v for k, v in kw.items() if k in DEFAULT_SETTINGS and _valid_setting(k, v)})
            self._save()
            return dict(self.settings)

    def set_favourite(self, plugin_id: str, on: bool) -> None:
        self._set(plugin_id, favourite=bool(on))

    def set_category(self, plugin_id: str, key: str | None) -> None:
        if key is not None and key not in KEYS:
            raise ValueError(f"unknown category {key!r}")
        self._set(plugin_id, category=key)

    def mark_used(self, plugin_id: str) -> None:
        self._set(plugin_id, last_used=time.time())

    def set_capture(self, plugin_id: str, status: str) -> None:
        if status not in CAPTURE_STATES:
            raise ValueError(f"unknown capture status {status!r}")
        self._set(plugin_id, capture=status, shot=time.time())

    def capture_status(self, plugin_id: str) -> str:
        return self._plugins.get(plugin_id, {}).get("capture", "none")

    def view(self, plugins: list[Plugin]) -> list[dict]:
        with self._lock:
            out = []
            for p in plugins:
                state = self._plugins.get(p.id, {})
                auto = resolve_category(p.reaper_tags, p.name, p.instrument)
                out.append({
                    "id": p.id, "name": p.name, "vendor": p.vendor, "format": p.format,
                    "instrument": p.instrument, "alternates": p.alternates,
                    "category": state.get("category") or auto, "category_auto": auto,
                    "favourite": state.get("favourite", False),
                    "last_used": state.get("last_used", 0),
                    "capture": state.get("capture", "none"),
                    "shot": state.get("shot", 0),
                })
            return out
