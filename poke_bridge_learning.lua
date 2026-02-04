-------------------------------------------------
-- CONFIG
-------------------------------------------------
BASE_PATH = "C:/Users/natmaw/Documents/Boston Stuff/CS 5100 Foundations of AI/cogai/"
STATE_FILE = BASE_PATH .. "game_state.json"
INPUT_FILE = BASE_PATH .. "input_cache.txt"  -- Separate lightweight file for inputs

-- TIMING CONFIG
CACHE_FLUSH_INTERVAL = 1800  -- 30 seconds at 60fps
STATE_WRITE_INTERVAL = 60    -- Write full state every 1 second
VISUAL_UPDATE_RATE = 120     -- Update visuals every 2 seconds

-------------------------------------------------
-- MEMORY ADDRESSES
-------------------------------------------------
ADDR_PLAYER_X   = 0x02036E48
ADDR_PLAYER_Y   = 0x02036E4A
ADDR_MAP_ID     = 0x02036E44
ADDR_DIRECTION  = 0x02036E50
ADDR_BATTLE     = 0x0202000A
ADDR_GAME_STATE = 0x020204C2
ADDR_BG_PALETTE = 0x05000000
ADDR_BG0_TILEMAP = 0x06000000

-------------------------------------------------
-- INPUT CACHE - Simple string buffer
-------------------------------------------------
local input_buffer = ""
local input_count = 0
local cache_start_frame = 0

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

-------------------------------------------------
-- DETECT HUMAN INPUT (returns nil if none)
-------------------------------------------------
function get_human_action()
    local input = joypad.get()
    
    if input.A then return "A"
    elseif input.B then return "B"
    elseif input.Start then return "S"  -- Shortened
    elseif input.Select then return "E"  -- Shortened
    elseif input.Up then return "U"
    elseif input.Down then return "D"
    elseif input.Left then return "L"
    elseif input.Right then return "R"
    else return nil
    end
end

-------------------------------------------------
-- CACHE INPUT - Just append to string buffer
-- Format: "ACTION,X,Y,MAP,BATTLE,MENU,DIR\n"
-------------------------------------------------
function cache_input(action, x, y, map, in_battle, menu_flag, direction)
    if action == nil then return end
    
    input_buffer = input_buffer .. action .. "," .. x .. "," .. y .. "," .. 
                   map .. "," .. in_battle .. "," .. menu_flag .. "," .. direction .. "\n"
    input_count = input_count + 1
end

-------------------------------------------------
-- FLUSH INPUT CACHE TO FILE
-------------------------------------------------
function flush_input_cache()
    if input_count == 0 then return end
    
    local f = io.open(INPUT_FILE, "w")
    if f then
        f:write(input_buffer)
        f:close()
    end
    
    print(string.format(">> FLUSHED %d inputs", input_count))
    
    -- CLEAR THE CACHE
    input_buffer = ""
    input_count = 0
end

-------------------------------------------------
-- WRITE MINIMAL STATE (no visuals unless needed)
-------------------------------------------------
function write_minimal_state(x, y, map, in_battle, menu_flag, direction)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    
    f:write('{"s":[' .. x .. ',' .. y .. ',' .. map .. ',' .. 
            in_battle .. ',' .. menu_flag .. ',' .. direction .. 
            '],"ic":' .. input_count .. '}')
    f:close()
end

-------------------------------------------------
-- WRITE FULL STATE WITH VISUALS (rarely)
-------------------------------------------------
local cached_palette_str = nil
local cached_tiles_str = nil

function update_visual_cache()
    -- Build palette string
    local p_parts = {}
    for i = 0, 255 do
        local addr = ADDR_BG_PALETTE + (i * 2)
        local ok, color = pcall(memory.read_u16_le, addr)
        if ok and color then
            local b = ((color >> 10) & 0x1F) / 31.0
            local g = ((color >> 5) & 0x1F) / 31.0
            local r = (color & 0x1F) / 31.0
            table.insert(p_parts, string.format("%.2f,%.2f,%.2f", r, g, b))
        else
            table.insert(p_parts, "0,0,0")
        end
    end
    cached_palette_str = table.concat(p_parts, ",")
    
    -- Build tiles string
    local t_parts = {}
    for y = 0, 19 do
        for x = 0, 29 do
            local offset = (y * 32 + x) * 2
            local tile_data = safe_read_u16(ADDR_BG0_TILEMAP + offset)
            local tile_id = (tile_data & 0x3FF) / 1024.0
            table.insert(t_parts, string.format("%.3f", tile_id))
        end
    end
    cached_tiles_str = table.concat(t_parts, ",")
end

function write_full_state(x, y, map, in_battle, menu_flag, direction)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    
    f:write('{"s":[' .. x .. ',' .. y .. ',' .. map .. ',' .. 
            in_battle .. ',' .. menu_flag .. ',' .. direction .. 
            '],"ic":' .. input_count)
    
    if cached_palette_str then
        f:write(',"p":[' .. cached_palette_str .. ']')
    end
    if cached_tiles_str then
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
print("Pokemon AI - TEACHING MODE (OPTIMIZED)")
print("==========================================")
print("Input flush: every 30 sec")
print("State write: every 1 sec")
print("Visual update: every 2 sec")
print("==========================================")

-- Initialize visual cache
update_visual_cache()

while true do
    local human_action = get_human_action()

    local x = safe_read_u8(ADDR_PLAYER_X)
    local y = safe_read_u8(ADDR_PLAYER_Y)
    local map = safe_read_u8(ADDR_MAP_ID)
    local direction = normalize_direction(safe_read_u8(ADDR_DIRECTION))
    local in_battle = (safe_read_u8(ADDR_BATTLE) == 1) and 1 or 0
    local menu_flag = (safe_read_u8(ADDR_GAME_STATE) == 1) and 1 or 0

    -- Cache input (only if button pressed)
    if human_action then
        cache_input(human_action, x, y, map, in_battle, menu_flag, direction)
    end

    -- Update visual cache (every 2 seconds)
    if frame_counter % VISUAL_UPDATE_RATE == 0 then
        update_visual_cache()
    end

    -- Write state (every 1 second)
    if frame_counter % STATE_WRITE_INTERVAL == 0 then
        write_full_state(x, y, map, in_battle, menu_flag, direction)
    end

    -- Flush input cache (every 30 seconds)
    if frame_counter % CACHE_FLUSH_INTERVAL == 0 and frame_counter > 0 then
        flush_input_cache()
        cache_start_frame = frame_counter
    end

    -- Status display (every 10 seconds)
    if frame_counter % 600 == 0 then
        print(string.format("Frame:%d | Pos:(%d,%d) Map:%d | Buffered:%d",
            frame_counter, x, y, map, input_count))
    end

    frame_counter = frame_counter + 1
    emu.frameadvance()
end