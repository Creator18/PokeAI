-------------------------------------------------
-- test.lua — Path Write Test
-- Lives in cogai/testing/
-- Tests whether BizHawk's Lua can read/write
-- to all 3 new path locations under jsons/
-------------------------------------------------

BASE_PATH = "C:/Users/HP/Documents/cogai/"
JSONS_ROOT = BASE_PATH .. "jsons/"

-- All 3 target directories
local test_paths = {
    { label = "IO (game_state)",     path = JSONS_ROOT .. "io/game_state.json" },
    { label = "IO (input_cache)",    path = JSONS_ROOT .. "io/input_cache.txt" },
    { label = "IO (action)",         path = JSONS_ROOT .. "io/action.json" },
    { label = "Taught (checkpoint)", path = JSONS_ROOT .. "taught_models/run_0/taught_model_checkpoint.json" },
    { label = "Taught (transitions)",path = JSONS_ROOT .. "taught_models/run_0/taught_transitions.json" },
    { label = "AI checkpoint",       path = JSONS_ROOT .. "ai_checkpoint/residual_perceptrons.json" },
    { label = "Taught logs",         path = JSONS_ROOT .. "logs/taught_logs/run_0/checkpoint_metrics.json" },
}

-- Also test the OLD flat paths for comparison
local old_paths = {
    { label = "OLD game_state",      path = BASE_PATH .. "game_state.json" },
    { label = "OLD input_cache",     path = BASE_PATH .. "input_cache.txt" },
    { label = "OLD transitions",     path = BASE_PATH .. "taught_transitions.json" },
}

print("==========================================")
print("  PATH WRITE TEST — v17.8 Reorganization")
print("==========================================")
print("BASE_PATH:  " .. BASE_PATH)
print("JSONS_ROOT: " .. JSONS_ROOT)
print("")

-- Test 1: Can we READ existing files?
print("--- READ TESTS ---")
for _, t in ipairs(test_paths) do
    local f = io.open(t.path, "r")
    if f then
        local content = f:read(50) or "(empty)"
        f:close()
        print(string.format("  READ  OK   %-25s  first50: %s", t.label, content))
    else
        print(string.format("  READ  FAIL %-25s  %s", t.label, t.path))
    end
end
print("")

-- Test 2: Can we WRITE to new paths?
print("--- WRITE TESTS (new paths) ---")
for _, t in ipairs(test_paths) do
    local test_file = t.path .. ".test_write"
    local f = io.open(test_file, "w")
    if f then
        f:write('{"test":true}')
        f:close()
        -- Verify by reading back
        local f2 = io.open(test_file, "r")
        if f2 then
            local content = f2:read("*a")
            f2:close()
            os.remove(test_file)
            print(string.format("  WRITE OK   %-25s  verified: %s", t.label, content))
        else
            print(string.format("  WRITE OK   %-25s  but READ-BACK FAILED", t.label))
        end
    else
        print(string.format("  WRITE FAIL %-25s  %s", t.label, test_file))
    end
end
print("")

-- Test 3: Can we write to OLD flat paths? (comparison)
print("--- WRITE TESTS (old flat paths) ---")
for _, t in ipairs(old_paths) do
    local test_file = t.path .. ".test_write"
    local f = io.open(test_file, "w")
    if f then
        f:write('{"test":true}')
        f:close()
        os.remove(test_file)
        print(string.format("  WRITE OK   %-25s", t.label))
    else
        print(string.format("  WRITE FAIL %-25s  %s", t.label, test_file))
    end
end
print("")

-- Test 4: Try writing directly to game_state.json (the actual file)
print("--- DIRECT OVERWRITE TEST ---")
local state_path = JSONS_ROOT .. "io/game_state.json"
local f = io.open(state_path, "w")
if f then
    f:write('{"s":[99,99,0,0,0,0],"gs":0,"tf":0,"bd":0,"dead":false,"test_marker":true}')
    f:close()
    print("  OVERWRITE OK — check game_state.json for test_marker:true")
else
    print("  OVERWRITE FAIL — io.open returned nil for: " .. state_path)
end

-- Test 5: Try with backslashes
print("")
print("--- BACKSLASH PATH TEST ---")
local bs_path = BASE_PATH:gsub("/", "\\") .. "jsons\\io\\game_state.json.bs_test"
local f_bs = io.open(bs_path, "w")
if f_bs then
    f_bs:write("backslash test")
    f_bs:close()
    os.remove(bs_path)
    print("  BACKSLASH OK — BizHawk handles both separators")
else
    print("  BACKSLASH FAIL — " .. bs_path)
end

local fs_path = JSONS_ROOT .. "io/game_state.json.fs_test"
local f_fs = io.open(fs_path, "w")
if f_fs then
    f_fs:write("forward slash test")
    f_fs:close()
    os.remove(fs_path)
    print("  FWDSLASH  OK — BizHawk handles forward slashes")
else
    print("  FWDSLASH  FAIL — " .. fs_path)
end

print("")
print("==========================================")
print("  TEST COMPLETE")
print("==========================================")