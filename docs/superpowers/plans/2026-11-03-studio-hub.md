# Studio Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old `main.py` with a polished Windows app: a visual, categorised library of the user's REAPER plugins, summoned by hotkey, that sends a plugin onto REAPER's selected track.

**Architecture:** Python package `studio_hub` reads REAPER's plugin cache, keeps user state in `library.json`, talks to REAPER through a file-based Lua bridge, and serves an HTML/CSS/JS UI plus a JSON API from a localhost `ThreadingHTTPServer`. pywebview shows that URL in a frameless window; a tray icon and a Win32 hotkey keep it one keystroke away.

**Tech Stack:** Python 3.13, pywebview 6 (WebView2), pywin32, mss, pystray, Pillow, pytest; vanilla JS/CSS; Lua ReaScript; PyInstaller + Inno Setup.

**Spec:** `docs/superpowers/specs/2026-11-03-studio-hub-design.md`

## Global Constraints

- Windows 10/11 only; Python 3.13 venv at `.venv`.
- Paths: REAPER config `%APPDATA%\REAPER` (override env `STUDIOHUB_REAPER_DIR`); app data `%APPDATA%\StudioHub` (override env `STUDIOHUB_DATA_DIR`). Tests always set both overrides to temp dirs.
- Never modify the user's REAPER project during capture; never overwrite `__startup.lua` (append one guarded line); all JSON writes atomic (temp + `os.replace`).
- Default hotkey **Ctrl+Shift+Space**. Default theme **graphite**. Themes: `graphite`, `light`, `glass`.
- UI: no emoji, inline-SVG thin-stroke icons only, 8-px spacing grid, font stack `"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`.
- No dependency beyond the Tech Stack list.
- Commits: the repo is not under git yet; `git init` in Task 1, and commit at the end of each task only once the owner has approved committing.

## Review Focus

1. **Odd plugin names** (commas, nested parentheses like `ReaStream (Cockos) (8ch)`, non-ASCII) — parse to the right name/vendor, never crash. → Task 1 `test_parses_tricky_names`.
2. **REAPER files missing** (no REAPER, fresh install) — empty library and a designed empty state, no exception. → Task 1 `test_missing_reaper_dir_returns_empty`.
3. **Corrupt `library.json`** — moved aside to `library.corrupt.json`, app starts with defaults. → Task 3 `test_corrupt_file_is_backed_up`.
4. **REAPER closed when sending** — returns `not_connected` within ~0.1 s instead of waiting out the timeout; UI stays responsive. → Task 4 `test_send_when_disconnected_is_fast`.
5. **Hotkey already taken by another app** — app keeps running; settings shows "Shortcut unavailable". → Task 7 `test_register_failure_reports_false`.

---

### Task 1: Scaffold + REAPER plugin reader

**Files:**
- Create: `requirements.txt`, `.gitignore` (`.venv/ __pycache__/ .superpowers/ build/ dist/`), `studio_hub/__init__.py`, `studio_hub/paths.py`, `studio_hub/reaper_db.py`
- Create: `tests/fixtures/reaper/reaper-vstplugins64.ini`, `reaper-clap-win64.ini`, `reaper-fxtags.ini` (small, hand-written, include the rows below)
- Test: `tests/test_reaper_db.py`
- Delete: `main.py`

**Interfaces:**
- Produces: `paths.reaper_dir() -> Path`, `paths.data_dir() -> Path` (creates it), `paths.snapshots_dir() -> Path`, `paths.bridge_dir() -> Path`
- Produces: `@dataclass Plugin(id: str, name: str, vendor: str, format: str, instrument: bool, add_name: str, reaper_tags: list[str], alternates: list[str])`; `load_plugins(reaper_dir: Path) -> list[Plugin]` sorted by `name.lower()`.
- `id` = first 12 hex of `sha1(f"{name}|{vendor}".lower())`. `format` ∈ `VST3|CLAP|VST`. `add_name` = `"{fmt}{'i' if instrument else ''}: {display}"` where display is REAPER's full string (e.g. `VST3: AmpliTube 5 (IK Multimedia)`). `alternates` = add_names of deduped lower-priority formats.

Fixture rows to include (vstcache): `reacomp.dll=00A9,1919247213,ReaComp (Cockos)`; `reastream.dll=009B,1920169074,ReaStream (Cockos) (8ch)`; `AmpliTube_5.vst3=0042,1566108953{5653,AmpliTube 5 (IK Multimedia)`; `Vital.vst3=808F,1854596000{5653,Vital (Vital Audio)!!!VSTi`; `WaveShell1_VST3_14.12_x64.vst3=8AFE,0,<SHELL>`; `WaveShell1_VST3_14.12_x64.vst3<1588611046=8AFE,1588611046{5653,IR-L Mono (Waves)`; `broken.dll=0011,0`; `AmpliTube_5.dll=0042,1566,AmpliTube 5 (IK Multimedia)`; `Ünïcode_Comp.vst3=01,2{56,Ünïcode, Comp (Tëst Co)`. Clap: `[TONE3000.clap]` / `com.tone3000.plugin=0|TONE3000 (TONE3000)`. fxtags `[developer]` and `[category]` for reacomp=Dynamics, AmpliTube_5.vst3=Distortion, WaveShell…<1588611046=Reverb, Vital.vst3=Synth.

- [ ] **Step 1:** `git init`; `py -3.13 -m venv .venv`; `requirements.txt`: `pywebview>=6.2`, `pywin32`, `mss`, `pystray`, `Pillow`, `pytest`; `.venv\Scripts\pip install -r requirements.txt`. Delete `main.py`.
- [ ] **Step 2: Write failing tests** in `tests/test_reaper_db.py`:

```python
def test_reads_vst_vst3_clap_and_shells(): ps = by_name(load_plugins(FIX)); assert {"ReaComp","AmpliTube 5","Vital","IR-L Mono","TONE3000"} <= ps.keys()
def test_skips_shell_header_and_nameless_rows(): assert not any(p.name in ("<SHELL>","") for p in load_plugins(FIX))
def test_instrument_flag_and_add_name(): v = by_name(load_plugins(FIX))["Vital"]; assert v.instrument and v.add_name == "VST3i: Vital (Vital Audio)"
def test_dedupes_preferring_vst3(): a = by_name(load_plugins(FIX))["AmpliTube 5"]; assert a.format == "VST3" and a.alternates == ["VST: AmpliTube 5 (IK Multimedia)"]
def test_tags_and_vendor_from_fxtags(): ps = by_name(load_plugins(FIX)); assert ps["ReaComp"].reaper_tags == ["Dynamics"] and ps["IR-L Mono"].vendor == "Waves"
def test_parses_tricky_names(): ps = by_name(load_plugins(FIX)); assert ps["ReaStream (8ch)"].vendor == "Cockos" and "Ünïcode, Comp" in ps
def test_missing_reaper_dir_returns_empty(tmp_path): assert load_plugins(tmp_path / "nope") == []
def test_ids_stable(): assert load_plugins(FIX)[0].id == load_plugins(FIX)[0].id and len(load_plugins(FIX)[0].id) == 12
```

- [ ] **Step 3:** Run `.venv\Scripts\pytest tests/test_reaper_db.py -v` → FAIL (import error).
- [ ] **Step 4: Implement** `paths.py` and `reaper_db.py`. Read ini files with `configparser.RawConfigParser(strict=False, interpolation=None)`, `optionxform = str`, encoding `utf-8` with `errors="replace"`. Value split `split(",", 2)`; strip `!!!VSTi`. Vendor = fxtags developer if present, else last `(…)` group not matching `^\d+ ?(out|ch)$`. Name = display with ` (vendor)` removed once. Format priority `VST3 > CLAP > VST` for dedupe on `(name.lower(), vendor.lower())`.
- [ ] **Step 5:** Re-run tests → PASS. Also run against the real `%APPDATA%\REAPER` with a one-off `python -c` printing the count and 5 samples; sanity-check by eye.
- [ ] **Step 6:** Commit (`feat: read plugin library from REAPER cache`).

### Task 2: Categories

**Files:** Create `studio_hub/categories.py`; Test `tests/test_categories.py`

**Interfaces:**
- Produces: `CATEGORIES: list[dict]` each `{"key","label","color"}` in sidebar order; `resolve_category(reaper_tags: list[str], name: str, instrument: bool) -> str` (a key).
- Keys/labels/colours (dark-theme hex; the UI adjusts for light): `eq` EQ `#30D158` · `dynamics` Dynamics `#FF9F0A` · `reverb` Reverb `#64D2FF` · `delay` Delay `#BF5AF2` · `modulation` Modulation `#FF375F` · `saturation` Saturation `#FF453A` · `filter` Filter `#40C8E0` · `pitch` Pitch & Tuning `#FFD60A` · `spatial` Spatial `#5E5CE6` · `strip` Channel Strip `#AC8E68` · `mastering` Mastering `#E5C07B` · `restoration` Restoration `#63E6BE` · `utility` Utility & Analysis `#8E8E93` · `instruments` Instruments `#0A84FF` · `amp` Amp & Guitar `#FF6B3D` · `uncategorised` Uncategorised `#636366`.
- Tag map (case-insensitive, first tag that maps wins): EQ→eq; Dynamics, Gate, Compressor, Limiter→dynamics; Reverb→reverb; Delay→delay; Modulation, Chorus, Flanger, Phaser→modulation; Distortion, Saturation→saturation; Filter→filter; Pitch Correction, Pitch Shift, Tuner→pitch; Surround, Spatial, Room, Ambisonics→spatial; Channel Strip→strip; Mastering→mastering; Restoration→restoration; Analyzer, Analysis, Tools, External, MIDI, Network→utility; Synth, Sampler, Drum, Instrument*→instruments; Guitar, Bass, Amp→amp. Then `instrument=True`→instruments. Then name keywords (`eq`, `comp`, `limit`, `verb`, `delay|echo`, `chorus|flanger|phaser`, `sat|drive|dist|tape`, `tune|pitch`, `amp`) matched on word boundaries. Else `uncategorised`.

- [ ] **Step 1: Failing tests:**

```python
def test_reaper_tag_wins(): assert resolve_category(["Distortion"], "Comp X", False) == "saturation"
def test_multi_tag_first_mapped(): assert resolve_category(["OnlyARA","EQ","Dynamics"], "x", False) == "eq"
def test_instrument_fallback(): assert resolve_category([], "Weird Name", True) == "instruments"
def test_name_keyword_fallback(): assert resolve_category([], "Bus Compressor", False) == "dynamics"
def test_no_false_keyword_hit(): assert resolve_category([], "Ampersand Space", False) == "uncategorised"
def test_every_category_has_color(): assert all(c["color"].startswith("#") for c in CATEGORIES) and CATEGORIES[-1]["key"] == "uncategorised"
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. **Step 5:** Commit.

### Task 3: Library store

**Files:** Create `studio_hub/library.py`; Test `tests/test_library.py`

**Interfaces:**
- Consumes: `Plugin`, `resolve_category`.
- Produces: `class Library(path: Path)` with `settings: dict` (defaults `{"theme":"graphite","hotkey":"Ctrl+Shift+Space","hide_after_add":True,"tile_size":200,"last_view":"all","window":None,"onboarded":False}`), `update_settings(**kw) -> dict`, `set_favourite(id, on: bool)`, `set_category(id, key: str | None)` (None clears override), `mark_used(id)` (stores `time.time()`), `set_capture(id, status: str)` (`none|ok|failed|custom`), `view(plugins: list[Plugin]) -> list[dict]`. Every mutator saves atomically.
- `view` item: `{"id","name","vendor","format","instrument","category","category_auto","favourite","last_used","capture","alternates"}` where `category` = override or `resolve_category(...)`.

- [ ] **Step 1: Failing tests:** `test_defaults_when_missing`, `test_roundtrip_persists_favourite_and_category` (new `Library` on same path sees changes), `test_override_beats_auto` (`view(...)[0]["category"] == "eq"` and `category_auto` unchanged), `test_clear_override`, `test_corrupt_file_is_backed_up` (write `"{not json"`, construct → defaults, `library.corrupt.json` exists), `test_unknown_settings_ignored` (`update_settings(bogus=1)` doesn't add key).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement (JSON `{"version":1,"settings":{},"plugins":{id:{...}}}`). **Step 4:** Run → PASS. **Step 5:** Commit.

### Task 4: REAPER bridge (Lua + Python)

**Files:** Create `studio_hub/reaper/studio_hub_bridge.lua`, `studio_hub/bridge.py`, `tests/fake_reaper.py`; Test `tests/test_bridge.py`

**Interfaces:**
- Produces: `class ReaperBridge(bridge_dir: Path)`: `connected() -> bool` (heartbeat mtime < 3 s), `send(verb: str, arg: str = "", timeout: float = 5.0) -> tuple[bool, str]` (returns `(False, "not_connected")` immediately when not connected; `(False, "timeout")` on timeout), `install(reaper_dir: Path) -> Path` (copies the Lua to `reaper_dir/Scripts/StudioHub/studio_hub_bridge.lua` with `BRIDGE_DIR` placeholder `--[[BRIDGE_DIR]]` replaced by a Lua long-string of `bridge_dir`; appends `dofile(reaper.GetResourcePath() .. "/Scripts/StudioHub/studio_hub_bridge.lua") -- studio-hub` to `Scripts/__startup.lua` only if the marker `-- studio-hub` is absent; returns script path), `installed(reaper_dir) -> bool`.
- Wire format (UTF-8, one line): `command.txt` = `id\tVERB\targ`; `response.txt` = `id\tOK|ERR\tdetail`. `id` = increasing int as str. Python writes via temp + `os.replace`; reads response until id matches.
- Lua verbs (spec): `ADD` → `GetSelectedTrack(0,0)`; none → `ERR NO_TRACK`; else `TrackFX_AddByName(tr, name, false, -1)`; idx < 0 → `ERR NOT_FOUND`; `TrackFX_Show(tr, idx, 3)`; `OK <track name or "Track N">`. `CAPTURE_BEGIN` → remember current project, `Main_OnCommand(40859,0)` new tab. `CAPTURE_OPEN name` → insert track at end of capture project, add FX, float it, `OK`. `CAPTURE_CLOSE` → delete that track. `CAPTURE_END` → `Main_SaveProjectEx(proj, os.tmpname()..".rpp", 0)`, `Main_OnCommand(40860,0)` close tab, `SelectProjectInstance(original)`. `PING` → `OK`. Loop: `reaper.defer`, poll every 0.1 s via `reaper.time_precise()`, heartbeat file rewritten each 1 s. All verbs wrapped in `pcall`; error → `ERR <msg>`.
- `fake_reaper.py`: `FakeReaper(bridge_dir, replies: dict[str, str])` thread that writes heartbeats and answers commands with `replies.get(verb, "OK")`; `.received: list[tuple[str,str]]`; `.stop()`.

- [ ] **Step 1: Failing tests:** `test_send_roundtrip_with_fake` (`send("ADD","VST3: X") == (True, "Track 1")` with replies `{"ADD":"OK\tTrack 1"}`; fake received it), `test_err_propagates` (`(False, "NO_TRACK")`), `test_send_when_disconnected_is_fast` (no fake; `send` returns `(False,"not_connected")` in < 0.2 s), `test_install_is_idempotent_and_preserves_startup` (existing `__startup.lua` with `print(1)` keeps it; marker appears exactly once after two installs; placeholder replaced), `test_connected_goes_false_after_heartbeat_stale`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement Python + Lua + fake. **Step 4:** Run → PASS.
- [ ] **Step 5: Manual REAPER check:** install into real REAPER, run the script once (Actions → Load ReaScript), select a track, `python -c "from studio_hub.bridge import *; ..."` send `ADD` for `ReaComp` → appears on track with window floating; with no track selected → `NO_TRACK`. **Step 6:** Commit.

### Task 5: Local server + API

**Files:** Create `studio_hub/server.py`, `studio_hub/api.py`; Test `tests/test_server.py`

**Interfaces:**
- Consumes: `load_plugins`, `CATEGORIES`, `Library`, `ReaperBridge`, (Task 6's `CaptureRunner` via duck typing: `start(ids: list[str] | None)`, `pause()`, `resume()`, `cancel()`, `status() -> dict`).
- Produces: `class Api(reaper_dir, library, bridge, capture, hooks: dict[str, Callable])` — hooks: `hide`, `minimize`, `quit`, `pick_image() -> str | None`, `set_hotkey(combo) -> bool`. Methods return JSON-able dicts: `state()`, `refresh()`, `send(id)`, `update_plugin(id, favourite=None, category=..., )`, `update_settings(**kw)`, `capture(action, id=None)`, `custom_image(id)`, `install_bridge()`, `window(action)`.
- `make_server(api: Api, ui_dir: Path, snapshots_dir: Path) -> ThreadingHTTPServer` on `127.0.0.1:0`. Routes: `GET /` → `index.html`; `GET /<static>` from `ui_dir` (reject `..`); `GET /snapshots/<id>.png` (`Cache-Control: no-cache`); `GET /api/state`; `POST /api/{refresh,send,plugin,settings,capture,custom-image,bridge/install,window}` with JSON body. Unknown → 404 JSON. Exceptions → 500 `{"error": str}`, logged.
- `state()` = `{"plugins": library.view(...), "categories": CATEGORIES, "settings": ..., "reaper": {"connected": bool, "installed": bool}, "capture": capture.status()}`.
- `send(id)`: unknown id → `{"ok":False,"error":"unknown"}`; else `bridge.send("ADD", plugin.add_name)`; on OK `library.mark_used`, and if `hide_after_add` call `hooks["hide"]`; returns `{"ok", "detail"}`.
- `custom_image(id)`: `pick_image()` path → Pillow open, convert RGB, save to `snapshots/<id>.png`, `set_capture(id,"custom")`.

- [ ] **Step 1: Failing tests** (server on a thread, `urllib.request`, fixture REAPER dir, `FakeReaper`, a stub capture): `test_state_lists_plugins_and_categories`, `test_send_adds_and_marks_used` (fake received `("ADD","VST3: AmpliTube 5 (IK Multimedia)")`; hide hook called), `test_send_unknown_id`, `test_plugin_update_category_override`, `test_static_rejects_traversal` (`/../secret` → 404), `test_bad_json_returns_400`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. **Step 5:** Commit.

### Task 6: Capture runner

**Files:** Create `studio_hub/capture.py`; Test `tests/test_capture.py`

**Interfaces:**
- Produces: `class CaptureRunner(bridge, library, snapshots_dir, plugins_fn: Callable[[], list[Plugin]], find_window=find_plugin_window, grab=grab_window)`; `start(ids=None)` (None → all with capture `none`/`failed`; runs on a daemon thread; no-op if running), `pause()`, `resume()`, `cancel()`, `status() -> {"running","paused","done","total","current","failed"}`.
- `find_plugin_window(name: str, timeout: float = 8.0) -> int | None`: pywin32 `EnumWindows`, visible windows owned by a `reaper.exe` process whose title contains `name` (case-insensitive), polled every 0.2 s.
- `grab_window(hwnd: int, out: Path) -> bool`: `SetForegroundWindow`, wait until two consecutive `mss` grabs of `GetWindowRect` 300 ms apart are identical (max 3 s, min 1.2 s), strip REAPER's title bar using `GetClientRect`/`ClientToScreen`, save PNG; reject images < 80×60 or ≥ 98 % one colour → False.
- Loop per plugin: `CAPTURE_BEGIN` once → for each: `CAPTURE_OPEN add_name` → find → grab → `CAPTURE_CLOSE` → `set_capture(ok|failed)`; `CAPTURE_END` at the end or on cancel. Bridge not connected → stop with `status.error = "not_connected"`.

- [ ] **Step 1: Failing tests** with `FakeReaper` and injected `find_window`/`grab` fakes: `test_captures_pending_and_marks_status` (one fake grab returns False → that plugin `failed`, others `ok`; order of verbs begins `CAPTURE_BEGIN` ends `CAPTURE_END`), `test_cancel_ends_session`, `test_skips_already_captured`, `test_stops_when_disconnected`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5: Manual:** with REAPER open, capture 5 real plugins (ReaComp, ReaEQ, one VST3, one Waves shell, one instrument); open PNGs and check they show the plugin face with no title bar. Tune timings if needed. **Step 6:** Commit.

### Task 7: Hotkey

**Files:** Create `studio_hub/hotkey.py`; Test `tests/test_hotkey.py`

**Interfaces:**
- Produces: `parse_hotkey(combo: str) -> tuple[int, int]` (`MOD_CONTROL|MOD_SHIFT|MOD_ALT|MOD_WIN` + `MOD_NOREPEAT`, VK; supports letters, digits, F1–F24, Space, Tab, names case-insensitive; raises `ValueError`), `class HotkeyListener(callback)`: `register(combo) -> bool` (re-register on its own message-loop thread via `PostThreadMessage`; False if `RegisterHotKey` fails), `stop()`. ctypes only.

- [ ] **Step 1: Failing tests:** `test_parse_default` (`parse_hotkey("Ctrl+Shift+Space") == (0x2|0x4|0x4000, 0x20)`), `test_parse_rejects_garbage`, `test_register_failure_reports_false` (register same combo in two listeners → second returns False), `test_register_and_stop`.
- [ ] **Step 2–4:** FAIL → implement → PASS. **Step 5:** Commit.

### Task 8: UI

**Files:** Create `studio_hub/ui/index.html`, `studio_hub/ui/styles.css`, `studio_hub/ui/app.js`, `studio_hub/ui/icons.js`; Create `studio_hub/devserver.py` (runs `make_server` with real data, prints URL, no window — for Playwright)

**Interfaces:**
- Consumes: Task 5 HTTP API only. Poll `GET /api/state` every 1 s while capturing, else every 3 s (REAPER connection indicator).
- Structure: `<body data-theme>`; title bar (drag region class `pywebview-drag-region`, app name, min + close buttons calling `/api/window`); sidebar (Library: All, Favourites, Recently Used; Categories with colour dot + count, empty categories hidden; footer: REAPER status dot + Settings button); main header (view title, count, search field, size slider 140–320 px bound to `--tile`); grid (`repeat(auto-fill, minmax(var(--tile), 1fr))`, virtual-free, lazy `<img loading="lazy">`); detail panel (slides from right, 320 px); settings sheet (modal); onboarding sheet when `!settings.onboarded`; toast stack bottom-centre; capture progress bar under header while running.
- Card: image area 4:3, `<img>` `object-fit: contain` over a `filter: blur(24px) saturate(1.4)` copy of itself; placeholder when `capture != ok/custom`: category-tinted surface with 2-letter initials and, if `failed`, a small "Couldn't capture" caption. Category mark = 8 px rounded square before vendor. Format badge only if not VST3. Star overlay when favourite.
- Themes via CSS custom properties on `[data-theme=graphite|light|glass]`: `--bg --surface --surface-2 --sidebar --border --text --text-2 --accent --shadow`. Glass: translucent sidebar/panels (`backdrop-filter: blur(30px) saturate(1.6)`) over a fixed radial colour wash. Light: category colours darkened ~15 % via `color-mix`.
- Keyboard: arrows move selection by grid columns (computed from layout), Enter = send, F = favourite, Ctrl+F or any printable key = focus search, Esc = clear search → close panel → hide window, Ctrl+, = settings.
- Hotkey recorder in settings: captures next key combo, POSTs settings; shows "Shortcut unavailable" if response `hotkey_ok` is false.
- All copy in sentence case; no emoji; icons from `icons.js` (`icon(name)` returns SVG string: search, star, star-fill, settings, close, minus, camera, image, refresh, plug, check, alert, grid, clock).

- [ ] **Step 1:** Build markup/CSS/JS against `devserver.py` with the real REAPER library.
- [ ] **Step 2: Visual verification with Playwright** (MCP browser): for each theme × {library with pictures, Favourites empty, search no results, detail panel open, settings open, onboarding, REAPER disconnected banner, capture in progress} take a screenshot at 1280×800 and 900×640; review alignment to the 8-px grid, contrast, truncation, focus rings. Fix and re-shoot until clean.
- [ ] **Step 3: Behaviour check in browser:** search filters live; category counts right; star persists after reload; category change moves card; keyboard navigation works; with `FakeReaper` running, Enter shows "Added to Track 1".
- [ ] **Step 4:** Commit.

### Task 9: App shell (window, tray, first run)

**Files:** Create `studio_hub/app.py`, `studio_hub/__main__.py`, `studio_hub/assets/icon.ico` (+ `icon.png`, designed: rounded-square, graphite with a 2×2 grid of coloured tiles)

**Interfaces:**
- Consumes: everything above.
- `main()`: build `Library(data_dir()/"library.json")`, `ReaperBridge(bridge_dir())`, `CaptureRunner`, `Api` with hooks bound to the pywebview window; `make_server` on a thread; `webview.create_window("Studio Hub", url, frameless=True, easy_drag=False, width/height from settings.window or 1200×780, min_size=(900, 600), background_color` per theme`)`; save window size/pos on hide/quit; `HotkeyListener(toggle).register(settings.hotkey)`; pystray icon (Show, Quit) on its own thread; `webview.start(gui="edgechromium")`. Toggle: if hidden or not foreground → show + restore + focus; else hide. Single instance: named mutex `StudioHub.SingleInstance`; second launch posts "show" to the first (via a `show` file in data dir watched by the first, or a `/api/window` POST to the URL saved in `data_dir()/server.txt`) and exits.
- [ ] **Step 1:** Implement; run `.venv\Scripts\python -m studio_hub`.
- [ ] **Step 2: Manual check:** hotkey toggles over REAPER; close hides; tray Show/Quit; second launch focuses first; window size remembered; no console window under `pythonw`.
- [ ] **Step 3:** Commit.

### Task 10: Packaging + README

**Files:** Create `packaging/studio_hub.spec`, `packaging/installer.iss`, `packaging/build.ps1`, `README.md`, `LICENSE` (MIT, owner's name to be confirmed), `docs/screenshots/*.png`

- PyInstaller one-folder, `windowed`, icon, datas: `studio_hub/ui`, `studio_hub/reaper`, `studio_hub/assets`. Resource paths resolved via `sys._MEIPASS` fallback in `paths.py` (`paths.resource(rel) -> Path`).
- Inno: install to `{autopf}\Studio Hub`, Start-menu shortcut, optional "Start with Windows" task (HKCU Run), uninstaller leaves `%APPDATA%\StudioHub` unless the user ticks "Remove my library data".
- README: one-line pitch, hero screenshot (Graphite), theme strip, features, how it works (REAPER cache → bridge → capture), install, build from source, tests, roadmap (non-goals).
- [ ] **Step 1:** `packaging/build.ps1` → `dist\StudioHub\StudioHub.exe` runs on its own; ISCC compiles if Inno Setup is installed (report if not).
- [ ] **Step 2:** Full `pytest` → all pass. **Step 3:** Commit.
