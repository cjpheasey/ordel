# Ordel: chains, grouped variants, help and new-plugin notice

Date: 2026-11-04. Status: ready for Charlie's review.

## Why

Ordel is a visual plugin library for REAPER (Windows only, REAPER only). Charlie, a mixing engineer, is
building it for their own mixing, their CV, and eventually for other producers to download.

What success sounds like, in their words: a producer who tries it says it "made their mixing workflow more
streamlined" and that they "learned the UI extremely quickly". Every feature below must serve one of those
two, without making the app feel cluttered or "vibe-coded" (premium, calm, Apple-inspired minimalism is the
house style; see `brand/GUIDELINES.md` and the existing UI).

Charlie's mix-start routine, which these features shorten:
1. Arrange tracks into groups and colour-code them (stays in REAPER, out of scope).
2. Rough mix with volume and panning (out of scope).
3. Set up their standard effect returns straight away: short room reverb, medium plate, large hall,
   short slapback delay, New York compression bus.
4. Put their usual chains on tracks, e.g. their vocal chain.

## Goals (this round)

1. **Chains**: saved groups of plugins that go onto REAPER in one click, either on the selected track or
   on a new return track (for sends).
2. **Grouped variants**: a plugin with Stereo / Mono / Sidechain / multi-output versions shows once, and
   the version is picked from it.
3. **Help**: a refreshed, brief first-run welcome tour, plus a quiet "?" on each page with a hover summary.
4. **New-plugin notice**: a subtle prompt when Ordel finds plugins it hasn't seen before.

## Non-goals (later, or never)

- Notes and tags on plugins; a "never used" view (later).
- Installer, download page, finding REAPER outside `C:\Program Files\REAPER (x64)` (later, before release).
- Automatically capturing pictures of new plugins. Charlie decided capture stays manual; Ordel only
  suggests it.
- Grouping or colour-coding the user's own tracks, mixing volume/pan.
- Supporting DAWs other than REAPER.

## Anti-goals

- Anything that pops up over the user's work or nags them.
- Help that clutters the clean look (big banners, permanent hint text).
- Losing or silently changing the user's data: favourites, recent use, category overrides, pictures,
  REAPER projects, REAPER settings.

## 1. Chains

### What the user sees

- A **Chains** entry in the sidebar, next to Favourites and Recently used. It lists the user's chains
  (expected to be a handful: vocal, drums, bus, the five returns, not dozens).
- **Chains already saved in REAPER are shown too** (Charlie's decision): every `.RfxChain` file in REAPER's
  `FXChains` folder (including subfolders) appears and can be applied straight away, alongside chains made
  through Ordel.
- Each chain shows its name and its plugins in order (using their pictures).
- **Click a chain** to put it on the selected REAPER track, after any plugins already there.
- A chain can be marked **"Use as return track"** (a switch on the chain). Applying it then creates a new
  track at the end of the project, named after the chain and given a colour, with the chain on it, instead
  of using the selected track. This is how the reverb/delay/NY-compression returns are set up.
  - **Ordel only creates the return track** with the chain on it; it does not create sends (Charlie's
    decision). The user routes sends themselves.
  - **Applying it again makes another return track** (Charlie's decision), and Ordel tells the user, e.g.
    "A Plate return already exists in this project. Added another." "Already exists" means a track in the
    current project with the same name as the chain (my call: matched by name).
- Two ways to make a chain (Charlie: "both should be available"; which is primary is my call):
  - **Save from REAPER (primary)**: the user sets up plugins on a track the way they like, selects the
    track, and chooses "Save as chain" in Ordel. Plugins **and their settings** are saved.
  - **Build in Ordel (secondary)**: the user picks plugins from the library into an ordered list. These
    plugins come in at default settings. Such a chain can later be overwritten by saving from REAPER once
    its settings are dialled in.
- Chains can be renamed, reordered (the list), edited (plugins added/removed/reordered for built chains),
  and deleted (with an undo toast, never a hard delete without a way back).
- A chain **remembers the exact plugin version** it was given (Charlie: "it should remember what version
  you picked"), e.g. the Mono de-esser stays Mono.

### Decided how

- **Storage (my call)**: a chain saved from REAPER is stored as a standard REAPER `.RfxChain` file in
  REAPER's own `FXChains\Ordel\` folder, so it also works in REAPER's own FX browser and survives if Ordel is
  removed. Ordel keeps its own list (name, order, return-track switch, colour, plugin list for display) in
  its data. Chains built in Ordel have no settings to save yet, so Ordel keeps them as a list of plugin
  versions in its own data and adds them one by one; saving one from REAPER later turns it into a file.
- Applying goes through the existing Lua bridge (file IPC, a new verb), not by driving REAPER's UI.
- Applying must be undoable in REAPER as one step ("Ordel: add chain Vocal").
- A chain referring to a plugin that is no longer installed still applies the rest and says which one was
  missing.
- **Several selected tracks (my call)**: a normal chain goes onto every selected track, as one undo step,
  so a drum chain can go on all the drum tracks at once. The "Added to ..." message says how many.
- **Source of truth (my call)**: the `FXChains` folder is the truth for which chains exist, so chains
  added, renamed or removed in REAPER show up in Ordel on its next refresh. Ordel keeps only its extras
  (order, "Use as return track", colour) keyed by the file's path; extras for a vanished file are dropped.
- **Plugin pictures for REAPER's own chains (my call)**: Ordel reads which plugins a chain contains from
  the file and shows their pictures; plugins it can't match show as a plain tile with the name.
- **Deleting (my call)**: only chains made through Ordel (in `FXChains\Ordel\`) can be deleted from
  Ordel; after the undo toast expires their file goes to the Recycle Bin, never a permanent delete.
  Chains the user made in REAPER can be **hidden** from Ordel but are never deleted by it.

### Left to the builder

- The exact bridge verbs and how the chain is inserted (state chunk vs. REAPER's own chain loading).
- The colour given to return tracks and how it is chosen.
- How the chain editor looks, within the existing sheet/side-panel patterns.

## 2. Grouped variants

### What the user sees

- Plugins that are versions of one another appear as **one card** in the library, with one picture.
  Examples in Charlie's library: FabFilter Pro-C 2 / Pro-C 2 (Mono); Volcano 2 / (Mono) / (SC) / (Mono SC);
  instruments with "(32 out)" style multi-output versions.
- The card shows a small, quiet hint of the versions (e.g. "Stereo · Mono").
- Double-click (the existing "add" gesture) adds the version the user picks most often for that plugin
  (default: the plain stereo version). Clicking the hint shows the versions to choose from.
- Favourites and Recently used follow the group: starring Pro-C 2 stars the plugin, whichever version.
- Search finds the group by any version's name.

### Decided how

- Grouping is by name: same developer, same name once variant suffixes are removed. Suffixes to recognise:
  Mono, Stereo, SC / Sidechain, Mono SC, multi-output "(N out)" / "(Nch)". Plugins that merely share a
  word ("Pro-Q 3" vs "Pro-Q 4") are not grouped.
- VST3/VST2/CLAP duplicates are already merged today (VST3 preferred); that stays as it is.

### Must not break

- Existing favourites, recent use, category overrides and pictures are stored per plugin id today
  (`library.json`). After grouping, nothing the user set may disappear: e.g. if only the Mono version was
  starred, the group shows as starred; the group uses the best existing picture.
- Capture keeps taking one picture per group (the main version), not one per variant.

## 3. Help

### Welcome tour

- Ordel already has a five-step first-run tour (`studio_hub/ui/tour.js`). Keep it brief (five or six steps
  at most), update it to introduce chains and grouped versions, keep it skippable, and make it replayable
  from Settings.

### "?" on each page

- A small question-mark icon at the top of each page, greyed until hovered, matching the existing icon set.
- Hovering (or keyboard focus) shows two or three short lines: what the page does and its handy tricks.
- Pages: the library (also used for category and developer views), Favourites, Recently used, Chains,
  Settings. Example for Chains: "Save a chain from the selected REAPER track. Click a chain to put it on the
  selected track. Turn on 'Use as return track' to make it a send."
- Copy is plain English for producers, no developer jargon.

## 4. New-plugin notice

- When Ordel reads REAPER's plugin list (at start, and whenever it refreshes it) and finds plugins it has
  never seen before, it shows one small, quiet line near the top: "2 new plugins found · Capture pictures".
- Clicking it captures pictures of just those plugins. It disappears once they are captured or when the
  user dismisses it. It never covers the user's work.
- Not shown on the very first run (onboarding already handles capturing everything), nor on the first
  launch after updating to this version: plugins installed by then count as already seen (my call).
- The "?" help or the notice explains the catch: Ordel only sees plugins REAPER has scanned, so a newly
  installed plugin may need REAPER restarted (or rescanned in its preferences) first.

## Constraints

- Everything must work for other users with no manual setup, on Windows, with REAPER only.
- Ask before every commit (Charlie approves each). Never push unasked.
- Never force-close the user's REAPER; never permanently delete user data.
- The existing capture safety (plugins opened in their own process, unsaved-work check) stays intact.
- Tests accompany new logic (pytest; the Lua bridge is tested with lupa).
