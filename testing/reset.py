# ============================================================================
# Reset/Create all teaching-side JSON files to empty state
# v17.8 — Path Reorganization + Live Eval Checkpoints
#
# Creates the jsons/ subfolder hierarchy and resets/creates 14 files:
#   jsons/io/                       → action.json, game_state.json, input_cache.txt
#   jsons/taught_models/run_0/      → 8 taught output files
#   jsons/ai_checkpoint/            → residual_perceptrons.json (single, not per-run)
#   jsons/logs/taught_logs/run_0/   → checkpoint_metrics.json, stagnation_metrics.json
#
# CHANGES from previous reset.py:
# 1. taught_model_checkpoint.json template now includes eval_state block
# 2. checkpoint_metrics.json metadata aligned with live writer
#    (total_timesteps instead of total_frames, added source field)
# ============================================================================

import json
from pathlib import Path

# === RESOLVE BASE PATH ===
SCRIPT_DIR = Path(__file__).resolve().parent
COGAI_ROOT = SCRIPT_DIR.parent

_CANDIDATE_ROOTS = [
    COGAI_ROOT,
    Path("C:/Users/HP/Documents/cogai"),
    Path("C:/Users/natmaw/Documents/Boston Stuff/CS 5100 Foundations of AI/PokeAI"),
]

BASE_PATH = None
for _p in _CANDIDATE_ROOTS:
    if _p.exists():
        BASE_PATH = _p
        break

if BASE_PATH is None:
    BASE_PATH = _CANDIDATE_ROOTS[0]
    print(f"⚠️ WARNING: No valid base path found. Defaulting to {BASE_PATH}")
else:
    print(f"📂 COGAI_ROOT: {BASE_PATH}")

JSONS_ROOT = BASE_PATH / "jsons"

# === SUBFOLDER PATHS ===
IO_DIR = JSONS_ROOT / "io"
TAUGHT_MODELS_DIR = JSONS_ROOT / "taught_models"
RUN_0_TAUGHT = TAUGHT_MODELS_DIR / "run_0"
AI_CHECKPOINT_DIR = JSONS_ROOT / "ai_checkpoint"
TAUGHT_LOGS_DIR = JSONS_ROOT / "logs" / "taught_logs"
RUN_0_LOGS = TAUGHT_LOGS_DIR / "run_0"

# === CREATE ALL DIRECTORIES ===
dirs_to_create = [
    IO_DIR,
    RUN_0_TAUGHT,
    AI_CHECKPOINT_DIR,
    RUN_0_LOGS,
]

print(f"\n📁 Creating directory structure under {JSONS_ROOT}/")
for d in dirs_to_create:
    d.mkdir(parents=True, exist_ok=True)
    rel = d.relative_to(BASE_PATH)
    print(f"  📂 {rel}/")

# === FILE COUNTER ===
count = 0
total = 14


def write_json(filepath, data, label):
    global count
    count += 1
    status = "RESET" if filepath.exists() else "CREATED"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    rel = filepath.relative_to(BASE_PATH)
    print(f"  ✅ {count}/{total} {rel} — {status}")


def write_text(filepath, content, label):
    global count
    count += 1
    status = "RESET" if filepath.exists() else "CREATED"
    with open(filepath, 'w') as f:
        f.write(content)
    rel = filepath.relative_to(BASE_PATH)
    print(f"  ✅ {count}/{total} {rel} — {status}")


# ============================================================================
# jsons/io/ — Real-time Lua ↔ Python communication (3 files)
# ============================================================================
print(f"\n{'='*50}")
print("  jsons/io/ — Real-time communication")
print(f"{'='*50}")

# 1. action.json
write_json(IO_DIR / "action.json", {
    "action": None
}, "Action file")

# 2. game_state.json
write_json(IO_DIR / "game_state.json", {
    "state": [0, 0, 0, 0, 0, 0],
    "palette": [],
    "tiles": [],
    "dead": False,
    "gs": 0,
    "tf": 0,
    "bd": 0
}, "Game state file")

# 3. input_cache.txt
write_text(IO_DIR / "input_cache.txt", "", "Input cache")

# ============================================================================
# jsons/taught_models/run_0/ — Taught output files (8 files)
# ============================================================================
print(f"\n{'='*50}")
print("  jsons/taught_models/run_0/ — Taught output")
print(f"{'='*50}")

# 4. taught_model_checkpoint.json
write_json(RUN_0_TAUGHT / "taught_model_checkpoint.json", {
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
    "battle_stats": {"battles_recorded": 0, "battle_buffer_size": 0},
    "chain_stats": {
        "entity_spawn_counts": {"overworld": 0, "battle": 0, "party": 0, "bag": 0, "shared": 0},
        "entity_merge_counts": {"overworld": 0, "battle": 0, "party": 0, "bag": 0, "shared": 0},
        "entity_capacities": {"overworld": 20, "battle": 10, "party": 5, "bag": 5, "shared": 10}
    },
    "bag_stats": {
        "sessions_recorded": 0, "total_frames": 0,
        "items_used": [], "pockets_visited": []
    },
    "start_menu_stats": {
        "start_menu_total_actions": 0, "start_menu_markov_actions": 0,
        "sessions_recorded": 0, "total_frames": 0, "targets_navigated": {}
    },
    "map_battle_stats": {},
    "type_clusters": {
        "move_type_clusters": {}, "species_type_clusters": {},
        "cluster_effectiveness": {}, "move_to_cluster": {},
        "species_to_cluster": {}, "clustering_run_count": 0
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
    "eval_state": {
        "checkpoint_log": [],
        "last_checkpoint_ts": 0,
        "last_checkpoint_order": -1,
        "nav_visited_targets": []
    }
}, "Model checkpoint")

# 5. taught_transitions.json
write_json(RUN_0_TAUGHT / "taught_transitions.json", {
    "batches": [],
    "metadata": {
        "total_frames": 0,
        "action_changes": 0,
        "maps_visited": []
    }
}, "Overworld transitions")

# 6. taught_exploration_memory.json
write_json(RUN_0_TAUGHT / "taught_exploration_memory.json",
           {}, "Exploration memory")

# 7. taught_nav_targets.json
write_json(RUN_0_TAUGHT / "taught_nav_targets.json", {
    "targets_by_map": {},
    "global_order": [],
    "metadata": {
        "total_targets": 0,
        "maps_with_targets": [],
        "analysis_window_after": 40,
        "min_forward_progress": 0.5,
        "dedup_radius": 2,
        "generated_from_frames": 0,
        "badge_count_at_extraction": 0,
        "team_avg_level_at_extraction": 0.0
    }
}, "Nav targets")

# 8. taught_battle_transitions.json
write_json(RUN_0_TAUGHT / "taught_battle_transitions.json", {
    "battle_sequences": [],
    "flat_frames": [],
    "metadata": {
        "total_battle_frames": 0,
        "battles_recorded": 0,
        "avg_battle_length": 0,
        "outcomes": {},
        "maps_with_battles": [],
        "most_common_sequences": [],
        "frames_with_battle_data": 0,
        "battle_data_coverage": 0.0
    }
}, "Battle transitions")

# 9. taught_bag_transitions.json
write_json(RUN_0_TAUGHT / "taught_bag_transitions.json", {
    "bag_frames": [],
    "metadata": {
        "total_bag_frames": 0,
        "bag_sessions_recorded": 0,
        "items_used": [],
        "pockets_visited": []
    }
}, "Bag transitions")

# 10. taught_start_menu_transitions.json
write_json(RUN_0_TAUGHT / "taught_start_menu_transitions.json", {
    "start_menu_frames": [],
    "metadata": {
        "total_frames": 0,
        "sessions_recorded": 0,
        "targets_navigated": {},
        "avg_session_length": 0
    }
}, "Start menu transitions")

# 11. event_timeline.json
write_json(RUN_0_TAUGHT / "event_timeline.json", {
    "events": [],
    "segments": [],
    "preparation_points": [],
    "metadata": {
        "total_events": 0,
        "total_battles": 0,
        "total_bag_sessions": 0,
        "total_switches": 0,
        "total_map_transitions": 0,
        "playthrough_timesteps": 0,
        "nav_targets_covered": [],
        "generation_timestamp": ""
    }
}, "Event timeline")

# ============================================================================
# jsons/ai_checkpoint/ — Residual perceptrons (1 file, shared across runs)
# ============================================================================
print(f"\n{'='*50}")
print("  jsons/ai_checkpoint/ — Residual perceptrons")
print(f"{'='*50}")

# 12. residual_perceptrons.json
write_json(AI_CHECKPOINT_DIR / "residual_perceptrons.json",
           {}, "Residual perceptrons")

# ============================================================================
# jsons/logs/taught_logs/run_0/ — Evaluation baseline (2 files)
# ============================================================================
print(f"\n{'='*50}")
print("  jsons/logs/taught_logs/run_0/ — Evaluation baseline")
print(f"{'='*50}")

# 13. checkpoint_metrics.json
write_json(RUN_0_LOGS / "checkpoint_metrics.json", {
    "checkpoints": [],
    "metadata": {
        "total_checkpoints": 0,
        "total_timesteps": 0,
        "badge_count": 0,
        "model_number": 0,
        "source": "human_teaching_live"
    }
}, "Taught checkpoint metrics")

# 14. stagnation_metrics.json
write_json(RUN_0_LOGS / "stagnation_metrics.json", {
    "snapshots": [],
    "metadata": {
        "note": "Human baseline has zero stagnation by definition",
        "total_snapshots": 0
    }
}, "Taught stagnation metrics (zero baseline)")

# ============================================================================
# SUMMARY
# ============================================================================
print(f"\n{'='*50}")
print(f"🧹 All {total} teaching files ready under {JSONS_ROOT}/")
print(f"   Taught models: {RUN_0_TAUGHT.relative_to(BASE_PATH)}/")
print(f"   Taught logs:   {RUN_0_LOGS.relative_to(BASE_PATH)}/")
print(f"   Shared:        {AI_CHECKPOINT_DIR.relative_to(BASE_PATH)}/")
print(f"   Fresh teaching can begin.")
print(f"{'='*50}")