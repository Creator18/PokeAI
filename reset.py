# Reset all JSON files for AI Agent (Multi-Pool Pipeline) + Teaching Code
# Creates files if they don't exist, resets to empty if they do
#
# MULTI-MODEL FOLDER STRUCTURE:
# Taught data now lives in taught_models/model_N/ folders.
# If old flat taught files exist in cogai/, they are MOVED into
# taught_models/model_1/ automatically (migration).
#
# Update BASE_PATH to match your device

import json
import shutil
from pathlib import Path

BASE_PATH = Path(r"C:\Users\HP\Documents\cogai")
BASE_PATH.mkdir(parents=True, exist_ok=True)

TAUGHT_MODELS_DIR = BASE_PATH / "taught_models"

count = 0
total = 20  # updated count

# ============================================================================
# TAUGHT MODEL FILE NAMES (these live inside each model_N folder)
# ============================================================================

TAUGHT_FILENAMES = [
    "taught_model_checkpoint.json",
    "taught_transitions.json",
    "taught_battle_transitions.json",
    "taught_bag_transitions.json",
    "taught_start_menu_transitions.json",
    "taught_exploration_memory.json",
    "taught_nav_targets.json",
    "event_timeline.json",
]

# Empty templates for each taught file (used when creating fresh model folders)
TAUGHT_TEMPLATES = {
    "taught_model_checkpoint.json": {
        "timestep": 0,
        "perceptrons": {"actions": [], "entities": []},
        "debt_tracking": {
            "map_novelty_debt": {},
            "location_novelty": {},
            "visited_maps": {}
        },
        "control_mode": "move",
        "markov_stats": {"markov_action_count": 0, "curiosity_action_count": 0},
        "blend_stats": {"blend_count": 0, "last_blend_tier": 0},
        "battle_stats": {
            "battle_action_count": 0,
            "battle_markov_action_count": 0,
            "current_battle_id": 0
        },
        "bag_stats": {
            "bag_thread_total_actions": 0,
            "bag_thread_markov_actions": 0
        },
        "prep_stats": {
            "prep_total_count": 0,
            "prep_success_count": 0
        },
        "start_menu_stats": {
            "start_menu_total_actions": 0,
            "start_menu_markov_actions": 0
        },
        "chain_stats": {
            "entity_spawn_counts": {"overworld": 0, "battle": 0, "party": 0, "bag": 0, "shared": 0},
            "entity_merge_counts": {"overworld": 0, "battle": 0, "party": 0, "bag": 0, "shared": 0},
            "entity_capacities": {"overworld": 20, "battle": 10, "party": 5, "bag": 5, "shared": 10}
        },
        "roster": {},
        "move_knowledge": {"player_moves": {}, "enemy_moves": {}},
        "item_knowledge": {},
        "map_battle_stats": {},
        "battle_tracking": {"battle_low_hp_exits": 0},
        "type_clusters": {
            "move_type_clusters": {},
            "species_type_clusters": {},
            "cluster_effectiveness": {},
            "move_to_cluster": {},
            "species_to_cluster": {},
            "clustering_run_count": 0
        },
        "pipelines": {
            "battle": {
                "pipeline_id": "battle", "name": "Battle Pipeline", "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "battle_L0_identification", "name": "identification", "output_width": 8, "max_perceptrons": 15, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "battle_L1_threat_assessment", "name": "threat_assessment", "output_width": 8, "max_perceptrons": 20, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "battle_L2_stay_or_bail", "name": "stay_or_bail", "output_width": 8, "max_perceptrons": 15, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "battle_L3_action_selection", "name": "action_selection", "output_width": 8, "max_perceptrons": 20, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "battle_L4_execution", "name": "execution", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "battle_L5_outcome_observation", "name": "outcome_observation", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}}
                ]
            },
            "overworld": {
                "pipeline_id": "overworld", "name": "Overworld Pipeline", "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "overworld_L0_spatial_awareness", "name": "spatial_awareness", "output_width": 8, "max_perceptrons": 15, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "overworld_L1_area_classification", "name": "area_classification", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "overworld_L2_frontier_detection", "name": "frontier_detection", "output_width": 8, "max_perceptrons": 15, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "overworld_L3_objective_management", "name": "objective_management", "output_width": 8, "max_perceptrons": 15, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "overworld_L4_pathfinding", "name": "pathfinding", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "overworld_L5_execution", "name": "execution", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "overworld_L6_outcome_observation", "name": "outcome_observation", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}}
                ]
            },
            "bag": {
                "pipeline_id": "bag", "name": "Bag Pipeline", "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "bag_L0_inventory_awareness", "name": "inventory_awareness", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "bag_L1_item_selection", "name": "item_selection", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "bag_L2_execution", "name": "execution", "output_width": 8, "max_perceptrons": 8, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}}
                ]
            },
            "party": {
                "pipeline_id": "party", "name": "Party Pipeline", "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "party_L0_assessment", "name": "assessment", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "party_L1_execution", "name": "execution", "output_width": 8, "max_perceptrons": 8, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}}
                ]
            }
        },
        "revenge_targets": {}
    },
    "taught_transitions.json": {
        "batches": [],
        "metadata": {"total_frames": 0, "action_changes": 0, "maps_visited": []}
    },
    "taught_battle_transitions.json": {
        "battle_sequences": [],
        "flat_frames": [],
        "metadata": {
            "total_battle_frames": 0, "battles_recorded": 0, "avg_battle_length": 0,
            "outcomes": {}, "maps_with_battles": [], "most_common_sequences": [],
            "frames_with_battle_data": 0, "battle_data_coverage": 0.0
        }
    },
    "taught_bag_transitions.json": {
        "bag_frames": [],
        "metadata": {"total_bag_frames": 0, "bag_sessions_recorded": 0, "items_used": [], "pockets_visited": []}
    },
    "taught_start_menu_transitions.json": {
        "start_menu_frames": [],
        "metadata": {"total_frames": 0, "sessions_recorded": 0, "targets_navigated": {}, "avg_session_length": 0}
    },
    "taught_exploration_memory.json": {},
    "taught_nav_targets.json": {
        "targets_by_map": {},
        "global_order": [],
        "metadata": {
            "total_targets": 0, "maps_with_targets": [],
            "analysis_window_after": 40, "min_forward_progress": 0.5,
            "dedup_radius": 2, "generated_from_frames": 0
        }
    },
    "event_timeline.json": {
        "events": [],
        "segments": [],
        "preparation_points": [],
        "metadata": {"nav_targets_covered": [], "total_events": 0}
    },
}

# ============================================================================
# STEP 1: Create taught_models/ directory
# ============================================================================
count += 1
TAUGHT_MODELS_DIR.mkdir(parents=True, exist_ok=True)
print(f"✅ {count}/{total} taught_models/ directory created")

# ============================================================================
# STEP 2: Migrate flat taught files → taught_models/model_1/ if they exist
# ============================================================================
count += 1

flat_taught_files = [BASE_PATH / fn for fn in TAUGHT_FILENAMES]
flat_files_exist = [f for f in flat_taught_files if f.exists()]

if flat_files_exist:
    # Find next available model number
    existing_models = sorted([
        d for d in TAUGHT_MODELS_DIR.iterdir()
        if d.is_dir() and d.name.startswith('model_')
    ], key=lambda d: int(d.name.split('_')[1]) if d.name.split('_')[1].isdigit() else 0)

    next_num = 1
    if existing_models:
        last_num = int(existing_models[-1].name.split('_')[1])
        next_num = last_num + 1

    migration_dir = TAUGHT_MODELS_DIR / f"model_{next_num}"
    migration_dir.mkdir(parents=True, exist_ok=True)

    migrated = 0
    for flat_file in flat_files_exist:
        dest = migration_dir / flat_file.name
        shutil.move(str(flat_file), str(dest))
        migrated += 1

    print(f"✅ {count}/{total} MIGRATED {migrated} flat taught files → {migration_dir.name}/")
    for f in flat_files_exist:
        print(f"     📦 {f.name}")

    # Check if any taught files are missing from the migration
    missing = [fn for fn in TAUGHT_FILENAMES if not (migration_dir / fn).exists()]
    if missing:
        print(f"     ⚠️ Missing files (creating empty): {', '.join(missing)}")
        for fn in missing:
            with open(migration_dir / fn, 'w') as f:
                json.dump(TAUGHT_TEMPLATES[fn], f, indent=2)
else:
    # No flat files to migrate — check if any model folders exist
    existing_models = sorted([
        d for d in TAUGHT_MODELS_DIR.iterdir()
        if d.is_dir() and d.name.startswith('model_')
    ]) if TAUGHT_MODELS_DIR.exists() else []

    if existing_models:
        print(f"✅ {count}/{total} No flat files to migrate — {len(existing_models)} model folder(s) already exist")
    else:
        # Create empty model_1 with template files
        model_1_dir = TAUGHT_MODELS_DIR / "model_1"
        model_1_dir.mkdir(parents=True, exist_ok=True)
        for fn in TAUGHT_FILENAMES:
            with open(model_1_dir / fn, 'w') as f:
                json.dump(TAUGHT_TEMPLATES[fn], f, indent=2)
        print(f"✅ {count}/{total} Created empty taught_models/model_1/ with {len(TAUGHT_FILENAMES)} template files")

# ============================================================================
# STEP 3: Report taught model folder contents
# ============================================================================
count += 1
existing_models = sorted([
    d for d in TAUGHT_MODELS_DIR.iterdir()
    if d.is_dir() and d.name.startswith('model_')
]) if TAUGHT_MODELS_DIR.exists() else []

print(f"✅ {count}/{total} Taught model folders: {len(existing_models)}")
for model_dir in existing_models:
    files_present = [f.name for f in model_dir.iterdir() if f.is_file()]
    files_with_data = []
    for f in model_dir.iterdir():
        if f.is_file() and f.stat().st_size > 50:  # more than just empty JSON
            files_with_data.append(f.name)
    print(f"     📂 {model_dir.name}: {len(files_present)}/{len(TAUGHT_FILENAMES)} files"
          f" ({len(files_with_data)} with data)")

# ============================================================================
# AI AGENT FILES (produced by AI agent — still in flat cogai/)
# ============================================================================

# 4. model_checkpoint.json
count += 1
fp = BASE_PATH / "model_checkpoint.json"
if fp.exists():
    fp.unlink()
    print(f"✅ {count}/{total} model_checkpoint.json (DELETED — AI will bootstrap from taught)")
else:
    print(f"✅ {count}/{total} model_checkpoint.json (not present — AI will bootstrap)")

# 5. exploration_memory.json
count += 1
with open(BASE_PATH / "exploration_memory.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} exploration_memory.json")

# 6. roster.json
count += 1
with open(BASE_PATH / "roster.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} roster.json")

# 7. move_knowledge.json
count += 1
with open(BASE_PATH / "move_knowledge.json", 'w') as f:
    json.dump({"player_moves": {}, "enemy_moves": {}}, f, indent=2)
print(f"✅ {count}/{total} move_knowledge.json")

# 8. item_knowledge.json
count += 1
with open(BASE_PATH / "item_knowledge.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} item_knowledge.json")

# 9. type_clusters.json
count += 1
with open(BASE_PATH / "type_clusters.json", 'w') as f:
    json.dump({
        "move_type_clusters": {},
        "species_type_clusters": {},
        "cluster_effectiveness": {},
        "move_to_cluster": {},
        "species_to_cluster": {},
        "clustering_run_count": 0,
        "last_clustering_timestep": 0
    }, f, indent=2)
print(f"✅ {count}/{total} type_clusters.json")

# 10. ai_event_timeline.json
count += 1
with open(BASE_PATH / "ai_event_timeline.json", 'w') as f:
    json.dump({
        "events": [],
        "summary": {
            "total_events": 0, "battle_events": 0, "bag_events": 0,
            "map_events": 0, "levelup_events": 0,
            "first_timestep": 0, "last_timestep": 0, "maps_visited": []
        }
    }, f, indent=2)
print(f"✅ {count}/{total} ai_event_timeline.json")

# 11. residual_perceptrons.json
count += 1
with open(BASE_PATH / "residual_perceptrons.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} residual_perceptrons.json")

# ============================================================================
# I/O FILES (Lua ↔ AI communication)
# ============================================================================

# 12. action.json
count += 1
with open(BASE_PATH / "action.json", 'w') as f:
    json.dump({"action": "NONE"}, f)
print(f"✅ {count}/{total} action.json")

# 13. game_state.json
count += 1
with open(BASE_PATH / "game_state.json", 'w') as f:
    json.dump({
        "s": [0, 0, 0, 0, 0, 0],
        "gs": 0,
        "tf": 0,
        "dead": False,
        "b": {"bc": -1, "mc": -1, "ps": -1, "es": -1, "ph": -1, "pm": -1, "eh": -1, "em": -1,
              "pl": -1, "el": -1, "pst": 0, "est": 0, "bt": 0,
              "m0": -1, "m1": -1, "m2": -1, "m3": -1,
              "pp0": -1, "pp1": -1, "pp2": -1, "pp3": -1,
              "pss": [-1, -1, -1, -1, -1, -1, -1],
              "em0": -1, "em1": -1, "em2": -1, "em3": -1,
              "epp0": -1, "epp1": -1, "epp2": -1, "epp3": -1,
              "ess": [-1, -1, -1, -1, -1, -1, -1],
              "pc": -1},
        "pa": {"c": 0, "s": []},
        "mu": {"mc": -1, "mm": -1, "pc": -1, "sc": -1},
        "bg": {"pk": -1, "bc": -1, "a": 0, "it": []}
    }, f, indent=2)
print(f"✅ {count}/{total} game_state.json")

# ============================================================================
# OPTIONAL FILES (not reset, just noted)
# ============================================================================

# 14. type_data.json — optional Track B ground truth
count += 1
opt_type_data = BASE_PATH / "type_data.json"
if opt_type_data.exists():
    print(f"✅ {count}/{total} type_data.json EXISTS ({opt_type_data.stat().st_size} bytes) — not reset (optional Track B)")
else:
    print(f"⬚  {count}/{total} type_data.json not found (Track B — optional, from Lua verification script)")

# ============================================================================
# CLEANUP: Warn about any leftover flat taught files (shouldn't exist after migration)
# ============================================================================
count += 1
leftover_flat = [BASE_PATH / fn for fn in TAUGHT_FILENAMES if (BASE_PATH / fn).exists()]
if leftover_flat:
    print(f"\n⚠️  {count}/{total} WARNING: {len(leftover_flat)} flat taught files still in cogai/:")
    for f in leftover_flat:
        print(f"     ⚠️ {f.name} ({f.stat().st_size} bytes)")
    print(f"     These should have been migrated. Delete manually or re-run reset.")
else:
    print(f"✅ {count}/{total} No leftover flat taught files (clean)")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'='*60}")
print(f"📁 All {total} items handled.")
print(f"   Path: {BASE_PATH}")
print(f"\n   Folder structure:")
print(f"     cogai/")
print(f"     ├── taught_models/")
for model_dir in existing_models:
    files_count = len(list(model_dir.iterdir()))
    print(f"     │   ├── {model_dir.name}/  ({files_count} files)")
print(f"     │   └── (add model_N/ folders for additional playthroughs)")
print(f"     ├── model_checkpoint.json      (AI's own checkpoint)")
print(f"     ├── exploration_memory.json     (AI's exploration data)")
print(f"     ├── residual_perceptrons.json   (pipeline paged perceptrons)")
print(f"     ├── roster.json                 (party roster)")
print(f"     ├── move_knowledge.json         (move effectiveness)")
print(f"     ├── item_knowledge.json         (item categorization)")
print(f"     ├── type_clusters.json          (empirical type chart)")
print(f"     ├── ai_event_timeline.json      (AI event log)")
print(f"     ├── type_data.json              (optional Track B)")
print(f"     ├── action.json                 (Lua ↔ AI)")
print(f"     └── game_state.json             (Lua ↔ AI)")
print(f"\n   File breakdown:")
print(f"     Taught models directory:    1 folder with {len(existing_models)} model(s)")
print(f"     AI agent state:             8 files (reset/deleted)")
print(f"     Lua ↔ AI communication:     2 files (reset)")
print(f"     Optional (Track B):         1 file  (not touched)")
print(f"\n   To add a new human playthrough:")
print(f"   1. Create taught_models/model_N/ (next number)")
print(f"   2. Put the 8 taught JSON files from GitHub into it")
print(f"   3. AI's load_all_taught_models() will discover and merge automatically")
print(f"\n   To start fresh AI run:")
print(f"   1. Run this reset script")
print(f"   2. Run AI agent — it bootstraps from best taught checkpoint")
print(f"   3. Pipelines start empty, populate through play")
print(f"   4. Revenge targets start empty, populate on losses")