# ============================================================================
# Reset all JSON files for AI Agent v17.8.1
# ============================================================================
# Creates the jsons/ directory structure under cogai/ and resets all files.
#
# CHANGES from v17.8 → v17.8.1:
# 1. UPDATED: ai_logs/ templates — checkpoint_metrics.json now has
#    source="ai_agent_live", checkpoint_types, maps_visited, badges_logged,
#    trainer_battles_logged fields matching the AI Brain's save_eval_logs()
# 2. UPDATED: ai_logs/ templates — stagnation_metrics.json now has
#    source="ai_agent_live", stagnation_types, total_stagnation_frames,
#    stagnation_ratio, active_at_save fields matching open/close snapshot system
# 3. REMOVED: taught_logs/ file creation — that folder is populated by the
#    teaching pipeline separately. Reset script preserves existing content.
# 4. UPDATED: taught model checkpoint template — includes eval_state and
#    stagnation_state blocks for session persistence compatibility
# 5. UPDATED: Version references in banner/comments
#
# FOLDER STRUCTURE:
#   cogai/jsons/
#   ├── io/                    Lua ↔ AI real-time communication
#   │   ├── action.json
#   │   └── game_state.json
#   ├── taught_models/         Human demonstration data (read-only by AI)
#   │   ├── model_1/
#   │   │   ├── taught_model_checkpoint.json
#   │   │   ├── taught_transitions.json
#   │   │   ├── taught_battle_transitions.json
#   │   │   ├── taught_bag_transitions.json
#   │   │   ├── taught_start_menu_transitions.json
#   │   │   ├── taught_exploration_memory.json
#   │   │   ├── taught_nav_targets.json
#   │   │   └── event_timeline.json
#   │   └── model_N/  ...
#   ├── ai_checkpoint/         AI's own learned weights + pipeline state
#   │   ├── model_checkpoint.json
#   │   └── residual_perceptrons.json
#   ├── empirical_knowledge/   Knowledge built through play
#   │   ├── exploration_memory.json
#   │   ├── roster.json
#   │   ├── move_knowledge.json
#   │   ├── item_knowledge.json
#   │   ├── type_clusters.json
#   │   ├── type_data.json         (Track B — optional, not reset if present)
#   │   └── ai_event_timeline.json
#   ├── debug/                 Adaptive window debug dumps (ephemeral)
#   │   ├── active_transitions.json
#   │   ├── active_battle.json
#   │   ├── active_bag.json
#   │   └── active_start_menu.json
#   └── logs/                  Evaluation metrics
#       ├── ai_logs/
#       │   ├── checkpoint_metrics.json   (event-driven: new_map, trainer_battle, badge)
#       │   └── stagnation_metrics.json   (open/close intervals, 7 types)
#       └── taught_logs/                  (NOT TOUCHED by reset — human data goes here)
#           ├── checkpoint_metrics.json   (from teaching pipeline)
#           └── stagnation_metrics.json   (from teaching pipeline)
#
# MIGRATION:
#   If old flat files exist in cogai/ (pre-v17.8 layout), they are
#   automatically moved into the correct subfolder.
#   If old taught_models/ exists at cogai/taught_models/, it is moved
#   into cogai/jsons/taught_models/.
#
# Run from: cogai/testing/
# ============================================================================

import json
import shutil
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parents[2]  # agent/testing/ → cogai/
BASE_PATH.mkdir(parents=True, exist_ok=True)

# ============================================================================
# NEW DIRECTORY STRUCTURE
# ============================================================================

JSONS_ROOT = BASE_PATH / "jsons"
IO_DIR = JSONS_ROOT / "io"
TAUGHT_MODELS_DIR = JSONS_ROOT / "taught_models"
AI_CHECKPOINT_DIR = JSONS_ROOT / "ai_checkpoint"
EMPIRICAL_DIR = JSONS_ROOT / "empirical_knowledge"
DEBUG_DIR = JSONS_ROOT / "debug"
LOGS_DIR = JSONS_ROOT / "logs"
AI_LOGS_DIR = LOGS_DIR / "ai_logs"
TAUGHT_LOGS_DIR = LOGS_DIR / "taught_logs"

ALL_DIRS = [JSONS_ROOT, IO_DIR, TAUGHT_MODELS_DIR, AI_CHECKPOINT_DIR,
            EMPIRICAL_DIR, DEBUG_DIR, LOGS_DIR, AI_LOGS_DIR, TAUGHT_LOGS_DIR]

# ============================================================================
# TAUGHT MODEL FILE NAMES (inside each model_N folder)
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

# ============================================================================
# EMPTY TEMPLATES
# ============================================================================

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
        "revenge_targets": {},
        # v17.8.1: Evaluation state (empty — populated during play)
        "eval_state": {
            "checkpoint_log": [],
            "checkpoint_id_counter": 0,
            "last_checkpoint_ts": 0,
            "maps_first_visited": [],
            "prev_badge_count": 0,
            "trainer_battle_count": 0
        },
        "stagnation_state": {
            "snapshot_log": [],
            "snapshot_id_counter": 0,
            "cooldown_until": {
                "position_stuck": 0,
                "action_pattern": 0,
                "action_repeat": 0,
                "area_grinding": 0,
                "no_level_progress": 0,
                "no_map_progress": 0,
                "backtracking": 0
            },
            "last_level_gain_ts": 0,
            "last_new_map_ts": 0,
            "last_team_avg_level": 0.0
        }
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
# MAPPING: old flat file name → new location
# (used for migration from pre-v17.8 flat layout)
# ============================================================================

FLAT_MIGRATION_MAP = {
    # io/
    "action.json": IO_DIR / "action.json",
    "game_state.json": IO_DIR / "game_state.json",

    # ai_checkpoint/
    "model_checkpoint.json": AI_CHECKPOINT_DIR / "model_checkpoint.json",
    "residual_perceptrons.json": AI_CHECKPOINT_DIR / "residual_perceptrons.json",

    # empirical_knowledge/
    "exploration_memory.json": EMPIRICAL_DIR / "exploration_memory.json",
    "roster.json": EMPIRICAL_DIR / "roster.json",
    "move_knowledge.json": EMPIRICAL_DIR / "move_knowledge.json",
    "item_knowledge.json": EMPIRICAL_DIR / "item_knowledge.json",
    "type_clusters.json": EMPIRICAL_DIR / "type_clusters.json",
    "type_data.json": EMPIRICAL_DIR / "type_data.json",
    "ai_event_timeline.json": EMPIRICAL_DIR / "ai_event_timeline.json",

    # debug/
    "active_transitions.json": DEBUG_DIR / "active_transitions.json",
    "active_battle.json": DEBUG_DIR / "active_battle.json",
    "active_bag.json": DEBUG_DIR / "active_bag.json",
    "active_start_menu.json": DEBUG_DIR / "active_start_menu.json",
}

# ============================================================================
# COUNTERS
# ============================================================================

step = 0
total_steps = 16

def log(msg):
    global step
    step += 1
    print(f"  [{step}/{total_steps}] {msg}")


print("=" * 65)
print("RESET — AI Agent v17.8.1 (eval logging: checkpoint + stagnation)")
print("=" * 65)

# ============================================================================
# STEP 1: Create directory structure
# ============================================================================

for d in ALL_DIRS:
    d.mkdir(parents=True, exist_ok=True)
log(f"✅ Directory structure created under {JSONS_ROOT}")
for d in ALL_DIRS[1:]:
    print(f"       📂 {d.relative_to(BASE_PATH)}/")

# ============================================================================
# STEP 2: Migrate old flat files → new locations
# ============================================================================

migrated_count = 0
for old_name, new_path in FLAT_MIGRATION_MAP.items():
    old_path = BASE_PATH / old_name
    if old_path.exists():
        if old_name == "type_data.json" and not new_path.exists():
            shutil.move(str(old_path), str(new_path))
            migrated_count += 1
            print(f"       📦 {old_name} → {new_path.relative_to(BASE_PATH)} (preserved)")
        elif old_name != "type_data.json":
            shutil.move(str(old_path), str(new_path))
            migrated_count += 1
            print(f"       📦 {old_name} → {new_path.relative_to(BASE_PATH)}")

# Migrate old taught_models/ folder if it exists at cogai/taught_models/
old_taught_dir = BASE_PATH / "taught_models"
if old_taught_dir.exists() and old_taught_dir != TAUGHT_MODELS_DIR:
    old_models = sorted([
        d for d in old_taught_dir.iterdir()
        if d.is_dir() and d.name.startswith('model_')
    ])
    for model_dir in old_models:
        dest = TAUGHT_MODELS_DIR / model_dir.name
        if not dest.exists():
            shutil.move(str(model_dir), str(dest))
            migrated_count += 1
            print(f"       📦 taught_models/{model_dir.name}/ → jsons/taught_models/{model_dir.name}/")
        else:
            print(f"       ⏭️  taught_models/{model_dir.name}/ already exists in jsons/, skipping")
    if not any(old_taught_dir.iterdir()):
        old_taught_dir.rmdir()
        print(f"       🗑️  Removed empty old taught_models/")

if migrated_count > 0:
    log(f"✅ Migrated {migrated_count} items from flat layout")
else:
    log(f"✅ No flat files to migrate")

# ============================================================================
# STEP 3: Taught models — ensure at least model_1/ exists
# ============================================================================

existing_models = sorted([
    d for d in TAUGHT_MODELS_DIR.iterdir()
    if d.is_dir() and d.name.startswith('model_')
], key=lambda d: int(d.name.split('_')[1]) if d.name.split('_')[1].isdigit() else 0)

if not existing_models:
    model_1_dir = TAUGHT_MODELS_DIR / "model_1"
    model_1_dir.mkdir(parents=True, exist_ok=True)
    for fn in TAUGHT_FILENAMES:
        with open(model_1_dir / fn, 'w') as f:
            json.dump(TAUGHT_TEMPLATES[fn], f, indent=2)
    log(f"✅ Created empty taught_models/model_1/ with {len(TAUGHT_FILENAMES)} templates")
    existing_models = [model_1_dir]
else:
    for model_dir in existing_models:
        missing = [fn for fn in TAUGHT_FILENAMES if not (model_dir / fn).exists()]
        if missing:
            for fn in missing:
                with open(model_dir / fn, 'w') as f:
                    json.dump(TAUGHT_TEMPLATES[fn], f, indent=2)
            print(f"       ⚠️  {model_dir.name}: created {len(missing)} missing template files")
    log(f"✅ Taught models: {len(existing_models)} folder(s)")

for model_dir in existing_models:
    files_present = list(model_dir.iterdir())
    files_with_data = [f for f in files_present if f.is_file() and f.stat().st_size > 50]
    print(f"       📂 {model_dir.name}: {len(files_present)}/{len(TAUGHT_FILENAMES)} files "
          f"({len(files_with_data)} with data)")

# ============================================================================
# STEP 4: Reset io/ files
# ============================================================================

with open(IO_DIR / "action.json", 'w') as f:
    json.dump({"action": "NONE"}, f)

with open(IO_DIR / "game_state.json", 'w') as f:
    json.dump({
        "s": [0, 0, 0, 0, 0, 0],
        "gs": 0,
        "tf": 0,
        "bd": 0,
        "dead": False,
        "b": {
            "bc": -1, "mc": -1, "ps": -1, "es": -1,
            "ph": -1, "pm": -1, "eh": -1, "em": -1,
            "pl": -1, "el": -1, "pst": 0, "est": 0, "bt": 0,
            "m0": -1, "m1": -1, "m2": -1, "m3": -1,
            "pp0": -1, "pp1": -1, "pp2": -1, "pp3": -1,
            "pss": [-1, -1, -1, -1, -1, -1, -1],
            "em0": -1, "em1": -1, "em2": -1, "em3": -1,
            "epp0": -1, "epp1": -1, "epp2": -1, "epp3": -1,
            "ess": [-1, -1, -1, -1, -1, -1, -1],
            "pc": -1
        },
        "pa": {"c": 0, "s": []},
        "mu": {"mc": -1, "mm": -1, "pc": -1, "sc": -1},
        "bg": {"pk": -1, "bc": -1, "a": 0, "it": []}
    }, f, indent=2)

log(f"✅ io/ — action.json + game_state.json (reset)")

# ============================================================================
# STEP 5: Reset ai_checkpoint/ files
# ============================================================================

fp = AI_CHECKPOINT_DIR / "model_checkpoint.json"
if fp.exists():
    fp.unlink()
    print(f"       🗑️  model_checkpoint.json deleted (AI will bootstrap from taught)")
else:
    print(f"       ⬚  model_checkpoint.json not present (AI will bootstrap)")

with open(AI_CHECKPOINT_DIR / "residual_perceptrons.json", 'w') as f:
    json.dump({}, f)

log(f"✅ ai_checkpoint/ — model_checkpoint (deleted) + residual_perceptrons (reset)")

# ============================================================================
# STEP 6: Reset empirical_knowledge/ files
# ============================================================================

with open(EMPIRICAL_DIR / "exploration_memory.json", 'w') as f:
    json.dump({}, f)

with open(EMPIRICAL_DIR / "roster.json", 'w') as f:
    json.dump({}, f)

with open(EMPIRICAL_DIR / "move_knowledge.json", 'w') as f:
    json.dump({"player_moves": {}, "enemy_moves": {}}, f, indent=2)

with open(EMPIRICAL_DIR / "item_knowledge.json", 'w') as f:
    json.dump({}, f)

with open(EMPIRICAL_DIR / "type_clusters.json", 'w') as f:
    json.dump({
        "move_type_clusters": {},
        "species_type_clusters": {},
        "cluster_effectiveness": {},
        "move_to_cluster": {},
        "species_to_cluster": {},
        "clustering_run_count": 0,
        "last_clustering_timestep": 0
    }, f, indent=2)

with open(EMPIRICAL_DIR / "ai_event_timeline.json", 'w') as f:
    json.dump({
        "events": [],
        "summary": {
            "total_events": 0, "battle_events": 0, "bag_events": 0,
            "map_events": 0, "levelup_events": 0,
            "first_timestep": 0, "last_timestep": 0, "maps_visited": []
        }
    }, f, indent=2)

log(f"✅ empirical_knowledge/ — 6 files reset")

# Handle type_data.json (Track B — preserve if exists, note if absent)
type_data_path = EMPIRICAL_DIR / "type_data.json"
if type_data_path.exists():
    print(f"       📌 type_data.json EXISTS ({type_data_path.stat().st_size} bytes) — preserved (Track B)")
else:
    print(f"       ⬚  type_data.json not found (Track B — optional, from Lua verification script)")

log(f"✅ empirical_knowledge/ — type_data.json checked")

# ============================================================================
# STEP 7: Reset debug/ files
# ============================================================================

for fn in ["active_transitions.json", "active_battle.json",
           "active_bag.json", "active_start_menu.json"]:
    with open(DEBUG_DIR / fn, 'w') as f:
        json.dump({}, f)

log(f"✅ debug/ — 4 active window files (reset)")

# ============================================================================
# STEP 8: Reset logs/ files (v17.8.1 schemas)
# ============================================================================

# --- AI LOGS: checkpoint_metrics.json ---
# Schema matches Brain.save_eval_logs() output exactly
with open(AI_LOGS_DIR / "checkpoint_metrics.json", 'w') as f:
    json.dump({
        "checkpoints": [],
        "metadata": {
            "total_checkpoints": 0,
            "total_timesteps": 0,
            "badge_count": 0,
            "model_number": 0,
            "source": "ai_agent_live",
            "checkpoint_types": {},
            "maps_visited": [],
            "badges_logged": [],
            "trainer_battles_logged": 0
        }
    }, f, indent=2)

# --- AI LOGS: stagnation_metrics.json ---
# Schema matches Brain.save_eval_logs() output exactly
with open(AI_LOGS_DIR / "stagnation_metrics.json", 'w') as f:
    json.dump({
        "snapshots": [],
        "metadata": {
            "total_snapshots": 0,
            "stagnation_types": {},
            "total_stagnation_frames": 0,
            "total_timesteps": 0,
            "stagnation_ratio": 0.0,
            "model_number": 0,
            "source": "ai_agent_live",
            "active_at_save": []
        }
    }, f, indent=2)

# --- TAUGHT LOGS: NOT TOUCHED ---
# taught_logs/ is populated by the teaching pipeline separately.
# The AI agent does not write to this folder.
# Check if files exist and report status.
taught_cp = TAUGHT_LOGS_DIR / "checkpoint_metrics.json"
taught_stag = TAUGHT_LOGS_DIR / "stagnation_metrics.json"
if taught_cp.exists():
    print(f"       📌 taught_logs/checkpoint_metrics.json EXISTS ({taught_cp.stat().st_size} bytes) — preserved")
else:
    print(f"       ⬚  taught_logs/checkpoint_metrics.json not found (place human data here)")
if taught_stag.exists():
    print(f"       📌 taught_logs/stagnation_metrics.json EXISTS ({taught_stag.stat().st_size} bytes) — preserved")
else:
    print(f"       ⬚  taught_logs/stagnation_metrics.json not found (place human data here)")

log(f"✅ logs/ — 2 AI eval files reset, taught_logs/ preserved")

# ============================================================================
# STEP 9: Cleanup — warn about leftover flat files in cogai/
# ============================================================================

all_known_flat_names = list(FLAT_MIGRATION_MAP.keys()) + TAUGHT_FILENAMES
leftover = [BASE_PATH / fn for fn in all_known_flat_names if (BASE_PATH / fn).exists()]

if leftover:
    print(f"\n  ⚠️  WARNING: {len(leftover)} stale flat file(s) still in cogai/:")
    for f in leftover:
        print(f"       ⚠️  {f.name} ({f.stat().st_size} bytes)")
    print(f"       These should have been migrated. Delete manually or re-run reset.")
    log(f"⚠️  {len(leftover)} leftover flat files detected")
else:
    log(f"✅ No leftover flat files in cogai/ (clean)")

# Old taught_models/ at root level
old_taught = BASE_PATH / "taught_models"
if old_taught.exists() and any(old_taught.iterdir()):
    print(f"\n  ⚠️  Old taught_models/ still has content at cogai/taught_models/")
    print(f"       Move contents to cogai/jsons/taught_models/ and delete the old folder.")
    log(f"⚠️  Old taught_models/ still has content")
else:
    log(f"✅ No old taught_models/ at root level")

# ============================================================================
# STEP 10: Verify all expected files exist
# ============================================================================

expected_files = {
    IO_DIR / "action.json": "io",
    IO_DIR / "game_state.json": "io",
    AI_CHECKPOINT_DIR / "residual_perceptrons.json": "ai_checkpoint",
    EMPIRICAL_DIR / "exploration_memory.json": "empirical_knowledge",
    EMPIRICAL_DIR / "roster.json": "empirical_knowledge",
    EMPIRICAL_DIR / "move_knowledge.json": "empirical_knowledge",
    EMPIRICAL_DIR / "item_knowledge.json": "empirical_knowledge",
    EMPIRICAL_DIR / "type_clusters.json": "empirical_knowledge",
    EMPIRICAL_DIR / "ai_event_timeline.json": "empirical_knowledge",
    DEBUG_DIR / "active_transitions.json": "debug",
    DEBUG_DIR / "active_battle.json": "debug",
    DEBUG_DIR / "active_bag.json": "debug",
    DEBUG_DIR / "active_start_menu.json": "debug",
    AI_LOGS_DIR / "checkpoint_metrics.json": "logs/ai_logs",
    AI_LOGS_DIR / "stagnation_metrics.json": "logs/ai_logs",
}

# taught_logs/ files are optional — placed by teaching pipeline, not reset
optional_files = {
    TAUGHT_LOGS_DIR / "checkpoint_metrics.json": "logs/taught_logs",
    TAUGHT_LOGS_DIR / "stagnation_metrics.json": "logs/taught_logs",
}

missing = [str(p.relative_to(BASE_PATH)) for p, _ in expected_files.items() if not p.exists()]
if missing:
    print(f"\n  ❌ VERIFICATION FAILED — missing files:")
    for m in missing:
        print(f"       ❌ {m}")
    log(f"❌ Verification: {len(missing)} files missing")
else:
    log(f"✅ Verification: all {len(expected_files)} expected files present")

# Check optional taught_logs files
optional_present = sum(1 for p in optional_files if p.exists())
optional_total = len(optional_files)
if optional_present == optional_total:
    print(f"       📌 taught_logs/: {optional_present}/{optional_total} files present (human data)")
elif optional_present > 0:
    print(f"       ⚠️  taught_logs/: {optional_present}/{optional_total} files present (incomplete)")
else:
    print(f"       ⬚  taught_logs/: empty (place human eval data here before comparison)")

# ============================================================================
# SUMMARY
# ============================================================================

print(f"\n{'=' * 65}")
print(f"📁 Reset complete — {total_steps} steps")
print(f"   Base: {BASE_PATH}")
print(f"\n   Directory structure:")
print(f"     cogai/")
print(f"     └── jsons/")
print(f"         ├── io/                          (2 files)")
print(f"         │   ├── action.json")
print(f"         │   └── game_state.json")
print(f"         ├── taught_models/                ({len(existing_models)} model folder(s))")
for model_dir in existing_models:
    fc = len(list(model_dir.iterdir()))
    print(f"         │   ├── {model_dir.name}/     ({fc} files)")
print(f"         │   └── (add model_N/ for additional playthroughs)")
print(f"         ├── ai_checkpoint/                (1 file — checkpoint deleted for bootstrap)")
print(f"         │   ├── model_checkpoint.json     (created by AI on save)")
print(f"         │   └── residual_perceptrons.json")
print(f"         ├── empirical_knowledge/          (7 files)")
print(f"         │   ├── exploration_memory.json")
print(f"         │   ├── roster.json")
print(f"         │   ├── move_knowledge.json")
print(f"         │   ├── item_knowledge.json")
print(f"         │   ├── type_clusters.json")
print(f"         │   ├── type_data.json            (Track B — optional)")
print(f"         │   └── ai_event_timeline.json")
print(f"         ├── debug/                        (4 files)")
print(f"         │   ├── active_transitions.json")
print(f"         │   ├── active_battle.json")
print(f"         │   ├── active_bag.json")
print(f"         │   └── active_start_menu.json")
print(f"         └── logs/")
print(f"             ├── ai_logs/                  (2 eval files, reset)")
print(f"             │   ├── checkpoint_metrics.json   (source: ai_agent_live)")
print(f"             │   └── stagnation_metrics.json   (7 types, open/close)")
print(f"             └── taught_logs/              (NOT TOUCHED — human data)")
print(f"                 ├── checkpoint_metrics.json   (place human data here)")
print(f"                 └── stagnation_metrics.json   (place human data here)")

print(f"\n   File counts:")
print(f"     io:                  2 files (reset)")
print(f"     taught_models:       {len(existing_models)} folder(s) (preserved)")
print(f"     ai_checkpoint:       1 file  (checkpoint deleted, residual reset)")
print(f"     empirical_knowledge: 7 files (6 reset + type_data preserved)")
print(f"     debug:               4 files (reset)")
print(f"     logs/ai_logs:        2 files (reset)")
print(f"     logs/taught_logs:    preserved (human data — not touched)")
print(f"     TOTAL:               {len(expected_files)} files verified + {optional_total} optional")

print(f"\n   Eval schemas (v17.8.1):")
print(f"     checkpoint_metrics.json:")
print(f"       triggers: new_map, trainer_battle, badge")
print(f"       fields: checkpoint_id, event_type, event_detail, badge_count,")
print(f"               timestep, frames_from_previous, team_avg_level,")
print(f"               avg_party_hp_ratio, map_id, position, time")
print(f"     stagnation_metrics.json:")
print(f"       types: position_stuck, action_pattern, action_repeat,")
print(f"              area_grinding, no_level_progress, no_map_progress, backtracking")
print(f"       fields: snapshot_id, stagnation_type, timestep_start/end,")
print(f"               duration_frames, map_id, position, resolution")

print(f"\n   Next steps:")
print(f"   1. Place human playthrough data in jsons/taught_models/model_N/")
print(f"   2. Place human eval logs in jsons/logs/taught_logs/")
print(f"   3. Run AI agent — it bootstraps from best taught checkpoint")
print(f"   4. AI eval logs populate in ai_logs/ during play")
print(f"   5. Run aggregation scripts on taught_logs/ and ai_logs/")
print(f"   6. Run compare_eval.py to produce comparison report")
print(f"{'=' * 65}")