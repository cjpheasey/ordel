"""How many of your REAPER projects use each plugin, read from the .rpp files themselves."""
import os
import re
from pathlib import Path

_FX = re.compile(r'^\s*<(VST|CLAP|DX|AU|LV2)\s+"([^"]+)"')
_RECENT = re.compile(r"^recent\d+=(.+)$", re.IGNORECASE)


def project_files(reaper_dir: Path, folder: Path | None) -> list[Path]:
    """Every project in the chosen folder (any depth), plus REAPER's recent projects, each once."""
    found: dict[str, Path] = {}
    ini = Path(reaper_dir) / "reaper.ini"
    if ini.is_file():
        for line in ini.read_text(encoding="utf-8", errors="replace").splitlines():
            if (m := _RECENT.match(line.strip())) and Path(m.group(1)).is_file():
                found.setdefault(os.path.normcase(m.group(1)), Path(m.group(1)))
    if folder and Path(folder).is_dir():
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d.lower() != "backups"]  # REAPER's timestamped backup copies
            for name in files:
                if name.lower().endswith(".rpp"):
                    found.setdefault(os.path.normcase(os.path.join(root, name)), Path(root) / name)
    return list(found.values())


def count_usage(projects: list[Path], key=lambda name: name) -> dict:
    """How many projects use each plugin. key turns REAPER's name ('VST3: Pro-Q 3 (FabFilter)') into what
    to count by (e.g. Ordel's card, so Mono and Stereo count a project once); None skips it."""
    counts: dict = {}
    for path in projects:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        used = {key(m.group(2)) for line in text.splitlines() if (m := _FX.match(line))}
        for k in used - {None}:
            counts[k] = counts.get(k, 0) + 1
    return counts
