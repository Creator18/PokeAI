-------------------------------------------------
-- PARTY SWAP CURSOR SCANNER
-- The swap target cursor isn't at any known addr.
-- Full region scan to find it.
--
-- CONTROLS:
--   START  = Take snapshot
--   SELECT = Compare
--
-- PROCEDURE:
--   1. Open Pokemon from start menu
--   2. Select Charmander → Switch
--   3. Charmander is "held", cursor free to move
--   4. SS1: Cursor sitting (wherever it starts)
--   5. Move cursor to Pidgey
--   6. SS2: Cursor on Pidgey
--   7. Move cursor back to Charmander
--   8. SS3: Cursor back on Charmander
--   9. SELECT to compare
-------------------------------------------------

function r8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

-------------------------------------------------
-- SCAN REGIONS — broad sweep
-------------------------------------------------
local scan_regions = {
    {
        name = "GAME STATE AREA",
        start_addr = 0x02020000,
        end_addr   = 0x02020600,
    },
    {
        name = "BATTLE UI AREA",
        start_addr = 0x02023F00,
        end_addr   = 0x02024100,
    },
    {
        name = "BAG/MENU UI",
        start_addr = 0x0203AC00,
        end_addr   = 0x0203B000,
    },
    {
        name = "PARTY CURSOR AREA",
        start_addr = 0x0203B000,
        end_addr   = 0x0203B300,
    },
    {
        name = "MENU REGION C",
        start_addr = 0x0203B300,
        end_addr   = 0x0203C000,
    },
    {
        name = "EXTENDED UI",
        start_addr = 0x0203F000,
        end_addr   = 0x02040000,
    },
}

local LABELS = {
    [0x020204C2] = "GameState",
    [0x0203ADE6] = "MenuCursor",
    [0x0203ADE8] = "MenuMaxIdx",
    [0x0203B0A9] = "PartyCursor",
    [0x0203AD02] = "BagPocket",
    [0x0203AD04] = "BagCursor",
}

-------------------------------------------------
-- SNAPSHOT
-------------------------------------------------
local snapshots = {}
local snap_labels = {}
local snap_count = 0

function take_snapshot()
    local snap = {}
    for _, region in ipairs(scan_regions) do
        for addr = region.start_addr, region.end_addr do
            snap[addr] = r8(addr)
        end
    end
    return snap
end

function auto_label()
    local gs = r8(0x020204C2)
    local mc = r8(0x0203ADE6)
    local pc = r8(0x0203B0A9)
    return string.format("GS=%d MC=%d PC=%d", gs, mc, pc)
end

-------------------------------------------------
-- COMPARISON
-------------------------------------------------
function print_comparison()
    if #snapshots < 2 then
        print("Need at least 2 snapshots.")
        return
    end

    print("")
    print("=====================================================================")
    print("  PARTY SWAP CURSOR SCAN — " .. #snapshots .. " snapshots")
    print("=====================================================================")

    for i, label in ipairs(snap_labels) do
        print(string.format("  S%d = %s", i, label))
    end

    -- === CURSOR CANDIDATES ===
    print("")
    print("  ====== CURSOR CANDIDATES (unit step, range 0-10) ======")
    print("")

    for _, region in ipairs(scan_regions) do
        local found = false

        for addr = region.start_addr, region.end_addr do
            local vals = {}
            local changed = false

            for i, snap in ipairs(snapshots) do
                vals[i] = snap[addr] or 0
                if i > 1 and vals[i] ~= vals[1] then changed = true end
            end

            if not changed then goto skip end

            local has_step = false
            for i = 2, #vals do
                local diff = vals[i] - vals[i-1]
                if diff == 1 or diff == -1 then has_step = true end
            end

            local in_range = true
            for _, v in ipairs(vals) do
                if v > 10 then in_range = false end
            end

            if has_step and in_range then
                if not found then
                    print(string.format("  --- %s ---", region.name))
                    found = true
                end

                local lbl = LABELS[addr] or ""
                local line = string.format("  >>> 0x%08X %-14s:", addr, lbl)
                for i = 1, #snapshots do
                    line = line .. string.format(" S%d=%d", i, vals[i])
                end
                print(line)
            end

            ::skip::
        end
    end

    -- === SMALL VALUE CHANGES ===
    print("")
    print("  ====== SMALL VALUE CHANGES (0-6, party range) ======")
    print("")

    for _, region in ipairs(scan_regions) do
        local found = false

        for addr = region.start_addr, region.end_addr do
            local vals = {}
            local changed = false
            local all_party = true

            for i, snap in ipairs(snapshots) do
                vals[i] = snap[addr] or 0
                if i > 1 and vals[i] ~= vals[1] then changed = true end
                if vals[i] > 6 then all_party = false end
            end

            if changed and all_party then
                if not found then
                    print(string.format("  --- %s ---", region.name))
                    found = true
                end

                local lbl = LABELS[addr] or ""
                local line = string.format("  0x%08X  %-14s:", addr, lbl)
                for i = 1, #snapshots do
                    line = line .. string.format(" S%d=%d", i, vals[i])
                end
                print(line)
            end
        end
    end

    -- === CHANGE SUMMARY ===
    print("")
    print("  ====== CHANGE SUMMARY ======")
    for _, region in ipairs(scan_regions) do
        local changes = 0
        for addr = region.start_addr, region.end_addr do
            local v1 = snapshots[1][addr] or 0
            for i = 2, #snapshots do
                if (snapshots[i][addr] or 0) ~= v1 then
                    changes = changes + 1
                    break
                end
            end
        end
        print(string.format("  %s: %d bytes changed", region.name, changes))
    end

    print("")
    print("=====================================================================")
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
print("")
print("=============================================")
print("  PARTY SWAP CURSOR SCANNER")
print("=============================================")
print("")
print("  START  = Take snapshot")
print("  SELECT = Compare")
print("")
print("  PROCEDURE:")
print("    Open Pokemon → Select mon → Switch")
print("    SS1: After selecting Switch")
print("    Move to other mon")
print("    SS2: Cursor on other mon")
print("    Move back")
print("    SS3: Cursor back")
print("    SELECT to compare")
print("=============================================")
print("")

while true do
    local input = joypad.get()

    if input.Start then
        snap_count = snap_count + 1
        local snap = take_snapshot()
        local label = string.format("SS%d — %s", snap_count, auto_label())
        table.insert(snapshots, snap)
        table.insert(snap_labels, label)

        print(string.format(">>> SS%d: %s", snap_count, label))

        while joypad.get().Start do emu.frameadvance() end
    end

    if input.Select then
        print_comparison()
        while joypad.get().Select do emu.frameadvance() end
    end

    emu.frameadvance()
end