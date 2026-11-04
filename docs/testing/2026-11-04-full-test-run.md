# Ordel full test run, 2026-11-04

Every feature, how it is tested, and the result. **Who:** A = automated tests, R = code review,
U = UI sweep in the browser pane, Q = real REAPER through Ordel, C = Charlie by hand.

Result: ✅ pass · ❌ bug (see Bugs) · ⏳ not run yet · ➖ not applicable

## App shell
| # | Feature | Who | Result |
|---|---|---|---|
| 1 | Starts, one copy only (second launch brings the first forward) | C | ✅ (Charlie) |
| 2 | Global shortcut shows/hides Ordel, including from inside REAPER | C | ✅ (Charlie) |
| 3 | Changing the shortcut; a shortcut another app owns is refused with a message | C, A | ✅ (Charlie) |
| 4 | Tray icon: show, hide, quit; right icon for light/dark taskbar | C | ✅ (Charlie) |
| 5 | Title bar: drag to move, minimise, close (hides to tray) | C | ✅ (Charlie) |
| 6 | Resize from every edge and corner; minimum size 900×600 | C, A | ✅ (Charlie) |
| 7 | Window size and position remembered; off-screen positions ignored | C, A | ✅ (Charlie) |
| 8 | "Hide after adding" setting | Q | ✅ |
| 9 | Quit from Settings | C | ✅ (Charlie) |

## Library
| # | Feature | Who | Result |
|---|---|---|---|
| 10 | Reads VST, VST3, CLAP from REAPER's lists; format duplicates merged | A, Q | ✅ |
| 11 | Grouped versions (FabFilter, Waves, multi-output) | A, U | ✅ |
| 12 | Categories: auto, override, drag a card onto a category, "Use detected" | A, U | ✅ |
| 13 | Developers view and chips (by category / developer) | U | ✅ |
| 14 | Search: box and type-anywhere, by name, developer, category, version | U | ✅ |
| 15 | Favourites (button and F), Recently used (newest first, max 30) | U, Q | ✅ |
| 16 | Picture size slider (remembered), keyboard arrows and Enter | U | ✅ (slider hides below 1000 px wide, by design) |
| 17 | Empty states (no plugins, no results, no favourites, empty category) | U | ✅ |
| 18 | Refresh plugin list | Q | ✅ |

## Adding to REAPER
| # | Feature | Who | Result |
|---|---|---|---|
| 19 | Double-click / Enter / "Add to track" puts the plugin on the selected track | Q | ✅ |
| 20 | Chosen version (Mono etc.) is the one added; usual version remembered | Q | ✅ |
| 21 | No track selected → "Select a track in REAPER first" | Q | ✅ |
| 22 | REAPER closed → clear message | Q | ✅ (Charlie) |
| 23 | One Ctrl+Z removes the add | Q | ✅ |

## Pictures
| # | Feature | Who | Result |
|---|---|---|---|
| 24 | First-run capture of everything; progress bar; pause, resume, stop | Q | ✅ (Charlie) |
| 25 | VST3 through the helper process | Q | ✅ |
| 26 | VST/VST3 through REAPER in a dedicated process; setting restored | Q | ✅ |
| 27 | CLAP: only with saved work; message when unsaved | Q | ✅ |
| 28 | Retake one picture; use my own image | Q, C | ✅ (Charlie) |
| 29 | Waits while REAPER is playing (was: refused with the wrong message) | Q | ✅ after fix |
| 30 | A crash marks the plugin and capture carries on; a slow REAPER isn't mistaken for a crash | R, A | ✅ after fix (I8) |

## Chains
| # | Feature | Who | Result |
|---|---|---|---|
| 31 | Save from selected track (settings kept) | Q | ✅ (earlier today) |
| 32 | Apply to all selected tracks; existing FX untouched; one undo | Q | ✅ (earlier today) |
| 33 | Return track; "already exists" note | Q | ✅ (earlier today) |
| 34 | Build in Ordel; add/remove/reorder plugins; versions | U, Q | ✅ |
| 35 | Rename, move in list, hide/show, delete + undo, replace (Recycle Bin backup) | U, Q | ✅ |
| 36 | Track with input FX | Q | ✅ |
| 37 | Track with a heavy instrument already loaded | Q | ✅ (Kontakt 7: same instance, not reloaded) |
| 38 | Chain with a container / parameter modulation | Q | ✅ (setting inside the container kept) |
| 39 | JS-only chain; chain with a missing plugin | Q | ✅ (missing plugin named; no REAPER pop-up; JS names fixed) |
| 40 | Chains saved in REAPER itself appear | Q | ✅ |

## Help, notice, settings, REAPER connection
| # | Feature | Who | Result |
|---|---|---|---|
| 41 | "?" on each page; welcome sheet; tour (skip, back, replay) | U | ✅ |
| 42 | New-plugin notice: appears, captures, dismisses | A, U | ✅ |
| 43 | Themes, accents, picture fit, density, corners, developer names, reset | U | ✅ |
| 44 | Connect REAPER (open / closed / reopen) | Q | ✅ (earlier today) |
| 45 | Script updates itself after an Ordel update | A | ✅ |
| 46 | Local server refuses other websites | A, R | ✅ |

## Bugs found
| # | Where | What | Grade | Status |
|---|---|---|---|---|
| B1 | Chains details, Light theme | The orange "Not installed" label is faint on white | Minor | fixed |
| B2 | Settings → REAPER | When already connected the button still says "Connect" (would read better as "Reconnect") | Minor | not a bug (only in the test copy; the real app says Reconnect) |
| B3 | Pictures | Kontakt 7 and 8 never get a picture: they take too long to open in Ordel's helper, are marked "crashed" and are never tried in REAPER, though REAPER can now open them safely in their own process | Important | fixed: helper → REAPER's separate process → REAPER itself when work is saved; Kontakt 7 and 8 now have pictures |
| B4 | Pictures | ReaSynDr never gets a picture: its plain slider window is judged "blank" | Minor | not a bug: ReaSynDr's interface is a single checkbox |
| B5 | Pictures | Capturing while REAPER plays shows "1 plugin need REAPER open to capture" instead of "Stop playback in REAPER, then capture again" (also "1 plugin need" grammar) | Important | fixed |
| B6 | Chains | JS effects are listed by file path ("utilityolume") instead of a readable name | Minor | fixed |

## Code review findings (fresh reviewer, read-only)
Grades are the reviewer's; each is verified (or not) before fixing. "Overlaps" points at a bug above.

| # | Where | What | Grade | Verified? |
|---|---|---|---|---|
| C1 | Capture (bridge) | Each plugin switches REAPER to the capture tab without checking whether the user is playing or recording in their project, which may interrupt a take | Critical | partly: audio keeps playing on a tab switch, but the view jumps (regraded Important); fixed, capture now waits, checked in REAPER |
| I1 | Window | Ordel finds its own window by the title "Ordel", so an Explorer window on the `dist\Ordel` folder gets moved, resized or toggled instead | Important | |
| I2 | Pictures | "Recapture all" overwrites custom images; a failed retake hides a good existing picture behind "Couldn't capture" | Important | |
| I3 | Window | Closing is always refused (to hide to the tray), which may also block Windows shutdown/restart | Important | fixed; checked: Ordel now answers yes to Windows' shutdown query |
| I4 | Adding | A slow plugin (big sampler) takes over 5 s to add, Ordel says "REAPER didn't respond", user adds it again → two copies | Important | |
| I5 | Pictures | Plugins installed while Ordel is running aren't found on disk until Ordel restarts, so they're captured without the safety process | Important | |
| I6 | Window | A remembered position on an unplugged, scaled monitor can open the window off-screen | Important | |
| I7 | Pictures | A plugin that hangs in the helper (licence prompt, slow load) is marked "crashed" for good | Important | fixed, see B3 |
| I8 | Pictures | A slow REAPER load is mistaken for a REAPER crash; the capture tab is left open and the toast says REAPER closed | Important | |
| I9 | Capture (bridge) | Closing the capture tab doesn't double-check it really is the capture tab before replacing it with an empty project | Important (latent data loss) | |
| M1 | Pictures | "Stop playback" message can never show | Minor | fixed (was B5) |
| M2 | Pictures | Pausing during the last plugin leaves the next capture stuck paused | Minor | |
| M3 | Adding | During a capture, adding goes to the project open when capture started, not the current one | Minor | |
| M4 | Pictures | An aborted run still says "Pictures updated" | Minor | |
| M5 | Pictures | Two capture runs can start at once (double request) | Minor | |
| M6 | UI | The once-a-second refresh resets the picture-size slider mid-drag and rebuilds the grid during capture (drops double-clicks); an error in drawing stops refreshing for good | Minor | |
| M7 | Window | Resizing doesn't work with swapped (left-handed) mouse buttons | Minor | |
| M8 | Settings | Shortcut recording uses key positions (wrong letter on AZERTY/QWERTZ); a combo already in use leaves "Press a shortcut…" stuck | Minor | |
| M9 | REAPER | Portable REAPER: found only at Ordel start; AppData wins over a running portable copy | Minor | |
| M10 | REAPER | Connect errors are silent; a failing script update at start stops Ordel starting | Minor | |
| M11 | Pictures | Stop/Quit during a slow plugin can leave REAPER on the capture tab | Minor | |
| M12 | Security | A web page could probe which plugin pictures exist on the local server | Minor | |
| M13 | Bridge | If REAPER can't delete the command file, the same command (e.g. an add) can run twice | Minor | |
| M14 | Tour | Typing can leak into search while the tour is showing | Minor | |
| M15 | Dev only | Running from source in the wrong folder makes every VST3 "crash" (built app unaffected) | Minor | |
