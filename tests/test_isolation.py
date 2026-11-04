from pathlib import Path

from studio_hub.isolation import Isolation, set_dedicated, unset_dedicated
from studio_hub.reaper_db import Plugin

USER_INI = "[vst_dll_options]\nFabFilter Pro-MB.dll=2 -1\nSome Synth.dll=1 -1\n"


def plugin(fmt="VST", key="Ampeg_SVTVR_Classic.dll", vendor="Plugin Alliance"):
    return Plugin("id", "Ampeg SVTVR Classic", vendor, fmt, False, f"{fmt}: Ampeg SVTVR Classic ({vendor})", key=key)


def setup(tmp_path, ini_text=USER_INI):
    reaper, data = tmp_path / "reaper", tmp_path / "data"
    reaper.mkdir()
    data.mkdir()
    plugins = tmp_path / "VSTPlugins"
    plugins.mkdir()
    (plugins / "Ampeg SVTVR Classic.dll").write_bytes(b"")
    (reaper / "reaper.ini").write_text(f"[reaper]\nvstpath64={plugins}\n")
    ini = reaper / "reaper-vstbridge64.ini"
    if ini_text is not None:
        ini.write_text(ini_text)
    return Isolation(reaper, data), ini, data


def test_set_and_unset_leave_the_users_choices_alone(tmp_path):
    ini = tmp_path / "bridge.ini"
    ini.write_text(USER_INI)
    assert set_dedicated(ini, "Ampeg SVTVR Classic.dll") == "added"
    assert "Ampeg SVTVR Classic.dll=2 -1" in ini.read_text()
    assert set_dedicated(ini, "fabfilter pro-mb.dll") == "already"
    assert set_dedicated(ini, "Some Synth.dll") == "other"
    unset_dedicated(ini, "Ampeg SVTVR Classic.dll")
    assert ini.read_text() == USER_INI


def test_set_creates_the_file_when_missing(tmp_path):
    ini = tmp_path / "bridge.ini"
    assert set_dedicated(ini, "A.dll") == "added"
    assert ini.read_text().splitlines() == ["[vst_dll_options]", "A.dll=2 -1"]


def test_plugin_runs_dedicated_only_during_capture(tmp_path):
    iso, ini, data = setup(tmp_path)
    with iso(plugin()) as safe:
        assert safe and "Ampeg SVTVR Classic.dll=2 -1" in ini.read_text()
    assert ini.read_text() == USER_INI and not (data / "isolated.txt").exists()


def test_vst3_is_isolated_by_its_file_name(tmp_path):
    iso, ini, _ = setup(tmp_path)
    (tmp_path / "VSTPlugins" / "FabFilter Pro-Q 3.vst3").mkdir()
    with iso(plugin("VST3", "FabFilter_Pro_Q_3.vst3")) as safe:
        assert safe and "FabFilter Pro-Q 3.vst3=2 -1" in ini.read_text()


def test_setting_left_behind_by_a_crash_is_undone_at_next_start(tmp_path):
    iso, ini, data = setup(tmp_path)
    cm = iso(plugin())
    cm.__enter__()  # Ordel dies here, mid-capture
    assert "Ampeg SVTVR Classic.dll" in ini.read_text()
    Isolation(tmp_path / "reaper", data)
    assert ini.read_text() == USER_INI


def test_users_own_dedicated_setting_survives_a_crash(tmp_path):
    iso, ini, data = setup(tmp_path, "[vst_dll_options]\nAmpeg SVTVR Classic.dll=2 -1\n")
    iso(plugin()).__enter__()
    Isolation(tmp_path / "reaper", data)
    assert "Ampeg SVTVR Classic.dll=2 -1" in ini.read_text()


def test_what_cant_be_isolated(tmp_path):
    iso, ini, _ = setup(tmp_path)
    with iso(plugin("CLAP", "Thing.clap")) as safe:
        assert not safe  # REAPER can't bridge CLAP
    with iso(plugin(key="Missing.dll")) as safe:
        assert not safe  # file not found, so no name to give REAPER
    with iso(plugin(vendor="Cockos", key="reacomp.dll")) as safe:
        assert safe  # REAPER's own plugins are trusted
    assert ini.read_text() == USER_INI


def test_forget_finds_plugins_installed_since(tmp_path):
    iso, ini, _ = setup(tmp_path)
    new = plugin(key="Brand_New.dll")
    with iso(new) as safe:
        assert not safe
    (tmp_path / "VSTPlugins" / "Brand New.dll").write_bytes(b"")
    iso.forget()
    with iso(new) as safe:
        assert safe and "Brand New.dll=2 -1" in ini.read_text()


def test_isolation_follows_a_reaper_folder_found_later(tmp_path):
    iso, ini, data = setup(tmp_path)
    other = tmp_path / "portable"
    other.mkdir()
    (other / "reaper.ini").write_text(f"[reaper]\nvstpath64={tmp_path / 'VSTPlugins'}\n")
    iso.use_reaper_dir(other)
    with iso(plugin()) as safe:
        assert safe and "Ampeg SVTVR Classic.dll=2 -1" in (other / "reaper-vstbridge64.ini").read_text()
    assert ini.read_text() == USER_INI  # the old folder's settings untouched


def test_isolation_says_how_the_plugin_will_run(tmp_path):
    iso, _, _ = setup(tmp_path)
    with iso(plugin()) as how:
        assert how == "bridged"  # in REAPER's separate process
    with iso(plugin(vendor="Cockos", key="reacomp.dll")) as how:
        assert how == "trusted"  # REAPER's own plugins run in REAPER itself
    with iso(plugin("CLAP", "Thing.clap")) as how:
        assert how is False
