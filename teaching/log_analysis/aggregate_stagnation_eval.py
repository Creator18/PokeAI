#!/usr/bin/env python3
"""Aggregate stagnation_metrics.json across multiple teaching runs of a Pokémon FireRed AI project.

Handles overlapping concurrent stagnation events via interval deduplication
to produce a true wall-clock stagnation ratio per run, then averages across runs.
"""

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path

COGAI_ROOT = Path(__file__).resolve().parent.parent
JSONS_ROOT = COGAI_ROOT / "jsons"
TAUGHT_LOGS_DIR = JSONS_ROOT / "logs" / "taught_logs"
OUTPUT_DIR = COGAI_ROOT / "log_analysis"
OUTPUT_FILE = OUTPUT_DIR / "aggregated_stagnation_metrics.json"

ALL_STAGNATION_TYPES = [
    "action_pattern",
    "action_repeat",
    "area_grinding",
    "no_level_progress",
    "no_map_progress",
    "backtracking",
    "position_stuck",
]


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


def merge_intervals(intervals):
    """Merge a list of (start, end) intervals into non-overlapping union intervals.

    Returns list of merged (start, end) tuples sorted by start.
    """
    if not intervals:
        return []
    sorted_iv = sorted(intervals)
    merged = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def deduplicated_stagnation_frames(snapshots):
    """Compute total stagnation frames after merging all overlapping intervals."""
    intervals = []
    for snap in snapshots:
        t_start = snap.get("timestep_start", 0)
        t_end = snap.get("timestep_end", t_start)
        if t_end > t_start:
            intervals.append((t_start, t_end))
    merged = merge_intervals(intervals)
    return sum(end - start for start, end in merged)


def discover_runs(logs_dir):
    """Find all run_N folders containing a valid stagnation_metrics.json with data."""
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
        metrics_file = entry / "stagnation_metrics.json"
        if metrics_file.is_file():
            try:
                data = json.loads(metrics_file.read_text())
                # Include runs even if snapshots is empty (zero stagnation is valid data)
                if "snapshots" in data:
                    runs[run_num] = data
            except (json.JSONDecodeError, OSError):
                continue
    return runs


def compute_per_run_overall(run_num, data):
    """Compute overall stagnation stats for a single run, including deduplication."""
    snapshots = data.get("snapshots", [])
    metadata = data.get("metadata", {})
    total_timesteps = metadata.get("total_timesteps", 0)
    total_events = len(snapshots)

    raw_stagnation_frames = sum(s.get("duration_frames", 0) for s in snapshots)
    raw_ratio = (raw_stagnation_frames / total_timesteps) if total_timesteps > 0 else 0.0

    dedup_frames = deduplicated_stagnation_frames(snapshots)
    dedup_ratio = (dedup_frames / total_timesteps) if total_timesteps > 0 else 0.0

    return {
        "run": run_num,
        "total_events": total_events,
        "total_timesteps": total_timesteps,
        "raw_stagnation_frames": raw_stagnation_frames,
        "raw_stagnation_ratio": round(raw_ratio, 4),
        "deduplicated_stagnation_frames": dedup_frames,
        "deduplicated_stagnation_ratio": round(dedup_ratio, 4),
    }


def compute_per_run_by_type(run_num, data):
    """Compute per-stagnation-type stats for a single run.

    Returns dict: stagnation_type -> {count, total_duration, mean_duration, resolutions}
    """
    snapshots = data.get("snapshots", [])
    by_type = {}

    for snap in snapshots:
        stype = snap.get("stagnation_type", "unknown")
        duration = snap.get("duration_frames", 0)
        resolution = snap.get("resolution", "unknown")

        if stype not in by_type:
            by_type[stype] = {
                "count": 0,
                "total_duration": 0,
                "durations": [],
                "resolutions": [],
            }
        by_type[stype]["count"] += 1
        by_type[stype]["total_duration"] += duration
        by_type[stype]["durations"].append(duration)
        by_type[stype]["resolutions"].append(resolution)

    result = {}
    for stype, info in by_type.items():
        mean_dur = safe_mean(info["durations"])
        result[stype] = {
            "count": info["count"],
            "total_duration": info["total_duration"],
            "mean_duration": round(mean_dur, 1),
            "resolutions": info["resolutions"],
        }
    return result


def aggregate_resolution_distribution(all_resolutions):
    """Compute resolution distribution from a flat list of resolution strings.

    Returns (most_common_list, distribution_dict).
    """
    if not all_resolutions:
        return [], {}
    counter = Counter(all_resolutions)
    total = sum(counter.values())
    distribution = {k: round(v / total, 4) for k, v in counter.most_common()}
    most_common = [k for k, _ in counter.most_common(3)]
    return most_common, distribution


def aggregate(runs_data):
    """Aggregate stagnation data across all discovered runs.

    Returns the full output dict ready for JSON serialization.
    """
    # --- Per-run overall ---
    per_run_overall = []
    for run_num, data in sorted(runs_data.items()):
        per_run_overall.append(compute_per_run_overall(run_num, data))

    dedup_ratios = [r["deduplicated_stagnation_ratio"] for r in per_run_overall]
    total_events_list = [r["total_events"] for r in per_run_overall]
    total_timesteps_list = [r["total_timesteps"] for r in per_run_overall]

    aggregated_overall = {
        "runs_analyzed": len(runs_data),
        "run_numbers": sorted(runs_data.keys()),
        "avg_deduplicated_stagnation_ratio": round(safe_mean(dedup_ratios), 4),
        "std_deduplicated_stagnation_ratio": round(safe_stdev(dedup_ratios), 4),
        "avg_total_events": round(safe_mean(total_events_list), 1),
        "std_total_events": round(safe_stdev(total_events_list), 1),
        "avg_total_timesteps": round(safe_mean(total_timesteps_list), 1),
        "per_run": per_run_overall,
    }

    # --- Per-type across runs ---
    # First compute per-run-per-type stats
    per_run_type_stats = {}
    for run_num, data in sorted(runs_data.items()):
        per_run_type_stats[run_num] = compute_per_run_by_type(run_num, data)

    # Collect all observed stagnation types
    observed_types = set()
    for stats in per_run_type_stats.values():
        observed_types.update(stats.keys())
    observed_types = sorted(observed_types)

    aggregated_by_type = {}
    for stype in observed_types:
        counts = []
        total_durations = []
        mean_durations = []
        all_resolutions = []
        per_run_entries = []

        for run_num in sorted(runs_data.keys()):
            run_stats = per_run_type_stats[run_num].get(stype)
            if run_stats:
                counts.append(run_stats["count"])
                total_durations.append(run_stats["total_duration"])
                mean_durations.append(run_stats["mean_duration"])
                all_resolutions.extend(run_stats["resolutions"])
                per_run_entries.append({
                    "run": run_num,
                    "count": run_stats["count"],
                    "total_duration": run_stats["total_duration"],
                    "mean_duration": run_stats["mean_duration"],
                })
            else:
                # Run had zero events of this type — counts as 0
                counts.append(0)
                total_durations.append(0)
                mean_durations.append(0.0)
                per_run_entries.append({
                    "run": run_num,
                    "count": 0,
                    "total_duration": 0,
                    "mean_duration": 0.0,
                })

        most_common, resolution_dist = aggregate_resolution_distribution(all_resolutions)

        aggregated_by_type[stype] = {
            "avg_count": round(safe_mean(counts), 1),
            "std_count": round(safe_stdev(counts), 1),
            "avg_total_duration": round(safe_mean(total_durations), 1),
            "std_total_duration": round(safe_stdev(total_durations), 1),
            "avg_mean_duration_per_event": round(safe_mean(mean_durations), 1),
            "std_mean_duration_per_event": round(safe_stdev(mean_durations), 1),
            "most_common_resolutions": most_common,
            "resolution_distribution": resolution_dist,
            "per_run": per_run_entries,
        }

    metadata = {
        "preprocessing_applied": [
            "interval_deduplication_for_stagnation_ratio",
            "per_type_duration_averaging",
        ],
        "stagnation_types_observed": observed_types,
        "notes": (
            "deduplicated_stagnation_ratio represents true wall-clock stagnation "
            "percentage after merging overlapping concurrent events"
        ),
    }

    return {
        "aggregated_overall": aggregated_overall,
        "aggregated_by_type": aggregated_by_type,
        "metadata": metadata,
    }


def print_summary(output):
    """Print a human-readable summary to stdout."""
    overall = output["aggregated_overall"]
    by_type = output["aggregated_by_type"]

    print(f"\n{'=' * 75}")
    print("  Stagnation Aggregation Summary")
    print(f"{'=' * 75}")
    print(f"  Runs analyzed:  {overall['runs_analyzed']}  {overall['run_numbers']}")
    print()

    print("  Per-run overview:")
    for r in overall["per_run"]:
        print(f"    run_{r['run']:>2}: {r['total_events']:>3} events, "
              f"{r['total_timesteps']:>6} timesteps, "
              f"raw ratio {r['raw_stagnation_ratio']:.3f}, "
              f"dedup ratio {r['deduplicated_stagnation_ratio']:.3f} "
              f"({r['deduplicated_stagnation_frames']} frames)")
    print()

    print(f"  Avg deduplicated stagnation ratio: "
          f"{overall['avg_deduplicated_stagnation_ratio']:.4f} "
          f"(std {overall['std_deduplicated_stagnation_ratio']:.4f})")
    print(f"  Avg total events:                  "
          f"{overall['avg_total_events']:.1f} "
          f"(std {overall['std_total_events']:.1f})")

    if by_type:
        print(f"\n  {'Type':<22} {'Avg Count':>10} {'Avg Duration':>13} {'Avg Mean/Evt':>13} {'Top Resolution':<20}")
        print(f"  {'-' * 22} {'-' * 10} {'-' * 13} {'-' * 13} {'-' * 20}")
        for stype in sorted(by_type.keys()):
            info = by_type[stype]
            top_res = info["most_common_resolutions"][0] if info["most_common_resolutions"] else "—"
            print(f"  {stype:<22} "
                  f"{info['avg_count']:>10.1f} "
                  f"{info['avg_total_duration']:>13.0f} "
                  f"{info['avg_mean_duration_per_event']:>13.0f} "
                  f"{top_res:<20}")

    print(f"\n{'=' * 75}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate stagnation_metrics.json across multiple teaching runs."
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
    args = parser.parse_args()

    print(f"Scanning for runs in: {args.logs_dir}")
    runs_data = discover_runs(args.logs_dir)

    if not runs_data:
        print("No valid runs found. Exiting.")
        return

    print(f"Found {len(runs_data)} run(s): {sorted(runs_data.keys())}")
    for rn, data in sorted(runs_data.items()):
        n_snap = len(data.get("snapshots", []))
        print(f"  run_{rn}: {n_snap} stagnation snapshots")

    output = aggregate(runs_data)
    print_summary(output)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote aggregated stagnation metrics to: {output_path}")


if __name__ == "__main__":
    main()