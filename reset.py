# Reset all JSON files for AI Agent (Multi-Pool Pipeline) + Teaching Code
# Creates files if they don't exist, resets to empty if they do
# Update BASE_PATH to match your device

import json
from pathlib import Path

BASE_PATH = Path(r"C:\Users\HP\Documents\cogai")
BASE_PATH.mkdir(parents=True, exist_ok=True)

count = 0
total = 19

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
        },
        "pipelines": {
            "battle": {
                "pipeline_id": "battle",
                "name": "Battle Pipeline",
                "credit_decay": 0.7,
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
                "pipeline_id": "overworld",
                "name": "Overworld Pipeline",
                "credit_decay": 0.7,
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
                "pipeline_id": "bag",
                "name": "Bag Pipeline",
                "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "bag_L0_inventory_awareness", "name": "inventory_awareness", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "bag_L1_item_selection", "name": "item_selection", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "bag_L2_execution", "name": "execution", "output_width": 8, "max_perceptrons": 8, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}}
                ]
            },
            "party": {
                "pipeline_id": "party",
                "name": "Party Pipeline",
                "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "party_L0_assessment", "name": "assessment", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "party_L1_execution", "name": "execution", "output_width": 8, "max_perceptrons": 8, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}}
                ]
            }
        },
        "revenge_targets": {}
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

# 7. taught_start_menu_transitions.json
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

# 14. type_clusters.json
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

# 15. ai_event_timeline.json
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

# 16. residual_perceptrons.json (NEW — pipeline paged perceptrons)
count += 1
with open(BASE_PATH / "residual_perceptrons.json", 'w') as f:
    json.dump({}, f)
print(f"✅ {count}/{total} residual_perceptrons.json")

# ============================================================================
# I/O FILES (Lua ↔ AI communication)
# ============================================================================

# 17. action.json
count += 1
with open(BASE_PATH / "action.json", 'w') as f:
    json.dump({"action": "NONE"}, f)
print(f"✅ {count}/{total} action.json")

# 18. game_state.json
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

# 19. type_data.json — optional Track B ground truth
count += 1
opt_type_data = BASE_PATH / "type_data.json"
if opt_type_data.exists():
    print(f"✅ {count}/{total} type_data.json EXISTS ({opt_type_data.stat().st_size} bytes) — not reset (optional Track B)")
else:
    print(f"⬚  {count}/{total} type_data.json not found (Track B — optional, from Lua verification script)")

print(f"\n{'='*60}")
print(f"📁 All {total} files handled.")
print(f"   Path: {BASE_PATH}")
print(f"\n   File breakdown:")
print(f"     Taught (human → AI):     8 files (reset to empty)")
print(f"     AI agent state:          8 files (reset/deleted)")
print(f"     Lua ↔ AI communication:  2 files (reset)")
print(f"     Optional (Track B):      1 file  (not touched)")
print(f"\n   To start fresh:")
print(f"   1. Run teaching code to record demonstrations")
print(f"   2. Run AI agent — it will bootstrap from taught_model_checkpoint.json")
print(f"   3. Pipelines start empty, populate through play")
print(f"   4. Revenge targets start empty, populate on losses")