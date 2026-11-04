"""Runs the real REAPER bridge script in an embedded Lua with a fake `reaper` API."""
from pathlib import Path

import pytest
from lupa import LuaRuntime, LuaSyntaxError

from studio_hub.bridge import PLACEHOLDER
from studio_hub.paths import resource

FAKE_REAPER = r"""
local P = { projects = {}, active = nil, playing = false, inserted = {} }
local function newproj(name) local p = { name = name, tracks = {}, alive = true }; table.insert(P.projects, p); return p end
P.user = newproj("user"); P.active = P.user
P.user.tracks[1] = { name = "Vocals", fx = {}, selected = true }
reaper = {
  GetExtState = function() return "" end, SetExtState = function() end, atexit = function() end,
  defer = function() end, time_precise = function() return 0 end,
  EnumProjects = function(i)
    if i < 0 then return P.active end
    local n = 0
    for _, p in ipairs(P.projects) do if p.alive then if n == i then return p end n = n + 1 end end
  end,
  IsProjectDirty = function(p) return p.dirty and 1 or 0 end,
  ValidatePtr = function(p) return type(p) == "table" and p.alive == true end,
  ValidatePtr2 = function(p, t) return type(p) == "table" and p.alive == true and t ~= nil end,
  SelectProjectInstance = function(p) if p.alive then P.active = p end end,
  Main_OnCommand = function(cmd)
    if cmd == 40859 then P.active = newproj("capture") end
    if cmd == 40860 then P.active.alive = false; P.active = P.user end
  end,
  Main_openProject = function() end,
  GetPlayStateEx = function(p) return P.playing and 1 or 0 end,
  InsertTrackAtIndex = function(i) table.insert(P.active.tracks, i + 1, { name = "", fx = {} }); table.insert(P.inserted, P.active.name) end,
  InsertTrackInProject = function(p, i) p = (p == 0) and P.active or p; table.insert(p.tracks, i + 1, { name = "", fx = {} }); table.insert(P.inserted, p.name) end,
  GetTrack = function(p, i) p = (p == 0) and P.active or p; return p.tracks[i + 1] end,
  CountTracks = function(p) p = (p == 0) and P.active or p; return #p.tracks end,
  CountSelectedTracks = function(p) p = (p == 0) and P.active or p; local n = 0; for _, t in ipairs(p.tracks) do if t.selected then n = n + 1 end end; return n end,
  GetTrackStateChunk = function(tr) return true, tr.chunk or ('<TRACK\nNAME "' .. tr.name .. '"\n>\n') end,
  SetTrackStateChunk = function(tr, s)
    tr.chunk, tr.sets = s, (tr.sets or 0) + 1
    tr.fx = {}
    for name in s:gmatch('\n%s*<VST "([^"]+)"') do table.insert(tr.fx, name) end
    return true
  end,
  TrackFX_GetCount = function(tr) return #tr.fx end,
  TrackFX_CopyToTrack = function(src, i, dst, j, move)
    if P.copy_fails then error("copy failed") end
    table.insert(dst.fx, j + 1, src.fx[i + 1])
  end,
  SetTrackColor = function(tr, c) tr.color = c end,
  ColorToNative = function(r, g, b) return r + g * 256 + b * 65536 end,
  RecursiveCreateDirectory = function() return 1 end,
  TrackList_AdjustWindows = function() end,
  DeleteTrack = function(tr) for _, p in ipairs(P.projects) do for i, t in ipairs(p.tracks) do if t == tr then table.remove(p.tracks, i) end end end end,
  GetSelectedTrack = function(p, i)
    p = (p == 0) and P.active or p
    local n = 0
    for _, t in ipairs(p.tracks) do if t.selected then if n == i then return t end n = n + 1 end end
  end,
  GetSetMediaTrackInfo_String = function(tr, k, v, set) if set then tr.name = v end return true, tr.name end,
  TrackFX_AddByName = function(tr, name) if name:find("Nope") then return -1 end table.insert(tr.fx, name); return #tr.fx - 1 end,
  TrackFX_Show = function() end,
  GetTrackName = function(tr) return true, tr.name end,
  Undo_BeginBlock2 = function() P.undo_open = (P.undo_open or 0) + 1 end,
  Undo_EndBlock2 = function() P.undo_open = P.undo_open - 1 end,
}
P.api = reaper
return P
"""


@pytest.fixture
def lua(tmp_path):
    runtime = LuaRuntime(unpack_returned_tuples=True)
    state = runtime.execute(FAKE_REAPER)
    source = resource("reaper/studio_hub_bridge.lua").read_text(encoding="utf-8")
    runtime.execute(source.replace(PLACEHOLDER, f"[==[{tmp_path}]==]"))
    handlers = runtime.globals().STUDIO_HUB_HANDLERS
    state.handle = runtime.globals().STUDIO_HUB_HANDLE
    return handlers, state


def compiles(source: str) -> bool:
    try:
        LuaRuntime().compile(source)
        return True
    except LuaSyntaxError:
        return False


def test_compile_check_catches_broken_lua():
    assert not compiles('f:write("a\nb")')


def test_script_compiles():
    source = resource("reaper/studio_hub_bridge.lua").read_text(encoding="utf-8").replace(PLACEHOLDER, "[[x]]")
    assert compiles(source)


def test_add_puts_plugin_on_selected_track(lua):
    handlers, state = lua
    assert handlers.ADD("VST3: X (Y)") == "OK\tVocals"
    assert list(state.user.tracks[1].fx.values()) == ["VST3: X (Y)"]


def test_capture_never_touches_user_project(lua):
    handlers, state = lua
    assert handlers.CAPTURE_BEGIN() == "OK"
    assert handlers.CAPTURE_OPEN("VST3: A (B)") == "OK"
    assert len(state.user.tracks) == 1
    assert handlers.CAPTURE_END() == "OK"
    assert len(state.user.tracks) == 1 and list(state.inserted.values()) == ["capture"]


def test_capture_tab_closed_midrun_does_not_add_tracks_to_user(lua):
    handlers, state = lua
    handlers.CAPTURE_BEGIN()
    capture = state.active
    capture.alive = False  # user closes the capture tab
    state.active = state.user
    assert handlers.CAPTURE_OPEN("VST3: A (B)").startswith("ERR")
    assert len(state.user.tracks) == 1


def test_add_after_capture_tab_lost_targets_active_project(lua):
    handlers, state = lua
    handlers.CAPTURE_BEGIN()
    state.active.alive = False
    state.active = state.user
    assert handlers.ADD("VST3: X (Y)") == "OK\tVocals"


def test_capture_works_on_reaper_without_insert_track_in_project(lua, tmp_path):
    handlers, state = lua
    state.api.InsertTrackInProject = None  # REAPER 7.14 doesn't have it
    assert handlers.CAPTURE_BEGIN() == "OK"
    assert handlers.CAPTURE_OPEN("VST3: A (B)") == "OK"
    assert len(state.user.tracks) == 1 and list(state.inserted.values()) == ["capture"]


def test_capture_open_refuses_if_capture_tab_not_active(lua):
    handlers, state = lua
    state.api.InsertTrackInProject = None
    state.api.SelectProjectInstance = lambda p: None  # switching tabs silently fails
    handlers.CAPTURE_BEGIN()
    state.active = state.user
    assert handlers.CAPTURE_OPEN("VST3: A (B)").startswith("ERR")
    assert len(state.user.tracks) == 1


def test_check_saved_ignores_ordels_own_capture_tab(lua):
    handlers, state = lua
    handlers.CAPTURE_BEGIN()
    state.active.dirty = True  # the capture tab always has changes
    assert handlers.CHECK_SAVED() == "OK"
    state.user.dirty = True
    assert handlers.CHECK_SAVED() == "ERR\tUNSAVED"


def test_capture_refuses_while_playing(lua):
    handlers, state = lua
    state.playing = True
    assert handlers.CAPTURE_BEGIN() == "ERR\tBUSY"
    assert len(state.projects) == 1


CHAIN = ('BYPASS 0 0 0\n<VST "VST: ReaEQ (Cockos)" reaeq.dll 0 "" 1919247729<5653>\nZXE=\n>\nFLOATPOS 0 0 0 0\n'
         'FXID {FILE-1}\nWAK 0 0\nBYPASS 0 0 0\n<VST "VST: ReaComp (Cockos)" reacomp.dll 0 "" 1919247213<5653>\nQUJD\n>\n'
         'FLOATPOS 0 0 0 0\nFXID {FILE-2}\nWAK 0 0\n')
INPUT_FX = ('<FXCHAIN_REC\nSHOW 0\nLASTSEL 0\nDOCKED 0\nBYPASS 0 0 0\n<VST "VST: ReaGate (Cockos)" reagate.dll 0 "" 1<56>\n'
            'AA==\n>\nFLOATPOS 0 0 0 0\nFXID {REC}\nWAK 0 0\n>\n')
TRACK_WITH_FX = ('<TRACK\nNAME "Vocals"\n' + INPUT_FX + '<FXCHAIN\nWNDRECT 0 0 0 0\nSHOW 0\nLASTSEL 0\nDOCKED 0\n' + CHAIN
                 + '>\n<ITEM\nPOSITION 0\n>\n>\n')
EQ_COMP = ["VST: ReaEQ (Cockos)", "VST: ReaComp (Cockos)"]


def balanced(chunk):
    lines = [l.strip() for l in chunk.splitlines()]
    return sum(l.startswith("<") for l in lines) == sum(l == ">" for l in lines)


def chain_file(tmp_path):
    f = tmp_path / "Vocal.RfxChain"
    f.write_text(CHAIN)
    return f


def fx(track):
    return list(track.fx.values())


def track_count(state):
    return len(state.user.tracks)


def test_save_writes_the_selected_tracks_fx_not_its_input_fx(lua, tmp_path):
    handlers, state = lua
    state.user.tracks[1].chunk = TRACK_WITH_FX
    out = tmp_path / "saved.RfxChain"
    assert handlers.CHAIN_SAVE(str(out)) == "OK\t2"
    text = out.read_text()
    assert text.startswith("BYPASS") and "ReaEQ" in text and "ReaComp" in text and "ReaGate" not in text
    assert "WNDRECT" not in text and "SHOW 0" not in text and "POSITION" not in text


def test_save_without_fx_says_so(lua, tmp_path):
    handlers, state = lua
    assert handlers.CHAIN_SAVE(str(tmp_path / "x.RfxChain")) == "ERR\tNO_FX"
    state.user.tracks[1].chunk = '<TRACK\nNAME "Vocals"\n' + INPUT_FX + '>\n'  # input FX only
    assert handlers.CHAIN_SAVE(str(tmp_path / "x.RfxChain")) == "ERR\tNO_FX"


def test_apply_to_every_selected_track(lua, tmp_path):
    handlers, state = lua
    state.api.InsertTrackAtIndex(1, False)  # a second track in the user's project
    state.user.tracks[2].selected = True
    assert handlers.CHAIN_APPLY(f"track\tVocal\t{chain_file(tmp_path)}") == "OK\t2"
    assert fx(state.user.tracks[1]) == EQ_COMP and fx(state.user.tracks[2]) == EQ_COMP
    assert track_count(state) == 2  # the temporary track is gone


def test_apply_copies_fx_in_without_rewriting_the_track(lua, tmp_path):
    handlers, state = lua
    target = state.user.tracks[1]
    target.fx[1] = "VSTi: Kontakt (NI)"  # already loaded: must not be reloaded
    f = chain_file(tmp_path)
    handlers.CHAIN_APPLY(f"track\tVocal\t{f}")
    handlers.CHAIN_APPLY(f"track\tVocal\t{f}")
    assert fx(target) == ["VSTi: Kontakt (NI)", *EQ_COMP, *EQ_COMP]
    assert target.sets is None and track_count(state) == 1


def test_temporary_chain_drops_fx_ids_so_reaper_makes_fresh_ones(lua, tmp_path):
    handlers, state = lua
    seen = []
    original = state.api.SetTrackStateChunk
    state.api.SetTrackStateChunk = lambda tr, s, undo=False: (seen.append(s), original(tr, s))[1]
    handlers.CHAIN_APPLY(f"track\tVocal\t{chain_file(tmp_path)}")
    assert seen and "FXID" not in seen[0] and "<FXCHAIN" in seen[0] and balanced(seen[0])


def test_apply_without_selected_track_says_so(lua, tmp_path):
    handlers, state = lua
    state.user.tracks[1].selected = False
    assert handlers.CHAIN_APPLY(f"track\tVocal\t{chain_file(tmp_path)}") == "ERR\tNO_TRACK"
    assert handlers.CHAIN_ADD("track\tVocal\tVST: X (Y)") == "ERR\tNO_TRACK"
    assert not state.undo_open  # no undo step left open


def test_apply_missing_file_says_so(lua, tmp_path):
    handlers, _ = lua
    assert handlers.CHAIN_APPLY(f"track\tVocal\t{tmp_path / 'gone.RfxChain'}") == "ERR\tNO_FILE"


def test_failed_apply_still_closes_the_undo_step_and_removes_the_temporary_track(lua, tmp_path):
    handlers, state = lua
    state.copy_fails = True
    with pytest.raises(Exception):
        handlers.CHAIN_APPLY(f"track\tVocal\t{chain_file(tmp_path)}")
    assert state.undo_open == 0 and track_count(state) == 1


def test_return_mode_adds_a_named_track_and_reports_duplicates(lua, tmp_path):
    handlers, state = lua
    f = chain_file(tmp_path)
    assert handlers.CHAIN_APPLY(f"return\tPlate\t{f}") == "OK\tNEW"
    assert handlers.CHAIN_APPLY(f"return\tPlate\t{f}") == "OK\tEXISTS"  # a second Plate track is still added
    names = [state.user.tracks[i].name for i in range(1, track_count(state) + 1)]
    assert names == ["Vocals", "Plate", "Plate"]
    assert state.user.tracks[2].color and fx(state.user.tracks[2]) == EQ_COMP
    assert fx(state.user.tracks[1]) == []  # the selected track is left alone


def test_chain_add_uses_add_by_name(lua):
    handlers, state = lua
    assert handlers.CHAIN_ADD("track\tDrums\tVST: A (B)\tVST3: C (D)") == "OK\t1"
    assert fx(state.user.tracks[1]) == ["VST: A (B)", "VST3: C (D)"]
    assert handlers.CHAIN_ADD("return\tVerb\tVST: R (S)") == "OK\tNEW"
    assert fx(state.user.tracks[2]) == ["VST: R (S)"]


def test_chain_verbs_never_touch_the_capture_tab(lua, tmp_path):
    handlers, state = lua
    handlers.CAPTURE_BEGIN()
    capture = state.active
    assert handlers.CHAIN_APPLY(f"track\tVocal\t{chain_file(tmp_path)}") == "OK\t1"
    assert fx(state.user.tracks[1]) == EQ_COMP and len(capture.tracks) == 0 and track_count(state) == 1


def test_capture_waits_while_the_user_is_playing_or_recording(lua):
    handlers, state = lua
    assert handlers.CAPTURE_BEGIN() == "OK"
    capture = state.active
    state.active = state.user  # the user went back to their project and pressed play
    state.playing = True
    assert handlers.CAPTURE_OPEN("VST3: A (B)") == "ERR\tBUSY"
    assert state.active.name == "user" and len(capture.tracks) == 0  # their view wasn't pulled away
    assert handlers.CAPTURE_END() == "ERR\tBUSY" and capture.alive
    state.playing = False
    assert handlers.CAPTURE_OPEN("VST3: A (B)") == "OK"
    assert handlers.CAPTURE_END() == "OK" and not capture.alive


def test_capture_end_never_closes_a_tab_that_isnt_the_capture_tab(lua):
    handlers, state = lua
    handlers.CAPTURE_BEGIN()
    state.api.SelectProjectInstance = lambda p: None  # switching tabs silently fails
    state.active = state.user
    assert handlers.CAPTURE_END() == "ERR\tTAB_NOT_ACTIVE"
    assert state.user.alive and len(state.user.tracks) == 1


def test_add_during_a_capture_goes_to_the_tab_the_user_is_in(lua):
    handlers, state = lua
    handlers.CAPTURE_BEGIN()
    state.api.Main_OnCommand(40859, 0)  # the user opens another project tab of their own
    other = state.active
    state.api.InsertTrackAtIndex(0, False)
    other.tracks[1].selected = True
    other.tracks[1].name = "Bass"
    assert handlers.ADD("VST3: X (Y)") == "OK\tBass"
    assert list(other.tracks[1].fx.values()) == ["VST3: X (Y)"] and len(state.user.tracks[1].fx) == 0


def test_the_same_command_never_runs_twice(lua, tmp_path):
    handlers, state = lua
    line = "42" + chr(9) + "ADD" + chr(9) + "VST3: X (Y)"
    state.handle(line)
    state.handle(line)  # e.g. REAPER couldn't delete the command file in time
    assert list(state.user.tracks[1].fx.values()) == ["VST3: X (Y)"]


def test_open_only_if_saved_is_checked_as_it_opens(lua):
    handlers, state = lua
    handlers.CAPTURE_BEGIN()
    state.user.dirty = True  # e.g. a take recorded while Ordel waited for playback to stop
    assert handlers.CAPTURE_OPEN("CLAP: X (Y)" + chr(9) + "saved") == "ERR\tUNSAVED"
    assert handlers.CAPTURE_OPEN("VST: ReaComp (Cockos)") == "OK"  # safe plugins don't need it
