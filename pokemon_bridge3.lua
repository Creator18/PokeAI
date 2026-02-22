-------------------------------------------------
-- CONFIG - AI MODE
-------------------------------------------------
BASE_PATH = "C:/Users/HP/Documents/cogai/"
ACTION_FILE = BASE_PATH .. "action.json"
STATE_FILE  = BASE_PATH .. "game_state.json"

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

-- Timing
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
function get_palette_string()
    local parts = {}
    for i = 0, 255 do
        local addr = ADDR_BG_PALETTE + (i * 2)
        local ok, color = pcall(memory.read_u16_le, addr)
        
        if ok and color then
            local b = ((color >> 10) & 0x1F) / 31.0
            local g = ((color >> 5) & 0x1F) / 31.0
            local r = (color & 0x1F) / 31.0
            parts[#parts + 1] = string.format("%.3f,%.3f,%.3f", r, g, b)
        else
            parts[#parts + 1] = "0,0,0"
        end
    end
    return table.concat(parts, ",")
end

-------------------------------------------------
-- TILE MAP EXTRACTION
-------------------------------------------------
function get_tiles_string()
    local parts = {}
    
    for y = 0, 19 do
        for x = 0, 29 do
            local offset = (y * 32 + x) * 2
            local tile_data = safe_read_u16(ADDR_BG0_TILEMAP + offset)
            local tile_id = tile_data & 0x3FF
            parts[#parts + 1] = string.format("%.3f", tile_id / 1024.0)
        end
    end
    
    return table.concat(parts, ",")
end

-------------------------------------------------
-- BATTLE DATA EXTRACTION
-- Only reads when in battle (saves cycles in overworld)
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
-- FILE WRITER
-- Uses short keys: s, p, t, b
-- b = battle data (new, ignored by old Python code)
-------------------------------------------------
local cached_palette_str = ""
local cached_tiles_str = ""

function write_state(x, y, map, in_battle, menu_flag, direction, include_visual)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    
    f:write('{"s":[')
    f:write(string.format('%d,%d,%d,%d,%d,%d', x, y, map, in_battle, menu_flag, direction))
    f:write('],"dead":false')
    
    -- Battle data — always included, uses -1 for unavailable fields
    f:write(',' .. get_battle_string(in_battle))
    
    if include_visual then
        if #cached_palette_str > 0 then
            f:write(',"p":[' .. cached_palette_str .. ']')
        end
        if #cached_tiles_str > 0 then
            f:write(',"t":[' .. cached_tiles_str .. ']')
        end
    end
    
    f:write('}')
    f:close()
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
local frame_counter = 0

print("==========================================")
print("Pokemon AI - AI MODE (Python Control)")
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
print("Reading actions from: " .. ACTION_FILE)
print("Writing state to: " .. STATE_FILE)
print("==========================================")

-- Initial visual cache
cached_palette_str = get_palette_string()
cached_tiles_str = get_tiles_string()

while true do
    -- Read action from Python
    local action = read_action()

    if action ~= nil then
        joypad.set({
            A = (action == "A"),
            B = (action == "B"),
            Up = (action == "UP"),
            Down = (action == "DOWN"),
            Left = (action == "LEFT"),
            Right = (action == "RIGHT"),
            Start = (action == "START"),
            Select = (action == "SELECT")
        })
    end

    -- Read game state
    local x = safe_read_u8(ADDR_PLAYER_X)
    local y = safe_read_u8(ADDR_PLAYER_Y)
    local map = safe_read_u8(ADDR_MAP_ID)
    local raw_direction = safe_read_u8(ADDR_DIRECTION)
    local direction = normalize_direction(raw_direction)
    
    local battle_flag = safe_read_u8(ADDR_BATTLE)
    local game_state = safe_read_u8(ADDR_GAME_STATE)
    
    local in_battle = (battle_flag == 1) and 1 or 0
    local menu_flag = (game_state == 1) and 1 or 0

    -- Update visual cache periodically
    local include_visual = false
    if frame_counter % VISUAL_UPDATE_RATE == 0 then
        cached_palette_str = get_palette_string()
        include_visual = true
    end
    if frame_counter % TILE_UPDATE_RATE == 0 then
        cached_tiles_str = get_tiles_string()
        include_visual = true
    end

    -- Write state for Python
    write_state(x, y, map, in_battle, menu_flag, direction, include_visual or (frame_counter % 5 == 0))

    -- Debug print every 60 frames
    if frame_counter % 60 == 0 then
        if in_battle == 1 then
            local bc = safe_read_u8(ADDR_BATTLE_MENU_CURSOR)
            local mc = safe_read_u8(ADDR_MOVE_MENU_CURSOR)
            local ps = safe_read_u16(ADDR_PLAYER_SPECIES)
            local es = safe_read_u16(ADDR_ENEMY_SPECIES)
            local ph = safe_read_u16(ADDR_PLAYER_HP_BATTLE)
            local eh = safe_read_u16(ADDR_ENEMY_HP_BATTLE)
            print(string.format("Frame:%d | BATTLE | Cursor:%d Move:%d | %d(hp:%d) vs %d(hp:%d) | Action:%s",
                frame_counter, bc, mc, ps, ph, es, eh, action or "nil"))
        else
            print(string.format("Frame:%d | Pos:(%d,%d) Map:%d Dir:%d | Battle:%d Menu:%d | Action:%s",
                frame_counter, x, y, map, direction, in_battle, menu_flag, action or "nil"))
        end
    end

    frame_counter = frame_counter + 1
    emu.frameadvance()
end