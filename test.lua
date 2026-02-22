-------------------------------------------------
-- VERIFY BATTLE MENU CURSOR ADDRESS
-- START = Take snapshot (safe in battle)
-- R = Show full comparison
-- L = Reset all
-------------------------------------------------

function safe_read_u8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function safe_read_u16(addr)
    local ok, val = pcall(memory.read_u16_le, addr)
    return (ok and val) or 0
end

-- Candidate addresses for PARTY SPECIES
-- Tight scan around 0x0203B09C (Pidgey=16 found here, near cursor 0x0203B0A9)
-- Plus the 0x020244XX area where Charmander=4 was found
local candidates = {}

-- Region 1: Tight around 0x0203B000 - 0x0203B0FF
for offset = 0, 255 do
    local addr = 0x0203B000 + offset
    table.insert(candidates, {addr = addr, name = string.format("3B0_%02X", offset)})
end

-- Region 2: 0x02024480 - 0x0202453F (around 0x020244DE)
for offset = 0, 191 do
    local addr = 0x02024480 + offset
    table.insert(candidates, {addr = addr, name = string.format("244_%02X", 0x80 + offset)})
end

-- Region 3: 0x020245E0 - 0x0202467F (around 0x0202461E)
for offset = 0, 159 do
    local addr = 0x020245E0 + offset
    table.insert(candidates, {addr = addr, name = string.format("246_%02X", offset)})
end

local snapshots = {}
local snap_count = 0

function take_snapshot()
    local snap = {}
    for _, c in ipairs(candidates) do
        snap[c.addr] = safe_read_u8(c.addr)
    end
    return snap
end

function print_snapshot(snap, label)
    print("")
    print("========== " .. label .. " ==========")
    for _, c in ipairs(candidates) do
        print(string.format("  %s (0x%08X): %3d  (0x%02X)", c.name, c.addr, snap[c.addr], snap[c.addr]))
    end
    print("==========================================")
end

function print_full_comparison()
    if #snapshots < 1 then
        print("Need at least 1 snapshot")
        return
    end
    
    -- If 2+ snapshots, do normal comparison
    if #snapshots >= 2 then
        print("")
        print("========== FULL COMPARISON ==========")
        
        local header = string.format("  %-10s %-12s", "NAME", "ADDR")
        for i = 1, #snapshots do
            header = header .. string.format(" | S%d ", i)
        end
        print(header)
        print("  " .. string.rep("-", 24 + #snapshots * 6))
        
        local changed_count = 0
        
        for _, c in ipairs(candidates) do
            local values = {}
            local all_same = true
            local first_val = snapshots[1][c.addr]
            
            for i, snap in ipairs(snapshots) do
                local val = snap[c.addr]
                table.insert(values, val)
                if val ~= first_val then all_same = false end
            end
            
            if not all_same then
                changed_count = changed_count + 1
                local line = string.format("  %-10s 0x%08X", c.name, c.addr)
                for _, v in ipairs(values) do
                    line = line .. string.format(" | %2d ", v)
                end
                
                local looks_like_cursor = true
                for _, v in ipairs(values) do
                    if v > 3 then looks_like_cursor = false end
                end
                if looks_like_cursor then
                    line = line .. " <<< CURSOR?"
                end
                
                local unique = {}
                for _, v in ipairs(values) do unique[v] = true end
                local unique_count = 0
                for _ in pairs(unique) do unique_count = unique_count + 1 end
                if unique_count == #values then
                    line = line .. " (ALL UNIQUE)"
                end
                
                print(line)
            end
        end
        
        if changed_count == 0 then
            print("  >>> NO addresses changed between snapshots!")
        else
            print(string.format("\n  %d addresses changed out of %d scanned", changed_count, #candidates))
        end
        -- Show ALL non-zero values in the 0x0203B0 region for analysis
    print("")
    print("All non-zero values near party cursor (0x0203B0XX):")
    for _, c in ipairs(candidates) do
        if c.addr >= 0x0203B000 and c.addr <= 0x0203B0FF then
            if snap[c.addr] ~= 0 then
                print(string.format("  %-10s 0x%08X = %3d (0x%02X)", c.name, c.addr, snap[c.addr], snap[c.addr]))
            end
        end
    end
    
    print("======================================")
        return
    end
    
    -- Single snapshot: find species values in party menu
    print("")
    print("========== PARTY SPECIES SCAN ==========")
    
    local snap = snapshots[1]
    
    -- Search for Charmander (4) as u8
    print("Value 4 (Charmander) as u8:")
    for _, c in ipairs(candidates) do
        if snap[c.addr] == 4 then
            print(string.format("  %-10s 0x%08X = 4", c.name, c.addr))
        end
    end
    
    -- Search for Pidgey (16) as u8
    print("")
    print("Value 16 (Pidgey) as u8:")
    for _, c in ipairs(candidates) do
        if snap[c.addr] == 16 then
            print(string.format("  %-10s 0x%08X = 16", c.name, c.addr))
        end
    end
    
    -- Search as u16 for both
    print("")
    print("Value 4 (Charmander) as u16:")
    for _, c in ipairs(candidates) do
        if c.addr % 2 == 0 then
            local val = safe_read_u16(c.addr)
            if val == 4 then
                print(string.format("  %-10s 0x%08X = 4 (u16)", c.name, c.addr))
            end
        end
    end
    
    print("")
    print("Value 16 (Pidgey) as u16:")
    for _, c in ipairs(candidates) do
        if c.addr % 2 == 0 then
            local val = safe_read_u16(c.addr)
            if val == 16 then
                print(string.format("  %-10s 0x%08X = 16 (u16)", c.name, c.addr))
            end
        end
    end
    
    -- Check if any pair of addresses near each other hold 4 and 16
    print("")
    print("Adjacent pairs (4 then 16 within 100 bytes):")
    for _, c1 in ipairs(candidates) do
        if snap[c1.addr] == 4 then
            for _, c2 in ipairs(candidates) do
                if snap[c2.addr] == 16 and c2.addr > c1.addr and (c2.addr - c1.addr) <= 100 then
                    print(string.format("  0x%08X=4  +  0x%08X=16  (gap=%d bytes)", c1.addr, c2.addr, c2.addr - c1.addr))
                end
            end
        end
    end
    
    print("======================================")
end

print("==========================================")
print("PARTY MENU SPECIES SCAN")
print("==========================================")
print("START  = Take snapshot")
print("SELECT = Show comparison (changed only)")
print("B      = Reset all snapshots")
print("")
print("STEPS:")
print("  1. Open START menu")
print("  2. Cursor on POKEMON, press SELECT")
print("  3. Cursor on BAG, press SELECT")
print("  4. Cursor on <NAME>, press SELECT")
print("  5. Cursor on SAVE, press SELECT")
print("  6. Cursor on OPTION, press SELECT")
print("  7. Cursor on EXIT, press SELECT")
print("  8. Press A to see comparison")
print("")
print(string.format("Scanning %d candidate addresses", #candidates))
print("==========================================")

while true do
    local input = joypad.get()
    
    if input.Start then
        snap_count = snap_count + 1
        local snap = take_snapshot()
        table.insert(snapshots, snap)
        print_snapshot(snap, "SNAPSHOT " .. snap_count)
        while joypad.get().Start do emu.frameadvance() end
    end
    
    if input.Select then
        print_full_comparison()
        while joypad.get().Select do emu.frameadvance() end
    end
    
    if input.B then
        snapshots = {}
        snap_count = 0
        print("")
        print(">>> ALL SNAPSHOTS CLEARED")
        print(">>> Press START to take new snapshots")
        print("")
        while joypad.get().B do emu.frameadvance() end
    end
    
    emu.frameadvance()
end