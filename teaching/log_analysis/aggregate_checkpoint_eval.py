#!/usr/bin/env python3
"""Aggregate checkpoint_metrics.json across multiple teaching runs of a Pokémon FireRed AI project."""

import argparse
import json
import math
import statistics
from pathlib import Path

COGAI_ROOT = Path(__file__).resolve().parent.parent
JSONS_ROOT = COGAI_ROOT / "jsons"
TAUGHT_LOGS_DIR = JSONS_ROOT / "logs" / "taught_logs"
OUTPUT_DIR = COGAI_ROOT / "log_analysis"
OUTPUT_FILE = OUTPUT_DIR / "aggregated_checkpoint_metrics.json"

MATCH_THRESHOLD = 0.75


def safe_mean(vals):
    """Return mean of vals, or 0.0 if empty."""
    if not vals:
        return 0.0
    return statistics.mean(vals)


def safe_stdev(vals):
    """Return stdev of vals, or 0.0 if fewer than 2 values."""
    if len(vals) < 2:
        return 0.0
    return statistics.stdev(vals)


def checkpoint_key(cp):
    """Build a composite matching key from event_type + event_detail."""
    event_type = cp.get("event_type", "unknown")
    detail = cp.get("event_detail", {}) or {}

    if event_type == "new_map":
        map_id = detail.get("new_map_id", cp.get("map_id", "unknown"))
        return f"new_map:{map_id}"
    elif event_type == "trainer_battle":
        battle_num = detail.get("trainer_battle_number", "?")
        species = detail.get("enemy_species", "?")
        level = detail.get("enemy_level", "?")
        return f"trainer_battle:{battle_num}:{species}:{level}"
    elif event_type == "badge":
        badge_num = detail.get("badge_number", "?")
        return f"badge:{badge_num}"
    else:
        return f"{event_type}:{json.dumps(detail, sort_keys=True)}"


def discover_runs(logs_dir):
    """Find all run_N folders containing a valid checkpoint_metrics.json with data."""
    logs_dir = Path(logs_dir)
    runs = {}
    if not logs_dir.is_dir():
        return runs
    for entry in sorted(logs_dir.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("run_"):
            continue
        try:
            run_num = int(entry.name.split("_", 1)[1])
        except (ValueError, IndexError):
            continue
        metrics_file = entry / "checkpoint_metrics.json"
        if metrics_file.is_file():
            try:
                data = json.loads(metrics_file.read_text())
                checkpoints = data.get("checkpoints", [])
                if checkpoints:
                    runs[run_num] = data
            except (json.JSONDecodeError, OSError):
                continue
    return runs


def aggregate(runs_data, threshold):
    """Aggregate checkpoint data across all discovered runs.

    Returns the full output dict ready for JSON serialization.
    """
    num_runs = len(runs_data)
    min_matches = math.ceil(threshold * num_runs)

    # Map each composite key to a list of (run_num, checkpoint_dict) pairs
    key_to_entries = {}
    key_to_first_detail = {}
    per_run_total = {}

    for run_num, data in sorted(runs_data.items()):
        checkpoints = data.get("checkpoints", [])
        per_run_total[run_num] = len(checkpoints)
        for cp in checkpoints:
            key = checkpoint_key(cp)
            key_to_entries.setdefault(key, []).append((run_num, cp))
            if key not in key_to_first_detail:
                key_to_first_detail[key] = {
                    "event_type": cp.get("event_type", "unknown"),
                    "event_detail": cp.get("event_detail", {}),
                }

    total_unique = len(key_to_entries)

    # Partition into matched / excluded
    aggregated = []
    excluded_list = []
    per_run_matched_count = {r: 0 for r in runs_data}

    for key, entries in key_to_entries.items():
        run_nums = sorted(set(rn for rn, _ in entries))
        if len(run_nums) >= min_matches:
            timesteps = []
            frames = []
            levels = []
            hp_ratios = []
            badge_counts = []
            per_run = []

            for rn, cp in entries:
                ts = cp.get("timestep", 0)
                fr = cp.get("frames_from_previous", 0)
                lv = cp.get("team_avg_level", 0.0)
                hp = cp.get("avg_party_hp_ratio", 0.0)
                bc = cp.get("badge_count", 0)
                timesteps.append(ts)
                frames.append(fr)
                levels.append(lv)
                hp_ratios.append(hp)
                badge_counts.append(bc)
                per_run.append({
                    "run": rn,
                    "timestep": ts,
                    "team_avg_level": lv,
                    "avg_party_hp_ratio": hp,
                    "frames_from_previous": fr,
                    "badge_count": bc,
                })

            info = key_to_first_detail[key]
            aggregated.append({
                "checkpoint_key": key,
                "event_type": info["event_type"],
                "event_detail": info["event_detail"],
                "runs_matched": len(run_nums),
                "run_ids": run_nums,
                "avg_timestep": round(safe_mean(timesteps), 1),
                "std_timestep": round(safe_stdev(timesteps), 1),
                "avg_frames_from_previous": round(safe_mean(frames), 1),
                "std_frames_from_previous": round(safe_stdev(frames), 1),
                "avg_team_avg_level": round(safe_mean(levels), 2),
                "std_team_avg_level": round(safe_stdev(levels), 2),
                "avg_party_hp_ratio": round(safe_mean(hp_ratios), 4),
                "std_party_hp_ratio": round(safe_stdev(hp_ratios), 4),
                "avg_badge_count": round(safe_mean(badge_counts), 1),
                "per_run": per_run,
            })

            for rn in run_nums:
                per_run_matched_count[rn] += 1
        else:
            excluded_list.append({
                "key": key,
                "appeared_in_runs": run_nums,
                "reason": "below_threshold",
            })

    # Sort aggregated checkpoints chronologically by avg_timestep
    aggregated.sort(key=lambda x: x["avg_timestep"])

    checkpoints_meeting = len(aggregated)
    checkpoints_excluded = len(excluded_list)

    per_run_summary = []
    for rn in sorted(runs_data):
        total = per_run_total[rn]
        matched = per_run_matched_count[rn]
        per_run_summary.append({
            "run": rn,
            "total_checkpoints": total,
            "matched": matched,
            "unmatched": total - matched,
        })

    output = {
        "aggregated_checkpoints": aggregated,
        "metadata": {
            "runs_analyzed": num_runs,
            "run_numbers": sorted(runs_data.keys()),
            "match_threshold": threshold,
            "total_unique_checkpoints_across_runs": total_unique,
            "checkpoints_meeting_threshold": checkpoints_meeting,
            "checkpoints_excluded": checkpoints_excluded,
            "excluded_checkpoints": excluded_list,
            "per_run_summary": per_run_summary,
        },
    }
    return output


def print_summary(output):
    """Print a human-readable summary to stdout."""
    meta = output["metadata"]
    agg = output["aggregated_checkpoints"]

    print(f"\n{'=' * 70}")
    print("  Checkpoint Aggregation Summary")
    print(f"{'=' * 70}")
    print(f"  Runs analyzed:    {meta['runs_analyzed']}  {meta['run_numbers']}")
    print(f"  Match threshold:  {meta['match_threshold']}")
    print()

    print("  Per-run checkpoint counts:")
    for rs in meta["per_run_summary"]:
        print(f"    run_{rs['run']:>2}: {rs['total_checkpoints']:>3} total, "
              f"{rs['matched']:>3} matched, {rs['unmatched']:>3} unmatched")
    print()

    print(f"  Unique keys across all runs: {meta['total_unique_checkpoints_across_runs']}")
    print(f"  Keys meeting threshold:      {meta['checkpoints_meeting_threshold']}")
    print(f"  Keys excluded:               {meta['checkpoints_excluded']}")

    if meta["excluded_checkpoints"]:
        print("\n  Excluded checkpoints:")
        for ex in meta["excluded_checkpoints"]:
            print(f"    {ex['key']}  (runs: {ex['appeared_in_runs']})")

    if agg:
        print(f"\n  {'Checkpoint Key':<45} {'Avg TS':>8} {'Avg Lvl':>8} {'Avg HP':>7} {'Runs':>5}")
        print(f"  {'-' * 45} {'-' * 8} {'-' * 8} {'-' * 7} {'-' * 5}")
        for cp in agg:
            print(f"  {cp['checkpoint_key']:<45} "
                  f"{cp['avg_timestep']:>8.0f} "
                  f"{cp['avg_team_avg_level']:>8.2f} "
                  f"{cp['avg_party_hp_ratio']:>7.3f} "
                  f"{cp['runs_matched']:>5}")

    print(f"\n{'=' * 70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate checkpoint_metrics.json across multiple teaching runs."
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=TAUGHT_LOGS_DIR,
        help=f"Directory containing run_N folders (default: {TAUGHT_LOGS_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help=f"Output JSON file path (default: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=MATCH_THRESHOLD,
        help=f"Fraction of runs a checkpoint must appear in (default: {MATCH_THRESHOLD})",
    )
    args = parser.parse_args()

    print(f"Scanning for runs in: {args.logs_dir}")
    runs_data = discover_runs(args.logs_dir)

    if not runs_data:
        print("No valid runs found. Exiting.")
        return

    print(f"Found {len(runs_data)} run(s): {sorted(runs_data.keys())}")
    for rn, data in sorted(runs_data.items()):
        n_cp = len(data.get("checkpoints", []))
        print(f"  run_{rn}: {n_cp} checkpoints")

    output = aggregate(runs_data, args.threshold)
    print_summary(output)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote aggregated metrics to: {output_path}")


if __name__ == "__main__":
    main()