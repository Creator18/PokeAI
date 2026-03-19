# ============================================================================
# navigation.py — Transitions, Debt, Navigation (Cell 3.4)
# ============================================================================
# All methods take `brain` as first argument. Attached via attach_to_brain().
#
# Contains:
#   - Transition recording + attraction scoring
#   - Transition ban system
#   - Debt systems (temp debt, map debt, location debt, decay)
#   - Exploration coverage + obstruction detection
#   - Standard helpers (location key, near edge, position stagnation, etc.)
#   - Map connectivity graph (BFS path finding)
#   - A* pathfinding
#   - Taught target lookup (per-map + cross-map)
#   - build_nav_target_list (taught, cross-map, revenge, transition only)
#   - Navigation execution (start, get_action, update_state, abort, complete)
#   - Cross-map navigation (advance chain, pause/resume, refresh)
# ============================================================================

import heapq
import numpy as np
from collections import deque as bfs_deque


# ============================================================================
# TRANSITION SYSTEM
# ============================================================================

def record_transition(brain, from_pos, from_map, to_map, direction, action_type):
    memory = brain.get_current_map_memory(from_map)
    for t in memory['transitions']:
        if t['position'] == from_pos and t['direction'] == direction:
            t['use_count'] += 1; t['last_used'] = brain.timestep; return
    memory['transitions'].append({
        'position': from_pos, 'direction': direction, 'action': action_type,
        'destination_map': to_map, 'use_count': 1, 'last_used': brain.timestep
    })
    brain._map_graph_dirty = True
    print(f"  🚪 TRANSITION FOUND: Map {from_map} ({from_pos}) → Map {to_map}")


def get_transition_attraction(brain, current_map):
    memory = brain.get_current_map_memory(current_map)
    transitions = memory.get('transitions', [])
    if not transitions: return 0.0, None
    current_debt = brain.map_novelty_debt.get(current_map, 0.0)
    current_temp_debt = get_temp_debt(brain, current_map)
    current_coverage = get_exploration_coverage(brain, current_map)
    best_attraction, best_transition = 0.0, None
    for t in transitions:
        if is_transition_banned(brain, current_map, t['position'], t['direction']): continue
        dest_map = t['destination_map']
        dest_debt = brain.map_novelty_debt.get(dest_map, 0.0)
        dest_temp_debt = get_temp_debt(brain, dest_map)
        dest_coverage = get_exploration_coverage(brain, dest_map)
        debt_diff = (current_debt + current_temp_debt * 2.0) - (dest_debt + dest_temp_debt * 2.0)
        coverage_diff = current_coverage - dest_coverage
        attraction = debt_diff * 0.5 + coverage_diff * 0.5
        if t['use_count'] < 3: attraction *= 1.5
        if attraction > best_attraction: best_attraction = attraction; best_transition = t
    return best_attraction * brain.TRANSITION_ATTRACTION_WEIGHT, best_transition


# ============================================================================
# TRANSITION BAN SYSTEM
# ============================================================================

def create_transition_ban(brain, map_id, tile_pos, direction_back):
    memory = brain.get_current_map_memory(map_id)
    transitions = memory.get('transitions', [])
    other_transitions = [t for t in transitions
                         if not (tuple(t['position']) == tuple(tile_pos) and t['direction'] == direction_back)]
    if not other_transitions:
        print(f"  🚫 SKIP BAN: Map {map_id} at {tile_pos} — only known exit"); return
    brain.transition_bans[map_id] = {
        'banned_tile': tile_pos, 'banned_direction': direction_back,
        'vicinity_radius': brain.BAN_VICINITY_RADIUS, 'vicinity_active': False,
        'created_at': brain.timestep
    }
    print(f"  🚫 TRANSITION BAN: Map {map_id} at {tile_pos} facing {brain.DIRECTION_NAMES.get(direction_back, '?')}")


def is_transition_banned(brain, map_id, position, direction):
    if map_id not in brain.transition_bans: return False
    ban = brain.transition_bans[map_id]
    banned_tile = tuple(ban['banned_tile']) if isinstance(ban['banned_tile'], list) else ban['banned_tile']
    position = tuple(position) if isinstance(position, list) else position
    if position == banned_tile and direction == ban['banned_direction']: return True
    if ban['vicinity_active']:
        dist = abs(position[0] - banned_tile[0]) + abs(position[1] - banned_tile[1])
        if dist <= ban['vicinity_radius'] and direction == ban['banned_direction']: return True
    return False


def is_position_banned(brain, map_id, x, y, direction):
    return is_transition_banned(brain, map_id, (x, y), direction)


def update_transition_ban(brain, map_id, current_pos):
    if map_id not in brain.transition_bans: return
    ban = brain.transition_bans[map_id]
    banned_tile = tuple(ban['banned_tile']) if isinstance(ban['banned_tile'], list) else ban['banned_tile']
    if not ban['vicinity_active'] and abs(current_pos[0] - banned_tile[0]) + abs(current_pos[1] - banned_tile[1]) >= 3:
        ban['vicinity_active'] = True
        print(f"  🚫 VICINITY BAN ACTIVE: Map {map_id}")


def check_ban_lift_conditions(brain, map_id):
    if map_id not in brain.transition_bans: return
    ban = brain.transition_bans[map_id]
    should_lift, reason = False, ""
    memory = brain.get_current_map_memory(map_id)
    non_banned = [t for t in memory.get('transitions', [])
                  if not is_transition_banned(brain, map_id, t['position'], t['direction'])]
    if non_banned: should_lift, reason = True, "alternative transition found"
    elif get_exploration_coverage(brain, map_id) >= brain.BAN_COVERAGE_LIFT_THRESHOLD:
        should_lift, reason = True, "coverage reached"
    elif brain.timestep - ban['created_at'] >= brain.BAN_TIMEOUT_STEPS:
        should_lift, reason = True, "timeout"
    if should_lift:
        del brain.transition_bans[map_id]
        print(f"  ✅ BAN LIFTED: Map {map_id} - {reason}")


# ============================================================================
# DEBT SYSTEMS
# ============================================================================

def get_temp_debt(brain, map_id):
    memory = brain.get_current_map_memory(map_id)
    raw_debt = memory.get('temp_debt', 0.0)
    if map_id != brain.current_map_id:
        steps_away = brain.timestep - memory.get('last_visited_timestep', 0)
        return max(0.0, raw_debt - steps_away * brain.TEMP_DEBT_DECAY)
    return raw_debt


def accumulate_temp_debt(brain, map_id):
    memory = brain.get_current_map_memory(map_id)
    memory['temp_debt'] = min(brain.TEMP_DEBT_MAX, memory.get('temp_debt', 0.0) + brain.TEMP_DEBT_ACCUMULATION)


def decay_all_debts(brain):
    for map_id in list(brain.map_novelty_debt.keys()):
        if map_id != brain.current_map_id:
            brain.map_novelty_debt[map_id] *= (1.0 - brain.DEBT_DECAY_RATE)
            if brain.map_novelty_debt[map_id] < 0.1: del brain.map_novelty_debt[map_id]
    current_loc = None
    if brain.current_map_id is not None and len(brain.last_positions) > 0:
        pos = brain.last_positions[-1]
        current_loc = get_location_key(brain, pos[0], pos[1], brain.current_map_id)
    for loc in list(brain.location_novelty.keys()):
        if loc != current_loc:
            brain.location_novelty[loc] *= (1.0 - brain.DEBT_DECAY_RATE)
            if brain.location_novelty[loc] < 0.1: del brain.location_novelty[loc]


def get_exploration_coverage(brain, map_id):
    memory = brain.get_current_map_memory(map_id)
    visited = len(memory['visited_tiles']); obstructions = len(memory['obstructions'])
    if visited == 0 or visited + obstructions < 10: return 0.0
    return visited / (visited + obstructions)


def detect_obstruction(brain, prev_context, context_state, raw_position, prev_raw_position):
    if prev_context is None or prev_raw_position is None: return False
    if brain.last_action not in ['UP', 'DOWN', 'LEFT', 'RIGHT']: return False
    if raw_position == prev_raw_position:
        brain.record_obstruction(raw_position[0], raw_position[1], int(context_state[2]), int(context_state[5]))
        return True
    return False


# ============================================================================
# STANDARD HELPERS
# ============================================================================

def get_location_key(brain, x, y, map_id, bin_size=5):
    return (int(map_id), int(x // bin_size) * bin_size, int(y // bin_size) * bin_size)


def is_near_map_edge(brain, x, y):
    return x < 10 or x > 245 or y < 10 or y > 245


def record_action_execution(brain, action_name):
    if action_name:
        brain.action_execution_count[action_name] = brain.action_execution_count.get(action_name, 0) + 1


def get_position_stagnation(brain):
    if len(brain.last_positions) < 2: return 0
    current_pos = brain.last_positions[-1]
    return sum(1 for pos in reversed(list(brain.last_positions)[:-1]) if pos == current_pos)


def get_group_weight(brain, group):
    return sum(a.utility for a in brain.actions() if a.group == group)


# ============================================================================
# MAP CONNECTIVITY GRAPH
# ============================================================================

def build_map_graph(brain):
    if not brain._map_graph_dirty: return brain._map_graph
    graph = {}
    for map_id, memory in brain.exploration_memory.items():
        edges = []
        for t in memory.get('transitions', []):
            dest = t.get('destination_map')
            if dest is not None: edges.append((dest, t))
        if edges: graph[map_id] = edges
    brain._map_graph = graph; brain._map_graph_dirty = False
    return graph


def find_map_path(brain, from_map, to_map):
    if from_map == to_map: return [from_map]
    graph = build_map_graph(brain)
    if from_map not in graph: return []
    queue = bfs_deque([(from_map, [from_map])]); visited = {from_map}
    while queue:
        current, path = queue.popleft()
        for dest_map, _ in graph.get(current, []):
            if dest_map == to_map: return path + [dest_map]
            if dest_map not in visited: visited.add(dest_map); queue.append((dest_map, path + [dest_map]))
    return []


def get_transition_to_map(brain, from_map, to_map):
    memory = brain.get_current_map_memory(from_map)
    best_transition, best_use_count = None, -1
    for t in memory.get('transitions', []):
        if t.get('destination_map') == to_map:
            pos = tuple(t['position']) if isinstance(t['position'], list) else t['position']
            if is_transition_banned(brain, from_map, pos, t['direction']): continue
            if t.get('use_count', 0) > best_use_count:
                best_use_count = t['use_count']; best_transition = t
    return best_transition


def get_cross_map_status(brain):
    if not brain.nav_map_chain: return {'active': False}
    return {
        'active': True, 'chain': brain.nav_map_chain,
        'chain_index': brain.nav_chain_index, 'chain_length': len(brain.nav_map_chain),
        'current_map': brain.nav_map_chain[brain.nav_chain_index] if brain.nav_chain_index < len(brain.nav_map_chain) else None,
        'target_map': brain.nav_map_chain[-1] if brain.nav_map_chain else None,
        'final_target': brain.nav_cross_map_target,
        'paused': brain.nav_paused, 'paused_reason': brain.nav_paused_reason
    }


# ============================================================================
# A* PATHFINDING
# ============================================================================

def _astar(brain, start, goal, map_id):
    memory = brain.get_current_map_memory(map_id)
    visited_tiles = memory['visited_tiles']; obstructions = memory['obstructions']
    start = (int(start[0]), int(start[1])); goal = (int(goal[0]), int(goal[1]))

    if start not in visited_tiles: return []
    if goal not in visited_tiles:
        best_adj, best_dist = None, float('inf')
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            adj = (goal[0]+dx, goal[1]+dy)
            if adj in visited_tiles and adj not in obstructions:
                d = abs(adj[0]-start[0]) + abs(adj[1]-start[1])
                if d < best_dist: best_dist = d; best_adj = adj
        if best_adj is None: return []
        goal = best_adj

    if start == goal: return [start]

    open_set = [(abs(goal[0]-start[0]) + abs(goal[1]-start[1]), 0, start)]
    came_from = {}; g_score = {start: 0}; closed = set()

    while open_set:
        f, g, current = heapq.heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from: current = came_from[current]; path.append(current)
            path.reverse(); return path
        if current in closed: continue
        closed.add(current)
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            neighbor = (current[0]+dx, current[1]+dy)
            if neighbor in closed or neighbor not in visited_tiles or neighbor in obstructions: continue
            new_g = g + 1
            if new_g < g_score.get(neighbor, float('inf')):
                g_score[neighbor] = new_g; h = abs(goal[0]-neighbor[0]) + abs(goal[1]-neighbor[1])
                came_from[neighbor] = current; heapq.heappush(open_set, (new_g+h, new_g, neighbor))
    return []


# ============================================================================
# TAUGHT TARGET LOOKUP
# ============================================================================

def _get_taught_targets_for_map(brain, map_id, current_pos):
    if not brain.taught_nav_loaded: return []
    map_targets = brain.taught_nav_targets.get(map_id, [])
    if not map_targets: return []
    candidates = []
    for t in map_targets:
        order = t.get('order', 0)
        if order in brain.nav_visited_targets: continue
        pos = tuple(t['position'])
        if pos in brain.nav_struck_targets: continue
        dist = abs(current_pos[0] - pos[0]) + abs(current_pos[1] - pos[1])
        candidates.append((pos, t, dist))
    candidates.sort(key=lambda x: x[1].get('order', 0))
    return [(pos, t) for pos, t, dist in candidates[:1]]


def _get_next_taught_target_any_map(brain, current_pos, current_map):
    if not brain.taught_nav_loaded or not brain.taught_nav_global_order: return None, None, None
    current_map_targets = _get_taught_targets_for_map(brain, current_map, current_pos)
    if current_map_targets: return None, None, None
    for entry in brain.taught_nav_global_order:
        order = entry.get('order', -1)
        if order in brain.nav_visited_targets: continue
        target_map = entry.get('map_id'); pos = tuple(entry.get('position', [0, 0]))
        if pos in brain.nav_struck_targets: continue
        target_data = entry
        for t in brain.taught_nav_targets.get(target_map, []):
            if t.get('order') == order: target_data = t; break
        return pos, target_data, target_map
    return None, None, None


# ============================================================================
# BUILD NAV TARGET LIST
# ============================================================================

def build_nav_target_list(brain, current_pos, map_id):
    targets = []

    # === TAUGHT TARGETS ===
    taught_targets = _get_taught_targets_for_map(brain, map_id, current_pos)
    if taught_targets:
        for pos, t_data in taught_targets:
            dist = abs(current_pos[0] - pos[0]) + abs(current_pos[1] - pos[1])
            score = t_data.get('forward_progress_score', 0.5) * 10.0 - dist * 0.02
            progress_type = t_data.get('progress_type', 'unknown')
            targets.append((pos, score, f"taught_{progress_type}", map_id))
        targets.sort(key=lambda x: x[1], reverse=True); return targets

    # === CROSS-MAP TARGET ===
    cross_pos, cross_data, cross_map = _get_next_taught_target_any_map(brain, current_pos, map_id)
    if cross_pos is not None and cross_map is not None and cross_map != map_id:
        map_path = find_map_path(brain, map_id, cross_map)
        if map_path and len(map_path) > 1:
            next_map = map_path[1]
            transition = get_transition_to_map(brain, map_id, next_map)
            if transition:
                t_pos = tuple(transition['position']) if isinstance(transition['position'], list) else transition['position']
                score = 15.0 - len(map_path) * 0.5
                targets.append((t_pos, score, f"cross_map_to_{cross_map}", cross_map))
                brain._pending_cross_map = {
                    'final_target': cross_pos, 'final_map': cross_map,
                    'target_data': cross_data, 'map_chain': map_path, 'transition': transition
                }
                targets.sort(key=lambda x: x[1], reverse=True); return targets
        elif not map_path:
            targets.append(((0, 0), 5.0, f"cross_map_need_{cross_map}", cross_map))
            brain._pending_cross_map = {
                'final_target': cross_pos, 'final_map': cross_map,
                'target_data': cross_data, 'map_chain': [], 'transition': None
            }
            return targets

    # === REVENGE TARGETS ===
    tid, revenge_target = brain.get_active_revenge_target()
    if revenge_target and revenge_target['status'] == 'ready':
        r_map = revenge_target['map_id']; r_pos = tuple(revenge_target['position'])
        if r_map == map_id:
            targets.append((r_pos, 20.0, 'revenge_ready', map_id))

    # === TRANSITION TARGETS ===
    memory = brain.get_current_map_memory(map_id)
    for t in memory.get('transitions', []):
        t_pos = tuple(t['position']) if isinstance(t['position'], list) else t['position']
        if is_transition_banned(brain, map_id, t_pos, t['direction']): continue
        dist = abs(current_pos[0] - t_pos[0]) + abs(current_pos[1] - t_pos[1])
        dest_coverage = get_exploration_coverage(brain, t['destination_map'])
        score = 3.0 * (1.0 - dest_coverage) - dist * 0.05
        if t_pos not in brain.nav_struck_targets:
            targets.append((t_pos, score, 'transition', map_id))

    targets.sort(key=lambda x: x[1], reverse=True)
    return targets


# ============================================================================
# NAVIGATION EXECUTION
# ============================================================================

def start_navigation(brain, current_pos, map_id):
    brain._pending_cross_map = None
    brain.nav_target_list = build_nav_target_list(brain, current_pos, map_id)
    if not brain.nav_target_list: return False

    if brain._pending_cross_map:
        cross = brain._pending_cross_map; brain._pending_cross_map = None
        if cross['map_chain'] and cross['transition']:
            brain.nav_map_chain = cross['map_chain']; brain.nav_chain_index = 0
            brain.nav_cross_map_target = cross['final_target']
            brain.nav_cross_map_target_data = cross['target_data']; brain.nav_paused = False
            t_pos = tuple(cross['transition']['position']) if isinstance(cross['transition']['position'], list) else cross['transition']['position']
            path = _astar(brain, current_pos, t_pos, map_id)
            if path and len(path) > 1:
                brain.nav_active = True; brain.nav_path = path; brain.nav_path_index = 1
                brain.nav_target = t_pos; brain.nav_steps_taken = 0
                brain.nav_stagnation_count = 0; brain.nav_last_position = current_pos
                chain_str = ' → '.join(str(m) for m in brain.nav_map_chain)
                print(f"  🧭🌍 CROSS-MAP NAV START: {chain_str}")
                print(f"     Final target: ({cross['final_target'][0]}, {cross['final_target'][1]}) on map {cross['final_map']}")
                print(f"     Immediate: → transition at ({t_pos[0]}, {t_pos[1]}) → map {brain.nav_map_chain[1]}")
                brain.nav_cross_map_refresh_countdown = brain.NAV_CROSS_MAP_REFRESH_INTERVAL
                return True
            else: _clear_cross_map_state(brain)
        elif not cross['map_chain']:
            brain.nav_map_chain = []; brain.nav_chain_index = 0
            brain.nav_cross_map_target = cross['final_target']
            brain.nav_cross_map_target_data = cross['target_data']
            brain.nav_paused = True; brain.nav_paused_reason = f"no path to map {cross['final_map']}"
            brain.nav_paused_target_map = cross['final_map']
            brain.nav_pause_check_countdown = brain.NAV_PAUSE_CHECK_INTERVAL
            brain.nav_active = True
            print(f"  🧭⏸️ CROSS-MAP NAV PAUSED: no path to map {cross['final_map']}")
            return True

    brain.nav_target_index = 0
    return _navigate_to_next_target(brain, current_pos, map_id)


def _navigate_to_next_target(brain, current_pos, map_id):
    while brain.nav_target_index < len(brain.nav_target_list):
        entry = brain.nav_target_list[brain.nav_target_index]
        target, score, target_type = entry[0], entry[1], entry[2]
        target_map = entry[3] if len(entry) > 3 else map_id

        if target in brain.nav_struck_targets:
            memory = brain.get_current_map_memory(map_id)
            current_visited = len(memory['visited_tiles'])
            struck_at_count = brain.nav_struck_tile_counts.get(target, 0)
            if struck_at_count > 0 and current_visited > struck_at_count * 1.3:
                brain.nav_struck_targets.discard(target)
                del brain.nav_struck_tile_counts[target]
                print(f"  🧭 RETRY struck target ({target[0]},{target[1]}): tiles {struck_at_count}→{current_visited}")
            else:
                brain.nav_target_index += 1; continue

        if target_type.startswith('cross_map_need'):
            brain.nav_target_index += 1; continue

        path = _astar(brain, current_pos, target, map_id)
        if path and len(path) > 1:
            brain.nav_active = True; brain.nav_path = path; brain.nav_path_index = 1
            brain.nav_target = target; brain.nav_steps_taken = 0
            brain.nav_stagnation_count = 0; brain.nav_last_position = current_pos
            print(f"  🧭 NAV START: → ({target[0]}, {target[1]}) [{target_type}] "
                  f"score={score:.1f} path={len(path)} steps")
            return True
        brain.nav_target_index += 1

    abort_navigation(brain, "no valid targets")
    return False


def get_nav_action(brain, current_pos):
    if not brain.nav_active or not brain.nav_path: return None
    if brain.nav_paused: return None
    if brain.nav_path_index < len(brain.nav_path):
        next_tile = brain.nav_path[brain.nav_path_index]
        if current_pos == next_tile:
            brain.nav_path_index += 1
            if brain.nav_path_index >= len(brain.nav_path): return None
            next_tile = brain.nav_path[brain.nav_path_index]
        dx = next_tile[0] - current_pos[0]; dy = next_tile[1] - current_pos[1]
        if dx > 0: return "RIGHT"
        elif dx < 0: return "LEFT"
        elif dy > 0: return "DOWN"
        elif dy < 0: return "UP"
    return None


def update_nav_state(brain, current_pos, map_id):
    if not brain.nav_active: return False
    if brain.nav_paused:
        check_nav_pause_resume(brain, current_pos, map_id); return True

    brain.nav_steps_taken += 1
    if brain.nav_map_chain:
        brain.nav_cross_map_refresh_countdown -= 1
        if brain.nav_cross_map_refresh_countdown <= 0:
            brain.nav_cross_map_refresh_countdown = brain.NAV_CROSS_MAP_REFRESH_INTERVAL
            refresh_cross_map_navigation(brain, current_pos, map_id)

    if brain.nav_steps_taken >= brain.NAV_MAX_STEPS:
        abort_navigation(brain, "max steps reached"); return False

    if current_pos == brain.nav_last_position:
        brain.nav_stagnation_count += 1
        if brain.nav_stagnation_count >= brain.NAV_STAGNATION_LIMIT:
            abort_navigation(brain, "stuck during pathfinding"); return False
    else: brain.nav_stagnation_count = 0
    brain.nav_last_position = current_pos

    if brain.nav_target:
        dist_to_target = abs(current_pos[0] - brain.nav_target[0]) + abs(current_pos[1] - brain.nav_target[1])
        if dist_to_target <= 1:
            if brain.nav_map_chain and brain.nav_chain_index < len(brain.nav_map_chain) - 1:
                print(f"  🧭🌍 Approaching transition at ({brain.nav_target[0]}, {brain.nav_target[1]})")
                return True
            _mark_taught_target_visited(brain, brain.nav_target)
            print(f"  🧭 NAV ARRIVED: ({brain.nav_target[0]}, {brain.nav_target[1]}) — target visited")
            complete_nav_target(brain)
            return False
    return True


def _mark_taught_target_visited(brain, position):
    if not brain.taught_nav_loaded: return
    pos_tuple = tuple(position)
    maps_to_check = [brain.current_map_id] if brain.current_map_id is not None else []
    maps_to_check += [m for m in brain.taught_nav_targets.keys() if m != brain.current_map_id]
    for check_map in maps_to_check:
        for t in brain.taught_nav_targets.get(check_map, []):
            if tuple(t['position']) == pos_tuple:
                order = t.get('order', -1)
                if order >= 0:
                    brain.nav_visited_targets.add(order)
                    print(f"  🧭 TARGET VISITED: order #{order} at ({pos_tuple[0]}, {pos_tuple[1]}) on map {check_map}")
                return


def complete_nav_target(brain):
    if brain.nav_target:
        print(f"  🧭 NAV COMPLETE: ({brain.nav_target[0]}, {brain.nav_target[1]})")
    if brain.nav_map_chain and brain.nav_chain_index >= len(brain.nav_map_chain) - 1:
        _clear_cross_map_state(brain)
    brain.nav_target_index += 1
    current_pos = brain.nav_last_position or (0, 0)
    map_id = brain.current_map_id
    if not _navigate_to_next_target(brain, current_pos, map_id):
        abort_navigation(brain, "all targets exhausted")


def abort_navigation(brain, reason=""):
    if brain.nav_active:
        cross_info = ""
        if brain.nav_map_chain:
            cross_info = f" [cross-map chain: {' → '.join(str(m) for m in brain.nav_map_chain)}]"
        print(f"  🧭 NAV END: {reason} (took {brain.nav_steps_taken} steps){cross_info}")
    brain.nav_active = False; brain.nav_path = []; brain.nav_path_index = 0
    brain.nav_target = None; brain.nav_steps_taken = 0; brain.nav_stagnation_count = 0
    _clear_cross_map_state(brain)


def is_nav_active(brain): return brain.nav_active
def is_nav_paused(brain): return brain.nav_paused


def get_nav_targets_status(brain):
    if not brain.taught_nav_loaded: return {'loaded': False, 'total': 0, 'visited': 0, 'remaining': 0}
    total = sum(len(t) for t in brain.taught_nav_targets.values())
    visited = len(brain.nav_visited_targets)
    return {'loaded': True, 'total': total, 'visited': visited, 'remaining': total - visited}


# ============================================================================
# CROSS-MAP NAVIGATION
# ============================================================================

def advance_map_chain(brain, new_map_id, current_pos):
    if not brain.nav_map_chain: return False
    new_index = None
    for i, chain_map in enumerate(brain.nav_map_chain):
        if chain_map == new_map_id: new_index = i; break
    if new_index is None:
        print(f"  🧭🌍 CROSS-MAP: landed on unexpected map {new_map_id}, aborting chain")
        _clear_cross_map_state(brain); return False
    brain.nav_chain_index = new_index

    if new_map_id == brain.nav_map_chain[-1]:
        if brain.nav_cross_map_target:
            path = _astar(brain, current_pos, brain.nav_cross_map_target, new_map_id)
            if path and len(path) > 1:
                brain.nav_path = path; brain.nav_path_index = 1
                brain.nav_target = brain.nav_cross_map_target; brain.nav_steps_taken = 0
                brain.nav_stagnation_count = 0; brain.nav_last_position = current_pos
                print(f"  🧭🌍 CROSS-MAP FINAL: arrived at map {new_map_id}, "
                      f"pathfinding to ({brain.nav_cross_map_target[0]}, {brain.nav_cross_map_target[1]})")
                return True
            else:
                print(f"  🧭🌍 CROSS-MAP: can't reach target on final map {new_map_id}")
                _clear_cross_map_state(brain); return False
        else: _clear_cross_map_state(brain); return False

    next_map = brain.nav_map_chain[new_index + 1]
    transition = get_transition_to_map(brain, new_map_id, next_map)
    if transition:
        t_pos = tuple(transition['position']) if isinstance(transition['position'], list) else transition['position']
        path = _astar(brain, current_pos, t_pos, new_map_id)
        if path and len(path) > 1:
            brain.nav_path = path; brain.nav_path_index = 1; brain.nav_target = t_pos
            brain.nav_steps_taken = 0; brain.nav_stagnation_count = 0; brain.nav_last_position = current_pos
            remaining = len(brain.nav_map_chain) - new_index - 1
            print(f"  🧭🌍 CROSS-MAP STEP: map {new_map_id} → transition to map {next_map} ({remaining} maps remaining)")
            return True
        else:
            brain.nav_paused = True; brain.nav_paused_reason = f"can't reach transition to map {next_map}"
            brain.nav_paused_target_map = next_map; brain.nav_pause_check_countdown = brain.NAV_PAUSE_CHECK_INTERVAL
            return True
    else:
        brain.nav_paused = True; brain.nav_paused_reason = f"no transition to map {next_map}"
        brain.nav_paused_target_map = next_map; brain.nav_pause_check_countdown = brain.NAV_PAUSE_CHECK_INTERVAL
        return True


def check_nav_pause_resume(brain, current_pos, map_id):
    if not brain.nav_paused: return False
    brain.nav_pause_check_countdown -= 1
    if brain.nav_pause_check_countdown > 0: return False
    brain.nav_pause_check_countdown = brain.NAV_PAUSE_CHECK_INTERVAL
    target_map = brain.nav_paused_target_map
    if target_map is None: return False
    brain._map_graph_dirty = True

    final_map = brain.nav_map_chain[-1] if brain.nav_map_chain else target_map
    if brain.nav_cross_map_target_data:
        for entry in brain.taught_nav_global_order:
            if tuple(entry.get('position', [])) == brain.nav_cross_map_target:
                final_map = entry.get('map_id', final_map); break

    new_path = find_map_path(brain, map_id, final_map)
    if new_path and len(new_path) > 1:
        brain.nav_map_chain = new_path; brain.nav_chain_index = 0
        brain.nav_paused = False; brain.nav_paused_reason = ""; brain.nav_paused_target_map = None
        next_map = new_path[1]
        transition = get_transition_to_map(brain, map_id, next_map)
        if transition:
            t_pos = tuple(transition['position']) if isinstance(transition['position'], list) else transition['position']
            path = _astar(brain, current_pos, t_pos, map_id)
            if path and len(path) > 1:
                brain.nav_path = path; brain.nav_path_index = 1; brain.nav_target = t_pos
                brain.nav_steps_taken = 0; brain.nav_stagnation_count = 0; brain.nav_last_position = current_pos
                print(f"  🧭▶️ CROSS-MAP NAV RESUMED: {' → '.join(str(m) for m in new_path)}")
                return True
        brain.nav_paused = True; brain.nav_paused_reason = f"can't reach transition to map {next_map}"
    return False


def refresh_cross_map_navigation(brain, current_pos, current_map):
    if not brain.nav_cross_map_target: return False
    final_target = brain.nav_cross_map_target
    final_map = brain.nav_map_chain[-1] if brain.nav_map_chain else None
    if final_map is None: return False

    if current_map == final_map:
        path = _astar(brain, current_pos, final_target, current_map)
        if path and len(path) > 1:
            brain.nav_path = path; brain.nav_path_index = 1; brain.nav_target = final_target
            brain.nav_stagnation_count = 0; brain.nav_last_position = current_pos; brain.nav_paused = False
            print(f"  🧭🔄 CROSS-MAP REFRESH: on final map {current_map}, re-pathing to target")
            return True
        else:
            print(f"  🧭🔄 CROSS-MAP REFRESH: on final map but can't reach target"); return False

    brain._map_graph_dirty = True
    new_chain = find_map_path(brain, current_map, final_map)
    if not new_chain:
        brain.nav_map_chain = [current_map]; brain.nav_chain_index = 0
        brain.nav_paused = True; brain.nav_paused_reason = f"refresh: no path from map {current_map} to map {final_map}"
        brain.nav_paused_target_map = final_map; brain.nav_pause_check_countdown = brain.NAV_PAUSE_CHECK_INTERVAL
        print(f"  🧭🔄 CROSS-MAP REFRESH: no path from {current_map} to {final_map}, pausing")
        return True

    old_chain = brain.nav_map_chain; brain.nav_map_chain = new_chain; brain.nav_chain_index = 0
    next_map = new_chain[1]
    transition = get_transition_to_map(brain, current_map, next_map)
    if transition:
        t_pos = tuple(transition['position']) if isinstance(transition['position'], list) else transition['position']
        path = _astar(brain, current_pos, t_pos, current_map)
        if path and len(path) > 1:
            brain.nav_path = path; brain.nav_path_index = 1; brain.nav_target = t_pos
            brain.nav_stagnation_count = 0; brain.nav_last_position = current_pos; brain.nav_paused = False
            if old_chain != new_chain:
                print(f"  🧭🔄 CROSS-MAP REFRESH: chain updated {' → '.join(str(m) for m in old_chain)} → {' → '.join(str(m) for m in new_chain)}")
            else:
                print(f"  🧭🔄 CROSS-MAP REFRESH: re-pathed on map {current_map}")
            return True
        else:
            brain.nav_paused = True; brain.nav_paused_reason = f"refresh: can't reach transition to map {next_map}"
            brain.nav_paused_target_map = next_map; brain.nav_pause_check_countdown = brain.NAV_PAUSE_CHECK_INTERVAL
            return True
    else:
        brain.nav_paused = True; brain.nav_paused_reason = f"refresh: no transition to map {next_map}"
        brain.nav_paused_target_map = next_map; brain.nav_pause_check_countdown = brain.NAV_PAUSE_CHECK_INTERVAL
        return True


def _clear_cross_map_state(brain):
    brain.nav_map_chain = []; brain.nav_chain_index = 0
    brain.nav_cross_map_target = None; brain.nav_cross_map_target_data = None
    brain.nav_paused = False; brain.nav_paused_reason = ""
    brain.nav_paused_target_map = None
    brain.nav_pause_check_countdown = 0; brain.nav_cross_map_refresh_countdown = 0


# ============================================================================
# ATTACH ALL METHODS TO BRAIN CLASS
# ============================================================================

def attach_to_brain(BrainClass):
    """Attach all navigation functions as methods on the Brain class."""
    # Transitions
    BrainClass.record_transition = record_transition
    BrainClass.get_transition_attraction = get_transition_attraction

    # Transition bans
    BrainClass.create_transition_ban = create_transition_ban
    BrainClass.is_transition_banned = is_transition_banned
    BrainClass.is_position_banned = is_position_banned
    BrainClass.update_transition_ban = update_transition_ban
    BrainClass.check_ban_lift_conditions = check_ban_lift_conditions

    # Debt
    BrainClass.get_temp_debt = get_temp_debt
    BrainClass.accumulate_temp_debt = accumulate_temp_debt
    BrainClass.decay_all_debts = decay_all_debts
    BrainClass.get_exploration_coverage = get_exploration_coverage
    BrainClass.detect_obstruction = detect_obstruction

    # Helpers
    BrainClass.get_location_key = get_location_key
    BrainClass.is_near_map_edge = is_near_map_edge
    BrainClass.record_action_execution = record_action_execution
    BrainClass.get_position_stagnation = get_position_stagnation
    BrainClass.get_group_weight = get_group_weight

    # Map graph
    BrainClass.build_map_graph = build_map_graph
    BrainClass.find_map_path = find_map_path
    BrainClass.get_transition_to_map = get_transition_to_map
    BrainClass.get_cross_map_status = get_cross_map_status

    # Navigation
    BrainClass._astar = _astar
    BrainClass.build_nav_target_list = build_nav_target_list
    BrainClass.start_navigation = start_navigation
    BrainClass.get_nav_action = get_nav_action
    BrainClass.update_nav_state = update_nav_state
    BrainClass.complete_nav_target = complete_nav_target
    BrainClass.abort_navigation = abort_navigation
    BrainClass.is_nav_active = is_nav_active
    BrainClass.is_nav_paused = is_nav_paused
    BrainClass.get_nav_targets_status = get_nav_targets_status

    # Cross-map
    BrainClass.advance_map_chain = advance_map_chain
    BrainClass.check_nav_pause_resume = check_nav_pause_resume
    BrainClass.refresh_cross_map_navigation = refresh_cross_map_navigation