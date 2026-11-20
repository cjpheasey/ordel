# Subgroups and character: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subgroups inside Ordel's groups (sidebar), character chips inside subgroups (first: compressors), automatic sorting from a reviewed built-in list plus name clues, drag-and-drop correction with hover labels, and honest messaging.

**Architecture:** A new `studio_hub/subgroups.py` holds the subgroup/character definitions and the detection (built-in list → REAPER tags → name clues → Other). The built-in list is a JSON data file Charlie reviews before it ships. `library.py` stores hand-set subgroup/character per plugin next to category and merges them across versions; `api.py` validates and exposes them. The UI opens the selected group's subgroups in the sidebar, shows character chips, moves developer chips into a menu, and extends drag and drop.

**Tech Stack:** Python 3.13, pytest, vanilla JS/CSS, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-11-20-subgroups-design.md`

## Global Constraints

- Existing users' data is untouched on upgrade: stored categories, favourites, pictures and custom categories stay as they are; subgroup and character are new optional per-plugin fields.
- A plugin's group, subgroup and character are a group-level choice shared by all its versions (Mono/Stereo), like category today.
- Priority for the group: what the user set → built-in list → REAPER's tags → name clues (today's order for the last two).
- Never more than one row of chips at a time.
- Custom categories have no subgroups.
- REAPER folders and Chains accept no drops.
- UI copy is plain English (studio terms like VCA, FET, plate are fine); exact messaging copy is in the spec, section 1 "Messaging".
- Ask Charlie before every commit. Commits credit only Charlie: no Co-Authored-By lines.
- Full suite: `.venv\Scripts\python.exe -m pytest -q` stays green after every task.

## Review Focus

1. A user who moved a plugin to a group by hand before upgrading: it stays in that group, and its subgroup is detected inside it. Test: Task 4 `test_hand_set_group_survives_and_gets_a_subgroup_inside_it`.
2. A plugin in a custom category: no subgroup, no character, nothing breaks. Test: Task 4 `test_custom_category_has_no_subgroup`.
3. Setting a subgroup on a group with Mono/Stereo versions applies to the whole card. Test: Task 4 `test_subgroup_set_on_a_group_covers_its_versions`.
4. A plugin in a group with no subgroups (e.g. Filter): subgroup is null everywhere. Test: Task 1 `test_groups_without_subgroups_give_none`.
5. A compressor with a hand-set character whose type is changed to Limiters: the character is dropped. Test: Task 4 `test_leaving_compressors_drops_the_character`.

---

### Task 1: Subgroup definitions and name-clue detection

**Files:**
- Create: `studio_hub/subgroups.py`
- Test: `tests/test_subgroups.py`

**Interfaces:**
- Produces:
  - `SUBGROUPS: dict[str, list[dict]]` — group key → ordered subgroups `{"key": str, "label": str, "characters": list[{"key","label"}]}` (empty list when no character). Exactly the spec's section 2 table; keys: dynamics → `compressors, limiters, deessers, gates, multiband, transient, other`; eq → `parametric, dynamic, pultec, console, graphic, other`; reverb → `plate, room, hall, chamber, spring, shimmer, convolution, other`; delay → `tape, analog, digital, other`; modulation → `chorus, flanger, phaser, tremolo, other`; saturation → `tape, tube, console, distortion, lofi, other`; instruments → `synths, samplers, drums, keys, orchestral, other`. Compressors' characters: `vca VCA, fet FET, optical Optical, tube Tube, diode "Diode bridge", digital Digital`.
  - `subgroup_from_name(group: str, name: str, reaper_tags: list[str]) -> str | None` — name clues, then REAPER tags; `"other"` when the group has subgroups and nothing matched; `None` when the group has none.
  - `character_from_name(name: str) -> str | None` — hardware-name clues for compressors (1176/FET → fet, LA-2/LA-3/opto → optical, Fairchild/670/vari-mu/tube → tube, SSL/bus comp/VCA/dbx/160/2500 → vca, 2254/254 → diode).

- [ ] **Step 1: Write the failing tests** — `test_dynamics_subgroups_from_name_clues` (Pro-L 2 → limiters, Pro-G → gates, Pro-DS → deessers, "RDeEsser" → deessers, Pro-MB → multiband, "kHs Transient Shaper" → transient, "UADx 1176AE Compressor" → compressors, "soothe2" → other); `test_reverb_and_saturation_clues` ("ValhallaPlate" → plate, "Spring Reverb" → spring, "Oxide Tape Recorder" in saturation → tape); `test_character_from_hardware_names` ("UADx 1176LN Rev E" → fet, "UADx LA-2A Gray" → optical, "Fairchild 670" → tube, "SSL G-Master Buss Compressor" → vca, "Lindell 254E" → diode, "FabFilter Pro-C 2" → None); `test_groups_without_subgroups_give_none` (`subgroup_from_name("filter", "Pro-Q 3", [])` is None).
- [ ] **Step 2: Run** `.venv\Scripts\python.exe -m pytest tests/test_subgroups.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** in `studio_hub/subgroups.py`: regex lists per group checked in table order (more specific first, e.g. multiband before compressors, deesser before compressors).
- [ ] **Step 4: Run** the file, then the full suite. Expected: PASS.
- [ ] **Step 5: Commit** (with approval): `Subgroups and compressor character, detected from names`.

### Task 2: Draft built-in list and its use in detection

**Files:**
- Create: `studio_hub/data/known_plugins.json`, `studio_hub/data/__init__.py` (empty, so it ships as package data)
- Modify: `studio_hub/subgroups.py`, `studio_hub/library.py` (`view()` uses `detect`), `packaging/studio_hub.spec` (add `studio_hub/data`)
- Test: `tests/test_subgroups.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - JSON format: list of `{"name": str, "developer": str | null, "group": str, "subgroup": str, "character": str | null}`; `name` is a case-insensitive substring of the plugin's name (e.g. `"1176"`), `developer` a case-insensitive substring of its vendor (null = any).
  - `detect(name: str, vendor: str, reaper_tags: list[str], instrument: bool, known: list[dict] | None = None) -> dict` → `{"group": str, "subgroup": str | None, "character": str | None}`. Order: first matching known entry (longest `name` wins) → else group = `resolve_category(...)`, subgroup = `subgroup_from_name`, character = `character_from_name` only when subgroup is `compressors`. `known=None` loads the shipped file once.
  - `library.view()` uses `detect(...)["group"]` as `category_auto`.

- [ ] **Step 1: Write the failing tests** — `test_known_list_beats_reaper_tags` (entry `{"name":"Pro-L 2","developer":"FabFilter","group":"dynamics","subgroup":"limiters"}` and tags `["Mastering"]` → dynamics/limiters); `test_longest_match_wins` ("1176" vs "1176 Rev A" entries); `test_no_match_falls_back_to_tags_then_names`; `test_shipped_list_is_valid` (every entry's group/subgroup/character exists in `SUBGROUPS`, no duplicate name+developer).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `detect` and its loader (read via `paths.resource("studio_hub/data/known_plugins.json")`, which resolves from the repo root or PyInstaller's bundle).
- [ ] **Step 4: Draft the list**: a few hundred entries for the spec's developers (Universal Audio, Waves, Plugin Alliance/Brainworx, FabFilter, Slate Digital, Softube, Arturia, Soundtoys, Valhalla, iZotope, Cockos), plus every plugin in Charlie's own library that names don't settle (check with a quick script against `load_plugins(%APPDATA%\REAPER)`). Mark nothing as certain; Task 3 is the review.
- [ ] **Step 5: Run** the full suite. Expected: PASS. Report the share of Charlie's Dynamics plugins now placed in a subgroup other than Other (spec estimate: ~30 of 36).
- [ ] **Step 6: Commit** (with approval): `Built-in list of well-known plugins (draft)`.

### Task 3: Review page and Charlie's review (checkpoint)

**Files:**
- Create: `scripts/review_known_plugins.py` (dev tool, not shipped)
- Modify: `studio_hub/data/known_plugins.json` (Charlie's corrections)

**Interfaces:**
- Consumes: Task 2's JSON format.
- Produces: the reviewed `known_plugins.json`.

- [ ] **Step 1:** `scripts/review_known_plugins.py` writes a self-contained HTML page to the scratchpad: a table (plugin, developer, group, subgroup, character) with dropdowns for group/subgroup/character, a remove tick per row, entries in Charlie's library highlighted, and an "Export" button that downloads the edited list as JSON. Plain, readable, works offline.
- [ ] **Step 2:** Open it in the browser pane and send it to Charlie. **Stop until Charlie returns the exported file.**
- [ ] **Step 3:** Replace `known_plugins.json` with Charlie's export; `test_shipped_list_is_valid` passes.
- [ ] **Step 4: Commit** (with approval): `Built-in plugin list, reviewed`.

### Task 4: Store and serve subgroup and character

**Files:**
- Modify: `studio_hub/library.py`, `studio_hub/api.py`, `studio_hub/server.py`
- Test: `tests/test_library.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: `detect`, `SUBGROUPS`.
- Produces:
  - `Library.set_subgroup(plugin_id, key | None, also=())`, `Library.set_character(plugin_id, key | None, also=())` (stored per plugin like `category`; `also` clears versions).
  - `Library.set_category(...)` additionally clears stored `subgroup` and `character` for the plugin and `also` (the user moved it: detect afresh in the new group).
  - `view()` entries gain `subgroup`, `subgroup_auto`, `character`, `character_auto`, `sorted_by` (`"you"` if any of category/subgroup/character is hand-set, else `"ordel"`). Effective subgroup: hand-set if it belongs to the effective group, else detected within that group (`subgroup_from_name` when the group differs from the detected one); `None` for groups without subgroups and custom categories. Effective character only when subgroup is `compressors`.
  - `Api.update_plugin(id, favourite=None, category=_UNSET, subgroup=_UNSET, character=_UNSET)`: `ValueError` if `subgroup` doesn't belong to the plugin's effective group or `character` doesn't belong to its subgroup; setting a subgroup other than compressors also clears character. `/api/plugin` passes `subgroup` and `character`.
  - `Api.state()["subgroups"] = SUBGROUPS`.

- [ ] **Step 1: Write the failing tests** — `test_hand_set_group_survives_and_gets_a_subgroup_inside_it`; `test_custom_category_has_no_subgroup`; `test_subgroup_set_on_a_group_covers_its_versions`; `test_leaving_compressors_drops_the_character`; `test_moving_group_detects_subgroup_afresh`; `test_subgroup_must_belong_to_the_group` (API 400); `test_sorted_by_you_after_any_hand_change`; `test_existing_library_json_loads_unchanged` (a library.json without the new fields reads and saves without losing anything).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** (with approval): `Keep each plugin's subgroup and character`.

### Task 5: Sidebar subgroups, character chips, Developer menu

**Files:**
- Modify: `studio_hub/ui/app.js`, `studio_hub/ui/styles.css`

**Interfaces:**
- Consumes: view fields and `state.subgroups` (Task 4).
- Produces: view keys `sub:<group>/<subgroup>`; `S.character` (chip filter); `S.developer` (menu filter).

- [ ] **Step 1:** When the current view is `cat:<g>` or `sub:<g>/…` and `g` has subgroups, render its subgroups indented under the group in `renderSidebar` with counts; hide empty ones; other groups stay collapsed.
- [ ] **Step 2:** `inView` handles `sub:`; `viewTitle` shows the subgroup label; chips: in `sub:dynamics/compressors` the chips are characters with counts (`S.character`), elsewhere inside a group the developer chips are replaced by a "Developer" menu (`S.developer`) at the right of the chip row; Favourites/Recently used keep their chips. `setView` clears `S.character` and `S.developer`. Startup fallback regex includes `sub`.
- [ ] **Step 3:** Card sub-line shows `Developer · Character` when a character is set.
- [ ] **Step 4: Check in the browser pane** (devserver) with Charlie's library: Dynamics opens into its subgroups; Compressors → FET shows the 1176s; Developer menu narrows; one chip row at a time; light and dark themes; 900×600.
- [ ] **Step 5: Commit** (with approval): `Subgroups in the sidebar and character chips`.

### Task 6: Details panel and drag and drop

**Files:**
- Modify: `studio_hub/ui/app.js`, `studio_hub/ui/styles.css`

**Interfaces:**
- Consumes: Tasks 4–5.

- [ ] **Step 1:** Details: **Type** menu (the group's subgroups) and **Character** menu (only for compressors) under Category; "Sorted by Ordel" / "Sorted by you" under Category; "Use detected" resets category, subgroup and character together.
- [ ] **Step 2:** Drag targets: group (`cat:` → `{category}`), subgroup (`sub:` → `{category, subgroup}`), character chip (→ `{character}`), Favourites (→ `{favourite: true}`); REAPER folders and Chains show nothing. While hovering, a small label beside the target: "Move to <label>", "Mark as <character>", "Add to Favourites". Toast after drop as today ("Moved … to …", "Marked … as FET", "Added … to Favourites").
- [ ] **Step 3: Check in the browser pane:** each drop target, its label and toast; dropping on REAPER folders/Chains does nothing; keyboard users can still set everything from the details menus.
- [ ] **Step 4: Commit** (with approval): `Drag plugins onto subgroups and characters`.

### Task 7: Messaging, rebuild and real check

**Files:**
- Modify: `studio_hub/ui/tour.js`, `studio_hub/ui/app.js` (HELP text)

- [ ] **Step 1:** Tour "Browse your way" step and the HELP text for group pages get the spec's exact sentences (section 1 "Messaging").
- [ ] **Step 2:** Full suite; rebuild with `packaging\build.ps1` (Charlie runs it in their own terminal if the installer step is blocked from here); Charlie installs and checks: Dynamics subgroups, Compressors → FET, a drag onto Limiters with its label, the tour sentence.
- [ ] **Step 3: Commit** (with approval): `Explain automatic sorting`. Push only if Charlie asks.
