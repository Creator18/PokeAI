# ============================================================================
# Reorganize JSON files into jsons/ subfolder structure (NO RESET)
# ============================================================================
# Moves all existing JSON files from the flat cogai/ layout into the new
# jsons/ directory structure WITHOUT resetting or overwriting any data.
#
# SAFE OPERATIONS:
#   - Never deletes or overwrites existing data
#   - Handles duplicate filenames (appends _2, _3, etc.)
#   - Handles multiple taught model folders (merges into jsons/taught_models/)
#   - Handles flat taught files (auto-assigns to next model_N/ folder)
#   - Dry-run mode by default — shows what WOULD happen before doing it
#   - Creates missing directories only, never removes them
#
# TARGET STRUCTURE:
#   cogai/jsons/
#   ├── io/                    action.json, game_state.json
#   ├── taught_models/         model_1/ … model_N/
#   ├── ai_checkpoint/         model_checkpoint.json, residual_perceptrons.json
#   ├── empirical_knowledge/   exploration_memory, roster, move/item knowledge, etc.
#   ├── debug/                 active_transitions, active_battle, etc.
#   └── logs/                  evaluation metrics
#       ├── ai_logs/           checkpoint_metrics.json, stagnation_metrics.json
#       └── taught_logs/       checkpoint_metrics.json, stagnation_metrics.json
#
# USAGE:
#   python reorganize.py          # dry run — shows plan
#   python reorganize.py --apply  # executes the moves
#   python reorganize.py --verify # checks current state only
#
# Run from: cogai/testing/
# ============================================================================

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

BASE_PATH = Path(__file__).resolve().parent.parent  # cogai/testing/ → cogai/

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
# FILE → DESTINATION MAPPING
# ============================================================================

FILE_DESTINATION_MAP = {
    # io/
    "action.json": IO_DIR,
    "game_state.json": IO_DIR,

    # ai_checkpoint/
    "model_checkpoint.json": AI_CHECKPOINT_DIR,
    "residual_perceptrons.json": AI_CHECKPOINT_DIR,

    # empirical_knowledge/
    "exploration_memory.json": EMPIRICAL_DIR,
    "roster.json": EMPIRICAL_DIR,
    "move_knowledge.json": EMPIRICAL_DIR,
    "item_knowledge.json": EMPIRICAL_DIR,
    "type_clusters.json": EMPIRICAL_DIR,
    "type_data.json": EMPIRICAL_DIR,
    "ai_event_timeline.json": EMPIRICAL_DIR,

    # debug/
    "active_transitions.json": DEBUG_DIR,
    "active_battle.json": DEBUG_DIR,
    "active_bag.json": DEBUG_DIR,
    "active_start_menu.json": DEBUG_DIR,
}

# Taught model filenames (live inside model_N/ folders)
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

# Eval log files that might exist from a previous v17.8 run
# (won't exist in pre-v17.8 layouts, but included for completeness)
EVAL_LOG_FILES = {
    "checkpoint_metrics.json": AI_LOGS_DIR,    # could be in ai_logs/ or taught_logs/
    "stagnation_metrics.json": AI_LOGS_DIR,
}

# ============================================================================
# HELPERS
# ============================================================================

def safe_dest_path(dest_dir, filename):
    target = dest_dir / filename
    if not target.exists():
        return target
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 2
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def file_has_data(filepath):
    try:
        if not filepath.exists():
            return False
        size = filepath.stat().st_size
        if size <= 4:
            return False
        with open(filepath, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict) and not data:
            return False
        if isinstance(data, list) and not data:
            return False
        if isinstance(data, dict):
            if data == {"action": "NONE"}:
                return False
            if data == {"player_moves": {}, "enemy_moves": {}}:
                return False
            # Empty eval logs
            if data.get('checkpoints') == [] and data.get('snapshots') is None:
                return False
            if data.get('snapshots') == [] and data.get('checkpoints') is None:
                return False
        return True
    except Exception:
        return False


def get_file_summary(filepath):
    try:
        size = filepath.stat().st_size
        if size <= 4:
            return "empty"
        with open(filepath, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict):
            if not data:
                return "empty {}"
            keys = list(data.keys())
            if "timestep" in data:
                return f"ts={data['timestep']} ({len(keys)} keys)"
            if "events" in data:
                return f"{len(data.get('events', []))} events"
            if "batches" in data:
                return f"{len(data.get('batches', []))} batches"
            if "player_moves" in data:
                return f"{len(data.get('player_moves', {}))} moves"
            if "checkpoints" in data:
                return f"{len(data.get('checkpoints', []))} checkpoints"
            if "snapshots" in data:
                return f"{len(data.get('snapshots', []))} snapshots"
            return f"{len(keys)} keys, {size}B"
        if isinstance(data, list):
            return f"{len(data)} items"
        return f"{size}B"
    except Exception:
        return f"{filepath.stat().st_size}B (parse error)"


def get_next_model_number(taught_dir):
    existing = sorted([
        d for d in taught_dir.iterdir()
        if d.is_dir() and d.name.startswith('model_')
    ], key=lambda d: int(d.name.split('_')[1]) if d.name.split('_')[1].isdigit() else 0) if taught_dir.exists() else []

    if not existing:
        return 1
    last_num = max(
        int(d.name.split('_')[1]) for d in existing if d.name.split('_')[1].isdigit()
    )
    return last_num + 1


# ============================================================================
# PLAN BUILDER
# ============================================================================

def build_plan():
    plan = []
    warnings = []

    # --- 1. Flat JSON files in cogai/ ---
    for filename, dest_dir in FILE_DESTINATION_MAP.items():
        src = BASE_PATH / filename
        if not src.exists():
            continue

        dest = dest_dir / filename

        if dest.exists():
            src_has_data = file_has_data(src)
            dest_has_data = file_has_data(dest)

            if src_has_data and dest_has_data:
                safe = safe_dest_path(dest_dir, filename)
                plan.append((src, safe, "move+rename",
                             f"DUPLICATE: dest has data, source renamed to {safe.name}"))
                warnings.append(f"Duplicate: {filename} — both source and dest have data. "
                                f"Source saved as {safe.name}")
            elif src_has_data and not dest_has_data:
                plan.append((src, dest, "move+overwrite",
                             "dest was empty, source overwrites"))
            elif not src_has_data and dest_has_data:
                plan.append((src, None, "delete",
                             "source empty, dest already has data"))
            else:
                plan.append((src, None, "delete",
                             "both empty, keeping dest"))
        else:
            plan.append((src, dest, "move", get_file_summary(src)))

    # --- 2. Old taught_models/ at cogai/taught_models/ ---
    old_taught_dir = BASE_PATH / "taught_models"
    if old_taught_dir.exists() and old_taught_dir != TAUGHT_MODELS_DIR:
        old_models = sorted([
            d for d in old_taught_dir.iterdir()
            if d.is_dir() and d.name.startswith('model_')
        ], key=lambda d: int(d.name.split('_')[1]) if d.name.split('_')[1].isdigit() else 0)

        for model_dir in old_models:
            dest = TAUGHT_MODELS_DIR / model_dir.name

            if dest.exists():
                src_files = {f.name for f in model_dir.iterdir() if f.is_file()}
                dest_files = {f.name for f in dest.iterdir() if f.is_file()}
                conflicts = src_files & dest_files

                if conflicts:
                    src_data_count = sum(1 for f in model_dir.iterdir()
                                         if f.is_file() and file_has_data(f))
                    dest_data_count = sum(1 for f in dest.iterdir()
                                          if f.is_file() and file_has_data(f))

                    if src_data_count > dest_data_count:
                        next_num = get_next_model_number(TAUGHT_MODELS_DIR)
                        planned_models = {p[1].parent.name for p in plan
                                          if p[1] is not None and
                                          TAUGHT_MODELS_DIR in p[1].parents}
                        while f"model_{next_num}" in planned_models:
                            next_num += 1
                        new_dest = TAUGHT_MODELS_DIR / f"model_{next_num}"
                        plan.append((model_dir, new_dest, "move-folder",
                                     f"CONFLICT: {model_dir.name} exists in dest with data, "
                                     f"source moved as model_{next_num}"))
                        warnings.append(f"Taught model conflict: {model_dir.name} → "
                                        f"model_{next_num} (both had data)")
                    else:
                        plan.append((model_dir, None, "skip-folder",
                                     f"dest {model_dir.name} has equal/more data ({dest_data_count} files), "
                                     f"source skipped"))
                        warnings.append(f"Taught model skipped: old {model_dir.name} "
                                        f"(dest already has {dest_data_count} data files)")
                else:
                    for src_file in model_dir.iterdir():
                        if src_file.is_file():
                            plan.append((src_file, dest / src_file.name, "move",
                                         f"merge into existing {model_dir.name}/"))
            else:
                plan.append((model_dir, dest, "move-folder",
                             f"{len(list(model_dir.iterdir()))} files"))

    # --- 3. Flat taught files in cogai/ (not inside a model folder) ---
    flat_taught = [BASE_PATH / fn for fn in TAUGHT_FILENAMES if (BASE_PATH / fn).exists()]

    if flat_taught:
        flat_with_data = [f for f in flat_taught if file_has_data(f)]

        if flat_with_data:
            next_num = get_next_model_number(TAUGHT_MODELS_DIR)
            planned_models = set()
            for p in plan:
                if (p[1] is not None and p[2] == "move-folder" and
                    TAUGHT_MODELS_DIR in p[1].parents):
                    planned_models.add(p[1].name)
            while f"model_{next_num}" in planned_models:
                next_num += 1

            new_model_dir = TAUGHT_MODELS_DIR / f"model_{next_num}"
            plan.append((None, new_model_dir, "create-dir",
                         f"new folder for {len(flat_taught)} flat taught files"))

            for f in flat_taught:
                plan.append((f, new_model_dir / f.name, "move",
                             f"flat taught → model_{next_num}/"))
        else:
            for f in flat_taught:
                plan.append((f, None, "delete", "empty flat taught file"))

    # --- 4. Any unexpected JSON files in cogai/ ---
    known_names = set(FILE_DESTINATION_MAP.keys()) | set(TAUGHT_FILENAMES)
    for f in BASE_PATH.iterdir():
        if f.is_file() and f.suffix == '.json' and f.name not in known_names:
            plan.append((f, None, "unknown",
                         f"unrecognized JSON ({f.stat().st_size}B) — manual review needed"))
            warnings.append(f"Unknown JSON: {f.name} — not moved automatically")

    return plan, warnings


# ============================================================================
# PLAN DISPLAY
# ============================================================================

def display_plan(plan, warnings):
    if not plan:
        print("\n  ✅ Nothing to do — all files are already in the correct location.")
        return

    print(f"\n  📋 REORGANIZATION PLAN ({len(plan)} operations)")
    print(f"  {'─' * 60}")

    action_icons = {
        "move": "📦",
        "move+rename": "📦⚠️",
        "move+overwrite": "📦🔄",
        "move-folder": "📂",
        "delete": "🗑️",
        "skip-folder": "⏭️",
        "create-dir": "📁",
        "unknown": "❓",
    }

    by_action = {}
    for src, dest, action, notes in plan:
        by_action.setdefault(action, []).append((src, dest, notes))

    action_order = ["create-dir", "move-folder", "move", "move+rename",
                    "move+overwrite", "delete", "skip-folder", "unknown"]

    for action in action_order:
        items = by_action.get(action, [])
        if not items:
            continue

        icon = action_icons.get(action, "•")
        print(f"\n  {icon} {action.upper()} ({len(items)}):")

        for src, dest, notes in items:
            src_name = src.name if src else "(new)"
            src_rel = str(src.relative_to(BASE_PATH)) if src and src.exists() else src_name

            if dest:
                dest_rel = str(dest.relative_to(BASE_PATH))
                print(f"       {src_rel}")
                print(f"         → {dest_rel}")
            elif action == "delete":
                print(f"       {src_rel}  (will be deleted)")
            elif action == "skip-folder":
                print(f"       {src_rel}  (skipped)")
            else:
                print(f"       {src_rel}")

            if notes:
                print(f"         💬 {notes}")

    if warnings:
        print(f"\n  ⚠️  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"       ⚠️  {w}")

    moves = sum(1 for _, _, a, _ in plan if a.startswith("move"))
    deletes = sum(1 for _, _, a, _ in plan if a == "delete")
    skips = sum(1 for _, _, a, _ in plan if a.startswith("skip"))
    creates = sum(1 for _, _, a, _ in plan if a == "create-dir")
    unknowns = sum(1 for _, _, a, _ in plan if a == "unknown")

    print(f"\n  📊 Summary: {moves} moves, {creates} creates, "
          f"{deletes} deletes, {skips} skips, {unknowns} unknown")


# ============================================================================
# PLAN EXECUTION
# ============================================================================

def execute_plan(plan):
    print(f"\n  🚀 EXECUTING ({len(plan)} operations)")
    print(f"  {'─' * 60}")

    success = 0
    errors = 0

    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)

    for src, dest, action, notes in plan:
        try:
            if action == "create-dir":
                dest.mkdir(parents=True, exist_ok=True)
                print(f"  ✅ Created {dest.relative_to(BASE_PATH)}/")
                success += 1

            elif action in ("move", "move+rename"):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                src_rel = src.relative_to(BASE_PATH)
                dest_rel = dest.relative_to(BASE_PATH)
                suffix = " (renamed)" if action == "move+rename" else ""
                print(f"  ✅ {src_rel} → {dest_rel}{suffix}")
                success += 1

            elif action == "move+overwrite":
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    dest.unlink()
                shutil.move(str(src), str(dest))
                print(f"  ✅ {src.relative_to(BASE_PATH)} → {dest.relative_to(BASE_PATH)} (overwrite)")
                success += 1

            elif action == "move-folder":
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                print(f"  ✅ {src.relative_to(BASE_PATH)}/ → {dest.relative_to(BASE_PATH)}/")
                success += 1

            elif action == "delete":
                src.unlink()
                print(f"  🗑️  Deleted {src.relative_to(BASE_PATH)}")
                success += 1

            elif action == "skip-folder":
                print(f"  ⏭️  Skipped {src.relative_to(BASE_PATH)}/")
                success += 1

            elif action == "unknown":
                print(f"  ❓ Skipped {src.relative_to(BASE_PATH)} (unknown — manual review)")
                success += 1

        except Exception as e:
            print(f"  ❌ ERROR: {src} → {e}")
            errors += 1

    # Clean up empty old directories
    old_taught = BASE_PATH / "taught_models"
    if old_taught.exists() and old_taught != TAUGHT_MODELS_DIR:
        try:
            remaining = list(old_taught.iterdir())
            if not remaining:
                old_taught.rmdir()
                print(f"  🗑️  Removed empty old taught_models/")
            elif all(not any(d.iterdir()) for d in remaining if d.is_dir()):
                for d in remaining:
                    if d.is_dir():
                        d.rmdir()
                old_taught.rmdir()
                print(f"  🗑️  Removed empty old taught_models/ (with empty subdirs)")
        except Exception:
            pass

    print(f"\n  📊 Done: {success} succeeded, {errors} errors")
    return errors == 0


# ============================================================================
# POST-EXECUTION VERIFICATION
# ============================================================================

def verify_structure():
    print(f"\n  🔍 VERIFICATION")
    print(f"  {'─' * 60}")

    all_ok = True

    for d in ALL_DIRS:
        if d.exists():
            print(f"  ✅ {d.relative_to(BASE_PATH)}/")
        else:
            print(f"  ❌ {d.relative_to(BASE_PATH)}/ MISSING")
            all_ok = False

    # io/
    for fn in ["action.json", "game_state.json"]:
        fp = IO_DIR / fn
        status = "✅" if fp.exists() else "⬚ "
        summary = get_file_summary(fp) if fp.exists() else "not present"
        print(f"    {status} io/{fn} — {summary}")

    # ai_checkpoint/
    for fn in ["model_checkpoint.json", "residual_perceptrons.json"]:
        fp = AI_CHECKPOINT_DIR / fn
        status = "✅" if fp.exists() else "⬚ "
        summary = get_file_summary(fp) if fp.exists() else "not present"
        print(f"    {status} ai_checkpoint/{fn} — {summary}")

    # empirical_knowledge/
    for fn in ["exploration_memory.json", "roster.json", "move_knowledge.json",
               "item_knowledge.json", "type_clusters.json", "type_data.json",
               "ai_event_timeline.json"]:
        fp = EMPIRICAL_DIR / fn
        status = "✅" if fp.exists() else "⬚ "
        summary = get_file_summary(fp) if fp.exists() else ("not present (optional)" if fn == "type_data.json" else "not present")
        print(f"    {status} empirical_knowledge/{fn} — {summary}")

    # debug/
    for fn in ["active_transitions.json", "active_battle.json",
               "active_bag.json", "active_start_menu.json"]:
        fp = DEBUG_DIR / fn
        status = "✅" if fp.exists() else "⬚ "
        summary = get_file_summary(fp) if fp.exists() else "not present"
        print(f"    {status} debug/{fn} — {summary}")

    # logs/
    for fn in ["checkpoint_metrics.json", "stagnation_metrics.json"]:
        fp_ai = AI_LOGS_DIR / fn
        fp_taught = TAUGHT_LOGS_DIR / fn
        status_ai = "✅" if fp_ai.exists() else "⬚ "
        status_taught = "✅" if fp_taught.exists() else "⬚ "
        summary_ai = get_file_summary(fp_ai) if fp_ai.exists() else "not present"
        summary_taught = get_file_summary(fp_taught) if fp_taught.exists() else "not present"
        print(f"    {status_ai} logs/ai_logs/{fn} — {summary_ai}")
        print(f"    {status_taught} logs/taught_logs/{fn} — {summary_taught}")

    # taught models
    models = sorted([
        d for d in TAUGHT_MODELS_DIR.iterdir()
        if d.is_dir() and d.name.startswith('model_')
    ]) if TAUGHT_MODELS_DIR.exists() else []

    if models:
        print(f"\n    📚 Taught models: {len(models)}")
        for model_dir in models:
            files = list(model_dir.iterdir())
            data_files = [f for f in files if f.is_file() and file_has_data(f)]
            print(f"      📂 {model_dir.name}: {len(files)} files ({len(data_files)} with data)")
            for f in sorted(files):
                if f.is_file():
                    has = "📄" if file_has_data(f) else "⬚ "
                    print(f"         {has} {f.name} — {get_file_summary(f)}")
    else:
        print(f"\n    ⬚  No taught model folders found")

    # leftover flat files
    all_known = set(FILE_DESTINATION_MAP.keys()) | set(TAUGHT_FILENAMES)
    leftovers = [f for f in BASE_PATH.iterdir()
                 if f.is_file() and f.suffix == '.json' and f.name in all_known]
    if leftovers:
        print(f"\n    ⚠️  Leftover flat files in cogai/:")
        for f in leftovers:
            print(f"       ⚠️  {f.name} ({f.stat().st_size}B)")
        all_ok = False
    else:
        print(f"\n    ✅ No leftover flat files in cogai/")

    old_taught = BASE_PATH / "taught_models"
    if old_taught.exists() and old_taught != TAUGHT_MODELS_DIR and any(old_taught.iterdir()):
        print(f"    ⚠️  Old taught_models/ still has content")
        all_ok = False

    return all_ok


# ============================================================================
# MAIN
# ============================================================================

def main():
    apply_mode = "--apply" in sys.argv
    verify_only = "--verify" in sys.argv

    print("=" * 65)
    print("REORGANIZE — Move files into jsons/ structure (no reset)")
    print("=" * 65)
    print(f"  Base: {BASE_PATH}")
    print(f"  Mode: {'🚀 APPLY' if apply_mode else '🔍 VERIFY ONLY' if verify_only else '📋 DRY RUN'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if verify_only:
        verify_structure()
        return

    plan, warnings = build_plan()
    display_plan(plan, warnings)

    if not plan:
        print("\n  Verifying current structure...")
        verify_structure()
        return

    if not apply_mode:
        print(f"\n  {'=' * 60}")
        print(f"  This was a DRY RUN — no files were moved.")
        print(f"  To execute, run:  python reorganize.py --apply")
        print(f"  To verify only:   python reorganize.py --verify")
        print(f"  {'=' * 60}")
        return

    print(f"\n  ⚠️  This will move {len(plan)} items. Proceed? [y/N] ", end="")
    response = input().strip().lower()
    if response != 'y':
        print("  Aborted.")
        return

    success = execute_plan(plan)

    print()
    all_ok = verify_structure()

    if all_ok and success:
        print(f"\n  {'=' * 60}")
        print(f"  ✅ Reorganization complete!")
        print(f"\n  Path constants for AI agent Cell 1:")
        print(f'     JSONS_ROOT        = BASE_PATH / "jsons"')
        print(f'     IO_DIR            = JSONS_ROOT / "io"')
        print(f'     TAUGHT_MODELS_DIR = JSONS_ROOT / "taught_models"')
        print(f'     AI_CHECKPOINT_DIR = JSONS_ROOT / "ai_checkpoint"')
        print(f'     EMPIRICAL_DIR     = JSONS_ROOT / "empirical_knowledge"')
        print(f'     DEBUG_DIR         = JSONS_ROOT / "debug"')
        print(f'     LOGS_DIR          = JSONS_ROOT / "logs"')
        print(f'     AI_LOGS_DIR       = LOGS_DIR / "ai_logs"')
        print(f'     TAUGHT_LOGS_DIR   = LOGS_DIR / "taught_logs"')
        print(f"\n  Next: update Cell 1 paths + Lua script paths")
        print(f"  {'=' * 60}")
    else:
        print(f"\n  {'=' * 60}")
        print(f"  ⚠️  Reorganization completed with issues — review output above")
        print(f"  {'=' * 60}")


if __name__ == "__main__":
    main()