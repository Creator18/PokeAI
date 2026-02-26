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
-- MEMORY ADDRESSES — ALL VERIFIED
-------------------------------------------------

-- === OVERWORLD ===
ADDR_PLAYER_X   = 0x02036E48   -- u8
ADDR_PLAYER_Y   = 0x02036E4A   -- u8
ADDR_MAP_ID     = 0x02036E44   -- u8
ADDR_DIRECTION  = 0x02036E50   -- u8 (raw: 17/34/51/68)
ADDR_BATTLE     = 0x0202000A   -- u8 (1=in battle)
ADDR_GAME_STATE = 0x020204C2   -- u8 (0=OW, 1=menu/party, 14=bag)

-- === MENU SYSTEM (universal, reused across all menus) ===
ADDR_MENU_CURSOR = 0x0203ADE6  -- u8: current menu/submenu cursor
ADDR_MENU_MAX    = 0x0203ADE8  -- u8: max cursor index for current menu

-- === BAG SYSTEM ===
ADDR_BAG_POCKET  = 0x0203AD02  -- u8: 0=Items,1=KeyItems,2=Pokeballs,3=TMs,4=Berries
ADDR_BAG_CURSOR  = 0x0203AD04  -- u8: cursor position within pocket
ADDR_SB1_PTR     = 0x03005008  -- u32: SaveBlock1 pointer
ADDR_SB2_PTR     = 0x0300500C  -- u32: SaveBlock2 pointer
BAG_KEY_OFFSET   = 0x0F20      -- u16 at SB2+0x0F20: XOR key for quantities

BAG_POCKET_INFO = {
    [0] = {offset = 0x0310, slots = 42, name = "Items"},
    [1] = {offset = 0x03B8, slots = 30, name = "KeyItems"},
    [2] = {offset = 0x0430, slots = 16, name = "Pokeballs"},
    [3] = {offset = 0x0464, slots = 64, name = "TMs"},
    [4] = {offset = 0x0564, slots = 46, name = "Berries"},
}

-- === BATTLE UI ===
ADDR_BATTLE_CURSOR = 0x02023FF8 -- u8: 0=Fight,1=Bag,2=Pokemon,3=Run
ADDR_MOVE_CURSOR   = 0x02023FFC -- u8: 0-3
ADDR_PARTY_CURSOR  = 0x0203B0A9 -- u8: 0-5, 6=cancel
ADDR_SWAP_CURSOR   = 0x0203B0AA -- u8: swap target cursor
ADDR_BATTLE_TYPE   = 0x02022B4C -- u8: 4=wild, 12=trainer (bit3=trainer)

-- === PLAYER BATTLE MIRROR (base 0x02023BE4) ===
ADDR_P_SPECIES   = 0x02023BE4  -- u16
ADDR_P_MOVE0     = 0x02023BF0  -- u16
ADDR_P_MOVE1     = 0x02023BF2  -- u16
ADDR_P_MOVE2     = 0x02023BF4  -- u16
ADDR_P_MOVE3     = 0x02023BF6  -- u16
ADDR_P_STAT_ATK  = 0x02023BFD  -- u8 (neutral=6)
ADDR_P_STAT_DEF  = 0x02023BFE  -- u8
ADDR_P_STAT_SPD  = 0x02023BFF  -- u8
ADDR_P_STAT_SPATK= 0x02023C00  -- u8
ADDR_P_STAT_SPDEF= 0x02023C01  -- u8
ADDR_P_STAT_ACC  = 0x02023C02  -- u8
ADDR_P_STAT_EVA  = 0x02023C03  -- u8
ADDR_P_PP0       = 0x02023C08  -- u8
ADDR_P_PP1       = 0x02023C09  -- u8
ADDR_P_PP2       = 0x02023C0A  -- u8
ADDR_P_PP3       = 0x02023C0B  -- u8
ADDR_P_HP        = 0x02023C0C  -- u16
ADDR_P_LEVEL     = 0x02023C0E  -- u8
ADDR_P_MAXHP     = 0x02023C10  -- u16
ADDR_P_STATUS    = 0x02023C30  -- u32

-- === ENEMY BATTLE MIRROR (base 0x02023C3C, +0x58 from player) ===
ADDR_E_SPECIES   = 0x02023C3C  -- u16
ADDR_E_MOVE0     = 0x02023C48  -- u16
ADDR_E_MOVE1     = 0x02023C4A  -- u16
ADDR_E_MOVE2     = 0x02023C4C  -- u16
ADDR_E_MOVE3     = 0x02023C4E  -- u16
ADDR_E_STAT_ATK  = 0x02023C55  -- u8
ADDR_E_STAT_DEF  = 0x02023C56  -- u8
ADDR_E_STAT_SPD  = 0x02023C57  -- u8
ADDR_E_STAT_SPATK= 0x02023C58  -- u8
ADDR_E_STAT_SPDEF= 0x02023C59  -- u8
ADDR_E_STAT_ACC  = 0x02023C5A  -- u8
ADDR_E_STAT_EVA  = 0x02023C5B  -- u8
ADDR_E_PP0       = 0x02023C60  -- u8
ADDR_E_PP1       = 0x02023C61  -- u8
ADDR_E_PP2       = 0x02023C62  -- u8
ADDR_E_PP3       = 0x02023C63  -- u8
ADDR_E_HP        = 0x02023C64  -- u16
ADDR_E_LEVEL     = 0x02023C66  -- u8
ADDR_E_MAXHP     = 0x02023C68  -- u16
ADDR_E_STATUS    = 0x02023C88  -- u32

-- === PARTY DATA ===
ADDR_PARTY_COUNT = 0x02024029  -- u8
PARTY_BASE       = 0x02024284
PARTY_SLOT_SIZE  = 0x64        -- 100 bytes per slot

-- === GBA VIDEO ===
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
-- BAG CACHE
-------------------------------------------------
local sb1_cache = 0
local bag_key_cache = 0

-------------------------------------------------
-- HELPERS
-------------------------------------------------
function r8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function r16(addr)
    local ok, val = pcall(memory.read_u16_le, addr)
    return (ok and val) or 0
end

function r32(addr)
    local ok, val = pcall(memory.read_u32_le, addr)
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
    elseif short == "S" then return "START"
    elseif short == "E" then return "SELECT"
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
-- BAG DATA
-------------------------------------------------
function update_bag_caches()
    sb1_cache = r32(ADDR_SB1_PTR)
    local sb2 = r32(ADDR_SB2_PTR)
    bag_key_cache = r16(sb2 + BAG_KEY_OFFSET)
end

function decode_qty(raw_qty)
    local result = raw_qty ~ bag_key_cache
    if result < 0 or result > 999 then return 0 end
    return result
end

function get_bag_string(game_state, in_battle, battle_cursor)
    local bag_active = (game_state == 14) or (in_battle == 1 and battle_cursor == 1)
    local pocket = r8(ADDR_BAG_POCKET)
    local cursor = r8(ADDR_BAG_CURSOR)

    if not bag_active then
        return string.format('"bg":{"pk":%d,"bc":%d,"a":0,"it":[]}', pocket, cursor)
    end

    local info = BAG_POCKET_INFO[pocket]
    if not info then
        return string.format('"bg":{"pk":%d,"bc":%d,"a":1,"it":[]}', pocket, cursor)
    end

    local base = sb1_cache + info.offset
    local items = {}
    local max_read = math.min(info.slots, 20)

    for i = 0, max_read - 1 do
        local addr = base + i * 4
        local item_id = r16(addr)
        local raw_qty = r16(addr + 2)

        if item_id == 0 then break end

        local qty = decode_qty(raw_qty)
        items[#items + 1] = string.format('{"id":%d,"q":%d}', item_id, qty)
    end

    return string.format('"bg":{"pk":%d,"bc":%d,"a":1,"it":[%s]}',
        pocket, cursor, table.concat(items, ","))
end

-------------------------------------------------
-- MENU DATA
-------------------------------------------------
function get_menu_string()
    local mc = r8(ADDR_MENU_CURSOR)
    local mm = r8(ADDR_MENU_MAX)
    local pc = r8(ADDR_PARTY_CURSOR)
    local sc = r8(ADDR_SWAP_CURSOR)
    return string.format('"mu":{"mc":%d,"mm":%d,"pc":%d,"sc":%d}', mc, mm, pc, sc)
end

-------------------------------------------------
-- PARTY DATA
-------------------------------------------------
function get_party_string()
    local count = r8(ADDR_PARTY_COUNT)
    local parts = {}

    for i = 0, 5 do
        local base = PARTY_BASE + (i * PARTY_SLOT_SIZE)
        local lv  = r8(base + 0x54)
        local hp  = r16(base + 0x56)
        local mhp = r16(base + 0x58)

        if mhp == 0 and lv == 0 then break end

        local atk   = r16(base + 0x5A)
        local def   = r16(base + 0x5C)
        local spd   = r16(base + 0x5E)
        local spatk = r16(base + 0x60)
        local spdef = r16(base + 0x62)
        local st    = r32(base + 0x50)

        parts[#parts + 1] = string.format(
            '{"l":%d,"h":%d,"m":%d,"a":%d,"d":%d,"sp":%d,"sa":%d,"sd":%d,"st":%d}',
            lv, hp, mhp, atk, def, spd, spatk, spdef, st
        )
    end

    return string.format('"pa":{"c":%d,"s":[%s]}', count, table.concat(parts, ","))
end

-------------------------------------------------
-- BATTLE DATA (full, matches AI Lua v3 format)
-------------------------------------------------
function get_battle_string(in_battle)
    if in_battle == 0 then
        return string.format(
            '"b":{"bc":-1,"mc":-1,"ps":-1,"es":-1,"ph":-1,"pm":-1,"eh":-1,"em":-1,"pl":-1,"el":-1,"pst":0,"est":0,"bt":0,"m0":-1,"m1":-1,"m2":-1,"m3":-1,"pp0":-1,"pp1":-1,"pp2":-1,"pp3":-1,"pss":[-1,-1,-1,-1,-1,-1,-1],"em0":-1,"em1":-1,"em2":-1,"em3":-1,"epp0":-1,"epp1":-1,"epp2":-1,"epp3":-1,"ess":[-1,-1,-1,-1,-1,-1,-1],"pc":-1}'
        )
    end

    local bc  = r8(ADDR_BATTLE_CURSOR)
    local mc  = r8(ADDR_MOVE_CURSOR)
    local pc  = r8(ADDR_PARTY_CURSOR)
    local bt  = r8(ADDR_BATTLE_TYPE)

    local ps  = r16(ADDR_P_SPECIES)
    local ph  = r16(ADDR_P_HP)
    local pm  = r16(ADDR_P_MAXHP)
    local pl  = r8(ADDR_P_LEVEL)
    local pst = r32(ADDR_P_STATUS)
    local m0  = r16(ADDR_P_MOVE0)
    local m1  = r16(ADDR_P_MOVE1)
    local m2  = r16(ADDR_P_MOVE2)
    local m3  = r16(ADDR_P_MOVE3)
    local pp0 = r8(ADDR_P_PP0)
    local pp1 = r8(ADDR_P_PP1)
    local pp2 = r8(ADDR_P_PP2)
    local pp3 = r8(ADDR_P_PP3)

    local psa = r8(ADDR_P_STAT_ATK)
    local psd = r8(ADDR_P_STAT_DEF)
    local pss = r8(ADDR_P_STAT_SPD)
    local psA = r8(ADDR_P_STAT_SPATK)
    local psD = r8(ADDR_P_STAT_SPDEF)
    local psC = r8(ADDR_P_STAT_ACC)
    local psE = r8(ADDR_P_STAT_EVA)

    local es   = r16(ADDR_E_SPECIES)
    local eh   = r16(ADDR_E_HP)
    local em   = r16(ADDR_E_MAXHP)
    local el   = r8(ADDR_E_LEVEL)
    local est  = r32(ADDR_E_STATUS)
    local em0  = r16(ADDR_E_MOVE0)
    local em1  = r16(ADDR_E_MOVE1)
    local em2  = r16(ADDR_E_MOVE2)
    local em3  = r16(ADDR_E_MOVE3)
    local epp0 = r8(ADDR_E_PP0)
    local epp1 = r8(ADDR_E_PP1)
    local epp2 = r8(ADDR_E_PP2)
    local epp3 = r8(ADDR_E_PP3)

    local esa = r8(ADDR_E_STAT_ATK)
    local esd = r8(ADDR_E_STAT_DEF)
    local ess_spd = r8(ADDR_E_STAT_SPD)
    local esA = r8(ADDR_E_STAT_SPATK)
    local esD = r8(ADDR_E_STAT_SPDEF)
    local esC = r8(ADDR_E_STAT_ACC)
    local esE = r8(ADDR_E_STAT_EVA)

    return string.format(
        '"b":{"bc":%d,"mc":%d,"ps":%d,"es":%d,"ph":%d,"pm":%d,"eh":%d,"em":%d,"pl":%d,"el":%d,"pst":%d,"est":%d,"bt":%d,"m0":%d,"m1":%d,"m2":%d,"m3":%d,"pp0":%d,"pp1":%d,"pp2":%d,"pp3":%d,"pss":[%d,%d,%d,%d,%d,%d,%d],"em0":%d,"em1":%d,"em2":%d,"em3":%d,"epp0":%d,"epp1":%d,"epp2":%d,"epp3":%d,"ess":[%d,%d,%d,%d,%d,%d,%d],"pc":%d}',
        bc, mc, ps, es, ph, pm, eh, em, pl, el, pst, est, bt,
        m0, m1, m2, m3, pp0, pp1, pp2, pp3,
        psa, psd, pss, psA, psD, psC, psE,
        em0, em1, em2, em3, epp0, epp1, epp2, epp3,
        esa, esd, ess_spd, esA, esD, esC, esE,
        pc
    )
end

-------------------------------------------------
-- BATCH MANAGEMENT
-- Frame records now include game_state, menu,
-- and bag context for richer Markov matching
-------------------------------------------------
function create_frame_record(x, y, map, in_battle, menu_flag, direction, action, frame_offset, game_state)
    local gs = game_state or 0
    local record = {
        state = {
            map_id = map, x = x, y = y,
            direction = direction, in_battle = in_battle, in_menu = menu_flag,
            game_state = gs,
            menu_cursor = r8(ADDR_MENU_CURSOR),
            menu_max = r8(ADDR_MENU_MAX),
            party_cursor = r8(ADDR_PARTY_CURSOR),
            bag_pocket = r8(ADDR_BAG_POCKET),
            bag_cursor = r8(ADDR_BAG_CURSOR),
        },
        action = expand_action(action),
        recent_actions = get_recent_actions_copy(),
        frame_offset = frame_offset
    }

    -- Add battle context when in battle
    if in_battle == 1 then
        record.state.battle_cursor = r8(ADDR_BATTLE_CURSOR)
        record.state.move_cursor = r8(ADDR_MOVE_CURSOR)
        record.state.player_species = r16(ADDR_P_SPECIES)
        record.state.enemy_species = r16(ADDR_E_SPECIES)
        record.state.player_hp = r16(ADDR_P_HP)
        record.state.enemy_hp = r16(ADDR_E_HP)
    end

    return record
end

function start_dense_batch(trigger_action, x, y, map, in_battle, menu_flag, direction, game_state)
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
    local fr = create_frame_record(x, y, map, in_battle, menu_flag, direction, trigger_action, 0, game_state)
    table.insert(current_batch.frames, fr)
    total_frames_logged = total_frames_logged + 1
end

function start_steady_batch()
    if current_batch and #current_batch.frames > 0 then
        table.insert(all_batches, current_batch)
    end
    current_batch = { batch_type = "steady", frames = {} }
end

function log_frame_to_batch(x, y, map, in_battle, menu_flag, direction, action, frame_offset, game_state)
    if current_batch == nil then start_steady_batch() end
    local fr = create_frame_record(x, y, map, in_battle, menu_flag, direction, action, frame_offset, game_state)
    table.insert(current_batch.frames, fr)
    total_frames_logged = total_frames_logged + 1
    maps_visited[map] = true
end

-------------------------------------------------
-- SAVE TRANSITIONS TO JSON
-- Now includes expanded state fields
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
            f:write('"in_menu":' .. frame.state.in_menu .. ',')
            -- New v3 fields
            f:write('"game_state":' .. (frame.state.game_state or 0) .. ',')
            f:write('"menu_cursor":' .. (frame.state.menu_cursor or 0) .. ',')
            f:write('"menu_max":' .. (frame.state.menu_max or 0) .. ',')
            f:write('"party_cursor":' .. (frame.state.party_cursor or 0) .. ',')
            f:write('"bag_pocket":' .. (frame.state.bag_pocket or 0) .. ',')
            f:write('"bag_cursor":' .. (frame.state.bag_cursor or 0))
            -- Battle context (optional)
            if frame.state.battle_cursor then
                f:write(',"battle_cursor":' .. frame.state.battle_cursor)
                f:write(',"move_cursor":' .. (frame.state.move_cursor or 0))
                f:write(',"player_species":' .. (frame.state.player_species or 0))
                f:write(',"enemy_species":' .. (frame.state.enemy_species or 0))
                f:write(',"player_hp":' .. (frame.state.player_hp or 0))
                f:write(',"enemy_hp":' .. (frame.state.enemy_hp or 0))
            end
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
            local tile_data = r16(ADDR_BG0_TILEMAP + offset)
            t[#t + 1] = string.format("%.3f", (tile_data & 0x3FF) / 1024.0)
        end
    end
    cached_tiles_str = table.concat(t, ",")
    t = nil
end

-------------------------------------------------
-- STATE WRITERS
-- Now include: gs, mu, bg, pa, b fields
-------------------------------------------------
function write_minimal_state(x, y, map, in_battle, menu_flag, direction, game_state)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    f:write('{"s":[' .. x .. ',' .. y .. ',' .. map .. ',' ..
            in_battle .. ',' .. menu_flag .. ',' .. direction ..
            '],"gs":' .. game_state .. ',"dead":false,' ..
            get_battle_string(in_battle) .. ',' ..
            get_party_string() .. ',' ..
            get_menu_string() ..
            ',"ic":' .. input_count .. '}')
    f:close()
end

function write_full_state(x, y, map, in_battle, menu_flag, direction, game_state)
    local f = io.open(STATE_FILE, "w")
    if not f then return end

    local battle_cursor = r8(ADDR_BATTLE_CURSOR)

    f:write('{"s":[' .. x .. ',' .. y .. ',' .. map .. ',' ..
            in_battle .. ',' .. menu_flag .. ',' .. direction ..
            '],"gs":' .. game_state .. ',"dead":false,' ..
            get_battle_string(in_battle) .. ',' ..
            get_party_string() .. ',' ..
            get_menu_string() .. ',' ..
            get_bag_string(game_state, in_battle, battle_cursor))

    if #cached_palette_str > 0 then
        f:write(',"p":[' .. cached_palette_str .. ']')
    end
    if #cached_tiles_str > 0 then
        f:write(',"t":[' .. cached_tiles_str .. ']')
    end
    f:write(',"ic":' .. input_count .. '}')
    f:close()
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
local frame_counter = 0

print("==========================================")
print("Pokemon AI v3 — TEACHING MODE")
print("==========================================")
print("OVERWORLD:")
print("  X: 0x02036E48  Y: 0x02036E4A")
print("  Map: 0x02036E44  Dir: 0x02036E50")
print("  Battle: 0x0202000A")
print("  GameState: 0x020204C2 (0=OW,1=menu,14=bag)")
print("MENU SYSTEM:")
print("  MenuCursor: 0x0203ADE6 (universal)")
print("  MenuMaxIdx: 0x0203ADE8")
print("  PartyCursor: 0x0203B0A9")
print("  SwapCursor:  0x0203B0AA")
print("BAG SYSTEM:")
print("  BagPocket: 0x0203AD02 (0-4)")
print("  BagCursor: 0x0203AD04")
print("  SB1 ptr: 0x03005008  SB2 ptr: 0x0300500C")
print("  Qty key: SB2+0x0F20 (XOR)")
print("BATTLE UI:")
print("  BattleCursor: 0x02023FF8")
print("  MoveCursor:   0x02023FFC")
print("  BattleType:   0x02022B4C")
print("PLAYER MIRROR (base 0x02023BE4)")
print("ENEMY MIRROR (base 0x02023C3C, +0x58)")
print("PARTY (base 0x02024284, stride 0x64)")
print("==========================================")

update_visual_cache()
update_bag_caches()
print(string.format("SB1=0x%08X BagKey=%d", sb1_cache, bag_key_cache))
collectgarbage("collect")

while true do
    local human_action = get_human_action()
    local x = r8(ADDR_PLAYER_X)
    local y = r8(ADDR_PLAYER_Y)
    local map = r8(ADDR_MAP_ID)
    local direction = normalize_direction(r8(ADDR_DIRECTION))
    local battle_flag = r8(ADDR_BATTLE)
    local game_state = r8(ADDR_GAME_STATE)
    local in_battle = (battle_flag == 1) and 1 or 0
    local menu_flag = (game_state > 0 and in_battle == 0) and 1 or 0

    -- Transition logging with expanded state
    if human_action ~= nil and human_action ~= previous_action then
        add_to_recent_actions(human_action)
        start_dense_batch(human_action, x, y, map, in_battle, menu_flag, direction, game_state)
        previous_action = human_action
    elseif dense_logging_countdown > 0 then
        if frame_counter % DENSE_FRAME_INTERVAL == 0 then
            log_frame_to_batch(x, y, map, in_battle, menu_flag, direction, human_action,
                              DENSE_BATCH_FRAMES - dense_logging_countdown, game_state)
        end
        dense_logging_countdown = dense_logging_countdown - 1
        if dense_logging_countdown == 0 then start_steady_batch() end
    else
        sparse_frame_counter = sparse_frame_counter + 1
        if sparse_frame_counter >= SPARSE_FRAME_INTERVAL then
            if human_action ~= nil then
                add_to_recent_actions(human_action)
                log_frame_to_batch(x, y, map, in_battle, menu_flag, direction, human_action, 0, game_state)
            end
            sparse_frame_counter = 0
        end
    end

    if human_action then
        cache_input(human_action, x, y, map, in_battle, menu_flag, direction)
    end

    -- Periodic updates
    if frame_counter % VISUAL_UPDATE_RATE == 0 then update_visual_cache() end
    if frame_counter % 30 == 0 then update_bag_caches() end  -- refresh bag key periodically

    if frame_counter % STATE_WRITE_INTERVAL == 0 then
        write_full_state(x, y, map, in_battle, menu_flag, direction, game_state)
    end
    if (frame_counter % CACHE_FLUSH_INTERVAL == 0 and frame_counter > 0) or
       (input_count >= MAX_INPUT_BUFFER) then
        flush_input_cache()
    end
    if frame_counter % GC_INTERVAL == 0 then collectgarbage("collect") end

    -- Debug output
    if frame_counter % 600 == 0 then
        local mc = r8(ADDR_MENU_CURSOR)
        local mm = r8(ADDR_MENU_MAX)
        local pc = r8(ADDR_PARTY_CURSOR)
        local bp = r8(ADDR_BAG_POCKET)
        local bcur = r8(ADDR_BAG_CURSOR)

        if in_battle == 1 then
            local bc = r8(ADDR_BATTLE_CURSOR)
            local moc = r8(ADDR_MOVE_CURSOR)
            local ps = r16(ADDR_P_SPECIES)
            local es = r16(ADDR_E_SPECIES)
            local ph = r16(ADDR_P_HP)
            local eh = r16(ADDR_E_HP)
            local bt = r8(ADDR_BATTLE_TYPE)
            local bt_str = (bt % 16 >= 8) and "TRAINER" or "WILD"
            local mem = collectgarbage("count")
            print(string.format(
                "F:%d | %s bc:%d mc:%d | P:%d hp:%d E:%d hp:%d | Menu:%d/%d PC:%d | Buf:%d | Mem:%.1fKB",
                frame_counter, bt_str, bc, moc, ps, ph, es, eh,
                mc, mm, pc, input_count, mem))
        else
            local gs_names = {[0]="OW", [1]="MENU", [14]="BAG"}
            local gs_str = gs_names[game_state] or string.format("GS%d", game_state)
            local party_count = r8(ADDR_PARTY_COUNT)
            local hp = r16(PARTY_BASE + 0x56)
            local mhp = r16(PARTY_BASE + 0x58)
            local mem = collectgarbage("count")

            local extra = ""
            if game_state == 14 then
                local pnames = {[0]="Items", [1]="Key", [2]="Ball", [3]="TMs", [4]="Berry"}
                extra = string.format(" Bag:%s cur:%d", pnames[bp] or "?", bcur)
            elseif game_state > 0 then
                extra = string.format(" Menu:%d/%d PC:%d", mc, mm, pc)
            end

            print(string.format(
                "F:%d | %s (%d,%d) Map:%d Dir:%d | Party:%d HP:%d/%d%s | Buf:%d Bat:%d Fr:%d | Mem:%.1fKB",
                frame_counter, gs_str, x, y, map, direction,
                party_count, hp, mhp, extra,
                input_count, #all_batches, total_frames_logged, mem))
        end
    end

    frame_counter = frame_counter + 1
    emu.frameadvance()
end