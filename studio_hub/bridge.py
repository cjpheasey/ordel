"""Talks to the Lua script running inside REAPER through two small text files."""
import os
import threading
import time
from pathlib import Path

from .paths import resource

MARKER = "-- studio-hub"
PLACEHOLDER = "--[[BRIDGE_DIR]]"
HEARTBEAT_MAX_AGE = 3.0


class ReaperBridge:
    def __init__(self, bridge_dir: Path):
        self.dir = Path(bridge_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._next_id = time.time_ns()

    def connected(self) -> bool:
        try:
            return time.time() - (self.dir / "heartbeat.txt").stat().st_mtime < HEARTBEAT_MAX_AGE
        except OSError:
            return False

    def send(self, verb: str, arg: str = "", timeout: float = 5.0) -> tuple[bool, str]:
        if not self.connected():
            return False, "not_connected"
        with self._lock:
            self._next_id += 1
            cid = str(self._next_id)
            tmp = self.dir / "command.tmp"
            tmp.write_text(f"{cid}\t{verb}\t{arg}\n", encoding="utf-8")
            os.replace(tmp, self.dir / "command.txt")
            response = self.dir / "response.txt"
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    rid, status, *detail = response.read_text(encoding="utf-8").rstrip("\r\n").split("\t", 2)
                except (OSError, ValueError):
                    rid = None
                if rid == cid:
                    response.unlink(missing_ok=True)
                    return status == "OK", detail[0] if detail else ""
                time.sleep(0.02)
            return False, "timeout"

    def script_path(self, reaper_dir: Path) -> Path:
        return Path(reaper_dir) / "Scripts" / "StudioHub" / "studio_hub_bridge.lua"

    def installed(self, reaper_dir: Path) -> bool:
        startup = Path(reaper_dir) / "Scripts" / "__startup.lua"
        return self.script_path(reaper_dir).exists() and startup.exists() and MARKER in startup.read_text(
            encoding="utf-8", errors="replace")

    def _script_text(self) -> str:
        source = resource("reaper/studio_hub_bridge.lua").read_text(encoding="utf-8")
        return source.replace(PLACEHOLDER, f"[==[{self.dir}]==]")

    def outdated(self, reaper_dir: Path) -> bool:
        """The installed script is from an older Ordel."""
        try:
            return self.script_path(reaper_dir).read_text(encoding="utf-8") != self._script_text()
        except OSError:
            return False

    def install(self, reaper_dir: Path) -> Path:
        script = self.script_path(reaper_dir)
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(self._script_text(), encoding="utf-8")

        startup = script.parent.parent / "__startup.lua"
        existing = startup.read_text(encoding="utf-8", errors="replace") if startup.exists() else ""
        if MARKER not in existing:
            line = f'dofile(reaper.GetResourcePath() .. "/Scripts/StudioHub/studio_hub_bridge.lua") {MARKER}\n'
            sep = "" if not existing or existing.endswith("\n") else "\n"
            with startup.open("a", encoding="utf-8") as f:
                f.write(sep + line)
        return script
