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


def test_custom_categories_can_be_made_used_and_survive_a_restart(tmp_path):
    lib = Library(tmp_path / "l.json")
    drums = lib.add_category("  Drum Bus  ")
    assert drums["label"] == "Drum Bus" and drums["key"].startswith("c-") and drums["color"].startswith("#")
    lib.set_category(plugin().id, drums["key"])
    again = Library(tmp_path / "l.json")
    assert [c["label"] for c in again.custom_categories()] == ["Drum Bus"]
    assert again.view([plugin()])[0]["category"] == drums["key"]


def test_each_new_category_gets_its_own_colour(tmp_path):
    lib = Library(tmp_path / "l.json")
    colours = {lib.add_category(f"Mine {i}")["color"] for i in range(5)}
    assert len(colours) == 5


def test_category_names_must_be_real_and_unique(tmp_path):
    import pytest
    lib = Library(tmp_path / "l.json")
    lib.add_category("Vocals")
    for bad in ("", "   ", "vocals", "EQ", "x" * 41):
        with pytest.raises(ValueError):
            lib.add_category(bad)


def test_renaming_and_recolouring_a_category(tmp_path):
    import pytest
    lib = Library(tmp_path / "l.json")
    key = lib.add_category("Vox")["key"]
    lib.update_category(key, label="Vocals", color="#81B29A")
    assert lib.custom_categories() == [{"key": key, "label": "Vocals", "color": "#81B29A", "custom": True}]
    with pytest.raises(ValueError):
        lib.update_category(key, color="red; background: url(x)")  # only real colours
    with pytest.raises(ValueError):
        lib.update_category("eq", label="Nope")  # built-in categories can't be changed


def test_deleting_a_category_sends_its_plugins_back_to_their_detected_category(tmp_path):
    lib = Library(tmp_path / "l.json")
    key = lib.add_category("Vox")["key"]
    lib.set_category(plugin().id, key)
    lib.delete_category(key)
    assert lib.custom_categories() == [] and lib.view([plugin()])[0]["category"] == "dynamics"


def comp(name="FabFilter Pro-C 2"):
    return Plugin("abc123abc123", name, "FabFilter", "VST3", False, f"VST3: {name} (FabFilter)", ["Dynamics"])


def test_subgroup_and_character_detected_by_default(tmp_path):
    v = Library(tmp_path / "l.json").view([comp("UADx 1176AE Compressor")])[0]
    assert (v["subgroup"], v["character"], v["sorted_by"]) == ("compressors", "fet", "ordel")
    assert (v["subgroup_auto"], v["character_auto"]) == ("compressors", "fet")


def test_hand_set_group_survives_and_gets_a_subgroup_inside_it(tmp_path):
    path = tmp_path / "l.json"
    path.write_text(json.dumps({"version": 1, "plugins": {"abc123abc123": {"category": "reverb"}}}))
    v = Library(path).view([comp("Plate Thing")])[0]
    assert (v["category"], v["subgroup"], v["sorted_by"]) == ("reverb", "plate", "you")


def test_custom_category_has_no_subgroup(tmp_path):
    lib = Library(tmp_path / "l.json")
    key = lib.add_category("Vocal Chain")["key"]
    lib.set_category("abc123abc123", key)
    v = lib.view([comp()])[0]
    assert v["category"] == key and v["subgroup"] is None and v["character"] is None


def test_subgroup_set_on_a_group_covers_its_versions(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_subgroup(MONO, "gates")
    assert lib.view([group()])[0]["subgroup"] == "gates"
    lib.set_subgroup(MAIN, "limiters", also=[MONO])
    assert lib.view([group()])[0]["subgroup"] == "limiters" and "subgroup" not in lib._plugins[MONO]


def test_leaving_compressors_drops_the_character(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_character("abc123abc123", "tube")
    assert lib.view([comp()])[0]["character"] == "tube"
    lib.set_subgroup("abc123abc123", "limiters")
    v = lib.view([comp()])[0]
    assert v["subgroup"] == "limiters" and v["character"] is None


def test_moving_group_detects_subgroup_afresh(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_subgroup("abc123abc123", "gates")
    lib.set_character("abc123abc123", "vca")
    lib.set_category("abc123abc123", "reverb")
    v = lib.view([comp("Spring Thing")])[0]
    assert (v["category"], v["subgroup"], v["character"]) == ("reverb", "spring", None)
    assert "subgroup" not in lib._plugins["abc123abc123"]


def test_deleting_a_custom_category_clears_subgroup_too(tmp_path):
    lib = Library(tmp_path / "l.json")
    key = lib.add_category("Mine")["key"]
    lib.set_category("abc123abc123", key)
    lib._plugins["abc123abc123"]["subgroup"] = "gates"
    lib.delete_category(key)
    assert lib.view([comp()])[0]["subgroup"] == "compressors"


def test_existing_library_json_loads_unchanged(tmp_path):
    path = tmp_path / "l.json"
    record = {"category": "eq", "favourite": True, "capture": "ok", "shot": 5, "last_used": 3}
    path.write_text(json.dumps({"version": 1, "plugins": {"abc123abc123": record}}))
    lib = Library(path)
    lib.mark_used("other0000000")
    assert {k: json.loads(path.read_text())["plugins"]["abc123abc123"][k] for k in record} == record


def test_extra_groups_show_with_a_type_detected_inside_them(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_extra("abc123abc123", "dynamics", None)
    lib.set_extra("abc123abc123", "reverb", "plate")
    v = lib.view([comp("Limit Thing")])[0]
    assert v["category"] == "dynamics"  # the main group is never listed as an extra
    assert v["extra_groups"] == [{"group": "reverb", "subgroup": "plate"}]
    lib.set_category("abc123abc123", "eq")
    assert lib.view([comp("Limit Thing")])[0]["extra_groups"] == [
        {"group": "dynamics", "subgroup": "limiters"}, {"group": "reverb", "subgroup": "plate"}]


def test_moving_to_an_extra_group_makes_it_the_main_one(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_extra("abc123abc123", "reverb", None)
    lib.set_category("abc123abc123", "reverb")
    v = lib.view([comp()])[0]
    assert v["category"] == "reverb" and v["extra_groups"] == []


def test_extra_groups_cover_versions_and_can_be_removed(tmp_path):
    lib = Library(tmp_path / "l.json")
    lib.set_extra(MONO, "eq", None)
    lib.set_extra(MAIN, "reverb", None, also=[MONO])
    assert [e["group"] for e in lib.view([group()])[0]["extra_groups"]] == ["eq", "reverb"]
    assert "extra" not in lib._plugins[MONO]
    lib.set_extra(MAIN, "eq", None, on=False, also=[MONO])
    assert [e["group"] for e in lib.view([group()])[0]["extra_groups"]] == ["reverb"]


def test_unknown_extra_group_rejected_and_deleted_category_dropped(tmp_path):
    lib = Library(tmp_path / "l.json")
    try:
        lib.set_extra("abc123abc123", "nope", None)
        raise AssertionError("should have raised")
    except ValueError:
        pass
    key = lib.add_category("Vocal Chain")["key"]
    lib.set_extra("abc123abc123", key, None)
    assert lib.view([comp()])[0]["extra_groups"] == [{"group": key, "subgroup": None}]
    lib.delete_category(key)
    assert lib.view([comp()])[0]["extra_groups"] == []


def test_your_own_types_sit_before_other_and_survive_a_reload(tmp_path):
    lib = Library(tmp_path / "l.json")
    t = lib.add_type("dynamics", "Vocal comps")
    keys = [s["key"] for s in lib.types_of("dynamics")]
    assert keys[-2:] == [t["key"], "other"] and t["custom"] is True
    assert Library(tmp_path / "l.json").types_of("dynamics")[-2]["label"] == "Vocal comps"


def test_type_names_are_unique_within_a_group(tmp_path):
    lib = Library(tmp_path / "l.json")
    for bad in ("", "Compressors", "x" * 41):
        try:
            lib.add_type("dynamics", bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    lib.add_type("dynamics", "Vocal comps")
    try:
        lib.add_type("dynamics", "vocal  comps")
        raise AssertionError("duplicate")
    except ValueError:
        pass
    lib.add_type("reverb", "Vocal comps")  # another group may use the same name


def test_plugins_in_your_type_and_what_deleting_it_does(tmp_path):
    lib = Library(tmp_path / "l.json")
    t = lib.add_type("dynamics", "Vocal comps")["key"]
    lib.set_subgroup("abc123abc123", t)
    lib.set_extra("abc123abc123", "reverb", None)
    v = lib.view([comp("UADx 1176AE Compressor")])[0]
    assert v["subgroup"] == t and v["character"] is None  # characters belong to Compressors only
    lib.rename_type("dynamics", t, "Vox")
    assert lib.types_of("dynamics")[-2]["label"] == "Vox"
    lib.delete_type("dynamics", t)
    v = lib.view([comp("UADx 1176AE Compressor")])[0]
    assert v["subgroup"] == "compressors" and v["character"] == "fet"
    try:
        lib.delete_type("dynamics", "compressors")
        raise AssertionError("built-in types can't be deleted")
    except ValueError:
        pass


def test_your_own_category_can_have_types(tmp_path):
    lib = Library(tmp_path / "l.json")
    key = lib.add_category("Vocal Chain")["key"]
    t = lib.add_type(key, "Tuning")["key"]
    assert [s["key"] for s in lib.types_of(key)] == [t]  # no built-in Other in your own categories
    lib.set_category("abc123abc123", key)
    assert lib.view([comp()])[0]["subgroup"] is None  # nothing is sorted into your types automatically
    lib.set_subgroup("abc123abc123", t)
    assert lib.view([comp()])[0]["subgroup"] == t
    lib.delete_category(key)
    assert lib.types_of(key) == []
