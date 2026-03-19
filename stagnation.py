# ============================================================================
# stagnation.py — Stagnation, Blend Triggers, Mode Swap, Repetition/Pattern,
#                  Exploration Tracking (Cell 3.5)
# ============================================================================
# All methods take `brain` as first argument. Attached via attach_to_brain().
#
# Contains:
#   - Bounding rectangle debt tracking
#   - Blend tier detection + try_blend_if_needed
#   - State stagnation + context hash
#   - Force random action decision
#   - Direction change progress
#   - Stagnation initiator penalty
#   - Productive change detection + on_productive_change
#   - Mode swap logic (move/interact/both)
#   - Exploration tracking (update per step, on_map_change)
#   - Repetition tracking (consecutive action, learning multiplier)
#   - Pattern detection + penalty
# ============================================================================

import random
import numpy as np


# ============================================================================
# BOUNDING RECTANGLE DEBT
# ============================================================================

def update_bounding_rect_tracking(brain, raw_position):
    if raw_position is not None:
        brain.recent_movement_positions.append(raw_position)


def compute_bounding_rect_debt(brain):
    positions = list(brain.recent_movement_positions)
    n = len(positions)
    if n < brain.BOUNDING_RECT_STAGNATION_THRESHOLD:
        return brain.bounding_rect_debt

    xs = [p[0] for p in positions]; ys = [p[1] for p in positions]
    min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
    width = max(1, max_x - min_x + 1); height = max(1, max_y - min_y + 1)
    area = width * height
    density = n / area

    if area < 25 and density > 2.0:
        increment = brain.BOUNDING_RECT_DEBT_INCREMENT * (density / 2.0)
        brain.bounding_rect_debt = min(brain.BOUNDING_RECT_DEBT_MAX, brain.bounding_rect_debt + increment)
    elif area < 50 and density > 3.0:
        increment = brain.BOUNDING_RECT_DEBT_INCREMENT * 0.5
        brain.bounding_rect_debt = min(brain.BOUNDING_RECT_DEBT_MAX, brain.bounding_rect_debt + increment)
    else:
        brain.bounding_rect_debt = max(0.0, brain.bounding_rect_debt - 0.1)

    return brain.bounding_rect_debt


def get_bounding_rect_info(brain):
    positions = list(brain.recent_movement_positions)
    n = len(positions)
    if n < 10: return {'positions': n, 'debt': brain.bounding_rect_debt}
    xs = [p[0] for p in positions]; ys = [p[1] for p in positions]
    min_x, max_x = min(xs), max(xs); min_y, max_y = min(ys), max(ys)
    width = max(1, max_x - min_x + 1); height = max(1, max_y - min_y + 1)
    area = width * height
    return {
        'positions': n, 'unique': len(set(positions)), 'area': area,
        'width': width, 'height': height,
        'density': n / area if area > 0 else 0, 'debt': brain.bounding_rect_debt,
    }


# ============================================================================
# BLEND TIER DETECTION
# ============================================================================

def get_blend_tier(brain):
    t3 = brain.BLEND_TIER_TRIGGERS[3]
    if brain.detected_pattern and brain.pattern_repeat_count >= t3['pattern_repeats']: return 3
    if brain.state_stagnation_count >= brain.STATE_STAGNATION_THRESHOLD * t3['state_stagnation_mult']: return 3

    t2 = brain.BLEND_TIER_TRIGGERS[2]
    if brain.detected_pattern and brain.pattern_repeat_count >= t2['pattern_repeats']: return 2
    if brain.get_position_stagnation() >= t2['pos_stagnation']: return 2
    if brain.consecutive_action_count >= t2['consecutive']: return 2
    if brain.bounding_rect_debt >= brain.BOUNDING_RECT_DEBT_MAX * 0.7: return 2

    t1 = brain.BLEND_TIER_TRIGGERS[1]
    if brain.detected_pattern and brain.pattern_repeat_count >= t1['pattern_repeats']: return 1
    if brain.get_position_stagnation() >= t1['pos_stagnation']: return 1
    if brain.consecutive_action_count >= t1['consecutive']: return 1
    if brain.bounding_rect_debt >= brain.BOUNDING_RECT_DEBT_MAX * 0.4: return 1

    return 0


def try_blend_if_needed(brain):
    if not brain.taught_reference['loaded']: return False
    tier = get_blend_tier(brain)
    if tier == 0: return False
    if tier <= brain.blend_tier and (brain.timestep - brain.last_blend_timestep) < brain.BLEND_COOLDOWN:
        return False
    brain.blend_from_taught(tier)
    return True


# ============================================================================
# MODE SWAP & STAGNATION
# ============================================================================

def get_context_state_hash(brain, context_state):
    return (round(context_state[0], 2), round(context_state[1], 2), int(context_state[2]),
            int(context_state[3]), round(context_state[4], 2), int(context_state[5]))


def check_state_stagnation(brain, context_state):
    current_hash = get_context_state_hash(brain, context_state)
    if current_hash == brain.last_context_state_hash:
        brain.state_stagnation_count += 1
        if brain.state_stagnation_count == 1 and brain.last_action:
            brain.stagnation_initiator_action = brain.last_action
    else:
        brain.state_stagnation_count = 0
        brain.stagnation_initiator_action = None
    brain.last_context_state_hash = current_hash
    compute_bounding_rect_debt(brain)
    return brain.state_stagnation_count >= brain.STATE_STAGNATION_THRESHOLD


def check_position_stagnation(brain):
    return brain.get_position_stagnation()


def should_force_random(brain):
    force = False
    if brain.get_position_stagnation() >= 8: force = True
    if brain.consecutive_action_count >= 15: force = True
    if brain.detected_pattern and brain.pattern_repeat_count >= 4: force = True
    if brain.state_stagnation_count >= brain.STATE_STAGNATION_THRESHOLD * 2: force = True
    if brain.bounding_rect_debt >= brain.BOUNDING_RECT_DEBT_MAX * 0.9: force = True
    if force: try_blend_if_needed(brain)
    return force


def get_forced_random_action_name(brain):
    candidates = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B"]
    if brain.current_repeated_action and brain.current_repeated_action in candidates:
        candidates.remove(brain.current_repeated_action)
    if brain.detected_pattern:
        for a in brain.detected_pattern:
            if a in candidates: candidates.remove(a)
    if not candidates:
        candidates = ["UP", "DOWN", "LEFT", "RIGHT"]
        if brain.current_repeated_action in candidates:
            candidates.remove(brain.current_repeated_action)
    if not candidates: candidates = ["UP", "DOWN", "LEFT", "RIGHT"]
    return random.choice(candidates)


def check_direction_change_progress(brain, context_state):
    current_dir = int(context_state[5])
    if brain.last_direction_for_progress is None:
        brain.last_direction_for_progress = current_dir; return False
    changed = current_dir != brain.last_direction_for_progress
    brain.last_direction_for_progress = current_dir
    return changed


def apply_stagnation_initiator_penalty(brain):
    if brain.stagnation_initiator_action is None: return
    for a in brain.actions():
        if a.action == brain.stagnation_initiator_action:
            old_util = a.utility
            floor = brain.INTERACT_UTILITY_FLOOR if a.group == "interact" else brain.MOVE_UTILITY_FLOOR
            a.utility = max(floor, a.utility * 0.5)
            print(f"  📍 STAGNATION PENALTY: {brain.stagnation_initiator_action} {old_util:.3f} → {a.utility:.3f}")
            break
    brain.stagnation_initiator_action = None


def check_productive_change(brain, context_state):
    current_map = int(context_state[2])
    current_battle = context_state[3] > 0.5
    current_pos = (context_state[0], context_state[1])
    productive, reason = False, ""
    if brain.last_map_id is not None and current_map != brain.last_map_id:
        productive, reason = True, "map change"
    if brain.last_battle_state is not None and current_battle != brain.last_battle_state:
        productive, reason = True, "battle change"
    if brain.position_at_mode_swap is not None:
        dist = np.sqrt((current_pos[0] - brain.position_at_mode_swap[0])**2 +
                      (current_pos[1] - brain.position_at_mode_swap[1])**2)
        if dist > 0.03: productive, reason = True, f"moved {dist*255:.1f} tiles"
    if brain.direction_change_counts_as_progress and check_direction_change_progress(brain, context_state):
        brain.state_stagnation_count = max(0, brain.state_stagnation_count - 5)
    brain.last_map_id = current_map; brain.last_battle_state = current_battle
    return productive, reason


def on_productive_change(brain, reason):
    brain.move_to_interact_threshold = brain.DEFAULT_MOVE_TO_INTERACT_THRESHOLD
    brain.interact_to_move_threshold = brain.DEFAULT_INTERACT_TO_MOVE_THRESHOLD
    brain.swap_chain_count = 0; brain.state_stagnation_count = 0
    brain.stagnation_initiator_action = None; brain.unproductive_swap_count = 0
    if brain.blend_tier > 0:
        print(f"  ✅ Blend tier reset: {brain.blend_tier} → 0 ({reason})")
        brain.blend_tier = 0
    brain.bounding_rect_debt = max(0.0, brain.bounding_rect_debt - 2.0)


def on_mode_swap(brain, from_mode, to_mode):
    brain.swap_chain_count += 1; brain.frames_in_current_mode = 0
    brain.unproductive_swap_count += 1
    if brain.unproductive_swap_count >= brain.UNPRODUCTIVE_SWAP_THRESHOLD:
        _reset_highest_to_third(brain, to_mode); brain.unproductive_swap_count = 0
    if to_mode == "interact":
        brain.interact_to_move_threshold = min(brain.MAX_THRESHOLD, brain.interact_to_move_threshold + brain.THRESHOLD_INCREMENT)
    else:
        brain.move_to_interact_threshold = min(brain.MAX_THRESHOLD, brain.move_to_interact_threshold + brain.THRESHOLD_INCREMENT)


def _reset_highest_to_third(brain, mode):
    if mode in ["battle", "both"]: return
    group = "move" if mode == "move" else "interact"
    group_actions = [a for a in brain.actions() if a.group == group]
    if len(group_actions) < 3: return
    sorted_actions = sorted(group_actions, key=lambda a: a.utility, reverse=True)
    floor = brain.INTERACT_UTILITY_FLOOR if group == "interact" else brain.MOVE_UTILITY_FLOOR
    sorted_actions[0].utility = max(sorted_actions[2].utility * 0.9, floor)


def should_use_both_mode(brain):
    return (brain.state_stagnation_count > brain.BOTH_MODE_STAGNATION_THRESHOLD or
            brain.unproductive_swap_count > brain.BOTH_MODE_SWAP_THRESHOLD)


def determine_control_mode(brain, context_state, raw_position=None):
    if context_state[3] > 0.5: return "battle"
    brain.frames_in_current_mode += 1
    position_stagnation = brain.get_position_stagnation()

    productive, reason = check_productive_change(brain, context_state)
    if productive: on_productive_change(brain, reason)
    if should_use_both_mode(brain): return "both"

    if check_state_stagnation(brain, context_state):
        apply_stagnation_initiator_penalty(brain)
        new_mode = "interact" if brain.control_mode == "move" else "move"
        brain.control_mode = new_mode
        brain.position_at_mode_swap = (context_state[0], context_state[1])
        on_mode_swap(brain, brain.control_mode, new_mode)
        brain.state_stagnation_count = 0
        return brain.control_mode

    raw_x = raw_position[0] if raw_position else int(context_state[0] * 255)
    raw_y = raw_position[1] if raw_position else int(context_state[1] * 255)
    current_map = int(context_state[2])

    tile_needs_probing = brain.should_interact_at_tile(raw_x, raw_y, current_map)
    untried_directions = brain.get_untried_directions(raw_x, raw_y, current_map)

    if tile_needs_probing and untried_directions and brain.control_mode == "move" and brain.frames_in_current_mode >= 3:
        brain.control_mode = "interact"
        brain.position_at_mode_swap = (context_state[0], context_state[1])
        brain.frames_in_current_mode = 0
        return brain.control_mode

    if brain.control_mode == "move" and position_stagnation >= brain.move_to_interact_threshold:
        brain.control_mode = "interact"
        brain.position_at_mode_swap = (context_state[0], context_state[1])
        on_mode_swap(brain, "move", "interact")
    elif brain.control_mode == "interact":
        if (not tile_needs_probing or not untried_directions) and brain.frames_in_current_mode >= 5:
            brain.control_mode = "move"
            brain.position_at_mode_swap = (context_state[0], context_state[1])
            brain.frames_in_current_mode = 0
        elif brain.frames_in_current_mode >= brain.interact_to_move_threshold:
            brain.control_mode = "move"
            brain.position_at_mode_swap = (context_state[0], context_state[1])
            on_mode_swap(brain, "interact", "move")

    return brain.control_mode


# ============================================================================
# EXPLORATION TRACKING
# ============================================================================

def update_exploration_tracking(brain, context_state, prev_context_state, raw_position=None, prev_raw_position=None):
    current_map = int(context_state[2])
    raw_x = raw_position[0] if raw_position else int(context_state[0] * 255)
    raw_y = raw_position[1] if raw_position else int(context_state[1] * 255)
    current_pos = (raw_x, raw_y)

    if brain.current_map_id is not None and current_map != brain.current_map_id:
        prev_map = brain.current_map_id
        if prev_context_state is not None and prev_raw_position is not None:
            brain.record_transition(prev_raw_position, prev_map, current_map,
                int(prev_context_state[5]), 'interact' if brain.last_action == 'A' else 'walk')
        if prev_raw_position is not None:
            entry_dir = int(context_state[5]) if prev_context_state is not None else 0
            brain.create_transition_ban(current_map, current_pos, (entry_dir + 2) % 4)
        on_map_change(brain, current_map)

    brain.current_map_id = current_map
    brain.record_visited_tile(raw_x, raw_y, current_map)
    brain.accumulate_temp_debt(current_map)
    brain.update_transition_ban(current_map, current_pos)
    brain.check_ban_lift_conditions(current_map)

    if prev_context_state is not None and prev_raw_position is not None:
        brain.detect_obstruction(prev_context_state, context_state, raw_position, prev_raw_position)

    brain.check_interaction_verification(context_state, prev_context_state)
    brain.last_direction = int(context_state[5])

    update_bounding_rect_tracking(brain, raw_position)

    if brain.timestep % 300 == 0:
        brain.decay_all_debts()


def on_map_change(brain, new_map):
    brain.save_exploration_memory()
    brain.control_mode = "move"; brain.frames_in_current_mode = 0

    if brain.nav_active:
        brain.abort_navigation("map changed")
    brain.nav_struck_targets.clear()
    brain.nav_struck_tile_counts.clear()

    brain.recent_movement_positions.clear()
    brain.bounding_rect_debt = max(0.0, brain.bounding_rect_debt - 3.0)

    memory = brain.get_current_map_memory(new_map)
    tile_interactions = memory.get('tile_interactions', {})
    print(f"  🗺️ MAP CHANGE → {new_map}: {len(memory['visited_tiles'])} visited, {len(memory['obstructions'])} obs")
    print(f"     Tiles probed: {len(tile_interactions)}, exhausted: {sum(1 for t in tile_interactions.values() if t.get('exhausted', False))}")


# ============================================================================
# REPETITION & PATTERN HANDLING
# ============================================================================

def track_consecutive_action(brain, action_name):
    if action_name == brain.current_repeated_action:
        brain.consecutive_action_count += 1
    else:
        brain.current_repeated_action = action_name; brain.consecutive_action_count = 1


def get_learning_multiplier(brain, action_name):
    if action_name != brain.current_repeated_action or brain.consecutive_action_count < brain.LEARNING_SLOWDOWN_START:
        return 1.0
    progress = min(1.0, (brain.consecutive_action_count - brain.LEARNING_SLOWDOWN_START) /
                   (brain.LEARNING_SLOWDOWN_MAX - brain.LEARNING_SLOWDOWN_START))
    return max(0.05, 1.0 - 0.95 * progress)


def get_nth_highest_utility(brain, group, n=3):
    utilities = sorted([a.utility for a in brain.actions() if a.group == group], reverse=True)
    if len(utilities) < n:
        return brain.INTERACT_UTILITY_FLOOR if group == "interact" else brain.MOVE_UTILITY_FLOOR
    return utilities[n-1]


def detect_pattern(brain):
    if len(brain.action_history) < 6: return None, 0
    recent = list(brain.action_history)[-brain.PATTERN_CHECK_WINDOW:]
    for pattern_len in range(1, brain.PATTERN_MAX_LENGTH + 1):
        if len(recent) < pattern_len * brain.PATTERN_MIN_REPEATS: continue
        candidate = tuple(recent[-pattern_len:])
        repeat_count, idx = 0, len(recent) - pattern_len
        while idx >= 0 and tuple(recent[idx:idx + pattern_len]) == candidate:
            repeat_count += 1; idx -= pattern_len
        if repeat_count >= brain.PATTERN_MIN_REPEATS:
            return candidate, repeat_count
    return None, 0


def apply_pattern_penalty(brain):
    pattern, repeat_count = detect_pattern(brain)
    if pattern is None:
        brain.detected_pattern = None; brain.pattern_repeat_count = 0; return
    brain.detected_pattern = pattern; brain.pattern_repeat_count = repeat_count
    penalty_factor = max(0.3, 1.0 - repeat_count * 0.15)
    for action_name in set(pattern):
        for a in brain.actions():
            if a.action == action_name:
                floor = brain.INTERACT_UTILITY_FLOOR if a.group == "interact" else brain.MOVE_UTILITY_FLOOR
                a.utility = max(floor, a.utility * penalty_factor); break


def apply_repetition_penalty(brain):
    if brain.current_repeated_action is None: return
    for a in brain.actions():
        if a.action == brain.current_repeated_action:
            floor = brain.INTERACT_UTILITY_FLOOR if a.group == "interact" else brain.MOVE_UTILITY_FLOOR
            if brain.consecutive_action_count >= brain.HARD_RESET_THRESHOLD:
                a.utility = floor; brain.consecutive_action_count = 0
                print(f"  🔨 HARD RESET: {a.action} → {floor:.3f}")
            elif brain.consecutive_action_count >= brain.PENALTY_THRESHOLD:
                a.utility = max(a.utility * 0.5, floor)
            break


# ============================================================================
# ATTACH ALL METHODS TO BRAIN CLASS
# ============================================================================

def attach_to_brain(BrainClass):
    """Attach all stagnation functions as methods on the Brain class."""
    # Bounding rect
    BrainClass.update_bounding_rect_tracking = update_bounding_rect_tracking
    BrainClass.compute_bounding_rect_debt = compute_bounding_rect_debt
    BrainClass.get_bounding_rect_info = get_bounding_rect_info

    # Blend
    BrainClass.get_blend_tier = get_blend_tier
    BrainClass.try_blend_if_needed = try_blend_if_needed

    # Stagnation
    BrainClass.get_context_state_hash = get_context_state_hash
    BrainClass.check_state_stagnation = check_state_stagnation
    BrainClass.check_position_stagnation = check_position_stagnation
    BrainClass.should_force_random = should_force_random
    BrainClass.get_forced_random_action_name = get_forced_random_action_name
    BrainClass.check_direction_change_progress = check_direction_change_progress
    BrainClass.apply_stagnation_initiator_penalty = apply_stagnation_initiator_penalty

    # Productive change
    BrainClass.check_productive_change = check_productive_change
    BrainClass.on_productive_change = on_productive_change

    # Mode swap
    BrainClass.on_mode_swap = on_mode_swap
    BrainClass.should_use_both_mode = should_use_both_mode
    BrainClass.determine_control_mode = determine_control_mode

    # Exploration tracking
    BrainClass.update_exploration_tracking = update_exploration_tracking
    BrainClass.on_map_change = on_map_change

    # Repetition / pattern
    BrainClass.track_consecutive_action = track_consecutive_action
    BrainClass.get_learning_multiplier = get_learning_multiplier
    BrainClass.get_nth_highest_utility = get_nth_highest_utility
    BrainClass.detect_pattern = detect_pattern
    BrainClass.apply_pattern_penalty = apply_pattern_penalty
    BrainClass.apply_repetition_penalty = apply_repetition_penalty