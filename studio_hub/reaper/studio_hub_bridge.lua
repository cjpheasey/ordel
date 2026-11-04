-- Ordel bridge: lets the Ordel app add plugins to tracks and capture plugin windows.
-- Installed by Ordel. Started automatically from Scripts/__startup.lua.

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

-- Lets Ordel stop this copy before it starts an updated one.
function handlers.QUIT()
  running = false
  return "OK"
end

-- The user's project: the active tab, or the one they were in before Ordel opened its capture tab.
local function user_project()
  if session_alive() and cap.orig and reaper.ValidatePtr(cap.orig, "ReaProject*") then return cap.orig end
  return 0
end

function handlers.ADD(name)
  local proj = user_project()
  local track = reaper.GetSelectedTrack(proj, 0)
  if not track then return "ERR\tNO_TRACK" end
  reaper.Undo_BeginBlock2(proj)
  local idx = reaper.TrackFX_AddByName(track, name, false, -1)
  reaper.Undo_EndBlock2(proj, "Ordel: add " .. name, -1)
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

-- Before opening a plugin that can't run in its own process: could a crash lose the user's work?
function handlers.CHECK_SAVED()
  local i = 0
  while true do
    local proj = reaper.EnumProjects(i)
    if not proj then return "OK" end
    if proj ~= cap.proj and reaper.IsProjectDirty(proj) ~= 0 then return "ERR\tUNSAVED" end
    i = i + 1
  end
end

-- ---------- chains ----------

local function split_lines(text)
  local lines = {}
  for line in text:gmatch("[^\r\n]+") do lines[#lines + 1] = line end
  return lines
end

local function opens(line) return line:match("^%s*<") ~= nil end
local function closes(line) return line:match("^%s*>%s*$") ~= nil end

-- Index of the <FXCHAIN line and of its closing '>' in a track chunk's lines, or nil.
local function find_chain_block(lines)
  local start, depth = nil, 0
  for i, line in ipairs(lines) do
    if start then
      if opens(line) then depth = depth + 1 elseif closes(line) then depth = depth - 1 end
      if depth == 0 then return start, i end
    elseif line:match("^%s*<FXCHAIN%s*$") then -- not <FXCHAIN_REC, the input FX
      start, depth = i, 1
    end
  end
end

-- What REAPER saves as an .RfxChain: the FX inside <FXCHAIN>, from its first BYPASS line.
local function chain_body(chunk)
  local lines = split_lines(chunk)
  local start, close = find_chain_block(lines)
  if not start then return nil end
  for i = start + 1, close - 1 do
    if lines[i]:match("^%s*BYPASS") then
      return table.concat(lines, "\n", i, close - 1) .. "\n"
    end
  end
end

-- The chunk with the chain's FX appended. FXID lines are dropped so REAPER gives every copy a fresh id.
local function with_chain(chunk, body)
  local lines = split_lines(chunk)
  local fx = {}
  for _, line in ipairs(split_lines(body)) do
    if not line:match("^%s*FXID ") then fx[#fx + 1] = line end
  end
  local start, close = find_chain_block(lines)
  local at = close
  if not start then
    -- No FX yet: add a chain block before the track's items (or its final '>').
    at = #lines
    while at > 1 and not closes(lines[at]) do at = at - 1 end
    local depth = 0
    for i = 2, #lines do
      if depth == 0 and lines[i]:match("^%s*<ITEM") then at = i break end
      if opens(lines[i]) then depth = depth + 1 elseif closes(lines[i]) then depth = depth - 1 end
    end
    table.insert(fx, 1, "<FXCHAIN")
    table.insert(fx, 2, "SHOW 0")
    table.insert(fx, 3, "LASTSEL 0")
    table.insert(fx, 4, "DOCKED 0")
    fx[#fx + 1] = ">"
  end
  for i = #fx, 1, -1 do table.insert(lines, at, fx[i]) end
  return table.concat(lines, "\n") .. "\n"
end

local function split_tabs(arg)
  local parts = {}
  for part in (arg .. "\t"):gmatch("([^\t]*)\t") do parts[#parts + 1] = part end
  return parts
end

local RETURN_COLOUR = { 201, 161, 90 } -- Ordel brass

-- A new track at the end of the user's project, or nil when this REAPER can't add one there right now.
local function new_track(proj)
  local index = reaper.CountTracks(proj)
  if reaper.InsertTrackInProject then
    reaper.InsertTrackInProject(proj, index, 0)
  elseif proj == 0 then
    reaper.InsertTrackAtIndex(index, false)
  else
    return nil -- older REAPER can only add tracks to the active tab, which is Ordel's capture tab
  end
  return reaper.GetTrack(proj, index)
end

-- Runs fill(proj, tracks) on every selected track ('track') or on a new return track ('return'), as one
-- undo step that is always closed, even if fill fails.
local function apply_chain(mode, name, fill)
  local proj = user_project()
  local tracks, reply = {}, nil
  if mode == "return" then
    local exists = false
    for i = 0, reaper.CountTracks(proj) - 1 do
      local _, track_name = reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(proj, i), "P_NAME", "", false)
      if track_name == name then exists = true end
    end
    reply = exists and "OK\tEXISTS" or "OK\tNEW"
  else
    local count = reaper.CountSelectedTracks(proj)
    if count == 0 then return "ERR\tNO_TRACK" end
    for i = 0, count - 1 do tracks[#tracks + 1] = reaper.GetSelectedTrack(proj, i) end
    reply = "OK\t" .. count
  end
  reaper.Undo_BeginBlock2(proj)
  local ok, err = pcall(function()
    if mode == "return" then
      local track = new_track(proj)
      if not track then error("CAPTURING", 0) end
      reaper.GetSetMediaTrackInfo_String(track, "P_NAME", name, true)
      reaper.SetTrackColor(track, reaper.ColorToNative(RETURN_COLOUR[1], RETURN_COLOUR[2], RETURN_COLOUR[3]) | 0x1000000)
      tracks = { track }
    end
    fill(proj, tracks)
  end)
  reaper.Undo_EndBlock2(proj, "Ordel: add chain " .. name, -1)
  reaper.TrackList_AdjustWindows(false)
  if not ok then
    if err == "CAPTURING" then return "ERR\tCAPTURING" end
    error(err, 0)
  end
  return reply
end

function handlers.CHAIN_SAVE(path)
  local track = reaper.GetSelectedTrack(user_project(), 0)
  if not track then return "ERR\tNO_TRACK" end
  local _, chunk = reaper.GetTrackStateChunk(track, "", false)
  local body = chain_body(chunk)
  if not body then return "ERR\tNO_FX" end
  reaper.RecursiveCreateDirectory(path:match("^(.*)[\\/]") or ".", 0)
  local f = io.open(path, "wb")
  if not f then return "ERR\tCANT_WRITE" end
  f:write(body)
  f:close()
  local count = 0
  for _ in body:gmatch("BYPASS") do count = count + 1 end
  return "OK\t" .. count
end

function handlers.CHAIN_APPLY(arg)
  local mode, name, path = table.unpack(split_tabs(arg))
  local f = path and io.open(path, "rb")
  if not f then return "ERR\tNO_FILE" end
  local body = f:read("a")
  f:close()
  -- Load the chain onto a temporary track, then copy its FX across: the target tracks' own FX and items are
  -- never rewritten, so nothing already loaded there reloads.
  return apply_chain(mode, name, function(proj, tracks)
    local temp = new_track(proj)
    if not temp then error("CAPTURING", 0) end
    local ok, err = pcall(function()
      local _, chunk = reaper.GetTrackStateChunk(temp, "", false)
      reaper.SetTrackStateChunk(temp, with_chain(chunk, body), false)
      for _, track in ipairs(tracks) do
        for i = 0, reaper.TrackFX_GetCount(temp) - 1 do
          reaper.TrackFX_CopyToTrack(temp, i, track, reaper.TrackFX_GetCount(track), false)
        end
      end
    end)
    reaper.DeleteTrack(temp)
    if not ok then error(err, 0) end
  end)
end

function handlers.CHAIN_ADD(arg)
  local parts = split_tabs(arg)
  return apply_chain(parts[1], parts[2], function(_, tracks)
    for _, track in ipairs(tracks) do
      for i = 3, #parts do reaper.TrackFX_AddByName(track, parts[i], false, -1) end
    end
  end)
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
