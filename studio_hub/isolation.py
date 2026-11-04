"""Opens plugins captured through REAPER in a process of their own, so a crashing plugin can't take REAPER down.

REAPER keeps the per-plugin "Run as" choice in reaper-vstbridge64.ini, keyed by the plugin's real file name,
and reads it each time a plugin is loaded. Ordel sets "dedicated process" just for the capture and then puts
the file back as it was. Cockos plugins are trusted and CLAP plugins can't be bridged by REAPER.
"""
import logging
from contextlib import contextmanager
from pathlib import Path

from .reaper_db import find_plugin_file, plugin_files, plugin_roots

log = logging.getLogger(__name__)
SECTION = "[vst_dll_options]"
DEDICATED = "2 -1"  # what REAPER writes for Run as > Dedicated process


def _read(ini: Path) -> list[str]:
    return ini.read_text(encoding="utf-8", errors="surrogateescape").splitlines() if ini.is_file() else []


def _write(ini: Path, lines: list[str]) -> None:
    ini.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="surrogateescape")


def _section(lines: list[str]) -> tuple[int, int] | None:
    """(header index, end index) of REAPER's per-plugin options section."""
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == SECTION), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    return start, end


def set_dedicated(ini: Path, filename: str) -> str:
    """Run this plugin in a dedicated process: 'added', 'already' (the user set it), or 'other' (the user chose
    another mode, which is left alone)."""
    lines = _read(ini)
    found = _section(lines)
    if found is None:
        lines += [SECTION]
        found = (len(lines) - 1, len(lines))
    start, end = found
    for line in lines[start + 1:end]:
        key, _, value = line.partition("=")
        if key.strip().lower() == filename.lower():
            return "already" if value.strip() == DEDICATED else "other"
    lines.insert(start + 1, f"{filename}={DEDICATED}")
    _write(ini, lines)
    return "added"


def unset_dedicated(ini: Path, filename: str) -> None:
    lines = _read(ini)
    found = _section(lines)
    if found is None:
        return
    start, end = found
    ours = f"{filename}={DEDICATED}".lower()
    keep = lines[:start + 1] + [l for l in lines[start + 1:end] if l.strip().lower() != ours] + lines[end:]
    if keep != lines:
        _write(ini, keep)


class Isolation:
    """isolation(plugin) is a context giving how the plugin runs: "bridged" (REAPER's separate process),
    "trusted" (REAPER's own plugins, in REAPER itself) or False (it could take REAPER down)."""

    def __init__(self, reaper_dir: Path, data_dir: Path):
        self.ini = Path(reaper_dir) / "reaper-vstbridge64.ini"
        self.reaper_dir = Path(reaper_dir)
        self.pending = Path(data_dir) / "isolated.txt"  # undone at next start if Ordel dies mid-capture
        self._index = None
        self.restore()

    def restore(self) -> None:
        try:
            for name in self.pending.read_text(encoding="utf-8").splitlines():
                if name.strip():
                    unset_dedicated(self.ini, name.strip())
            self.pending.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            log.warning("could not restore REAPER's bridge settings", exc_info=True)

    def forget(self) -> None:
        """Look for plugin files again next time (new plugins may have been installed)."""
        self._index = None

    def use_reaper_dir(self, reaper_dir: Path) -> None:
        self.reaper_dir = Path(reaper_dir)
        self.ini = self.reaper_dir / "reaper-vstbridge64.ini"
        self.forget()

    def _file(self, plugin) -> str | None:
        if self._index is None:
            self._index = plugin_files(plugin_roots(self.reaper_dir))
        path = find_plugin_file(plugin.key, [], self._index)
        return path.name if path else None

    @contextmanager
    def __call__(self, plugin):
        if plugin.vendor == "Cockos":
            yield "trusted"
            return
        name = self._file(plugin) if plugin.format in ("VST", "VST3") else None
        state = None
        if name:
            try:
                self.pending.write_text(name, encoding="utf-8")  # before the change, so a crash can't strand it
                state = set_dedicated(self.ini, name)
            except OSError:
                log.warning("could not isolate %s", plugin.name, exc_info=True)
            if state != "added":
                self.pending.unlink(missing_ok=True)
        try:
            yield "bridged" if state in ("added", "already") else False
        finally:
            if state == "added":
                try:
                    unset_dedicated(self.ini, name)
                    self.pending.unlink(missing_ok=True)
                except OSError:
                    log.warning("could not restore %s's bridge setting; will retry at next start", plugin.name)
