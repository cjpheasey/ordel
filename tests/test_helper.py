import sys
import time

import win32api
import win32con

from studio_hub.helper import LOAD_FAILED, capture_with_helper, helper_command


def alive(pid: int) -> bool:
    try:
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    except win32api.error:
        return False
    try:
        import win32process
        return win32process.GetExitCodeProcess(handle) == 259  # STILL_ACTIVE
    finally:
        win32api.CloseHandle(handle)


def py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def ok_grab(hwnd, out):
    out.write_bytes(b"png")
    return True


def test_plugin_that_wont_load_is_unsupported(tmp_path):
    result = capture_with_helper(py(f"import sys; sys.exit({LOAD_FAILED})"), tmp_path / "a.png", ok_grab, timeout=10)
    assert result == "unsupported"


def test_helper_crash_is_contained(tmp_path):
    result = capture_with_helper(py("import os; os._exit(139)"), tmp_path / "a.png", ok_grab, timeout=10)
    assert result == "crashed"


def test_hung_plugin_is_killed_with_its_whole_process_family(tmp_path):
    pidfile = tmp_path / "pid.txt"
    code = f"import os, time; open(r'{pidfile}', 'w').write(str(os.getpid())); time.sleep(120)"
    start = time.monotonic()
    result = capture_with_helper(py(code), tmp_path / "a.png", ok_grab, timeout=3)
    assert result == "hung" and time.monotonic() - start < 10
    # The venv python.exe is a launcher; this pid is the real interpreter underneath it.
    time.sleep(0.5)
    assert not alive(int(pidfile.read_text()))


def test_window_titled_pedalboard_is_captured(tmp_path):
    code = ("import tkinter as tk; r = tk.Tk(); r.title('Pedalboard'); r.geometry('400x300+50+50'); "
            "r.after(20000, r.destroy); r.mainloop()")
    grabbed = []
    result = capture_with_helper(py(code), tmp_path / "a.png", lambda h, o: grabbed.append(h) or ok_grab(h, o),
                                 timeout=15)
    assert result == "ok" and grabbed and (tmp_path / "a.png").exists()


def test_other_windows_such_as_licence_dialogs_are_ignored(tmp_path):
    code = ("import tkinter as tk; r = tk.Tk(); r.title('Authorise your plugin'); r.geometry('400x300+50+50'); "
            "r.after(20000, r.destroy); r.mainloop()")
    assert capture_with_helper(py(code), tmp_path / "a.png", ok_grab, timeout=3) == "hung"


def test_helper_command_runs_studio_hub_in_helper_mode():
    cmd = helper_command("C:/x/Plug.vst3", "IR-L Mono")
    assert cmd[-3:] == ["--capture-helper", "C:/x/Plug.vst3", "IR-L Mono"]
    assert helper_command("C:/x/Plug.vst3", None)[-2:] == ["--capture-helper", "C:/x/Plug.vst3"]


def test_helper_capture_finds_the_file_and_names_shell_plugins(tmp_path, monkeypatch):
    from studio_hub import helper
    from studio_hub.reaper_db import Plugin
    vst3 = tmp_path / "VST3"
    (vst3 / "FabFilter").mkdir(parents=True)
    (vst3 / "FabFilter" / "FabFilter Micro.vst3").write_bytes(b"")
    (vst3 / "WaveShell1-VST3 14.12_x64.vst3").write_bytes(b"")
    calls = []
    monkeypatch.setattr(helper, "capture_with_helper", lambda cmd, out, grab, timeout: calls.append(cmd) or "ok")
    capture = helper.HelperCapture(tmp_path / "reaper")
    capture.roots = [vst3]

    def plugin(name, fmt, key):
        return Plugin("x", name, "V", fmt, False, f"{fmt}: {name} (V)", key=key)

    assert capture(plugin("Micro", "VST3", "FabFilter_Micro.vst3"), tmp_path / "a.png") == "ok"
    assert calls[-1][-1].endswith("FabFilter Micro.vst3")
    assert capture(plugin("IR-L Mono", "VST3", "WaveShell1_VST3_14.12_x64.vst3<15886"), tmp_path / "b.png") == "ok"
    assert calls[-1][-1] == "IR-L Mono"
    assert capture(plugin("ReaComp", "VST", "reacomp.dll"), tmp_path / "c.png") is None
    assert capture(plugin("Gone", "VST3", "Gone.vst3"), tmp_path / "d.png") is None
