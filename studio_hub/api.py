"""Everything the UI can ask Ordel to do."""
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable

from PIL import Image

from . import chains as chainlib
from .categories import CATEGORIES
from .library import Library
from .reaper_db import Plugin, load_plugins

_UNSET = object()
_PLUGIN_NAME = re.compile(r"^(?:VST3?i?|CLAPi?|DXi?|AUi?): (.*?)(?: \([^()]*\))?$")


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
            "chains": self.chains(),
            "new_plugins": self.new_plugins(),
        }

    def new_plugins(self) -> list[str]:
        """Plugins REAPER has found since Ordel last looked. The first look (also right after updating Ordel)
        counts everything as already seen, so the notice never lists a whole library."""
        ids = [p.id for p in self.plugins]
        seen = self.library.seen()
        if seen is None:
            if ids:  # with nothing scanned yet, wait for the real first look
                self.library.mark_seen(set(ids))
            return []
        return [i for i in ids if i not in seen]

    def refresh(self) -> dict:
        self.plugins = load_plugins(self.reaper_dir)
        return self.state()

    def send(self, id: str, variant: str | None = None) -> dict:
        plugin = self._plugin(id)
        if plugin is None:
            return {"ok": False, "detail": "unknown"}
        version = next((m for m in [plugin, *plugin.variants] if m.id == (variant or id)), None)
        if version is None:
            raise ValueError("unknown version")
        ok, detail = self.bridge.send("ADD", version.add_name)
        if ok:
            self.library.mark_used(id)
            self.library.count_variant(id, version.id)
            if self.library.settings["hide_after_add"]:
                self.hooks["hide"]()
        return {"ok": ok, "detail": detail}

    def update_plugin(self, id: str, favourite=None, category=_UNSET) -> dict:
        if self._plugin(id) is None:
            raise ValueError("unknown plugin")
        others = [v.id for v in self._plugin(id).variants]
        if favourite is not None:
            self.library.set_favourite(id, favourite, also=others)
        if category is not _UNSET:
            self.library.set_category(id, category, also=others)
        return {"ok": True}

    # ---------- chains ----------

    def _versions(self) -> dict[str, tuple[Plugin, Plugin]]:
        """Every name REAPER may use for a plugin version -> (its group, the version)."""
        out = {}
        for group in self.plugins:
            for version in [group, *group.variants]:
                for name in [version.add_name, *version.alternates]:
                    out.setdefault(name, (group, version))
        return out

    def chains(self) -> list[dict]:
        files = chainlib.chain_files(self.reaper_dir)
        if chainlib.chains_dir(self.reaper_dir).is_dir():  # a briefly missing folder must not wipe the extras
            self.library.prune_chain_meta(set(files))
        meta = self.library.chain_meta()
        versions = self._versions()

        def entry(chain_id: str, name: str, names: list[str], ordel: bool) -> dict:
            m = meta.get(chain_id, {})
            plugins = []
            for n in names:
                group, version = versions.get(n, (None, None))
                shown = group.name if group else (_PLUGIN_NAME.match(n) or [n, n])[1]
                plugins.append({"name": shown, "id": group and group.id, "variant": version and version.id})
            return {"id": chain_id, "name": name, "kind": chain_id.split(":", 1)[0], "ordel": ordel,
                    "return_track": bool(m.get("return_track", False)), "hidden": bool(m.get("hidden", False)),
                    "order": m.get("order", 10**6), "plugins": plugins, "_names": names}

        out = [entry(cid, path.stem, chainlib.parse_chain(path), cid.startswith(f"file:{chainlib.ORDEL_FOLDER}/"))
               for cid, path in files.items()]
        out += [entry(cid, m.get("name", "Chain"), list(m.get("plugins", [])), True)
                for cid, m in meta.items() if cid.startswith("built:")]
        out.sort(key=lambda c: (c["order"], c["name"].lower()))
        # Chains seen for the first time take the next places, so a newly saved chain lands at the end.
        last = max((c["order"] for c in out if c["order"] < 10**6), default=-1)
        for c in out:
            if c.pop("order") >= 10**6:
                last += 1
                self.library.set_chain_meta(c["id"], order=last)
        return [{k: v for k, v in c.items() if k != "_names"} for c in out]

    def _chain(self, chain_id: str) -> dict:
        files = chainlib.chain_files(self.reaper_dir)
        meta = self.library.chain_meta()
        if chain_id in files:
            return {"id": chain_id, "path": files[chain_id], "meta": meta.get(chain_id, {}),
                    "ordel": chain_id.startswith(f"file:{chainlib.ORDEL_FOLDER}/")}
        if chain_id.startswith("built:") and chain_id in meta:
            return {"id": chain_id, "path": None, "meta": meta[chain_id], "ordel": True}
        raise ValueError("unknown chain")

    def _file_id(self, path: Path) -> str:
        return "file:" + path.relative_to(chainlib.chains_dir(self.reaper_dir)).as_posix()

    def _next_order(self) -> int:
        self.chains()  # gives chains not yet seen their places first
        return max((m.get("order", 0) for m in self.library.chain_meta().values()), default=0) + 1

    def _version_names(self, ids: list[str]) -> list[str]:
        by_id = {v.id: v for g in self.plugins for v in [g, *g.variants]}
        if not isinstance(ids, list) or any(i not in by_id for i in ids):
            raise ValueError("unknown plugin")
        return [by_id[i].add_name for i in ids]

    def chain_action(self, action: str, id: str | None = None, **body) -> dict:
        if action == "save":
            return self._save_chain(str(body.get("name") or ""), body.get("replace"))
        if action == "build":
            name = chainlib.safe_name(str(body.get("name") or ""))
            chain_id = f"built:{uuid.uuid4().hex}"
            self.library.set_chain_meta(chain_id, name=name, plugins=self._version_names(body.get("plugins", [])),
                                        order=self._next_order())
            return {"ok": True, "id": chain_id}
        c = self._chain(str(id))
        if action == "apply":
            return self._apply_chain(c)
        if action == "update":
            return self._update_chain(c, **body)
        if action == "hide":
            self.library.set_chain_meta(c["id"], hidden=bool(body.get("hidden", True)))
            return {"ok": True}
        if action == "move":
            ids = [x["id"] for x in self.chains()]
            i = ids.index(c["id"])
            j = max(0, min(len(ids) - 1, i + (1 if body.get("delta", 1) > 0 else -1)))
            ids[i], ids[j] = ids[j], ids[i]
            for n, chain_id in enumerate(ids):
                self.library.set_chain_meta(chain_id, order=n)
            return {"ok": True}
        if action == "delete":
            if not c["ordel"]:
                raise ValueError("this chain was made in REAPER; hide it instead")
            if c["path"]:
                chainlib.send_to_recycle_bin(c["path"])
            self.library.remove_chain_meta(c["id"])
            return {"ok": True}
        raise ValueError(f"unknown chain action {action!r}")

    def _apply_chain(self, c: dict) -> dict:
        names = chainlib.parse_chain(c["path"]) if c["path"] else list(c["meta"].get("plugins", []))
        versions = self._versions()
        missing = [(_PLUGIN_NAME.match(n) or [n, n])[1] for n in names if _PLUGIN_NAME.match(n) and n not in versions]
        name = c["meta"].get("name") or (c["path"].stem if c["path"] else "Chain")
        mode = "return" if c["meta"].get("return_track") else "track"
        if c["path"]:
            ok, detail = self.bridge.send("CHAIN_APPLY", f"{mode}	{name}	{c['path']}")
        else:
            ok, detail = self.bridge.send("CHAIN_ADD", "	".join([mode, name, *names]))
        tracks = int(detail) if ok and detail.isdigit() else (1 if ok else 0)
        return {"ok": ok, "detail": detail, "missing": missing, "exists": ok and detail == "EXISTS", "tracks": tracks}

    def _save_chain(self, name: str, replace: str | None) -> dict:
        if not name.strip():
            raise ValueError("a chain needs a name")
        old = self._chain(replace) if replace else None
        if old and old["path"] and old["ordel"]:
            path = old["path"]  # overwrite in place, keeping the old version in the Recycle Bin
            backup = path.with_name(f"{path.stem} (before replace){path.suffix}")
            shutil.copy2(path, backup)
            chainlib.send_to_recycle_bin(backup)
        elif old and old["path"]:
            raise ValueError("this chain was made in REAPER; save it under a new name")
        else:
            path = chainlib.new_chain_path(self.reaper_dir, name)
        ok, detail = self.bridge.send("CHAIN_SAVE", str(path))
        if not ok:
            return {"ok": False, "detail": detail}
        new_id = self._file_id(path)
        if old and old["id"] != new_id:  # a chain built in Ordel becomes a real REAPER chain
            extras = {k: v for k, v in old["meta"].items() if k not in ("name", "plugins")}
            self.library.remove_chain_meta(old["id"])
            self.library.set_chain_meta(new_id, **extras)
        elif not old:
            self.library.set_chain_meta(new_id, order=self._next_order())
        return {"ok": True, "detail": detail, "id": new_id}

    def _update_chain(self, c: dict, name=None, return_track=None, plugins=None) -> dict:
        if return_track is not None:
            self.library.set_chain_meta(c["id"], return_track=bool(return_track))
        if plugins is not None:
            if c["path"]:
                raise ValueError("save this chain from REAPER to change its plugins")
            self.library.set_chain_meta(c["id"], plugins=self._version_names(plugins))
        if name is not None:
            if not c["ordel"]:
                raise ValueError("this chain was made in REAPER; rename it there")
            if c["path"]:
                target = chainlib.new_chain_path(self.reaper_dir, name)
                c["path"].rename(target)
                new_id = self._file_id(target)
                extras = self.library.chain_meta().get(c["id"], {})
                self.library.remove_chain_meta(c["id"])
                self.library.set_chain_meta(new_id, **extras)
                return {"ok": True, "id": new_id}
            self.library.set_chain_meta(c["id"], name=chainlib.safe_name(name))
        return {"ok": True, "id": c["id"]}

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
        elif action == "capture_new":
            new = self.new_plugins()
            if new:
                self.capture.start(new)
            self.library.mark_seen(set(new))
        elif action == "dismiss_new":
            self.library.mark_seen(set(self.new_plugins()))
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
        # Start it inside the running REAPER straight away, so no restart is needed; a closed REAPER loads it
        # when it next starts. A busy REAPER can't take the hand-off, and -nonewinst then starts a second one.
        from . import capture
        exe = capture.running_reaper_exe()
        if exe and not _reaper_busy():
            try:
                subprocess.Popen([str(exe), "-nonewinst", str(script)],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError:
                pass
        return {"ok": True, "installed": True}

    def refresh_bridge(self) -> None:
        """After an update, swap in the new REAPER script; a running REAPER switches to it straight away."""
        if not (self.bridge.installed(self.reaper_dir) and self.bridge.outdated(self.reaper_dir)):
            return
        if self.bridge.connected():
            self.install_bridge()
        else:
            self.bridge.install(self.reaper_dir)  # REAPER loads it next time it starts; don't launch REAPER

    def window(self, action: str) -> dict:
        edge = action.removeprefix("resize-")
        if action.startswith("resize-") and edge in ("n", "s", "e", "w", "ne", "nw", "se", "sw"):
            self.hooks["resize"](edge)
            return {"ok": True}
        if action not in ("show", "hide", "minimize", "quit"):
            raise ValueError(f"unknown window action {action!r}")
        self.hooks[action]()
        return {"ok": True}
