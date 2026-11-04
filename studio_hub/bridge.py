"""Talks to the Lua script running inside REAPER through two small text files."""
import contextlib
import os
import threading
import time
from pathlib import Path

from .paths import resource

MARKER = "-- studio-hub"
PLACEHOLDER = "--[[BRIDGE_DIR]]"
HEARTBEAT_MAX_AGE = 3.0
BUSY_TIMEOUT = 90.0  # longest wait for REAPER to finish a command it has started


def replace_file(src: Path, dst: Path) -> None:
    """os.replace, retried briefly: antivirus and sync tools can hold a file for a moment."""
    for attempt in range(10):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


class ReaperBridge:
    def __init__(self, bridge_dir: Path):
        self.dir = Path(bridge_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._next_id = time.time_ns()

    @staticmethod
    def alive() -> bool:
        """Is a REAPER process running at all (it can be busy and silent without having crashed)?"""
        from .capture import running_reaper_exe

        return running_reaper_exe() is not None

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
            command = self.dir / "command.txt"
            tmp.write_text(f"{cid}\t{verb}\t{arg}\n", encoding="utf-8")
            replace_file(tmp, command)
            response = self.dir / "response.txt"
            deadline = time.monotonic() + timeout
            taken = False
            next_check = 0.0
            while time.monotonic() < deadline:
                try:
                    rid, status, *detail = response.read_text(encoding="utf-8").rstrip("\r\n").split("\t", 2)
                except (OSError, ValueError):
                    rid = None
                if rid == cid:
                    response.unlink(missing_ok=True)
                    return status == "OK", detail[0] if detail else ""
                if not taken and not command.exists():
                    # REAPER has taken it and is working on it (a heavy plugin can take a while): wait it out
                    # rather than report a failure and have the user try again.
                    taken = True
                    deadline = max(deadline, time.monotonic() + BUSY_TIMEOUT)
                if taken and time.monotonic() >= next_check:
                    next_check = time.monotonic() + 1.0
                    if not self.connected() and not self.alive():
                        return False, "not_connected"  # REAPER crashed while doing it
                time.sleep(0.02)
            if not taken:
                with contextlib.suppress(OSError):  # never picked up: withdraw it so it can't run later
                    if command.read_text(encoding="utf-8").startswith(cid + "\t"):
                        command.unlink()
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
        # Only runs the script if it's there, so uninstalling Ordel never leaves REAPER showing an error.
        line = ('local ordel = reaper.GetResourcePath() .. "/Scripts/StudioHub/studio_hub_bridge.lua" '
                f'if reaper.file_exists(ordel) then dofile(ordel) end {MARKER}')
        lines = [l for l in existing.splitlines() if MARKER not in l]  # the user's own lines stay as they are
        startup.write_text("\n".join(lines + [line]) + "\n", encoding="utf-8")
        return script
