-------------------------------------------------
-- BADGE ADDRESS VERIFICATION v1
-- 
-- Confirmed candidate: SB1 + 0x0EE0 + 0x104
-- (flags_base = 0x0EE0, badge byte at +0x104)
--
-- This script continuously displays the badge
-- byte value so you can verify it's correct
-- across saves, map transitions, battles, etc.
--
-- Also monitors nearby offsets in case the
-- base is off by a few bytes.
-------------------------------------------------

ADDR_SB1_PTR    = 0x03005008
ADDR_SB2_PTR    = 0x0300500C
ADDR_BATTLE     = 0x0202000A
ADDR_GAME_STATE = 0x020204C2
ADDR_MAP_ID     = 0x02036E44

-- Primary candidate
FLAGS_BASE = 0x0EE0
BADGE_BYTE_IN_FLAGS = 0x104  -- 0x820 / 8

-- Check a few nearby bases too
CHECK_BASES = { 0x0EDB, 0x0EDC, 0x0EDD, 0x0EDE, 0x0EDF, 0x0EE0, 0x0EE1, 0x0EE2, 0x0EE3, 0x0EE4, 0x0EE5 }

function r8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function r32(addr)
    local ok, val = pcall(memory.read_u32_le, addr)
    return (ok and val) or 0
end

function count_bits(byte)
    local n = 0
    local v = byte
    while v > 0 do
        n = n + (v % 2)
        v = math.floor(v / 2)
    end
    return n
end

function bits_string(byte)
    local s = ""
    for i = 7, 0, -1 do
        if byte >= 2^i then
            s = s .. "1"
            byte = byte - 2^i
        else
            s = s .. "0"
        end
    end
    return s
end

function badge_names(byte)
    local names = {"Boulder","Cascade","Thunder","Rainbow","Soul","Marsh","Volcano","Earth"}
    local owned = {}
    local v = byte
    for i = 1, 8 do
        if v % 2 == 1 then owned[#owned + 1] = names[i] end
        v = math.floor(v / 2)
    end
    if #owned == 0 then return "none" end
    return table.concat(owned, ", ")
end

local frame_counter = 0
local prev_badge_val = -1
local prev_sb1 = 0

print("=============================================")
print("  BADGE ADDRESS VERIFICATION")
print("=============================================")
print("  Primary: SB1 + 0x0EE0 + 0x104 = SB1+0x0FE4")
print("  Checking nearby bases too")
print("=============================================")
print("")
print("  WHAT TO LOOK FOR:")
print("  - 0 badges: 0x00 (00000000)")
print("  - Boulder:  0x01 (00000001)")
print("  - +Cascade: 0x03 (00000011)")
print("  - +Thunder: 0x07 (00000111)")
print("  - All 8:    0xFF (11111111)")
print("")
print("  If the value doesn't match your badge")
print("  count, check the nearby bases.")
print("=============================================")
print("")

while true do
    local sb1 = r32(ADDR_SB1_PTR)
    
    if sb1 ~= prev_sb1 and sb1 ~= 0 then
        print(string.format("  [F:%d] SB1 pointer: 0x%08X", frame_counter, sb1))
        prev_sb1 = sb1
    end
    
    if sb1 ~= 0 then
        local primary_addr = sb1 + FLAGS_BASE + BADGE_BYTE_IN_FLAGS
        local badge_val = r8(primary_addr)
        
        -- Print on change or every 5 seconds
        if badge_val ~= prev_badge_val then
            print("")
            print(string.format(
                "  >>> BADGE CHANGE at F:%d: 0x%02X → 0x%02X",
                frame_counter,
                (prev_badge_val >= 0) and prev_badge_val or 0,
                badge_val
            ))
            print(string.format(
                "      Bits: %s  Count: %d  Badges: %s",
                bits_string(badge_val), count_bits(badge_val),
                badge_names(badge_val)
            ))
            print(string.format(
                "      Addr: 0x%08X (SB1+0x%04X)",
                primary_addr, FLAGS_BASE + BADGE_BYTE_IN_FLAGS
            ))
            
            -- Show all nearby bases when change happens
            print("")
            print("      Nearby bases check:")
            for _, base in ipairs(CHECK_BASES) do
                local addr = sb1 + base + BADGE_BYTE_IN_FLAGS
                local val = r8(addr)
                local marker = ""
                if base == FLAGS_BASE then marker = " << PRIMARY" end
                if val > 0 and count_bits(val) <= 8 then
                    print(string.format(
                        "        base=0x%04X  SB1+0x%04X = 0x%02X (%s) %d badges [%s]%s",
                        base, base + BADGE_BYTE_IN_FLAGS, val,
                        bits_string(val), count_bits(val),
                        badge_names(val), marker
                    ))
                else
                    print(string.format(
                        "        base=0x%04X  SB1+0x%04X = 0x%02X (%s)%s",
                        base, base + BADGE_BYTE_IN_FLAGS, val,
                        bits_string(val), marker
                    ))
                end
            end
            
            prev_badge_val = badge_val
        end
        
        -- Periodic status
        if frame_counter % 300 == 0 then
            local map = r8(ADDR_MAP_ID)
            local gs = r8(ADDR_GAME_STATE)
            local bat = r8(ADDR_BATTLE)
            print(string.format(
                "  [F:%d] Bd:%d (0x%02X) %s | Map:%d GS:%d Bat:%d",
                frame_counter, count_bits(badge_val), badge_val,
                badge_names(badge_val), map, gs, bat
            ))
        end
    end
    
    frame_counter = frame_counter + 1
    emu.frameadvance()
end