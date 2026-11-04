# Chains, grouped versions, help and new-plugin notice: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add chains (one-click plugin chains, including return tracks), grouped plugin versions, page help and a new-plugin notice to Ordel.

**Architecture:** Python holds the data and logic (`reaper_db.py` groups versions, new `chains.py` reads/writes REAPER `.RfxChain` files, `library.py` stores Ordel's extras, `api.py`/`server.py` expose it). REAPER-side work goes through new verbs in the Lua bridge (file IPC), which edits track state chunks so each action is one undo step. The vanilla-JS UI (`studio_hub/ui/`) gets a Chains view, a version picker, "?" help and a notice line.

**Tech Stack:** Python 3.13, pywin32, pytest, lupa (Lua tests), vanilla JS/CSS, REAPER Lua ReaScript.

**Spec:** `docs/superpowers/specs/2026-11-04-chains-variants-help-design.md`

## Global Constraints

- Windows and REAPER only; everything must work for other users with no manual setup.
- Ask Charlie before every commit; never push. "Commit" steps below mean: show what changed, ask, then commit.
- Never force-close REAPER; never permanently delete user data (Ordel's own chain files go to the Recycle Bin; chains made in REAPER are never deleted, only hidden).
- No new pip dependencies (pywin32 already covers the Recycle Bin).
- UI copy: plain English for producers, no jargon; calm and minimal, nothing that pops over the user's work.
- Keep the existing capture safety (isolation, unsaved-work check) and the existing `ADD` behaviour intact.
- Run the full suite with `.venv\Scripts\python.exe -m pytest -q`; it must stay green after every task.

## Review Focus

1. A plugin that exists only as a Mono (or only a "(32 out)") version must still show as one normal card, not vanish or become an empty group. Test: Task 1 `test_single_variant_is_not_grouped`.
2. Applying the same chain twice (or to a track that already has FX) must give each plugin a fresh FX ID and keep existing FX. Test: Task 5 `test_apply_twice_gives_fresh_fx_ids`.
3. A fresh track with no FX yet has no `<FXCHAIN` block; applying must create one. Test: Task 5 `test_apply_to_track_without_fx_creates_chain_block`.
4. A chain file holding JS effects, plugins Ordel doesn't know, or odd bytes must list without crashing; unknown plugins show as a plain tile. Test: Task 4 `test_parse_tolerates_js_unknown_and_bad_bytes`.
5. Applying a normal chain with no track selected must say "Select a track in REAPER first", not fail silently. Test: Task 5 `test_apply_without_selected_track_says_so`.

---

### Task 1: Group plugin versions

**Files:**
- Modify: `studio_hub/reaper_db.py` (add `variants` to `Plugin`; add `group_variants`; call it at the end of `load_plugins`)
- Test: `tests/test_reaper_db.py`

**Interfaces:**
- Produces: `Plugin.variants: list[Plugin]` (other versions, not including the plugin itself; empty when not grouped); `Plugin.variant: str` (this version's label); `variant_label(name: str) -> tuple[str, str]` returning `(base_name, label)`; `group_variants(plugins: list[Plugin]) -> list[Plugin]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_variant_label():
    from studio_hub.reaper_db import variant_label
    assert variant_label("FabFilter Pro-C 2 (Mono)") == ("FabFilter Pro-C 2", "Mono")
    assert variant_label("FabFilter Volcano 2 (Mono SC)") == ("FabFilter Volcano 2", "Mono sidechain")
    assert variant_label("FabFilter Timeless 2 (SC)") == ("FabFilter Timeless 2", "Sidechain")
    assert variant_label("Sitala (32 out)") == ("Sitala", "32 outputs")
    assert variant_label("ReaStream (8ch)") == ("ReaStream", "8 channels")
    assert variant_label("FabFilter Pro-Q 3") == ("FabFilter Pro-Q 3", "Stereo")

def test_versions_are_grouped_under_the_stereo_one():
    # build Plugin objects for Pro-C 2, Pro-C 2 (Mono), Pro-Q 3, Pro-Q 4 (same vendor)
    groups = group_variants(plugins)
    names = sorted(g.name for g in groups)
    assert names == ["FabFilter Pro-C 2", "FabFilter Pro-Q 3", "FabFilter Pro-Q 4"]
    proc = next(g for g in groups if g.name == "FabFilter Pro-C 2")
    assert proc.variant == "Stereo" and [v.variant for v in proc.variants] == ["Mono"]
    assert proc.id == <id of the original stereo Pro-C 2>  # existing data stays attached

def test_group_without_a_plain_version_is_named_by_its_base():
    # Volcano 2 (Mono) + Volcano 2 (SC), no plain one
    g, = group_variants(plugins)
    assert g.name == "FabFilter Volcano 2" and g.variant == "Mono" and [v.variant for v in g.variants] == ["Sidechain"]

def test_single_variant_is_not_grouped():
    # only "Creepy Piano 3 Lite (32 out)"
    g, = group_variants(plugins)
    assert g.name == "Creepy Piano 3 Lite (32 out)" and g.variants == []

def test_same_name_different_developer_is_not_grouped(): ...
```

- [ ] **Step 2: Run** `.venv\Scripts\python.exe -m pytest tests/test_reaper_db.py -q`. Expected: FAIL (`variant_label` not defined).

- [ ] **Step 3: Implement** in `studio_hub/reaper_db.py`.
  - Recognised trailing suffixes (case-insensitive) and labels: `(Mono)` → "Mono", `(Stereo)` → "Stereo", `(SC)`/`(Sidechain)` → "Sidechain", `(Mono SC)`/`(Mono Sidechain)` → "Mono sidechain", `(N out)` → "N outputs", `(Nch)` → "N channels". No suffix → "Stereo".
  - Group key: `(base_name.lower(), vendor.lower())`. Main member: the one labelled "Stereo", else the first by label order Stereo, Mono, Sidechain, Mono sidechain, then outputs/channels ascending.
  - A group of one keeps its original name. A group of two or more takes `base_name` as its name; the main keeps its own `id`.
  - `load_plugins` returns `group_variants(...)` sorted by name as today. Existing tests in `tests/test_reaper_db.py` must still pass; update any whose expectations change because of grouping (e.g. the ReaStream fixture stays a single card named "ReaStream (8ch)").

- [ ] **Step 4: Run** the test file, then the full suite. Expected: PASS.

- [ ] **Step 5: Commit** (with approval): `Group plugin versions (stereo, mono, sidechain, multi-output)`.

### Task 2: Merge each group's saved data and pick the version to add

**Files:**
- Modify: `studio_hub/library.py` (`view`, `set_favourite`, `set_category`, new `count_variant`)
- Modify: `studio_hub/api.py` (`send(id, variant=None)`, `update_plugin`)
- Modify: `studio_hub/server.py` (`/api/send` passes `b.get("variant")`)
- Test: `tests/test_library.py`, `tests/test_app.py` (or wherever `Api.send` is tested; grep `def test_send`)

**Interfaces:**
- Consumes: `Plugin.variants`, `Plugin.variant` (Task 1).
- Produces: each `Library.view()` entry gains `variants: [{"id": str, "label": str}]` (main first, so the list includes the main), `preferred: str` (variant id to add on double-click), `shot_id: str` (whose picture to show); `favourite`, `last_used`, `category`, `capture`, `shot` are merged across the group. `Api.send(id: str, variant: str | None = None) -> dict`. `Library.count_variant(group_id: str, variant_id: str) -> None`. `Library.set_favourite(plugin_id, on, also: Iterable[str] = ())` and `Library.set_category(plugin_id, key, also: Iterable[str] = ())`: `also` are the group's other version ids, cleared alongside (favourite off / category override removed) so the merged view matches what the user just did; `Api.update_plugin` passes them.

- [ ] **Step 1: Write the failing tests**

```python
def test_group_is_starred_if_any_version_was(): ...          # only the Mono id starred -> group favourite True
def test_unstarring_a_group_unstars_every_version(): ...     # set_favourite(group_id, False, variant_ids) clears all
def test_group_uses_a_versions_picture_when_main_has_none(): # main capture none, Mono capture ok -> shot_id == mono id, capture "ok"
def test_group_recent_use_is_the_latest_of_its_versions(): ...
def test_category_override_on_a_version_carries_to_the_group(): ...  # main override wins if both set
def test_preferred_version_is_the_one_added_most(): ...      # count_variant x2 Mono, x1 Stereo -> preferred == mono id; default main id
def test_send_adds_the_chosen_version_and_counts_it(tmp_path): ...  # FakeReaper receives ("ADD", "VST: ... (Mono) ...")
```

- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** New writes go on the main id; `also` ids are cleared. Store counts as a `variants` dict field on the group id's record. `Api.send` rejects a `variant` that isn't one of the group's ids (`ValueError`). Capture already only sees `api.plugins` (groups), so it takes one picture per group: confirm with an existing capture test, no change expected.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** (with approval): `Keep favourites, pictures and recent use across a plugin's versions`.

### Task 3: Version picker in the UI

**Files:**
- Modify: `studio_hub/ui/app.js` (`cardHtml`, `renderDetail`, `visiblePlugins` search, `send`, `shotUrl`), `studio_hub/ui/styles.css`

**Interfaces:**
- Consumes: view fields `variants`, `preferred`, `shot_id` (Task 2); `POST /api/send {id, variant}`.

- [ ] **Step 1:** `shotUrl(p)` uses `p.shot_id`. Card shows a quiet hint under the developer line when `p.variants.length > 1`, e.g. "Stereo · Mono" (labels joined with " · "), styled like `.fmt`.
- [ ] **Step 2:** Double-click / Enter sends `{id, variant: p.preferred}`. Clicking the hint opens a small menu of the labels; choosing one sends that variant. In the detail panel, "Add to track" becomes a split control when there are versions: the main button adds the preferred version, a segmented choice beside it picks another.
- [ ] **Step 3:** Search haystack includes the version labels.
- [ ] **Step 4: Check in the browser pane** with the devserver (`.venv\Scripts\python.exe -m studio_hub.devserver 8765`): FabFilter Pro-C 2 shows once with "Stereo · Mono"; choosing Mono calls `/api/send` with the Mono id (check network log); light and dark themes both readable. Full pytest suite still green.
- [ ] **Step 5: Commit** (with approval): `Pick a plugin's version from its card`.

### Task 4: Read and list chains

**Files:**
- Create: `studio_hub/chains.py`
- Modify: `studio_hub/library.py` (a top-level `chains` dict saved in `library.json` beside `settings`/`plugins`; methods below)
- Test: `tests/test_chains.py`, `tests/test_library.py`

**Interfaces:**
- Produces (in `chains.py`):
  - `chains_dir(reaper_dir: Path) -> Path` = `reaper_dir / "FXChains"`; `ORDEL_FOLDER = "Ordel"`.
  - `parse_chain(path: Path) -> list[str]`: the plugin names in order, from lines starting `<VST`, `<CLAP`, `<JS`, `<DX`, `<AU`: the first quoted string (e.g. `"VST3: FabFilter Pro-Q 3 (FabFilter)"`; for `<JS` the script path). Reads bytes, decodes UTF-8 with `errors="replace"`.
  - `chain_files(reaper_dir: Path) -> dict[str, Path]`: id `"file:" + path relative to FXChains with forward slashes` → path, for every `*.RfxChain` under FXChains (recursive, case-insensitive extension).
  - `safe_name(name: str) -> str`: strips `<>:"/\|?*` and control characters, trims, max 80 chars, falls back to "Chain".
  - `new_chain_path(reaper_dir: Path, name: str) -> Path`: `FXChains/Ordel/<safe_name>.RfxChain`, adding " 2", " 3" … if taken.
  - `send_to_recycle_bin(path: Path) -> None`: `win32com.shell.shell.SHFileOperation` with `FO_DELETE` and `FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI`; raises `OSError` on a non-zero result.
- Produces (in `Library`): `chain_meta() -> dict[str, dict]`; `set_chain_meta(chain_id: str, **fields) -> None` (fields: `order: int`, `return_track: bool`, `hidden: bool`, `name: str` and `plugins: list[str]` for built chains); `remove_chain_meta(chain_id: str) -> None`; `prune_chain_meta(existing_ids: set[str]) -> None` (drops extras of `file:` ids whose file is gone; keeps `built:` ids).

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_chain_lists_plugins_in_order(tmp_path):
    f = tmp_path / "Vocal.RfxChain"
    f.write_text('BYPASS 0 0 0\n<VST "VST: ReaEQ (Cockos)" reaeq.dll 0 "" 1919247729<5653>\nZXE=\n>\nFLOATPOS 0 0 0 0\nFXID {1}\nWAK 0 0\n'
                 'BYPASS 0 0 0\n<VST "VST3: FabFilter Pro-Q 3 (FabFilter)" "FabFilter Pro-Q 3.vst3" 0 "" 1{2}\nAAA=\n>\n')
    assert parse_chain(f) == ["VST: ReaEQ (Cockos)", "VST3: FabFilter Pro-Q 3 (FabFilter)"]

def test_parse_tolerates_js_unknown_and_bad_bytes(tmp_path):
    # a <JS "utility/volume" ""> block, a <CLAP "CLAP: Nope (X)" ...> block and b"\xff\xfe" garbage
    assert parse_chain(f) == ["utility/volume", "CLAP: Nope (X)"]

def test_chain_files_finds_subfolders_and_ignores_other_files(tmp_path): ...  # ids "file:Ordel/Vocal.RfxChain", "file:Drums/Kit.rfxchain"
def test_new_chain_path_is_safe_and_unique(tmp_path):
    assert new_chain_path(tmp_path, 'Vox: "lead"').name == "Vox lead.RfxChain"
    # second call with same name after creating the first -> "Vox lead 2.RfxChain"
def test_chain_meta_survives_reload_and_prunes_missing_files(tmp_path): ...
```

- [ ] **Step 2: Run** `.venv\Scripts\python.exe -m pytest tests/test_chains.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** the functions above. `Library._save` writes `chains` too; `_load` accepts only a dict of dicts for it.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** (with approval): `Read REAPER's saved FX chains`.

### Task 5: Bridge verbs to save and apply chains

**Files:**
- Modify: `studio_hub/reaper/studio_hub_bridge.lua`
- Test: `tests/test_lua_bridge.py` (extend `FAKE_REAPER`: tracks carry a `chunk` string; add `CountSelectedTracks`, `GetSelectedTrack(proj, i)` honouring several selected tracks, `GetTrackStateChunk`, `SetTrackStateChunk`, `CountTracks`, `GetSetMediaTrackInfo_String` for `P_NAME`, `SetTrackColor`, `RecursiveCreateDirectory`)

**Interfaces:**
- Produces three verbs. Fields in `arg` are separated by tab (`\t`); plugin names and Windows paths never contain tabs.
  - `CHAIN_SAVE <path>`: writes the first selected track's FX (from its first `BYPASS` line to just before the `<FXCHAIN` block's closing `>`, matched by depth) to `path`, creating folders. Replies `OK\t<fx count>`, `ERR\tNO_TRACK`, or `ERR\tNO_FX`.
  - `CHAIN_APPLY <mode>\t<name>\t<path>` with mode `track` or `return`: reads the file, removes its `FXID` lines (REAPER assigns fresh ones), and appends the FX to each target track's chunk: inside the existing `<FXCHAIN` block before its closing `>`, or by adding `<FXCHAIN\nSHOW 0\nLASTSEL 0\nDOCKED 0\n…\n>` before the track chunk's final `>` when there is none. `track` targets every selected track and replies `OK\t<n>`; `return` inserts a new track at the end, names it `name`, gives it a colour, applies the chain, and replies `OK\tEXISTS` if a track named `name` was already in the project, else `OK\tNEW`. One undo block per call: `Ordel: add chain <name>`. `ERR\tNO_TRACK` when `track` mode has no selection; `ERR\tNO_FILE` when the file can't be read.
  - `CHAIN_ADD <mode>\t<name>\t<plugin1>\t<plugin2>…`: same targets, replies and undo as `CHAIN_APPLY`, but adds each plugin with `TrackFX_AddByName` (for chains built in Ordel).
  - All three use the same project as `ADD` (the user's project, never the capture tab).

- [ ] **Step 1: Write the failing tests**

```python
def test_save_writes_the_selected_tracks_fx(lua, tmp_path): ...       # file starts with "BYPASS", contains both <VST blocks, no WNDRECT/SHOW lines
def test_save_without_fx_says_so(lua, tmp_path): assert handlers.CHAIN_SAVE(str(p)) == "ERR\tNO_FX"
def test_apply_to_every_selected_track(lua, tmp_path): ...            # two selected -> "OK\t2", both chunks contain the chain
def test_apply_to_track_without_fx_creates_chain_block(lua, tmp_path): ...  # chunk gains "<FXCHAIN" then the chain, and stays balanced
def test_apply_twice_gives_fresh_fx_ids(lua, tmp_path): ...           # no "FXID" lines copied in; existing FX kept
def test_apply_without_selected_track_says_so(lua, tmp_path): assert ... == "ERR\tNO_TRACK"
def test_return_mode_adds_a_named_track_and_reports_duplicates(lua, tmp_path):
    assert handlers.CHAIN_APPLY(f"return\tPlate\t{p}") == "OK\tNEW"
    assert handlers.CHAIN_APPLY(f"return\tPlate\t{p}") == "OK\tEXISTS"   # a second Plate track is still added
def test_chain_add_uses_add_by_name(lua): ...
def test_chain_verbs_never_touch_the_capture_tab(lua, tmp_path): ...
```

- [ ] **Step 2: Run** `.venv\Scripts\python.exe -m pytest tests/test_lua_bridge.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the verbs (shared helpers for "targets", "insert into chunk", undo block).
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Check in the real REAPER** (Charlie opens REAPER; Ordel's script auto-updates on Ordel start via `refresh_bridge`, or run the bridge script with `reaper.exe -nonewinst`). With a throwaway test project: put ReaEQ + ReaComp on a track, change a ReaComp setting, run `CHAIN_SAVE` through the bridge to `FXChains\Ordel\Probe.RfxChain`, apply it to another selected track and as a return track; confirm settings match, a single Ctrl+Z removes it, and REAPER's own FX browser lists the chain. Then delete the probe file (it's ours) and close the test project without saving.
- [ ] **Step 6: Commit** (with approval): `Bridge: save and apply FX chains`.

### Task 6: Chains in the API

**Files:**
- Modify: `studio_hub/api.py`, `studio_hub/server.py`
- Test: `tests/test_app.py` or a new `tests/test_api_chains.py` (FakeReaper + tmp REAPER folder)

**Interfaces:**
- Consumes: Task 4 functions and Library methods; Task 5 verbs; groups from Task 1/2 for matching.
- Produces: `Api.state()["chains"]`: list sorted by `order` then name, of
  `{"id", "name", "kind": "file"|"built", "ordel": bool, "return_track": bool, "hidden": bool, "plugins": [{"name": str, "id": str|None, "variant": str|None}]}`; `ordel` is true for built chains and files under `FXChains/Ordel/`; `plugins[i].id`/`variant` are the matched group id and version id (matched on `add_name` and `alternates` of every version), `None` when unknown.
  `Api.chain_action(action: str, **body) -> dict`, routed from `POST /api/chain`. Actions:
  - `apply {id}` → bridge `CHAIN_APPLY`/`CHAIN_ADD`; returns `{"ok", "detail", "missing": [plugin names not installed], "exists": bool, "tracks": int}`.
  - `save {name, replace: id|None}` → `CHAIN_SAVE` to `new_chain_path` (or the replaced chain's own file when it lives in Ordel's folder; replacing a built chain turns it into a file chain and moves its extras); returns `{"ok", "id"}`.
  - `build {name, plugins: [variant ids]}` → new `built:<uuid4 hex>` chain storing the versions' `add_name`s.
  - `update {id, name?, return_track?, plugins?}` (renaming an Ordel file renames the file; renaming a REAPER chain is refused with `ValueError`).
  - `move {id, delta: -1|1}` → reorders by rewriting `order` for all chains.
  - `hide {id, hidden: bool}`.
  - `delete {id}` → Ordel file: `send_to_recycle_bin`; built: `remove_chain_meta`; REAPER chain: `ValueError("hide it instead")`.
  `state()` calls `prune_chain_meta` with the current file ids.

- [ ] **Step 1: Write the failing tests:** listing (REAPER chain + Ordel chain + built chain, order, `ordel` flags, plugin matching incl. a Mono version and an unknown plugin), `apply` reporting `missing` and `exists`, `save` into `FXChains/Ordel`, `build` → `apply` sends `CHAIN_ADD` with the chosen versions' names, `delete` refusing a REAPER chain, `delete` of an Ordel file calling the recycle function (monkeypatch it), rename of an Ordel file.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** (with approval): `Chains: list, save, build, apply`.

### Task 7: Chains view in the UI

**Files:**
- Modify: `studio_hub/ui/app.js`, `studio_hub/ui/styles.css`, `studio_hub/ui/icons.js` (add `chain` and `help` icons in the existing stroke style), `studio_hub/ui/index.html` if a container is needed

**Interfaces:**
- Consumes: `state.chains` and `POST /api/chain` (Task 6).

- [ ] **Step 1:** Sidebar: "Chains" `navItem("chains", …, icon("chain"))` after Recently used, count = visible chains. `S.view === "chains"` renders chain cards instead of plugin cards: name, a strip of the plugins' pictures in order (plain initials tile for unknown ones), a small "Return track" mark when set. Hidden chains appear only under a quiet "Show hidden (n)" toggle.
- [ ] **Step 2:** Click a chain card → `apply`. Toasts: "Added Vocal to 3 tracks", "Added a Plate return track", "A Plate return already exists in this project. Added another.", "Added Vocal. Not installed: X, Y", and the existing `SEND_ERRORS` for `NO_TRACK`/`not_connected`/`timeout`.
- [ ] **Step 3:** Toolbar in Chains view: "Save from selected track" (asks for a name in a small inline field) and "Build a chain" (opens the chain panel empty).
- [ ] **Step 4:** Chain detail panel (reuse `#detail`): name (editable when `ordel`), "Use as return track" switch, plugin list; for built chains add (search field listing library plugins, version chosen like Task 3), remove, move up/down; "Save from selected track" to overwrite with REAPER's settings; move chain up/down in the list; Delete (Ordel chains) or Hide (REAPER chains).
- [ ] **Step 5:** Delete with undo: `toast()` gains an optional `{label, run}` action button; deleting hides the chain at once and calls `delete` only when the 6-second toast ends without Undo.
- [ ] **Step 6: Check in the browser pane** with the devserver and a temp FXChains folder holding a sample chain: list, apply (FakeReaper or real), save, build, rename, return switch, hide, delete + undo, keyboard focus visible, light/dark themes. Full suite green.
- [ ] **Step 7: Commit** (with approval): `Chains view`.

### Task 8: Help: "?" on each page and a refreshed tour

**Files:**
- Modify: `studio_hub/ui/app.js`, `studio_hub/ui/tour.js`, `studio_hub/ui/styles.css`, `studio_hub/ui/index.html`

**Interfaces:**
- Produces: `HELP` text keyed by page (`library` for All plugins, categories and developers; `favourites`; `recent`; `chains`; `settings`).

- [ ] **Step 1:** A small `?` button (`.help-btn`, greyed until hover/focus, `aria-describedby` → a `role="tooltip"` popover) beside `#view-title`, and one in the Settings sheet header. Shows on hover and on keyboard focus; Esc hides it. Copy:
  - library: "Every plugin REAPER has scanned, with a picture of each. Double-click one to put it on the selected track. Drag a card onto a category to move it."
  - favourites: "Plugins you've starred. Select one and press F to star or unstar it. The chips narrow it down by category."
  - recent: "The last plugins you added from Ordel, newest first."
  - chains: "Save a chain from the selected REAPER track. Click a chain to put it on the selected track. Turn on 'Use as return track' to make it a send."
  - settings: "Themes, your shortcut, pictures and the REAPER connection. New plugin not showing? Restart REAPER so it scans it, then refresh."
- [ ] **Step 2:** `TOUR_STEPS`: keep five or six steps. Replace "Browse your way" body to also mention versions ("Plugins with Mono or sidechain versions show once; pick the version from the card."), and add a step targeting the Chains sidebar item: title "Chains in one click", body "Save the plugins on a REAPER track as a chain, then put them on any track, or on a new return track, with one click." Replay stays in Settings.
- [ ] **Step 3: Check in the browser pane:** each page's "?" text, hover and focus, tour runs start to finish and skips cleanly, nothing overlaps at the 900×600 minimum size.
- [ ] **Step 4: Commit** (with approval): `Page help and refreshed welcome tour`.

### Task 9: New-plugin notice

**Files:**
- Modify: `studio_hub/library.py` (top-level `seen: list[str] | None` in `library.json`), `studio_hub/api.py`, `studio_hub/ui/app.js`, `studio_hub/ui/index.html`, `studio_hub/ui/styles.css`
- Test: `tests/test_library.py`, API test file

**Interfaces:**
- Produces: `Library.seen() -> set[str] | None` (None when never recorded); `Library.mark_seen(ids: set[str]) -> None`. `Api.state()["new_plugins"]: list[str]` (group ids not seen). `capture_action("capture_new")` starts capture of exactly those ids and marks them seen; `capture_action("dismiss_new")` marks them seen.

- [ ] **Step 1: Write the failing tests:** first ever state (and first state after upgrading, i.e. no `seen` key) marks everything seen and reports `[]`; a plugin added to the fixture afterwards appears in `new_plugins`; `capture_new` starts the runner with only that id; `dismiss_new` clears it; a version added to an existing group doesn't count as new (only group ids are tracked).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** UI: a single quiet line (new `#notice` element under `#banner`, no animation beyond the existing fade): "2 new plugins found · Capture pictures" with a close button. "Capture pictures" works without REAPER too: VST3s go through the helper, and the rest are counted by the existing `needs_reaper` message.
- [ ] **Step 4: Run** the full suite; check the line in the browser pane.
- [ ] **Step 5: Commit** (with approval): `Notice when new plugins are found`.

### Task 10: Finish

- [ ] **Step 1:** Full suite: `.venv\Scripts\python.exe -m pytest -q`. Expected: all pass.
- [ ] **Step 2:** Ask Charlie to quit Ordel (or use `POST /api/window {"action":"quit"}`), rebuild with `powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\build.ps1`, and ask Charlie to start `dist\Ordel\Ordel.exe` from File Explorer.
- [ ] **Step 3:** With Charlie's REAPER: save a real vocal chain, apply it to two tracks, apply the Plate return twice (second shows the "already exists" message), pick Pro-C 2 Mono from its card, check the "?" texts and the tour.
- [ ] **Step 4:** Whole-branch review, then commit any fixes (with approval).
