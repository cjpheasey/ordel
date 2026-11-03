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
