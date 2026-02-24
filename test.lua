-------------------------------------------------
-- STATUS CONDITION SCANNER
-- Finds where status conditions are stored in
-- the battle mirror for both player and enemy
--
-- CONTROLS:
--   START  = Take snapshot
--   SELECT = Compare snapshots
--   B      = Reset
--
-- HOW TO USE:
--   When a status happens (poison, sleep, etc):
--   1. SS1 should be from BEFORE the status
--      (take it at battle start as habit)
--   2. SS2: After status is applied
--   3. SELECT to compare
--
--   IDEAL FLOW:
--   1. Enter battle
--   2. SS1: Baseline (no status on anyone)
--   3. Status happens (poison/sleep/paralyze)
--   4. SS2: After status text shows
--   5. SELECT to compare
--
--   STATUS ENCODING (Gen III):
--     0 = none
--     1-7 = sleep (turns remaining)
--     8 = poison (bit 3)
--     16 = burn (bit 4)
--     32 = freeze (bit 5)
--     64 = paralysis (bit 6)
--     128 = toxic/bad poison (bit 7)
--
-- Scans the full player and enemy battle structs
-- plus party slot 0 status for cross-reference
-------------------------------------------------

function safe_u8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function safe_u16(addr)
    local ok, val = pcall(memory.read_u16_le, addr)
    return (ok and val) or 0
end

function safe_u32(addr)
    local ok, val = pcall(memory.read_u32_le, addr)
    return (ok and val) or 0
end

-------------------------------------------------
-- STATUS DECODER
-------------------------------------------------
function decode_status(val)
    if val == 0 then return "healthy" end
    local parts = {}
    local sleep = val % 8  -- bits 0-2
    if sleep > 0 then table.insert(parts, string.format("SLEEP(%d turns)", sleep)) end
    if val % 16 >= 8 then table.insert(parts, "POISON") end
    if val % 32 >= 16 then table.insert(parts, "BURN") end
    if val % 64 >= 32 then table.insert(parts, "FREEZE") end
    if val % 128 >= 64 then table.insert(parts, "PARALYSIS") end
    if val >= 128 then table.insert(parts, "TOXIC") end
    if #parts == 0 then return string.format("unknown(%d)", val) end
    return table.concat(parts, "+")
end

-------------------------------------------------
-- SCAN RANGES
-------------------------------------------------
local scan_regions = {
    {
        name = "PLAYER BATTLE STRUCT",
        start_addr = 0x02023BE4,
        end_addr   = 0x02023C3B,
    },
    {
        name = "ENEMY BATTLE STRUCT",
        start_addr = 0x02023C3C,
        end_addr   = 0x02023C93,
    },
    {
        name = "PRE-PLAYER",
        start_addr = 0x02023B80,
        end_addr   = 0x02023BE3,
    },
    {
        name = "POST-ENEMY",
        start_addr = 0x02023C94,
        end_addr   = 0x02023D20,
    },
}

-- Known landmarks
local LABELS = {
    [0x02023BE4] = "PlayerSpecies",
    [0x02023BF0] = "Move0 ID",
    [0x02023BFD] = "P.StatATK",
    [0x02023BFE] = "P.StatDEF",
    [0x02023C08] = "PP0",
    [0x02023C09] = "PP1",
    [0x02023C0A] = "PP2",
    [0x02023C0C] = "PlayerHP",
    [0x02023C0E] = "PlayerLevel",
    [0x02023C10] = "PlayerMaxHP",
    [0x02023C3C] = "EnemySpecies",
    [0x02023C48] = "E.Move0 ID",
    [0x02023C55] = "E.StatATK",
    [0x02023C60] = "E.PP0",
    [0x02023C64] = "EnemyHP",
    [0x02023C66] = "EnemyLevel",
    [0x02023C68] = "EnemyMaxHP",
    [0x020242D4] = "Party0 Status",
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
            snap[addr] = safe_u8(addr)
        end
    end
    -- Also grab party status and u32 reads at key locations
    snap["party0_status"] = safe_u32(0x020242D4)
    snap["battle_flag"] = safe_u8(0x0202000A)
    snap["player_hp"] = safe_u16(0x02023C0C)
    snap["enemy_hp"] = safe_u16(0x02023C64)
    snap["player_species"] = safe_u16(0x02023BE4)
    snap["enemy_species"] = safe_u16(0x02023C3C)
    return snap
end

function auto_label()
    local in_battle = safe_u8(0x0202000A) == 1
    if not in_battle then return "OVERWORLD" end
    local php = safe_u16(0x02023C0C)
    local ehp = safe_u16(0x02023C64)
    local p_status = safe_u32(0x020242D4)
    return string.format("BATTLE PHP=%d EHP=%d PartyStatus=%d(%s)",
        php, ehp, p_status, decode_status(p_status))
end

-------------------------------------------------
-- COMPARISON
-------------------------------------------------
function print_comparison()
    if #snapshots < 2 then
        if #snapshots == 1 then
            print("Need at least 2 snapshots.")
        else
            print("No snapshots yet.")
        end
        return
    end

    print("")
    print("=====================================================================")
    print("  STATUS CONDITION SCAN — " .. #snapshots .. " snapshots")
    print("=====================================================================")

    for i, label in ipairs(snap_labels) do
        local snap = snapshots[i]
        print(string.format("  S%d = %s", i, label))
        print(string.format("       Party0 status: %d (%s)",
            snap["party0_status"], decode_status(snap["party0_status"])))
    end

    -- === PHASE 1: Find bytes that changed and match status encoding ===
    print("")
    print("  ====== STATUS VALUE CANDIDATES ======")
    print("  Looking for bytes that went from 0 to a status value")
    print("  Status values: 1-7=sleep, 8=poison, 16=burn,")
    print("  32=freeze, 64=paralysis, 128=toxic")
    print("")

    local status_values = {1,2,3,4,5,6,7,8,16,32,64,128}
    local status_set = {}
    for _, v in ipairs(status_values) do status_set[v] = true end

    for _, region in ipairs(scan_regions) do
        local found_in_region = false

        for addr = region.start_addr, region.end_addr do
            local vals = {}
            local changed = false
            for i, snap in ipairs(snapshots) do
                vals[i] = snap[addr] or 0
                if i > 1 and vals[i] ~= vals[1] then changed = true end
            end

            if changed then
                -- Check if any value matches a status encoding
                local has_status_val = false
                local was_zero = false
                for i, v in ipairs(vals) do
                    if status_set[v] then has_status_val = true end
                    if v == 0 then was_zero = true end
                end

                if has_status_val and was_zero then
                    if not found_in_region then
                        print(string.format("  --- %s ---", region.name))
                        found_in_region = true
                    end

                    local lbl = LABELS[addr] or ""
                    local offset = ""
                    if addr >= 0x02023BE4 and addr <= 0x02023C3B then
                        offset = string.format("player+0x%02X", addr - 0x02023BE4)
                    elseif addr >= 0x02023C3C and addr <= 0x02023C93 then
                        offset = string.format("enemy+0x%02X", addr - 0x02023C3C)
                    end

                    local line = string.format("  >>> 0x%08X %-14s %-16s:", addr, offset, lbl)
                    for i = 1, #snapshots do
                        local decoded = decode_status(vals[i])
                        line = line .. string.format(" S%d=%d(%s)", i, vals[i], decoded)
                    end
                    print(line)

                    -- Also check as u32
                    local u32_line = string.format("      as u32:")
                    for i, snap in ipairs(snapshots) do
                        -- Reconstruct u32 from 4 bytes
                        local b0 = snap[addr] or 0
                        local b1 = snap[addr+1] or 0
                        local b2 = snap[addr+2] or 0
                        local b3 = snap[addr+3] or 0
                        local v32 = b0 + b1*256 + b2*65536 + b3*16777216
                        u32_line = u32_line .. string.format(" S%d=%d(%s)", i, v32, decode_status(v32))
                    end
                    print(u32_line)
                    print("")
                end
            end
        end
    end

    -- === PHASE 2: ALL changes (for context) ===
    print("")
    print("  ====== ALL CHANGED BYTES ======")

    for _, region in ipairs(scan_regions) do
        local changes = {}

        for addr = region.start_addr, region.end_addr do
            local vals = {}
            local changed = false
            for i, snap in ipairs(snapshots) do
                vals[i] = snap[addr] or 0
                if i > 1 and vals[i] ~= vals[1] then changed = true end
            end

            if changed then
                table.insert(changes, {addr = addr, vals = vals})
            end
        end

        if #changes > 0 then
            print(string.format("\n  --- %s (%d changed) ---", region.name, #changes))

            local hdr = string.format("  %-12s %-14s %-16s", "Address", "Offset", "Label")
            for i = 1, #snapshots do
                hdr = hdr .. string.format(" |S%-4d", i)
            end
            print(hdr)
            print("  " .. string.rep("-", 50 + #snapshots * 7))

            for _, ch in ipairs(changes) do
                local lbl = LABELS[ch.addr] or ""
                local offset = ""
                if ch.addr >= 0x02023BE4 and ch.addr <= 0x02023C3B then
                    offset = string.format("player+0x%02X", ch.addr - 0x02023BE4)
                elseif ch.addr >= 0x02023C3C and ch.addr <= 0x02023C93 then
                    offset = string.format("enemy+0x%02X", ch.addr - 0x02023C3C)
                end

                local line = string.format("  0x%08X  %-14s %-16s", ch.addr, offset, lbl)
                for i = 1, #snapshots do
                    line = line .. string.format(" |%-5d", ch.vals[i])
                end
                print(line)
            end
        end
    end

    -- === PHASE 3: Party status cross-reference ===
    print("")
    print("  ====== PARTY STATUS CROSS-REFERENCE ======")
    local ps_line = "  Party slot 0 status (0x020242D4 u32):"
    for i, snap in ipairs(snapshots) do
        local val = snap["party0_status"]
        ps_line = ps_line .. string.format(" S%d=%d(%s)", i, val, decode_status(val))
    end
    print(ps_line)
    print("")
    print("  If player got statused, party status should match")
    print("  a battle mirror address. Look for same value above.")

    print("")
    print("=====================================================================")
end

-------------------------------------------------
-- MAIN LOOP
-------------------------------------------------
print("")
print("=============================================")
print("  STATUS CONDITION SCANNER")
print("=============================================")
print("")
print("  CONTROLS:")
print("    START  = Take snapshot")
print("    SELECT = Compare")
print("    B      = Reset")
print("")
print("  WHEN STATUS HAPPENS:")
print("    SS1 = Before status (battle start)")
print("    SS2 = After status applied")
print("    SELECT to compare")
print("")
print("  STATUS ENCODING:")
print("    0 = healthy")
print("    1-7 = sleep (turns)")
print("    8 = poison")
print("    16 = burn")
print("    32 = freeze")
print("    64 = paralysis")
print("    128 = toxic")
print("=============================================")
print("")

-- Show current party status
local p0s = safe_u32(0x020242D4)
print(string.format("Current party0 status: %d (%s)", p0s, decode_status(p0s)))
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
        print(string.format("    Party0 status: %d (%s)",
            snap["party0_status"], decode_status(snap["party0_status"])))
        print("")

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