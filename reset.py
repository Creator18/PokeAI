# Reset all JSON files for AI Agent v17.2 + Teaching Code
# Creates files if they don't exist, resets to empty if they do
# Update BASE_PATH to match your device

import json
from pathlib import Path

BASE_PATH = Path(r"C:\Users\HP\Documents\cogai")
BASE_PATH.mkdir(parents=True, exist_ok=True)

count = 0
total = 16

# ============================================================================
# TAUGHT FILES (produced by teaching code, consumed by AI agent)
# ============================================================================

# 1. taught_model_checkpoint.json
count += 1
with open(BASE_PATH / "taught_model_checkpoint.json", 'w') as f:
    json.dump({
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
        }
    }, f, indent=2)
print(f"✅ {count}/{total} taught_model_checkpoint.json")

# 2. taught_transitions.json
count += 1
with open(BASE_PATH / "taught_transitions.json", 'w') as f:
    json.dump({
        "batches": [],
        "metadata": {
            "total_frames": 0,
            "action_changes": 0,
            "maps_visited": []
        }
    }, f, indent=2)
print(f"✅ {count}/{total} taught_transitions.json")

# 3. taught_exploration_memory.json
count += 1
with open(BASE_PATH / "taught_exploration_memory.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} taught_exploration_memory.json")

# 4. taught_nav_targets.json
count += 1
with open(BASE_PATH / "taught_nav_targets.json", 'w') as f:
    json.dump({
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
    }, f, indent=2)
print(f"✅ {count}/{total} taught_nav_targets.json")

# 5. taught_battle_transitions.json
count += 1
with open(BASE_PATH / "taught_battle_transitions.json", 'w') as f:
    json.dump({
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
    }, f, indent=2)
print(f"✅ {count}/{total} taught_battle_transitions.json")

# 6. taught_bag_transitions.json
count += 1
with open(BASE_PATH / "taught_bag_transitions.json", 'w') as f:
    json.dump({
        "bag_frames": [],
        "metadata": {
            "total_bag_frames": 0,
            "bag_sessions_recorded": 0,
            "items_used": [],
            "pockets_visited": []
        }
    }, f, indent=2)
print(f"✅ {count}/{total} taught_bag_transitions.json")

# 7. taught_start_menu_transitions.json (NEW v17.2)
count += 1
with open(BASE_PATH / "taught_start_menu_transitions.json", 'w') as f:
    json.dump({
        "start_menu_frames": [],
        "metadata": {
            "total_frames": 0,
            "sessions_recorded": 0,
            "targets_navigated": {},
            "avg_session_length": 0
        }
    }, f, indent=2)
print(f"✅ {count}/{total} taught_start_menu_transitions.json")

# 8. event_timeline.json (taught events from human play)
count += 1
with open(BASE_PATH / "event_timeline.json", 'w') as f:
    json.dump({
        "events": [],
        "segments": [],
        "preparation_points": [],
        "metadata": {
            "nav_targets_covered": [],
            "total_events": 0
        }
    }, f, indent=2)
print(f"✅ {count}/{total} event_timeline.json")

# ============================================================================
# AI AGENT FILES (produced by AI agent)
# ============================================================================

# 9. model_checkpoint.json
count += 1
fp = BASE_PATH / "model_checkpoint.json"
if fp.exists():
    fp.unlink()
    print(f"✅ {count}/{total} model_checkpoint.json (DELETED — AI will bootstrap from taught)")
else:
    print(f"✅ {count}/{total} model_checkpoint.json (not present — AI will bootstrap)")

# 10. exploration_memory.json
count += 1
with open(BASE_PATH / "exploration_memory.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} exploration_memory.json")

# 11. roster.json
count += 1
with open(BASE_PATH / "roster.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} roster.json")

# 12. move_knowledge.json
count += 1
with open(BASE_PATH / "move_knowledge.json", 'w') as f:
    json.dump({"player_moves": {}, "enemy_moves": {}}, f, indent=2)
print(f"✅ {count}/{total} move_knowledge.json")

# 13. item_knowledge.json
count += 1
with open(BASE_PATH / "item_knowledge.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} item_knowledge.json")

# 14. type_clusters.json (NEW v17.2)
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

# 15. ai_event_timeline.json (NEW v17.2)
count += 1
with open(BASE_PATH / "ai_event_timeline.json", 'w') as f:
    json.dump({
        "events": [],
        "summary": {
            "total_events": 0,
            "battle_events": 0,
            "bag_events": 0,
            "map_events": 0,
            "levelup_events": 0,
            "first_timestep": 0,
            "last_timestep": 0,
            "maps_visited": []
        }
    }, f, indent=2)
print(f"✅ {count}/{total} ai_event_timeline.json")

# ============================================================================
# I/O FILES (Lua ↔ AI communication)
# ============================================================================

# 16. action.json
count += 1
with open(BASE_PATH / "action.json", 'w') as f:
    json.dump({"action": "NONE"}, f)
print(f"✅ {count}/{total} action.json")

# ============================================================================
# OPTIONAL FILES (not reset, just noted)
# ============================================================================

print(f"\n{'='*60}")
print("OPTIONAL FILES (not reset by this script):")

opt_type_data = BASE_PATH / "type_data.json"
if opt_type_data.exists():
    print(f"  📄 type_data.json EXISTS ({opt_type_data.stat().st_size} bytes)")
else:
    print(f"  ❌ type_data.json not found (Track B — optional, from Lua verification script)")

opt_game_state = BASE_PATH / "game_state.json"
if opt_game_state.exists():
    print(f"  📄 game_state.json EXISTS (produced by Lua — will be overwritten at runtime)")
else:
    print(f"  ❌ game_state.json not found (Lua will create it at runtime)")

print(f"{'='*60}")
print(f"\n🧹 All {total} files reset. Ready for fresh teaching + AI play.")
print(f"   Path: {BASE_PATH}")
print(f"\n   To start fresh:")
print(f"   1. Run teaching code to record demonstrations")
print(f"   2. Delete model_checkpoint.json if it exists (already done above)")
print(f"   3. Run AI agent — it will bootstrap from taught_model_checkpoint.json")