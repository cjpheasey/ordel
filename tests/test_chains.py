from studio_hub.chains import chain_files, new_chain_path, parse_chain, safe_name

TWO_FX = ('BYPASS 0 0 0\n<VST "VST: ReaEQ (Cockos)" reaeq.dll 0 "" 1919247729<5653>\nZXE=\n>\nFLOATPOS 0 0 0 0\n'
          'FXID {1}\nWAK 0 0\nBYPASS 0 0 0\n<VST "VST3: FabFilter Pro-Q 3 (FabFilter)" "FabFilter Pro-Q 3.vst3" 0 "" 1{2}\n'
          'AAA=\n>\n')


def test_parse_chain_lists_plugins_in_order(tmp_path):
    f = tmp_path / "Vocal.RfxChain"
    f.write_text(TWO_FX)
    assert parse_chain(f) == ["VST: ReaEQ (Cockos)", "VST3: FabFilter Pro-Q 3 (FabFilter)"]


def test_parse_tolerates_js_unknown_and_bad_bytes(tmp_path):
    f = tmp_path / "Odd.RfxChain"
    f.write_bytes(b'BYPASS 0 0 0\n<JS utility/volume ""\n0 - - -\n>\n\xff\xfe garbage\n'
                  b'BYPASS 0 0 0\n<JS "my scripts/soft clip" ""\n>\n'
                  b'BYPASS 0 0 0\n<CLAP "CLAP: Nope (X)" com.x.nope\n>\n')
    # REAPER only quotes names that contain spaces
    assert parse_chain(f) == ["utility/volume", "my scripts/soft clip", "CLAP: Nope (X)"]


def test_parse_missing_file_is_empty(tmp_path):
    assert parse_chain(tmp_path / "gone.RfxChain") == []


def test_chain_files_finds_subfolders_and_ignores_other_files(tmp_path):
    root = tmp_path / "FXChains"
    (root / "Ordel").mkdir(parents=True)
    (root / "Drums").mkdir()
    (root / "Ordel" / "Vocal.RfxChain").write_text(TWO_FX)
    (root / "Drums" / "Kit.rfxchain").write_text(TWO_FX)
    (root / "notes.txt").write_text("x")
    assert sorted(chain_files(tmp_path)) == ["file:Drums/Kit.rfxchain", "file:Ordel/Vocal.RfxChain"]
    assert chain_files(tmp_path / "missing") == {}


def test_new_chain_path_is_safe_and_unique(tmp_path):
    first = new_chain_path(tmp_path, 'Vox: "lead"')
    assert first == tmp_path / "FXChains" / "Ordel" / "Vox lead.RfxChain"
    first.parent.mkdir(parents=True)
    first.write_text("")
    assert new_chain_path(tmp_path, 'Vox: "lead"').name == "Vox lead 2.RfxChain"
    assert safe_name("  ???  ") == "Chain" and len(safe_name("x" * 200)) == 80
