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


def test_find_plugin_file_matches_reaper_key_in_subfolders(tmp_path):
    from studio_hub.reaper_db import find_plugin_file as find_vst3
    (tmp_path / "VST3" / "FabFilter" / "FabFilter Micro.vst3").mkdir(parents=True)  # bundle folder
    (tmp_path / "VST3" / "WaveShell1-VST3 14.12_x64.vst3").write_bytes(b"")          # single file
    (tmp_path / "VST3" / "Ampeg SVTVR Classic.dll").write_bytes(b"")                # VST2
    roots = [tmp_path / "VST3", tmp_path / "missing"]
    assert find_vst3("FabFilter_Micro.vst3", roots) == tmp_path / "VST3" / "FabFilter" / "FabFilter Micro.vst3"
    assert find_vst3("WaveShell1_VST3_14.12_x64.vst3<1588611046", roots) == tmp_path / "VST3" / "WaveShell1-VST3 14.12_x64.vst3"
    assert find_vst3("Ampeg_SVTVR_Classic.dll", roots) == tmp_path / "VST3" / "Ampeg SVTVR Classic.dll"
    assert find_vst3("Nope.vst3", roots) is None


def test_plugin_roots_read_from_reaper_ini(tmp_path, monkeypatch):
    from studio_hub.reaper_db import plugin_roots as vst3_roots
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


def make(name, vendor="FabFilter", fmt="VST3"):
    from studio_hub.reaper_db import Plugin
    return Plugin(f"id-{name}", name, vendor, fmt, False, f"{fmt}: {name} ({vendor})")


def test_variant_label():
    from studio_hub.reaper_db import variant_label
    assert variant_label("FabFilter Pro-C 2 (Mono)") == ("FabFilter Pro-C 2", "Mono")
    assert variant_label("FabFilter Volcano 2 (Mono SC)") == ("FabFilter Volcano 2", "Mono sidechain")
    assert variant_label("FabFilter Timeless 2 (SC)") == ("FabFilter Timeless 2", "Sidechain")
    assert variant_label("Sitala (32 out)") == ("Sitala", "32 outputs")
    assert variant_label("ReaStream (8ch)") == ("ReaStream", "8 channels")
    assert variant_label("FabFilter Pro-Q 3") == ("FabFilter Pro-Q 3", "Stereo")
    assert variant_label("CLA-76 Mono") == ("CLA-76", "Mono")  # Waves names versions without brackets
    assert variant_label("C1 comp Stereo") == ("C1 comp", "Stereo")


def test_waves_style_versions_are_grouped_but_a_lone_one_keeps_its_name():
    from studio_hub.reaper_db import group_variants
    g, = group_variants([make("CLA-76 Mono", "Waves"), make("CLA-76 Stereo", "Waves")])
    assert g.name == "CLA-76" and g.variant == "Stereo" and [v.variant for v in g.variants] == ["Mono"]
    lone, = group_variants([make("IR-L Mono", "Waves")])
    assert lone.name == "IR-L Mono" and lone.variants == []


def test_versions_are_grouped_under_the_stereo_one():
    from studio_hub.reaper_db import group_variants
    plugins = [make("FabFilter Pro-C 2 (Mono)"), make("FabFilter Pro-C 2"), make("FabFilter Pro-Q 3"),
               make("FabFilter Pro-Q 4")]
    groups = group_variants(plugins)
    assert sorted(g.name for g in groups) == ["FabFilter Pro-C 2", "FabFilter Pro-Q 3", "FabFilter Pro-Q 4"]
    proc = next(g for g in groups if g.name == "FabFilter Pro-C 2")
    assert proc.variant == "Stereo" and [v.variant for v in proc.variants] == ["Mono"]
    assert proc.id == "id-FabFilter Pro-C 2"  # existing data stays attached
    assert next(g for g in groups if g.name == "FabFilter Pro-Q 3").variants == []


def test_group_without_a_plain_version_is_named_by_its_base():
    from studio_hub.reaper_db import group_variants
    g, = group_variants([make("FabFilter Volcano 2 (SC)"), make("FabFilter Volcano 2 (Mono)")])
    assert g.name == "FabFilter Volcano 2" and g.variant == "Mono" and [v.variant for v in g.variants] == ["Sidechain"]


def test_single_variant_is_not_grouped():
    from studio_hub.reaper_db import group_variants
    g, = group_variants([make("Creepy Piano 3 Lite (32 out)", "ESL", "VST")])
    assert g.name == "Creepy Piano 3 Lite (32 out)" and g.variants == []


def test_same_name_different_developer_is_not_grouped():
    from studio_hub.reaper_db import group_variants
    groups = group_variants([make("Comp", "Acme"), make("Comp (Mono)", "Other Co")])
    assert sorted(g.name for g in groups) == ["Comp", "Comp (Mono)"] and all(not g.variants for g in groups)
