"""Takes a picture of every plugin by opening it in REAPER's capture tab and grabbing its window."""
import contextlib
import logging
import threading
import time
from pathlib import Path
from typing import Callable

from PIL import Image

log = logging.getLogger(__name__)


def _processes():
    """(pid, full path of its program) for every process we may look at."""
    import win32api
    import win32con
    import win32process

    for pid in win32process.EnumProcesses():
        try:
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            name = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
        except Exception:
            continue
        yield pid, name


def _reaper_pids() -> set[int]:
    pids = set()
    for pid, name in _processes():
        exe = name.lower().rsplit("\\", 1)[-1]
        if exe == "reaper.exe" or exe.startswith("reaper_host"):  # reaper_host64.exe runs bridged plugins
            pids.add(pid)
    return pids


def running_reaper_exe() -> Path | None:
    """Where the open REAPER lives, wherever it was installed."""
    return next((Path(name) for _, name in _processes() if Path(name).name.lower() == "reaper.exe"), None)


def title_matches(title: str, name: str) -> bool:
    """REAPER's window titles sometimes carry doubled spaces, e.g. 'VST3: The Klone  (Fazertone) - Track 1'."""
    return " ".join(name.lower().split()) in " ".join(title.lower().split())


def window_matches(title: str, add_name: str | None, name: str) -> bool:
    """REAPER's floating FX window, a bridged plugin's window ('FabFilter Pro-Q 3 (x64 bridged)'), or a
    plugin's own window titled exactly its name (ReaNINJAM).

    add_name=None looks for the plugin's own window only."""
    if add_name is not None:
        flat = " ".join(title.lower().split())
        core = " ".join(name.lower().split(" (")[0].split())  # without '(32 out)' style suffixes
        if title_matches(title, add_name) or (flat.endswith("bridged)") and flat.startswith(core + " (")):
            return True
    return title.strip() == name


def close_own_window(hwnd: int, name: str) -> None:
    """A plugin's own window outlives its track, so close it after capture. REAPER's FX windows are left alone."""
    import win32con
    import win32gui

    try:
        if win32gui.GetWindowText(hwnd).strip() == name:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    except Exception:
        pass


def find_plugin_window(name: str | None, timeout: float = 15.0, plugin_name: str = "") -> int | None:
    """The floating FX window REAPER opened for this plugin, e.g. 'VST3: Pro-Q 3 (FabFilter) - Track 1'."""
    import win32gui
    import win32process

    # shortcut: the same plugin open bridged in the user's own project would also match; fine while rare.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pids = _reaper_pids()  # each time: a bridged plugin's host process may start after we begin looking
        found = []

        def visit(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and window_matches(win32gui.GetWindowText(hwnd), name, plugin_name):
                if win32process.GetWindowThreadProcessId(hwnd)[1] in pids:
                    found.append(hwnd)

        win32gui.EnumWindows(visit, None)
        if found:
            return found[0]
        time.sleep(0.2)
    return None


def _editor_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Screen rect of the plugin's own UI inside REAPER's floating FX window."""
    import win32gui

    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    x, y = win32gui.ClientToScreen(hwnd, (left, top))
    controls = []
    win32gui.EnumChildWindows(hwnd, lambda h, _: controls.append(win32gui.GetWindowRect(h))
                              if win32gui.IsWindowVisible(h) else None, None)
    return plugin_area((x, y, x + right - left, y + bottom - top), controls)


def client_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Screen rect of the window's contents, without its title bar (used for the helper's editor window)."""
    import win32gui

    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    x, y = win32gui.ClientToScreen(hwnd, (left, top))
    return x, y, x + right - left, y + bottom - top


def plugin_area(client: tuple, controls: list[tuple]) -> tuple:
    """Crop off REAPER's preset/parameter strip: the short controls hugging the top of the client area."""
    left, top, right, bottom = client
    header = [r for r in controls if r[1] - top < 40 and r[3] - r[1] < 40]
    if header:
        top = max(r[3] for r in header) + 2
    return left, top, right, bottom


def _print_window(hwnd: int) -> Image.Image | None:
    """Ask Windows to draw the window itself, so whatever is covering it never ends up in the picture."""
    import ctypes

    import win32gui
    import win32ui

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    window_dc = win32gui.GetWindowDC(hwnd)
    src = win32ui.CreateDCFromHandle(window_dc)
    mem = src.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(src, width, height)
        mem.SelectObject(bitmap)
        if not ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2):  # PW_RENDERFULLCONTENT
            return None
        info = bitmap.GetInfo()
        return Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), bitmap.GetBitmapBits(True),
                                "raw", "BGRX", 0, 1)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        mem.DeleteDC()
        src.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)


def _looks_blank(img: Image.Image) -> bool:
    small = img.convert("RGB").resize((64, 48))
    colors = small.getcolors(64 * 48) or []
    return bool(colors) and max(c for c, _ in colors) / (64 * 48) >= 0.98


def grab_window(hwnd: int, out: Path, area: Callable[[int], tuple] = _editor_rect) -> bool:
    import ctypes

    import win32con
    import win32gui

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixel coordinates on scaled displays
    except OSError:
        pass  # already set for this process
    flags = win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 40, 40, 0, 0, flags)  # fully on-screen so it renders
    time.sleep(1.2)  # plugins draw their UI a moment after opening
    img = previous = None
    for _ in range(10):
        img = _print_window(hwnd)
        if img is None or (previous is not None and img.tobytes() == previous.tobytes()):
            break
        previous = img
        time.sleep(0.3)
    win_left, win_top, _, _ = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = area(hwnd)
    printed = img.crop((left - win_left, top - win_top, right - win_left, bottom - win_top)) if img else None
    img = pick_image(printed, lambda: _screen_grab(hwnd, area))
    if img is None:
        return False
    img.save(out)
    return True


def _usable(img: Image.Image | None) -> bool:
    return img is not None and img.width >= 80 and img.height >= 60 and not _looks_blank(img)


def pick_image(printed: Image.Image | None, screen_grab: Callable[[], Image.Image | None]) -> Image.Image | None:
    """GPU-drawn plugins (OpenGL) often come back blank from PrintWindow; then photograph the screen instead."""
    if _usable(printed):
        return printed
    shot = screen_grab()
    return shot if _usable(shot) else None


def _screen_grab(hwnd: int, area: Callable[[int], tuple] = _editor_rect) -> Image.Image | None:
    import mss
    import win32con
    import win32gui

    keep = win32con.SWP_NOSIZE | win32con.SWP_NOMOVE | win32con.SWP_NOACTIVATE
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, keep)  # nothing may cover it
    try:
        time.sleep(0.4)
        left, top, right, bottom = area(hwnd)
        with mss.MSS() as screen:
            shot = screen.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
        return Image.frombytes("RGB", shot.size, shot.rgb)
    except Exception:
        log.exception("screen grab failed")
        return None
    finally:
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, keep)


class CaptureRunner:
    def __init__(self, bridge, library, snapshots_dir: Path, plugins_fn: Callable,
                 find_window=find_plugin_window, grab=grab_window, helper=None, grab_own=None, isolate=None):
        self.bridge = bridge
        self.library = library
        self.snapshots_dir = Path(snapshots_dir)
        self.plugins_fn = plugins_fn
        self.find_window = find_window
        self.grab = grab
        # helper(plugin, out) -> 'ok' | 'failed' | 'unsupported' | 'crashed' | 'hung', or None if it can't take it
        self.helper = helper
        # isolate(plugin) -> context giving True when the plugin runs where it can't take REAPER down
        self.isolate = isolate or (lambda plugin: contextlib.nullcontext(True))
        self.close_window = close_own_window
        # A plugin's own window has no REAPER strip to trim, so it keeps its whole contents.
        self.grab_own = grab_own or (lambda hwnd, out: grab_window(hwnd, out, area=client_rect))
        self._thread: threading.Thread | None = None
        self._resume = threading.Event()
        self._resume.set()
        self._cancel = threading.Event()
        self._status = {"running": False, "paused": False, "done": 0, "total": 0,
                        "current": None, "failed": 0, "error": None, "crashed": None, "needs_reaper": 0,
                        "needs_save": 0}
        self.open_timeout = 20.0
        self.crash_grace = 10.0  # REAPER can go quiet for seconds while a heavy plugin loads

    def status(self) -> dict:
        return dict(self._status, paused=not self._resume.is_set())

    def start(self, ids: list[str] | None = None) -> None:
        if self._thread and self._thread.is_alive():
            return
        plugins = self.plugins_fn()
        if ids is None:
            # Never-tried plugins first; ones that crashed REAPER are only retried on request.
            todo = [p for p in plugins if self.library.capture_status(p.id) == "none"]
            todo += [p for p in plugins if self.library.capture_status(p.id) == "failed"]
        else:
            wanted = set(ids)
            todo = [p for p in plugins if p.id in wanted]
        self._cancel.clear()
        self._status.update(running=True, done=0, total=len(todo), current=None, failed=0, error=None,
                            crashed=None, needs_reaper=0, needs_save=0)
        self._thread = threading.Thread(target=self._run, args=(todo,), daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._resume.set()

    def stop(self, timeout: float = 5.0) -> None:
        """Cancel and wait, so REAPER's capture tab is closed before the app exits."""
        self.cancel()
        if self._thread:
            self._thread.join(timeout)

    def _run(self, todo) -> None:
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        session = None  # REAPER's capture tab opens only once a plugin actually needs REAPER
        try:
            for plugin in todo:
                self._resume.wait()
                if self._cancel.is_set():
                    break
                self._status["current"] = plugin.name
                result = self._via_helper(plugin)
                if result is None:
                    if session is None:
                        ok, detail = self.bridge.send("CAPTURE_BEGIN")
                        session = ok
                        if not ok:
                            self._status["error"] = detail
                    if not session:
                        self._status["needs_reaper"] += 1  # left as is, to capture once REAPER is open
                        self._status["done"] += 1
                        continue
                    with self.isolate(plugin) as safe:
                        if not safe and not self._work_saved():
                            self._status["needs_save"] += 1  # left as is, to capture once the work is saved
                            self._status["done"] += 1
                            continue
                        result = self._capture_one(plugin)
                    if result != "ok" and self._reaper_gone():
                        result = "crashed"  # REAPER went down while this plugin was open
                        session = False
                        self._status.update(error="not_connected", crashed=plugin.name)
                self.library.set_capture(plugin.id, result)
                self._status["done"] += 1
                self._status["failed"] += result != "ok"
            if session:
                self.bridge.send("CAPTURE_END")
        except Exception as e:  # a capture problem must never take the app down
            log.exception("capture run failed")
            self._status["error"] = str(e)
        finally:
            self._status.update(running=False, current=None)

    def _via_helper(self, plugin) -> str | None:
        """'ok', 'failed' or 'crashed' when the helper handled it; None means REAPER should try it."""
        if self.helper is None:
            return None
        result = self.helper(plugin, self.snapshots_dir / f"{plugin.id}.png")
        if result in ("crashed", "hung"):
            return "crashed"  # it would likely take REAPER down too, so don't try it there
        return result if result in ("ok", "failed") else None

    def _work_saved(self) -> bool:
        """A plugin that can't be isolated could crash REAPER, so only open it when nothing would be lost."""
        ok, detail = self.bridge.send("CHECK_SAVED")
        return ok or detail == "UNKNOWN_VERB"  # an older bridge can't tell; behave as before

    def _reaper_gone(self) -> bool:
        deadline = time.monotonic() + self.crash_grace
        while time.monotonic() < deadline:
            if self.bridge.connected():
                return False
            time.sleep(0.2)
        return True

    def _capture_one(self, plugin) -> str:
        ok, detail = self.bridge.send("CAPTURE_OPEN", plugin.add_name, timeout=self.open_timeout)
        try:
            if not ok:
                log.info("capture %s: REAPER couldn't open it (%s)", plugin.add_name, detail)
                return "failed"
            # REAPER titles the window with its full name, e.g. 'VST3i: Sitala (Decomposer) (32 out) - Track 1'
            hwnd = self.find_window(plugin.add_name, plugin_name=plugin.name)
            if not hwnd:
                log.info("capture %s: its window never appeared", plugin.add_name)
                return "failed"
            out = self.snapshots_dir / f"{plugin.id}.png"
            try:
                if self.grab(hwnd, out):
                    return "ok"
                # Some plugins leave REAPER's window empty and draw in a window of their own (ReaNINJAM).
                own = self.find_window(None, timeout=3.0, plugin_name=plugin.name)
                if own and own != hwnd:
                    try:
                        if self.grab_own(own, out):
                            return "ok"
                    finally:
                        self.close_window(own, plugin.name)
                log.info("capture %s: picture came out blank or too small", plugin.add_name)
                return "failed"
            finally:
                self.close_window(hwnd, plugin.name)
        except Exception:
            log.exception("capture failed for %s", plugin.name)
            return "failed"
        finally:
            if not self._reaper_gone():
                self.bridge.send("CAPTURE_CLOSE")
