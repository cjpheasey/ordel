import json

from studio_hub.library import DEFAULT_SETTINGS, Library
from studio_hub.reaper_db import Plugin


def plugin(name="Opto", tags=("Dynamics",)):
    return Plugin("abc123abc123", name, "Vendor", "VST3", False, f"VST3: {name} (Vendor)", list(tags))


def test_defaults_when_missing(tmp_path):
    lib = Library(tmp_path / "library.json")
    assert lib.settings == DEFAULT_SETTINGS and lib.settings["theme"] == "ordel"
    assert lib.settings["hotkey"] == "Ctrl+Shift+Space"


def test_roundtrip_persists_favourite_and_category(tmp_path):
    Library(tmp_path / "l.json").set_favourite("abc123abc123", True)
    lib = Library(tmp_path / "l.json")
    lib.set_category("abc123abc123", "eq")
    item = Library(tmp_path / "l.json").view([plugin()])[0]
    assert item["favourite"] and item["category"] == "eq"


def test_override_beats_auto(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_category("abc123abc123", "eq")
    item = lib.view([plugin()])[0]
    assert item["category"] == "eq" and item["category_auto"] == "dynamics"


def test_clear_override(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_category("abc123abc123", "eq")
    lib.set_category("abc123abc123", None)
    assert lib.view([plugin()])[0]["category"] == "dynamics"


def test_invalid_category_rejected(tmp_path):
    lib = Library(tmp_path / "l.json")
    try:
        lib.set_category("abc123abc123", "nonsense")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_mark_used_and_capture_status(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.mark_used("abc123abc123")
    lib.set_capture("abc123abc123", "ok")
    item = lib.view([plugin()])[0]
    assert item["last_used"] > 0 and item["capture"] == "ok" and item["shot"] > 0


def test_corrupt_file_is_backed_up(tmp_path):
    (tmp_path / "library.json").write_text("{not json")
    lib = Library(tmp_path / "library.json")
    assert lib.settings == DEFAULT_SETTINGS
    assert (tmp_path / "library.corrupt.json").read_text() == "{not json"


def test_unknown_settings_ignored(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.update_settings(bogus=1, theme="glass")
    saved = json.loads((tmp_path / "l.json").read_text())
    assert "bogus" not in saved["settings"] and saved["settings"]["theme"] == "glass"


def test_wrong_shape_json_falls_back_to_defaults(tmp_path):
    path = tmp_path / "library.json"
    path.write_text('{"settings": {"window": "x", "theme": 5, "tile_size": 240}, "plugins": [1, 2]}')
    lib = Library(path)
    assert lib.settings["window"] is None and lib.settings["theme"] == "ordel" and lib.settings["tile_size"] == 240
    assert lib.view([plugin()])[0]["category"] == "dynamics"


def test_non_dict_plugin_entries_dropped(tmp_path):
    path = tmp_path / "library.json"
    path.write_text('{"plugins": {"abc123abc123": "x", "other": {"favourite": true}}}')
    assert Library(path).view([plugin()])[0]["favourite"] is False


def test_update_settings_rejects_wrong_types(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.update_settings(window="x", hide_after_add="no", theme="neon", tile_size=260)
    assert lib.settings["window"] is None and lib.settings["hide_after_add"] is False
    assert lib.settings["theme"] == "ordel" and lib.settings["tile_size"] == 260
    lib.update_settings(window={"x": 1, "y": 2, "width": 900, "height": 600})
    assert lib.settings["window"]["width"] == 900


def test_view_includes_tidy_developer_name(tmp_path):
    p = Plugin("abc123abc123", "Shimmer", "Valhalla DSP, LLC", "VST3", False, "VST3: Shimmer (Valhalla DSP, LLC)")
    item = Library(tmp_path / "l.json").view([p])[0]
    assert item["developer"] == "Valhalla DSP" and item["vendor"] == "Valhalla DSP, LLC"


def test_sidebar_mode_setting(tmp_path):
    lib = Library(tmp_path / "l.json")
    assert lib.settings["sidebar_mode"] == "categories"
    lib.update_settings(sidebar_mode="developers")
    lib.update_settings(sidebar_mode="nonsense")
    assert Library(tmp_path / "l.json").settings["sidebar_mode"] == "developers"


def test_tour_starts_unseen_and_is_remembered(tmp_path):
    lib = Library(tmp_path / "l.json")
    assert lib.settings["toured"] is False
    lib.update_settings(toured=True)
    assert Library(tmp_path / "l.json").settings["toured"] is True


def test_appearance_defaults_match_the_brand(tmp_path):
    s = Library(tmp_path / "l.json").settings
    assert s["theme"] == "ordel" and s["accent"] == "theme"
    assert (s["picture_fit"], s["density"], s["corners"], s["show_developer"]) == ("contain", "comfortable", "rounded", True)


def test_appearance_settings_only_accept_known_values(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.update_settings(accent="blue", picture_fit="cover", density="compact", corners="square", show_developer=False)
    lib.update_settings(accent="neon", picture_fit="stretch", density="tiny", corners="wobbly", show_developer="no")
    s = Library(tmp_path / "l.json").settings
    assert (s["accent"], s["picture_fit"], s["density"], s["corners"], s["show_developer"]) == (
        "blue", "cover", "compact", "square", False)


MAIN, MONO = "aaaaaaaaaaaa", "bbbbbbbbbbbb"


def group():
    main = Plugin(MAIN, "Comp", "Vendor", "VST3", False, "VST3: Comp (Vendor)", ["Dynamics"])
    mono = Plugin(MONO, "Comp (Mono)", "Vendor", "VST3", False, "VST3: Comp (Mono) (Vendor)", ["Dynamics"],
                  variant="Mono")
    main.variants = [mono]
    return main


def test_group_lists_its_versions_main_first(tmp_path):
    v, = Library(tmp_path / "l.json").view([group()])
    assert v["variants"] == [{"id": MAIN, "label": "Stereo", "shot": 0}, {"id": MONO, "label": "Mono", "shot": 0}]
    assert Library(tmp_path / "l.json").view([plugin()])[0]["variants"] == []


def test_group_is_starred_if_any_version_was(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_favourite(MONO, True)
    assert lib.view([group()])[0]["favourite"] is True


def test_unstarring_a_group_unstars_every_version(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_favourite(MONO, True)
    lib.set_favourite(MAIN, False, also=[MONO])
    assert lib.view([group()])[0]["favourite"] is False


def test_group_uses_a_versions_picture_when_main_has_none(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_capture(MONO, "ok")
    v, = lib.view([group()])
    assert v["shot_id"] == MONO and v["capture"] == "ok" and v["shot"] > 0
    lib.set_capture(MAIN, "custom")
    assert lib.view([group()])[0]["shot_id"] == MAIN


def test_group_recent_use_is_the_latest_of_its_versions(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.mark_used(MONO)
    assert lib.view([group()])[0]["last_used"] > 0


def test_category_override_on_a_version_carries_to_the_group(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_category(MONO, "eq")
    assert lib.view([group()])[0]["category"] == "eq"
    lib.set_category(MAIN, "reverb", also=[MONO])
    assert lib.view([group()])[0]["category"] == "reverb"
    assert lib._plugins[MONO].get("category") is None


def test_preferred_version_is_the_one_added_most(tmp_path):
    lib = Library(tmp_path / "l.json")
    assert lib.view([group()])[0]["preferred"] == MAIN
    lib.count_variant(MAIN, MONO)
    lib.count_variant(MAIN, MONO)
    lib.count_variant(MAIN, MAIN)
    assert lib.view([group()])[0]["preferred"] == MONO


def test_chain_meta_survives_reload_and_prunes_missing_files(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_chain_meta("file:Ordel/Vocal.RfxChain", order=1, return_track=False)
    lib.set_chain_meta("file:Gone.RfxChain", order=2)
    lib.set_chain_meta("built:abc", name="Drums", plugins=["VST: ReaEQ (Cockos)"])
    lib.set_chain_meta("file:Ordel/Vocal.RfxChain", return_track=True)
    lib.prune_chain_meta({"file:Ordel/Vocal.RfxChain"})
    again = Library(tmp_path / "l.json")
    assert again.chain_meta() == {"file:Ordel/Vocal.RfxChain": {"order": 1, "return_track": True},
                                  "built:abc": {"name": "Drums", "plugins": ["VST: ReaEQ (Cockos)"]}}
    again.remove_chain_meta("built:abc")
    assert "built:abc" not in Library(tmp_path / "l.json").chain_meta()


def test_bad_chain_meta_on_disk_is_ignored(tmp_path):
    (tmp_path / "l.json").write_text(json.dumps({"chains": {"file:a": "nope", "file:b": {"order": 1}}}))
    assert Library(tmp_path / "l.json").chain_meta() == {"file:b": {"order": 1}}


def test_seen_plugins_are_remembered(tmp_path):
    lib = Library(tmp_path / "l.json")
    assert lib.seen() is None  # never recorded: first run, or first run after updating
    lib.mark_seen({"a"})
    lib.mark_seen({"b"})
    assert Library(tmp_path / "l.json").seen() == {"a", "b"}


def test_each_version_says_whether_it_has_its_own_picture(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_capture(MONO, "ok")
    v, = lib.view([group()])
    main, mono = v["variants"]
    assert main["id"] == MAIN and main["shot"] == 0  # no picture of its own yet
    assert mono["id"] == MONO and mono["shot"] > 0
