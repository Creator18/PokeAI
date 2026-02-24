-------------------------------------------------
-- CONFIG - AI MODE v2
-------------------------------------------------
BASE_PATH = "C:/Users/HP/Documents/cogai/"
ACTION_FILE = BASE_PATH .. "action.json"
STATE_FILE  = BASE_PATH .. "game_state.json"

-------------------------------------------------
-- MEMORY ADDRESSES — ALL VERIFIED
-------------------------------------------------

-- === OVERWORLD ===
ADDR_PLAYER_X   = 0x02036E48   -- u8
ADDR_PLAYER_Y   = 0x02036E4A   -- u8
ADDR_MAP_ID     = 0x02036E44   -- u8
ADDR_DIRECTION  = 0x02036E50   -- u8 (raw: 17/34/51/68)
ADDR_BATTLE     = 0x0202000A   -- u8 (1=in battle)
ADDR_GAME_STATE = 0x020204C2   -- u8

-- === BATTLE UI ===
ADDR_BATTLE_CURSOR = 0x02023FF8 -- u8: 0=Fight,1=Bag,2=Pokemon,3=Run
ADDR_MOVE_CURSOR   = 0x02023FFC -- u8: 0-3
ADDR_PARTY_CURSOR  = 0x0203B0A9 -- u8: 0-5, 6=cancel
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
-- Offsets from slot base:
--   +0x50 = status (u32)
--   +0x54 = level (u8)
--   +0x56 = hp (u16)
--   +0x58 = maxhp (u16)
--   +0x5A = atk (u16)
--   +0x5C = def (u16)
--   +0x5E = spd (u16)
--   +0x60 = spatk (u16)
--   +0x62 = spdef (u16)

-- === GBA VIDEO ===
ADDR_BG_PALETTE  = 0x05000000
ADDR_BG0_TILEMAP = 0x06000000

-- Timing
VISUAL_UPDATE_RATE = 30
TILE_UPDATE_RATE   = 15

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
function read_action()
    local f = io.open(ACTION_FILE, "r")
    if not f then return nil end
    local c = f:read("*all")
    f:close()
    return c:match('"action"%s*:%s*"(.-)"')
end

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

-------------------------------------------------
-- PALETTE EXTRACTION
-------------------------------------------------
function get_palette_string()
    local p = {}
    for i = 0, 255 do
        local ok, color = pcall(memory.read_u16_le, ADDR_BG_PALETTE + (i * 2))
        if ok and color then
            local b = ((color >> 10) & 0x1F) / 31.0
            local g = ((color >> 5) & 0x1F) / 31.0
            local r = (color & 0x1F) / 31.0
            p[#p + 1] = string.format("%.3f,%.3f,%.3f", r, g, b)
        else
            p[#p + 1] = "0,0,0"
        end
    end
    return table.concat(p, ",")
end

-------------------------------------------------
-- TILE MAP EXTRACTION
-------------------------------------------------
function get_tiles_string()
    local p = {}
    for y = 0, 19 do
        for x = 0, 29 do
            local offset = (y * 32 + x) * 2
            local td = r16(ADDR_BG0_TILEMAP + offset)
            p[#p + 1] = string.format("%.3f", (td & 0x3FF) / 1024.0)
        end
    end
    return table.concat(p, ",")
end

-------------------------------------------------
-- PARTY DATA EXTRACTION
-- Reads all occupied party slots
-- Short keys: level=l, hp=h, maxhp=m, atk=a,
-- def=d, spd=sp, spatk=sa, spdef=sd, status=st
-------------------------------------------------
function get_party_string()
    local count = r8(ADDR_PARTY_COUNT)
    local parts = {}

    for i = 0, 5 do
        local base = PARTY_BASE + (i * PARTY_SLOT_SIZE)
        local lv  = r8(base + 0x54)
        local hp  = r16(base + 0x56)
        local mhp = r16(base + 0x58)

        -- Empty slot detection
        if mhp == 0 and lv == 0 then
            break
        end

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
-- BATTLE DATA EXTRACTION
-- Short keys for JSON size:
--   bc=battle cursor, mc=move cursor
--   ps=player species, es=enemy species
--   ph=player hp, pm=player maxhp
--   eh=enemy hp, em=enemy maxhp
--   pl=player level, el=enemy level
--   pst=player status, est=enemy status
--   bt=battle type
--   m0-m3=player move IDs
--   pp0-pp3=player move PP
--   pss=player stat stages [atk,def,spd,spatk,spdef,acc,eva]
--   em0-em3=enemy move IDs
--   epp0-epp3=enemy move PP
--   ess=enemy stat stages
--   pc=party cursor
-------------------------------------------------
function get_battle_string(in_battle)
    if in_battle == 0 then
        -- Minimal data outside battle
        return string.format(
            '"b":{"bc":-1,"mc":-1,"ps":-1,"es":-1,"ph":-1,"pm":-1,"eh":-1,"em":-1,"pl":-1,"el":-1,"pst":0,"est":0,"bt":0,"m0":-1,"m1":-1,"m2":-1,"m3":-1,"pp0":-1,"pp1":-1,"pp2":-1,"pp3":-1,"pss":[-1,-1,-1,-1,-1,-1,-1],"em0":-1,"em1":-1,"em2":-1,"em3":-1,"epp0":-1,"epp1":-1,"epp2":-1,"epp3":-1,"ess":[-1,-1,-1,-1,-1,-1,-1],"pc":-1}'
        )
    end

    -- Full battle data
    local bc  = r8(ADDR_BATTLE_CURSOR)
    local mc  = r8(ADDR_MOVE_CURSOR)
    local pc  = r8(ADDR_PARTY_CURSOR)
    local bt  = r8(ADDR_BATTLE_TYPE)

    -- Player
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

    -- Player stat stages
    local psa = r8(ADDR_P_STAT_ATK)
    local psd = r8(ADDR_P_STAT_DEF)
    local pss = r8(ADDR_P_STAT_SPD)
    local psA = r8(ADDR_P_STAT_SPATK)
    local psD = r8(ADDR_P_STAT_SPDEF)
    local psC = r8(ADDR_P_STAT_ACC)
    local psE = r8(ADDR_P_STAT_EVA)

    -- Enemy
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

    -- Enemy stat stages
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
-- FILE WRITER
-- Keys: s=state, p=palette, t=tiles, b=battle, pa=party
-------------------------------------------------
local cached_palette_str = ""
local cached_tiles_str = ""

function write_state(x, y, map, in_battle, menu_flag, direction, include_visual)
    local f = io.open(STATE_FILE, "w")
    if not f then return end

    f:write('{"s":[')
    f:write(string.format('%d,%d,%d,%d,%d,%d', x, y, map, in_battle, menu_flag, direction))
    f:write('],"dead":false')

    -- Battle data (always included, -1 for unavailable)
    f:write(',' .. get_battle_string(in_battle))

    -- Party data (always included, lightweight)
    f:write(',' .. get_party_string())

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
print("Pokemon AI v2 — Full Battle Data")
print("==========================================")
print("OVERWORLD:")
print("  X: 0x02036E48  Y: 0x02036E4A")
print("  Map: 0x02036E44  Dir: 0x02036E50")
print("  Battle: 0x0202000A  State: 0x020204C2")
print("BATTLE UI:")
print("  BattleCursor: 0x02023FF8")
print("  MoveCursor:   0x02023FFC")
print("  PartyCursor:  0x0203B0A9")
print("  BattleType:   0x02022B4C (4=wild,12=trainer)")
print("PLAYER MIRROR (base 0x02023BE4):")
print("  Species: +0x00  Moves: +0x0C-0x12")
print("  StatStages: +0x19-0x1F  PP: +0x24-0x27")
print("  HP: +0x28  Level: +0x2A  MaxHP: +0x2C")
print("  Status: +0x4C")
print("ENEMY MIRROR (base 0x02023C3C, +0x58):")
print("  Same layout as player")
print("PARTY (base 0x02024284, stride 0x64):")
print("  Count: 0x02024029")
print("  Per slot: status+0x50 level+0x54 hp+0x56")
print("  maxhp+0x58 atk+0x5A def+0x5C spd+0x5E")
print("  spatk+0x60 spdef+0x62")
print("==========================================")
print("Actions: " .. ACTION_FILE)
print("State:   " .. STATE_FILE)
print("==========================================")

-- Initial visual cache
cached_palette_str = get_palette_string()
cached_tiles_str = get_tiles_string()

while true do
    local action = read_action()

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

    local x = r8(ADDR_PLAYER_X)
    local y = r8(ADDR_PLAYER_Y)
    local map = r8(ADDR_MAP_ID)
    local raw_dir = r8(ADDR_DIRECTION)
    local direction = normalize_direction(raw_dir)
    local battle_flag = r8(ADDR_BATTLE)
    local game_state = r8(ADDR_GAME_STATE)
    local in_battle = (battle_flag == 1) and 1 or 0
    local menu_flag = (game_state == 1) and 1 or 0

    -- Visual cache update
    local include_visual = false
    if frame_counter % VISUAL_UPDATE_RATE == 0 then
        cached_palette_str = get_palette_string()
        include_visual = true
    end
    if frame_counter % TILE_UPDATE_RATE == 0 then
        cached_tiles_str = get_tiles_string()
        include_visual = true
    end

    -- Write state
    write_state(x, y, map, in_battle, menu_flag, direction, include_visual or (frame_counter % 5 == 0))

    -- Debug output
    if frame_counter % 60 == 0 then
        if in_battle == 1 then
            local bc = r8(ADDR_BATTLE_CURSOR)
            local mc = r8(ADDR_MOVE_CURSOR)
            local ps = r16(ADDR_P_SPECIES)
            local es = r16(ADDR_E_SPECIES)
            local ph = r16(ADDR_P_HP)
            local eh = r16(ADDR_E_HP)
            local pl = r8(ADDR_P_LEVEL)
            local el = r8(ADDR_E_LEVEL)
            local bt = r8(ADDR_BATTLE_TYPE)
            local pst = r32(ADDR_P_STATUS)
            local est = r32(ADDR_E_STATUS)
            local pp0 = r8(ADDR_P_PP0)
            local pp1 = r8(ADDR_P_PP1)
            local pp2 = r8(ADDR_P_PP2)
            local pp3 = r8(ADDR_P_PP3)
            local bt_str = (bt % 16 >= 8) and "TRAINER" or "WILD"

            print(string.format(
                "F:%d | %s | bc:%d mc:%d | P:%d Lv%d %d/%d st:%d | E:%d Lv%d %d/%d st:%d | PP:%d/%d/%d/%d | %s",
                frame_counter, bt_str, bc, mc,
                ps, pl, ph, r16(ADDR_P_MAXHP), pst,
                es, el, eh, r16(ADDR_E_MAXHP), est,
                pp0, pp1, pp2, pp3,
                action or "nil"
            ))
        else
            local pc = r8(ADDR_PARTY_COUNT)
            local hp = r16(PARTY_BASE + 0x56)
            local mhp = r16(PARTY_BASE + 0x58)
            print(string.format(
                "F:%d | Pos:(%d,%d) Map:%d Dir:%d | Party:%d HP:%d/%d | %s",
                frame_counter, x, y, map, direction, pc, hp, mhp,
                action or "nil"
            ))
        end
    end

    frame_counter = frame_counter + 1
    emu.frameadvance()
end