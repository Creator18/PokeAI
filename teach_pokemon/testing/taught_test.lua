-------------------------------------------------
-- DIALOGUE SCANNER — BATTLE TEXT TEST
-- Uses SELECT for snapshot (safe in battle —
-- SELECT does nothing during battle)
--
-- Test: does 0x0202004F (tf) go to 1 during
-- battle text like "A wild PIDGEY appeared!"
--
-- SELECT toggle:
--   1st: BEFORE snapshot
--   2nd: AFTER snapshot + compare
--   Repeats.
-------------------------------------------------

local SCAN_REGIONS = {
    {start = 0x02020000, size = 0x10,  name = "window_base"},
    {start = 0x02020004, size = 0x90,  name = "text_printers"},
    {start = 0x02020040, size = 0x30,  name = "text_flags_wide"},
    {start = 0x020204C0, size = 0x20,  name = "game_state"},
    {start = 0x02037070, size = 0x20,  name = "lock_flags"},
    {start = 0x02037080, size = 0x10,  name = "ow_state"},
    {start = 0x020375F0, size = 0x20,  name = "field_msg"},
    {start = 0x0203B0A0, size = 0x10,  name = "menu_choice"},
}

function r8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function take_snapshot()
    local snap = {}
    for _, region in ipairs(SCAN_REGIONS) do
        for offset = 0, region.size - 1 do
            local addr = region.start + offset
            snap[addr] = {val = r8(addr), region = region.name}
        end
    end
    return snap
end

function compare_and_report(before, after)
    local diffs = {}
    for addr, data1 in pairs(before) do
        local data2 = after[addr]
        if data2 and data1.val ~= data2.val then
            diffs[#diffs + 1] = {
                addr = addr, region = data1.region,
                before = data1.val, after = data2.val
            }
        end
    end
    table.sort(diffs, function(a, b) return a.addr < b.addr end)
    
    print("")
    print("===== SCAN #" .. scan_count .. " =====")
    print("Diffs: " .. #diffs)
    
    if #diffs == 0 then
        print("  No differences."); return
    end
    
    for _, d in ipairs(diffs) do
        local tag = ""
        if d.addr == 0x020204C2 then tag = " *GAME_STATE"
        elseif d.addr == 0x0202004F then tag = " *TEXT_FLAG"
        elseif d.addr == 0x02020050 then tag = " *TEXT_STATE"
        elseif d.addr == 0x0202000A then tag = " *BATTLE_FLAG"
        end
        local star = (d.before == 0 and d.after > 0) and "★" or " "
        print(string.format(" %s 0x%08X [%-14s] %3d→%3d%s",
            star, d.addr, d.region, d.before, d.after, tag))
    end
    print("=================")
end

local scan_state = 0
local snapshot_before = {}
local cooldown = 0
scan_count = 0

print("BATTLE DIALOGUE TEST")
print("SELECT: BEFORE / AFTER toggle")
print("")
print("TEST PLAN:")
print("  1. Walk in grass, SELECT before battle")
print("  2. When 'A wild X appeared!' shows, SELECT")
print("  3. Check if tf (0x0202004F) goes 0→1")
print("")
print("Also test:")
print("  - Battle menu (Fight/Bag/Run) visible")
print("  - Move selection screen")
print("  - 'X used Y!' attack text")
print("  - 'Enemy fainted!' text")

while true do
    local input = joypad.get()
    
    if cooldown > 0 then cooldown = cooldown - 1 end
    
    if input.Select and cooldown == 0 then
        cooldown = 30
        
        if scan_state == 0 then
            snapshot_before = take_snapshot()
            scan_state = 1
            scan_count = scan_count + 1
            local gs = r8(0x020204C2); local tf = r8(0x0202004F)
            local ts = r8(0x02020050); local btl = r8(0x0202000A)
            print(string.format("BEFORE #%d | gs:%d tf:%d ts:%d btl:%d",
                scan_count, gs, tf, ts, btl))
        else
            local snapshot_after = take_snapshot()
            scan_state = 0
            local gs = r8(0x020204C2); local tf = r8(0x0202004F)
            local ts = r8(0x02020050); local btl = r8(0x0202000A)
            print(string.format("AFTER #%d  | gs:%d tf:%d ts:%d btl:%d",
                scan_count, gs, tf, ts, btl))
            compare_and_report(snapshot_before, snapshot_after)
        end
    end
    
    emu.frameadvance()
end