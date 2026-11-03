"""Everything the UI can ask Mise to do."""
import subprocess
import time
from pathlib import Path
from typing import Callable

from PIL import Image

from .categories import CATEGORIES
from .library import Library
from .reaper_db import Plugin, load_plugins

REAPER_EXE = Path(r"C:\Program Files\REAPER (x64)\reaper.exe")
_UNSET = object()


def _reaper_busy() -> bool:
    """True when REAPER's main window has stopped responding (e.g. a plugin is still loading)."""
    import ctypes

    import win32gui

    hwnd = win32gui.FindWindow("REAPERwnd", None)
    return bool(hwnd) and bool(ctypes.windll.user32.IsHungAppWindow(hwnd))


class Api:
    def __init__(self, reaper_dir: Path, library: Library, bridge, capture, hooks: dict[str, Callable]):
        self.reaper_dir = Path(reaper_dir)
        self.library = library
        self.bridge = bridge
        self.capture = capture
        self.hooks = hooks
        self.plugins: list[Plugin] = load_plugins(self.reaper_dir)
        self.snapshots_dir: Path | None = None
        self.hotkey_ok = True  # set by the app after registering the saved shortcut

    def _plugin(self, plugin_id: str) -> Plugin | None:
        return next((p for p in self.plugins if p.id == plugin_id), None)

    def state(self) -> dict:
        return {
            "plugins": self.library.view(self.plugins),
            "categories": CATEGORIES,
            "settings": dict(self.library.settings),
            "reaper": {"connected": self.bridge.connected(), "installed": self.bridge.installed(self.reaper_dir),
                       "library_found": bool(self.plugins)},
            "capture": self.capture.status(),
            "hotkey_ok": self.hotkey_ok,
        }

    def refresh(self) -> dict:
        self.plugins = load_plugins(self.reaper_dir)
        return self.state()

    def send(self, id: str) -> dict:
        plugin = self._plugin(id)
        if plugin is None:
            return {"ok": False, "detail": "unknown"}
        ok, detail = self.bridge.send("ADD", plugin.add_name)
        if ok:
            self.library.mark_used(id)
            if self.library.settings["hide_after_add"]:
                self.hooks["hide"]()
        return {"ok": ok, "detail": detail}

    def update_plugin(self, id: str, favourite=None, category=_UNSET) -> dict:
        if self._plugin(id) is None:
            raise ValueError("unknown plugin")
        if favourite is not None:
            self.library.set_favourite(id, favourite)
        if category is not _UNSET:
            self.library.set_category(id, category)
        return {"ok": True}

    def update_settings(self, **kw) -> dict:
        hotkey_ok = True
        if "hotkey" in kw:
            # Always re-register, so the same combo works again once another app releases it.
            hotkey_ok = bool(self.hooks["set_hotkey"](kw["hotkey"]))
            if hotkey_ok:
                self.hotkey_ok = True
            else:
                kw.pop("hotkey")
        return {"settings": self.library.update_settings(**kw), "hotkey_ok": hotkey_ok}

    def capture_action(self, action: str, id: str | None = None) -> dict:
        if action == "start":
            self.capture.start(None)
        elif action == "retake":
            if not id:
                raise ValueError("retake needs an id")
            self.capture.start([id])
        elif action == "recapture_all":
            self.capture.start([p.id for p in self.plugins])
        elif action in ("pause", "resume", "cancel"):
            getattr(self.capture, action)()
        else:
            raise ValueError(f"unknown capture action {action!r}")
        return self.capture.status()

    def custom_image(self, id: str) -> dict:
        if self._plugin(id) is None:
            raise ValueError("unknown plugin")
        path = self.hooks["pick_image"]()
        if not path:
            return {"ok": False}
        with Image.open(path) as img:
            img.convert("RGB").save(self.snapshots_dir / f"{id}.png")
        self.library.set_capture(id, "custom")
        return {"ok": True}

    def install_bridge(self) -> dict:
        script = self.bridge.install(self.reaper_dir)
        if self.bridge.connected():
            self.bridge.send("QUIT", timeout=2.0)  # stop the old copy so the new one can start
            time.sleep(0.3)
        # Start it inside the running REAPER straight away, so no restart is needed.
        # A busy REAPER can't take the hand-off, and -nonewinst then starts a second REAPER instead.
        if REAPER_EXE.exists() and not _reaper_busy():
            try:
                subprocess.Popen([str(REAPER_EXE), "-nonewinst", str(script)],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError:
                pass
        return {"ok": True, "installed": True}

    def window(self, action: str) -> dict:
        if action not in ("show", "hide", "minimize", "quit"):
            raise ValueError(f"unknown window action {action!r}")
        self.hooks[action]()
        return {"ok": True}
