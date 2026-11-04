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
  InsertTrackAtIndex = function(i) table.insert(P.active.tracks, 1, { name = "", fx = {} }); table.insert(P.inserted, P.active.name) end,
  InsertTrackInProject = function(p, i) table.insert(p.tracks, 1, { name = "", fx = {} }); table.insert(P.inserted, p.name) end,
  GetTrack = function(p, i) return p.tracks[i + 1] end,
  DeleteTrack = function(tr) for _, p in ipairs(P.projects) do for i, t in ipairs(p.tracks) do if t == tr then table.remove(p.tracks, i) end end end end,
  GetSelectedTrack = function(p, i) p = (p == 0) and P.active or p; for _, t in ipairs(p.tracks) do if t.selected then return t end end end,
  GetSetMediaTrackInfo_String = function(tr, k, v, set) if set then tr.name = v end return true, tr.name end,
  TrackFX_AddByName = function(tr, name) if name:find("Nope") then return -1 end table.insert(tr.fx, name); return #tr.fx - 1 end,
  TrackFX_Show = function() end,
  GetTrackName = function(tr) return true, tr.name end,
  Undo_BeginBlock2 = function() end, Undo_EndBlock2 = function() end,
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
