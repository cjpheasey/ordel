"""Reads the plugin list REAPER has already scanned, instead of crawling plugin folders."""
import configparser
import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)
FORMAT_PRIORITY ={"VST3": 0, "CLAP": 1, "VST": 2}
_SUFFIX = re.compile(r"^\d+\s*(out|ch)$", re.IGNORECASE)
_PARENS = re.compile(r"\(([^()]*)\)")


@dataclass
class Plugin:
    id: str
    name: str
    vendor: str
    format: str
    instrument: bool
    add_name: str
    reaper_tags: list[str] = field(default_factory=list)
    alternates: list[str] = field(default_factory=list)


def _read_ini(path: Path) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(strict=False, interpolation=None, delimiters=("=",), allow_no_value=True)
    parser.optionxform = str
    if not path.is_file():
        return parser
    # REAPER owns these files; skip anything before the first section rather than refusing the whole file.
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    first = text.find("[")
    try:
        parser.read_string(text[first:] if first > 0 else text)
    except configparser.Error:
        log.warning("could not read %s", path, exc_info=True)
    return parser


def _split_display(display: str, developer: str | None) -> tuple[str, str]:
    """'ReaStream (Cockos) (8ch)' -> ('ReaStream (8ch)', 'Cockos')."""
    vendor = developer
    if not vendor:
        groups = [g for g in _PARENS.findall(display) if not _SUFFIX.match(g.strip())]
        vendor = groups[-1].strip() if groups else ""
    name = display.replace(f" ({vendor})", "", 1) if vendor else display
    return name.strip(), vendor


def _entries(reaper_dir: Path):
    """Yield (key, format, instrument, display) for every scanned plugin."""
    vst = _read_ini(reaper_dir / "reaper-vstplugins64.ini")
    if vst.has_section("vstcache"):
        for key, value in vst.items("vstcache"):
            parts = (value or "").split(",", 2)
            if len(parts) < 3 or not parts[2].strip() or parts[2].strip() == "<SHELL>":
                continue
            display = parts[2].strip()
            instrument = display.endswith("!!!VSTi")
            file = key.split("<", 1)[0].lower()
            fmt = "VST3" if file.endswith(".vst3") else "VST"
            yield key, fmt, instrument, display.removesuffix("!!!VSTi").strip()

    clap = _read_ini(reaper_dir / "reaper-clap-win64.ini")
    for section in clap.sections():
        for key, value in clap.items(section):
            flags, _, display = (value or "").partition("|")
            if key == "_" or not display.strip():
                continue
            yield section, "CLAP", flags.strip() == "1", display.strip()


def load_plugins(reaper_dir: Path) -> list[Plugin]:
    tags = _read_ini(reaper_dir / "reaper-fxtags.ini")
    developers = dict(tags.items("developer")) if tags.has_section("developer") else {}
    categories = dict(tags.items("category")) if tags.has_section("category") else {}

    best: dict[tuple[str, str], Plugin] = {}
    for key, fmt, instrument, display in _entries(reaper_dir):
        name, vendor = _split_display(display, developers.get(key))
        add_name = f"{fmt}{'i' if instrument else ''}: {display}"
        uid = hashlib.sha1(f"{name}|{vendor}".lower().encode()).hexdigest()[:12]
        plugin = Plugin(uid, name, vendor, fmt, instrument, add_name,
                        [t for t in (categories.get(key) or "").split("|") if t])
        dedupe = (name.lower(), vendor.lower())
        current = best.get(dedupe)
        if current is None:
            best[dedupe] = plugin
            continue
        keep, other = sorted([current, plugin], key=lambda p: FORMAT_PRIORITY[p.format])
        keep.alternates = current.alternates + plugin.alternates + [other.add_name]
        keep.reaper_tags = keep.reaper_tags or other.reaper_tags
        best[dedupe] = keep
    return sorted(best.values(), key=lambda p: p.name.lower())
