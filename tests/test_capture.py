import time
from pathlib import Path

from studio_hub.bridge import ReaperBridge
from studio_hub.capture import CaptureRunner
from studio_hub.library import Library
from studio_hub.reaper_db import load_plugins
from tests.fake_reaper import FakeReaper

FIX = Path(__file__).parent / "fixtures" / "reaper"


def wait_done(runner, timeout=10):
    end = time.monotonic() + timeout
    while runner.status()["running"] and time.monotonic() < end:
        time.sleep(0.02)
    assert not runner.status()["running"]


def make(tmp_path, grab_fails=(), fake=True, die_on=None, helper=None):
    plugins = load_plugins(FIX)
    lib = Library(tmp_path / "lib.json")
    reaper = FakeReaper(tmp_path / "bridge", die_on=die_on) if fake else None
    grabbed = []

    def grab(hwnd, out):
        if hwnd in grab_fails:
            return False
        out.write_bytes(b"png")
        grabbed.append(hwnd)
        return True

    runner = CaptureRunner(ReaperBridge(tmp_path / "bridge"), lib, tmp_path / "snaps", lambda: plugins,
                           find_window=lambda name, timeout=8.0: name, grab=grab, helper=helper)
    return runner, lib, plugins, reaper, grabbed


def test_captures_pending_and_marks_status(tmp_path):
    runner, lib, plugins, reaper, _ = make(tmp_path, grab_fails={"VST3i: Vital (Vital Audio)"})
    try:
        runner.start()
        wait_done(runner)
        states = {v["name"]: v["capture"] for v in lib.view(plugins)}
        assert states["Vital"] == "failed" and states["ReaComp"] == "ok"
        verbs = [v for v, _ in reaper.received]
        assert verbs[0] == "CAPTURE_BEGIN" and verbs[-1] == "CAPTURE_END"
        assert ("CAPTURE_OPEN", "VST3: AmpliTube 5 (IK Multimedia)") in reaper.received
        assert (tmp_path / "snaps" / f"{plugins[0].id}.png").exists()
        assert runner.status()["done"] == len(plugins) and runner.status()["failed"] == 1
    finally:
        reaper.stop()


def test_skips_already_captured(tmp_path):
    runner, lib, plugins, reaper, grabbed = make(tmp_path)
    try:
        for p in plugins[1:]:
            lib.set_capture(p.id, "ok")
        runner.start()
        wait_done(runner)
        assert grabbed == [plugins[0].add_name]
    finally:
        reaper.stop()


def test_explicit_ids_recapture(tmp_path):
    runner, lib, plugins, reaper, grabbed = make(tmp_path)
    try:
        lib.set_capture(plugins[2].id, "ok")
        runner.start([plugins[2].id])
        wait_done(runner)
        assert grabbed == [plugins[2].add_name]
    finally:
        reaper.stop()


def test_cancel_ends_session(tmp_path):
    runner, lib, plugins, reaper, grabbed = make(tmp_path)
    try:
        runner.pause()
        runner.start()
        time.sleep(0.2)
        runner.cancel()
        wait_done(runner)
        verbs = [v for v, _ in reaper.received]
        assert ("CAPTURE_BEGIN" not in verbs or verbs[-1] == "CAPTURE_END") and len(grabbed) < len(plugins)
    finally:
        reaper.stop()


def test_stops_when_disconnected(tmp_path):
    runner, lib, plugins, _, grabbed = make(tmp_path, fake=False)
    runner.start()
    wait_done(runner)
    assert runner.status()["error"] == "not_connected" and grabbed == []


def test_stop_waits_for_capture_end(tmp_path):
    runner, lib, plugins, reaper, grabbed = make(tmp_path)
    try:
        runner.start()
        runner.stop(timeout=5)
        verbs = [v for v, _ in reaper.received]
        assert not runner.status()["running"] and ("CAPTURE_BEGIN" not in verbs or verbs[-1] == "CAPTURE_END")
    finally:
        reaper.stop()


def test_crop_removes_reaper_header_strip():
    from studio_hub.capture import plugin_area
    client = (100, 200, 700, 700)  # left, top, right, bottom in screen pixels
    header_controls = [(105, 203, 300, 225), (310, 204, 360, 226), (640, 203, 690, 224)]
    plugin_child = (120, 400, 300, 500)  # a knob deep inside the plugin UI must not count as header
    assert plugin_area(client, header_controls + [plugin_child]) == (100, 228, 700, 700)


def test_crop_keeps_whole_client_without_header():
    from studio_hub.capture import plugin_area
    assert plugin_area((0, 0, 400, 300), []) == (0, 0, 400, 300)


def test_finds_window_by_reapers_full_name(tmp_path):
    runner, lib, plugins, reaper, grabbed = make(tmp_path)
    try:
        runner.start()
        wait_done(runner)
        # e.g. 'VST3i: Sitala (Decomposer) (32 out)': the short name never appears whole in the title
        assert sorted(grabbed) == sorted(p.add_name for p in plugins)
    finally:
        reaper.stop()


def test_plugin_that_crashes_reaper_is_marked_and_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr("studio_hub.bridge.HEARTBEAT_MAX_AGE", 0.3)
    runner, lib, plugins, reaper, grabbed = make(tmp_path, die_on="Vital")
    runner.open_timeout = 1.0
    runner.crash_grace = 0.5
    try:
        runner.start()
        wait_done(runner)
        states = {v["name"]: v["capture"] for v in lib.view(plugins)}
        assert states["Vital"] == "crashed" and runner.status()["error"] == "not_connected"
        assert runner.status()["crashed"] == "Vital"
    finally:
        reaper.stop()
    runner, lib2, _, reaper, grabbed = make(tmp_path)
    try:
        runner.start()
        wait_done(runner)
        assert "VST3i: Vital (Vital Audio)" not in grabbed
    finally:
        reaper.stop()


def test_never_tried_plugins_go_before_failed_ones(tmp_path):
    runner, lib, plugins, reaper, grabbed = make(tmp_path)
    try:
        lib.set_capture(plugins[0].id, "failed")
        runner.start()
        wait_done(runner)
        assert grabbed[-1] == plugins[0].add_name
    finally:
        reaper.stop()


def test_blank_drawn_image_falls_back_to_screen_grab():
    from PIL import Image

    from studio_hub.capture import pick_image
    blank = Image.new("RGB", (400, 300), (40, 40, 40))
    real = Image.effect_noise((400, 300), 80).convert("RGB")
    assert pick_image(real, lambda: blank) is real
    assert pick_image(blank, lambda: real) is real
    assert pick_image(blank, lambda: blank) is None
    assert pick_image(None, lambda: real) is real


def test_window_title_match_ignores_extra_spaces_and_case():
    from studio_hub.capture import title_matches
    assert title_matches("VST3: The Klone  (Fazertone) - Track 1", "VST3: The Klone (Fazertone)")
    assert title_matches("vst: reaeq (cockos) - Track 1", "VST: ReaEQ (Cockos)")
    assert not title_matches("VST3: Pro-Q 3 (FabFilter) - Track 1", "VST3: Pro-Q 4 (FabFilter)")


def test_brief_heartbeat_gap_is_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr("studio_hub.bridge.HEARTBEAT_MAX_AGE", 0.3)
    plugins = load_plugins(FIX)
    lib = Library(tmp_path / "lib.json")
    reaper = FakeReaper(tmp_path / "bridge", stall_after_open=1.0)  # busy loading a slow plugin
    runner = CaptureRunner(ReaperBridge(tmp_path / "bridge"), lib, tmp_path / "snaps", lambda: plugins[:1],
                           find_window=lambda name, timeout=8.0: None, grab=lambda h, o: False)
    runner.crash_grace = 3.0
    try:
        runner.start()
        wait_done(runner, timeout=15)
        assert lib.capture_status(plugins[0].id) == "failed" and runner.status()["crashed"] is None
    finally:
        reaper.stop()


def fake_helper(outcomes: dict[str, str], seen: list):
    """Stands in for the helper process: VST3 plugins get the outcome named for them (default 'ok')."""
    def helper(plugin, out):
        if plugin.format != "VST3":
            return None
        seen.append(plugin.name)
        result = outcomes.get(plugin.name, "ok")
        if result == "ok":
            out.write_bytes(b"png")
        return result
    return helper


def reaper_opened(reaper):
    return [arg for verb, arg in reaper.received if verb == "CAPTURE_OPEN"]


def test_vst3_plugins_go_to_the_helper_not_reaper(tmp_path):
    seen = []
    runner, lib, plugins, reaper, _ = make(tmp_path, helper=fake_helper({}, seen))
    try:
        runner.start()
        wait_done(runner)
        assert sorted(seen) == sorted(p.name for p in plugins if p.format == "VST3")
        assert not any(a.startswith("VST3") for a in reaper_opened(reaper))
        assert "VST: ReaComp (Cockos)" in reaper_opened(reaper)
        assert all(v["capture"] == "ok" for v in lib.view(plugins))
    finally:
        reaper.stop()


def test_plugin_the_helper_cant_load_falls_back_to_reaper(tmp_path):
    runner, lib, plugins, reaper, _ = make(tmp_path, helper=fake_helper({"Vital": "unsupported"}, []))
    try:
        runner.start()
        wait_done(runner)
        assert "VST3i: Vital (Vital Audio)" in reaper_opened(reaper)
        assert {v["name"]: v["capture"] for v in lib.view(plugins)}["Vital"] == "ok"
    finally:
        reaper.stop()


def test_crash_or_hang_in_helper_is_skipped_without_touching_reaper(tmp_path):
    outcomes = {"Vital": "crashed", "AmpliTube 5": "hung"}
    runner, lib, plugins, reaper, _ = make(tmp_path, helper=fake_helper(outcomes, []))
    try:
        runner.start()
        wait_done(runner)
        states = {v["name"]: v["capture"] for v in lib.view(plugins)}
        assert states["Vital"] == "crashed" and states["AmpliTube 5"] == "crashed" and states["ReaComp"] == "ok"
        assert not any("Vital" in a or "AmpliTube" in a for a in reaper_opened(reaper))
        assert runner.status()["error"] is None
    finally:
        reaper.stop()


def test_without_reaper_helper_plugins_are_still_captured(tmp_path):
    runner, lib, plugins, _, _ = make(tmp_path, fake=False, helper=fake_helper({}, []))
    runner.start()
    wait_done(runner)
    states = {v["name"]: (v["capture"], v["format"]) for v in lib.view(plugins)}
    assert all(c == "ok" for c, f in states.values() if f == "VST3")
    assert all(c == "none" for c, f in states.values() if f != "VST3")  # left for when REAPER is open
    assert runner.status()["needs_reaper"] == sum(f != "VST3" for _, f in states.values())


def test_reaper_session_only_opens_when_a_plugin_needs_it(tmp_path):
    runner, lib, plugins, reaper, _ = make(tmp_path, helper=fake_helper({}, []))
    try:
        runner.start([p.id for p in plugins if p.format == "VST3"])
        wait_done(runner)
        assert reaper.received == []
    finally:
        reaper.stop()
