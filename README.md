# Mise

<img src="studio_hub/assets/icon.png" width="96" alt="Mise icon">

A visual plugin library for REAPER. The name comes from *mise en place*: everything in its place before you start. Every plugin you own is shown as a picture of its real interface, sorted into categories, one keyboard shortcut away, and sent straight onto the selected track.

Built for mixing sessions where you remember a plugin by its face, not its name.

## Features

- **See every plugin.** Mise opens each plugin once and photographs its real interface. No web scraping, no stock images.
- **Crash-safe capture.** VST3 plugins open in a throwaway helper process, so a plugin that crashes or freezes can't take REAPER down. It's marked and skipped.
- **Sorted for you.** Plugins are grouped into EQ, Dynamics, Reverb, Delay, Saturation and more, using the categories developers declare to REAPER. Drag a plugin onto another category to correct it.
- **Browse by developer.** Switch the sidebar to Developers to see everything from Waves, FabFilter or Plugin Alliance, then narrow with one click: Waves EQs, or every developer's reverbs.
- **One shortcut away.** Press **Ctrl+Shift+Space** from anywhere, including REAPER, to show or hide Mise.
- **Straight to the track.** Double-click a plugin, or press Enter, and it's added to the selected REAPER track with its window open.
- **Three themes.** Graphite, Light and Glass, each with colour-coded categories.
- **Keyboard first.** Type to search, arrow keys to move, Enter to add, F to favourite, Esc to clear or hide.

## How it works

```
REAPER's plugin scan ──► Mise reads reaper-vstplugins64.ini, reaper-clap-win64.ini, reaper-fxtags.ini
                         (names, makers, formats, developer categories)

Mise  ◄──files──►  studio_hub_bridge.lua running inside REAPER
                   ADD: put a plugin on the selected track
                   CAPTURE_*: open VST2/CLAP plugins in a temporary project tab to photograph them

Mise ──► Mise.exe --capture-helper <plugin.vst3>   (pedalboard, one throwaway process per VST3 plugin)
```

- **Engine:** Python 3.13. It reads REAPER's own plugin cache instead of crawling plugin folders, so the list matches what REAPER can load.
- **Interface:** HTML, CSS and vanilla JavaScript in a frameless [pywebview](https://pywebview.flowrl.com/) (WebView2) window, served by a local-only HTTP server that also exposes a small JSON API.
- **REAPER bridge:** a Lua ReaScript started from `Scripts/__startup.lua`. Mise adds one line to that file and never overwrites anything else in it. Commands pass through two text files in `%APPDATA%\StudioHub\bridge`.
- **Capture:** VST3 plugins open in a helper process (Mise itself, using [pedalboard](https://github.com/spotify/pedalboard)) inside a kill-on-close Windows job, so a crash or hang only takes the helper down. VST2, CLAP and VST3s the helper can't load open in a temporary REAPER tab instead. Windows are drawn with `PrintWindow`, falling back to a screen grab for GPU-drawn plugins, then checked for blank frames.

Your data stays on your machine: favourites, categories and pictures live in `%APPDATA%\StudioHub`.

## Install

Download `Mise-Setup.exe` from Releases and run it. On first launch Mise finds your plugins, connects to REAPER, and offers to capture pictures.

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

This produces `dist\Mise\Mise.exe`, and also `dist\Mise-Setup.exe` if [Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed.

## Roadmap

- Other DAWs (Ableton Live, Bitwig)
- macOS support
- Saved plugin chains

## License

MIT
