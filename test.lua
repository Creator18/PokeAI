-------------------------------------------------
-- START MENU CURSOR SCANNER
-- Finds start menu open flag, cursor position,
-- and menu item count in Pokemon FireRed
--
-- CONTROLS:
--   START  = Take snapshot
--   SELECT = Compare snapshots
--   B      = Reset
--
-- HOW TO USE:
--   1. SS1: In overworld, menu CLOSED
--   2. Press START to open start menu
--   3. SS2: Menu open, cursor on first item
--   4. Move cursor DOWN one slot
--   5. SS3: Cursor on second item
--   6. Move cursor DOWN again
--   7. SS4: Cursor on third item
--   8. SELECT to compare
--
--   WHAT TO LOOK FOR:
--   - Menu open flag: 0→nonzero between SS1→SS2
--   - Cursor byte: incrementing 0→1→2 across SS2→SS3→SS4
--   - Menu count: stable nonzero while menu is open
--
--   FireRed start menu order (after getting Pokedex):
--     0 = Pokedex
--     1 = Pokemon
--     2 = Bag
--     3 = (Player Name / Trainer Card)
--     4 = Save
--     5 = Option
--     6 = Exit
--   Early game (no Pokedex yet):
--     0 = Pokemon
--     1 = Bag
--     ...etc shifted
--
-- Scans broad RAM regions where UI state lives
-------------------------------------------------

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
-- SCAN REGIONS
-- Battle cursors were at 0x02023FF8, 0x02023FFC
-- Party cursor at 0x0203B0A9
-- Game state at 0x020204C2
-- Broad scan of likely UI regions
-------------------------------------------------
local scan_regions = {
    {
        name = "GAME STATE AREA",
        start_addr = 0x02020000,
        end_addr   = 0x02020600,
    },
    {
        name = "BATTLE UI AREA (may have menu reuse)",
        start_addr = 0x02023F00,
        end_addr   = 0x02024100,
    },
    {
        name = "MENU/UI REGION A",
        start_addr = 0x0203A000,
        end_addr   = 0x0203B200,
    },
    {
        name = "MENU/UI REGION B",
        start_addr = 0x0203F000,
        end_addr   = 0x02040000,
    },
}

-- Known landmarks for context
local LABELS = {
    [0x0202000A] = "BattleFlag",
    [0x020204C2] = "GameState",
    [0x02023FF8] = "BattleCursor",
    [0x02023FFC] = "MoveCursor",
    [0x02024029] = "PartyCount",
    [0x0203B0A9] = "PartyCursor",
}

-------------------------------------------------
-- SNAPSHOT SYSTEM
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
    -- Context reads
    snap["game_state"] = r8(0x020204C2)
    snap["battle_flag"] = r8(0x0202000A)
    return snap
end

function auto_label()
    local gs = r8(0x020204C2)
    local bf = r8(0x0202000A)
    return string.format("GameState=%d BattleFlag=%d", gs, bf)
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
    print("  START MENU SCAN — " .. #snapshots .. " snapshots")
    print("=====================================================================")

    for i, label in ipairs(snap_labels) do
        print(string.format("  S%d = %s", i, label))
    end

    -- === PHASE 1: CURSOR CANDIDATES ===
    -- Look for bytes that increment by 1 across consecutive snapshots
    -- Pattern: stays same S1→S2 (or changes), then increments S2→S3→S4
    print("")
    print("  ====== CURSOR CANDIDATES (incrementing pattern) ======")
    print("  Looking for bytes that go 0→1→2 or N→N+1→N+2")
    print("")

    for _, region in ipairs(scan_regions) do
        local found = false

        for addr = region.start_addr, region.end_addr do
            local vals = {}
            for i, snap in ipairs(snapshots) do
                vals[i] = snap[addr] or 0
            end

            -- Check for incrementing pattern across 3+ consecutive snapshots
            -- We want at least 2 consecutive increments of exactly 1
            local has_increment = false
            local inc_start = -1

            for i = 2, #vals do
                if vals[i] == vals[i-1] + 1 then
                    if inc_start < 0 then inc_start = i - 1 end
                    if i - inc_start >= 2 then
                        has_increment = true
                        break
                    end
                else
                    inc_start = -1
                end
            end

            -- Also catch: value stays in small range 0-7 and changes
            local in_menu_range = true
            local changed = false
            for i, v in ipairs(vals) do
                if v > 10 then in_menu_range = false end
                if i > 1 and v ~= vals[1] then changed = true end
            end

            if has_increment then
                if not found then
                    print(string.format("  --- %s ---", region.name))
                    found = true
                end

                local lbl = LABELS[addr] or ""
                local line = string.format("  >>> 0x%08X %-16s:", addr, lbl)
                for i = 1, #snapshots do
                    line = line .. string.format(" S%d=%d", i, vals[i])
                end
                line = line .. "  << INCREMENTING"
                print(line)
            end
        end
    end

    -- === PHASE 2: MENU OPEN FLAG CANDIDATES ===
    -- Look for bytes that go 0→nonzero between S1 (closed) and S2 (open)
    -- and stay nonzero while menu is open
    print("")
    print("  ====== MENU OPEN FLAG CANDIDATES ======")
    print("  Bytes that changed from 0→nonzero at S1→S2")
    print("  (assuming S1=menu closed, S2+=menu open)")
    print("")

    if #snapshots >= 2 then
        for _, region in ipairs(scan_regions) do
            local found = false

            for addr = region.start_addr, region.end_addr do
                local v1 = snapshots[1][addr] or 0
                local v2 = snapshots[2][addr] or 0

                -- Was 0, became nonzero
                if v1 == 0 and v2 > 0 and v2 <= 20 then
                    -- Check if it stays stable (nonzero) in later snapshots
                    local stays_nonzero = true
                    for i = 3, #snapshots do
                        if (snapshots[i][addr] or 0) == 0 then
                            stays_nonzero = false
                            break
                        end
                    end

                    if stays_nonzero then
                        if not found then
                            print(string.format("  --- %s ---", region.name))
                            found = true
                        end

                        local lbl = LABELS[addr] or ""
                        local line = string.format("  >>> 0x%08X %-16s:", addr, lbl)
                        for i = 1, #snapshots do
                            line = line .. string.format(" S%d=%d", i, snapshots[i][addr] or 0)
                        end
                        line = line .. "  << 0→NONZERO (flag?)"
                        print(line)
                    end
                end
            end
        end
    end

    -- === PHASE 3: SMALL VALUE CHANGES (menu range 0-10) ===
    -- Catches cursors that don't perfectly increment
    print("")
    print("  ====== SMALL VALUE CHANGES (range 0-10) ======")
    print("  Bytes that changed and all values stay in 0-10")
    print("")

    for _, region in ipairs(scan_regions) do
        local found = false

        for addr = region.start_addr, region.end_addr do
            local vals = {}
            local changed = false
            local all_small = true

            for i, snap in ipairs(snapshots) do
                vals[i] = snap[addr] or 0
                if i > 1 and vals[i] ~= vals[1] then changed = true end
                if vals[i] > 10 then all_small = false end
            end

            if changed and all_small then
                if not found then
                    print(string.format("  --- %s ---", region.name))
                    found = true
                end

                local lbl = LABELS[addr] or ""
                local line = string.format("  0x%08X  %-16s:", addr, lbl)
                for i = 1, #snapshots do
                    line = line .. string.format(" S%d=%d", i, vals[i])
                end
                print(line)
            end
        end
    end

    -- === PHASE 4: ALL CHANGES (condensed) ===
    print("")
    print("  ====== ALL CHANGED BYTES (summary) ======")

    local total_changes = 0
    for _, region in ipairs(scan_regions) do
        local changes = 0
        for addr = region.start_addr, region.end_addr do
            local v1 = snapshots[1][addr] or 0
            local changed = false
            for i = 2, #snapshots do
                if (snapshots[i][addr] or 0) ~= v1 then
                    changed = true
                    break
                end
            end
            if changed then changes = changes + 1 end
        end
        total_changes = total_changes + changes
        print(string.format("  %s: %d bytes changed", region.name, changes))
    end
    print(string.format("  TOTAL: %d bytes changed across all regions", total_changes))

    -- === PHASE 5: Known address states ===
    print("")
    print("  ====== KNOWN ADDRESS CROSS-REFERENCE ======")
    local known = {0x020204C2, 0x0202000A, 0x02023FF8, 0x02023FFC, 0x0203B0A9}
    for _, addr in ipairs(known) do
        local lbl = LABELS[addr] or ""
        local line = string.format("  0x%08X %-16s:", addr, lbl)
        for i, snap in ipairs(snapshots) do
            line = line .. string.format(" S%d=%d", i, snap[addr] or 0)
        end
        print(line)
    end

    print("")
    print("=====================================================================")
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
print("")
print("=============================================")
print("  START MENU CURSOR SCANNER")
print("=============================================")
print("")
print("  CONTROLS:")
print("    START  = Take snapshot")
print("    SELECT = Compare")
print("    B      = Reset")
print("")
print("  PROCEDURE:")
print("    SS1: Overworld, menu CLOSED")
print("    (open start menu)")
print("    SS2: Menu open, cursor on item 0")
print("    (move cursor DOWN)")
print("    SS3: Cursor on item 1")
print("    (move cursor DOWN)")
print("    SS4: Cursor on item 2")
print("    SELECT to compare")
print("")
print("  NOTE: START button opens the menu!")
print("  So for SS1, make sure menu is closed.")
print("  For SS2+, the menu will already be open.")
print("  Taking a snapshot while menu is open")
print("  won't re-open it (START is consumed by")
print("  the snapshot script, not the game).")
print("")
print("  ACTUALLY: START *will* toggle the menu.")
print("  Better flow:")
print("    1. Close menu if open (B)")
print("    2. SS1: menu closed")
print("    3. Open menu (START opens it AND takes SS2)")
print("       -- this means SS2 might catch the")
print("       transition frame. Wait a moment.")
print("    4. Use a MODIFIED approach:")
print("       SS1: menu closed")
print("       Open menu manually, wait")
print("       SS2: menu open, cursor pos 0")
print("       Move cursor down, wait")
print("       SS3: cursor pos 1")
print("       Move cursor down, wait")
print("       SS4: cursor pos 2")
print("       SELECT to compare")
print("")
print("  *** START takes snapshot AND may toggle menu.")
print("  *** Plan snapshots carefully around this.")
print("=============================================")
print("")

local gs = r8(0x020204C2)
local bf = r8(0x0202000A)
print(string.format("Current: GameState=%d BattleFlag=%d", gs, bf))
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

        -- Wait for START release
        while joypad.get().Start do emu.frameadvance() end
    end

    if input.Select then
        print_comparison()
        while joypad.get().Select do emu.frameadvance() end
    end

    if input.B then
        snapshots = {}
        snap_labels = {}
        snap_count = 0
        print("")
        print(">>> ALL SNAPSHOTS CLEARED")
        print("")
        while joypad.get().B do emu.frameadvance() end
    end

    emu.frameadvance()
end