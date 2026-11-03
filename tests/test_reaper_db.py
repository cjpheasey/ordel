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


def test_plugin_keeps_reaper_file_key():
    ps = by_name(load_plugins(FIX))
    assert ps["AmpliTube 5"].key == "AmpliTube_5.vst3"
    assert ps["IR-L Mono"].key == "WaveShell1_VST3_14.12_x64.vst3<1588611046"


def test_find_vst3_matches_reaper_key_in_subfolders(tmp_path):
    from studio_hub.reaper_db import find_vst3
    (tmp_path / "VST3" / "FabFilter" / "FabFilter Micro.vst3").mkdir(parents=True)  # bundle folder
    (tmp_path / "VST3" / "WaveShell1-VST3 14.12_x64.vst3").write_bytes(b"")          # single file
    roots = [tmp_path / "VST3", tmp_path / "missing"]
    assert find_vst3("FabFilter_Micro.vst3", roots) == tmp_path / "VST3" / "FabFilter" / "FabFilter Micro.vst3"
    assert find_vst3("WaveShell1_VST3_14.12_x64.vst3<1588611046", roots) == tmp_path / "VST3" / "WaveShell1-VST3 14.12_x64.vst3"
    assert find_vst3("Nope.vst3", roots) is None


def test_vst3_roots_read_from_reaper_ini(tmp_path, monkeypatch):
    from studio_hub.reaper_db import vst3_roots
    monkeypatch.setenv("COMMONPROGRAMFILES", str(tmp_path / "Common"))
    (tmp_path / "reaper.ini").write_text(r"[reaper]" "\n" r"vstpath64=%COMMONPROGRAMFILES%\VST3;D:\Plugins" "\n")
    roots = vst3_roots(tmp_path)
    assert tmp_path / "Common" / "VST3" in roots and Path("D:/Plugins") in roots


def test_developer_names_are_tidied_for_display():
    from studio_hub.reaper_db import tidy_developer
    assert tidy_developer("Valhalla DSP, LLC") == "Valhalla DSP"
    assert tidy_developer("Universal Audio (UADx)") == "Universal Audio"
    assert tidy_developer("iZotope, Inc.") == "iZotope"
    assert tidy_developer("Native Instruments GmbH") == "Native Instruments"
    assert tidy_developer("Plugin Alliance") == "Plugin Alliance"
    assert tidy_developer("") == ""
