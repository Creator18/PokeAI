# ============================================================================
# markov.py — Taught Reference, Blend System, All Markov Systems,
#              Multi-Model Loading, Nav Target Loading
# ============================================================================
# All methods take `brain` as first argument. Attached via attach_to_brain().
#
# Contains:
#   - Taught model reference (load + blend)
#   - Multi-model taught data loading (load_all_taught_models + merge helpers)
#   - Overworld Markov (load, extract context, similarity, get action)
#   - Battle Markov (load, similarity, get action)
#   - Bag Markov (load, similarity, get action)
#   - Start Menu Markov (load, similarity, get action)
#   - Nav targets (load primary + merge secondary)
# ============================================================================

import json
import numpy as np
from pathlib import Path

from constants import (
    TAUGHT_MODELS_DIR,
    TAUGHT_MODEL_CHECKPOINT_FILENAME, TAUGHT_TRANSITIONS_FILENAME,
    TAUGHT_BATTLE_TRANSITIONS_FILENAME, TAUGHT_BAG_TRANSITIONS_FILENAME,
    TAUGHT_START_MENU_TRANSITIONS_FILENAME, TAUGHT_EXPLORATION_FILENAME,
    TAUGHT_NAV_TARGETS_FILENAME, TAUGHT_EVENT_TIMELINE_FILENAME,
    AI_EVENT_TIMELINE_FILE,
    MARKOV_IMMEDIATE_WEIGHT, MARKOV_SEQUENTIAL_WEIGHT, MARKOV_PARTIAL_WEIGHT,
    MARKOV_FAMILIARITY_THRESHOLD,
    MARKOV_SEQ_FULL_WEIGHT, MARKOV_SEQ_MEDIUM_WEIGHT, MARKOV_SEQ_SHORT_WEIGHT,
    MARKOV_POS_EXACT_BONUS, MARKOV_POS_NEAR_BONUS, MARKOV_POS_FAR_BONUS,
    MARKOV_POS_MAX_DIST,
    BATTLE_MARKOV_ACTION_SEQ_WEIGHT, BATTLE_MARKOV_PALETTE_WEIGHT,
    BATTLE_MARKOV_MENU_STATE_WEIGHT,
    BATTLE_MARKOV_THRESHOLD_LOW, BATTLE_MARKOV_THRESHOLD_HIGH,
    BAG_MARKOV_MENU_STATE_WEIGHT, BAG_MARKOV_ACTION_SEQ_WEIGHT,
    BAG_MARKOV_PARTY_CONTEXT_WEIGHT, BAG_MARKOV_THRESHOLD,
    START_MENU_MARKOV_MENU_STATE_WEIGHT, START_MENU_MARKOV_ACTION_SEQ_WEIGHT,
    START_MENU_MARKOV_CONTEXT_WEIGHT, START_MENU_MARKOV_THRESHOLD,
    get_taught_model_paths,
)


# ============================================================================
# TAUGHT MODEL REFERENCE
# ============================================================================

def load_taught_reference(brain, filepath):
    try:
        if not Path(filepath).exists():
            print(f"  No taught reference model found at {filepath}"); return
        with open(filepath, 'r') as f:
            model = json.load(f)
        if "perceptrons" not in model:
            print(f"  ⚠️ Taught reference model empty or invalid"); return
        for saved_action in model["perceptrons"].get("actions", []):
            action_name = saved_action.get("action")
            if action_name:
                brain.taught_reference['utilities'][action_name] = saved_action.get("utility", 1.0)
                if saved_action.get("weights_nonzero"):
                    dim = saved_action.get("weights_shape", 1376)
                    w = np.zeros(dim)
                    for idx, val in saved_action["weights_nonzero"]:
                        if idx < dim: w[idx] = val
                    brain.taught_reference['weights'][action_name] = w
        brain.taught_reference['loaded'] = True
        print(f"  📖 Taught reference loaded:")
        print(f"     Actions: {list(brain.taught_reference['utilities'].keys())}")
        print(f"     Utilities: {', '.join(f'{k}:{v:.3f}' for k, v in brain.taught_reference['utilities'].items())}")
        print(f"     Weights available: {list(brain.taught_reference['weights'].keys())}")
    except Exception as e:
        print(f"  ⚠️ Error loading taught reference: {e}")


def blend_from_taught(brain, tier):
    if not brain.taught_reference['loaded']: return
    if tier not in brain.BLEND_RATIOS: return
    if brain.timestep - brain.last_blend_timestep < brain.BLEND_COOLDOWN: return

    ai_weight, taught_weight = brain.BLEND_RATIOS[tier]
    blend_weights = (tier == 3)
    blended_actions = []

    for a in brain.actions():
        if a.action not in brain.taught_reference['utilities']: continue
        taught_util = brain.taught_reference['utilities'][a.action]
        old_util = a.utility
        a.utility = ai_weight * a.utility + taught_weight * taught_util
        if taught_util > 1.0: a.utility = max(a.utility, taught_util * 0.5)
        floor = brain.INTERACT_UTILITY_FLOOR if a.group == "interact" else brain.MOVE_UTILITY_FLOOR
        a.utility = max(a.utility, floor)
        a.utility = min(a.utility, 2.0)
        blended_actions.append(f"{a.action}:{old_util:.3f}→{a.utility:.3f}")
        if blend_weights and a.action in brain.taught_reference['weights']:
            taught_w = brain.taught_reference['weights'][a.action]
            if a.weights is not None:
                min_dim = min(len(a.weights), len(taught_w))
                a.weights[:min_dim] = ai_weight * a.weights[:min_dim] + taught_weight * taught_w[:min_dim]

    brain.last_blend_timestep = brain.timestep
    brain.blend_tier = tier
    brain.blend_count += 1
    tier_names = {1: "LIGHT", 2: "MEDIUM", 3: "HARD"}
    print(f"  🔀 BLEND [{tier_names.get(tier, '?')}] ({ai_weight:.0%} AI / {taught_weight:.0%} taught)"
          f" | Blend #{brain.blend_count}")
    for ba in blended_actions: print(f"     {ba}")
    if blend_weights:
        print(f"     + Weights blended for: {list(brain.taught_reference['weights'].keys())}")


# ============================================================================
# MULTI-MODEL TAUGHT DATA LOADING
# ============================================================================

def load_all_taught_models(brain):
    model_paths = get_taught_model_paths()
    if not model_paths:
        print("  📚 No taught model folders found"); return

    brain.taught_model_count = len(model_paths)
    print(f"  📚 Found {brain.taught_model_count} taught models")

    for model_path in model_paths:
        print(f"  📂 Loading {model_path.name}...")
        _merge_taught_transitions(brain, model_path / TAUGHT_TRANSITIONS_FILENAME)
        _merge_battle_transitions(brain, model_path / TAUGHT_BATTLE_TRANSITIONS_FILENAME)
        _merge_bag_transitions(brain, model_path / TAUGHT_BAG_TRANSITIONS_FILENAME)
        _merge_start_menu_transitions(brain, model_path / TAUGHT_START_MENU_TRANSITIONS_FILENAME)
        _merge_taught_exploration(brain, model_path / TAUGHT_EXPLORATION_FILENAME)
        _merge_event_timeline(brain, model_path / TAUGHT_EVENT_TIMELINE_FILENAME)

    _load_primary_nav_targets(brain, model_paths[0] / TAUGHT_NAV_TARGETS_FILENAME)
    for mp in model_paths[1:]:
        _merge_secondary_nav_targets(brain, mp / TAUGHT_NAV_TARGETS_FILENAME)

    best_checkpoint, best_ts = None, -1
    for mp in model_paths:
        cp_path = mp / TAUGHT_MODEL_CHECKPOINT_FILENAME
        if cp_path.exists():
            try:
                with open(cp_path, 'r') as f: cp = json.load(f)
                ts = cp.get('timestep', 0)
                if ts > best_ts: best_ts = ts; best_checkpoint = cp_path
            except Exception: pass

    if best_checkpoint:
        brain.best_taught_checkpoint_path = best_checkpoint
        print(f"  📚 Best checkpoint: {best_checkpoint.parent.name} (ts={best_ts})")

    brain.taught_transitions = brain.all_taught_transitions
    brain.battle_transitions = brain.all_battle_transitions
    brain.battle_sequences = brain.all_battle_sequences
    brain.bag_transitions = brain.all_bag_transitions
    brain.start_menu_transitions = brain.all_start_menu_transitions

    if brain.battle_transitions: brain.battle_loaded = True
    if brain.bag_transitions: brain.bag_loaded = True
    if brain.start_menu_transitions: brain.start_menu_loaded = True

    print(f"  📚 MERGED TOTALS:")
    print(f"     Overworld frames: {len(brain.taught_transitions)} ({len(brain.all_taught_batches)} batches)")
    print(f"     Battle frames: {len(brain.battle_transitions)} ({len(brain.battle_sequences)} sequences)")
    print(f"     Bag frames: {len(brain.bag_transitions)}")
    print(f"     Start menu frames: {len(brain.start_menu_transitions)}")
    print(f"     Nav targets: {sum(len(t) for t in brain.taught_nav_targets.values())} "
          f"across {len(brain.taught_nav_targets)} maps")
    print(f"     Events: {len(brain.event_timeline)}")


# ============================================================================
# MERGE HELPERS
# ============================================================================

def _merge_taught_transitions(brain, filepath):
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f: data = json.load(f)
        batches = data.get('batches', [])
        frames_added = 0
        for batch in batches:
            batch_type = batch.get('batch_type', 'steady')
            trigger_action = batch.get('trigger_action')
            for frame in batch.get('frames', []):
                brain.all_taught_transitions.append({
                    'state': frame.get('state', {}), 'action': frame.get('action'),
                    'recent_actions': frame.get('recent_actions', []),
                    'frame_offset': frame.get('frame_offset', 0),
                    'batch_type': batch_type, 'trigger_action': trigger_action
                })
                frames_added += 1
        brain.all_taught_batches.extend(batches)
        meta = data.get('metadata', {})
        if not brain.taught_metadata: brain.taught_metadata = meta.copy()
        else:
            existing_maps = set(brain.taught_metadata.get('maps_visited', []))
            new_maps = set(meta.get('maps_visited', []))
            brain.taught_metadata['maps_visited'] = sorted(existing_maps | new_maps)
            brain.taught_metadata['action_changes'] = brain.taught_metadata.get('action_changes', 0) + meta.get('action_changes', 0)
        if frames_added > 0: print(f"     OW transitions: +{frames_added} frames ({len(batches)} batches)")
    except Exception as e: print(f"     ⚠️ Error merging OW transitions from {filepath}: {e}")


def _merge_battle_transitions(brain, filepath):
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f: data = json.load(f)
        flat_frames = data.get('flat_frames', [])
        sequences = data.get('battle_sequences', [])
        meta = data.get('metadata', {})
        brain.all_battle_transitions.extend(flat_frames)
        brain.all_battle_sequences.extend(sequences)
        if not brain.battle_metadata: brain.battle_metadata = meta.copy()
        else:
            brain.battle_metadata['total_battle_frames'] = brain.battle_metadata.get('total_battle_frames', 0) + meta.get('total_battle_frames', 0)
            brain.battle_metadata['battles_recorded'] = brain.battle_metadata.get('battles_recorded', 0) + meta.get('battles_recorded', 0)
            existing_outcomes = brain.battle_metadata.get('outcomes', {})
            for k, v in meta.get('outcomes', {}).items(): existing_outcomes[k] = existing_outcomes.get(k, 0) + v
            brain.battle_metadata['outcomes'] = existing_outcomes
        if flat_frames: print(f"     Battle transitions: +{len(flat_frames)} frames ({len(sequences)} sequences)")
    except Exception as e: print(f"     ⚠️ Error merging battle transitions from {filepath}: {e}")


def _merge_bag_transitions(brain, filepath):
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f: data = json.load(f)
        bag_frames = data.get('bag_frames', [])
        meta = data.get('metadata', {})
        brain.all_bag_transitions.extend(bag_frames)
        if not brain.bag_metadata: brain.bag_metadata = meta.copy()
        else:
            brain.bag_metadata['bag_sessions_recorded'] = brain.bag_metadata.get('bag_sessions_recorded', 0) + meta.get('bag_sessions_recorded', 0)
            brain.bag_metadata['items_used'] = sorted(set(brain.bag_metadata.get('items_used', [])) | set(meta.get('items_used', [])))
            brain.bag_metadata['pockets_visited'] = sorted(set(brain.bag_metadata.get('pockets_visited', [])) | set(meta.get('pockets_visited', [])))
        if bag_frames: print(f"     Bag transitions: +{len(bag_frames)} frames")
    except Exception as e: print(f"     ⚠️ Error merging bag transitions from {filepath}: {e}")


def _merge_start_menu_transitions(brain, filepath):
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f: data = json.load(f)
        sm_frames = data.get('start_menu_frames', [])
        meta = data.get('metadata', {})
        brain.all_start_menu_transitions.extend(sm_frames)
        if not brain.start_menu_metadata: brain.start_menu_metadata = meta.copy()
        else:
            brain.start_menu_metadata['sessions_recorded'] = brain.start_menu_metadata.get('sessions_recorded', 0) + meta.get('sessions_recorded', 0)
            existing_targets = brain.start_menu_metadata.get('targets_navigated', {})
            for k, v in meta.get('targets_navigated', {}).items(): existing_targets[k] = existing_targets.get(k, 0) + v
            brain.start_menu_metadata['targets_navigated'] = existing_targets
        if sm_frames: print(f"     Start menu transitions: +{len(sm_frames)} frames")
    except Exception as e: print(f"     ⚠️ Error merging start menu transitions from {filepath}: {e}")


def _merge_taught_exploration(brain, filepath):
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f: taught_data = json.load(f)
        ta, ia = 0, 0
        for map_key, taught_map in taught_data.items():
            map_id = int(map_key.replace('map_', ''))
            ai_map = brain.get_current_map_memory(map_id)
            for tt in taught_map.get('transitions', []):
                tp = tuple(tt['position']); td = tt['direction']
                if not any(tuple(e['position']) == tp and e['direction'] == td for e in ai_map['transitions']):
                    ai_map['transitions'].append(tt); ta += 1
            for ti in taught_map.get('interactable_objects', []):
                if ti not in ai_map['interactable_objects']:
                    ai_map['interactable_objects'].append(ti); ia += 1
            for tile in taught_map.get('visited_tiles', []):
                ai_map['visited_tiles'].add(tuple(tile) if isinstance(tile, list) else tile)
            for obs in taught_map.get('obstructions', []):
                ai_map['obstructions'].add(tuple(obs) if isinstance(obs, list) else obs)
        if ta > 0 or ia > 0: print(f"     Exploration: +{ta} transitions, +{ia} interactables")
    except Exception as e: print(f"     ⚠️ Error merging exploration from {filepath}: {e}")


def _merge_event_timeline(brain, filepath):
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f: data = json.load(f)
        brain.event_timeline.extend(data.get('events', []))
        existing_seg_keys = set((seg.get('from_nav_order', -1), seg.get('to_nav_order', -1)) for seg in brain.event_segments)
        for seg in data.get('segments', []):
            key = (seg.get('from_nav_order', -1), seg.get('to_nav_order', -1))
            if key not in existing_seg_keys: brain.event_segments.append(seg); existing_seg_keys.add(key)
        existing_prep_orders = set(pp.get('before_nav_order', -1) for pp in brain.event_preparation_points)
        for pp in data.get('preparation_points', []):
            order = pp.get('before_nav_order', -1)
            if order not in existing_prep_orders: brain.event_preparation_points.append(pp); existing_prep_orders.add(order)
        new_meta = data.get('metadata', {})
        if not brain.event_timeline_metadata: brain.event_timeline_metadata = new_meta.copy()
        else:
            existing_covered = set(brain.event_timeline_metadata.get('nav_targets_covered', []))
            brain.event_timeline_metadata['nav_targets_covered'] = sorted(existing_covered | set(new_meta.get('nav_targets_covered', [])))
        new_events = data.get('events', [])
        if new_events: print(f"     Event timeline: +{len(new_events)} events")
        brain.event_timeline.sort(key=lambda e: (e.get('nav_target_order', 0), e.get('order', 0)))
        if brain.event_timeline: brain.event_timeline_loaded = True
    except Exception as e: print(f"     ⚠️ Error merging event timeline from {filepath}: {e}")


def _load_primary_nav_targets(brain, filepath):
    try:
        if not Path(filepath).exists():
            print(f"     No primary nav targets at {filepath}"); return
        with open(filepath, 'r') as f: data = json.load(f)
        brain.taught_nav_targets = {}
        for map_key, targets in data.get('targets_by_map', {}).items():
            brain.taught_nav_targets[int(map_key)] = targets
        brain.taught_nav_global_order = data.get('global_order', [])
        brain.taught_nav_loaded = True
        total = sum(len(t) for t in brain.taught_nav_targets.values())
        print(f"     Primary nav targets: {total} across {len(brain.taught_nav_targets)} maps, "
              f"{len(brain.taught_nav_global_order)} global order")
    except Exception as e: print(f"     ⚠️ Error loading primary nav targets from {filepath}: {e}")


def _merge_secondary_nav_targets(brain, filepath):
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f: data = json.load(f)
        existing_positions = set()
        for map_id, targets in brain.taught_nav_targets.items():
            for t in targets: existing_positions.add((map_id, tuple(t.get('position', [0, 0]))))
        max_order = 0
        for t in brain.taught_nav_global_order: max_order = max(max_order, t.get('order', 0))
        for targets in brain.taught_nav_targets.values():
            for t in targets: max_order = max(max_order, t.get('order', 0))
        added, next_order = 0, max_order + 1
        for map_key, targets in data.get('targets_by_map', {}).items():
            map_id = int(map_key)
            for t in targets:
                pos = tuple(t.get('position', [0, 0]))
                if (map_id, pos) not in existing_positions:
                    new_target = t.copy(); new_target['order'] = next_order; new_target['source'] = 'secondary'
                    if map_id not in brain.taught_nav_targets: brain.taught_nav_targets[map_id] = []
                    brain.taught_nav_targets[map_id].append(new_target)
                    brain.taught_nav_global_order.append({'order': next_order, 'map_id': map_id, 'position': list(pos)})
                    existing_positions.add((map_id, pos)); next_order += 1; added += 1
        if added > 0:
            brain.taught_nav_global_order.sort(key=lambda x: x.get('order', 0))
            print(f"     Secondary nav targets: +{added} new positions")
    except Exception as e: print(f"     ⚠️ Error merging secondary nav targets from {filepath}: {e}")


# ============================================================================
# OVERWORLD MARKOV
# ============================================================================

def load_taught_transitions(brain, filepath):
    try:
        if not Path(filepath).exists():
            brain.taught_transitions = []; brain.taught_batches = []; brain.taught_metadata = {}
            print(f"  No taught transitions file found at {filepath}"); return
        with open(filepath, 'r') as f: data = json.load(f)
        brain.taught_transitions = []; brain.taught_batches = data.get('batches', [])
        for batch in brain.taught_batches:
            bt = batch.get('batch_type', 'steady'); ta = batch.get('trigger_action')
            for frame in batch.get('frames', []):
                brain.taught_transitions.append({
                    'state': frame.get('state', {}), 'action': frame.get('action'),
                    'recent_actions': frame.get('recent_actions', []),
                    'frame_offset': frame.get('frame_offset', 0), 'batch_type': bt, 'trigger_action': ta
                })
        brain.taught_metadata = data.get('metadata', {})
        print(f"  📚 Loaded taught transitions: {len(brain.taught_batches)} batches, {len(brain.taught_transitions)} frames")
    except Exception as e:
        print(f"  Error loading taught transitions: {e}")
        brain.taught_transitions = []; brain.taught_batches = []; brain.taught_metadata = {}


def extract_partial_context(brain, context_state, raw_position=None):
    raw_x = raw_position[0] if raw_position else int(context_state[0] * 255)
    raw_y = raw_position[1] if raw_position else int(context_state[1] * 255)
    current_map = int(context_state[2])
    movement_blocked = brain.get_position_stagnation() > 3
    near_transition = False
    memory = brain.get_current_map_memory(current_map)
    for t in memory.get('transitions', []):
        t_pos = tuple(t['position']) if isinstance(t['position'], list) else t['position']
        if abs(raw_x - t_pos[0]) + abs(raw_y - t_pos[1]) <= 2: near_transition = True; break
    tile_probed = not brain.should_interact_at_tile(raw_x, raw_y, current_map)
    return {'in_battle': context_state[3] > 0.5, 'in_menu': context_state[4] > 0.5,
            'movement_blocked': movement_blocked, 'near_transition': near_transition, 'tile_probed': tile_probed}


def compute_markov_similarity(brain, context_state, raw_position=None, taught_frames=None):
    frames = taught_frames if taught_frames is not None else brain.taught_transitions
    skip_map_check = taught_frames is not None
    if not frames: return 0.0, None, -1

    raw_x = raw_position[0] if raw_position else int(context_state[0] * 255)
    raw_y = raw_position[1] if raw_position else int(context_state[1] * 255)
    current_map = int(context_state[2]); current_dir = int(context_state[5])
    in_battle = context_state[3] > 0.5; in_menu = context_state[4] > 0.5
    current_actions = list(brain.action_history)
    current_partial = extract_partial_context(brain, context_state, raw_position)

    best_score, best_action, best_idx = 0.0, None, -1
    for idx, transition in enumerate(frames):
        t_state = transition.get('state', {}); t_action = transition.get('action')
        t_recent = transition.get('recent_actions', []); batch_type = transition.get('batch_type', 'steady')
        if not t_action or t_action == "NONE": continue

        immediate_score = 0.0
        if not skip_map_check:
            if t_state.get('map_id') != current_map: continue
        immediate_score += 0.25
        t_x, t_y = t_state.get('x', 0), t_state.get('y', 0)
        pos_dist = abs(raw_x - t_x) + abs(raw_y - t_y)
        if pos_dist == 0: immediate_score += MARKOV_POS_EXACT_BONUS
        elif pos_dist <= 2: immediate_score += MARKOV_POS_NEAR_BONUS
        elif pos_dist <= MARKOV_POS_MAX_DIST: immediate_score += MARKOV_POS_FAR_BONUS
        else: continue
        if t_state.get('direction') == current_dir: immediate_score += 0.2
        t_in_battle = t_state.get('in_battle', 0) == 1; t_in_menu = t_state.get('in_menu', 0) == 1
        if t_in_battle == in_battle: immediate_score += 0.1
        if t_in_menu == in_menu: immediate_score += 0.1

        sequential_score = 0.0
        if t_recent and current_actions:
            if len(current_actions) >= 8 and len(t_recent) >= 8 and list(current_actions)[-8:] == t_recent[-8:]: sequential_score = MARKOV_SEQ_FULL_WEIGHT
            if sequential_score < MARKOV_SEQ_MEDIUM_WEIGHT and len(current_actions) >= 5 and len(t_recent) >= 5 and list(current_actions)[-5:] == t_recent[-5:]: sequential_score = MARKOV_SEQ_MEDIUM_WEIGHT
            if sequential_score < MARKOV_SEQ_SHORT_WEIGHT and len(current_actions) >= 3 and len(t_recent) >= 3 and list(current_actions)[-3:] == t_recent[-3:]: sequential_score = MARKOV_SEQ_SHORT_WEIGHT

        partial_score = 0.0; pm = 0
        if t_in_battle == current_partial['in_battle']: pm += 1
        if t_in_menu == current_partial['in_menu']: pm += 1
        partial_score = pm / 2

        total_score = MARKOV_IMMEDIATE_WEIGHT * immediate_score + MARKOV_SEQUENTIAL_WEIGHT * sequential_score + MARKOV_PARTIAL_WEIGHT * partial_score
        if batch_type == "action_change": total_score *= 1.2
        if transition.get('frame_offset', 0) == 0: total_score *= 1.1
        if total_score > best_score: best_score = total_score; best_action = t_action; best_idx = idx

    return best_score, best_action, best_idx


def get_markov_action(brain, context_state, raw_position=None, taught_frames=None):
    if not brain.markov_enabled: return False, None, 0.0
    frames = taught_frames if taught_frames is not None else brain.taught_transitions
    if not frames: return False, None, 0.0
    score, action, idx = compute_markov_similarity(brain, context_state, raw_position, taught_frames=frames)
    brain.last_markov_score = score
    if score >= MARKOV_FAMILIARITY_THRESHOLD:
        brain.last_markov_action = action; return True, action, score
    return False, None, score


# ============================================================================
# BATTLE MARKOV
# ============================================================================

def load_taught_battle_transitions(brain, filepath):
    try:
        if not Path(filepath).exists():
            brain.battle_transitions = []; brain.battle_sequences = []; brain.battle_metadata = {}; brain.battle_loaded = False
            print(f"  ⚔️ No battle transitions file found at {filepath}"); return
        with open(filepath, 'r') as f: data = json.load(f)
        brain.battle_transitions = data.get('flat_frames', []); brain.battle_sequences = data.get('battle_sequences', [])
        brain.battle_metadata = data.get('metadata', {}); brain.battle_loaded = True
        print(f"  ⚔️ Loaded battle transitions: {len(brain.battle_transitions)} frames, {len(brain.battle_sequences)} sequences")
    except Exception as e:
        print(f"  ⚠️ Error loading battle transitions: {e}")
        brain.battle_transitions = []; brain.battle_sequences = []; brain.battle_metadata = {}; brain.battle_loaded = False


def compute_battle_markov_similarity(brain, context_state, palette_state=None):
    if not brain.battle_transitions: return 0.0, None, -1
    current_actions = list(brain.battle_action_history); in_menu = context_state[4] > 0.5
    best_score, best_action, best_idx = 0.0, None, -1

    for idx, frame in enumerate(brain.battle_transitions):
        t_action = frame.get('action'); t_recent = frame.get('recent_actions', [])
        t_state = frame.get('state', {}); batch_type = frame.get('batch_type', 'steady')
        if not t_action or t_action == "NONE": continue

        seq_score = 0.0
        if t_recent and current_actions:
            if len(current_actions) >= 8 and len(t_recent) >= 8 and list(current_actions)[-8:] == t_recent[-8:]: seq_score = 1.0
            if seq_score < 0.6 and len(current_actions) >= 5 and len(t_recent) >= 5 and list(current_actions)[-5:] == t_recent[-5:]: seq_score = 0.6
            if seq_score < 0.3 and len(current_actions) >= 3 and len(t_recent) >= 3 and list(current_actions)[-3:] == t_recent[-3:]: seq_score = 0.3

        palette_score = 0.0
        if palette_state is not None and 'palette_snapshot' in frame:
            t_palette = np.array(frame['palette_snapshot'], dtype=float)
            if len(t_palette) > 0 and len(palette_state) > 0:
                min_dim = min(len(t_palette), len(palette_state))
                diff = np.linalg.norm(t_palette[:min_dim] - palette_state[:min_dim])
                palette_score = 1.0 / (1.0 + diff * 0.01)
        else: palette_score = 0.5

        menu_score = 1.0 if (t_state.get('in_menu', 0) == 1) == in_menu else 0.0
        total_score = BATTLE_MARKOV_ACTION_SEQ_WEIGHT * seq_score + BATTLE_MARKOV_PALETTE_WEIGHT * palette_score + BATTLE_MARKOV_MENU_STATE_WEIGHT * menu_score
        if batch_type == "action_change": total_score *= 1.15
        if frame.get('frame_offset', 0) == 0: total_score *= 1.1
        if total_score > best_score: best_score = total_score; best_action = t_action; best_idx = idx

    return best_score, best_action, best_idx


def get_battle_markov_action(brain, context_state, palette_state=None):
    if not brain.battle_loaded or not brain.battle_transitions: return False, None, 0.0
    score, action, idx = compute_battle_markov_similarity(brain, context_state, palette_state)
    brain.last_battle_markov_score = score
    threshold = BATTLE_MARKOV_THRESHOLD_HIGH if len(brain.battle_transitions) > 200 else BATTLE_MARKOV_THRESHOLD_LOW
    if score >= threshold and action:
        brain.last_battle_markov_action = action; return True, action, score
    return False, None, score


# ============================================================================
# BAG MARKOV
# ============================================================================

def load_taught_bag_transitions(brain, filepath):
    try:
        if not Path(filepath).exists():
            brain.bag_transitions = []; brain.bag_metadata = {}; brain.bag_loaded = False
            print(f"  🎒 No bag transitions file found at {filepath}"); return
        with open(filepath, 'r') as f: data = json.load(f)
        brain.bag_transitions = data.get('bag_frames', []); brain.bag_metadata = data.get('metadata', {}); brain.bag_loaded = True
        print(f"  🎒 Loaded bag transitions: {len(brain.bag_transitions)} frames")
    except Exception as e:
        print(f"  ⚠️ Error loading bag transitions: {e}")
        brain.bag_transitions = []; brain.bag_metadata = {}; brain.bag_loaded = False


def compute_bag_markov_similarity(brain):
    if not brain.bag_transitions: return 0.0, None, -1
    bgd = brain.bag_data; md = brain.menu_data
    in_battle = brain.battle_data.get('battle_cursor', -1) != -1
    current_pocket = bgd.get('pocket', -1); current_cursor = bgd.get('cursor', -1)
    current_item_id = brain.get_item_at_cursor(); current_mc = md.get('mc', -1)
    from brain_systems import get_lowest_hp_ratio, has_status_condition_in_party
    lowest_hp = get_lowest_hp_ratio(brain); has_status = has_status_condition_in_party(brain)
    party_count = brain.party_data.get('count', 0)
    current_actions = list(brain.bag_action_history)
    best_score, best_action, best_idx = 0.0, None, -1

    for idx, frame in enumerate(brain.bag_transitions):
        t_action = frame.get('action'); t_state = frame.get('state', {})
        t_recent = frame.get('recent_actions', []); t_party = frame.get('party_context', {})
        batch_type = frame.get('batch_type', 'steady')
        if not t_action or t_action == "NONE": continue

        menu_matches = 0
        if t_state.get('pocket', -1) == current_pocket and current_pocket >= 0: menu_matches += 1
        t_cursor = t_state.get('cursor', -1)
        if t_cursor >= 0 and current_cursor >= 0:
            cd = abs(t_cursor - current_cursor)
            menu_matches += 1 if cd == 0 else (0.5 if cd == 1 else 0)
        if t_state.get('item_id', -1) > 0 and t_state.get('item_id', -1) == current_item_id: menu_matches += 1
        if t_state.get('mc', -1) >= 0 and t_state.get('mc', -1) == current_mc: menu_matches += 1
        if t_state.get('in_battle', False) == in_battle: menu_matches += 1
        if menu_matches < 1.0: continue
        menu_score = menu_matches / 5

        seq_score = 0.0
        if t_recent and current_actions:
            if len(current_actions) >= 6 and len(t_recent) >= 6 and list(current_actions)[-6:] == t_recent[-6:]: seq_score = 1.0
            if seq_score < 0.6 and len(current_actions) >= 4 and len(t_recent) >= 4 and list(current_actions)[-4:] == t_recent[-4:]: seq_score = 0.6
            if seq_score < 0.3 and len(current_actions) >= 2 and len(t_recent) >= 2 and list(current_actions)[-2:] == t_recent[-2:]: seq_score = 0.3

        party_matches = 0
        t_lowest_hp = t_party.get('lowest_hp_ratio', 1.0)
        if t_lowest_hp < 1.0 or lowest_hp < 1.0:
            hd = abs(t_lowest_hp - lowest_hp)
            party_matches += 1 if hd < 0.15 else (0.5 if hd < 0.3 else 0)
            if t_lowest_hp < 0.3 and lowest_hp < 0.3: party_matches += 0.5
        else: party_matches += 1
        if t_party.get('has_status', False) == has_status: party_matches += 1
        t_pc = t_party.get('party_count', 0)
        if t_pc > 0: party_matches += 1 if t_pc == party_count else 0.5
        party_score = party_matches / 3

        total_score = BAG_MARKOV_MENU_STATE_WEIGHT * menu_score + BAG_MARKOV_ACTION_SEQ_WEIGHT * seq_score + BAG_MARKOV_PARTY_CONTEXT_WEIGHT * party_score
        if batch_type == "action_change": total_score *= 1.2
        if frame.get('frame_offset', 0) == 0: total_score *= 1.1
        if total_score > best_score: best_score = total_score; best_action = t_action; best_idx = idx

    return best_score, best_action, best_idx


def get_bag_markov_action(brain):
    if not brain.bag_loaded or not brain.bag_transitions: return False, None, 0.0
    score, action, idx = compute_bag_markov_similarity(brain)
    brain.last_bag_markov_score = score
    if score >= BAG_MARKOV_THRESHOLD and action:
        brain.last_bag_markov_action = action; return True, action, score
    return False, None, score


# ============================================================================
# START MENU MARKOV
# ============================================================================

def load_taught_start_menu_transitions(brain, filepath):
    try:
        if not Path(filepath).exists():
            brain.start_menu_transitions = []; brain.start_menu_metadata = {}; brain.start_menu_loaded = False
            print(f"  📋 No start menu transitions file found at {filepath}"); return
        with open(filepath, 'r') as f: data = json.load(f)
        brain.start_menu_transitions = data.get('start_menu_frames', []); brain.start_menu_metadata = data.get('metadata', {}); brain.start_menu_loaded = True
        print(f"  📋 Loaded start menu transitions: {len(brain.start_menu_transitions)} frames")
    except Exception as e:
        print(f"  ⚠️ Error loading start menu transitions: {e}")
        brain.start_menu_transitions = []; brain.start_menu_metadata = {}; brain.start_menu_loaded = False


def compute_start_menu_markov_similarity(brain):
    if not brain.start_menu_transitions: return 0.0, None, -1
    md = brain.menu_data; current_mc = md.get('mc', -1); current_mm = md.get('mm', -1); current_pc = md.get('pc', -1)
    target_mc = brain.start_menu_target_mc
    from brain_systems import get_lowest_hp_ratio, has_status_condition_in_party
    lowest_hp = get_lowest_hp_ratio(brain); has_status = has_status_condition_in_party(brain)
    in_battle = brain.battle_data.get('battle_cursor', -1) != -1
    current_actions = list(brain.start_menu_action_history)
    best_score, best_action, best_idx = 0.0, None, -1

    for idx, frame in enumerate(brain.start_menu_transitions):
        t_action = frame.get('action'); t_state = frame.get('state', {}); t_recent = frame.get('recent_actions', [])
        t_context = frame.get('context', {}); batch_type = frame.get('batch_type', 'steady')
        if not t_action or t_action == "NONE": continue

        menu_matches = 0
        t_mc = t_state.get('mc', -1)
        if t_mc >= 0 and current_mc >= 0:
            menu_matches += 1 if t_mc == current_mc else (0.5 if abs(t_mc - current_mc) == 1 else 0)
        t_target_mc = t_context.get('target_mc', -1)
        if t_target_mc >= 0 and target_mc >= 0:
            if t_target_mc == target_mc: menu_matches += 1
            if t_mc >= 0 and current_mc >= 0 and min(current_mc, target_mc) <= t_mc <= max(current_mc, target_mc): menu_matches += 0.3
        elif target_mc < 0: menu_matches += 0.5
        if t_state.get('mm', -1) >= 4 and current_mm >= 4: menu_matches += 1
        t_pc = t_state.get('pc', -1)
        if t_pc < 0 and current_pc < 0: menu_matches += 1
        elif t_pc >= 0 and current_pc >= 0: menu_matches += 0.5
        if menu_matches < 1.0: continue
        menu_score = menu_matches / 4

        seq_score = 0.0
        if t_recent and current_actions:
            if len(current_actions) >= 5 and len(t_recent) >= 5 and list(current_actions)[-5:] == t_recent[-5:]: seq_score = 1.0
            if seq_score < 0.6 and len(current_actions) >= 3 and len(t_recent) >= 3 and list(current_actions)[-3:] == t_recent[-3:]: seq_score = 0.6
            if seq_score < 0.3 and len(current_actions) >= 2 and len(t_recent) >= 2 and list(current_actions)[-2:] == t_recent[-2:]: seq_score = 0.3

        context_matches = 0
        t_target = t_context.get('target', '')
        if brain.start_menu_context == "preparation" and t_target == "bag": context_matches += 1
        elif brain.start_menu_context == t_target: context_matches += 1
        elif brain.start_menu_context == "unknown": context_matches += 0.5
        hd = abs(t_context.get('party_hp_lowest', 1.0) - lowest_hp)
        context_matches += 1 if hd < 0.2 else (0.5 if hd < 0.4 else 0)
        if t_context.get('in_battle', False) == in_battle: context_matches += 1
        context_score = context_matches / 3

        total_score = START_MENU_MARKOV_MENU_STATE_WEIGHT * menu_score + START_MENU_MARKOV_ACTION_SEQ_WEIGHT * seq_score + START_MENU_MARKOV_CONTEXT_WEIGHT * context_score
        if batch_type == "action_change": total_score *= 1.2
        if frame.get('frame_offset', 0) == 0: total_score *= 1.1
        if total_score > best_score: best_score = total_score; best_action = t_action; best_idx = idx

    return best_score, best_action, best_idx


def get_start_menu_markov_action(brain):
    if not brain.start_menu_loaded or not brain.start_menu_transitions: return False, None, 0.0
    score, action, idx = compute_start_menu_markov_similarity(brain)
    brain.last_start_menu_markov_score = score
    if score >= START_MENU_MARKOV_THRESHOLD and action:
        brain.last_start_menu_markov_action = action; return True, action, score
    return False, None, score


# ============================================================================
# NAV TARGETS (standalone load — legacy/fallback)
# ============================================================================

def load_taught_nav_targets(brain, filepath):
    try:
        if not Path(filepath).exists():
            brain.taught_nav_targets = {}; brain.taught_nav_global_order = []; brain.taught_nav_loaded = False
            print(f"  No taught nav targets found at {filepath}"); return
        with open(filepath, 'r') as f: data = json.load(f)
        brain.taught_nav_targets = {}
        for map_key, targets in data.get('targets_by_map', {}).items():
            brain.taught_nav_targets[int(map_key)] = targets
        brain.taught_nav_global_order = data.get('global_order', [])
        brain.taught_nav_loaded = True
        total = sum(len(t) for t in brain.taught_nav_targets.values())
        print(f"  🎯 Loaded taught nav targets: {total} across {len(brain.taught_nav_targets)} maps")
    except Exception as e:
        print(f"  Error loading taught nav targets: {e}")
        brain.taught_nav_targets = {}; brain.taught_nav_global_order = []; brain.taught_nav_loaded = False


# ============================================================================
# ATTACH ALL METHODS TO BRAIN CLASS
# ============================================================================

def attach_to_brain(BrainClass):
    """Attach all markov functions as methods on the Brain class."""
    # Taught reference + blend
    BrainClass.load_taught_reference = load_taught_reference
    BrainClass.blend_from_taught = blend_from_taught

    # Multi-model loading
    BrainClass.load_all_taught_models = load_all_taught_models

    # Overworld Markov
    BrainClass.load_taught_transitions = load_taught_transitions
    BrainClass.extract_partial_context = extract_partial_context
    BrainClass.compute_markov_similarity = compute_markov_similarity
    BrainClass.get_markov_action = get_markov_action

    # Battle Markov
    BrainClass.load_taught_battle_transitions = load_taught_battle_transitions
    BrainClass.compute_battle_markov_similarity = compute_battle_markov_similarity
    BrainClass.get_battle_markov_action = get_battle_markov_action

    # Bag Markov
    BrainClass.load_taught_bag_transitions = load_taught_bag_transitions
    BrainClass.compute_bag_markov_similarity = compute_bag_markov_similarity
    BrainClass.get_bag_markov_action = get_bag_markov_action

    # Start Menu Markov
    BrainClass.load_taught_start_menu_transitions = load_taught_start_menu_transitions
    BrainClass.compute_start_menu_markov_similarity = compute_start_menu_markov_similarity
    BrainClass.get_start_menu_markov_action = get_start_menu_markov_action

    # Nav targets
    BrainClass.load_taught_nav_targets = load_taught_nav_targets