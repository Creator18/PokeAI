# Run this script once to reset all 5 taught JSON files to empty state
# Place in C:\Users\HP\Documents\cogai\ and run with Python

import json
from pathlib import Path

BASE_PATH = Path(r"C:\Users\HP\Documents\cogai")

# 1. taught_model_checkpoint.json
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
        "battle_stats": {"battles_recorded": 0, "battle_buffer_size": 0}
    }, f, indent=2)
print("✅ 1/5 taught_model_checkpoint.json")

# 2. taught_transitions.json — SKIPPED (keeping existing data)
print("⏭️ 2/5 taught_transitions.json — kept as-is")

# 3. taught_exploration_memory.json — SKIPPED (keeping existing data)
print("⏭️ 3/5 taught_exploration_memory.json — kept as-is")

# 4. taught_nav_targets.json — SKIPPED (keeping existing data)
print("⏭️ 4/5 taught_nav_targets.json — kept as-is")

# 5. taught_battle_transitions.json
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
print("✅ 5/5 taught_battle_transitions.json")

print("\n🧹 All 5 taught files reset to empty. Ready for fresh teaching.")