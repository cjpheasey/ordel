# Ordel

<img src="brand/final/ordel-lockup-horizontal.svg" width="320" alt="Ordel">

A visual plugin library for REAPER. The name comes from *order*: every plugin in its place. Every plugin you own is shown as a picture of its real interface, sorted into categories, one keyboard shortcut away, and sent straight onto the selected track.

Built for mixing sessions where you remember a plugin by its face, not its name.

## Features

- **See every plugin.** Ordel opens each plugin once and photographs its real interface. No web scraping, no stock images.
- **Crash-safe capture.** Plugins are photographed in a throwaway helper process or in REAPER's own separate plugin process, so one that crashes or freezes can't take REAPER down. Anything riskier waits until your work is saved, and capture pauses while you're playing or recording.
- **One card per plugin.** Stereo, Mono, Sidechain and multi-output versions show as one card with a switch underneath; each version keeps its own picture.
- **Sorted for you.** Plugins are grouped into EQ, Dynamics, Reverb, Delay, Saturation and more, using the categories developers declare to REAPER. Drag a plugin onto another category to correct it.
- **Browse by developer.** Switch the sidebar to Developers to see everything from Waves, FabFilter or Plugin Alliance, then narrow with one click: Waves EQs, or every developer's reverbs.
- **One shortcut away.** Press **Ctrl+Shift+Space** from anywhere, including REAPER, to show or hide Ordel.
- **Straight to the track.** Click the + on a card, double-click it, or press Enter, and it's added to the selected REAPER track with its window open.
- **Chains in one click.** Save the plugins on a REAPER track (settings included) as a chain, or build one in Ordel, then put it on any number of tracks, or on a new return track for your sends. Chains you saved in REAPER show up too.
- **New plugins noticed.** When REAPER finds plugins Ordel hasn't seen, a quiet line offers to capture their pictures.
- **Make it yours.** Four themes (Ordel, Graphite, Light and Glass), seven accent colours, fit or fill pictures, comfortable or compact layouts, rounded or square corners, and adjustable picture size.
- **A quick tour.** The first time you open Ordel, a short tour shows you around, and a **?** on each page explains it. Replay the tour any time from Settings.
- **Keyboard first.** Type to search, arrow keys to move, Enter to add, F to favourite, Esc to clear or hide.

## How it works

```
REAPER's plugin scan ──► Ordel reads reaper-vstplugins64.ini, reaper-clap-win64.ini, reaper-fxtags.ini
                         (names, makers, formats, developer categories)

Ordel  ◄──files──►  studio_hub_bridge.lua running inside REAPER
                   ADD: put a plugin on the selected track
                   CAPTURE_*: open VST2/CLAP plugins in a temporary project tab to photograph them

Ordel ──► Ordel.exe --capture-helper <plugin.vst3>   (pedalboard, one throwaway process per VST3 plugin)
```

- **Engine:** Python 3.13. It reads REAPER's own plugin cache instead of crawling plugin folders, so the list matches what REAPER can load.
- **Interface:** HTML, CSS and vanilla JavaScript in a frameless [pywebview](https://pywebview.flowrl.com/) (WebView2) window, served by a local-only HTTP server that also exposes a small JSON API.
- **REAPER bridge:** a Lua ReaScript started from `Scripts/__startup.lua`. Ordel adds one line to that file and never overwrites anything else in it. Commands pass through two text files in `%APPDATA%\StudioHub\bridge`.
- **Capture:** VST3 plugins open in a helper process (Ordel itself, using [pedalboard](https://github.com/spotify/pedalboard)) inside a kill-on-close Windows job, so a crash or hang only takes the helper down. Everything else opens in a temporary REAPER tab, switched for the moment into REAPER's "dedicated process" plugin bridging (and switched back after), so a crash only takes that process down; CLAP plugins, which REAPER can't bridge, wait until your work is saved. Windows are drawn with `PrintWindow`, falling back to a screen grab for GPU-drawn plugins, then checked for blank frames.

Your data stays on your machine: favourites, categories and pictures live in `%APPDATA%\StudioHub`.

## Install

Download `Ordel-Setup.exe` from [Releases](../../releases) and run it. It installs for your Windows user (no administrator rights needed). On first launch Ordel finds your plugins, connects to REAPER, and offers to capture pictures.

The installer isn't code-signed yet, so Windows may say **"Windows protected your PC"**. Click **More info**, then **Run anyway**.

Uninstalling removes Ordel's script from REAPER and asks whether to keep your library.

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

This produces `dist\Ordel\Ordel.exe`, and also `dist\Ordel-Setup.exe` if [Inno Setup](https://jrsoftware.org/isinfo.php) 6 or 7 is installed.

## Roadmap

- Notes and tags on plugins
- A "never used" view
- Code-signed installer

## Licence

Copyright © 2026 Charlie Pheasey. All rights reserved. The source is public to read; the app is free to download and use. See [LICENSE](LICENSE).
