from studio_hub.usage import count_usage, project_files

SONG = ('<REAPER_PROJECT 0.1\n<TRACK\n<FXCHAIN\n<VST "VST3: Pro-Q 3 (FabFilter)" "FabFilter Pro-Q 3.vst3" 0\n>\n'
        '<VST "VST3: Pro-Q 3 (FabFilter)" "FabFilter Pro-Q 3.vst3" 0\n>\n<JS utility/volume ""\n>\n>\n>\n'
        '<TRACK\n<FXCHAIN_REC\n<VST "VST: ReaComp (Cockos)" reacomp.dll 0\n>\n>\n>\n>\n')


def test_counts_how_many_projects_use_each_plugin(tmp_path):
    a, b = tmp_path / "a.rpp", tmp_path / "b.rpp"
    a.write_text(SONG)
    b.write_text('<REAPER_PROJECT 0.1\n<VST "VST3: Pro-Q 3 (FabFilter)" x 0\n>\n<CLAP "CLAP: Vital (Vital Audio)" v\n>\n>\n')
    counts = count_usage([a, b, tmp_path / "gone.rpp"])
    # Pro-Q 3 twice in one project still counts that project once; input FX count too; JS effects aren't plugins
    assert counts == {"VST3: Pro-Q 3 (FabFilter)": 2, "VST: ReaComp (Cockos)": 1, "CLAP: Vital (Vital Audio)": 1}


def test_project_files_come_from_the_folder_and_reapers_recent_list(tmp_path):
    folder = tmp_path / "Projects"
    (folder / "Song" / "Backups").mkdir(parents=True)
    (folder / "Song" / "Song.rpp").write_text("x")
    (folder / "Song" / "Song.rpp-bak").write_text("x")              # REAPER's backups don't count
    (folder / "Song" / "Backups" / "Song-2026.rpp").write_text("x")  # nor its timestamped backups folder
    loose = tmp_path / "Loose.rpp"
    loose.write_text("x")
    reaper = tmp_path / "reaper"
    reaper.mkdir()
    (reaper / "reaper.ini").write_text(f"[REAPER]\nrecent01={loose}\nrecent02={folder / 'Song' / 'Song.rpp'}\n"
                                      f"recent03={tmp_path / 'deleted.rpp'}\n")
    found = project_files(reaper, folder)
    assert sorted(p.name for p in found) == ["Loose.rpp", "Song.rpp"]  # each project once
    assert [p.name for p in project_files(reaper, None)] == ["Loose.rpp", "Song.rpp"]  # no folder chosen yet


def test_versions_of_one_plugin_count_a_project_once(tmp_path):
    p = tmp_path / "mix.rpp"
    p.write_text('<VST "VST3: SSLChannel Mono (Waves)" x 0\n>\n<VST "VST3: SSLChannel Stereo (Waves)" x 0\n>\n')
    card = {"VST3: SSLChannel Mono (Waves)": "ssl", "VST3: SSLChannel Stereo (Waves)": "ssl"}.get
    assert count_usage([p], key=card) == {"ssl": 1}
