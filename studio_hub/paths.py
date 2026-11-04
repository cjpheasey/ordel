"""Where Ordel reads REAPER's files and keeps its own data."""
import os
import sys
from pathlib import Path


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))


def reaper_dir() -> Path:
    """REAPER's resource folder: the standard one in AppData, else a portable REAPER's own folder."""
    if os.environ.get("STUDIOHUB_REAPER_DIR"):
        return Path(os.environ["STUDIOHUB_REAPER_DIR"])
    standard = _appdata() / "REAPER"
    if (standard / "reaper.ini").is_file():
        return standard
    from .capture import running_reaper_exe

    remembered = data_dir() / "reaper_dir.txt"  # so a portable REAPER is found even while it's closed
    exe = running_reaper_exe()
    if exe and (exe.parent / "reaper.ini").is_file():
        remembered.write_text(str(exe.parent), encoding="utf-8")
        return exe.parent
    if remembered.is_file():
        folder = Path(remembered.read_text(encoding="utf-8").strip())
        if (folder / "reaper.ini").is_file():
            return folder
    return standard


def data_dir() -> Path:
    path = Path(os.environ.get("STUDIOHUB_DATA_DIR") or _appdata() / "StudioHub")  # folder name kept from before the rename, so existing libraries carry over
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshots_dir() -> Path:
    path = data_dir() / "snapshots"
    path.mkdir(exist_ok=True)
    return path


def bridge_dir() -> Path:
    path = data_dir() / "bridge"
    path.mkdir(exist_ok=True)
    return path


def resource(rel: str) -> Path:
    """Bundled file inside the package (works from source and from a PyInstaller build)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "studio_hub" / rel
