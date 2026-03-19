# ============================================================================
# learning.py — Entity Spawning/Pruning, Pipeline Learning, Save/Load,
#                Main Learn Loop (Cell 3.6)
# ============================================================================
# All methods take `brain` as first argument. Attached via attach_to_brain().
#
# Contains:
#   - Entity spawning wrappers (legacy)
#   - Innate entity spawning wrappers (legacy)
#   - Entity pruning (per-chain, periodic)
#   - Pipeline pool pruning
#   - Memory cleanup
#   - Utility enforcement
#   - Adaptive spawn threshold
#   - Stagnation level
#   - predict_future_error (curiosity scoring)
#   - Multi-modal error computation
#   - Pipeline learning (generic forward + backward + spawn)
#   - Chain-generic learning
#   - learn_battle_chain, learn_party_chain, learn_bag_chain
#   - Main learn() — overworld + dispatch to active chains
#   - State logging helpers (log_state, update_position)
#   - Save/load model checkpoint
#   - Initialize from taught model (bootstrap)
#   - Legacy merge_taught_exploration
# ============================================================================

import json
import numpy as np
from pathlib import Path

from constants import BASE_PATH, MODEL_CHECKPOINT_FILE
from perceptron import Perceptron
from state import (
    build_learning_state_battle, build_learning_state_party,
    build_learning_state_bag,
)
from pool import Pool


# ============================================================================
# ENTITY SPAWNING WRAPPERS (Legacy)
# ============================================================================

def spawn_entity_from_novelty(brain, learning_state, context_state, raw_position=None):
    brain.spawn_entity_for_chain("overworld", learning_state, context_state, raw_position)

def check_entity_capacity(brain):
    brain.check_chain_entity_capacity("overworld")

def cluster_entities(brain):
    brain.cluster_chain_entities("overworld")

def spawn_innate_entities(brain, learning_state):
    brain.spawn_innate_overworld_entities(learning_state)


# ============================================================================
# ENTITY PRUNING
# ============================================================================

def prune_low_utility_entities(brain, chain, min_familiarity=5.0,
                                max_fit_score=0.05, min_activations=30):
    innate_types = {"sense_menu", "sense_battle", "sense_movement", "sense_map_transition",
                    "battle_hp_crisis", "battle_enemy_weak", "battle_species_match",
                    "battle_status", "battle_trainer"}
    chain_entities = brain.entities(chain=chain)
    prunable = [e for e in chain_entities
                if e.entity_type not in innate_types
                and len(e.cluster_activations) >= min_activations
                and e.familiarity >= min_familiarity
                and e.activation_fit_score <= max_fit_score]
    if not prunable: return 0
    non_innate = [e for e in chain_entities if e.entity_type not in innate_types]
    max_prune = max(1, len(non_innate) // 2)
    prunable.sort(key=lambda e: e.utility)
    to_prune = prunable[:max_prune]
    prune_ids = {id(e) for e in to_prune}
    brain.perceptrons = [p for p in brain.perceptrons if id(p) not in prune_ids]
    brain._cache_valid = False
    pruned = len(to_prune)
    if pruned > 0:
        print(f"  🧹 [{chain}] Pruned {pruned} low-utility entities "
              f"(fam≥{min_familiarity:.1f} fit≤{max_fit_score:.2f})")
    return pruned


def periodic_entity_pruning(brain):
    total_pruned = 0
    for chain in ['overworld', 'battle', 'party', 'bag', 'shared']:
        n_entities = brain.get_chain_entity_count(chain)
        capacity = brain.get_chain_entity_capacity(chain)
        if n_entities >= capacity * 0.7:
            total_pruned += prune_low_utility_entities(brain, chain)
    return total_pruned


# ============================================================================
# PIPELINE POOL PRUNING
# ============================================================================

def prune_pipeline_pools(brain):
    total_pruned = 0
    for pid, pipeline in brain.pipelines.items():
        for i, pool in enumerate(pipeline.pools):
            pool_perceptrons = [p for p in brain.perceptrons if p.pool_id == pool.pool_id]
            if len(pool_perceptrons) < pool.max_perceptrons * 0.7: continue
            prunable = [p for p in pool_perceptrons
                        if len(p.cluster_activations) >= 20
                        and p.familiarity >= 3.0
                        and p.activation_fit_score <= 0.05]
            if not prunable: continue
            max_prune = max(1, len(pool_perceptrons) // 3)
            prunable.sort(key=lambda p: p.utility)
            to_prune = prunable[:max_prune]
            for p in to_prune: pool.page_to_residual(p)
            prune_ids = {id(p) for p in to_prune}
            brain.perceptrons = [p for p in brain.perceptrons if id(p) not in prune_ids]
            brain._cache_valid = False
            total_pruned += len(to_prune)
            if to_prune:
                print(f"  🧹 [{pid}.{pool.name}] Pruned {len(to_prune)} → residual "
                      f"(pool: {len(pool_perceptrons) - len(to_prune)} remain, residual: {len(pool.residual)})")
    return total_pruned


# ============================================================================
# MEMORY CLEANUP
# ============================================================================

def cleanup_memory(brain):
    if len(brain.location_memory) > 500:
        sorted_locs = sorted(brain.location_memory.items(), key=lambda x: x[1], reverse=True)
        brain.location_memory = dict(sorted_locs[:400])
        print(f"  🧹 Location memory trimmed to 400")
    if len(brain.location_novelty) > 500:
        sorted_nov = sorted(brain.location_novelty.items(), key=lambda x: x[1], reverse=True)
        brain.location_novelty = dict(sorted_nov[:400])

    for map_id, memory in brain.exploration_memory.items():
        ti = memory.get('tile_interactions', {})
        if len(ti) > 200:
            to_remove = [tk for tk, td in ti.items()
                         if td.get('exhausted', False)
                         and not any(td.get('direction_successes', {}).get(d, 0) > 0 for d in range(4))]
            for tk in to_remove[:50]: del ti[tk]
            if to_remove: print(f"  🧹 Map {map_id}: removed {min(len(to_remove), 50)} exhausted tiles")

    periodic_entity_pruning(brain)
    prune_pipeline_pools(brain)
    brain.prune_stale_move_knowledge()
    brain.prune_stale_item_knowledge()

    if brain.battles_since_last_clustering >= brain.CLUSTERING_BATTLE_INTERVAL:
        brain.run_type_clustering()

    brain.check_revenge_readiness()


# ============================================================================
# LEARNING CORE HELPERS
# ============================================================================

def enforce_utility_floors(brain):
    for a in brain.actions():
        floor = brain.MOVE_UTILITY_FLOOR if a.group == "move" else brain.INTERACT_UTILITY_FLOOR
        a.utility = max(a.utility, floor)


def get_spawn_threshold_adaptive(brain, error_type='combined', percentile=50):
    history = {'numeric': brain.numeric_error_history, 'visual': brain.visual_error_history}.get(
        error_type, brain.error_history)
    return max(0.001, np.percentile(history, percentile)) if len(history) >= 100 else 0.0005


def stagnation_level(brain, window=10):
    if len(brain.prev_learning_states) < window: return 0.0
    recent = list(brain.prev_learning_states)[-window:]
    diffs = []
    for i in range(1, len(recent)):
        a, b = recent[i], recent[i-1]
        min_dim = min(len(a), len(b))
        diffs.append(np.linalg.norm(a[:min_dim] - b[:min_dim]))
    return 1.0 - np.tanh(np.mean(diffs) * 2.0)


def predict_future_error(brain, state, action, context_state, raw_position=None):
    entity_novelty = np.mean([e.predict(state) * e.utility
                              for e in brain.entities(chain="overworld")]) if brain.entities(chain="overworld") else 0.5
    shared_ents = brain.entities(chain="shared")
    if shared_ents:
        shared_signal = np.mean([e.predict(state) * e.utility for e in shared_ents])
        entity_novelty = entity_novelty * 0.7 + shared_signal * 0.3

    ow_pipeline = brain.overworld_pipeline
    if ow_pipeline.active:
        ow_output = ow_pipeline.pools[-2].get_cached_output()
        if np.any(ow_output != 0):
            pipeline_signal = np.mean(np.abs(ow_output))
            entity_novelty = entity_novelty * 0.5 + pipeline_signal * 0.5

    combined = entity_novelty * 0.7 + action.utility * 0.3

    current_map = int(context_state[2])
    loc = brain.get_location_key(*(raw_position if raw_position else
                                    (context_state[0]*255, context_state[1]*255)), current_map)

    map_debt = min(brain.map_novelty_debt.get(current_map, 0.0), brain.MAX_MAP_DEBT)
    loc_debt = min(brain.location_novelty.get(loc, 0.0), brain.MAX_LOCATION_DEBT)
    total_debt = map_debt + brain.get_temp_debt(current_map) + loc_debt * 0.5
    total_debt += brain.bounding_rect_debt * 0.5

    combined *= 1.0 / (1.0 + total_debt * 5.0)

    if action.action == brain.current_repeated_action and brain.consecutive_action_count > brain.LEARNING_SLOWDOWN_START:
        combined *= 1.0 / (1.0 + (brain.consecutive_action_count - brain.LEARNING_SLOWDOWN_START) * 0.15)
    if brain.detected_pattern and action.action in brain.detected_pattern:
        combined *= 1.0 / (1.0 + brain.pattern_repeat_count * 0.2)

    return combined + np.random.randn() * 0.05


def compute_multi_modal_error(brain, state, next_state):
    diffs = [abs(next_state[i] - state[i]) for i in range(min(8, len(state), len(next_state)))]
    weights = [0.5, 0.5, 10.0, 5.0, 3.0, 2.0, 1.5, 0.3]
    weighted = sum(d * w for d, w in zip(diffs, weights)) + np.linalg.norm(next_state[8:] - state[8:]) * 2.0
    numeric = sum(diffs)
    visual = np.linalg.norm(next_state[8:] - state[8:])
    return weighted, numeric, visual


# ============================================================================
# PIPELINE LEARNING (generic forward + backward + spawn)
# ============================================================================

def learn_pipeline(brain, pipeline_id, raw_input, prev_raw_input=None,
                   error_scale=1.0, game_state_data=None):
    pipeline = brain.pipelines.get(pipeline_id)
    if pipeline is None: return np.zeros(Pool.DEFAULT_OUTPUT_WIDTH), 0.0, False

    output, active = pipeline.forward(raw_input, brain.perceptrons)
    if prev_raw_input is None: return output, 0.0, active

    min_dim = min(len(raw_input), len(prev_raw_input))
    error = np.linalg.norm(raw_input[:min_dim] - prev_raw_input[:min_dim]) * error_scale
    pipeline.backward(error, brain.perceptrons)

    for i, pool in enumerate(pipeline.pools):
        if pool.needs_spawn(error):
            n_current = pool.get_perceptron_count(brain.perceptrons)
            if n_current < pool.max_perceptrons:
                layer_input = pipeline._layer_inputs[i] if i < len(pipeline._layer_inputs) else raw_input
                brain.spawn_into_pipeline_pool(pipeline_id, i, layer_input,
                                               game_state_data=game_state_data)

    return output, error, active


# ============================================================================
# CHAIN-GENERIC LEARNING
# ============================================================================

def learn_chain(brain, chain, learning_state, next_learning_state, error_scale=1.0):
    if learning_state.shape != next_learning_state.shape:
        max_dim = max(len(learning_state), len(next_learning_state))
        learning_state = np.pad(learning_state, (0, max(0, max_dim - len(learning_state))))
        next_learning_state = np.pad(next_learning_state, (0, max(0, max_dim - len(next_learning_state))))

    diff = next_learning_state - learning_state
    error = np.linalg.norm(diff) * error_scale

    chain_history = brain.get_chain_error_history(chain)
    chain_history.append(error)

    chain_actions = brain.actions(chain=chain); chain_entities = brain.entities(chain=chain)
    shared_actions = brain.actions(chain="shared"); shared_entities = brain.entities(chain="shared")
    all_chain_perceptrons = chain_actions + chain_entities + shared_actions + shared_entities

    for p in all_chain_perceptrons: p.update(learning_state, error, stagnation=0.0)

    spawn_threshold = brain.get_chain_spawn_threshold(chain, percentile=75)
    if error > spawn_threshold and len(chain_history) >= 50:
        n_ents = brain.get_chain_entity_count(chain)
        cap = brain.get_chain_entity_capacity(chain)
        if n_ents < cap * 1.5:
            brain.spawn_entity_for_chain(chain, learning_state)

    if chain == "battle": brain.prev_battle_learning_states.append(learning_state)
    elif chain == "party": brain.prev_party_learning_states.append(learning_state)
    elif chain == "bag": brain.prev_bag_learning_states.append(learning_state)

    return error


def learn_battle_chain(brain, battle_data, party_data, turn_count):
    current_state = build_learning_state_battle(battle_data, party_data, turn_count)
    if not brain.innate_entities_spawned_battle:
        brain.spawn_innate_battle_entities(current_state)

    prev_state = brain.prev_battle_learning_states[-1] if len(brain.prev_battle_learning_states) > 0 else None

    game_data = {
        'enemy_species': battle_data.get('enemy_species', -1),
        'player_species': battle_data.get('player_species', -1),
    }
    pipeline_output, pipeline_error, pipeline_active = learn_pipeline(
        brain, "battle", current_state, prev_state, error_scale=1.0, game_state_data=game_data)

    # Zero-damage penalty for action_selection pool
    if brain.battle_no_damage_turns >= 2 and brain.last_move_slot >= 0:
        action_pool = brain.battle_pipeline.pools[3]
        pool_perceptrons = [p for p in brain.perceptrons if p.pool_id == action_pool.pool_id]
        if pool_perceptrons and len(brain.prev_battle_learning_states) > 0:
            prev_learn_state = brain.prev_battle_learning_states[-1]
            penalty = -0.5 * brain.battle_no_damage_turns
            for p in pool_perceptrons: p.update(prev_learn_state, penalty)

    chain_error = 0.0
    if prev_state is not None:
        chain_error = learn_chain(brain, "battle", prev_state, current_state)
    else:
        brain.prev_battle_learning_states.append(current_state)

    authority = brain.battle_pipeline.get_total_authority()
    if authority > 0 and pipeline_error > 0:
        return pipeline_error * authority + chain_error * (1.0 - authority)
    return chain_error


def learn_party_chain(brain, party_data, active_slot=-1):
    current_state = build_learning_state_party(party_data, active_slot)
    prev_state = brain.prev_party_learning_states[-1] if len(brain.prev_party_learning_states) > 0 else None

    pipeline_output, pipeline_error, pipeline_active = learn_pipeline(
        brain, "party", current_state, prev_state, error_scale=0.5)

    chain_error = 0.0
    if prev_state is not None:
        chain_error = learn_chain(brain, "party", prev_state, current_state, error_scale=0.5)
    else:
        brain.prev_party_learning_states.append(current_state)

    authority = brain.party_pipeline.get_total_authority()
    if authority > 0 and pipeline_error > 0:
        return pipeline_error * authority + chain_error * (1.0 - authority)
    return chain_error


def learn_bag_chain(brain, bag_data, party_data, menu_data, in_battle=False):
    current_state = build_learning_state_bag(bag_data, party_data, menu_data, in_battle)
    prev_state = brain.prev_bag_learning_states[-1] if len(brain.prev_bag_learning_states) > 0 else None

    game_data = {'pocket': bag_data.get('pocket', -1)}
    pipeline_output, pipeline_error, pipeline_active = learn_pipeline(
        brain, "bag", current_state, prev_state, error_scale=0.5, game_state_data=game_data)

    chain_error = 0.0
    if prev_state is not None:
        chain_error = learn_chain(brain, "bag", prev_state, current_state, error_scale=0.5)
    else:
        brain.prev_bag_learning_states.append(current_state)

    authority = brain.bag_pipeline.get_total_authority()
    if authority > 0 and pipeline_error > 0:
        return pipeline_error * authority + chain_error * (1.0 - authority)
    return chain_error


# ============================================================================
# MAIN LEARN
# ============================================================================

def learn(brain, learning_state, next_learning_state, context_state, next_context_state,
          dead=False, raw_position=None, next_raw_position=None):
    if learning_state.shape != next_learning_state.shape:
        max_dim = max(len(learning_state), len(next_learning_state))
        learning_state = np.pad(learning_state, (0, max(0, max_dim - len(learning_state))))
        next_learning_state = np.pad(next_learning_state, (0, max(0, max_dim - len(next_learning_state))))

    if not brain.innate_entities_spawned_overworld:
        brain.spawn_innate_overworld_entities(learning_state)

    prev_context = brain.prev_context_states[-1] if brain.prev_context_states else None
    prev_raw = getattr(brain, '_last_raw_position', None)
    brain.update_exploration_tracking(context_state, prev_context, raw_position, prev_raw)
    brain._last_raw_position = raw_position
    brain._prev_game_state_raw = brain.game_state_raw

    weighted_error, numeric_error, visual_error = compute_multi_modal_error(
        brain, learning_state, next_learning_state)
    brain.error_history.append(weighted_error)
    brain.numeric_error_history.append(numeric_error)
    brain.visual_error_history.append(visual_error)

    # Overworld pipeline
    if context_state[3] <= 0.5 and context_state[4] <= 0.5:
        prev_ow = brain.prev_learning_states[-1] if len(brain.prev_learning_states) > 0 else None
        game_data = {'map_id': int(context_state[2])}
        learn_pipeline(brain, "overworld", learning_state, prev_ow,
                       error_scale=1.0, game_state_data=game_data)

    # Overworld entity spawning (legacy)
    spawn_threshold = get_spawn_threshold_adaptive(brain, 'combined', percentile=75)
    if weighted_error > spawn_threshold and len(brain.error_history) >= 100:
        if context_state[4] <= 0.5 and context_state[3] <= 0.5:
            brain.spawn_entity_for_chain("overworld", learning_state, context_state, raw_position)

    current_map = int(context_state[2])
    loc = brain.get_location_key(*(raw_position if raw_position else
                                    (context_state[0]*255, context_state[1]*255)), current_map)

    brain.visited_maps[current_map] = brain.visited_maps.get(current_map, 0) + 1
    brain.location_memory[loc] = brain.location_memory.get(loc, 0) + 1

    if brain.visited_maps[current_map] > 10:
        brain.map_novelty_debt[current_map] = min(brain.MAX_MAP_DEBT,
            brain.map_novelty_debt.get(current_map, 0.0) + 0.05 * (brain.visited_maps[current_map] - 10))
    if brain.location_memory[loc] > 15:
        brain.location_novelty[loc] = min(brain.MAX_LOCATION_DEBT,
            brain.location_novelty.get(loc, 0.0) + 0.1 * (brain.location_memory[loc] - 15))

    if brain.visited_maps[current_map] > 30: weighted_error *= 0.5
    if brain.location_memory[loc] > 25: weighted_error *= 0.7

    stag = stagnation_level(brain)
    learning_mult = brain.get_learning_multiplier(brain.last_action) if brain.last_action else 1.0
    if brain.detected_pattern and brain.last_action in brain.detected_pattern: learning_mult *= 0.5

    overworld_perceptrons = brain.actions(chain="overworld") + brain.entities(chain="overworld")
    shared_perceptrons = brain.actions(chain="shared") + brain.entities(chain="shared")
    legacy_ow = [p for p in overworld_perceptrons if p.pool_id is None]
    legacy_shared = [p for p in shared_perceptrons if p.pool_id is None]

    for p in legacy_ow + legacy_shared:
        mult = learning_mult if (p.kind == "action" and p.action == brain.last_action) else 1.0
        if p.kind == "action" and brain.detected_pattern and p.action in brain.detected_pattern: mult *= 0.5
        p.update(learning_state, weighted_error * mult, stagnation=stag)

    for a in brain.actions():
        if a.action in ['Start', 'Select'] and a.weights is not None: a.weights *= 0.999

    brain.apply_repetition_penalty()
    brain.apply_pattern_penalty()
    enforce_utility_floors(brain)

    # Movement boost
    if prev_context is not None and np.linalg.norm(context_state[:2] - prev_context[:2]) > 0.001:
        if brain.last_action and brain.consecutive_action_count < brain.PENALTY_THRESHOLD:
            if context_state[4] <= 0.5 and context_state[3] <= 0.5:
                boost = 1.08
                if brain.nav_active: boost = 1.0 + (0.08 * brain.NAV_LEARNING_DAMPENING)
                elif raw_position and brain.is_near_map_edge(*raw_position): boost = 1.15
                for a in brain.actions(chain="overworld") + brain.actions(chain="shared"):
                    if a.action == brain.last_action: a.utility = min(a.utility * boost, 2.0); break

    # Dispatch to active chains
    if context_state[3] > 0.5 and brain.has_battle_data():
        learn_battle_chain(brain, brain.battle_data, brain.party_data, brain.turn_count)
    if brain.party_menu_active:
        active_slot = brain.get_active_slot_index()
        learn_party_chain(brain, brain.party_data, active_slot)
    if brain.bag_thread_active:
        in_battle = context_state[3] > 0.5
        learn_bag_chain(brain, brain.bag_data, brain.party_data, brain.menu_data, in_battle)

    if brain.timestep % 100 == 0: brain.check_revenge_readiness()
    if brain.timestep % 1000 == 0 and brain.timestep > 0: cleanup_memory(brain)

    if brain.timestep % brain.SAVE_INTERVAL == 0:
        brain.save_exploration_memory()
        if brain.roster_dirty: brain.save_roster()
        if brain.move_knowledge_dirty: brain.save_move_knowledge()
        if brain.item_knowledge_dirty: brain.save_item_knowledge()
        if brain.type_clusters_dirty: brain.save_type_clusters()

    brain.action_history.append(brain.last_action)


# ============================================================================
# STATE LOGGING
# ============================================================================

def log_state(brain, learning_state, context_state):
    brain.prev_learning_states.append(learning_state)
    brain.prev_context_states.append(context_state)

def update_position(brain, x, y):
    brain.last_positions.append((int(x), int(y)))


# ============================================================================
# SAVE / LOAD MODEL CHECKPOINT
# ============================================================================

def save_model_checkpoint(brain, filepath):
    model = {
        "timestep": brain.timestep,
        "perceptrons": {"actions": [], "entities": []},
        "debt_tracking": {
            "map_novelty_debt": {str(k): v for k, v in brain.map_novelty_debt.items()},
            "location_novelty": {str(k): v for k, v in brain.location_novelty.items()},
            "visited_maps": {str(k): v for k, v in brain.visited_maps.items()}
        },
        "control_mode": brain.control_mode,
        "markov_stats": {"markov_action_count": brain.markov_action_count, "curiosity_action_count": brain.curiosity_action_count},
        "blend_stats": {"blend_count": brain.blend_count, "last_blend_tier": brain.blend_tier},
        "battle_stats": {"battle_action_count": brain.battle_action_count, "battle_markov_action_count": brain.battle_markov_action_count, "current_battle_id": brain.current_battle_id},
        "bag_stats": {"bag_thread_total_actions": brain.bag_thread_total_actions, "bag_thread_markov_actions": brain.bag_thread_markov_actions},
        "prep_stats": {"prep_total_count": brain.prep_total_count, "prep_success_count": brain.prep_success_count},
        "start_menu_stats": {"start_menu_total_actions": brain.start_menu_total_actions, "start_menu_markov_actions": brain.start_menu_markov_actions},
        "chain_stats": {"entity_spawn_counts": brain.entity_spawn_counts, "entity_merge_counts": brain.entity_merge_counts, "entity_capacities": dict(brain.ENTITY_CAPACITY)},
        "roster": {}, "move_knowledge": {"player_moves": {}, "enemy_moves": {}},
        "item_knowledge": {}, "map_battle_stats": {},
        "battle_tracking": {"battle_low_hp_exits": brain.battle_low_hp_exits},
        "type_clusters": {
            "move_type_clusters": {str(k): v for k, v in brain.move_type_clusters.items()},
            "species_type_clusters": {str(k): v for k, v in brain.species_type_clusters.items()},
            "cluster_effectiveness": brain.cluster_effectiveness,
            "move_to_cluster": {str(k): v for k, v in brain.move_to_cluster.items()},
            "species_to_cluster": {str(k): v for k, v in brain.species_to_cluster.items()},
            "clustering_run_count": brain.clustering_run_count,
        },
        "pipelines": {pid: p.get_save_state() for pid, p in brain.pipelines.items()},
        "revenge_targets": brain.revenge_targets,
    }

    for k, v in brain.roster.items():
        e = v.copy()
        if isinstance(e.get('fingerprint'), tuple): e['fingerprint'] = list(e['fingerprint'])
        model["roster"][str(k)] = e
    for mk, mv in brain.move_knowledge.items():
        c = mv.copy(); c['vs_species'] = {str(sk): sv for sk, sv in mv.get('vs_species', {}).items()}
        model["move_knowledge"]["player_moves"][str(mk)] = c
    for ek, ev in brain.enemy_move_knowledge.items():
        model["move_knowledge"]["enemy_moves"][str(ek)] = ev
    model["item_knowledge"] = {str(k): v for k, v in brain.item_knowledge.items()}
    model["map_battle_stats"] = brain.get_map_battle_stats_for_save()

    for a in brain.actions():
        model["perceptrons"]["actions"].append({
            "action": a.action, "group": a.group, "chain": a.chain,
            "utility": float(a.utility),
            "weights_shape": len(a.weights) if a.weights is not None else 0,
            "weights_nonzero": [[i, float(v)] for i, v in enumerate(a.weights) if abs(v) > 1e-10] if a.weights is not None else [],
            "learning_rate": float(a.learning_rate), "familiarity": float(a.familiarity),
            "activation_state": a.get_activation_state(), "pool_state": a.get_pool_state(),
        })
    for e in brain.entities():
        model["perceptrons"]["entities"].append({
            "entity_type": e.entity_type, "chain": e.chain,
            "utility": float(e.utility),
            "weights_shape": len(e.weights) if e.weights is not None else 0,
            "weights_nonzero": [[i, float(v)] for i, v in enumerate(e.weights) if abs(v) > 1e-10] if e.weights is not None else [],
            "familiarity": float(e.familiarity),
            "activation_state": e.get_activation_state(), "pool_state": e.get_pool_state(),
        })

    with open(filepath, 'w') as f: json.dump(model, f, indent=2)
    if brain.roster_dirty: brain.save_roster()
    if brain.move_knowledge_dirty: brain.save_move_knowledge()
    if brain.item_knowledge_dirty: brain.save_item_knowledge()
    if brain.type_clusters_dirty: brain.save_type_clusters()
    brain.save_residual_file()


def load_taught_model(brain, filepath):
    try:
        with open(filepath, 'r') as f: model = json.load(f)
        if "perceptrons" not in model: print(f"  ⚠️ Model empty, starting fresh"); return 0

        for saved_action in model["perceptrons"]["actions"]:
            for a in brain.actions():
                if a.action == saved_action["action"]:
                    a.utility = saved_action["utility"]; a.learning_rate = saved_action.get("learning_rate", 0.01)
                    a.familiarity = saved_action.get("familiarity", 0.0); a.chain = saved_action.get("chain", "shared")
                    if saved_action.get("weights_nonzero"):
                        dim = saved_action.get("weights_shape", 1376); a.weights = np.zeros(dim)
                        for idx, val in saved_action["weights_nonzero"]:
                            if idx < dim: a.weights[idx] = val
                    a.set_activation_state(saved_action.get("activation_state"))
                    a.set_pool_state(saved_action.get("pool_state")); break
                if a.action in ['Start', 'Select'] and a.weights is not None:
                    a.weights = np.zeros(len(a.weights)); a.utility = 0.05

        for saved_entity in model["perceptrons"].get("entities", []):
            matched = False
            for e in brain.entities():
                if e.entity_type == saved_entity["entity_type"]:
                    e.utility = saved_entity.get("utility", 1.0); e.familiarity = saved_entity.get("familiarity", 0.0)
                    e.chain = saved_entity.get("chain", "shared")
                    if saved_entity.get("weights_nonzero"):
                        dim = saved_entity.get("weights_shape", 1376); e.weights = np.zeros(dim)
                        for idx, val in saved_entity["weights_nonzero"]:
                            if idx < dim: e.weights[idx] = val
                    e.set_activation_state(saved_entity.get("activation_state"))
                    e.set_pool_state(saved_entity.get("pool_state")); matched = True; break
            if not matched and saved_entity.get("weights_nonzero"):
                chain = saved_entity.get("chain", "shared")
                entity = Perceptron("entity", entity_type=saved_entity["entity_type"], chain=chain)
                dim = saved_entity.get("weights_shape", 1376); entity.weights = np.zeros(dim)
                for idx, val in saved_entity["weights_nonzero"]:
                    if idx < dim: entity.weights[idx] = val
                entity.utility = saved_entity.get("utility", 1.0); entity.familiarity = saved_entity.get("familiarity", 0.0)
                entity.set_activation_state(saved_entity.get("activation_state"))
                entity.set_pool_state(saved_entity.get("pool_state")); brain.add(entity)

        if "debt_tracking" in model:
            debt = model["debt_tracking"]
            brain.map_novelty_debt = {int(k): v for k, v in debt.get("map_novelty_debt", {}).items()}
            brain.visited_maps = {int(k): v for k, v in debt.get("visited_maps", {}).items()}
            for k, v in debt.get("location_novelty", {}).items(): brain.location_novelty[eval(k)] = v
        if "roster" in model:
            brain.roster = {int(k): v for k, v in model["roster"].items()}
            for v in brain.roster.values():
                if isinstance(v.get('fingerprint'), list): v['fingerprint'] = tuple(v['fingerprint'])
        if "move_knowledge" in model:
            mk_data = model["move_knowledge"]; brain.move_knowledge = {}
            for mk, mv in mk_data.get('player_moves', {}).items():
                mv['vs_species'] = {int(sk): sv for sk, sv in mv.get('vs_species', {}).items()}
                brain.move_knowledge[int(mk)] = mv
            brain.enemy_move_knowledge = {int(k): v for k, v in mk_data.get('enemy_moves', {}).items()}
        if "item_knowledge" in model: brain.item_knowledge = {int(k): v for k, v in model["item_knowledge"].items()}
        if "map_battle_stats" in model: brain.load_map_battle_stats(model["map_battle_stats"])
        if "battle_tracking" in model: brain.battle_low_hp_exits = model["battle_tracking"].get("battle_low_hp_exits", 0)
        if "chain_stats" in model:
            cs = model["chain_stats"]
            brain.entity_spawn_counts = cs.get("entity_spawn_counts", brain.entity_spawn_counts)
            brain.entity_merge_counts = cs.get("entity_merge_counts", brain.entity_merge_counts)
            for chain, cap in cs.get("entity_capacities", {}).items(): brain.ENTITY_CAPACITY[chain] = cap
        if "type_clusters" in model:
            tc = model["type_clusters"]
            brain.move_type_clusters = {int(k): v for k, v in tc.get('move_type_clusters', {}).items()}
            brain.species_type_clusters = {int(k): v for k, v in tc.get('species_type_clusters', {}).items()}
            brain.cluster_effectiveness = tc.get('cluster_effectiveness', {})
            brain.move_to_cluster = {int(k): int(v) for k, v in tc.get('move_to_cluster', {}).items()}
            brain.species_to_cluster = {int(k): int(v) for k, v in tc.get('species_to_cluster', {}).items()}
            brain.clustering_run_count = tc.get('clustering_run_count', 0)
        if "pipelines" in model:
            for pid, p_state in model["pipelines"].items():
                pipeline = brain.pipelines.get(pid)
                if pipeline: pipeline.load_save_state(p_state)
        if "revenge_targets" in model: brain.revenge_targets = model["revenge_targets"]

        loaded_ts = model.get("timestep", 0); brain.timestep = loaded_ts
        return loaded_ts
    except Exception as e:
        print(f"  ⚠️ Error loading model: {e}, starting fresh"); return 0


def initialize_from_taught_model(brain, filepath):
    if not Path(filepath).exists(): print(f"  No taught model at {filepath}"); return 0
    try:
        with open(filepath, 'r') as f: model = json.load(f)
        if "perceptrons" not in model: print(f"  ⚠️ Taught model empty or invalid"); return 0
        taught_timestep = model.get("timestep", 0)

        actions_loaded = 0
        for saved_action in model["perceptrons"].get("actions", []):
            for a in brain.actions():
                if a.action == saved_action["action"]:
                    a.utility = saved_action["utility"]; a.learning_rate = saved_action.get("learning_rate", 0.01)
                    a.familiarity = saved_action.get("familiarity", 0.0); a.chain = saved_action.get("chain", "shared")
                    if saved_action.get("weights_nonzero"):
                        dim = saved_action.get("weights_shape", 1376); a.weights = np.zeros(dim)
                        for idx, val in saved_action["weights_nonzero"]:
                            if idx < dim: a.weights[idx] = val
                    a.set_activation_state(saved_action.get("activation_state"))
                    a.set_pool_state(saved_action.get("pool_state")); actions_loaded += 1; break

        innate_types = {"sense_menu", "sense_battle", "sense_movement", "sense_map_transition",
                        "battle_hp_crisis", "battle_enemy_weak", "battle_species_match",
                        "battle_status", "battle_trainer"}
        entities_loaded = 0
        for saved_entity in model["perceptrons"].get("entities", []):
            et = saved_entity.get("entity_type", "unknown"); chain = saved_entity.get("chain", "shared")
            if et in innate_types:
                for e in brain.entities():
                    if e.entity_type == et:
                        e.utility = saved_entity.get("utility", 1.0); e.familiarity = saved_entity.get("familiarity", 0.0)
                        e.learning_rate = saved_entity.get("learning_rate", 0.01); e.chain = chain
                        if saved_entity.get("weights_nonzero"):
                            dim = saved_entity.get("weights_shape", 1376); e.ensure_weights(dim); e.weights = np.zeros(dim)
                            for idx, val in saved_entity["weights_nonzero"]:
                                if idx < dim: e.weights[idx] = val
                        e.set_activation_state(saved_entity.get("activation_state"))
                        e.set_pool_state(saved_entity.get("pool_state")); entities_loaded += 1; break
                continue
            if saved_entity.get("weights_nonzero"):
                entity = Perceptron("entity", entity_type=et, chain=chain)
                dim = saved_entity.get("weights_shape", 1376); entity.weights = np.zeros(dim)
                for idx, val in saved_entity["weights_nonzero"]:
                    if idx < dim: entity.weights[idx] = val
                entity.utility = saved_entity.get("utility", 1.0); entity.familiarity = saved_entity.get("familiarity", 0.0)
                entity.learning_rate = saved_entity.get("learning_rate", 0.01)
                entity.set_activation_state(saved_entity.get("activation_state"))
                entity.set_pool_state(saved_entity.get("pool_state")); brain.add(entity); entities_loaded += 1

        ow_innate = {"sense_menu", "sense_battle", "sense_movement", "sense_map_transition"}
        bat_innate = {"battle_hp_crisis", "battle_enemy_weak", "battle_species_match", "battle_status", "battle_trainer"}
        restored_types = {se.get("entity_type") for se in model["perceptrons"].get("entities", [])}
        if ow_innate.issubset(restored_types): brain.innate_entities_spawned_overworld = True; brain.innate_entities_spawned = True
        if bat_innate.issubset(restored_types): brain.innate_entities_spawned_battle = True

        cs = model.get("chain_stats", {})
        if cs:
            brain.entity_spawn_counts = cs.get("entity_spawn_counts", brain.entity_spawn_counts)
            brain.entity_merge_counts = cs.get("entity_merge_counts", brain.entity_merge_counts)
            for chain, cap in cs.get("entity_capacities", {}).items(): brain.ENTITY_CAPACITY[chain] = cap
        if "map_battle_stats" in model: brain.load_map_battle_stats(model["map_battle_stats"])
        if "type_clusters" in model:
            tc = model["type_clusters"]
            brain.move_type_clusters = {int(k): v for k, v in tc.get('move_type_clusters', {}).items()}
            brain.species_type_clusters = {int(k): v for k, v in tc.get('species_type_clusters', {}).items()}
            brain.cluster_effectiveness = tc.get('cluster_effectiveness', {})
            brain.move_to_cluster = {int(k): int(v) for k, v in tc.get('move_to_cluster', {}).items()}
            brain.species_to_cluster = {int(k): int(v) for k, v in tc.get('species_to_cluster', {}).items()}
            brain.clustering_run_count = tc.get('clustering_run_count', 0)
        if "pipelines" in model:
            for pid, p_state in model["pipelines"].items():
                pipeline = brain.pipelines.get(pid)
                if pipeline: pipeline.load_save_state(p_state)

        brain.timestep = 0
        print(f"  🎓 BOOTSTRAPPED FROM TAUGHT MODEL:")
        print(f"     Source: {filepath}")
        print(f"     Human played: {taught_timestep} steps")
        print(f"     Actions: {actions_loaded} | Entities: {entities_loaded}")
        return taught_timestep
    except Exception as e:
        print(f"  ⚠️ Error bootstrapping from taught model: {e}"); return 0


def merge_taught_exploration(brain, taught_filepath):
    if not Path(taught_filepath).exists(): print(f"  No taught exploration at {taught_filepath}"); return
    with open(taught_filepath, 'r') as f: taught_data = json.load(f)
    ta, ia = 0, 0
    for map_key, taught_map in taught_data.items():
        map_id = int(map_key.replace('map_', ''))
        ai_map = brain.get_current_map_memory(map_id)
        for tt in taught_map.get('transitions', []):
            tp, td = tuple(tt['position']), tt['direction']
            if not any(tuple(e['position']) == tp and e['direction'] == td for e in ai_map['transitions']):
                ai_map['transitions'].append(tt); ta += 1
        for ti in taught_map.get('interactable_objects', []):
            if ti not in ai_map['interactable_objects']: ai_map['interactable_objects'].append(ti); ia += 1
    print(f"  Merged: {ta} transitions, {ia} interactables")


# ============================================================================
# ATTACH ALL METHODS TO BRAIN CLASS
# ============================================================================

def attach_to_brain(BrainClass):
    """Attach all learning functions as methods on the Brain class."""
    # Entity spawning wrappers
    BrainClass.spawn_entity_from_novelty = spawn_entity_from_novelty
    BrainClass.check_entity_capacity = check_entity_capacity
    BrainClass.cluster_entities = cluster_entities
    BrainClass.spawn_innate_entities = spawn_innate_entities

    # Pruning
    BrainClass.prune_low_utility_entities = prune_low_utility_entities
    BrainClass.periodic_entity_pruning = periodic_entity_pruning
    BrainClass.prune_pipeline_pools = prune_pipeline_pools
    BrainClass.cleanup_memory = cleanup_memory

    # Learning helpers
    BrainClass.enforce_utility_floors = enforce_utility_floors
    BrainClass.get_spawn_threshold_adaptive = get_spawn_threshold_adaptive
    BrainClass.stagnation_level = stagnation_level
    BrainClass.predict_future_error = predict_future_error
    BrainClass.compute_multi_modal_error = compute_multi_modal_error

    # Pipeline learning
    BrainClass.learn_pipeline = learn_pipeline

    # Chain learning
    BrainClass.learn_chain = learn_chain
    BrainClass.learn_battle_chain = learn_battle_chain
    BrainClass.learn_party_chain = learn_party_chain
    BrainClass.learn_bag_chain = learn_bag_chain

    # Main learn
    BrainClass.learn = learn

    # State logging
    BrainClass.log_state = log_state
    BrainClass.update_position = update_position

    # Save/load
    BrainClass.save_model_checkpoint = save_model_checkpoint
    BrainClass.load_taught_model = load_taught_model
    BrainClass.initialize_from_taught_model = initialize_from_taught_model
    BrainClass.merge_taught_exploration = merge_taught_exploration