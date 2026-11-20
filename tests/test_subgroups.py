from studio_hub.subgroups import SUBGROUPS, character_from_name, subgroup_from_name


def test_dynamics_subgroups_from_name_clues():
    cases = {
        "FabFilter Pro-L 2": "limiters", "FabFilter Pro-G": "gates", "FabFilter Pro-DS": "deessers",
        "RDeEsser": "deessers", "FabFilter Pro-MB": "multiband", "kHs Transient Shaper": "transient",
        "UADx 1176AE Compressor": "compressors", "soothe2": "other",
    }
    for name, want in cases.items():
        assert subgroup_from_name("dynamics", name, []) == want, name


def test_reverb_and_saturation_clues():
    assert subgroup_from_name("reverb", "ValhallaPlate", []) == "plate"
    assert subgroup_from_name("reverb", "Spring Reverb", []) == "spring"
    assert subgroup_from_name("reverb", "ValhallaRoom", []) == "room"  # not Hall: "Valhalla" contains "hall"
    assert subgroup_from_name("saturation", "UADx Oxide Tape Recorder", []) == "tape"


def test_reaper_tags_used_after_names():
    assert subgroup_from_name("dynamics", "Mystery", ["Limiter"]) == "limiters"
    assert subgroup_from_name("dynamics", "Pro-G", ["Compressor"]) == "gates"


def test_character_from_hardware_names():
    assert character_from_name("UADx 1176LN Rev E") == "fet"
    assert character_from_name("UADx LA-2A Gray") == "optical"
    assert character_from_name("Fairchild 670") == "tube"
    assert character_from_name("SSL G-Master Buss Compressor") == "vca"
    assert character_from_name("Lindell 254E") == "diode"
    assert character_from_name("FabFilter Pro-C 2") is None


def test_groups_without_subgroups_give_none():
    assert subgroup_from_name("filter", "Pro-Q 3", []) is None


def test_every_listed_group_ends_with_other():
    for group, subs in SUBGROUPS.items():
        assert subs[-1]["key"] == "other", group
        assert len({s["key"] for s in subs}) == len(subs), group


from studio_hub.categories import KEYS  # noqa: E402
from studio_hub.subgroups import detect, known_plugins  # noqa: E402


def test_known_list_beats_reaper_tags():
    known = [{"name": "Pro-L 2", "developer": "FabFilter", "group": "dynamics", "subgroup": "limiters",
              "character": None}]
    got = detect("FabFilter Pro-L 2", "FabFilter", ["Mastering"], False, known)
    assert got == {"group": "dynamics", "subgroup": "limiters", "character": None}


def test_known_list_needs_the_developer_and_a_word_start():
    known = [{"name": "L2", "developer": "Waves", "group": "dynamics", "subgroup": "limiters", "character": None}]
    assert detect("L2", "Someone Else", ["EQ"], False, known)["group"] == "eq"
    assert detect("SSL2 Thing", "Waves", ["EQ"], False, known)["group"] == "eq"
    assert detect("Waves L2 Stereo", "Waves", [], False, known)["subgroup"] == "limiters"


def test_longest_match_wins():
    known = [{"name": "1176", "developer": None, "group": "dynamics", "subgroup": "compressors", "character": "fet"},
             {"name": "1176 Rev A", "developer": None, "group": "dynamics", "subgroup": "compressors",
              "character": "vca"}]
    assert detect("UADx 1176 Rev A Compressor", "UA", [], False, known)["character"] == "vca"
    assert detect("UADx 1176AE Compressor", "UA", [], False, known)["character"] == "fet"


def test_no_match_falls_back_to_tags_then_names():
    assert detect("UADx LA-2A Gray Compressor", "UA", ["Dynamics"], False, []) == {
        "group": "dynamics", "subgroup": "compressors", "character": "optical"}
    assert detect("Mystery Gate", "X", [], False, []) == {"group": "dynamics", "subgroup": "gates", "character": None}
    assert detect("Mystery", "X", ["Filter"], False, []) == {"group": "filter", "subgroup": None, "character": None}


def test_shipped_list_is_valid():
    seen = set()
    for e in known_plugins():
        assert e["group"] in KEYS, e
        if e["group"] in SUBGROUPS:
            subs = {s["key"]: s for s in SUBGROUPS[e["group"]]}
            assert e["subgroup"] in subs, e
            assert e["character"] in {None, *(c["key"] for c in subs[e["subgroup"]]["characters"])}, e
        else:
            assert e["subgroup"] is None and e["character"] is None, e
        ident = (e["name"].lower(), (e["developer"] or "").lower())
        assert ident not in seen, e
        seen.add(ident)
    assert len(seen) >= 200
