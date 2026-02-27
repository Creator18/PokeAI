# ============================================================================
# Reset/Create all 8 taught JSON files to empty state (v17.2)
# If file exists → reset to empty. If file doesn't exist → create it.
# Update BASE_PATH to match your device.
# ============================================================================

import json
from pathlib import Path

# === UPDATE THIS PATH ===
_CANDIDATE_PATHS = [
    Path("C:/Users/HP/Documents/cogai/"),
    Path("C:/Users/natmaw/Documents/Boston Stuff/CS 5100 Foundations of AI/PokeAI/"),
]

BASE_PATH = None
for _p in _CANDIDATE_PATHS:
    if _p.exists():
        BASE_PATH = _p
        break

if BASE_PATH is None:
    BASE_PATH = _CANDIDATE_PATHS[0]
    print(f"⚠️ WARNING: No valid base path found. Defaulting to {BASE_PATH}")
else:
    print(f"📂 BASE_PATH: {BASE_PATH}")

count = 0
total = 8

def write_file(filepath, data, label):
    global count
    count += 1
    status = "RESET" if filepath.exists() else "CREATED"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ {count}/{total} {filepath.name} — {status}")


# 1. taught_model_checkpoint.json
write_file(BASE_PATH / "taught_model_checkpoint.json", {
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
    }
}, "Model checkpoint")

# 2. taught_transitions.json
write_file(BASE_PATH / "taught_transitions.json", {
    "batches": [],
    "metadata": {
        "total_frames": 0,
        "action_changes": 0,
        "maps_visited": []
    }
}, "Overworld transitions")

# 3. taught_exploration_memory.json
write_file(BASE_PATH / "taught_exploration_memory.json", {}, "Exploration memory")

# 4. taught_nav_targets.json
write_file(BASE_PATH / "taught_nav_targets.json", {
    "targets_by_map": {},
    "global_order": [],
    "metadata": {
        "total_targets": 0,
        "maps_with_targets": [],
        "analysis_window_after": 40,
        "min_forward_progress": 0.5,
        "dedup_radius": 2,
        "generated_from_frames": 0
    }
}, "Nav targets")

# 5. taught_battle_transitions.json
write_file(BASE_PATH / "taught_battle_transitions.json", {
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

# 6. taught_bag_transitions.json
write_file(BASE_PATH / "taught_bag_transitions.json", {
    "bag_frames": [],
    "metadata": {
        "total_bag_frames": 0,
        "bag_sessions_recorded": 0,
        "items_used": [],
        "pockets_visited": []
    }
}, "Bag transitions")

# 7. taught_start_menu_transitions.json (NEW v17.2)
write_file(BASE_PATH / "taught_start_menu_transitions.json", {
    "start_menu_frames": [],
    "metadata": {
        "total_frames": 0,
        "sessions_recorded": 0,
        "targets_navigated": {},
        "avg_session_length": 0
    }
}, "Start menu transitions")

# 8. event_timeline.json
write_file(BASE_PATH / "event_timeline.json", {
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

print(f"\n🧹 All {total} taught files ready at {BASE_PATH}")
print(f"   Fresh teaching can begin.")