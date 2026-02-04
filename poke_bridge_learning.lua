-------------------------------------------------
-- CONFIG
-------------------------------------------------
BASE_PATH = "C:/Users/natmaw/Documents/Boston Stuff/CS 5100 Foundations of AI/cogai"
STATE_FILE  = BASE_PATH .. "game_state.json"

-------------------------------------------------
-- MEMORY ADDRESSES (VERIFIED)
-------------------------------------------------
ADDR_PLAYER_X   = 0x02036E48
ADDR_PLAYER_Y   = 0x02036E4A
ADDR_MAP_ID     = 0x02036E44
ADDR_DIRECTION  = 0x02036E50
ADDR_BATTLE     = 0x0202000A
ADDR_GAME_STATE = 0x020204C2

ADDR_BG_PALETTE = 0x05000000
ADDR_BG0_TILEMAP = 0x06000000

VISUAL_UPDATE_RATE = 30
TILE_UPDATE_RATE = 15

-------------------------------------------------
-- DIRECTION MAPPING
-------------------------------------------------
function normalize_direction(raw_dir)
    if raw_dir == 17 then return 0
    elseif raw_dir == 34 then return 1
    elseif raw_dir == 51 then return 2
    elseif raw_dir == 68 then return 3
    else return raw_dir % 4
    end
end

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

-------------------------------------------------
-- DETECT HUMAN INPUT
-------------------------------------------------
function get_human_action()
    local input = joypad.get()
    
    if input.A then return "A"
    elseif input.B then return "B"
    elseif input.Start then return "Start"
    elseif input.Select then return "Select"
    elseif input.Up then return "UP"
    elseif input.Down then return "DOWN"
    elseif input.Left then return "LEFT"
    elseif input.Right then return "RIGHT"
    else return "NONE"
    end
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
-- DETECT GAME MODE
-------------------------------------------------
function get_game_mode(battle_flag, game_state)
    if battle_flag == 1 and game_state > 1 then
        return "battle"
    elseif battle_flag == 0 and game_state == 1 then
        return "menu"
    elseif battle_flag == 0 and game_state == 0 then
        return "overworld"
    else
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
-- FILE WRITER (CORRECTED)
-------------------------------------------------
function write_state_with_visual(x, y, map, in_battle, menu_flag, direction, palette, tiles, human_action)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    
    local json_parts = {}
    table.insert(json_parts, '{"state":[')
    table.insert(json_parts, string.format('%d,%d,%d,%d,%d,%d', 
        x, y, map, in_battle, menu_flag, direction))
    table.insert(json_parts, '],"dead":false,"human_action":"')
    table.insert(json_parts, human_action)
    table.insert(json_parts, '","palette":[')
    
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
print("Pokemon AI - TEACHING MODE")
print("==========================================")
print("HUMAN IS IN CONTROL")
print("AI is observing and learning from you")
print("==========================================")

while true do
    local human_action = get_human_action()

    local x = safe_read_u8(ADDR_PLAYER_X)
    local y = safe_read_u8(ADDR_PLAYER_Y)
    local map = safe_read_u8(ADDR_MAP_ID)
    local raw_direction = safe_read_u8(ADDR_DIRECTION)
    local direction = normalize_direction(raw_direction)
    
    local battle_flag = safe_read_u8(ADDR_BATTLE)
    local game_state = safe_read_u8(ADDR_GAME_STATE)
    
    local in_battle = (battle_flag == 1) and 1 or 0
    local menu_flag = (game_state == 1) and 1 or 0
    
    local mode = get_game_mode(battle_flag, game_state)

    if frame_counter % 60 == 0 then
        print(string.format("Pos:(%d,%d) Map:%d Dir:%d | Battle:%d State:%d | Mode:%s | Human:%s",
            x, y, map, direction, battle_flag, game_state, mode, human_action))
    end

    local palette = last_palette
    if frame_counter % VISUAL_UPDATE_RATE == 0 then
        palette = get_palette_colors()
        last_palette = palette
    end
    
    local tiles = last_tiles
    if frame_counter % TILE_UPDATE_RATE == 0 then
        tiles = get_tile_map()
        last_tiles = tiles
    end

    write_state_with_visual(x, y, map, in_battle, menu_flag, direction, palette, tiles, human_action)

    frame_counter = frame_counter + 1
    emu.frameadvance()
end