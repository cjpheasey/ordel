import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from studio_hub.api import Api
from studio_hub.bridge import ReaperBridge
from studio_hub.library import Library
from studio_hub.server import make_server
from tests.fake_reaper import FakeReaper

FIX = Path(__file__).parent / "fixtures" / "reaper"


class StubCapture:
    def __init__(self):
        self.calls = []

    def start(self, ids=None): self.calls.append(("start", ids))
    def pause(self): self.calls.append(("pause",))
    def resume(self): self.calls.append(("resume",))
    def cancel(self): self.calls.append(("cancel",))
    def status(self): return {"running": False, "paused": False, "done": 0, "total": 0, "current": None, "failed": 0, "error": None}


@pytest.fixture
def env(tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<h1>hi</h1>")
    (tmp_path / "secret.txt").write_text("nope")
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    hidden = []
    fake = FakeReaper(tmp_path / "bridge", {"ADD": "OK\tTrack 1"})
    api = Api(FIX, Library(tmp_path / "lib.json"), ReaperBridge(tmp_path / "bridge"), StubCapture(),
              {"hide": lambda: hidden.append(1), "minimize": lambda: None, "quit": lambda: None,
               "pick_image": lambda: None, "set_hotkey": lambda combo: combo != "Ctrl+Shift+F12"})
    server = make_server(api, ui, snaps)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base, api, fake, hidden
    server.shutdown()
    fake.stop()


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read()


def post(url, body):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def find(api, name):
    return next(p for p in api.state()["plugins"] if p["name"] == name)


def test_serves_index(env):
    base, *_ = env
    assert get(base + "/") == (200, b"<h1>hi</h1>")


def test_state_lists_plugins_and_categories(env):
    base, *_ = env
    status, body = get(base + "/api/state")
    state = json.loads(body)
    assert status == 200 and len(state["plugins"]) == 7 and state["categories"][0]["key"] == "eq"
    assert state["reaper"]["connected"] is True and state["settings"]["theme"] == "ordel"


def test_send_keeps_window_open_by_default(env):
    base, api, fake, hidden = env
    assert post(base + "/api/send", {"id": find(api, "AmpliTube 5")["id"]})[1]["ok"] is True
    assert hidden == []


def test_send_adds_and_marks_used(env):
    base, api, fake, hidden = env
    api.library.update_settings(hide_after_add=True)
    pid = find(api, "AmpliTube 5")["id"]
    assert post(base + "/api/send", {"id": pid}) == (200, {"ok": True, "detail": "Track 1"})
    assert fake.received[-1] == ("ADD", "VST3: AmpliTube 5 (IK Multimedia)")
    assert hidden == [1] and find(api, "AmpliTube 5")["last_used"] > 0


def test_send_unknown_id(env):
    base, *_ = env
    assert post(base + "/api/send", {"id": "zzz"}) == (200, {"ok": False, "detail": "unknown"})


def test_plugin_update_category_override(env):
    base, api, *_ = env
    pid = find(api, "ReaComp")["id"]
    status, _ = post(base + "/api/plugin", {"id": pid, "category": "eq", "favourite": True})
    item = find(api, "ReaComp")
    assert status == 200 and item["category"] == "eq" and item["favourite"]


def test_invalid_category_is_400(env):
    base, api, *_ = env
    pid = find(api, "ReaComp")["id"]
    assert post(base + "/api/plugin", {"id": pid, "category": "nope"})[0] == 400


def test_settings_hotkey_failure_reported(env):
    base, *_ = env
    status, body = post(base + "/api/settings", {"hotkey": "Ctrl+Shift+F12"})
    assert status == 200 and body["hotkey_ok"] is False and body["settings"]["hotkey"] == "Ctrl+Shift+Space"


def test_capture_actions_forwarded(env):
    base, api, *_ = env
    post(base + "/api/capture", {"action": "retake", "id": "abc"})
    post(base + "/api/capture", {"action": "start"})
    assert api.capture.calls == [("start", ["abc"]), ("start", None)]


def test_static_rejects_traversal(env):
    base, *_ = env
    with pytest.raises(urllib.error.HTTPError) as e:
        get(base + "/..%2Fsecret.txt")
    assert e.value.code == 404


def test_bad_json_returns_400(env):
    base, *_ = env
    assert post(base + "/api/send", b"{nope")[0] == 400


def test_unknown_route_404(env):
    base, *_ = env
    assert post(base + "/api/nothing", {})[0] == 404


def test_state_reports_hotkey_ok(env):
    base, api, *_ = env
    api.hotkey_ok = False
    assert json.loads(get(base + "/api/state")[1])["hotkey_ok"] is False


def test_same_hotkey_can_be_registered_again(env):
    base, api, *_ = env
    calls = []
    api.hooks["set_hotkey"] = lambda combo: calls.append(combo) or True
    post(base + "/api/settings", {"hotkey": "Ctrl+Shift+Space"})
    assert calls == ["Ctrl+Shift+Space"] and api.hotkey_ok is True


def test_rejects_foreign_host(env):
    base, *_ = env
    req = urllib.request.Request(base + "/api/window", b'{"action":"quit"}',
                                 {"Content-Type": "application/json", "Host": "evil.example"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_rejects_non_json_post(env):
    base, *_ = env
    req = urllib.request.Request(base + "/api/window", b'{"action":"quit"}', {"Content-Type": "text/plain"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 415


def test_window_resize_actions_are_validated(env):
    base, api, *_ = env
    edges = []
    api.hooks["resize"] = edges.append
    assert post(base + "/api/window", {"action": "resize-se"})[0] == 200
    assert post(base + "/api/window", {"action": "resize-up"})[0] == 400
    assert edges == ["se"]


def test_send_adds_the_chosen_version_and_counts_it(env):
    from studio_hub.reaper_db import Plugin
    base, api, fake, hidden = env
    main = Plugin("aaaaaaaaaaaa", "Comp", "Vendor", "VST3", False, "VST3: Comp (Vendor)")
    mono = Plugin("bbbbbbbbbbbb", "Comp (Mono)", "Vendor", "VST3", False, "VST3: Comp (Mono) (Vendor)", variant="Mono")
    main.variants = [mono]
    api.plugins = [main]
    assert post(base + "/api/send", {"id": main.id, "variant": mono.id})[1]["ok"] is True
    assert fake.received[-1] == ("ADD", "VST3: Comp (Mono) (Vendor)")
    v = find(api, "Comp")
    assert v["preferred"] == mono.id and v["last_used"] > 0
    assert post(base + "/api/send", {"id": main.id, "variant": "zzzzzzzzzzzz"})[0] == 400
    post(base + "/api/send", {"id": main.id})
    assert fake.received[-1] == ("ADD", "VST3: Comp (Vendor)")


def test_starring_a_group_through_the_api_covers_its_versions(env):
    from studio_hub.reaper_db import Plugin
    base, api, *_ = env
    main = Plugin("aaaaaaaaaaaa", "Comp", "Vendor", "VST3", False, "VST3: Comp (Vendor)")
    main.variants = [Plugin("bbbbbbbbbbbb", "Comp (Mono)", "Vendor", "VST3", False, "x", variant="Mono")]
    api.plugins = [main]
    api.library.set_favourite("bbbbbbbbbbbb", True)
    post(base + "/api/plugin", {"id": main.id, "favourite": False})
    assert find(api, "Comp")["favourite"] is False


def new_plugin(pid="cccccccccccc", name="Fresh"):
    from studio_hub.reaper_db import Plugin
    return Plugin(pid, name, "Vendor", "VST3", False, f"VST3: {name} (Vendor)")


def test_first_state_counts_every_plugin_as_seen(env):
    _, api, *_ = env
    assert api.state()["new_plugins"] == []
    assert api.library.seen() == {p.id for p in api.plugins}


def test_plugin_found_later_is_new_until_captured(env):
    _, api, *_ = env
    api.state()
    api.plugins.append(new_plugin())
    assert api.state()["new_plugins"] == ["cccccccccccc"]
    api.capture_action("capture_new")
    assert api.capture.calls[-1] == ("start", ["cccccccccccc"]) and api.state()["new_plugins"] == []


def test_new_plugin_notice_can_be_dismissed(env):
    _, api, *_ = env
    api.state()
    api.plugins.append(new_plugin())
    api.capture_action("dismiss_new")
    assert api.state()["new_plugins"] == [] and api.capture.calls == []


def test_new_version_of_a_known_plugin_is_not_new(env):
    _, api, *_ = env
    api.state()
    api.plugins[0].variants.append(new_plugin("dddddddddddd", "Mono one"))
    assert api.state()["new_plugins"] == []


def test_first_look_with_no_plugins_yet_does_not_flag_the_whole_library_later(env):
    _, api, *_ = env
    real = api.plugins
    api.plugins = []  # REAPER hasn't scanned anything yet
    api.state()
    api.plugins = real
    assert api.state()["new_plugins"] == []


def test_connecting_starts_the_script_in_the_running_reaper_wherever_it_lives(env, monkeypatch, tmp_path):
    _, api, *_ = env
    api.reaper_dir = tmp_path / "reaper"  # the script is installed here, not into the shared fixtures
    launched = []
    monkeypatch.setattr("studio_hub.api._reaper_busy", lambda: False)
    monkeypatch.setattr("studio_hub.api.subprocess.Popen", lambda args, **kw: launched.append(args))
    exe = tmp_path / "D drive" / "REAPER" / "reaper.exe"
    monkeypatch.setattr("studio_hub.capture.running_reaper_exe", lambda: exe)
    api.install_bridge()
    assert launched and launched[-1][:2] == [str(exe), "-nonewinst"]
    monkeypatch.setattr("studio_hub.capture.running_reaper_exe", lambda: None)
    launched.clear()
    api.install_bridge()  # REAPER closed: it picks the script up when it next starts; never open REAPER
    assert launched == []


def test_recapture_all_leaves_your_own_images_alone(env):
    _, api, *_ = env
    mine = api.plugins[0]
    api.library.set_capture(mine.id, "custom")
    api.capture_action("recapture_all")
    started = api.capture.calls[-1][1]
    assert mine.id not in started and len(started) == len(api.plugins) - 1


def test_other_websites_cant_probe_the_local_server(env):
    base, *_ = env

    def get_from(site):
        req = urllib.request.Request(base + "/api/state", headers={"Sec-Fetch-Site": site})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    assert get_from("cross-site") == 403 and get_from("same-site") == 403
    assert get_from("same-origin") == 200 and get_from("none") == 200  # Ordel's own page, or typed in


def test_refresh_finds_reaper_that_wasnt_found_at_start(tmp_path, monkeypatch):
    from studio_hub.api import Api
    from studio_hub.library import Library
    moved = []

    class Indexed:
        def use_reaper_dir(self, folder): moved.append(folder)

    capture = StubCapture()
    capture.helper, capture.isolate = Indexed(), Indexed()
    api = Api(tmp_path / "nothing-here", Library(tmp_path / "lib.json"), ReaperBridge(tmp_path / "b"), capture, {})
    assert api.plugins == []  # e.g. a portable REAPER that was closed when Ordel started
    monkeypatch.setattr("studio_hub.api.reaper_dir", lambda: FIX)
    api.refresh()
    assert len(api.plugins) == 7 and api.reaper_dir == FIX and moved == [FIX, FIX]


def test_recapture_all_includes_every_version(env):
    from studio_hub.reaper_db import Plugin
    _, api, *_ = env
    api.plugins[0].variants = [Plugin("cccccccccccc", "X (Mono)", "V", "VST3", False, "VST3: X (Mono) (V)", variant="Mono")]
    api.capture_action("recapture_all")
    assert "cccccccccccc" in api.capture.calls[-1][1]


def test_custom_categories_appear_before_uncategorised(env):
    base, api, *_ = env
    created = post(base + "/api/category", {"action": "add", "label": "Vocal Chain"})[1]
    cats = api.state()["categories"]
    assert cats[-1]["key"] == "uncategorised" and cats[-2]["key"] == created["key"] and cats[-2]["custom"]
    pid = api.plugins[0].id
    assert post(base + "/api/plugin", {"id": pid, "category": created["key"]})[0] == 200
    assert post(base + "/api/category", {"action": "explode"})[0] == 400
