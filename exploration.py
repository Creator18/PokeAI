# ============================================================================
# exploration.py — Action Confirmation, Exploration Memory, Tile Probing
# ============================================================================
# Cell 3.3 equivalent. All methods take `brain` as first argument.
# Attached via attach_to_brain().
#
# Contains:
#   - Action execution confirmation (pending action tracking)
#   - Exploration memory persistence (load/save/serialize/deserialize)
#   - Map memory access (get_current_map_memory, record_visited_tile,
#     record_obstruction)
#   - Tile-based interaction probing (should_interact, untried directions,
#     best probe action, record attempt, exhaustion check, verification)
# ============================================================================

import json
import numpy as np
from pathlib import Path


# ============================================================================
# ACTION EXECUTION CONFIRMATION
# ============================================================================

def set_pending_action(brain, action_name):
    brain.pending_action = action_name
    brain.pending_action_frames = 0


def confirm_action_executed(brain, context_state, prev_context_state):
    if brain.pending_action is None:
        return True
    brain.pending_action_frames += 1
    action_executed = False
    if prev_context_state is not None:
        if brain.pending_action in ["UP", "DOWN", "LEFT", "RIGHT"]:
            pos_changed = (context_state[0] != prev_context_state[0] or
                          context_state[1] != prev_context_state[1])
            dir_changed = context_state[5] != prev_context_state[5]
            action_executed = pos_changed or dir_changed
        elif brain.pending_action in ["A", "B", "Start", "Select"]:
            menu_changed = abs(context_state[4] - prev_context_state[4]) > 0.1
            battle_changed = context_state[3] != prev_context_state[3]
            map_changed = context_state[2] != prev_context_state[2]
            action_executed = menu_changed or battle_changed or map_changed
    if action_executed or brain.pending_action_frames >= brain.ACTION_CONFIRM_FRAMES:
        brain.last_confirmed_action = brain.pending_action
        brain.pending_action = None
        brain.pending_action_frames = 0
        return True
    return False


def should_send_new_action(brain):
    return brain.pending_action is None or brain.pending_action_frames >= brain.ACTION_CONFIRM_FRAMES


# ============================================================================
# EXPLORATION MEMORY PERSISTENCE
# ============================================================================

def load_exploration_memory(brain):
    try:
        if brain.EXPLORATION_MEMORY_FILE.exists():
            with open(brain.EXPLORATION_MEMORY_FILE, 'r') as f:
                data = json.load(f)
                brain.exploration_memory = {}
                for map_key, map_data in data.items():
                    map_id = int(map_key.replace('map_', ''))
                    brain.exploration_memory[map_id] = _deserialize_map_memory(map_data)
            print(f"  Loaded exploration memory: {len(brain.exploration_memory)} maps")
        else:
            brain.exploration_memory = {}
    except Exception as e:
        print(f"  Error loading exploration memory: {e}")
        brain.exploration_memory = {}


def _deserialize_map_memory(map_data):
    memory = {
        'visited_tiles': set(tuple(t) for t in map_data.get('visited_tiles', [])),
        'obstructions': set(tuple(t) for t in map_data.get('obstructions', [])),
        'interactable_objects': map_data.get('interactable_objects', []),
        'last_visited_timestep': map_data.get('last_visited_timestep', 0),
        'transitions': map_data.get('transitions', []),
        'temp_debt': map_data.get('temp_debt', 0.0),
        'tile_interactions': {}
    }
    for tile_key, tile_data in map_data.get('tile_interactions', {}).items():
        memory['tile_interactions'][tile_key] = {
            'directions_tried': set(tile_data.get('directions_tried', [])),
            'direction_attempts': {int(k): v for k, v in tile_data.get('direction_attempts', {}).items()},
            'direction_successes': {int(k): v for k, v in tile_data.get('direction_successes', {}).items()},
            'exhausted': tile_data.get('exhausted', False)
        }
    return memory


def save_exploration_memory(brain):
    try:
        data = {f'map_{mid}': _serialize_map_memory(md) for mid, md in brain.exploration_memory.items()}
        with open(brain.EXPLORATION_MEMORY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"  Error saving exploration memory: {e}")


def _serialize_map_memory(map_data):
    serialized_ti = {}
    for tile_key, td in map_data.get('tile_interactions', {}).items():
        serialized_ti[tile_key] = {
            'directions_tried': list(td.get('directions_tried', set())),
            'direction_attempts': {str(k): v for k, v in td.get('direction_attempts', {}).items()},
            'direction_successes': {str(k): v for k, v in td.get('direction_successes', {}).items()},
            'exhausted': td.get('exhausted', False)
        }
    return {
        'visited_tiles': list(map_data['visited_tiles']),
        'obstructions': list(map_data['obstructions']),
        'interactable_objects': map_data['interactable_objects'],
        'last_visited_timestep': map_data['last_visited_timestep'],
        'transitions': map_data.get('transitions', []),
        'temp_debt': map_data.get('temp_debt', 0.0),
        'tile_interactions': serialized_ti
    }


# ============================================================================
# MAP MEMORY ACCESS
# ============================================================================

def get_current_map_memory(brain, map_id):
    if map_id not in brain.exploration_memory:
        brain.exploration_memory[map_id] = {
            'visited_tiles': set(), 'obstructions': set(), 'interactable_objects': [],
            'last_visited_timestep': brain.timestep, 'transitions': [], 'temp_debt': 0.0,
            'tile_interactions': {}
        }
    return brain.exploration_memory[map_id]


def record_visited_tile(brain, x, y, map_id):
    memory = get_current_map_memory(brain, map_id)
    memory['visited_tiles'].add((int(x), int(y)))
    memory['last_visited_timestep'] = brain.timestep


def record_obstruction(brain, x, y, map_id, direction):
    dx, dy = brain.DIRECTION_DELTAS_INT.get(direction, (0, 0))
    memory = get_current_map_memory(brain, map_id)
    memory['obstructions'].add((int(x + dx), int(y + dy)))


# ============================================================================
# TILE-BASED INTERACTION PROBING
# ============================================================================

def get_tile_interaction_key(brain, x, y):
    return f"{int(x)}_{int(y)}"


def get_tile_interaction_state(brain, x, y, map_id):
    memory = get_current_map_memory(brain, map_id)
    tile_key = get_tile_interaction_key(brain, x, y)
    if tile_key not in memory['tile_interactions']:
        memory['tile_interactions'][tile_key] = {
            'directions_tried': set(),
            'direction_attempts': {0: 0, 1: 0, 2: 0, 3: 0},
            'direction_successes': {0: 0, 1: 0, 2: 0, 3: 0},
            'exhausted': False
        }
    return memory['tile_interactions'][tile_key]


def should_interact_at_tile(brain, x, y, map_id):
    tile_state = get_tile_interaction_state(brain, x, y, map_id)
    if tile_state['exhausted']:
        return False
    if len(tile_state['directions_tried']) < 4:
        return True
    for d in range(4):
        attempts = tile_state['direction_attempts'].get(d, 0)
        successes = tile_state['direction_successes'].get(d, 0)
        if attempts > 0 and successes / attempts >= brain.MIN_SUCCESS_RATE_THRESHOLD:
            return True
    return False


def get_untried_directions(brain, x, y, map_id):
    tile_state = get_tile_interaction_state(brain, x, y, map_id)
    return [d for d in range(4) if d not in tile_state['directions_tried']]


def get_best_interaction_direction(brain, x, y, map_id):
    tile_state = get_tile_interaction_state(brain, x, y, map_id)
    untried = get_untried_directions(brain, x, y, map_id)
    if untried:
        return untried[0]
    best_dir, best_rate = None, 0.0
    for d in range(4):
        attempts = tile_state['direction_attempts'].get(d, 0)
        if attempts > 0:
            rate = tile_state['direction_successes'].get(d, 0) / attempts
            if rate > best_rate:
                best_rate, best_dir = rate, d
    return best_dir


def get_best_probe_action(brain, raw_x, raw_y, current_map, current_dir):
    cache_key = (raw_x, raw_y, current_map, current_dir)

    if brain._probe_cache_position == cache_key:
        return brain._cached_probe_action, brain._cached_probe_dir

    if not should_interact_at_tile(brain, raw_x, raw_y, current_map):
        result = (None, None)
    else:
        untried = get_untried_directions(brain, raw_x, raw_y, current_map)
        if not untried:
            best_dir = get_best_interaction_direction(brain, raw_x, raw_y, current_map)
            if best_dir is not None:
                result = ('A', current_dir) if current_dir == best_dir else (brain.INT_TO_ACTION[best_dir], best_dir)
            else:
                result = (None, None)
        elif current_dir in untried:
            result = ('A', current_dir)
        else:
            target_dir = untried[0]
            result = (brain.INT_TO_ACTION[target_dir], target_dir)

    brain._probe_cache_position = cache_key
    brain._cached_probe_action, brain._cached_probe_dir = result
    return result


def record_tile_interaction_attempt(brain, x, y, map_id, direction, success):
    tile_state = get_tile_interaction_state(brain, x, y, map_id)
    tile_state['directions_tried'].add(direction)
    tile_state['direction_attempts'][direction] = tile_state['direction_attempts'].get(direction, 0) + 1
    if success:
        tile_state['direction_successes'][direction] = tile_state['direction_successes'].get(direction, 0) + 1
        memory = get_current_map_memory(brain, map_id)
        dir_name = brain.DIRECTION_NAMES.get(direction, str(direction))
        interactable = [int(x), int(y), dir_name]
        if interactable not in memory['interactable_objects']:
            memory['interactable_objects'].append(interactable)
            print(f"  🎯 INTERACTABLE FOUND: ({x}, {y}) facing {dir_name}")
    _check_tile_exhaustion(brain, x, y, map_id)


def _check_tile_exhaustion(brain, x, y, map_id):
    tile_state = get_tile_interaction_state(brain, x, y, map_id)
    if len(tile_state['directions_tried']) < 4:
        return
    if not any(tile_state['direction_successes'].get(d, 0) > 0 for d in range(4)):
        tile_state['exhausted'] = True
        print(f"  ✓ Tile ({x}, {y}) exhausted - no interactions found")


def get_direction_success_rate(brain, x, y, map_id, direction):
    tile_state = get_tile_interaction_state(brain, x, y, map_id)
    attempts = tile_state['direction_attempts'].get(direction, 0)
    if attempts == 0:
        return None
    return tile_state['direction_successes'].get(direction, 0) / attempts


def start_interaction_verification(brain, x, y, map_id, direction):
    brain.pending_interaction_verify = {'x': x, 'y': y, 'map_id': map_id, 'direction': direction}
    brain.interaction_verify_countdown = brain.INTERACTION_VERIFY_FRAMES


def check_interaction_verification(brain, context_state, prev_context_state):
    if brain.pending_interaction_verify is None:
        return
    brain.interaction_verify_countdown -= 1
    success = False
    if prev_context_state is not None:
        in_overworld = prev_context_state[3] <= 0.5 and prev_context_state[4] <= 0.5
        if in_overworld:
            menu_changed = abs(context_state[4] - prev_context_state[4]) > 0.1
            battle_started = context_state[3] > 0.5 and prev_context_state[3] <= 0.5
            map_changed = int(context_state[2]) != int(prev_context_state[2])
            success = menu_changed or battle_started or map_changed
    if success or brain.interaction_verify_countdown <= 0:
        info = brain.pending_interaction_verify
        record_tile_interaction_attempt(brain, info['x'], info['y'], info['map_id'], info['direction'], success)
        brain.pending_interaction_verify = None


def get_tile_interaction_stats(brain, map_id):
    memory = get_current_map_memory(brain, map_id)
    ti = memory.get('tile_interactions', {})
    return {
        'probed': len(ti),
        'exhausted': sum(1 for t in ti.values() if t.get('exhausted', False)),
        'with_success': sum(1 for t in ti.values()
                            if any(t.get('direction_successes', {}).get(d, 0) > 0 for d in range(4)))
    }


# ============================================================================
# ATTACH ALL METHODS TO BRAIN CLASS
# ============================================================================

def attach_to_brain(BrainClass):
    """Attach all exploration functions as methods on the Brain class."""
    # Action confirmation
    BrainClass.set_pending_action = set_pending_action
    BrainClass.confirm_action_executed = confirm_action_executed
    BrainClass.should_send_new_action = should_send_new_action

    # Exploration memory
    BrainClass.load_exploration_memory = load_exploration_memory
    BrainClass.save_exploration_memory = save_exploration_memory
    BrainClass.get_current_map_memory = get_current_map_memory
    BrainClass.record_visited_tile = record_visited_tile
    BrainClass.record_obstruction = record_obstruction

    # Tile probing
    BrainClass.get_tile_interaction_key = get_tile_interaction_key
    BrainClass.get_tile_interaction_state = get_tile_interaction_state
    BrainClass.should_interact_at_tile = should_interact_at_tile
    BrainClass.get_untried_directions = get_untried_directions
    BrainClass.get_best_interaction_direction = get_best_interaction_direction
    BrainClass.get_best_probe_action = get_best_probe_action
    BrainClass.record_tile_interaction_attempt = record_tile_interaction_attempt
    BrainClass.get_direction_success_rate = get_direction_success_rate
    BrainClass.start_interaction_verification = start_interaction_verification
    BrainClass.check_interaction_verification = check_interaction_verification
    BrainClass.get_tile_interaction_stats = get_tile_interaction_stats