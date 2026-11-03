"""Ordel desktop app: the window, the global shortcut and the tray icon around the local server."""
import ctypes
import json
import logging
import sys
import threading
import time
import urllib.request

import pystray
import webview
import win32api
import win32con
import win32gui
from PIL import Image

from .api import Api
from .bridge import ReaperBridge
from .capture import CaptureRunner
from .helper import HelperCapture
from .hotkey import HotkeyListener
from .library import Library
from .paths import bridge_dir, data_dir, reaper_dir, resource, snapshots_dir
from .server import make_server

TITLE = "Ordel"
BACKGROUNDS = {"ordel": "#14171F", "graphite": "#1E1E20", "light": "#FFFFFF", "glass": "#121218"}
log = logging.getLogger("studio_hub")


MIN_SIZE = (900, 600)


def resized_rect(start: tuple, dx: int, dy: int, edge: str, min_w: int, min_h: int) -> tuple:
    """New window rect after dragging `edge` (n, s, e, w or a corner like "se") by dx, dy; never below the minimum."""
    left, top, right, bottom = start
    if "e" in edge:
        right = max(right + dx, left + min_w)
    if "w" in edge:
        left = min(left + dx, right - min_w)
    if "s" in edge:
        bottom = max(bottom + dy, top + min_h)
    if "n" in edge:
        top = min(top + dy, bottom - min_h)
    return left, top, right, bottom


def safe_geometry(geo: dict | None) -> dict:
    """Saved window size/position, minus a position that is minimised (-32000) or on an unplugged monitor."""
    if not geo:
        return {}
    out = {k: geo[k] for k in ("width", "height") if geo.get(k, 0) >= 400}
    x, y = geo.get("x"), geo.get("y")
    if isinstance(x, int) and isinstance(y, int) and win32api.MonitorFromPoint((x + 40, y + 20), 0):
        out.update(x=x, y=y)
    return out


def _light_taskbar() -> bool:
    """Windows' light taskbar would hide the white knob, so the tray uses a darker version there."""
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


def _already_running() -> bool:
    ctypes.windll.kernel32.CreateMutexW(None, False, "Ordel.SingleInstance")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def _show_existing() -> None:
    """A second launch just brings the running copy forward."""
    try:
        url = (data_dir() / "server.txt").read_text().strip()
        req = urllib.request.Request(url + "api/window", json.dumps({"action": "show"}).encode(),
                                     {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2)
    except OSError:
        pass


class App:
    def __init__(self):
        self.library = Library(data_dir() / "library.json")
        self.bridge = ReaperBridge(bridge_dir())
        self.capture = CaptureRunner(self.bridge, self.library, snapshots_dir(), lambda: self.api.plugins,
                                     helper=HelperCapture(reaper_dir()))
        self.api = Api(reaper_dir(), self.library, self.bridge, self.capture, {
            "show": self.show, "hide": self.hide, "minimize": self.minimize, "quit": self.quit,
            "resize": self.resize,
            "pick_image": self.pick_image, "set_hotkey": self.set_hotkey,
        })
        self.server = make_server(self.api, resource("ui"), snapshots_dir())
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        self.window: webview.Window | None = None
        self.tray: pystray.Icon | None = None
        self.hotkey = HotkeyListener(self.toggle)
        self.visible = True
        self._quitting = False

    # --- window ---
    def _hwnd(self) -> int:
        return win32gui.FindWindow(None, TITLE)

    def show(self) -> None:
        self.window.show()
        self.window.restore()
        self.visible = True
        hwnd = self._hwnd()
        if hwnd:
            # Alt tap lifts Windows' focus-stealing guard so the window really comes to the front.
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
        self.window.evaluate_js("document.getElementById('search').focus()")

    def hide(self) -> None:
        self._save_geometry()
        self.window.hide()
        self.visible = False

    def resize(self, edge: str) -> None:
        """The window is borderless, so Windows gives it no resize edges; follow the mouse ourselves."""
        threading.Thread(target=self._drag_resize, args=(edge,), daemon=True).start()

    def _drag_resize(self, edge: str) -> None:
        hwnd = self._hwnd()
        if not hwnd:
            return
        start = win32gui.GetWindowRect(hwnd)
        sx, sy = win32api.GetCursorPos()
        scale = ctypes.windll.user32.GetDpiForWindow(hwnd) / 96
        min_w, min_h = round(MIN_SIZE[0] * scale), round(MIN_SIZE[1] * scale)
        flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        while win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:  # until the mouse button is let go
            x, y = win32api.GetCursorPos()
            left, top, right, bottom = resized_rect(start, x - sx, y - sy, edge, min_w, min_h)
            win32gui.SetWindowPos(hwnd, 0, left, top, right - left, bottom - top, flags)
            time.sleep(0.012)
        self._save_geometry()

    def minimize(self) -> None:
        self.window.minimize()

    def toggle(self) -> None:
        if self.visible and self._hwnd() == win32gui.GetForegroundWindow():
            self.hide()
        else:
            self.show()

    def _save_geometry(self) -> None:
        w = self.window
        hwnd = self._hwnd()
        if w and w.width > 0 and not (hwnd and win32gui.IsIconic(hwnd)):
            self.library.update_settings(window={"x": w.x, "y": w.y, "width": w.width, "height": w.height})

    def pick_image(self) -> str | None:
        result = self.window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("Images (*.png;*.jpg;*.jpeg;*.bmp;*.webp)",))
        return result[0] if result else None

    def set_hotkey(self, combo: str) -> bool:
        ok = self.hotkey.register(combo)
        if not ok:
            self.hotkey.register(self.library.settings["hotkey"])  # keep the old one working
        return ok

    def quit(self) -> None:
        self._quitting = True
        self._save_geometry()
        self.capture.stop()
        if self.tray:
            self.tray.stop()
        self.hotkey.stop()
        self.server.shutdown()
        self.window.destroy()

    # --- start ---
    def _start_tray(self) -> None:
        menu = pystray.Menu(pystray.MenuItem("Show Ordel", lambda: self.show(), default=True),
                            pystray.MenuItem("Quit", lambda: self.quit()))
        tray = "assets/tray-light.png" if _light_taskbar() else "assets/tray.png"
        self.tray = pystray.Icon("Ordel", Image.open(resource(tray)), TITLE, menu)
        self.tray.run_detached()

    def run(self) -> None:
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        (data_dir() / "server.txt").write_text(self.url)
        self.api.hotkey_ok = self.hotkey.register(self.library.settings["hotkey"])
        if not self.api.hotkey_ok:
            log.warning("shortcut %s is taken by another app", self.library.settings["hotkey"])
        geo = safe_geometry(self.library.settings.get("window"))
        self.window = webview.create_window(
            TITLE, self.url, frameless=True, easy_drag=False, resizable=True,
            width=geo.get("width", 1200), height=geo.get("height", 780), x=geo.get("x"), y=geo.get("y"),
            min_size=MIN_SIZE, background_color=BACKGROUNDS.get(self.library.settings["theme"], "#14171F"))
        self.window.events.closing += self._on_closing
        self._start_tray()
        webview.start(gui="edgechromium", private_mode=False, storage_path=str(data_dir() / "webview"),
                      icon=str(resource("assets/icon.ico")))

    def _on_closing(self):
        if self._quitting:
            return True
        # Alt+F4 or the taskbar's Close hides instead, so the shortcut and tray keep working.
        threading.Thread(target=self.hide, daemon=True).start()
        return False


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--capture-helper":  # Ordel started as its own capture helper
        from . import helper
        helper.run(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        return
    logging.basicConfig(filename=data_dir() / "studio_hub.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if _already_running():
        _show_existing()
        return
    try:
        App().run()
    except Exception:
        log.exception("Ordel crashed")
        raise
