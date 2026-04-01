-------------------------------------------------
-- CONFIG
-------------------------------------------------
BASE_PATH = "C:/Users/HP/Documents/cogai/"
ACTION_FILE = BASE_PATH .. "action.json"
STATE_FILE  = BASE_PATH .. "game_state.json"

-------------------------------------------------
-- MEMORY ADDRESSES (VERIFIED)
-------------------------------------------------
ADDR_PLAYER_X   = 0x02036E48
ADDR_PLAYER_Y   = 0x02036E4A
ADDR_MAP_ID     = 0x02036E44
ADDR_DIRECTION  = 0x02036E50
ADDR_BATTLE     = 0x0202000A    -- 0=no battle, 1=in battle
ADDR_GAME_STATE = 0x020204C2    -- 0=overworld, 1=menu, 35=battle

-- GBA Video Memory
ADDR_BG_PALETTE = 0x05000000
ADDR_BG0_TILEMAP = 0x06000000

VISUAL_UPDATE_RATE = 30
TILE_UPDATE_RATE = 15

-------------------------------------------------
-- DIRECTION MAPPING
-- Raw values: DOWN=17, UP=34, LEFT=51, RIGHT=68
-------------------------------------------------
function normalize_direction(raw_dir)
    if raw_dir == 17 then return 0      -- DOWN
    elseif raw_dir == 34 then return 1  -- UP
    elseif raw_dir == 51 then return 2  -- LEFT
    elseif raw_dir == 68 then return 3  -- RIGHT
    else return raw_dir % 4
    end
end

-------------------------------------------------
-- HELPERS
-------------------------------------------------
function read_action()
    local f = io.open(ACTION_FILE, "r")
    if not f then return nil end
    local content = f:read("*all")
    f:close()
    return content:match('"action"%s*:%s*"(.-)"')
end

function safe_read_u8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function safe_read_u16(addr)
    local ok, val = pcall(memory.read_u16_le, addr)
    return (ok and val) or 0
end

-------------------------------------------------
-- PALETTE EXTRACTION
-------------------------------------------------
function get_palette_colors()
    local colors = {}
    for i = 0, 255 do
        local addr = ADDR_BG_PALETTE + (i * 2)
        local ok, color = pcall(memory.read_u16_le, addr)
        
        if ok and color then
            local b = ((color >> 10) & 0x1F) / 31.0
            local g = ((color >> 5) & 0x1F) / 31.0
            local r = (color & 0x1F) / 31.0
            table.insert(colors, r)
            table.insert(colors, g)
            table.insert(colors, b)
        else
            table.insert(colors, 0.0)
            table.insert(colors, 0.0)
            table.insert(colors, 0.0)
        end
    end
    return colors
end

-------------------------------------------------
-- TILE MAP EXTRACTION
-------------------------------------------------
function get_tile_map()
    local tiles = {}
    
    for y = 0, 19 do
        for x = 0, 29 do
            local offset = (y * 32 + x) * 2
            local tile_data = safe_read_u16(ADDR_BG0_TILEMAP + offset)
            local tile_id = tile_data & 0x3FF
            table.insert(tiles, tile_id / 1024.0)
        end
    end
    
    return tiles
end

-------------------------------------------------
-- DETECT GAME MODE (uses both flags)
-------------------------------------------------
function get_game_mode(battle_flag, game_state)
    -- Double verification for reliability
    if battle_flag == 1 and game_state > 1 then
        return "battle"
    elseif battle_flag == 0 and game_state == 1 then
        return "menu"
    elseif battle_flag == 0 and game_state == 0 then
        return "overworld"
    else
        -- Fallback: trust battle_flag primarily
        if battle_flag == 1 then
            return "battle"
        elseif game_state == 1 then
            return "menu"
        else
            return "overworld"
        end
    end
end

-------------------------------------------------
-- FILE WRITER
-------------------------------------------------
function write_state_with_visual(x, y, map, in_battle, menu_flag, direction, palette, tiles)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    
    local json_parts = {}
    table.insert(json_parts, '{"state":[')
    table.insert(json_parts, string.format('%d,%d,%d,%d,%d,%d', 
        x, y, map, in_battle, menu_flag, direction))
    table.insert(json_parts, '],"dead":false,"palette":[')
    
    for i, v in ipairs(palette) do
        if i > 1 then table.insert(json_parts, ",") end
        table.insert(json_parts, string.format("%.3f", v))
    end
    
    table.insert(json_parts, '],"tiles":[')
    
    for i, v in ipairs(tiles) do
        if i > 1 then table.insert(json_parts, ",") end
        table.insert(json_parts, string.format("%.3f", v))
    end
    
    table.insert(json_parts, ']}')
    f:write(table.concat(json_parts))
    f:close()
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
local frame_counter = 0
local last_palette = {}
local last_tiles = {}

print("==========================================")
print("Pokemon AI - Lua Script (VERIFIED)")
print("==========================================")
print("ADDRESSES:")
print("  X:        0x02036E48")
print("  Y:        0x02036E4A")
print("  Map:      0x02036E44")
print("  Direction:0x02036E50 (raw: 17/34/51/68)")
print("  Battle:   0x0202000A (0/1)")
print("  State:    0x020204C2 (0=ow, 1=menu, 35=bat)")
print("==========================================")

while true do
    local action = read_action()

    if action ~= nil then
        joypad.set({
            A = (action == "A"), B = (action == "B"),
            Up = (action == "UP"), Down = (action == "DOWN"),
            Left = (action == "LEFT"), Right = (action == "RIGHT"),
            Start = (action == "START"), Select = (action == "SELECT")
        })
    end

    -- Read all values
    local x = safe_read_u8(ADDR_PLAYER_X)
    local y = safe_read_u8(ADDR_PLAYER_Y)
    local map = safe_read_u8(ADDR_MAP_ID)
    local raw_direction = safe_read_u8(ADDR_DIRECTION)
    local direction = normalize_direction(raw_direction)
    
    local battle_flag = safe_read_u8(ADDR_BATTLE)
    local game_state = safe_read_u8(ADDR_GAME_STATE)
    
    -- Derive in_battle and menu_flag for Python
    local in_battle = (battle_flag == 1) and 1 or 0
    local menu_flag = (game_state == 1) and 1 or 0
    
    local mode = get_game_mode(battle_flag, game_state)

    -- Debug print every 60 frames
    if frame_counter % 60 == 0 then
        print(string.format("Pos:(%d,%d) Map:%d Dir:%d | Battle:%d State:%d | Mode:%s",
            x, y, map, direction, battle_flag, game_state, mode))
    end

    -- Update palette
    local palette = last_palette
    if frame_counter % VISUAL_UPDATE_RATE == 0 then
        palette = get_palette_colors()
        last_palette = palette
    end
    
    -- Update tiles
    local tiles = last_tiles
    if frame_counter % TILE_UPDATE_RATE == 0 then
        tiles = get_tile_map()
        last_tiles = tiles
    end

    -- Write state
    write_state_with_visual(x, y, map, in_battle, menu_flag, direction, palette, tiles)

    frame_counter = frame_counter + 1
    emu.frameadvance()
end