"""System-wide keyboard shortcut via Win32 RegisterHotKey (no admin rights, no extra dependency)."""
import ctypes
import threading
from ctypes import wintypes

MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
NAMED_KEYS = {"space": 0x20, "tab": 0x09, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
              "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E, "pageup": 0x21, "pagedown": 0x22,
              "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
              "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE,
              ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC}
WM_HOTKEY, WM_APP_REGISTER, WM_QUIT = 0x0312, 0x8001, 0x0012
HOTKEY_ID = 1

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32")


def parse_hotkey(combo: str) -> tuple[int, int]:
    parts = [p.strip().lower() for p in combo.split("+")]
    if len(parts) < 2 or not all(parts):
        raise ValueError(f"invalid shortcut {combo!r}")
    *mods, key = parts
    if any(m not in MODS for m in mods):
        raise ValueError(f"invalid shortcut {combo!r}")
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x6F + int(key[1:])
    else:
        raise ValueError(f"invalid shortcut {combo!r}")
    flags = MOD_NOREPEAT
    for m in mods:
        flags |= MODS[m]
    return flags, vk


class HotkeyListener:
    """Owns a thread with a Win32 message loop; hotkeys are tied to the thread that registers them."""

    def __init__(self, callback):
        self.callback = callback
        self._pending: tuple[int, int] | None = None
        self._result = False
        self._done = threading.Event()
        self._ready = threading.Event()
        self._thread_id = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._ready.wait()

    def _loop(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # creates this thread's message queue
        self._ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                try:
                    self.callback()
                except Exception:
                    pass
            elif msg.message == WM_APP_REGISTER:
                user32.UnregisterHotKey(None, HOTKEY_ID)
                mods, vk = self._pending
                self._result = bool(user32.RegisterHotKey(None, HOTKEY_ID, mods, vk))
                self._done.set()
        user32.UnregisterHotKey(None, HOTKEY_ID)

    def register(self, combo: str) -> bool:
        try:
            self._pending = parse_hotkey(combo)
        except ValueError:
            return False
        self._done.clear()
        user32.PostThreadMessageW(self._thread_id, WM_APP_REGISTER, 0, 0)
        self._done.wait(2.0)
        return self._result

    def stop(self) -> None:
        user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(2.0)
