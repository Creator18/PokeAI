# ============================================================================
# reorganize.py — Run Management & Structure Validation (v17.8.1)
#
# Lives in cogai/testing/. Handles:
#   1. Validates the jsons/ directory structure exists (run reset.py if not)
#   2. Finds the current (highest-numbered) run folder
#   3. If the current run has non-empty data → creates next run_N+1 with
#      empty files, ready for a new playthrough
#   4. Reports current state of all runs
#
# Run-numbered folders:
#   jsons/taught_models/run_N/      → 8 taught output files per playthrough
#   jsons/logs/taught_logs/run_N/   → eval baseline per playthrough
#
# Shared (not per-run):
#   jsons/io/                       → real-time Lua ↔ Python communication
#   jsons/ai_checkpoint/            → residual_perceptrons.json (accumulates)
#
# CHANGES from v17.8 reorganize.py:
# 1. eval_state template updated to v17.8.1 event-driven format
# 2. NEW: stagnation_state block in checkpoint template
# 3. checkpoint_metrics.json template updated with full v17.8.1 fields
# 4. stagnation_metrics.json template updated with full v17.8.1 fields
# 5. is_run_empty() now also checks stagnation snapshots
# 6. get_run_summary() now includes stagnation snapshot count
#
# Usage:
#   python reorganize.py           → check state, create next run if needed
#   python reorganize.py --status  → report only, no changes
#   python reorganize.py --force   → always create next run even if current empty
# ============================================================================

import json
import sys
from pathlib import Path
from datetime import datetime

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
AI_CHECKPOINT_DIR = JSONS_ROOT / "ai_checkpoint"
TAUGHT_LOGS_DIR = JSONS_ROOT / "logs" / "taught_logs"


# ============================================================================
# EMPTY FILE TEMPLATES
# ============================================================================

EMPTY_TAUGHT_FILES = {
    "taught_model_checkpoint.json": {
        "timestep": 0,
        "perceptrons": {"actions": [], "entities": []},
        "debt_tracking": {"map_novelty_debt": {}, "location_novelty": {}, "visited_maps": {}},
        "control_mode": "move",
        "markov_stats": {"markov_action_count": 0, "curiosity_action_count": 0},
        "blend_stats": {"blend_count": 0, "last_blend_tier": 0},
        "battle_stats": {"battles_recorded": 0, "battle_buffer_size": 0},
        "chain_stats": {
            "entity_spawn_counts": {"overworld": 0, "battle": 0, "party": 0, "bag": 0, "shared": 0},
            "entity_merge_counts": {"overworld": 0, "battle": 0, "party": 0, "bag": 0, "shared": 0},
            "entity_capacities": {"overworld": 20, "battle": 10, "party": 5, "bag": 5, "shared": 10},
        },
        "bag_stats": {"sessions_recorded": 0, "total_frames": 0, "items_used": [], "pockets_visited": []},
        "start_menu_stats": {
            "start_menu_total_actions": 0, "start_menu_markov_actions": 0,
            "sessions_recorded": 0, "total_frames": 0, "targets_navigated": {},
        },
        "map_battle_stats": {},
        "type_clusters": {
            "move_type_clusters": {}, "species_type_clusters": {},
            "cluster_effectiveness": {}, "move_to_cluster": {},
            "species_to_cluster": {}, "clustering_run_count": 0,
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
                    {"pool_id": "battle_L5_outcome_observation", "name": "outcome_observation", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                ],
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
                    {"pool_id": "overworld_L6_outcome_observation", "name": "outcome_observation", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                ],
            },
            "bag": {
                "pipeline_id": "bag", "name": "Bag Pipeline", "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "bag_L0_inventory_awareness", "name": "inventory_awareness", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "bag_L1_item_selection", "name": "item_selection", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "bag_L2_execution", "name": "execution", "output_width": 8, "max_perceptrons": 8, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                ],
            },
            "party": {
                "pipeline_id": "party", "name": "Party Pipeline", "credit_decay": 0.7,
                "pools": [
                    {"pool_id": "party_L0_assessment", "name": "assessment", "output_width": 8, "max_perceptrons": 10, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                    {"pool_id": "party_L1_execution", "name": "execution", "output_width": 8, "max_perceptrons": 8, "spawn_threshold": 0.0005, "spawn_count": 0, "authority": 0.0, "residual": {}},
                ],
            },
        },
        "revenge_targets": {},
        # v17.8.1: Event-driven evaluation checkpoint state
        "eval_state": {
            "checkpoint_log": [],
            "last_checkpoint_ts": 0,
            "checkpoint_counter": 0,
            "maps_first_visited": [],
            "badges_checkpointed": [],
            "trainer_battles_checkpointed": 0,
        },
        # v17.8.1: Stagnation snapshot state
        "stagnation_state": {
            "snapshot_log": [],
            "snapshot_counter": 0,
            "total_stagnation_frames": 0,
            "cooldowns": {},
            "map_progress_ts": 0,
            "last_check_ts": 0,
            "active_events": {},
        },
    },
    "taught_transitions.json": {
        "batches": [],
        "metadata": {"total_frames": 0, "action_changes": 0, "maps_visited": []},
    },
    "taught_exploration_memory.json": {},
    "taught_nav_targets.json": {
        "targets_by_map": {},
        "global_order": [],
        "metadata": {
            "total_targets": 0, "maps_with_targets": [],
            "analysis_window_after": 40, "min_forward_progress": 0.5,
            "dedup_radius": 2, "generated_from_frames": 0,
            "badge_count_at_extraction": 0, "team_avg_level_at_extraction": 0.0,
        },
    },
    "taught_battle_transitions.json": {
        "battle_sequences": [],
        "flat_frames": [],
        "metadata": {
            "total_battle_frames": 0, "battles_recorded": 0,
            "avg_battle_length": 0, "outcomes": {},
            "maps_with_battles": [], "most_common_sequences": [],
            "frames_with_battle_data": 0, "battle_data_coverage": 0.0,
        },
    },
    "taught_bag_transitions.json": {
        "bag_frames": [],
        "metadata": {
            "total_bag_frames": 0, "bag_sessions_recorded": 0,
            "items_used": [], "pockets_visited": [],
        },
    },
    "taught_start_menu_transitions.json": {
        "start_menu_frames": [],
        "metadata": {
            "total_frames": 0, "sessions_recorded": 0,
            "targets_navigated": {}, "avg_session_length": 0,
        },
    },
    "event_timeline.json": {
        "events": [],
        "segments": [],
        "preparation_points": [],
        "metadata": {
            "total_events": 0, "total_battles": 0, "total_bag_sessions": 0,
            "total_switches": 0, "total_map_transitions": 0,
            "playthrough_timesteps": 0, "nav_targets_covered": [],
            "generation_timestamp": "",
        },
    },
}

EMPTY_LOG_FILES = {
    "checkpoint_metrics.json": {
        "checkpoints": [],
        "metadata": {
            "total_checkpoints": 0,
            "total_timesteps": 0,
            "badge_count": 0,
            "model_number": 0,
            "source": "human_teaching_live",
            "checkpoint_types": {},
            "maps_visited": [],
            "badges_logged": [],
            "trainer_battles_logged": 0,
        },
    },
    "stagnation_metrics.json": {
        "snapshots": [],
        "metadata": {
            "total_snapshots": 0,
            "stagnation_types": {},
            "total_stagnation_frames": 0,
            "total_timesteps": 0,
            "stagnation_ratio": 0.0,
            "model_number": 0,
            "source": "human_teaching_live",
            "active_at_save": [],
        },
    },
}


# ============================================================================
# HELPERS
# ============================================================================

def get_run_numbers(parent_dir):
    """Scan parent_dir for run_N folders, return sorted list of N values."""
    if not parent_dir.exists():
        return []
    nums = []
    for entry in parent_dir.iterdir():
        if entry.is_dir() and entry.name.startswith("run_"):
            try:
                n = int(entry.name.split("_")[1])
                nums.append(n)
            except (IndexError, ValueError):
                pass
    return sorted(nums)


def get_highest_run(parent_dir):
    """Return highest run number, or -1 if none exist."""
    nums = get_run_numbers(parent_dir)
    return nums[-1] if nums else -1


def is_run_empty(taught_dir, logs_dir):
    """
    Check if a run folder contains only empty/default data.
    A run is 'empty' if its checkpoint timestep is 0, it has no
    transition batches, no eval checkpoints, and no stagnation snapshots.
    """
    # Check taught_model_checkpoint.json
    ckpt = taught_dir / "taught_model_checkpoint.json"
    if ckpt.exists():
        try:
            with open(ckpt, 'r') as f:
                data = json.load(f)
            if data.get("timestep", 0) > 0:
                return False
        except (json.JSONDecodeError, Exception):
            pass

    # Check taught_transitions.json
    trans = taught_dir / "taught_transitions.json"
    if trans.exists():
        try:
            with open(trans, 'r') as f:
                data = json.load(f)
            if len(data.get("batches", [])) > 0:
                return False
        except (json.JSONDecodeError, Exception):
            pass

    # Check checkpoint_metrics.json in logs
    metrics = logs_dir / "checkpoint_metrics.json"
    if metrics.exists():
        try:
            with open(metrics, 'r') as f:
                data = json.load(f)
            if len(data.get("checkpoints", [])) > 0:
                return False
        except (json.JSONDecodeError, Exception):
            pass

    # Check stagnation_metrics.json in logs
    stagnation = logs_dir / "stagnation_metrics.json"
    if stagnation.exists():
        try:
            with open(stagnation, 'r') as f:
                data = json.load(f)
            if len(data.get("snapshots", [])) > 0:
                return False
        except (json.JSONDecodeError, Exception):
            pass

    return True


def create_run_folder(run_number):
    """Create run_N folders in both taught_models and taught_logs with empty files."""
    taught_dir = TAUGHT_MODELS_DIR / f"run_{run_number}"
    logs_dir = TAUGHT_LOGS_DIR / f"run_{run_number}"

    taught_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    created_count = 0

    # Write taught model files
    for filename, template in EMPTY_TAUGHT_FILES.items():
        filepath = taught_dir / filename
        with open(filepath, 'w') as f:
            json.dump(template, f, indent=2)
        created_count += 1

    # Write log files with correct model_number
    for filename, template in EMPTY_LOG_FILES.items():
        filepath = logs_dir / filename
        data = json.loads(json.dumps(template))  # deep copy
        if "metadata" in data and "model_number" in data["metadata"]:
            data["metadata"]["model_number"] = run_number
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        created_count += 1

    return taught_dir, logs_dir, created_count


def get_run_summary(run_number):
    """Get a brief summary of what's in a run folder."""
    taught_dir = TAUGHT_MODELS_DIR / f"run_{run_number}"
    logs_dir = TAUGHT_LOGS_DIR / f"run_{run_number}"

    summary = {"run": run_number, "empty": True, "timestep": 0,
               "batches": 0, "battles": 0, "checkpoints": 0,
               "stagnation_snapshots": 0}

    ckpt = taught_dir / "taught_model_checkpoint.json"
    if ckpt.exists():
        try:
            with open(ckpt, 'r') as f:
                data = json.load(f)
            summary["timestep"] = data.get("timestep", 0)
            if summary["timestep"] > 0:
                summary["empty"] = False
        except Exception:
            pass

    trans = taught_dir / "taught_transitions.json"
    if trans.exists():
        try:
            with open(trans, 'r') as f:
                data = json.load(f)
            summary["batches"] = len(data.get("batches", []))
            if summary["batches"] > 0:
                summary["empty"] = False
        except Exception:
            pass

    battle = taught_dir / "taught_battle_transitions.json"
    if battle.exists():
        try:
            with open(battle, 'r') as f:
                data = json.load(f)
            summary["battles"] = data.get("metadata", {}).get("battles_recorded", 0)
        except Exception:
            pass

    metrics = logs_dir / "checkpoint_metrics.json"
    if metrics.exists():
        try:
            with open(metrics, 'r') as f:
                data = json.load(f)
            summary["checkpoints"] = len(data.get("checkpoints", []))
            if summary["checkpoints"] > 0:
                summary["empty"] = False
        except Exception:
            pass

    stagnation = logs_dir / "stagnation_metrics.json"
    if stagnation.exists():
        try:
            with open(stagnation, 'r') as f:
                data = json.load(f)
            summary["stagnation_snapshots"] = len(data.get("snapshots", []))
            if summary["stagnation_snapshots"] > 0:
                summary["empty"] = False
        except Exception:
            pass

    return summary


# ============================================================================
# VALIDATION
# ============================================================================

def validate_structure():
    """Check that the jsons/ directory structure exists. Return list of issues."""
    issues = []

    if not JSONS_ROOT.exists():
        issues.append(f"jsons/ root does not exist at {JSONS_ROOT}")
        return issues  # nothing else to check

    for d, label in [
        (IO_DIR, "jsons/io/"),
        (TAUGHT_MODELS_DIR, "jsons/taught_models/"),
        (AI_CHECKPOINT_DIR, "jsons/ai_checkpoint/"),
        (TAUGHT_LOGS_DIR, "jsons/logs/taught_logs/"),
    ]:
        if not d.exists():
            issues.append(f"Missing directory: {label}")

    # Check IO files
    for f in ["action.json", "game_state.json", "input_cache.txt"]:
        if not (IO_DIR / f).exists():
            issues.append(f"Missing IO file: {f}")

    # Check residual perceptrons
    if not (AI_CHECKPOINT_DIR / "residual_perceptrons.json").exists():
        issues.append("Missing: ai_checkpoint/residual_perceptrons.json")

    # Check at least one run exists
    if get_highest_run(TAUGHT_MODELS_DIR) < 0:
        issues.append("No run folders found in taught_models/")
    if get_highest_run(TAUGHT_LOGS_DIR) < 0:
        issues.append("No run folders found in logs/taught_logs/")

    return issues


# ============================================================================
# MAIN COMMANDS
# ============================================================================

def cmd_status():
    """Report current state of all runs."""
    print(f"\n{'='*60}")
    print("  REORGANIZE — STATUS REPORT")
    print(f"{'='*60}")

    issues = validate_structure()
    if issues:
        print(f"\n⚠️ Structure issues ({len(issues)}):")
        for issue in issues:
            print(f"  ❌ {issue}")
        print(f"\n  Run reset.py first to create the base structure.")
        return False

    print(f"\n✅ Directory structure valid")

    # IO files
    print(f"\n📂 jsons/io/")
    for f in ["action.json", "game_state.json", "input_cache.txt"]:
        fp = IO_DIR / f
        status = "✅" if fp.exists() else "❌"
        print(f"  {status} {f}")

    # Residual perceptrons
    rp = AI_CHECKPOINT_DIR / "residual_perceptrons.json"
    print(f"\n📂 jsons/ai_checkpoint/")
    if rp.exists():
        try:
            with open(rp, 'r') as f:
                data = json.load(f)
            n_entries = sum(len(v) if isinstance(v, dict) else 0 for v in data.values())
            print(f"  ✅ residual_perceptrons.json ({n_entries} entries)")
        except Exception:
            print(f"  ⚠️ residual_perceptrons.json (unreadable)")
    else:
        print(f"  ❌ residual_perceptrons.json missing")

    # Run folders
    taught_runs = get_run_numbers(TAUGHT_MODELS_DIR)
    log_runs = get_run_numbers(TAUGHT_LOGS_DIR)
    all_runs = sorted(set(taught_runs + log_runs))

    print(f"\n📂 Runs: {len(all_runs)} found")
    print(f"{'─'*60}")

    for n in all_runs:
        s = get_run_summary(n)
        taught_exists = (TAUGHT_MODELS_DIR / f"run_{n}").exists()
        logs_exists = (TAUGHT_LOGS_DIR / f"run_{n}").exists()

        status = "🟢 EMPTY" if s["empty"] else "🔵 HAS DATA"
        parts = []
        if s["timestep"] > 0:
            parts.append(f"step={s['timestep']}")
        if s["batches"] > 0:
            parts.append(f"batches={s['batches']}")
        if s["battles"] > 0:
            parts.append(f"battles={s['battles']}")
        if s["checkpoints"] > 0:
            parts.append(f"checkpoints={s['checkpoints']}")
        if s["stagnation_snapshots"] > 0:
            parts.append(f"stagnation={s['stagnation_snapshots']}")
        detail = f" | {', '.join(parts)}" if parts else ""

        missing = []
        if not taught_exists:
            missing.append("taught_models")
        if not logs_exists:
            missing.append("taught_logs")
        missing_str = f" ⚠️ missing: {', '.join(missing)}" if missing else ""

        print(f"  run_{n}: {status}{detail}{missing_str}")

    # Identify active run
    highest = max(all_runs) if all_runs else -1
    if highest >= 0:
        s = get_run_summary(highest)
        if s["empty"]:
            print(f"\n  ▶ Active run: run_{highest} (empty, ready for recording)")
        else:
            print(f"\n  ▶ Active run: run_{highest} (has data — run reorganize to create next)")

    print(f"{'='*60}\n")
    return True


def cmd_reorganize(force=False):
    """Check highest run, create next if non-empty (or if --force)."""
    print(f"\n{'='*60}")
    print("  REORGANIZE — Preparing next run")
    print(f"{'='*60}")

    # Validate structure first
    issues = validate_structure()
    if issues:
        print(f"\n⚠️ Structure issues found — run reset.py first:")
        for issue in issues:
            print(f"  ❌ {issue}")
        return False

    # Find highest run across both taught_models and taught_logs
    taught_highest = get_highest_run(TAUGHT_MODELS_DIR)
    logs_highest = get_highest_run(TAUGHT_LOGS_DIR)
    highest = max(taught_highest, logs_highest)

    if highest < 0:
        print(f"\n⚠️ No run folders found. Run reset.py first.")
        return False

    # Sync: ensure both directories have the same run folders
    if taught_highest != logs_highest:
        print(f"\n⚠️ Run mismatch: taught_models has run_{taught_highest}, "
              f"taught_logs has run_{logs_highest}")
        sync_target = max(taught_highest, logs_highest)
        taught_dir = TAUGHT_MODELS_DIR / f"run_{sync_target}"
        logs_dir = TAUGHT_LOGS_DIR / f"run_{sync_target}"
        if not taught_dir.exists():
            print(f"  Creating missing taught_models/run_{sync_target}/")
            create_run_folder(sync_target)
        if not logs_dir.exists():
            print(f"  Creating missing taught_logs/run_{sync_target}/")
            logs_dir.mkdir(parents=True, exist_ok=True)
            for fn, tmpl in EMPTY_LOG_FILES.items():
                data = json.loads(json.dumps(tmpl))
                if "metadata" in data and "model_number" in data["metadata"]:
                    data["metadata"]["model_number"] = sync_target
                with open(logs_dir / fn, 'w') as f:
                    json.dump(data, f, indent=2)
        highest = sync_target

    # Check if current run is empty
    current_taught = TAUGHT_MODELS_DIR / f"run_{highest}"
    current_logs = TAUGHT_LOGS_DIR / f"run_{highest}"
    empty = is_run_empty(current_taught, current_logs)

    if empty and not force:
        print(f"\n  run_{highest} is still empty — no new run needed.")
        print(f"  ▶ Active run: run_{highest} (ready for recording)")
        print(f"\n  Use --force to create a new run anyway.")
        return True

    if empty and force:
        print(f"\n  run_{highest} is empty but --force specified.")

    if not empty:
        s = get_run_summary(highest)
        print(f"\n  run_{highest} has data:")
        if s["timestep"] > 0:
            print(f"    timestep: {s['timestep']}")
        if s["batches"] > 0:
            print(f"    batches: {s['batches']}")
        if s["battles"] > 0:
            print(f"    battles: {s['battles']}")
        if s["checkpoints"] > 0:
            print(f"    checkpoints: {s['checkpoints']}")
        if s["stagnation_snapshots"] > 0:
            print(f"    stagnation snapshots: {s['stagnation_snapshots']}")

    # Create next run
    next_n = highest + 1
    print(f"\n  Creating run_{next_n}...")
    taught_dir, logs_dir, file_count = create_run_folder(next_n)

    print(f"\n  ✅ run_{next_n} created:")
    print(f"     {taught_dir.relative_to(BASE_PATH)}/  ({len(EMPTY_TAUGHT_FILES)} files)")
    print(f"     {logs_dir.relative_to(BASE_PATH)}/  ({len(EMPTY_LOG_FILES)} files)")
    print(f"\n  ▶ Active run: run_{next_n} (empty, ready for recording)")
    print(f"{'='*60}\n")
    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--status" in args:
        cmd_status()
    elif "--force" in args:
        cmd_reorganize(force=True)
    else:
        cmd_reorganize(force=False)