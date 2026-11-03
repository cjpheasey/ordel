"""Where Mise reads REAPER's files and keeps its own data."""
import os
import sys
from pathlib import Path


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))


def reaper_dir() -> Path:
    return Path(os.environ.get("STUDIOHUB_REAPER_DIR") or _appdata() / "REAPER")


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
