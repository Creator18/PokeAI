-------------------------------------------------
-- CONFIG (EDIT THIS PATH)
-------------------------------------------------
BASE_PATH = "C:/Users/natmaw/Documents/Boston Stuff/CS 5100 Foundations of AI/cogai/"

ACTION_FILE = BASE_PATH .. "action.json"
STATE_FILE  = BASE_PATH .. "game_state.json"

-------------------------------------------------
-- MEMORY ADDRESSES (FireRed - US)
-------------------------------------------------
ADDR_PLAYER_X   = 0x02036E48
ADDR_PLAYER_Y   = 0x02036E4A
ADDR_MAP_ID     = 0x02036E44
ADDR_HP_CURRENT = 0x02024284          -- not set yet 
ADDR_HP_MAX     = 0x02024286          -- not set yet 

-- --- NEW STATE SIGNALS ---
ADDR_IN_BATTLE          = 0x0202000A  -- 0 = overworld, 1 = battle
ADDR_MENU_FLAG          = 0x020204C2  -- 0 = no menu, >0 = menu open
ADDR_DIRECTION_FACING   = 0x02036E50  -- 0–3 direction

-------------------------------------------------
-- HELPERS
-------------------------------------------------
function read_action()
    local f = io.open(ACTION_FILE, "r")
    if not f then return nil end
    local content = f:read("*all")
    f:close()

    local action = content:match('"action"%s*:%s*"(.-)"')
    return action
end

function write_state(state)
    local f = io.open(STATE_FILE, "w")
    if not f then return end
    f:write(state)
    f:close()
end

-- Safe memory read: u16
function safe_read_u16(addr)
    local ok, val = pcall(memory.read_u16_le, addr)
    if ok and val ~= nil then
        return val
    else
        return 0
    end
end

-- Safe memory read: u8
function safe_read_u8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    if ok and val ~= nil then
        return val
    else
        return 0
    end
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
while true do
    ---------------------------------------------
    -- READ ACTION FROM PYTHON
    ---------------------------------------------
    local action = read_action()

    joypad.set({})  -- clear all buttons

    if action ~= nil then
        joypad.set({
            A      = (action == "A"),
            B      = (action == "B"),
            Up     = (action == "UP"),
            Down   = (action == "DOWN"),
            Left   = (action == "LEFT"),
            Right  = (action == "RIGHT"),
            Start  = (action == "START"),
            Select = (action == "SELECT")
        })
    end

    ---------------------------------------------
    -- READ GAME STATE
    ---------------------------------------------
    local x          = safe_read_u16(ADDR_PLAYER_X)
    local y          = safe_read_u16(ADDR_PLAYER_Y)
    local map        = safe_read_u16(ADDR_MAP_ID)
    local hp_cur     = safe_read_u16(ADDR_HP_CURRENT)
    local hp_max     = safe_read_u16(ADDR_HP_MAX)

    local in_battle  = safe_read_u8(ADDR_IN_BATTLE)
    local menu_flag  = safe_read_u8(ADDR_MENU_FLAG)
    local direction  = safe_read_u8(ADDR_DIRECTION_FACING)

    local dead = (hp_cur <= 0)

    ---------------------------------------------
    -- WRITE STATE TO PYTHON
    ---------------------------------------------
    -- State vector (8 dims):
    -- x, y, map, hp_cur, hp_max, in_battle, menu_flag, direction
    local json = string.format(
        '{"state":[%d,%d,%d,%d,%d,%d,%d,%d],"dead":%s}',
        x,
        y,
        map,
        hp_cur,
        hp_max,
        in_battle,
        menu_flag,
        direction,
        tostring(dead)
    )

    write_state(json)

    ---------------------------------------------
    -- ADVANCE ONE FRAME
    ---------------------------------------------
    emu.frameadvance()
end
