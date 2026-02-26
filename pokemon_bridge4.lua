-------------------------------------------------
-- CONFIG - AI MODE v3
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
ADDR_GAME_STATE = 0x020204C2   -- u8 (0=OW, 1=menu/party, 14=bag)

-- === MENU SYSTEM (universal, reused across all menus) ===
ADDR_MENU_CURSOR = 0x0203ADE6  -- u8: current menu/submenu cursor
ADDR_MENU_MAX    = 0x0203ADE8  -- u8: max cursor index for current menu
-- Context-dependent meaning:
--   Start menu: 0=Pokedex,1=Pokemon,2=Bag,3=TrainerCard,4=Save,5=Option,6=Exit
--   Party submenu (OW): 0=Summary,1=Switch,2=Item,3=Cancel
--   Party submenu (battle): 0=Switch,1=Summary,2=Cancel
--   Bag item submenu: 0=Use,1=Give,2=Toss,3=Cancel
--   Give/Take submenu: 0=Give,1=Take,2=Cancel

-- === BAG SYSTEM ===
ADDR_BAG_POCKET  = 0x0203AD02  -- u8: 0=Items,1=KeyItems,2=Pokeballs,3=TMs,4=Berries
ADDR_BAG_CURSOR  = 0x0203AD04  -- u8: cursor position within pocket

-- Bag storage (read via SaveBlock pointers)
ADDR_SB1_PTR     = 0x03005008  -- u32: SaveBlock1 pointer
ADDR_SB2_PTR     = 0x0300500C  -- u32: SaveBlock2 pointer
BAG_KEY_OFFSET   = 0x0F20      -- u16 at SB2+0x0F20: XOR key for quantities

-- Pocket offsets from SaveBlock1, 4 bytes per slot (u16 item_id + u16 encrypted_qty)
BAG_ITEMS_OFFSET    = 0x0310   -- 42 slots
BAG_KEYITEMS_OFFSET = 0x03B8   -- 30 slots
BAG_BALLS_OFFSET    = 0x0430   -- 16 slots
BAG_TMS_OFFSET      = 0x0464   -- 64 slots
BAG_BERRIES_OFFSET  = 0x0564   -- 46 slots

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
ADDR_PARTY_CURSOR  = 0x0203B0A9 -- u8: 0-5, 6=cancel (also item use target)
ADDR_SWAP_CURSOR   = 0x0203B0AA -- u8: swap target cursor (during Switch)
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

-- Timing
VISUAL_UPDATE_RATE = 30
TILE_UPDATE_RATE   = 15
BAG_UPDATE_RATE    = 10        -- bag reads every 10 frames (not every frame)

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
-------------------------------------------------
function get_party_string()
    local count = r8(ADDR_PARTY_COUNT)
    local parts = {}

    for i = 0, 5 do
        local base = PARTY_BASE + (i * PARTY_SLOT_SIZE)
        local lv  = r8(base + 0x54)
        local hp  = r16(base + 0x56)
        local mhp = r16(base + 0x58)

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
-- BAG DATA EXTRACTION
-- Reads current pocket items with decryption
-- Short keys: pk=pocket, bc=bag cursor
--   items array: id=item id, q=quantity
-- Only reads when bag-relevant state is active
-------------------------------------------------
local cached_bag_str = ""
local bag_key_cache = 0
local sb1_cache = 0

function update_bag_caches()
    sb1_cache = r32(ADDR_SB1_PTR)
    local sb2 = r32(ADDR_SB2_PTR)
    bag_key_cache = r16(sb2 + BAG_KEY_OFFSET)
end

function decode_qty(raw_qty)
    -- XOR with encryption key from SaveBlock2
    local result = raw_qty ~ bag_key_cache
    -- Clamp to sane range
    if result < 0 or result > 999 then return 0 end
    return result
end

function get_bag_string(game_state, in_battle, battle_cursor)
    -- Determine if bag is relevant right now
    local bag_active = (game_state == 14) or (in_battle == 1 and battle_cursor == 1)

    local pocket = r8(ADDR_BAG_POCKET)
    local cursor = r8(ADDR_BAG_CURSOR)

    if not bag_active then
        -- Minimal bag state — just pocket and cursor (useful for context)
        return string.format('"bg":{"pk":%d,"bc":%d,"a":0,"it":[]}', pocket, cursor)
    end

    -- Bag is active — read current pocket items
    local info = BAG_POCKET_INFO[pocket]
    if not info then
        return string.format('"bg":{"pk":%d,"bc":%d,"a":1,"it":[]}', pocket, cursor)
    end

    local base = sb1_cache + info.offset
    local items = {}
    local max_read = math.min(info.slots, 20) -- cap at 20 for JSON size

    for i = 0, max_read - 1 do
        local addr = base + i * 4
        local item_id = r16(addr)
        local raw_qty = r16(addr + 2)

        if item_id == 0 then
            break -- empty slot = end of items in pocket
        end

        local qty = decode_qty(raw_qty)
        items[#items + 1] = string.format('{"id":%d,"q":%d}', item_id, qty)
    end

    return string.format('"bg":{"pk":%d,"bc":%d,"a":1,"it":[%s]}',
        pocket, cursor, table.concat(items, ","))
end

-------------------------------------------------
-- MENU DATA EXTRACTION
-- Short keys: mc=menu cursor, mm=menu max
--   pc=party cursor, sc=swap cursor
-------------------------------------------------
function get_menu_string()
    local mc = r8(ADDR_MENU_CURSOR)
    local mm = r8(ADDR_MENU_MAX)
    local pc = r8(ADDR_PARTY_CURSOR)
    local sc = r8(ADDR_SWAP_CURSOR)

    return string.format('"mu":{"mc":%d,"mm":%d,"pc":%d,"sc":%d}',
        mc, mm, pc, sc)
end

-------------------------------------------------
-- BATTLE DATA EXTRACTION
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
-- FILE WRITER
-- Keys: s=state, p=palette, t=tiles, b=battle,
--   pa=party, mu=menu, bg=bag
-------------------------------------------------
local cached_palette_str = ""
local cached_tiles_str = ""

function write_state(x, y, map, in_battle, game_state, direction, include_visual, include_bag)
    local f = io.open(STATE_FILE, "w")
    if not f then return end

    -- menu_flag: 1 if any menu is active (game_state > 0 and not in battle)
    local menu_flag = (game_state > 0 and in_battle == 0) and 1 or 0

    f:write('{"s":[')
    f:write(string.format('%d,%d,%d,%d,%d,%d', x, y, map, in_battle, menu_flag, direction))
    f:write(string.format('],"gs":%d,"dead":false', game_state))

    -- Battle data
    f:write(',' .. get_battle_string(in_battle))

    -- Party data
    f:write(',' .. get_party_string())

    -- Menu data (always — lightweight, 4 reads)
    f:write(',' .. get_menu_string())

    -- Bag data (periodic or when bag active)
    if include_bag then
        f:write(',' .. get_bag_string(game_state, in_battle, r8(ADDR_BATTLE_CURSOR)))
    elseif #cached_bag_str > 0 then
        f:write(',' .. cached_bag_str)
    end

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
print("Pokemon AI v3 — Full Menu + Bag + Battle")
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
print("  SB1 ptr: 0x03005008")
print("  SB2 ptr: 0x0300500C")
print("  Qty key: SB2+0x0F20 (XOR)")
print("  Pockets: Items+0x310, Key+0x3B8,")
print("    Balls+0x430, TMs+0x464, Berry+0x564")
print("BATTLE UI:")
print("  BattleCursor: 0x02023FF8")
print("  MoveCursor:   0x02023FFC")
print("  BattleType:   0x02022B4C")
print("PLAYER MIRROR (base 0x02023BE4):")
print("  Species+0 Moves+0C-12 Stats+19-1F")
print("  PP+24-27 HP+28 Level+2A MaxHP+2C")
print("  Status+4C")
print("ENEMY MIRROR (base 0x02023C3C, +0x58)")
print("PARTY (base 0x02024284, stride 0x64)")
print("==========================================")
print("Actions: " .. ACTION_FILE)
print("State:   " .. STATE_FILE)
print("==========================================")

-- Initial caches
cached_palette_str = get_palette_string()
cached_tiles_str = get_tiles_string()
update_bag_caches()
print(string.format("SB1=0x%08X SB2_key=%d", sb1_cache, bag_key_cache))

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

    -- Bag cache update (periodic + when bag active)
    local include_bag = false
    local bag_active = (game_state == 14) or (in_battle == 1 and r8(ADDR_BATTLE_CURSOR) == 1)
    if bag_active or (frame_counter % BAG_UPDATE_RATE == 0) then
        update_bag_caches()
        cached_bag_str = get_bag_string(game_state, in_battle, r8(ADDR_BATTLE_CURSOR))
        include_bag = true
    end

    -- Write state
    write_state(x, y, map, in_battle, game_state, direction,
                include_visual or (frame_counter % 5 == 0), include_bag)

    -- Debug output
    if frame_counter % 60 == 0 then
        local mc = r8(ADDR_MENU_CURSOR)
        local mm = r8(ADDR_MENU_MAX)
        local pc = r8(ADDR_PARTY_CURSOR)
        local sc = r8(ADDR_SWAP_CURSOR)
        local bp = r8(ADDR_BAG_POCKET)
        local bcur = r8(ADDR_BAG_CURSOR)

        if in_battle == 1 then
            local bc = r8(ADDR_BATTLE_CURSOR)
            local moc = r8(ADDR_MOVE_CURSOR)
            local ps = r16(ADDR_P_SPECIES)
            local es = r16(ADDR_E_SPECIES)
            local ph = r16(ADDR_P_HP)
            local eh = r16(ADDR_E_HP)
            local pl = r8(ADDR_P_LEVEL)
            local el = r8(ADDR_E_LEVEL)
            local bt = r8(ADDR_BATTLE_TYPE)
            local pst = r32(ADDR_P_STATUS)
            local est = r32(ADDR_E_STATUS)
            local bt_str = (bt % 16 >= 8) and "TRAINER" or "WILD"

            print(string.format(
                "F:%d | %s bc:%d mc:%d | P:%d Lv%d %d/%d st:%d | E:%d Lv%d %d/%d st:%d | Menu:%d/%d PC:%d | %s",
                frame_counter, bt_str, bc, moc,
                ps, pl, ph, r16(ADDR_P_MAXHP), pst,
                es, el, eh, r16(ADDR_E_MAXHP), est,
                mc, mm, pc,
                action or "nil"
            ))
        else
            local party_count = r8(ADDR_PARTY_COUNT)
            local hp = r16(PARTY_BASE + 0x56)
            local mhp = r16(PARTY_BASE + 0x58)

            local gs_names = {[0]="OW", [1]="MENU", [14]="BAG"}
            local gs_str = gs_names[game_state] or string.format("GS%d", game_state)

            local extra = ""
            if game_state == 14 then
                local pnames = {[0]="Items", [1]="Key", [2]="Ball", [3]="TMs", [4]="Berry"}
                extra = string.format(" | Bag:%s cur:%d", pnames[bp] or "?", bcur)
            elseif game_state > 0 then
                extra = string.format(" | Menu:%d/%d PC:%d SC:%d", mc, mm, pc, sc)
            end

            print(string.format(
                "F:%d | %s (%d,%d) Map:%d Dir:%d | Party:%d HP:%d/%d%s | %s",
                frame_counter, gs_str, x, y, map, direction,
                party_count, hp, mhp, extra,
                action or "nil"
            ))
        end
    end

    frame_counter = frame_counter + 1
    emu.frameadvance()
end