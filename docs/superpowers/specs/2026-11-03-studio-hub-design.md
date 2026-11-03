# Studio Hub — Design

**Date:** 2026-11-03 · **Status:** approved in conversation, ready to plan

## Why

During mixing sessions the owner (a mixing engineer working in REAPER) scrolls a long, text-only plugin list to find what they need. They often remember a plugin by its *face*, not its name, and end up opening plugins one by one. Studio Hub is a visual plugin library: every plugin shown as a picture of its real interface, sorted into categories, summoned with a keyboard shortcut, and sent straight onto the selected REAPER track.

## Goals

1. **Recognise by sight.** Every plugin has a real screenshot of its UI, captured automatically.
2. **Sort by category.** Standard types (EQ, Dynamics, Reverb, …) with a colour tag each; the user can correct any plugin's category.
3. **Instant in a session.** A global shortcut toggles the window over REAPER. Double-click / Enter adds the plugin to REAPER's selected track and opens its window.
4. **Professional product feel.** It must not look or behave "vibe-coded" (see Quality bar). This is the anti-goal that outranks features.
5. **Shareable.** Clean GitHub repo with README and real screenshots (owner's CV), and a Windows installer other REAPER users can run without Python.

## Non-goals (v1)

macOS/Linux; DAWs other than REAPER; preset browsing; saving plugin chains; auto-update; cloud sync; web image scraping (replaced by real capture). The old `main.py` is discarded entirely (owner's permission).

## Decided by the owner

- **Layout:** library window (Apple Music / Photos style) — sidebar of Library + Categories, gallery of plugin pictures, search on top. Not a Spotlight-style finder.
- **Themes:** three, user-selectable in Settings: **Graphite** (dark), **Light**, **Glass** (dark, translucent/frosted panels, soft colour wash). Category colour tags appear in **all** themes.
- **Categories:** standard types are enough; no custom groupings.
- **Summon:** global keyboard shortcut.
- **DAW:** REAPER only for now; REAPER is assumed present.
- **Tools:** left to the builder (see below).

## Decided by the builder (Claude's calls — owner may override)

- **Stack:** Python 3.13 engine; UI is HTML/CSS/vanilla JS shown in a **pywebview** (WebView2) frameless window. No JS build step.
- **One transport:** Python runs a stdlib `ThreadingHTTPServer` on `127.0.0.1:<random port>` serving the UI, snapshot images, and a small JSON API (`/api/...`). pywebview just displays that URL. This lets the real UI be tested in a normal browser with Playwright against the real backend.
- **Plugin list comes from REAPER, not a folder crawl.** REAPER already scanned everything. Read from `%APPDATA%\REAPER\`:
  - `reaper-vstplugins64.ini` `[vstcache]`: `key=hash,uid{guid,Name (Vendor)[!!!VSTi]`. Key is the file name (spaces→underscores) or `file<shellid` for shell sub-plugins (Waves). Skip `<SHELL>` rows and rows with no name. `!!!VSTi` ⇒ instrument. Split the value with `split(',', 2)`.
  - `reaper-clap-win64.ini`: `[file.clap]` sections with `id=flags|Name (Vendor)`.
  - `reaper-fxtags.ini` `[developer]` and `[category]` keyed the same way as vstcache. Categories may be `A|B` — first is primary.
  - Format from extension: `.vst3` → VST3, `.dll` → VST, `.clap` → CLAP (instrument variants VST3i/VSTi/CLAPi).
  - **Dedupe** one card per `(name, vendor)`; prefer VST3 > CLAP > VST, keep the others as alternates.
  - Plugins on disk that REAPER hasn't scanned are out of scope (UI tip: "Rescan in REAPER, then refresh").
- **Standard categories + colours** (Apple system colours), mapped from REAPER's tags:
  EQ (green) · Dynamics (orange — compressors, limiters, gates) · Reverb (cyan) · Delay (purple) · Modulation (pink) · Saturation (red — "Distortion") · Filter (teal) · Pitch & Tuning (yellow) · Spatial (indigo — Surround, Spatial, Room) · Channel Strip (brown) · Mastering (gold) · Restoration (mint) · Utility & Analysis (grey — Analyzer, Tools, Analysis, External, MIDI, Network) · Instruments (blue — Synth, Sampler, any instrument) · Amp & Guitar (orange-red) · Uncategorised (grey, dashed). Unknown REAPER tags fall back to a keyword guess on the name, then Uncategorised. User overrides always win.
- **REAPER bridge:** a Lua ReaScript (`studio_hub_bridge.lua`) runs as a `defer` loop inside REAPER, auto-started via `Scripts\__startup.lua` (Studio Hub appends one guarded line; never overwrites the user's file). IPC is plain files in `%APPDATA%\StudioHub\bridge\`:
  - Studio Hub writes `command.txt` atomically (temp file + rename): `id\tVERB\targ`.
  - Lua replies in `response.txt`: `id\tOK|ERR\tdetail`, and touches `heartbeat.txt` every second (connected = heartbeat < 3 s old).
  - Verbs: `ADD name` (insert on first selected track, float its window; `ERR NO_TRACK` if none) · `CAPTURE_BEGIN` (open a new project tab) · `CAPTURE_OPEN name` (new track in that tab, add FX, float window) · `CAPTURE_CLOSE` (delete that track) · `CAPTURE_END` (save the tab to a temp path so no save prompt, then close it). The user's own project is never touched by capture.
  - FX added by REAPER's add-name, e.g. `VST3: AmpliTube 5 (IK Multimedia)`, `VST3i: Vital (Vital Audio)`, `CLAP: …`, `VST: …`.
- **Capture:** Studio Hub drives the bridge one plugin at a time: open → find the floating window among `reaper.exe` top-level windows whose title contains the plugin name (pywin32) → bring to front → wait for it to stop changing (≈1.5 s, max 8 s) → grab its rect with `mss` → save PNG to `%APPDATA%\StudioHub\snapshots\<id>.png` → close. Failures (window never appears, licence dialog, crash) mark the plugin `capture_failed` and move on. Progress persists per plugin, so a REAPER crash mid-run resumes where it stopped. User can also **Retake** one or **Use my own image** (file picker).
- **Persistence:** `%APPDATA%\StudioHub\library.json` — per plugin: category override, favourite, last used, capture status; plus settings (theme, hotkey, picture size, hide-after-add, window size/pos, last category). Written atomically.
- **Hotkey:** default **Ctrl+Shift+Space**, configurable. Win32 `RegisterHotKey` via ctypes on its own thread (no dependency, no admin). Toggles show/hide.
- **Background running:** closing the window hides it; a tray icon (pystray) offers Show / Quit. The app keeps running so the hotkey works.
- **Packaging:** PyInstaller one-folder build (windowed, app icon) + Inno Setup script producing `StudioHub-Setup.exe`. The installer does not touch REAPER; first launch offers to install the bridge.

## Experience

- **First launch:** welcome sheet → reads REAPER's library (instant) → "Connect REAPER" (installs bridge, asks the user to restart REAPER or run the script once) → "Capture pictures" with progress bar, ETA, current plugin, pause/cancel; the user can leave it running. Library is usable throughout; uncaptured plugins show a designed placeholder (category colour + initials), not a broken image.
- **Window:** frameless, custom title bar (drag region, minimise, close-to-hide). Sidebar: *All Plugins*, *Favourites*, *Recently Used*, then categories with colour tag + count. Main: category title, search field (filters within the current view as you type; matches name and vendor), picture-size slider, grid of cards.
- **Card:** screenshot shown `contain` on a blurred copy of itself (no cropping of wide UIs); name; vendor; small category colour mark; format badge only when non-VST3; star if favourite. Single click selects and opens a slim detail panel (name, vendor, category with change control, formats, favourite, Retake picture, Use my own image). Double-click or Enter → send to REAPER.
- **Send:** success → subtle toast "Added to <track name>" and (setting, default on) the window hides. No track selected → toast "Select a track in REAPER first". REAPER not connected → banner with a Connect action.
- **Keyboard:** arrows move selection in the grid, Enter sends, Ctrl+F / typing focuses search, Esc clears search then hides, F toggles favourite.
- **Settings sheet:** Theme (3 swatches), Hotkey (record a new combo), Hide after adding, Picture size, REAPER connection status + reinstall bridge, Recapture all, Quit.
- **Motion:** window fades/scales in ~150 ms; cards ease on filter; respects reduced motion.

## Quality bar (anti-"vibe-coded")

- No emoji icons, no stock purple→blue gradients, no glow-everything, no generic card soup. One thin-stroke icon set (inline SVG, Lucide-style) used consistently.
- 8-px spacing grid; a fixed type scale (Segoe UI Variable, falling back to Segoe UI); colour comes from plugin art and category tags.
- Every state designed: empty, loading, scanning/capturing, no picture, capture failed, no search results, REAPER disconnected, no track selected.
- Nothing fake: every control works; no placeholder features.
- Behaves like an app: fast start, no console window, app icon, remembers window/theme/category, full keyboard use, accessible contrast in all three themes, visible focus.
- Verified by eye: every screen × theme is screenshotted (Playwright against the real local server) and reviewed before "done".

## Constraints

- Windows 10/11, REAPER x64 with its config in `%APPDATA%\REAPER` (portable installs: path configurable later, not v1).
- Must never modify the user's REAPER project during capture, never overwrite `__startup.lua`, never lose `library.json` (atomic writes).

## Left to the builder

Exact visual tokens per theme, icon artwork, card dimensions/slider range, window-detection heuristics, timing constants, test structure, repo layout, README wording.
