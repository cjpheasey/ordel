# PyInstaller build: one folder, no console window.
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "studio_hub" / "ui"), "studio_hub/ui"),
        (str(ROOT / "studio_hub" / "reaper"), "studio_hub/reaper"),
        (str(ROOT / "studio_hub" / "assets"), "studio_hub/assets"),
    ],
    hiddenimports=["pystray._win32", "webview.platforms.edgechromium", "webview.platforms.winforms"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Mise", console=False,
          icon=str(ROOT / "studio_hub" / "assets" / "icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="Mise")
