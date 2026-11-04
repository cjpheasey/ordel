import os
import time

from studio_hub.bridge import ReaperBridge
from tests.fake_reaper import FakeReaper


def test_send_roundtrip_with_fake(tmp_path):
    fake = FakeReaper(tmp_path, {"ADD": "OK\tTrack 1"})
    try:
        assert ReaperBridge(tmp_path).send("ADD", "VST3: X (Y)") == (True, "Track 1")
        assert fake.received == [("ADD", "VST3: X (Y)")]
    finally:
        fake.stop()


def test_err_propagates(tmp_path):
    fake = FakeReaper(tmp_path, {"ADD": "ERR\tNO_TRACK"})
    try:
        assert ReaperBridge(tmp_path).send("ADD", "x") == (False, "NO_TRACK")
    finally:
        fake.stop()


def test_send_when_disconnected_is_fast(tmp_path):
    start = time.monotonic()
    assert ReaperBridge(tmp_path).send("ADD", "x") == (False, "not_connected")
    assert time.monotonic() - start < 0.2


def test_timeout_when_reaper_stops_answering(tmp_path):
    (tmp_path / "heartbeat.txt").write_text("1")
    assert ReaperBridge(tmp_path).send("PING", timeout=0.3) == (False, "timeout")


def test_connected_goes_false_after_heartbeat_stale(tmp_path):
    hb = tmp_path / "heartbeat.txt"
    hb.write_text("1")
    bridge = ReaperBridge(tmp_path)
    assert bridge.connected()
    old = time.time() - 10
    os.utime(hb, (old, old))
    assert not bridge.connected()


def test_install_is_idempotent_and_preserves_startup(tmp_path):
    reaper = tmp_path / "reaper"
    (reaper / "Scripts").mkdir(parents=True)
    (reaper / "Scripts" / "__startup.lua").write_text("print(1)\n")
    bridge = ReaperBridge(tmp_path / "bridge")
    assert not bridge.installed(reaper)
    script = bridge.install(reaper)
    bridge.install(reaper)
    startup = (reaper / "Scripts" / "__startup.lua").read_text()
    assert startup.startswith("print(1)\n") and startup.count("-- studio-hub") == 1
    body = script.read_text()
    assert "--[[BRIDGE_DIR]]" not in body and str(tmp_path / "bridge") in body
    assert bridge.installed(reaper)


def test_install_creates_startup_when_missing(tmp_path):
    reaper = tmp_path / "reaper"
    ReaperBridge(tmp_path / "bridge").install(reaper)
    assert "-- studio-hub" in (reaper / "Scripts" / "__startup.lua").read_text()


def test_script_from_an_older_ordel_is_outdated(tmp_path):
    bridge = ReaperBridge(tmp_path / "bridge")
    script = bridge.install(tmp_path / "reaper")
    assert not bridge.outdated(tmp_path / "reaper")
    script.write_text("-- older bridge", encoding="utf-8")
    assert bridge.outdated(tmp_path / "reaper")


def test_slow_command_is_waited_for_once_reaper_has_taken_it(tmp_path):
    fake = FakeReaper(tmp_path / "b", delays={"ADD": 1.0})  # e.g. a big sampler loading
    try:
        assert ReaperBridge(tmp_path / "b").send("ADD", "VSTi: Big (X)", timeout=0.3) == (True, "")
    finally:
        fake.stop()


def test_command_reaper_never_took_is_withdrawn_so_it_cant_run_later(tmp_path):
    bridge = ReaperBridge(tmp_path / "b")
    (tmp_path / "b" / "heartbeat.txt").write_text("1")  # looks connected, but nothing reads commands
    assert bridge.send("ADD", "VST: X (Y)", timeout=0.3) == (False, "timeout")
    assert not (tmp_path / "b" / "command.txt").exists()


def test_reaper_crashing_mid_command_is_noticed_quickly(tmp_path, monkeypatch):
    monkeypatch.setattr("studio_hub.bridge.HEARTBEAT_MAX_AGE", 0.3)
    fake = FakeReaper(tmp_path / "b", die_on="Crashy")
    bridge = ReaperBridge(tmp_path / "b")
    bridge.alive = lambda: not fake.dead  # its process is gone
    try:
        start = time.monotonic()
        assert bridge.send("CAPTURE_OPEN", "VST: Crashy (X)", timeout=0.3) == (False, "not_connected")
        assert time.monotonic() - start < 5
    finally:
        fake.stop()


def test_reaper_start_up_line_survives_ordel_being_uninstalled(tmp_path):
    reaper = tmp_path / "reaper"
    (reaper / "Scripts").mkdir(parents=True)
    startup = reaper / "Scripts" / "__startup.lua"
    startup.write_text('-- mine\ndofile(reaper.GetResourcePath() .. "/Scripts/StudioHub/studio_hub_bridge.lua") -- studio-hub\n')
    ReaperBridge(tmp_path / "b").install(reaper)
    lines = startup.read_text().splitlines()
    assert lines[0] == "-- mine" and len(lines) == 2  # the old line is replaced, the user's own kept
    assert "file_exists" in lines[1] and lines[1].endswith("-- studio-hub")  # no error once the script is gone
