-------------------------------------------------
-- CONFIG
-------------------------------------------------
BASE_PATH = "C:/Users/HP/Documents/cogai/"
STATE_FILE = BASE_PATH .. "game_state.json"
INPUT_FILE = BASE_PATH .. "input_cache.txt"
TRANSITIONS_FILE = BASE_PATH .. "taught_transitions.json"

-- TIMING CONFIG
CACHE_FLUSH_INTERVAL = 1800
STATE_WRITE_INTERVAL = 60
VISUAL_UPDATE_RATE = 300
GC_INTERVAL = 600
MAX_INPUT_BUFFER = 500

-- BATCH LOGGING CONFIG
DENSE_BATCH_FRAMES = 10
DENSE_FRAME_INTERVAL = 2
SPARSE_FRAME_INTERVAL = 12
RECENT_ACTIONS_SIZE = 8

-------------------------------------------------
-- MEMORY ADDRESSES (VERIFIED)
-------------------------------------------------
-- Overworld (original)
ADDR_PLAYER_X   = 0x02036E48
ADDR_PLAYER_Y   = 0x02036E4A
ADDR_MAP_ID     = 0x02036E44
ADDR_DIRECTION  = 0x02036E50
ADDR_BATTLE     = 0x0202000A
ADDR_GAME_STATE = 0x020204C2

-- Battle UI (verified)
ADDR_BATTLE_MENU_CURSOR = 0x02023FF8  -- u8: 0=Fight,1=Bag,2=Pokemon,3=Run
ADDR_MOVE_MENU_CURSOR   = 0x02023FFC  -- u8: 0-3 (move slot)

-- Battle Pokemon (verified, all u16)
ADDR_PLAYER_SPECIES     = 0x02023BE4  -- active Pokemon species ID
ADDR_PLAYER_HP_BATTLE   = 0x02023C0C  -- active Pokemon current HP
ADDR_ENEMY_SPECIES      = 0x02023C3C  -- enemy species ID
ADDR_ENEMY_HP_BATTLE    = 0x02023C64  -- enemy current HP

-- Party data (verified, all u16)
ADDR_PLAYER_HP_PARTY    = 0x020242DA  -- party slot 0 current HP (+0x56)
ADDR_PLAYER_MAXHP_PARTY = 0x020242DC  -- party slot 0 max HP (+0x58)

-- Party menu (verified)
ADDR_PARTY_CURSOR       = 0x0203B0A9  -- u8: 0-5 (slot), possibly 6=cancel

-- GBA Video Memory
ADDR_BG_PALETTE  = 0x05000000
ADDR_BG0_TILEMAP = 0x06000000

-------------------------------------------------
-- INPUT CACHE
-------------------------------------------------
local input_lines = {}
local input_count = 0

-------------------------------------------------
-- TRANSITION BATCH TRACKING
-------------------------------------------------
local recent_actions = {}
local previous_action = nil
local current_batch = nil
local all_batches = {}
local dense_logging_countdown = 0
local sparse_frame_counter = 0
local total_frames_logged = 0
local action_change_count = 0
local maps_visited = {}

-------------------------------------------------
-- VISUAL CACHE
-------------------------------------------------
local cached_palette_str = ""
local cached_tiles_str = ""

-------------------------------------------------
-- HELPERS
-------------------------------------------------
function safe_read_u8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function safe_read_u16(addr)
    local ok, val = pcall(memory.read_u16_le, addr)
    return (ok and val) or 0
end

function normalize_direction(raw_dir)
    if raw_dir == 17 then return 0
    elseif raw_dir == 34 then return 1
    elseif raw_dir == 51 then return 2
    elseif raw_dir == 68 then return 3
    else return raw_dir % 4
    end
end

function get_human_action()
    local input = joypad.get()
    if input.A then return "A"
    elseif input.B then return "B"
    elseif input.Start then return "S"
    elseif input.Select then return "E"
    elseif input.Up then return "U"
    elseif input.Down then return "D"
    elseif input.Left then return "L"
    elseif input.Right then return "R"
    else return nil
    end
end

function expand_action(short)
    if short == "U" then return "UP"
    elseif short == "D" then return "DOWN"
    elseif short == "L" then return "LEFT"
    elseif short == "R" then return "RIGHT"
    elseif short == "S" then return "Start"
    elseif short == "E" then return "Select"
    else return short
    end
end

-------------------------------------------------
-- RECENT ACTIONS BUFFER
-------------------------------------------------
function add_to_recent_actions(action)
    if action == nil then return end
    table.insert(recent_actions, expand_action(action))
    while #recent_actions > RECENT_ACTIONS_SIZE do
        table.remove(recent_actions, 1)
    end
end

function get_recent_actions_copy()
    local copy = {}
    for i, v in ipairs(recent_actions) do
        copy[i] = v
    end
    return copy
end

-------------------------------------------------
-- BATTLE DATA EXTRACTION
-- Matches AI Lua format exactly: "b" field with short keys
-- Uses -1 for unavailable fields
-------------------------------------------------
function get_battle_string(in_battle)
    if in_battle == 0 then
        -- Outside battle: only party HP and party cursor are meaningful
        local player_hp = safe_read_u16(ADDR_PLAYER_HP_PARTY)
        local player_max_hp = safe_read_u16(ADDR_PLAYER_MAXHP_PARTY)
        local party_cursor = safe_read_u8(ADDR_PARTY_CURSOR)

        return string.format(
            '"b":{"bc":-1,"mc":-1,"ps":-1,"es":-1,"ph":%d,"pm":%d,"eh":-1,"pc":%d}',
            player_hp, player_max_hp, party_cursor
        )
    end

    -- In battle: read everything
    local battle_cursor = safe_read_u8(ADDR_BATTLE_MENU_CURSOR)
    local move_cursor = safe_read_u8(ADDR_MOVE_MENU_CURSOR)
    local player_species = safe_read_u16(ADDR_PLAYER_SPECIES)
    local enemy_species = safe_read_u16(ADDR_ENEMY_SPECIES)
    local player_hp = safe_read_u16(ADDR_PLAYER_HP_BATTLE)
    local player_max_hp = safe_read_u16(ADDR_PLAYER_MAXHP_PARTY)
    local enemy_hp = safe_read_u16(ADDR_ENEMY_HP_BATTLE)
    local party_cursor = safe_read_u8(ADDR_PARTY_CURSOR)

    return string.format(
        '"b":{"bc":%d,"mc":%d,"ps":%d,"es":%d,"ph":%d,"pm":%d,"eh":%d,"pc":%d}',
        battle_cursor, move_cursor, player_species, enemy_species,
        player_hp, player_max_hp, enemy_hp, party_cursor
    )
end

-------------------------------------------------
-- BATCH MANAGEMENT
-------------------------------------------------
function create_frame_record(x, y, map, in_battle, menu_flag, direction, action, frame_offset)
    return {
        state = {
            map_id = map, x = x, y = y,
            direction = direction, in_battle = in_battle, in_menu = menu_flag
        },
        action = expand_action(action),
        recent_actions = get_recent_actions_copy(),
        frame_offset = frame_offset
    }
end

function start_dense_batch(trigger_action, x, y, map, in_battle, menu_flag, direction)
    if current_batch and #current_batch.frames > 0 then
        table.insert(all_batches, current_batch)
    end
    current_batch = {
        batch_type = "action_change",
        trigger_action = expand_action(trigger_action),
        frames = {}
    }
    dense_logging_countdown = DENSE_BATCH_FRAMES
    action_change_count = action_change_count + 1
    local fr = create_frame_record(x, y, map, in_battle, menu_flag, direction, trigger_action, 0)
    table.insert(current_batch.frames, fr)
    total_frames_logged = total_frames_logged + 1
end

function start_steady_batch()
    if current_batch and #current_batch.frames > 0 then
        table.insert(all_batches, current_batch)
    end
    current_batch = { batch_type = "steady", frames = {} }
end

function log_frame_to_batch(x, y, map, in_battle, menu_flag, direction, action, frame_offset)
    if current_batch == nil then start_steady_batch() end
    local fr = create_frame_record(x, y, map, in_battle, menu_flag, direction, action, frame_offset)
    table.insert(current_batch.frames, fr)
    total_frames_logged = total_frames_logged + 1
    maps_visited[map] = true
end

-------------------------------------------------
-- SAVE TRANSITIONS TO JSON
-------------------------------------------------
function save_transitions()
    local batches_to_save = {}
    for i, batch in ipairs(all_batches) do
        table.insert(batches_to_save, batch)
    end
    if current_batch and #current_batch.frames > 0 then
        table.insert(batches_to_save, current_batch)
    end
    if #batches_to_save == 0 then return end

    local f = io.open(TRANSITIONS_FILE, "w")
    if not f then print("ERROR: Cannot open transitions file"); return end

    f:write('{"batches":[')
    for bi, batch in ipairs(batches_to_save) do
        if bi > 1 then f:write(',') end
        f:write('{"batch_type":"' .. batch.batch_type .. '"')
        if batch.trigger_action then
            f:write(',"trigger_action":"' .. batch.trigger_action .. '"')
        end
        f:write(',"frames":[')
        for fi, frame in ipairs(batch.frames) do
            if fi > 1 then f:write(',') end
            f:write('{"state":{')
            f:write('"map_id":' .. frame.state.map_id .. ',')
            f:write('"x":' .. frame.state.x .. ',')
            f:write('"y":' .. frame.state.y .. ',')
            f:write('"direction":' .. frame.state.direction .. ',')
            f:write('"in_battle":' .. frame.state.in_battle .. ',')
            f:write('"in_menu":' .. frame.state.in_menu)
            f:write('},')
            f:write('"action":"' .. (frame.action or "NONE") .. '",')
            f:write('"recent_actions":[')
            for ri, ra in ipairs(frame.recent_actions) do
                if ri > 1 then f:write(',') end
                f:write('"' .. ra .. '"')
            end
            f:write('],')
            f:write('"frame_offset":' .. frame.frame_offset)
            f:write('}')
        end
        f:write(']}')
    end

    f:write('],"metadata":{')
    f:write('"total_frames":' .. total_frames_logged .. ',')
    f:write('"action_changes":' .. action_change_count .. ',')
    f:write('"maps_visited":[')
    local first_map = true
    for map_id, _ in pairs(maps_visited) do
        if not first_map then f:write(',') end
        f:write(tostring(map_id))
        first_map = false
    end
    f:write(']}}')
    f:close()
    print(string.format(">> TRANSITIONS SAVED: %d batches, %d frames, %d action changes",
        #batches_to_save, total_frames_logged, action_change_count))
end

-------------------------------------------------
-- INPUT CACHE
-------------------------------------------------
function cache_input(action, x, y, map, in_battle, menu_flag, direction)
    if action == nil then return end
    input_count = input_count + 1
    input_lines[input_count] = action .. "," .. x .. "," .. y .. "," ..
                                map .. "," .. in_battle .. "," .. menu_flag .. "," .. direction
end

function flush_input_cache()
    if input_count == 0 then return end
    local f = io.open(INPUT_FILE, "w")
    if f then f:write(table.concat(input_lines, "\n")); f:close() end
    print(string.format(">> FLUSHED %d inputs", input_count))
    for i = 1, input_count do input_lines[i] = nil end
    input_count = 0
    save_transitions()
    collectgarbage("collect")
end

-------------------------------------------------
-- VISUAL CACHE
-------------------------------------------------
function update_visual_cache()
    local p = {}
    for i = 0, 255 do
        local addr = ADDR_BG_PALETTE + (i * 2)
        local ok, color = pcall(memory.read_u16_le, addr)
        if ok and color then
            local b = ((color >> 10) & 0x1F) / 31.0
            local g = ((color >> 5) & 0x1F) / 31.0
            local r = (color & 0x1F) / 31.0
            p[#p + 1] = string.format("%.3f,%.3f,%.3f", r, g, b)
        else
            p[#p + 1] = "0,0,0"
        end
    end
    cached_palette_str = table.concat(p, ",")
    p = nil

    local t = {}
    for y = 0, 19 do
        for x = 0, 29 do
            local offset = (y * 32 + x) * 2
            local tile_data = safe_read_u16(ADDR_BG0_TILEMAP + offset)
            t[#t + 1] = string.format("%.3f", (tile_data & 0x3FF) / 1024.0)
        end
    end
    cached_tiles_str = table.concat(t, ",")
    t = nil
end

-------------------------------------------------
-- STATE WRITERS
-- Both include "b" field (battle data) matching AI Lua format
-------------------------------------------------
function write_minimal_state(x, y, map, in_battle, menu_flag, direction)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    f:write('{"s":[' .. x .. ',' .. y .. ',' .. map .. ',' ..
            in_battle .. ',' .. menu_flag .. ',' .. direction ..
            '],"dead":false,' .. get_battle_string(in_battle) ..
            ',"ic":' .. input_count .. '}')
    f:close()
end

function write_full_state(x, y, map, in_battle, menu_flag, direction)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    f:write('{"s":[' .. x .. ',' .. y .. ',' .. map .. ',' ..
            in_battle .. ',' .. menu_flag .. ',' .. direction ..
            '],"dead":false,' .. get_battle_string(in_battle) ..
            ',"ic":' .. input_count)
    if #cached_palette_str > 0 then
        f:write(',"p":[' .. cached_palette_str .. ']')
    end
    if #cached_tiles_str > 0 then
        f:write(',"t":[' .. cached_tiles_str .. ']')
    end
    f:write('}')
    f:close()
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
local frame_counter = 0

print("==========================================")
print("Pokemon AI - TEACHING MODE + TRANSITIONS")
print("==========================================")
print("ADDRESSES (Overworld):")
print("  X:         0x02036E48")
print("  Y:         0x02036E4A")
print("  Map:       0x02036E44")
print("  Direction: 0x02036E50")
print("  Battle:    0x0202000A")
print("  State:     0x020204C2")
print("ADDRESSES (Battle - NEW):")
print("  BattleCursor: 0x02023FF8 (Fight/Bag/Pkmn/Run)")
print("  MoveCursor:   0x02023FFC (move 0-3)")
print("  PlayerSpecies:0x02023BE4")
print("  EnemySpecies: 0x02023C3C")
print("  PlayerHP:     0x02023C0C (battle)")
print("  EnemyHP:      0x02023C64 (battle)")
print("  PartyHP:      0x020242DA (party)")
print("  PartyMaxHP:   0x020242DC (party)")
print("  PartyCursor:  0x0203B0A9")
print("==========================================")

update_visual_cache()
collectgarbage("collect")

while true do
    local human_action = get_human_action()
    local x = safe_read_u8(ADDR_PLAYER_X)
    local y = safe_read_u8(ADDR_PLAYER_Y)
    local map = safe_read_u8(ADDR_MAP_ID)
    local direction = normalize_direction(safe_read_u8(ADDR_DIRECTION))
    local in_battle = (safe_read_u8(ADDR_BATTLE) == 1) and 1 or 0
    local menu_flag = (safe_read_u8(ADDR_GAME_STATE) == 1) and 1 or 0

    if human_action ~= nil and human_action ~= previous_action then
        add_to_recent_actions(human_action)
        start_dense_batch(human_action, x, y, map, in_battle, menu_flag, direction)
        previous_action = human_action
    elseif dense_logging_countdown > 0 then
        if frame_counter % DENSE_FRAME_INTERVAL == 0 then
            log_frame_to_batch(x, y, map, in_battle, menu_flag, direction, human_action,
                              DENSE_BATCH_FRAMES - dense_logging_countdown)
        end
        dense_logging_countdown = dense_logging_countdown - 1
        if dense_logging_countdown == 0 then start_steady_batch() end
    else
        sparse_frame_counter = sparse_frame_counter + 1
        if sparse_frame_counter >= SPARSE_FRAME_INTERVAL then
            if human_action ~= nil then
                add_to_recent_actions(human_action)
                log_frame_to_batch(x, y, map, in_battle, menu_flag, direction, human_action, 0)
            end
            sparse_frame_counter = 0
        end
    end

    if human_action then
        cache_input(human_action, x, y, map, in_battle, menu_flag, direction)
    end

    if frame_counter % VISUAL_UPDATE_RATE == 0 then update_visual_cache() end
    if frame_counter % STATE_WRITE_INTERVAL == 0 then
        write_full_state(x, y, map, in_battle, menu_flag, direction)
    end
    if (frame_counter % CACHE_FLUSH_INTERVAL == 0 and frame_counter > 0) or
       (input_count >= MAX_INPUT_BUFFER) then
        flush_input_cache()
    end
    if frame_counter % GC_INTERVAL == 0 then collectgarbage("collect") end

    -- Debug print every 600 frames (with battle info when in battle)
    if frame_counter % 600 == 0 then
        if in_battle == 1 then
            local bc = safe_read_u8(ADDR_BATTLE_MENU_CURSOR)
            local mc = safe_read_u8(ADDR_MOVE_MENU_CURSOR)
            local ps = safe_read_u16(ADDR_PLAYER_SPECIES)
            local es = safe_read_u16(ADDR_ENEMY_SPECIES)
            local ph = safe_read_u16(ADDR_PLAYER_HP_BATTLE)
            local eh = safe_read_u16(ADDR_ENEMY_HP_BATTLE)
            local mem = collectgarbage("count")
            print(string.format("Frame:%d | BATTLE | Cursor:%d Move:%d | %d(hp:%d) vs %d(hp:%d) | Buf:%d | Mem:%.1fKB",
                frame_counter, bc, mc, ps, ph, es, eh, input_count, mem))
        else
            local mem = collectgarbage("count")
            print(string.format("Frame:%d | Pos:(%d,%d) Map:%d Dir:%d | Battle:%d Menu:%d | Buf:%d | Batches:%d | Frames:%d | Mem:%.1fKB",
                frame_counter, x, y, map, direction, in_battle, menu_flag, input_count, #all_batches, total_frames_logged, mem))
        end
    end

    frame_counter = frame_counter + 1
    emu.frameadvance()
end