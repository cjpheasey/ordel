# Ordel: subgroups and character within groups

Date: 2026-11-20. Status: ready for Charlie's review.

## Why

Ordel's groups (EQ, Dynamics, Reverb…) are too broad once a library is large: Dynamics holds compressors,
limiters, de-essers, gates and more. Charlie wants to narrow a group first by what a plugin does (compressor,
limiter, de-esser), and then, where it matters, by its character (VCA, FET, optical, tube). This must work
without the user sorting everything by hand, while letting them correct anything Ordel gets wrong.

## Goals

1. **Subgroups** inside each group, shown in the sidebar under the group (layout "A", chosen by Charlie).
2. **Character** within subgroups where it matters (first: compressors), shown as chips above the cards.
3. **Automatic sorting** into subgroups and character, from REAPER's developer tags, name clues and a
   built-in list of well-known plugins.
4. **Correcting by drag and drop**, with a label while hovering ("Move to Limiters").
5. **Honest messaging** that sorting is automatic and may need correcting.

## Non-goals

- Sorting by sound or by analysing audio.
- Subgroups for groups you make yourself (custom categories stay as they are; Charlie can ask later).
- Writing to REAPER's FX folders.
- An online or AI lookup of plugins.

## Anti-goals

- A busy screen: never more than one row of chips at a time.
- Ordel overriding a choice the user made by hand.
- Claiming accuracy it doesn't have.

## 1. What the user sees

### Sidebar

- Clicking a group that has subgroups opens it in place: its subgroups are listed under it, indented, each
  with a count. Clicking the group itself still shows everything in it ("All" for that group).
- Only the open group shows its subgroups; others stay collapsed. A subgroup with no plugins is hidden.
- The group's colour dot stays on the group line; subgroups have no dot.
- Plugins Ordel can't place in a subgroup go in the group's **Other** subgroup.

### Chips (one row)

- Inside a subgroup that has character (first: Compressors), the chips are the character values with counts:
  All · VCA · FET · Optical · Tube · Diode bridge · Digital. Click one to narrow; All clears it.
- Elsewhere, the chip row works as today.
- The developer chips that appear today inside a group move into a small **Developer** menu at the right of
  the chip row, so the row never doubles up. (The developer chips on Favourites/Recently used stay as they
  are.)

### Cards and details

- A card's sub-line can show its character next to the developer when it has one (e.g. "Universal Audio · FET").
- The details panel gains **Type** (the subgroup) and, where relevant, **Character**, each a menu like
  Category is today, with "Sorted by Ordel" or "Sorted by you" under the group and a **Use detected** link
  when the user has changed it.

### Drag and drop

- Drag a card onto a **group** in the sidebar: it moves to that group; its subgroup is detected within it.
- Onto a **subgroup**: it moves to that group and subgroup.
- Onto a **character chip**: its character changes.
- Onto **Favourites**: it's starred.
- While hovering, the target highlights and a small label appears beside it: **"Move to Limiters"**,
  **"Mark as FET"**, **"Add to Favourites"**. "Move", because a plugin is in exactly one group.
- REAPER folders and Chains don't accept drops (no label, no highlight).
- A toast confirms the drop, as today ("Moved Pro-L 2 to Limiters").

### Messaging

- Tour: the step about the sidebar adds: *"Ordel sorts plugins using what developers tell REAPER, plus its
  own knowledge of well-known plugins. It won't get every one right: drag a plugin onto any group to move it,
  and Ordel remembers."*
- "?" help on group pages adds: *"Sorted automatically. Something in the wrong place? Drag it onto the right
  group."*
- Details panel: "Sorted by Ordel" / "Sorted by you" (above).

## 2. Subgroups and character, per group (first version)

Groups not listed have no subgroups yet. Every listed group also has **Other**. These lists are my call.

| Group | Subgroups | Character |
|---|---|---|
| Dynamics | Compressors, Limiters, De-essers, Gates & expanders, Multiband, Transient shapers, Other | Compressors: VCA, FET, Optical, Tube, Diode bridge, Digital |
| EQ | Parametric, Dynamic EQ, Pultec-style, Console-style, Graphic, Other | — |
| Reverb | Plate, Room, Hall, Chamber, Spring, Shimmer & ambient, Convolution, Other | — |
| Delay | Tape, Analog, Digital, Other | — |
| Modulation | Chorus, Flanger, Phaser, Tremolo & vibrato, Other | — |
| Saturation | Tape, Tube, Console & transformer, Distortion & fuzz, Lo-fi, Other | — |
| Instruments | Synths, Samplers, Drums, Keys, Orchestral, Other | — |

The lists live in one place in the code so more groups or values can be added later.

## 3. How Ordel decides (in this order)

1. **What the user set** (subgroup and character are remembered per plugin, like category today).
2. **Built-in list** of well-known plugins (a data file shipped with Ordel): plugin name and developer →
   subgroup and character, e.g. "1176" family → Compressors / FET, "LA-2A" → Compressors / Optical,
   "Lindell 254E" → Compressors / Diode bridge, "Pro-L 2" → Limiters. A few hundred entries to start, covering
   the most common developers (Universal Audio, Waves, Plugin Alliance/Brainworx, FabFilter, Slate Digital,
   Softube, Arturia, Soundtoys, Valhalla, iZotope, Cockos). Built from general knowledge; not exhaustive.
3. **Name clues**: words in the name ("limit", "gate", "de-ess", "esser", "multiband", "transient", "plate",
   "spring", "tape", "chorus"…, and hardware names like 1176, LA-2, Fairchild, Pultec, SSL).
4. **REAPER's developer tags**, where they say more than the group (some do, e.g. "Compressor", "Limiter").
5. Otherwise **Other**, and no character.

**The built-in list can move a plugin to another group** (Charlie's decision), e.g. a limiter REAPER tags
"Mastering" goes to Dynamics → Limiters. So for the group, the order is: what the user set, then the
built-in list, then REAPER's tags, then name clues (today's order). Nothing stored is changed on upgrade, but
some plugins' detected group changes, so they may appear in a new group after updating; anything the user
moved by hand stays put. The details panel's "Detected as …" / "Use detected" uses the new detection.

**Charlie reviews the built-in list before it ships** (Charlie's decision, option A). It is built as a full
list (a few hundred entries), then shown to Charlie on a simple review page (plugin, developer, proposed
group, subgroup, character), where he corrects or removes entries. Only the reviewed list ships. This review
is its own step in the build, with a checkpoint.

Measured on Charlie's library: name clues alone placed 12 of 36 Dynamics plugins; with subgroup clues and the
built-in list, the estimate is around 30 of 36.

### When the group changes (my call)

- A subgroup belongs to its group and a character to its subgroup. When the user moves a plugin to another
  group (drag, the Category menu, "Use detected", or deleting a custom category it was in), its subgroup and
  character are detected afresh within the new group. That isn't Ordel overriding the user: the user just
  made the move.
- Changing the Type so a plugin leaves Compressors drops its character, since it no longer applies.
- "Sorted by you" shows when the user set any of group, subgroup or character by hand.

## 4. Constraints

- Everything must keep working for existing users: their category choices, favourites, pictures and
  custom categories are untouched. Subgroup and character are new, optional data per plugin.
- A plugin's group, subgroup and character are a group-level choice (all its versions — Mono, Stereo — share
  them), like category today.
- Plain English in the interface; no jargon beyond common studio terms (VCA, FET, plate…).
- Tests with every piece of logic; ask Charlie before every commit; commits credit only Charlie (no co-author
  lines).

## 5. Left to the builder

- Exact styling of the open group, the hover label and the Developer menu, within Ordel's existing look.
- The data file's format and where it lives in the package.
- How name clues and the built-in list are matched (e.g. by plugin name with or without developer).
- Keyboard access for the new controls, matching the rest of the app.
