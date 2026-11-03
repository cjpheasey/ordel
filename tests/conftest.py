import pytest


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIOHUB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STUDIOHUB_REAPER_DIR", str(tmp_path / "reaper"))
