"""REAPER's saved FX chains (.RfxChain files): finding them, reading which plugins they hold, naming new ones."""
import re
from pathlib import Path

ORDEL_FOLDER = "Ordel"  # chains saved through Ordel live in FXChains\Ordel\
_FX_LINE = re.compile(r'^\s*<(VST|CLAP|JS|DX|AU|LV2)\s+(?:"([^"]*)"|(\S+))')  # quoted only if it has spaces
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def chains_dir(reaper_dir: Path) -> Path:
    return Path(reaper_dir) / "FXChains"


def parse_chain(path: Path) -> list[str]:
    """The plugins in a chain, in order, by the name REAPER shows (e.g. 'VST3: Pro-Q 3 (FabFilter)')."""
    try:
        text = Path(path).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []
    return [m.group(2) if m.group(2) is not None else m.group(3)
            for line in text.splitlines() if (m := _FX_LINE.match(line))]


def chain_files(reaper_dir: Path) -> dict[str, Path]:
    """'file:<path inside FXChains>' -> path, for every saved chain."""
    root = chains_dir(reaper_dir)
    if not root.is_dir():
        return {}
    return {"file:" + p.relative_to(root).as_posix(): p
            for p in sorted(root.rglob("*")) if p.is_file() and p.suffix.lower() == ".rfxchain"}


def safe_name(name: str) -> str:
    cleaned = " ".join(_UNSAFE.sub("", name).split())[:80].strip(" .")
    return cleaned or "Chain"


def new_chain_path(reaper_dir: Path, name: str) -> Path:
    folder = chains_dir(reaper_dir) / ORDEL_FOLDER
    base = safe_name(name)
    path, n = folder / f"{base}.RfxChain", 2
    while path.exists():
        path, n = folder / f"{base} {n}.RfxChain", n + 1
    return path


def send_to_recycle_bin(path: Path) -> None:
    from win32com.shell import shell, shellcon

    flags = shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION | shellcon.FOF_SILENT | shellcon.FOF_NOERRORUI
    result, aborted = shell.SHFileOperation((0, shellcon.FO_DELETE, str(path), None, flags, None, None))
    if result or aborted:
        raise OSError(f"couldn't move {path.name} to the Recycle Bin ({result})")
