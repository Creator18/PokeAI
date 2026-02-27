-------------------------------------------------
-- TYPE DATA EXTRACTOR
-- Reads species, move, and type chart data
-- from Pokemon FireRed ROM and writes type_data.json
--
-- Standalone script — run once, get the file.
-- Does NOT interfere with game state.
--
-- ROM: Pokemon FireRed US v1.0
-------------------------------------------------

BASE_PATH = "C:/Users/HP/Documents/cogai/"
OUTPUT_FILE = BASE_PATH .. "type_data.json"

-- ROM TABLE ADDRESSES (FireRed US v1.0)
ROM_BASE_STATS    = 0x08254784
ROM_MOVE_DATA     = 0x08250C04
ROM_TYPE_CHART    = 0x0824F050
ROM_SPECIES_NAMES = 0x08245EE0
ROM_MOVE_NAMES    = 0x08247094

-- TABLE SIZES
SPECIES_COUNT      = 412
SPECIES_ENTRY_SIZE = 28
MOVE_COUNT         = 355
MOVE_ENTRY_SIZE    = 12
SPECIES_NAME_LEN   = 11
MOVE_NAME_LEN      = 13

-------------------------------------------------
-- HELPERS
-------------------------------------------------
function r8(addr)
    local ok, val = pcall(memory.read_u8, addr)
    return (ok and val) or 0
end

function r16(addr)
    local ok, val = pcall(memory.read_u16_le, addr)
    return (ok and val) or 0
end

-- Signed byte read for move priority (-8 to +7 range)
function rs8(addr)
    local v = r8(addr)
    if v >= 128 then v = v - 256 end
    return v
end

-------------------------------------------------
-- GBA CHARACTER DECODING
-------------------------------------------------
function decode_gba_char(byte)
    if byte == 0xFF then return nil end          -- terminator
    if byte == 0x00 then return " " end          -- space
    if byte >= 0xBB and byte <= 0xD4 then        -- A-Z
        return string.char(65 + (byte - 0xBB))
    end
    if byte >= 0xD5 and byte <= 0xEE then        -- a-z
        return string.char(97 + (byte - 0xD5))
    end
    if byte >= 0xA1 and byte <= 0xAA then        -- 0-9
        return string.char(48 + (byte - 0xA1))
    end
    if byte == 0xAB then return "!" end
    if byte == 0xAC then return "?" end
    if byte == 0xAD then return "." end
    if byte == 0xAE then return "-" end
    if byte == 0xB0 then return "'" end
    if byte == 0xB1 then return "&" end
    if byte == 0xB8 then return "," end
    return "?"
end

function decode_gba_string(addr, max_len)
    local chars = {}
    for i = 0, max_len - 1 do
        local byte = r8(addr + i)
        local ch = decode_gba_char(byte)
        if ch == nil then break end
        chars[#chars + 1] = ch
    end
    return table.concat(chars)
end

-------------------------------------------------
-- TYPE NAMES
-------------------------------------------------
local TYPE_NAMES = {
    [0]  = "Normal",   [1]  = "Fighting", [2]  = "Flying",
    [3]  = "Poison",   [4]  = "Ground",   [5]  = "Rock",
    [6]  = "Bug",      [7]  = "Ghost",    [8]  = "Steel",
    [9]  = "???",      [10] = "Fire",     [11] = "Water",
    [12] = "Grass",    [13] = "Electric", [14] = "Psychic",
    [15] = "Ice",      [16] = "Dragon",   [17] = "Dark",
}

function type_name(id)
    return TYPE_NAMES[id] or "Unknown"
end

-------------------------------------------------
-- STEP 0: ROM VERIFICATION
-------------------------------------------------
print("")
print("=============================================")
print("  TYPE DATA EXTRACTOR - FireRed US v1.0")
print("=============================================")
print("")
print("  Verifying ROM addresses...")

-- Check species 1 (Bulbasaur): base HP should be 45, Grass/Poison
local bulba_hp = r8(ROM_BASE_STATS + SPECIES_ENTRY_SIZE * 1 + 0x00)
local bulba_t1 = r8(ROM_BASE_STATS + SPECIES_ENTRY_SIZE * 1 + 0x06)
local bulba_t2 = r8(ROM_BASE_STATS + SPECIES_ENTRY_SIZE * 1 + 0x07)

-- Check move 1 (Pound): power should be 40, type Normal(0)
local pound_power = r8(ROM_MOVE_DATA + MOVE_ENTRY_SIZE * 1 + 0x01)
local pound_type  = r8(ROM_MOVE_DATA + MOVE_ENTRY_SIZE * 1 + 0x02)

-- Check type chart first entry exists and is valid
local tc_first_atk = r8(ROM_TYPE_CHART)
local tc_first_def = r8(ROM_TYPE_CHART + 1)
local tc_first_eff = r8(ROM_TYPE_CHART + 2)

print(string.format("  Bulbasaur (species 1): HP=%d type1=%d(%s) type2=%d(%s)",
    bulba_hp, bulba_t1, type_name(bulba_t1), bulba_t2, type_name(bulba_t2)))
print(string.format("  Pound (move 1): power=%d type=%d(%s)",
    pound_power, pound_type, type_name(pound_type)))
print(string.format("  Type chart first entry: atk=%d def=%d eff=0x%02X",
    tc_first_atk, tc_first_def, tc_first_eff))

local rom_ok = true
if bulba_hp ~= 45 then
    print("  FAIL: Bulbasaur base HP should be 45, got " .. bulba_hp)
    rom_ok = false
end
if bulba_t1 ~= 12 or bulba_t2 ~= 3 then
    print("  FAIL: Bulbasaur should be Grass/Poison (12/3)")
    rom_ok = false
end
if pound_power ~= 40 or pound_type ~= 0 then
    print("  FAIL: Pound should be Normal type, 40 power")
    rom_ok = false
end
if tc_first_atk > 17 or tc_first_def > 17 then
    print("  FAIL: Type chart first entry has invalid type IDs")
    rom_ok = false
end
if tc_first_eff ~= 0x00 and tc_first_eff ~= 0x05 and tc_first_eff ~= 0x14 then
    print("  FAIL: Type chart first entry has invalid effectiveness byte")
    rom_ok = false
end

if not rom_ok then
    print("")
    print("  ROM VERIFICATION FAILED - wrong ROM version?")
    print("  Aborting.")
    print("=============================================")
    return
end

print("  ROM verification passed")
print("")

-------------------------------------------------
-- STEP 1: READ SPECIES DATA
-------------------------------------------------
print("  Reading species data...")

local species_data = {}
local species_read = 0

for id = 1, SPECIES_COUNT do
    local base = ROM_BASE_STATS + SPECIES_ENTRY_SIZE * id

    local hp    = r8(base + 0x00)
    local atk   = r8(base + 0x01)
    local def   = r8(base + 0x02)
    local spd   = r8(base + 0x03)
    local spatk = r8(base + 0x04)
    local spdef = r8(base + 0x05)
    local t1    = r8(base + 0x06)
    local t2    = r8(base + 0x07)
    local ab1   = r8(base + 0x16)
    local ab2   = r8(base + 0x17)

    -- Skip empty entries (all base stats zero)
    if hp == 0 and atk == 0 and def == 0 and spd == 0 and spatk == 0 and spdef == 0 then
        goto next_species
    end

    -- Read name
    local name_addr = ROM_SPECIES_NAMES + SPECIES_NAME_LEN * id
    local name = decode_gba_string(name_addr, SPECIES_NAME_LEN)

    species_data[id] = {
        name = name,
        type1 = t1, type2 = t2,
        hp = hp, atk = atk, def = def,
        spd = spd, spatk = spatk, spdef = spdef,
        ability1 = ab1, ability2 = ab2
    }
    species_read = species_read + 1

    ::next_species::
end

print(string.format("  Read %d species", species_read))

-- Verify key species
local verify_species = {
    {id=1,   name="Bulbasaur",  t1=12, t2=3},
    {id=4,   name="Charmander", t1=10, t2=10},
    {id=7,   name="Squirtle",   t1=11, t2=11},
    {id=16,  name="Pidgey",     t1=0,  t2=2},
    {id=25,  name="Pikachu",    t1=13, t2=13},
    {id=150, name="Mewtwo",     t1=14, t2=14},
}

for _, v in ipairs(verify_species) do
    local s = species_data[v.id]
    if s then
        local pass = (s.type1 == v.t1 and s.type2 == v.t2)
        print(string.format("    #%-3d %-12s %s/%s %s",
            v.id, s.name, type_name(s.type1), type_name(s.type2),
            pass and "OK" or "MISMATCH"))
    else
        print(string.format("    #%-3d %-12s NOT FOUND", v.id, v.name))
    end
end

-------------------------------------------------
-- STEP 2: READ MOVE DATA
-------------------------------------------------
print("")
print("  Reading move data...")

local move_data = {}
local moves_read = 0

for id = 1, MOVE_COUNT do
    local base = ROM_MOVE_DATA + MOVE_ENTRY_SIZE * id

    local effect   = r8(base + 0x00)
    local power    = r8(base + 0x01)
    local mtype    = r8(base + 0x02)
    local accuracy = r8(base + 0x03)
    local pp       = r8(base + 0x04)
    local eff_ch   = r8(base + 0x05)
    local target   = r8(base + 0x06)
    local priority = rs8(base + 0x07)   -- signed: Quick Attack = +1, Counter = -5, etc.
    local flags    = r8(base + 0x08)

    -- Read name
    local name_addr = ROM_MOVE_NAMES + MOVE_NAME_LEN * id
    local name = decode_gba_string(name_addr, MOVE_NAME_LEN)

    -- Skip if name is empty (unused move slot)
    if name == "" or name == "?" then
        goto next_move
    end

    move_data[id] = {
        name = name,
        mtype = mtype,
        power = power,
        accuracy = accuracy,
        pp = pp,
        effect = effect,
        effect_chance = eff_ch,
        target = target,
        priority = priority,
        flags = flags
    }
    moves_read = moves_read + 1

    ::next_move::
end

print(string.format("  Read %d moves", moves_read))

-- Verify key moves
local verify_moves = {
    {id=1,  name="Pound",     mtype=0,  power=40},
    {id=10, name="Scratch",   mtype=0,  power=40},
    {id=52, name="Ember",     mtype=10, power=40},
    {id=55, name="Water Gun", mtype=11, power=40},
    {id=73, name="Leech Seed",mtype=12, power=0},
    {id=85, name="Thunderbolt",mtype=13, power=95},
}

for _, v in ipairs(verify_moves) do
    local m = move_data[v.id]
    if m then
        local pass = (m.mtype == v.mtype and m.power == v.power)
        print(string.format("    #%-3d %-14s %-8s pow:%-3d %s",
            v.id, m.name, type_name(m.mtype), m.power,
            pass and "OK" or "MISMATCH"))
    else
        print(string.format("    #%-3d %-14s NOT FOUND", v.id, v.name))
    end
end

-------------------------------------------------
-- STEP 3: READ TYPE EFFECTIVENESS TABLE
-------------------------------------------------
print("")
print("  Reading type chart...")

local type_chart = {}
local chart_entries = 0
local addr = ROM_TYPE_CHART

while true do
    local atk_type = r8(addr)
    local def_type = r8(addr + 1)
    local eff_val  = r8(addr + 2)

    -- Terminator: 0xFF 0xFF 0x00
    if atk_type == 0xFF and def_type == 0xFF then
        break
    end

    -- Separator: 0xFE 0xFE 0x00 (Foresight/Odor Sleuth section after this)
    -- Skip the separator itself but keep reading — the entries after it
    -- are immunities (Normal→Ghost, Fighting→Ghost) that are real in normal
    -- gameplay. Foresight/Odor Sleuth REMOVE them, so the game stores them
    -- in this section. We still want them in our type chart.
    if atk_type == 0xFE and def_type == 0xFE then
        addr = addr + 3
        goto next_entry
    end

    -- Sanity check: type IDs should be 0-17
    if atk_type > 17 or def_type > 17 then
        print(string.format("  WARNING: Unexpected type ID at 0x%08X: atk=%d def=%d eff=0x%02X",
            addr, atk_type, def_type, eff_val))
    elseif eff_val ~= 0x00 and eff_val ~= 0x05 and eff_val ~= 0x14 then
        print(string.format("  WARNING: Unknown eff byte 0x%02X at 0x%08X", eff_val, addr))
    else
        -- Decode effectiveness
        local multiplier
        if eff_val == 0x00 then
            multiplier = 0.0
        elseif eff_val == 0x05 then
            multiplier = 0.5
        elseif eff_val == 0x14 then
            multiplier = 2.0
        end

        local key = atk_type .. "_" .. def_type
        type_chart[key] = multiplier
        chart_entries = chart_entries + 1
    end

    ::next_entry::
    addr = addr + 3
end

print(string.format("  Read %d type chart entries", chart_entries))

-- Verify key matchups
local verify_chart = {
    {atk=10, def=12, exp=2.0, desc="Fire vs Grass"},
    {atk=10, def=11, exp=0.5, desc="Fire vs Water"},
    {atk=10, def=10, exp=0.5, desc="Fire vs Fire"},
    {atk=11, def=10, exp=2.0, desc="Water vs Fire"},
    {atk=12, def=11, exp=2.0, desc="Grass vs Water"},
    {atk=0,  def=7,  exp=0.0, desc="Normal vs Ghost (immune)"},
    {atk=7,  def=0,  exp=0.0, desc="Ghost vs Normal (immune)"},
    {atk=1,  def=7,  exp=0.0, desc="Fighting vs Ghost (immune)"},
    {atk=13, def=11, exp=2.0, desc="Electric vs Water"},
    {atk=13, def=4,  exp=0.0, desc="Electric vs Ground (immune)"},
    {atk=14, def=17, exp=0.0, desc="Psychic vs Dark (immune)"},
    {atk=1,  def=0,  exp=2.0, desc="Fighting vs Normal"},
    {atk=4,  def=13, exp=2.0, desc="Ground vs Electric (SE)"},
}

for _, v in ipairs(verify_chart) do
    local key = v.atk .. "_" .. v.def
    local got = type_chart[key]
    if got then
        local pass = (got == v.exp)
        print(string.format("    %-8s vs %-8s: %.1fx %s",
            type_name(v.atk), type_name(v.def), got,
            pass and "OK" or ("EXPECTED " .. v.exp)))
    else
        print(string.format("    %-8s vs %-8s: NOT FOUND", type_name(v.atk), type_name(v.def)))
    end
end

-------------------------------------------------
-- STEP 4: WRITE JSON
-------------------------------------------------
print("")
print("  Writing " .. OUTPUT_FILE .. "...")

local f = io.open(OUTPUT_FILE, "w")
if not f then
    print("  ERROR: Cannot open output file!")
    print("  Check that the directory exists: " .. BASE_PATH)
    return
end

-- === Species ===
f:write('{\n"species": {\n')
local first_species = true
for id = 1, SPECIES_COUNT do
    local s = species_data[id]
    if s then
        if not first_species then f:write(',\n') end
        first_species = false

        local safe_name = s.name:gsub('"', '\\"')

        f:write(string.format(
            '  "%d": {"name": "%s", "type1": %d, "type2": %d, "type1_name": "%s", "type2_name": "%s", ' ..
            '"base_stats": {"hp": %d, "atk": %d, "def": %d, "spd": %d, "spatk": %d, "spdef": %d}, ' ..
            '"abilities": [%d, %d]}',
            id, safe_name, s.type1, s.type2, type_name(s.type1), type_name(s.type2),
            s.hp, s.atk, s.def, s.spd, s.spatk, s.spdef,
            s.ability1, s.ability2
        ))
    end
end
f:write('\n},\n')

-- === Moves ===
f:write('"moves": {\n')
local first_move = true
for id = 1, MOVE_COUNT do
    local m = move_data[id]
    if m then
        if not first_move then f:write(',\n') end
        first_move = false

        local safe_name = m.name:gsub('"', '\\"')

        f:write(string.format(
            '  "%d": {"name": "%s", "type": %d, "type_name": "%s", "power": %d, "accuracy": %d, ' ..
            '"pp": %d, "effect": %d, "effect_chance": %d, "priority": %d, "flags": %d}',
            id, safe_name, m.mtype, type_name(m.mtype), m.power, m.accuracy,
            m.pp, m.effect, m.effect_chance, m.priority, m.flags
        ))
    end
end
f:write('\n},\n')

-- === Type Chart ===
f:write('"type_chart": {\n')
local first_chart = true
-- Sort keys numerically (by atk type, then def type)
local chart_keys = {}
for k in pairs(type_chart) do chart_keys[#chart_keys + 1] = k end
table.sort(chart_keys, function(a, b)
    local a1, a2 = a:match("(%d+)_(%d+)")
    local b1, b2 = b:match("(%d+)_(%d+)")
    a1, a2, b1, b2 = tonumber(a1), tonumber(a2), tonumber(b1), tonumber(b2)
    if a1 ~= b1 then return a1 < b1 end
    return a2 < b2
end)

for _, key in ipairs(chart_keys) do
    if not first_chart then f:write(',\n') end
    first_chart = false
    local val = type_chart[key]
    local val_str
    if val == 0.0 then val_str = "0.0"
    elseif val == 0.5 then val_str = "0.5"
    elseif val == 2.0 then val_str = "2.0"
    else val_str = string.format("%.1f", val) end
    f:write(string.format('  "%s": %s', key, val_str))
end
f:write('\n},\n')

-- === Type Names ===
f:write('"type_names": {\n')
local first_type = true
for id = 0, 17 do
    if id ~= 9 then  -- skip ??? type
        if not first_type then f:write(',\n') end
        first_type = false
        f:write(string.format('  "%d": "%s"', id, type_name(id)))
    end
end
f:write('\n},\n')

-- === Metadata ===
f:write('"metadata": {\n')
f:write('  "game": "Pokemon FireRed US v1.0",\n')
f:write(string.format('  "species_count": %d,\n', species_read))
f:write(string.format('  "move_count": %d,\n', moves_read))
f:write(string.format('  "type_chart_entries": %d,\n', chart_entries))
f:write('  "rom_addresses": {\n')
f:write(string.format('    "base_stats": "0x%08X",\n', ROM_BASE_STATS))
f:write(string.format('    "move_data": "0x%08X",\n', ROM_MOVE_DATA))
f:write(string.format('    "type_chart": "0x%08X",\n', ROM_TYPE_CHART))
f:write(string.format('    "species_names": "0x%08X",\n', ROM_SPECIES_NAMES))
f:write(string.format('    "move_names": "0x%08X"\n', ROM_MOVE_NAMES))
f:write('  }\n')
f:write('}\n')
f:write('}\n')

f:close()

-------------------------------------------------
-- STEP 5: SUMMARY
-------------------------------------------------
print("")
print("  DONE — " .. OUTPUT_FILE)
print("")
print(string.format("  Species:    %d", species_read))
print(string.format("  Moves:      %d", moves_read))
print(string.format("  Type chart: %d entries", chart_entries))
print("")

-- Quick team reference
print("  === CURRENT TEAM TYPES ===")
local team_ids = {4, 16}  -- Charmander, Pidgey
for _, sid in ipairs(team_ids) do
    local s = species_data[sid]
    if s then
        print(string.format("  #%-3d %-12s %s/%s  HP:%d ATK:%d DEF:%d SPD:%d SPATK:%d SPDEF:%d",
            sid, s.name, type_name(s.type1), type_name(s.type2),
            s.hp, s.atk, s.def, s.spd, s.spatk, s.spdef))
    end
end

print("")
print("=============================================")