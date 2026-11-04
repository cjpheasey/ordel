"""Opens one plugin in a throwaway helper process, so a plugin that crashes or hangs can't take REAPER down."""
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from .reaper_db import find_plugin_file, plugin_files, plugin_roots

log = logging.getLogger(__name__)

LOAD_FAILED = 3  # helper exit code: the plugin isn't loadable outside a DAW, so REAPER should try it instead
WINDOW_TITLE = "Pedalboard"  # pedalboard's editor window; anything else (licence prompts, splash screens) is ignored
STILL_ACTIVE = 259


def run(path: str, name: str | None) -> None:
    """Helper side: load the plugin and show its editor until Ordel kills this process."""
    try:
        import pedalboard

        plugin = pedalboard.load_plugin(path, plugin_name=name) if name else pedalboard.load_plugin(path)
    except Exception:
        sys.exit(LOAD_FAILED)
    plugin.show_editor()


def helper_command(path: str, name: str | None) -> list[str]:
    base = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "studio_hub"]
    return base + ["--capture-helper", str(path)] + ([name] if name else [])


def _start_in_job(cmd: list[str]):
    """Start suspended inside a kill-on-close job, so every process it spawns dies with it."""
    import win32con
    import win32job
    import win32process

    job = win32job.CreateJobObject(None, "")
    info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
    flags = win32con.CREATE_SUSPENDED | win32process.CREATE_NO_WINDOW
    process, thread, _, _ = win32process.CreateProcess(
        None, subprocess.list2cmdline(cmd), None, None, False, flags, None, None, win32process.STARTUPINFO())
    win32job.AssignProcessToJobObject(job, process)
    win32process.ResumeThread(thread)
    thread.Close()
    return job, process


def _editor_window(job) -> int | None:
    import win32gui
    import win32job
    import win32process

    pids = set(win32job.QueryInformationJobObject(job, win32job.JobObjectBasicProcessIdList))
    found = []

    def visit(hwnd, _):
        if (win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == WINDOW_TITLE
                and win32process.GetWindowThreadProcessId(hwnd)[1] in pids):
            found.append(hwnd)

    win32gui.EnumWindows(visit, None)
    return found[0] if found else None


def capture_with_helper(cmd: list[str], out: Path, grab: Callable[[int, Path], bool], timeout: float = 30.0) -> str:
    """Returns 'ok', 'failed' (blank picture), 'unsupported', 'crashed' or 'hung'."""
    import win32job
    import win32process

    job, process = _start_in_job(cmd)
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            code = win32process.GetExitCodeProcess(process)
            if code != STILL_ACTIVE:
                return "unsupported" if code == LOAD_FAILED else "crashed"
            hwnd = _editor_window(job)
            if hwnd:
                return "ok" if grab(hwnd, out) else "failed"
            time.sleep(0.2)
        return "hung"
    finally:
        win32job.TerminateJobObject(job, 1)
        process.Close()
        job.Close()


def _grab_editor(hwnd: int, out: Path) -> bool:
    from .capture import client_rect, grab_window

    return grab_window(hwnd, out, area=client_rect)


class HelperCapture:
    """CaptureRunner's helper: VST3 plugins whose file can be found open in a throwaway process."""

    def __init__(self, reaper_dir: Path, timeout: float = 30.0):
        self.roots = plugin_roots(reaper_dir)
        self.timeout = timeout
        self._index: dict[str, Path] | None = None  # shortcut: built once per app run; plugins added later use REAPER

    def __call__(self, plugin, out: Path) -> str | None:
        if plugin.format != "VST3":
            return None
        if self._index is None:
            self._index = plugin_files(self.roots)
        path = find_plugin_file(plugin.key, self.roots, self._index)
        if path is None:
            return None
        name = plugin.name if "<" in plugin.key else None  # one file holding many plugins, e.g. Waves shells
        result = capture_with_helper(helper_command(str(path), name), out, _grab_editor, self.timeout)
        log.info("helper capture %s: %s", plugin.add_name, result)
        return result
