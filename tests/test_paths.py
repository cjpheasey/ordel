from pathlib import Path

import pytest

from studio_hub import paths


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.delenv("STUDIOHUB_REAPER_DIR", raising=False)
    monkeypatch.setenv("STUDIOHUB_DATA_DIR", str(tmp_path / "data"))
    running = {"exe": None}
    monkeypatch.setattr("studio_hub.capture.running_reaper_exe", lambda: running["exe"])
    return tmp_path, running


def portable(tmp_path) -> Path:
    folder = tmp_path / "Music" / "REAPER Portable"
    folder.mkdir(parents=True)
    (folder / "reaper.exe").write_bytes(b"")
    (folder / "reaper.ini").write_text("[reaper]\n")
    return folder


def test_standard_install_uses_appdata(home):
    tmp_path, running = home
    (tmp_path / "Roaming" / "REAPER").mkdir(parents=True)
    (tmp_path / "Roaming" / "REAPER" / "reaper.ini").write_text("[reaper]\n")
    running["exe"] = portable(tmp_path) / "reaper.exe"  # a standard install wins
    assert paths.reaper_dir() == tmp_path / "Roaming" / "REAPER"


def test_portable_reaper_is_found_while_running_and_remembered(home):
    tmp_path, running = home
    folder = portable(tmp_path)
    running["exe"] = folder / "reaper.exe"
    assert paths.reaper_dir() == folder
    running["exe"] = None  # next start, REAPER closed
    assert paths.reaper_dir() == folder


def test_nothing_found_falls_back_to_appdata(home):
    tmp_path, _ = home
    assert paths.reaper_dir() == tmp_path / "Roaming" / "REAPER"


def test_explicit_folder_wins(home, monkeypatch):
    tmp_path, _ = home
    monkeypatch.setenv("STUDIOHUB_REAPER_DIR", str(tmp_path / "mine"))
    assert paths.reaper_dir() == tmp_path / "mine"
