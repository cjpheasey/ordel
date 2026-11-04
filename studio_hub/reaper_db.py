"""Reads the plugin list REAPER has already scanned, instead of crawling plugin folders."""
import configparser
import hashlib
import logging
import os
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
    key: str = ""  # REAPER's cache key, e.g. 'FabFilter_Micro.vst3' or 'WaveShell1_VST3_14.12_x64.vst3<1588611046'
    variant: str = "Stereo"  # this version's label, e.g. 'Mono'
    variants: list["Plugin"] = field(default_factory=list)  # the other versions shown under this one


_VARIANT = re.compile(r"^(.*\S)\s+\((mono|stereo|sc|sidechain|mono sc|mono sidechain|(\d+) out|(\d+)ch)\)$",
                      re.IGNORECASE)
_BARE_VARIANT = re.compile(r"^(.*\S)\s+(mono|stereo)$", re.IGNORECASE)  # Waves: 'CLA-76 Mono'
_LABELS = {"mono": "Mono", "stereo": "Stereo", "sc": "Sidechain", "sidechain": "Sidechain",
           "mono sc": "Mono sidechain", "mono sidechain": "Mono sidechain"}
_LABEL_ORDER = ["Stereo", "Mono", "Sidechain", "Mono sidechain"]


def variant_label(name: str) -> tuple[str, str]:
    """'FabFilter Pro-C 2 (Mono)' -> ('FabFilter Pro-C 2', 'Mono'); no recognised suffix means 'Stereo'."""
    m = _VARIANT.match(name.strip())
    if not m:
        bare = _BARE_VARIANT.match(name.strip())
        return (bare.group(1), _LABELS[bare.group(2).lower()]) if bare else (name, "Stereo")
    suffix = m.group(2).lower()
    if m.group(3):
        return m.group(1), f"{m.group(3)} outputs"
    if m.group(4):
        return m.group(1), f"{m.group(4)} channels"
    return m.group(1), _LABELS[suffix]


def _variant_rank(label: str) -> tuple[int, int]:
    if label in _LABEL_ORDER:
        return _LABEL_ORDER.index(label), 0
    return len(_LABEL_ORDER), int(label.split()[0])


def group_variants(plugins: list[Plugin]) -> list[Plugin]:
    """One plugin per set of versions (Stereo, Mono, Sidechain, multi-output), the stereo one in front."""
    groups: dict[tuple[str, str], list[tuple[str, str, Plugin]]] = {}
    for p in plugins:
        base, label = variant_label(p.name)
        groups.setdefault((base.lower(), p.vendor.lower()), []).append((base, label, p))
    out = []
    for members in groups.values():
        if len(members) == 1:
            out.append(members[0][2])  # nothing to group: keep its full name, e.g. 'Sitala (32 out)'
            continue
        members.sort(key=lambda m: _variant_rank(m[1]))
        base, label, main = members[0]
        main.name, main.variant = base, label
        main.variants = []
        for _, other_label, other in members[1:]:
            other.variant = other_label
            main.variants.append(other)
        out.append(main)
    return out


_COMPANY_SUFFIX = re.compile(r"[,\s]+(llc|inc|ltd|gmbh|co|corp|s\.?a\.?|b\.?v\.?)\.?$", re.IGNORECASE)


def tidy_developer(vendor: str) -> str:
    """Display name for a developer: 'Valhalla DSP, LLC' -> 'Valhalla DSP', 'Universal Audio (UADx)' -> 'Universal Audio'."""
    name = re.sub(r"\s*\([^()]*\)", "", vendor).strip()
    return _COMPANY_SUFFIX.sub("", name).strip() or vendor.strip()


def _norm_file(name: str) -> str:
    """REAPER's cache keys replace spaces and dashes with underscores."""
    return re.sub(r"[^a-z0-9.]", "_", name.lower())


# Where REAPER looks when the user never changed its plug-in paths.
_DEFAULT_PATHS = [r"%COMMONPROGRAMFILES%\VST3", r"%PROGRAMFILES%\VSTPlugins", r"%PROGRAMFILES%\Steinberg\VSTPlugins",
                  r"%COMMONPROGRAMFILES%\VST2", r"%COMMONPROGRAMFILES%\Steinberg\VST2"]


def plugin_roots(reaper_dir: Path) -> list[Path]:
    """Folders to look for plugin files in: the standard ones plus REAPER's own plug-in paths."""
    paths = list(_DEFAULT_PATHS)
    ini = _read_ini(Path(reaper_dir) / "reaper.ini")
    section = next((s for s in ini.sections() if s.lower() == "reaper"), None)  # REAPER writes '[reaper]'
    if section and ini.has_option(section, "vstpath64"):
        paths += [p.strip() for p in (ini.get(section, "vstpath64") or "").split(";") if p.strip()]
    out: list[Path] = []
    for p in paths:
        path = Path(os.path.expandvars(p))
        if path not in out:
            out.append(path)
    return out


def plugin_files(roots: list[Path]) -> dict[str, Path]:
    """Normalised file name -> path of every .vst3 (file or bundle folder) and VST2 .dll under the roots."""
    index: dict[str, Path] = {}
    for root in roots:
        for folder, dirs, files in os.walk(root):
            for name in dirs + files:
                if name.lower().endswith((".vst3", ".dll")):
                    index.setdefault(_norm_file(name), Path(folder) / name)
            dirs[:] = [d for d in dirs if not d.lower().endswith(".vst3")]  # don't descend into bundles
    return index


def find_plugin_file(key: str, roots: list[Path], index: dict[str, Path] | None = None) -> Path | None:
    return (index if index is not None else plugin_files(roots)).get(_norm_file(key.split("<", 1)[0]))


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
                        [t for t in (categories.get(key) or "").split("|") if t], key=key)
        dedupe = (name.lower(), vendor.lower())
        current = best.get(dedupe)
        if current is None:
            best[dedupe] = plugin
            continue
        keep, other = sorted([current, plugin], key=lambda p: FORMAT_PRIORITY[p.format])
        keep.alternates = current.alternates + plugin.alternates + [other.add_name]
        keep.reaper_tags = keep.reaper_tags or other.reaper_tags
        best[dedupe] = keep
    return sorted(group_variants(list(best.values())), key=lambda p: p.name.lower())
