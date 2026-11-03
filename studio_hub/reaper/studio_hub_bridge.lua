-- Mise bridge: lets the Mise app add plugins to tracks and capture plugin windows.
-- Installed by Mise. Started automatically from Scripts/__startup.lua.

local BRIDGE_DIR = --[[BRIDGE_DIR]]
local SEP = package.config:sub(1, 1)
local CMD = BRIDGE_DIR .. SEP .. "command.txt"
local RESP = BRIDGE_DIR .. SEP .. "response.txt"
local HEARTBEAT = BRIDGE_DIR .. SEP .. "heartbeat.txt"
local EMPTY_RPP = BRIDGE_DIR .. SEP .. "empty.rpp"

if reaper.GetExtState("StudioHub", "running") == "1" then return end
reaper.SetExtState("StudioHub", "running", "1", false)
reaper.atexit(function() reaper.SetExtState("StudioHub", "running", "", false) end)

local function read_file(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local s = f:read("a")
  f:close()
  return s
end

local function write_atomic(path, text)
  local tmp = path .. ".tmp"
  local f = io.open(tmp, "wb")
  if not f then return end
  f:write(text)
  f:close()
  os.remove(path)
  os.rename(tmp, path)
end

-- Capture happens in its own project tab so the user's project is never touched.
local cap = { proj = nil, orig = nil, track = nil }

local function session_alive()
  if cap.proj and reaper.ValidatePtr(cap.proj, "ReaProject*") then return true end
  cap.proj, cap.orig, cap.track = nil, nil, nil -- tab was closed by the user: forget it
  return false
end

local function close_capture_track()
  if cap.track and session_alive() and reaper.ValidatePtr2(cap.proj, cap.track, "MediaTrack*") then
    reaper.DeleteTrack(cap.track)
  end
  cap.track = nil
end

local handlers = {}

local running = true

function handlers.PING() return "OK" end

-- Lets Mise stop this copy before it starts an updated one.
function handlers.QUIT()
  running = false
  return "OK"
end

function handlers.ADD(name)
  local proj = 0
  if session_alive() and cap.orig and reaper.ValidatePtr(cap.orig, "ReaProject*") then proj = cap.orig end
  local track = reaper.GetSelectedTrack(proj, 0)
  if not track then return "ERR\tNO_TRACK" end
  reaper.Undo_BeginBlock2(proj)
  local idx = reaper.TrackFX_AddByName(track, name, false, -1)
  reaper.Undo_EndBlock2(proj, "Mise: add " .. name, -1)
  if idx < 0 then return "ERR\tNOT_FOUND" end
  reaper.TrackFX_Show(track, idx, 3)
  local _, track_name = reaper.GetTrackName(track)
  return "OK\t" .. track_name
end

function handlers.CAPTURE_BEGIN()
  if session_alive() then return "OK" end
  local current = reaper.EnumProjects(-1)
  -- Switching tabs can stop playback, so never start while the user is playing or recording.
  if reaper.GetPlayStateEx(current) ~= 0 then return "ERR\tBUSY" end
  cap.orig = current
  reaper.Main_OnCommand(40859, 0) -- New project tab
  cap.proj = reaper.EnumProjects(-1)
  return "OK"
end

function handlers.CAPTURE_OPEN(name)
  if not session_alive() then return "ERR\tNO_SESSION" end
  close_capture_track()
  reaper.SelectProjectInstance(cap.proj)
  if reaper.InsertTrackInProject then
    reaper.InsertTrackInProject(cap.proj, 0, 0)
  elseif reaper.EnumProjects(-1) == cap.proj then
    reaper.InsertTrackAtIndex(0, false) -- older REAPER: inserts into the active tab, checked above
  else
    return "ERR\tTAB_NOT_ACTIVE"
  end
  local track = reaper.GetTrack(cap.proj, 0)
  local idx = reaper.TrackFX_AddByName(track, name, false, -1)
  if idx < 0 then
    reaper.DeleteTrack(track)
    return "ERR\tNOT_FOUND"
  end
  cap.track = track
  reaper.TrackFX_Show(track, idx, 3)
  return "OK"
end

function handlers.CAPTURE_CLOSE()
  close_capture_track()
  return "OK"
end

function handlers.CAPTURE_END()
  local orig = cap.orig
  if session_alive() then
    close_capture_track()
    reaper.SelectProjectInstance(cap.proj)
    -- Swap in a clean empty project ("noprompt:") so closing the tab never asks to save.
    local f = io.open(EMPTY_RPP, "wb")
    f:write("<REAPER_PROJECT 0.1\n>\n")
    f:close()
    reaper.Main_openProject("noprompt:" .. EMPTY_RPP)
    reaper.Main_OnCommand(40860, 0) -- Close current project tab
  end
  if orig and reaper.ValidatePtr(orig, "ReaProject*") then
    reaper.SelectProjectInstance(orig)
  end
  cap.proj, cap.orig, cap.track = nil, nil, nil
  return "OK"
end

STUDIO_HUB_HANDLERS = handlers -- read by the test suite

local function handle(line)
  local id, verb, arg = line:match("^([^\t]*)\t([^\t]*)\t?([^\r\n]*)")
  if not id then return end
  local fn = handlers[verb]
  local reply
  if not fn then
    reply = "ERR\tUNKNOWN_VERB"
  else
    local ok, result = pcall(fn, arg)
    reply = ok and result or ("ERR\t" .. tostring(result))
  end
  write_atomic(RESP, id .. "\t" .. reply .. "\n")
end

local last_beat = 0
local function loop()
  local now = reaper.time_precise()
  if now - last_beat >= 1 then
    write_atomic(HEARTBEAT, tostring(os.time()))
    last_beat = now
  end
  local line = read_file(CMD)
  if line then
    os.remove(CMD)
    handle(line)
  end
  if running then
    reaper.defer(loop)
  else
    reaper.SetExtState("StudioHub", "running", "", false)
  end
end

loop()
