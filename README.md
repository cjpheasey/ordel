# Studio Hub

A visual plugin library for REAPER. Every plugin you own is shown as a picture of its real interface, sorted into categories, one keyboard shortcut away, and sent straight onto the selected track.

Built for mixing sessions where you remember a plugin by its face, not its name.

## Features

- **See every plugin.** Studio Hub opens each plugin once in a separate REAPER tab and photographs its interface. No web scraping, no stock images.
- **Sorted for you.** Plugins are grouped into EQ, Dynamics, Reverb, Delay, Saturation and more, using the categories developers declare to REAPER. Drag a plugin onto another category to correct it.
- **One shortcut away.** Press **Ctrl+Shift+Space** from anywhere, including REAPER, to show or hide Studio Hub.
- **Straight to the track.** Double-click a plugin, or press Enter, and it's added to the selected REAPER track with its window open.
- **Three themes.** Graphite, Light and Glass, each with colour-coded categories.
- **Keyboard first.** Type to search, arrow keys to move, Enter to add, F to favourite, Esc to clear or hide.

## How it works

```
REAPER's plugin scan ──► Studio Hub reads reaper-vstplugins64.ini, reaper-clap-win64.ini, reaper-fxtags.ini
                         (names, makers, formats, developer categories)

Studio Hub  ◄──files──►  studio_hub_bridge.lua running inside REAPER
                         ADD: put a plugin on the selected track
                         CAPTURE_*: open plugins in a temporary project tab to photograph them
```

- **Engine:** Python 3.13. It reads REAPER's own plugin cache instead of crawling plugin folders, so the list matches what REAPER can load.
- **Interface:** HTML, CSS and vanilla JavaScript in a frameless [pywebview](https://pywebview.flowrl.com/) (WebView2) window, served by a local-only HTTP server that also exposes a small JSON API.
- **REAPER bridge:** a Lua ReaScript started from `Scripts/__startup.lua`. Studio Hub adds one line to that file and never overwrites anything else in it. Commands pass through two text files in `%APPDATA%\StudioHub\bridge`.
- **Capture:** each plugin's floating window is found with Win32 APIs, grabbed with `mss`, and checked for blank frames. Plugins that won't open are marked so you can retake them or use your own image.

Your data stays on your machine: favourites, categories and pictures live in `%APPDATA%\StudioHub`.

## Install

Download `StudioHub-Setup.exe` from Releases and run it. On first launch Studio Hub finds your plugins, connects to REAPER, and offers to capture pictures.

Requires Windows 10 or 11, REAPER (x64), and the Microsoft Edge WebView2 runtime, which ships with Windows 11.

## Run from source

```powershell
py -3.13 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m studio_hub
```

Run the tests with `.venv\Scripts\pytest`. To see the interface in a normal browser, run `.venv\Scripts\python -m studio_hub.devserver 8765` and open the printed address.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

This produces `dist\StudioHub\StudioHub.exe`, and also `dist\StudioHub-Setup.exe` if [Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed.

## Roadmap

- Other DAWs (Ableton Live, Bitwig)
- macOS support
- Saved plugin chains

## License

MIT
