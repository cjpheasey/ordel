from pathlib import Path

from studio_hub.reaper_db import load_plugins

FIX = Path(__file__).parent / "fixtures" / "reaper"


def by_name(plugins):
    return {p.name: p for p in plugins}


def test_reads_vst_vst3_clap_and_shells():
    names = by_name(load_plugins(FIX)).keys()
    assert {"ReaComp", "AmpliTube 5", "Vital", "IR-L Mono", "TONE3000"} <= names


def test_skips_shell_header_and_nameless_rows():
    assert not any(p.name in ("<SHELL>", "") for p in load_plugins(FIX))
    assert len(load_plugins(FIX)) == 7


def test_instrument_flag_and_add_name():
    v = by_name(load_plugins(FIX))["Vital"]
    assert v.instrument and v.add_name == "VST3i: Vital (Vital Audio)"


def test_clap_add_name():
    assert by_name(load_plugins(FIX))["TONE3000"].add_name == "CLAP: TONE3000 (TONE3000)"


def test_dedupes_preferring_vst3():
    a = by_name(load_plugins(FIX))["AmpliTube 5"]
    assert a.format == "VST3" and a.alternates == ["VST: AmpliTube 5 (IK Multimedia)"]


def test_tags_and_vendor_from_fxtags():
    ps = by_name(load_plugins(FIX))
    assert ps["ReaComp"].reaper_tags == ["Dynamics"] and ps["IR-L Mono"].vendor == "Waves"


def test_parses_tricky_names():
    ps = by_name(load_plugins(FIX))
    assert ps["ReaStream (8ch)"].vendor == "Cockos"
    assert ps["Ünïcode, Comp"].vendor == "Tëst Co"


def test_missing_reaper_dir_returns_empty(tmp_path):
    assert load_plugins(tmp_path / "nope") == []


def test_ids_stable_and_unique():
    ids = [p.id for p in load_plugins(FIX)]
    assert ids == [p.id for p in load_plugins(FIX)] and len(set(ids)) == len(ids) and len(ids[0]) == 12


def test_malformed_lines_and_bom_are_tolerated(tmp_path):
    (tmp_path / "reaper-vstplugins64.ini").write_text(
        "﻿[vstcache]\nthis line has no equals sign\nreacomp.dll=00A9,1919247213,ReaComp (Cockos)\n",
        encoding="utf-8")
    (tmp_path / "reaper-fxtags.ini").write_text("garbage before any section\n[category]\nreacomp.dll=Dynamics\n")
    ps = load_plugins(tmp_path)
    assert [p.name for p in ps] == ["ReaComp"]
