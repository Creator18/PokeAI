-------------------------------------------------
-- CONFIG
-------------------------------------------------
BASE_PATH = "C:/Users/natmaw/Documents/Boston Stuff/CS 5100 Foundations of AI/PokeAI/"
STATE_FILE = BASE_PATH .. "game_state.json"
INPUT_FILE = BASE_PATH .. "input_cache.txt"

-- TIMING CONFIG
CACHE_FLUSH_INTERVAL = 1800  -- 30 seconds at 60fps
STATE_WRITE_INTERVAL = 60    -- Write state every 1 second
VISUAL_UPDATE_RATE = 300     -- Update visuals every 5 seconds (reduced!)

-- MEMORY MANAGEMENT
GC_INTERVAL = 600            -- Force garbage collection every 10 seconds
MAX_INPUT_BUFFER = 500       -- Emergency flush if buffer gets too big

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
-- INPUT CACHE - Use table instead of string concat
-------------------------------------------------
local input_lines = {}  -- Table of lines, NOT string concatenation
local input_count = 0

-------------------------------------------------
-- VISUAL CACHE - Reuse tables instead of recreating
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

-------------------------------------------------
-- DETECT HUMAN INPUT
-------------------------------------------------
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

-------------------------------------------------
-- CACHE INPUT - Table append (much faster than string concat)
-------------------------------------------------
function cache_input(action, x, y, map, in_battle, menu_flag, direction)
    if action == nil then return end
    
    -- Use table insert instead of string concatenation
    input_count = input_count + 1
    input_lines[input_count] = action .. "," .. x .. "," .. y .. "," .. 
                                map .. "," .. in_battle .. "," .. menu_flag .. "," .. direction
end

-------------------------------------------------
-- FLUSH INPUT CACHE TO FILE
-------------------------------------------------
function flush_input_cache()
    if input_count == 0 then return end
    
    local f = io.open(INPUT_FILE, "w")
    if f then
        -- Join all lines at once (single allocation)
        f:write(table.concat(input_lines, "\n"))
        f:close()
    end
    
    print(string.format(">> FLUSHED %d inputs", input_count))
    
    -- CLEAR: Reset table and count
    for i = 1, input_count do
        input_lines[i] = nil
    end
    input_count = 0
    
    -- Force garbage collection after flush
    collectgarbage("collect")
end

-------------------------------------------------
-- WRITE MINIMAL STATE
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
-- UPDATE VISUAL CACHE (reuse string buffer)
-------------------------------------------------
function update_visual_cache()
    -- Palette - build in chunks to reduce allocations
    local p = {}
    for i = 0, 255 do
        local addr = ADDR_BG_PALETTE + (i * 2)
        local ok, color = pcall(memory.read_u16_le, addr)
        if ok and color then
            local b = ((color >> 10) & 0x1F) / 31.0
            local g = ((color >> 5) & 0x1F) / 31.0
            local r = (color & 0x1F) / 31.0
            p[#p + 1] = string.format("%.2f,%.2f,%.2f", r, g, b)
        else
            p[#p + 1] = "0,0,0"
        end
    end
    cached_palette_str = table.concat(p, ",")
    p = nil  -- Help GC
    
    -- Tiles
    local t = {}
    for y = 0, 19 do
        for x = 0, 29 do
            local offset = (y * 32 + x) * 2
            local tile_data = safe_read_u16(ADDR_BG0_TILEMAP + offset)
            t[#t + 1] = string.format("%.3f", (tile_data & 0x3FF) / 1024.0)
        end
    end
    cached_tiles_str = table.concat(t, ",")
    t = nil  -- Help GC
end

-------------------------------------------------
-- WRITE FULL STATE
-------------------------------------------------
function write_full_state(x, y, map, in_battle, menu_flag, direction)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    
    f:write('{"s":[' .. x .. ',' .. y .. ',' .. map .. ',' .. 
            in_battle .. ',' .. menu_flag .. ',' .. direction .. 
            '],"ic":' .. input_count)
    
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
print("Pokemon AI - TEACHING MODE (MEMORY SAFE)")
print("==========================================")
print("GC every 10 sec, Max buffer: 500 inputs")
print("==========================================")

-- Initialize
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

    -- Cache input
    if human_action then
        cache_input(human_action, x, y, map, in_battle, menu_flag, direction)
    end

    -- Update visuals (every 5 seconds)
    if frame_counter % VISUAL_UPDATE_RATE == 0 then
        update_visual_cache()
    end

    -- Write state (every 1 second)
    if frame_counter % STATE_WRITE_INTERVAL == 0 then
        write_full_state(x, y, map, in_battle, menu_flag, direction)
    end

    -- Flush on interval OR if buffer too large
    local should_flush = (frame_counter % CACHE_FLUSH_INTERVAL == 0 and frame_counter > 0) or
                         (input_count >= MAX_INPUT_BUFFER)
    
    if should_flush then
        flush_input_cache()
    end

    -- Periodic garbage collection
    if frame_counter % GC_INTERVAL == 0 then
        collectgarbage("collect")
    end

    -- Status (every 10 seconds)
    if frame_counter % 600 == 0 then
        local mem = collectgarbage("count")
        print(string.format("Frame:%d | Buf:%d | Mem:%.1fKB", frame_counter, input_count, mem))
    end

    frame_counter = frame_counter + 1
    emu.frameadvance()
end