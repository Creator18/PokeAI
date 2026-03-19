# ============================================================================
# action_selection.py — Action Selection (Cell 4)
# ============================================================================
# Standalone functions — NOT attached to Brain. Called directly from main.py.
#
# Contains:
#   - Helper functions (manhattan, get_action_perceptron, record_* helpers)
#   - Pipeline action interpretation
#   - Grid/cursor navigation
#   - Text dialogue action (A/B skip)
#   - Dialogue choice action
#   - Party menu action
#   - Start menu action
#   - Bag action (pipeline + Markov + fallback)
#   - Preparation action
#   - Battle action (dialog priority + pipeline + smart moves + Markov)
#   - anticipatory_action (main overworld — no forced exploration)
# ============================================================================

import random
import numpy as np

from constants import (
    ACTION_DELTAS, ACTION_TO_DIRECTION,
    BATTLE_CURSOR_FIGHT, BATTLE_CURSOR_RUN,
    PIPELINE_ACTION_MAP,
    MARKOV_FAMILIARITY_THRESHOLD,
)
from perceptron import Perceptron
from state import build_learning_state_battle, build_learning_state_bag


# ============================================================================
# HELPERS
# ============================================================================

def manhattan_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])


def _get_action_perceptron(actions_list, action_name):
    for a in actions_list:
        if a.action == action_name: return a
    return None


def _record_battle_action(brain, a):
    brain.record_action_execution(a.action)
    brain.track_consecutive_action(a.action)
    brain.battle_action_history.append(a.action)
    brain.set_party_menu_last_action(a.action)
    return a


def _record_party_menu_action(brain, a):
    brain.record_action_execution(a.action)
    brain.track_consecutive_action(a.action)
    brain.party_menu_action_count += 1
    brain.set_party_menu_last_action(a.action)
    if brain.party_menu_context in ("battle_forced", "battle_voluntary"):
        brain.battle_action_history.append(a.action)
        brain.battle_action_count += 1
    return a


def _record_bag_action(brain, a):
    brain.record_action_execution(a.action)
    brain.track_consecutive_action(a.action)
    brain.bag_thread_action_count += 1
    brain.bag_thread_total_actions += 1
    brain.bag_action_history.append(a.action)
    brain.set_bag_thread_last_action(a.action)
    if brain.bag_thread_context == "battle":
        brain.battle_action_history.append(a.action)
        brain.battle_action_count += 1
    return a


def _record_preparation_action(brain, a):
    brain.record_action_execution(a.action)
    brain.track_consecutive_action(a.action)
    return a


def _record_start_menu_action(brain, a):
    brain.record_action_execution(a.action)
    brain.track_consecutive_action(a.action)
    brain.start_menu_action_count += 1
    brain.start_menu_total_actions += 1
    brain.start_menu_action_history.append(a.action)
    brain.set_start_menu_last_action(a.action)
    return a


def _record_dialogue_action(brain, a, is_choice=False):
    brain.record_action_execution(a.action)
    brain.dialogue_last_action = a.action
    if is_choice:
        brain.track_consecutive_action(a.action)
        brain.dialogue_choice_action_count += 1
    else:
        brain.dialogue_skip_action_count += 1
    return a


# ============================================================================
# PIPELINE ACTION INTERPRETATION
# ============================================================================

def _pipeline_action_override(brain, pipeline_id, layer_name, raw_input,
                               actions_list, min_authority=0.15):
    pipeline = brain.pipelines.get(pipeline_id)
    if pipeline is None: return None, 0.0

    exec_pool, exec_idx = None, -1
    for i, pool in enumerate(pipeline.pools):
        if pool.name == layer_name: exec_pool = pool; exec_idx = i; break
    if exec_pool is None or exec_pool.authority < min_authority: return None, 0.0

    current_input = raw_input
    for i in range(exec_idx + 1):
        current_input = pipeline.pools[i].compute_output(current_input, brain.perceptrons)

    output = current_input
    best_action_name, best_score = None, -float('inf')
    for dim_idx, action_name in enumerate(PIPELINE_ACTION_MAP):
        if dim_idx < len(output):
            score = float(output[dim_idx])
            if score > best_score: best_score = score; best_action_name = action_name

    if best_action_name is None: return None, 0.0
    return _get_action_perceptron(actions_list, best_action_name), exec_pool.authority


# ============================================================================
# GRID + CURSOR NAVIGATION
# ============================================================================

def _navigate_2x2(current, target):
    if current == target: return "A"
    cr, cc = current // 2, current % 2
    tr, tc = target // 2, target % 2
    if cr < tr: return "DOWN"
    elif cr > tr: return "UP"
    elif cc < tc: return "RIGHT"
    elif cc > tc: return "LEFT"
    return "A"


def _navigate_party_cursor(current, target):
    if current == target: return "A"
    return "DOWN" if current < target else "UP"


def _navigate_vertical_cursor(current, target):
    if current == target: return "A"
    return "DOWN" if current < target else "UP"


# ============================================================================
# TEXT DIALOGUE ACTION
# ============================================================================

def text_dialogue_action(brain, context_state):
    actions_list = brain.actions()
    if brain.dialogue_last_action == "A":
        action_name = "B" if random.random() < 0.3 else "A"
    else:
        action_name = "A"
    a = _get_action_perceptron(actions_list, action_name)
    if a: return _record_dialogue_action(brain, a, is_choice=False)
    a = _get_action_perceptron(actions_list, "A")
    return _record_dialogue_action(brain, a, is_choice=False) if a else actions_list[0]


# ============================================================================
# DIALOGUE CHOICE ACTION
# ============================================================================

def dialogue_choice_action(brain, context_state):
    actions_list = brain.actions()
    if brain.markov_enabled:
        matched, action_name, score = brain.get_markov_action(context_state)
        if matched and action_name and action_name in ("A", "B", "UP", "DOWN"):
            a = _get_action_perceptron(actions_list, action_name)
            if a: brain.markov_action_count += 1; return _record_dialogue_action(brain, a, is_choice=True)
    a = _get_action_perceptron(actions_list, "A")
    return _record_dialogue_action(brain, a, is_choice=True) if a else actions_list[0]


# ============================================================================
# PARTY MENU ACTION
# ============================================================================

def party_menu_action(brain, context_state):
    actions_list = brain.actions()
    context = brain.party_menu_context
    pc = brain.battle_data.get('party_cursor', -1)

    if context == "battle_forced":
        target = brain.party_menu_target_slot
        if target < 0:
            target = brain.get_best_switch_slot()
            brain.party_menu_target_slot = target; brain.forced_switch_target_slot = target
            if target >= 0: print(f"  🔄 FORCED SWITCH → slot {target}")
            else:
                a = _get_action_perceptron(actions_list, "B")
                return _record_party_menu_action(brain, a) if a else actions_list[0]
        if target >= 0 and 0 <= pc <= 5:
            nav = _navigate_party_cursor(pc, target)
            if nav == "A": brain.forced_switch_pending = False; brain.forced_switch_target_slot = -1
            a = _get_action_perceptron(actions_list, nav)
            return _record_party_menu_action(brain, a) if a else actions_list[0]
        a = _get_action_perceptron(actions_list, "A")
        return _record_party_menu_action(brain, a) if a else actions_list[0]

    a = _get_action_perceptron(actions_list, "B")
    return _record_party_menu_action(brain, a) if a else actions_list[0]


# ============================================================================
# START MENU ACTION
# ============================================================================

def start_menu_action(brain, context_state):
    actions_list = brain.actions()
    mc = brain.menu_data.get('mc', -1)
    target_mc = brain.start_menu_target_mc

    matched, action_name, score = brain.get_start_menu_markov_action()
    if matched and action_name:
        if action_name in ("START", "SELECT"): action_name = "A" if mc == target_mc else "B"
        brain.start_menu_markov_actions += 1; brain.last_start_menu_markov_action = action_name
        a = _get_action_perceptron(actions_list, action_name)
        if a: return _record_start_menu_action(brain, a)

    if target_mc >= 0 and 0 <= mc <= 6:
        if mc == target_mc:
            a = _get_action_perceptron(actions_list, "A")
            if a: return _record_start_menu_action(brain, a)
        else:
            nav = _navigate_vertical_cursor(mc, target_mc)
            a = _get_action_perceptron(actions_list, nav)
            if a: return _record_start_menu_action(brain, a)

    a = _get_action_perceptron(actions_list, "B")
    return _record_start_menu_action(brain, a) if a else actions_list[0]


# ============================================================================
# BAG ACTION
# ============================================================================

def bag_action(brain, context_state):
    actions_list = brain.actions()
    prev_mc = brain.prev_menu_data.get('mc', -1)
    prev_action = brain.bag_thread_last_action
    if prev_action == "A" and prev_mc == 0:
        prev_items = brain.prev_bag_data.get('items', [])
        prev_cursor = brain.prev_bag_data.get('cursor', -1)
        item_id = prev_items[prev_cursor].get('id', -1) if 0 <= prev_cursor < len(prev_items) else -1
        if item_id > 0 and brain.pending_item_observation is None:
            brain.start_item_observation(item_id, target_slot=brain.menu_data.get('pc', -1))

    bag_state = build_learning_state_bag(brain.bag_data, brain.party_data,
                                          brain.menu_data, context_state[3] > 0.5)
    pipeline_action, pipeline_auth = _pipeline_action_override(
        brain, "bag", "execution", bag_state, actions_list, min_authority=0.2)
    if pipeline_action is not None:
        if random.random() < pipeline_auth: return _record_bag_action(brain, pipeline_action)

    matched, action_name, score = brain.get_bag_markov_action()
    if matched and action_name:
        if action_name in ("START", "SELECT"): action_name = "B"
        brain.bag_thread_markov_actions += 1; brain.last_bag_markov_action = action_name
        a = _get_action_perceptron(actions_list, action_name)
        if a: return _record_bag_action(brain, a)

    a = _get_action_perceptron(actions_list, "B")
    return _record_bag_action(brain, a) if a else actions_list[0]


# ============================================================================
# PREPARATION ACTION
# ============================================================================

def preparation_action(brain, context_state):
    actions_list = brain.actions()
    action_name = brain.get_preparation_action()
    if action_name is None:
        if brain.is_start_menu_active() and brain.start_menu_context == "preparation":
            return start_menu_action(brain, context_state)
        a = _get_action_perceptron(actions_list, "B")
        return _record_preparation_action(brain, a) if a else actions_list[0]
    a = _get_action_perceptron(actions_list, action_name)
    return _record_preparation_action(brain, a) if a else actions_list[0]


# ============================================================================
# BATTLE ACTION (dialog priority + pipeline + smart moves)
# ============================================================================

def battle_action(brain, context_state, palette_state=None):
    actions_list = brain.actions()
    brain.battle_frame_count += 1; brain.battle_action_count += 1
    bd = brain.battle_data; has_data = brain.has_battle_data()

    # === DIALOG PRIORITY CHECK ===
    if brain.text_flag == 1 and has_data:
        bc = bd.get('battle_cursor', -1); mc = bd.get('move_cursor', -1)
        if not (0 <= bc <= 3) and not (0 <= mc <= 3):
            return text_dialogue_action(brain, context_state)

    if has_data:
        menu_state = brain.infer_battle_menu_state(); brain.battle_menu_state = menu_state
        bc, mc = bd['battle_cursor'], bd['move_cursor']
        want_run = brain.should_run()

        battle_state = build_learning_state_battle(bd, brain.party_data, brain.turn_count)
        pipeline_action, pipeline_auth = _pipeline_action_override(
            brain, "battle", "execution", battle_state, actions_list, min_authority=0.2)

        if menu_state == "main_menu" and 0 <= bc <= 3:
            brain.battle_cursor_action_count += 1
            if pipeline_action is not None and pipeline_auth > 0.3:
                if pipeline_action.action in ("UP", "DOWN", "LEFT", "RIGHT", "A"):
                    if random.random() < pipeline_auth * 0.5:
                        return _record_battle_action(brain, pipeline_action)
            target = BATTLE_CURSOR_RUN if want_run else BATTLE_CURSOR_FIGHT
            nav = _navigate_2x2(bc, target)
            a = _get_action_perceptron(actions_list, nav)
            if a: return _record_battle_action(brain, a)

        if menu_state == "move_select" and 0 <= mc <= 3:
            brain.battle_cursor_action_count += 1
            target_slot = 0
            enemy_species = bd.get('enemy_species', -1)
            if enemy_species > 0:
                ranked = brain.get_best_move_for_enemy(enemy_species)
                if ranked and ranked[0][2] > 1.5: target_slot = ranked[0][1]
                elif ranked:
                    battle_signal = brain.get_chain_entity_signal("battle", battle_state)
                    if battle_signal > 0.4 and len(ranked) > 1:
                        target_slot = ranked[1][1] if random.random() < 0.3 else ranked[0][1]
                    else: target_slot = ranked[0][1]
                else:
                    available = brain.get_moves_with_pp()
                    if available: target_slot = available[0][0]
            else:
                available = brain.get_moves_with_pp()
                if available: target_slot = available[0][0]
            nav = _navigate_2x2(mc, target_slot)
            if nav == "A":
                brain.last_move_slot = target_slot
                brain.last_move_used = bd.get(['move0','move1','move2','move3'][target_slot], -1)
            a = _get_action_perceptron(actions_list, nav)
            if a: return _record_battle_action(brain, a)

        if pipeline_action is not None and pipeline_auth > 0.25:
            if random.random() < pipeline_auth:
                return _record_battle_action(brain, pipeline_action)

    matched, action_name, score = brain.get_battle_markov_action(context_state, palette_state)
    if matched and action_name:
        if action_name in ("START", "SELECT"): action_name = "A"
        brain.battle_markov_action_count += 1; brain.last_battle_markov_action = action_name
        a = _get_action_perceptron(actions_list, action_name)
        if a: return _record_battle_action(brain, a)

    a = _get_action_perceptron(actions_list, "A")
    return _record_battle_action(brain, a) if a else actions_list[0]


# ============================================================================
# MAIN ACTION SELECTION
# ============================================================================

def anticipatory_action(brain, learning_state, context_state,
                       exploration_weight=1.3, min_interact_prob=0.15,
                       raw_position=None,
                       override_threshold=1.5, taught_frames=None,
                       map_density=None, palette_state=None):
    actions_list = brain.actions()
    if not actions_list: return Perceptron("action", action="UP", group="move")

    # === 0. PARTY MENU ===
    if brain.is_party_menu_active(): return party_menu_action(brain, context_state)

    # === 0.3. TEXT DIALOGUE ===
    if brain.is_dialogue_skip_state(): return text_dialogue_action(brain, context_state)

    # === 0.4. DIALOGUE CHOICE ===
    if brain.is_dialogue_choice_state(): return dialogue_choice_action(brain, context_state)

    # === 0.5. START MENU ===
    if brain.is_start_menu_active() and not brain.is_preparation_active():
        return start_menu_action(brain, context_state)

    # === 1. BAG ===
    if brain.is_bag_thread_active(): return bag_action(brain, context_state)

    # === 2. BATTLE ===
    if context_state[3] > 0.5: return battle_action(brain, context_state, palette_state)

    # === 3. PREPARATION ===
    if brain.is_preparation_active():
        brain.update_preparation_state(context_state)
        if brain.is_preparation_active(): return preparation_action(brain, context_state)

    # === OVERWORLD ===
    density = map_density or {'taught_frames': 0, 'tier': 'sparse', 'coverage': 0.0, 'visited': 0}
    tier = density['tier']

    markov_threshold = {'sparse': 0.72, 'thin': 0.65, 'medium': 0.58, 'dense': 0.50}.get(
        tier, MARKOV_FAMILIARITY_THRESHOLD)
    adapted_exploration_weight = {'sparse': 1.8, 'thin': 1.5, 'medium': 1.3, 'dense': 1.1}.get(
        tier, exploration_weight)
    transition_weight_mult = {'sparse': 0.3, 'thin': 0.6, 'medium': 1.0, 'dense': 1.4}.get(tier, 1.0)

    raw_x = raw_position[0] if raw_position else int(context_state[0] * 255)
    raw_y = raw_position[1] if raw_position else int(context_state[1] * 255)
    current_map = int(context_state[2]); current_dir = int(context_state[5])
    current_pos = (raw_x, raw_y)
    currently_in_battle = context_state[3] > 0.5

    # === 4. PREP TRIGGER ===
    if context_state[3] <= 0.5 and context_state[4] <= 0.5:
        should, reason, target = brain.should_prepare(raw_x, raw_y, current_map)
        if should:
            brain.start_preparation(reason, target)
            if brain.is_preparation_active(): return preparation_action(brain, context_state)

    # === 5. FORCED RANDOM ===
    brain.check_state_stagnation(context_state)
    if brain.should_force_random():
        if brain.is_nav_active(): brain.abort_navigation("forced random")
        forced_name = brain.get_forced_random_action_name()
        for a in actions_list:
            if a.action == forced_name:
                brain.curiosity_action_count += 1
                brain.record_action_execution(a.action)
                brain.track_consecutive_action(a.action); return a

    # === 6. ACTIVE NAVIGATION ===
    if brain.is_nav_active():
        if brain.is_nav_paused():
            brain.update_nav_state(current_pos, current_map)
        else:
            if brain.update_nav_state(current_pos, current_map):
                nav_action = brain.get_nav_action(current_pos)
                if nav_action:
                    for a in actions_list:
                        if a.action == nav_action:
                            brain.curiosity_action_count += 1
                            brain.record_action_execution(a.action)
                            brain.track_consecutive_action(a.action); return a
                elif not brain.nav_paused:
                    brain.abort_navigation("path invalid")

    # === 6.5. OVERWORLD PIPELINE QUERY ===
    ow_pipeline_action, ow_pipeline_auth = _pipeline_action_override(
        brain, "overworld", "execution", learning_state, actions_list, min_authority=0.2)

    # === 7. MARKOV ===
    if brain.markov_enabled and taught_frames:
        score, action, idx = brain.compute_markov_similarity(context_state, raw_position, taught_frames=taught_frames)
        brain.last_markov_score = score
        if score >= markov_threshold and action:
            brain.last_markov_action = action
            for a in actions_list:
                if a.action == action:
                    brain.markov_action_count += 1
                    brain.record_action_execution(a.action)
                    brain.track_consecutive_action(a.action)
                    if a.action == 'A' and brain.should_interact_at_tile(raw_x, raw_y, current_map):
                        brain.start_interaction_verification(raw_x, raw_y, current_map, current_dir)
                    return a

    # === 7.5. TAUGHT-TARGET NAV TRIGGER ===
    if not brain.is_nav_active() and not currently_in_battle:
        if context_state[3] <= 0.5 and context_state[4] <= 0.5:
            targets = brain.build_nav_target_list(current_pos, current_map)
            if targets:
                if brain.start_navigation(current_pos, current_map):
                    nav_action = brain.get_nav_action(current_pos)
                    if nav_action:
                        for a in actions_list:
                            if a.action == nav_action:
                                brain.curiosity_action_count += 1
                                brain.record_action_execution(a.action)
                                brain.track_consecutive_action(a.action); return a

    # === 8. CURIOSITY SCORING ===
    brain.curiosity_action_count += 1
    mode = brain.determine_control_mode(context_state, raw_position=raw_position)

    memory = brain.get_current_map_memory(current_map)
    visited_tiles = memory['visited_tiles']; obstructions = memory['obstructions']
    tile_probing = brain.should_interact_at_tile(raw_x, raw_y, current_map)
    probe_action, probe_dir = brain.get_best_probe_action(raw_x, raw_y, current_map, current_dir)
    trans_attract, best_trans = brain.get_transition_attraction(current_map)
    coverage = brain.get_exploration_coverage(current_map)

    action_scores = {}
    for a in actions_list:
        if a.action in ('Start', 'Select'): action_scores[a.action] = (a, 0.0); continue

        predicted = brain.predict_future_error(learning_state, a, context_state, raw_position=raw_position)

        if a.group == "move":
            predicted *= adapted_exploration_weight
            dx, dy = ACTION_DELTAS.get(a.action, (0, 0))
            target_tile = (raw_x + dx, raw_y + dy)
            action_dir = ACTION_TO_DIRECTION.get(a.action, -1)

            if target_tile not in visited_tiles: predicted *= brain.UNVISITED_TILE_BONUS
            if target_tile in obstructions: predicted *= brain.OBSTRUCTION_PENALTY
            if brain.is_position_banned(current_map, raw_x, raw_y, action_dir): predicted *= 0.05

            if trans_attract > 0.3 and best_trans and coverage > 0.5:
                tp = tuple(best_trans['position']) if isinstance(best_trans['position'], list) else best_trans['position']
                if manhattan_distance(target_tile, tp) < manhattan_distance(current_pos, tp):
                    predicted *= (1.0 + trans_attract * transition_weight_mult)

            if probe_action == a.action and probe_dir is not None: predicted *= 2.0
            predicted *= (0.9 + random.random() * 0.2)

        elif a.group == "interact":
            predicted = max(predicted, min_interact_prob)
            if a.action == 'B': predicted *= brain.menu_trap_b_boost
            if a.action == 'A':
                if tile_probing and probe_action == 'A': predicted *= 3.0
                elif tile_probing: predicted *= 0.5
                else: predicted *= 0.3

        # Pipeline preference blend
        if ow_pipeline_action is not None and a.action == ow_pipeline_action.action:
            predicted *= (1.0 + ow_pipeline_auth * 2.0)

        action_scores[a.action] = (a, predicted)

    pref = "interact" if mode in ("battle", "interact") else "move"
    in_mode = [(a, s) for _, (a, s) in action_scores.items() if a.group == pref and s > 0]
    out_mode = [(a, s) for _, (a, s) in action_scores.items()
                if a.group != pref and s > 0 and a.action not in ('Start', 'Select')]

    best_in = max(in_mode, key=lambda x: x[1]) if in_mode else None
    best_out = max(out_mode, key=lambda x: x[1]) if out_mode else None

    if best_in and best_out:
        chosen = best_out[0] if best_out[1] > best_in[1] * override_threshold else best_in[0]
    elif best_in: chosen = best_in[0]
    elif best_out: chosen = best_out[0]
    else: chosen = max(actions_list, key=lambda a: a.utility)

    brain.record_action_execution(chosen.action)
    brain.track_consecutive_action(chosen.action)
    if chosen.action == 'A' and tile_probing:
        brain.start_interaction_verification(raw_x, raw_y, current_map, current_dir)
    return chosen