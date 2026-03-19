# ============================================================================
# brain_data.py — Brain Data Management Methods (Cell 3.1C)
# ============================================================================
# All methods take `brain` as first argument. Attached via attach_to_brain().
#
# Contains:
#   - Chain-specific helpers (error history, spawn threshold, entity signal)
#   - Pipeline pool signal query
#   - Battle pipeline move score query
#   - Memory monitoring (activation observations, knowledge file sizes)
#   - Knowledge pruning
#   - Type chart discovery (Track A empirical clustering)
#   - Type chart persistence
#   - Ground truth type loading (Track B)
#   - Menu/bag/party data update
#   - Bag thread management
#   - Item knowledge (get, observe, record, categorize, persistence)
#   - Party data helpers
#   - Battle data management (update, start/end, menu state, turn tracking)
#   - Party menu thread
#   - Forced switch + running decision
#   - Roster management
#   - Move knowledge (record, enemy moves, scoring)
#   - Battle risk assessment
#   - Persistence (roster, moves, map stats, checkpoint helpers)
# ============================================================================

import json
import time
import numpy as np
from pathlib import Path

from constants import (
    ROSTER_FILE, MOVE_KNOWLEDGE_FILE, ITEM_KNOWLEDGE_FILE,
    TYPE_CLUSTERS_FILE, TYPE_DATA_FILE,
    BATTLE_CHAIN_DIM,
)
from state import (
    build_learning_state_battle, load_type_data, get_type_effectiveness,
)
from pool import Pool


# ============================================================================
# CHAIN-SPECIFIC HELPERS
# ============================================================================

def get_chain_error_history(brain, chain):
    if chain == "battle": return brain.battle_error_history
    elif chain == "party": return brain.party_error_history
    elif chain == "bag": return brain.bag_error_history
    else: return brain.error_history


def get_chain_spawn_threshold(brain, chain, percentile=75):
    history = get_chain_error_history(brain, chain)
    if len(history) >= 50:
        return max(0.001, np.percentile(history, percentile))
    return 0.0005


def get_chain_entity_signal(brain, chain, learning_state):
    chain_ents = brain.entities(chain=chain)
    if not chain_ents: return 0.5
    return np.mean([abs(e.predict(learning_state)) * e.utility for e in chain_ents])


# ============================================================================
# PIPELINE POOL SIGNAL QUERY
# ============================================================================

def get_pipeline_pool_signal(brain, pipeline_id, layer_index, input_state=None):
    pipeline = brain.pipelines.get(pipeline_id)
    if pipeline is None:
        return np.zeros(Pool.DEFAULT_OUTPUT_WIDTH), 0.0
    if layer_index < 0 or layer_index >= pipeline.num_layers:
        return np.zeros(Pool.DEFAULT_OUTPUT_WIDTH), 0.0
    pool = pipeline.pools[layer_index]
    if input_state is not None:
        output = pool.compute_output(input_state, brain.perceptrons)
        return output, pool.authority
    else:
        return pool.get_cached_output(), pool.authority


def query_battle_pipeline_move_scores(brain, battle_state):
    pipeline = brain.battle_pipeline
    total_pool_perceptrons = sum(
        pool.get_perceptron_count(brain.perceptrons) for pool in pipeline.pools[:4]
    )
    if total_pool_perceptrons == 0: return None

    current_input = battle_state
    for i in range(min(4, pipeline.num_layers)):
        pool = pipeline.pools[i]
        current_input = pool.compute_output(current_input, brain.perceptrons)

    action_pool = pipeline.pools[3] if pipeline.num_layers > 3 else None
    if action_pool is None or action_pool.authority < 0.1: return None

    output = current_input
    move_scores = []
    for slot in range(4):
        if slot < len(output):
            move_scores.append((slot, float(output[slot])))
        else:
            move_scores.append((slot, 0.0))

    move_scores.sort(key=lambda x: x[1], reverse=True)
    return move_scores


# ============================================================================
# MEMORY MONITORING
# ============================================================================

def get_total_activation_observations(brain):
    return sum(len(p.activation_observations) for p in brain.perceptrons)


def get_activation_observation_stats(brain):
    stats = {}
    for chain in ['overworld', 'battle', 'party', 'bag', 'shared']:
        chain_perceptrons = [p for p in brain.perceptrons if p.chain == chain]
        if not chain_perceptrons: continue
        obs_count = sum(len(p.activation_observations) for p in chain_perceptrons)
        n_perceptrons = len(chain_perceptrons)
        estimated_bytes = obs_count * 80
        stats[chain] = {
            'perceptrons': n_perceptrons, 'observations': obs_count,
            'avg_per_perceptron': obs_count / max(1, n_perceptrons),
            'estimated_bytes': estimated_bytes,
        }
    total_obs = sum(s['observations'] for s in stats.values())
    total_bytes = sum(s['estimated_bytes'] for s in stats.values())
    stats['_total'] = {
        'observations': total_obs, 'estimated_bytes': total_bytes,
        'estimated_mb': total_bytes / (1024 * 1024),
    }
    return stats


def get_knowledge_file_sizes(brain):
    files = {
        'model_checkpoint': Path(brain.EXPLORATION_MEMORY_FILE).parent / "model_checkpoint.json",
        'exploration_memory': brain.EXPLORATION_MEMORY_FILE,
        'roster': ROSTER_FILE,
        'move_knowledge': MOVE_KNOWLEDGE_FILE,
        'item_knowledge': ITEM_KNOWLEDGE_FILE,
        'type_clusters': TYPE_CLUSTERS_FILE,
        'residual_perceptrons': brain.RESIDUAL_FILE,
    }
    sizes = {}
    for name, filepath in files.items():
        try:
            sizes[name] = Path(filepath).stat().st_size if Path(filepath).exists() else 0
        except Exception:
            sizes[name] = -1
    sizes['_total'] = sum(v for v in sizes.values() if v > 0)
    return sizes


# ============================================================================
# KNOWLEDGE PRUNING
# ============================================================================

def prune_stale_move_knowledge(brain, min_uses=2, max_entries=500):
    if len(brain.move_knowledge) <= max_entries: return 0
    pruned = 0
    to_remove = [mid for mid, data in brain.move_knowledge.items() if data.get('total_uses', 0) < min_uses]
    for mid in to_remove:
        del brain.move_knowledge[mid]; pruned += 1
    if pruned > 0:
        brain.move_knowledge_dirty = True
        print(f"  🧹 Pruned {pruned} move knowledge entries (<{min_uses} uses)")
    return pruned


def prune_stale_item_knowledge(brain, min_uses=1, max_entries=200):
    if len(brain.item_knowledge) <= max_entries: return 0
    pruned = 0
    to_remove = [iid for iid, data in brain.item_knowledge.items()
                 if data.get('uses', 0) < min_uses and data.get('category', 'unknown') == 'unknown']
    for iid in to_remove:
        del brain.item_knowledge[iid]; pruned += 1
    if pruned > 0:
        brain.item_knowledge_dirty = True
        print(f"  🧹 Pruned {pruned} item knowledge entries (unused+unknown)")
    return pruned


# ============================================================================
# EMPIRICAL TYPE CHART DISCOVERY — TRACK A
# ============================================================================

def run_type_clustering(brain):
    eligible_moves = {}
    for move_id, data in brain.move_knowledge.items():
        vs = data.get('vs_species', {})
        reliable_species = {sp: sd for sp, sd in vs.items() if sd.get('uses', 0) >= 2}
        if len(reliable_species) >= brain.CLUSTERING_MIN_SPECIES_PER_MOVE:
            eligible_moves[move_id] = reliable_species

    if len(eligible_moves) < brain.CLUSTERING_MIN_MOVES: return

    all_species = sorted(set(sp for vs in eligible_moves.values() for sp in vs.keys()))
    species_idx = {sp: i for i, sp in enumerate(all_species)}
    n_species = len(all_species)
    if n_species < 2: return

    move_ids = sorted(eligible_moves.keys())
    n_moves = len(move_ids)
    damage_matrix = np.full((n_moves, n_species), 0.5)

    for mi, move_id in enumerate(move_ids):
        vs = eligible_moves[move_id]
        max_dmg = max((sd.get('avg', 0.0) for sd in vs.values()), default=1.0)
        if max_dmg <= 0: max_dmg = 1.0
        for sp, sd in vs.items():
            damage_matrix[mi, species_idx[sp]] = np.clip(sd.get('avg', 0.0) / max_dmg, 0.0, 1.0)

    # Cluster moves
    move_clusters, move_assigned, cluster_id = {}, set(), 0
    for i in range(n_moves):
        if i in move_assigned: continue
        group = [i]
        vec_i = damage_matrix[i]
        norm_i = np.linalg.norm(vec_i)
        if norm_i < 1e-10: continue
        for j in range(i + 1, n_moves):
            if j in move_assigned: continue
            vec_j = damage_matrix[j]
            norm_j = np.linalg.norm(vec_j)
            if norm_j < 1e-10: continue
            if np.dot(vec_i, vec_j) / (norm_i * norm_j) >= brain.CLUSTERING_SIMILARITY_THRESHOLD:
                group.append(j); move_assigned.add(j)
        if len(group) >= 1:
            move_assigned.add(i); move_clusters[cluster_id] = [move_ids[idx] for idx in group]; cluster_id += 1

    # Cluster species
    species_clusters, species_assigned, sp_cluster_id = {}, set(), 0
    for i in range(n_species):
        if i in species_assigned: continue
        group = [i]
        vec_i = damage_matrix[:, i]
        norm_i = np.linalg.norm(vec_i)
        if norm_i < 1e-10: continue
        for j in range(i + 1, n_species):
            if j in species_assigned: continue
            vec_j = damage_matrix[:, j]
            norm_j = np.linalg.norm(vec_j)
            if norm_j < 1e-10: continue
            if np.dot(vec_i, vec_j) / (norm_i * norm_j) >= brain.CLUSTERING_SIMILARITY_THRESHOLD:
                group.append(j); species_assigned.add(j)
        if len(group) >= 1:
            species_assigned.add(i); species_clusters[sp_cluster_id] = [all_species[idx] for idx in group]; sp_cluster_id += 1

    # Effectiveness
    cluster_eff = {}
    for mc_id, mc_moves in move_clusters.items():
        mc_indices = [move_ids.index(m) for m in mc_moves if m in move_ids]
        for sc_id, sc_species in species_clusters.items():
            sc_indices = [species_idx[sp] for sp in sc_species if sp in species_idx]
            if not mc_indices or not sc_indices: continue
            values = [damage_matrix[mi, si] for mi in mc_indices for si in sc_indices if damage_matrix[mi, si] != 0.5]
            if values: cluster_eff[(mc_id, sc_id)] = float(np.mean(values))

    # Store
    brain.move_type_clusters = {int(k): v for k, v in move_clusters.items()}
    brain.species_type_clusters = {int(k): v for k, v in species_clusters.items()}
    brain.cluster_effectiveness = {f"{k[0]}_{k[1]}": v for k, v in cluster_eff.items()}
    brain.move_to_cluster = {int(m): int(mc_id) for mc_id, moves in move_clusters.items() for m in moves}
    brain.species_to_cluster = {int(sp): int(sc_id) for sc_id, sps in species_clusters.items() for sp in sps}

    brain.clustering_run_count += 1
    brain.last_clustering_timestep = brain.timestep
    brain.battles_since_last_clustering = 0
    brain.type_clusters_dirty = True

    print(f"  🧬 TYPE CLUSTERING #{brain.clustering_run_count}:")
    print(f"     Moves: {n_moves} → {len(move_clusters)} clusters")
    print(f"     Species: {n_species} → {len(species_clusters)} clusters")
    print(f"     Effectiveness entries: {len(cluster_eff)}")


def get_cluster_effectiveness_for_move(brain, move_id, species_id):
    mc_id = brain.move_to_cluster.get(move_id)
    sc_id = brain.species_to_cluster.get(species_id)
    if mc_id is None or sc_id is None: return None
    return brain.cluster_effectiveness.get(f"{mc_id}_{sc_id}")


def get_type_chart_status(brain):
    return {
        'clustering_runs': brain.clustering_run_count,
        'move_clusters': len(brain.move_type_clusters),
        'species_clusters': len(brain.species_type_clusters),
        'effectiveness_entries': len(brain.cluster_effectiveness),
        'moves_clustered': len(brain.move_to_cluster),
        'species_clustered': len(brain.species_to_cluster),
        'battles_since_clustering': brain.battles_since_last_clustering,
        'track_b_loaded': brain.type_data_loaded,
    }


# ============================================================================
# TYPE CHART PERSISTENCE
# ============================================================================

def load_type_clusters(brain, filepath=None):
    filepath = filepath or TYPE_CLUSTERS_FILE
    try:
        if not Path(filepath).exists():
            print(f"  🧬 No type clusters file"); return
        with open(filepath, 'r') as f:
            data = json.load(f)
        brain.move_type_clusters = {int(k): v for k, v in data.get('move_type_clusters', {}).items()}
        brain.species_type_clusters = {int(k): v for k, v in data.get('species_type_clusters', {}).items()}
        brain.cluster_effectiveness = data.get('cluster_effectiveness', {})
        brain.move_to_cluster = {int(k): int(v) for k, v in data.get('move_to_cluster', {}).items()}
        brain.species_to_cluster = {int(k): int(v) for k, v in data.get('species_to_cluster', {}).items()}
        brain.clustering_run_count = data.get('clustering_run_count', 0)
        brain.type_clusters_dirty = False
        print(f"  🧬 Type clusters loaded: {len(brain.move_type_clusters)} move clusters, "
              f"{len(brain.species_type_clusters)} species clusters, "
              f"{len(brain.cluster_effectiveness)} effectiveness entries")
    except Exception as e:
        print(f"  ⚠️ Error loading type clusters: {e}")


def save_type_clusters(brain, filepath=None):
    filepath = filepath or TYPE_CLUSTERS_FILE
    try:
        data = {
            'move_type_clusters': {str(k): v for k, v in brain.move_type_clusters.items()},
            'species_type_clusters': {str(k): v for k, v in brain.species_type_clusters.items()},
            'cluster_effectiveness': brain.cluster_effectiveness,
            'move_to_cluster': {str(k): v for k, v in brain.move_to_cluster.items()},
            'species_to_cluster': {str(k): v for k, v in brain.species_to_cluster.items()},
            'clustering_run_count': brain.clustering_run_count,
            'last_clustering_timestep': brain.last_clustering_timestep,
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        brain.type_clusters_dirty = False
    except Exception as e:
        print(f"  ⚠️ Error saving type clusters: {e}")


def load_ground_truth_types(brain, filepath=None):
    brain.type_data = load_type_data(filepath)
    brain.type_data_loaded = brain.type_data is not None and brain.type_data.get('loaded', False)


# ============================================================================
# MENU / BAG / PARTY DATA UPDATE
# ============================================================================

def update_menu_data(brain, menu_data):
    brain.prev_menu_data = brain.menu_data.copy()
    brain.menu_data = menu_data.copy()


def update_bag_data(brain, bag_data):
    brain.prev_bag_data = brain.bag_data.copy()
    brain.bag_data = {
        'pocket': bag_data.get('pocket', -1), 'cursor': bag_data.get('cursor', -1),
        'active': bag_data.get('active', 0),
        'items': [item.copy() for item in bag_data.get('items', [])],
    }


def update_party_data(brain, party_data):
    brain.prev_party_data = brain.party_data.copy()
    brain.party_data = party_data.copy()


# ============================================================================
# BAG THREAD
# ============================================================================

def open_bag_thread(brain, context):
    brain.bag_thread_active = True
    brain.bag_thread_context = context
    brain.bag_thread_entered_at = brain.timestep
    brain.bag_thread_action_count = 0
    brain.bag_thread_last_action = None
    brain.bag_action_history.clear()
    pk_names = {0:"Items",1:"KeyItems",2:"Pokeballs",3:"TMs",4:"Berries"}
    print(f"  {'🎒' if context=='overworld' else '🎒⚔️'} BAG OPEN: {context} | "
          f"{pk_names.get(brain.bag_data.get('pocket',-1),'?')} items={len(brain.bag_data.get('items',[]))}")


def close_bag_thread(brain, reason=""):
    if brain.bag_thread_active:
        print(f"  🎒 BAG CLOSED: {reason} ({brain.bag_thread_context} "
              f"{brain.timestep - brain.bag_thread_entered_at}f {brain.bag_thread_action_count}act)")
    brain.bag_thread_active = False
    brain.bag_thread_context = "none"
    brain.bag_thread_entered_at = 0
    brain.bag_thread_action_count = 0
    brain.bag_thread_last_action = None


def is_bag_thread_active(brain):
    return brain.bag_thread_active


def set_bag_thread_last_action(brain, action_name):
    brain.bag_thread_last_action = action_name


def update_bag_thread_state(brain, context_state):
    in_battle = context_state[3] > 0.5
    gs = brain.game_state_raw
    bgd, prev_bgd = brain.bag_data, brain.prev_bag_data

    if brain.bag_thread_active:
        if brain.timestep - brain.bag_thread_entered_at > brain.BAG_THREAD_TIMEOUT:
            close_bag_thread(brain, "timeout"); return
    if brain.bag_thread_active:
        if brain.bag_thread_context == "overworld":
            if gs != 14: close_bag_thread(brain, "gs_left_14"); return
        elif brain.bag_thread_context == "battle":
            if not in_battle: close_bag_thread(brain, "battle_ended"); return
            if bgd.get('active', 0) == 0 and prev_bgd.get('active', 0) == 0:
                close_bag_thread(brain, "bag_deactivated"); return
        return

    if brain.party_menu_active: return
    if not in_battle and gs == 14: open_bag_thread(brain, "overworld"); return
    if in_battle and bgd.get('active', 0) == 1: open_bag_thread(brain, "battle"); return


# ============================================================================
# ITEM KNOWLEDGE
# ============================================================================

def get_item_knowledge(brain, item_id):
    if item_id not in brain.item_knowledge:
        brain.item_knowledge[item_id] = {
            'uses': 0, 'category': 'unknown', 'confidence': 0.0,
            'avg_hp_restored': 0.0, 'total_hp_restored': 0,
            'status_cured': [], 'catch_attempts': 0,
            'catch_successes': 0, 'last_used_timestep': 0,
        }
    return brain.item_knowledge[item_id]


def get_item_at_cursor(brain):
    items = brain.bag_data.get('items', [])
    cursor = brain.bag_data.get('cursor', -1)
    if 0 <= cursor < len(items): return items[cursor].get('id', -1)
    return -1


def snapshot_party_for_item(brain):
    return {
        'slots': [{'hp': s.get('hp',0), 'max_hp': s.get('max_hp',0), 'status': s.get('status',0)}
                   for s in brain.party_data.get('slots', [])],
        'count': brain.party_data.get('count', 0)
    }


def start_item_observation(brain, item_id, target_slot=-1):
    in_battle = brain.battle_data.get('battle_cursor', -1) != -1
    brain.pending_item_observation = {
        'item_id': item_id, 'item_pocket': brain.bag_data.get('pocket', -1),
        'target_slot': target_slot, 'party_snapshot': snapshot_party_for_item(brain),
        'party_count': brain.party_data.get('count', 0), 'in_battle': in_battle,
        'enemy_hp_before': brain.battle_data.get('enemy_hp', -1) if in_battle else -1,
        'timestep': brain.timestep, 'frames_waiting': 0,
    }
    print(f"  🎒📝 ITEM OBS: item {item_id} pocket {brain.bag_data.get('pocket',-1)} slot {target_slot}")


def check_item_observation(brain):
    if brain.pending_item_observation is None: return False
    obs = brain.pending_item_observation
    obs['frames_waiting'] += 1
    if obs['frames_waiting'] > brain.ITEM_OBSERVE_WAIT_FRAMES:
        brain.pending_item_observation = None; return True

    snap = obs['party_snapshot']
    cur_slots = brain.party_data.get('slots', [])
    cur_count = brain.party_data.get('count', 0)

    hp_r, hp_t = 0, -1
    for i, (sn, cu) in enumerate(zip(snap['slots'], cur_slots)):
        d = cu.get('hp', 0) - sn['hp']
        if d > 0: hp_r, hp_t = d, i; break

    st_c, st_t = 0, -1
    for i, (sn, cu) in enumerate(zip(snap['slots'], cur_slots)):
        if sn['status'] != 0 and cu.get('status', 0) == 0:
            st_c, st_t = sn['status'], i; break

    caught = cur_count > obs['party_count'] and obs['party_count'] > 0
    if not (hp_r > 0 or st_c != 0 or caught): return False

    target = hp_t if hp_t >= 0 else (st_t if st_t >= 0 else obs['target_slot'])
    record_item_observation(brain, obs['item_id'], hp_r, st_c, caught, target, obs['in_battle'])
    brain.pending_item_observation = None
    return True


def record_item_observation(brain, item_id, hp_restored=0, status_cured=0,
                             caught=False, target_slot=-1, in_battle=False):
    if item_id <= 0: return
    ik = get_item_knowledge(brain, item_id)
    ik['uses'] += 1; ik['last_used_timestep'] = brain.timestep
    if hp_restored > 0:
        ik['total_hp_restored'] += hp_restored
        ik['avg_hp_restored'] = ik['total_hp_restored'] / max(1, ik['uses'])
    if status_cured != 0 and status_cured not in ik['status_cured']:
        ik['status_cured'].append(status_cured)
    if in_battle:
        ik['catch_attempts'] += 1
        if caught: ik['catch_successes'] += 1
    ik['category'] = _categorize_item(ik)
    ik['confidence'] = min(1.0, ik['uses'] / 5.0)
    brain.item_knowledge_dirty = True
    fx = []
    if hp_restored > 0: fx.append(f"+{hp_restored}HP")
    if status_cured != 0: fx.append(f"cured {status_cured}")
    if caught: fx.append("CAUGHT!")
    print(f"  🎒📖 ITEM: {item_id} → {ik['category']} ({ik['confidence']:.0%}) | {', '.join(fx) if fx else 'none'}")


def _categorize_item(ik):
    if ik['uses'] == 0: return 'unknown'
    hp = ik['total_hp_restored'] > 0
    st = len(ik['status_cured']) > 0
    ca = ik['catch_successes'] > 0 or ik['catch_attempts'] >= 2
    if ca: return 'catch'
    if hp and st: return 'heal_both'
    if hp: return 'heal_hp'
    if st: return 'heal_status'
    if ik['uses'] >= 3: return 'other'
    return 'unknown'


# ============================================================================
# ITEM KNOWLEDGE PERSISTENCE
# ============================================================================

def load_item_knowledge(brain, filepath=None):
    filepath = filepath or ITEM_KNOWLEDGE_FILE
    try:
        if Path(filepath).exists():
            with open(filepath, 'r') as f:
                brain.item_knowledge = {int(k): v for k, v in json.load(f).items()}
            brain.item_knowledge_dirty = False
            known = sum(1 for v in brain.item_knowledge.values() if v.get('category','unknown') != 'unknown')
            print(f"  🎒📖 Items loaded: {len(brain.item_knowledge)} ({known} categorized)")
        else:
            print(f"  🎒📖 No item knowledge file")
    except Exception as e:
        print(f"  ⚠️ Item knowledge error: {e}")
        brain.item_knowledge = {}


def save_item_knowledge(brain, filepath=None):
    filepath = filepath or ITEM_KNOWLEDGE_FILE
    try:
        with open(filepath, 'w') as f:
            json.dump({str(k): v for k, v in brain.item_knowledge.items()}, f, indent=2)
        brain.item_knowledge_dirty = False
    except Exception as e:
        print(f"  ⚠️ Item save error: {e}")


# ============================================================================
# PARTY DATA HELPERS
# ============================================================================

def get_party_slot_fingerprint(brain, slot_index):
    slots = brain.party_data.get('slots', [])
    if slot_index < 0 or slot_index >= len(slots): return None
    s = slots[slot_index]
    return (s['atk'], s['def'], s['spd'], s['spatk'], s['spdef'])


def get_living_party_slots(brain):
    return [(i, s) for i, s in enumerate(brain.party_data.get('slots', []))
            if s.get('hp', 0) > 0 and s.get('max_hp', 0) > 0]


def get_active_slot_index(brain):
    bd = brain.battle_data
    if bd['player_hp'] <= 0 and bd['player_max_hp'] <= 0: return -1
    for i, s in enumerate(brain.party_data.get('slots', [])):
        if (s.get('hp',-1) == bd['player_hp'] and s.get('max_hp',-1) == bd['player_max_hp']
            and s.get('level',-1) == bd['player_level']):
            return i
    return -1


def get_team_avg_level(brain):
    levels = [s.get('level', 0) for s in brain.party_data.get('slots', []) if s.get('hp', 0) > 0]
    return np.mean(levels) if levels else 0.0


# ============================================================================
# BATTLE DATA
# ============================================================================

def update_battle_data(brain, battle_data):
    brain.prev_battle_data = brain.battle_data.copy()
    for k in ('player_stat_stages', 'enemy_stat_stages'):
        v = brain.battle_data.get(k)
        if isinstance(v, list): brain.prev_battle_data[k] = list(v)
    brain.battle_data = battle_data.copy()
    for k in ('player_stat_stages', 'enemy_stat_stages'):
        v = battle_data.get(k)
        if isinstance(v, list): brain.battle_data[k] = list(v)


def on_battle_start_with_data(brain):
    bd = brain.battle_data
    if bd['player_species'] > 0: brain.battle_player_species = bd['player_species']
    if bd['enemy_species'] > 0: brain.battle_enemy_species = bd['enemy_species']
    if bd['player_hp'] > 0: brain.battle_start_hp = bd['player_hp']
    if bd['enemy_hp'] > 0: brain.battle_enemy_start_hp = bd['enemy_hp']
    brain.battle_menu_state = "unknown"; brain.battle_cursor_action_count = 0
    brain.turn_count = 0
    brain.turn_start_player_hp = bd['player_hp']; brain.turn_start_enemy_hp = bd['enemy_hp']
    brain.turn_start_pp = [bd['pp0'], bd['pp1'], bd['pp2'], bd['pp3']]
    brain.turn_start_enemy_pp = [bd['enemy_pp0'], bd['enemy_pp1'], bd['enemy_pp2'], bd['enemy_pp3']]
    brain.turn_start_player_stats = list(bd.get('player_stat_stages', [-1]*7))
    brain.turn_start_enemy_stats = list(bd.get('enemy_stat_stages', [-1]*7))
    brain.turn_start_player_status = bd.get('player_status', 0)
    brain.turn_start_enemy_status = bd.get('enemy_status', 0)
    brain.last_move_used = -1; brain.last_move_slot = -1
    brain.battle_no_damage_turns = 0; brain.battle_hp_trend.clear()
    close_party_menu(brain, "battle_start"); close_bag_thread(brain, "battle_start")
    from brain_systems import abort_preparation
    abort_preparation(brain, "battle_start")
    brain.forced_switch_pending = False; brain.forced_switch_target_slot = -1
    update_roster_from_battle(brain)


def on_battle_end_with_data(brain):
    outcome = 'unknown'
    if brain.battle_start_hp > 0:
        lp = brain.prev_battle_data.get('player_hp', -1)
        le = brain.prev_battle_data.get('enemy_hp', -1)
        if le == 0: outcome = 'win'
        elif lp == 0: outcome = 'loss'
        elif lp > 0 and le > 0: outcome = 'run'

    pc, cc = brain.prev_party_data.get('count', 0), brain.party_data.get('count', 0)
    if cc > pc and pc > 0: outcome = 'catch'; print(f"  🎊 CATCH! {pc}→{cc}")

    if brain.battle_start_hp > 0:
        lp = brain.prev_battle_data.get('player_hp', -1)
        if lp > 0:
            if lp / brain.battle_start_hp < 0.3: brain.battle_low_hp_exits += 1
            else: brain.battle_low_hp_exits = max(0, brain.battle_low_hp_exits - 1)

    if brain.current_map_id is not None and brain.battle_start_hp > 0:
        lp = brain.prev_battle_data.get('player_hp', -1)
        pmhp = brain.battle_data.get('player_max_hp', brain.battle_start_hp)
        hp_cost = max(0.0, (brain.battle_start_hp - lp) / pmhp) if lp >= 0 and pmhp > 0 else 0.0
        from brain_systems import update_map_battle_stats
        update_map_battle_stats(brain, brain.current_map_id, brain.battle_enemy_species,
                                brain.prev_battle_data.get('enemy_level', -1),
                                hp_cost, is_trainer_battle(brain), outcome)

    if outcome == 'loss' and brain.current_map_id is not None:
        enemy_level = brain.prev_battle_data.get('enemy_level', -1)
        if enemy_level > 0:
            pos = brain.last_positions[-1] if brain.last_positions else (0, 0)
            brain.record_revenge_loss(
                map_id=brain.current_map_id, position=pos,
                enemy_species=[brain.battle_enemy_species] if brain.battle_enemy_species > 0 else [],
                enemy_avg_level=float(enemy_level),
                my_avg_level=get_team_avg_level(brain),
                is_trainer=is_trainer_battle(brain),
            )
    elif outcome == 'win' and brain.current_map_id is not None:
        pos = brain.last_positions[-1] if brain.last_positions else (0, 0)
        brain.record_revenge_victory(brain.current_map_id, pos)

    brain.battles_since_last_clustering += 1

    brain.battle_player_species = -1; brain.battle_enemy_species = -1
    brain.battle_start_hp = -1; brain.battle_enemy_start_hp = -1
    brain.battle_menu_state = "unknown"; brain.battle_cursor_action_count = 0
    brain.turn_count = 0
    brain.turn_start_player_hp = -1; brain.turn_start_enemy_hp = -1
    brain.turn_start_pp = [-1]*4; brain.turn_start_enemy_pp = [-1]*4
    brain.turn_start_player_stats = [-1]*7; brain.turn_start_enemy_stats = [-1]*7
    brain.turn_start_player_status = 0; brain.turn_start_enemy_status = 0
    brain.last_move_used = -1; brain.last_move_slot = -1; brain.battle_no_damage_turns = 0
    close_party_menu(brain, "battle_end"); close_bag_thread(brain, "battle_end")
    brain.forced_switch_pending = False; brain.forced_switch_target_slot = -1
    return outcome


def has_battle_data(brain):
    return brain.battle_data.get('battle_cursor', -1) != -1 or brain.battle_data.get('player_hp', -1) != -1


def is_trainer_battle(brain):
    return (brain.battle_data.get('battle_type', 0) & 8) != 0


def infer_battle_menu_state(brain):
    bd, prev = brain.battle_data, brain.prev_battle_data
    if not has_battle_data(brain) or brain.party_menu_active or brain.bag_thread_active: return "unknown"
    bc, mc = bd['battle_cursor'], bd['move_cursor']
    pbc, pmc = prev['battle_cursor'], prev['move_cursor']
    if 0 <= bc <= 3 and bc != pbc: return "main_menu"
    if 0 <= mc <= 3 and mc != pmc: return "move_select"
    if 0 <= bc <= 3: return "main_menu"
    return "unknown"


# ============================================================================
# PARTY MENU THREAD
# ============================================================================

def open_party_menu(brain, context, target_slot=-1):
    brain.party_menu_active = True; brain.party_menu_context = context
    brain.party_menu_entered_at = brain.timestep; brain.party_menu_target_slot = target_slot
    brain.party_menu_action_count = 0; brain.party_menu_last_action = None
    if context == "battle_forced":
        brain.forced_switch_pending = True; brain.forced_switch_target_slot = target_slot
    emoji = {"battle_voluntary":"🔄","battle_forced":"🔄⚠️","overworld":"📋"}.get(context,"❓")
    print(f"  {emoji} PARTY MENU: {context}{f' →slot{target_slot}' if target_slot>=0 else ''}")


def close_party_menu(brain, reason=""):
    if brain.party_menu_active:
        print(f"  📋 PARTY CLOSED: {reason} ({brain.party_menu_context} "
              f"{brain.timestep-brain.party_menu_entered_at}f {brain.party_menu_action_count}act)")
    brain.party_menu_active = False; brain.party_menu_context = "none"
    brain.party_menu_entered_at = 0; brain.party_menu_target_slot = -1
    brain.party_menu_action_count = 0; brain.party_menu_awaiting_entry = False
    brain.party_menu_battle_cursor_on_entry = -1; brain.party_menu_last_action = None


def is_party_menu_active(brain): return brain.party_menu_active


def update_party_menu_state(brain, context_state):
    in_battle = context_state[3] > 0.5
    bd, prev_bd = brain.battle_data, brain.prev_battle_data
    md, gs = brain.menu_data, brain.game_state_raw

    if brain.party_menu_active:
        if brain.timestep - brain.party_menu_entered_at > brain.PARTY_MENU_TIMEOUT:
            close_party_menu(brain, "timeout"); return
    if brain.party_menu_active:
        if in_battle:
            bc = bd.get('battle_cursor', -1)
            if 0 <= bc <= 3 and 0 <= prev_bd.get('battle_cursor', -1) <= 3:
                close_party_menu(brain, "returned_to_battle"); return
        else:
            if brain.party_menu_context in ("battle_voluntary","battle_forced"):
                close_party_menu(brain, "battle_ended"); return
            if brain.party_menu_context == "overworld":
                if gs != 1: close_party_menu(brain, "gs_changed"); return
                if not (0 <= md.get('pc',-1) <= 6): close_party_menu(brain, "pc_invalid"); return
            if context_state[4] <= 0.5 and brain.party_menu_context == "overworld":
                close_party_menu(brain, "menu_closed"); return
        return

    if in_battle and has_battle_data(brain):
        bc = bd.get('battle_cursor', -1)
        if bd['player_hp'] == 0 and prev_bd.get('player_hp', -1) > 0:
            open_party_menu(brain, "battle_forced", get_best_switch_slot(brain)); return
        if brain.party_menu_awaiting_entry:
            brain.party_menu_awaiting_entry = False
            if not (0 <= bc <= 3): open_party_menu(brain, "battle_voluntary")
            return
        if brain.party_menu_last_action == "A" and prev_bd.get('battle_cursor', -1) == 2 and not (0 <= bc <= 3):
            open_party_menu(brain, "battle_voluntary"); return

    if not in_battle:
        pc = md.get('pc', -1)
        ppc = brain.prev_menu_data.get('pc', -1)
        if gs == 1 and 0 <= pc <= 5:
            if not (0 <= ppc <= 5):
                open_party_menu(brain, "overworld"); return


def set_party_menu_last_action(brain, action_name):
    brain.party_menu_last_action = action_name


# ============================================================================
# FORCED SWITCH + RUNNING
# ============================================================================

def detect_forced_switch(brain):
    return brain.party_menu_active and brain.party_menu_context == "battle_forced"


def get_best_switch_slot(brain):
    living = get_living_party_slots(brain)
    if not living: return -1
    active = get_active_slot_index(brain)
    cands = [(i, s) for i, s in living if i != active]
    if not cands: return living[0][0] if living else -1
    return max(cands, key=lambda x: x[1].get('hp', 0))[0]


def should_run(brain):
    if not brain.BATTLE_RUN_ENABLED or is_trainer_battle(brain): return False
    bd = brain.battle_data
    if brain.battle_no_damage_turns >= brain.BATTLE_RUN_NO_DAMAGE_THRESHOLD: return True
    if bd['player_hp'] > 0 and bd['player_max_hp'] > 0:
        if bd['player_hp'] / bd['player_max_hp'] < brain.BATTLE_RUN_HP_RATIO_THRESHOLD: return True
    if len(brain.battle_hp_trend) >= 3 and brain.battle_no_damage_turns >= 2:
        t = list(brain.battle_hp_trend)
        if all(t[i] >= t[i+1] for i in range(len(t)-1)): return True
    if brain.battle_low_hp_exits >= 3: return True
    return False


# ============================================================================
# TURN TRACKING
# ============================================================================

def detect_turn_resolved(brain):
    bd = brain.battle_data
    if bd['player_hp'] < 0 or brain.turn_start_player_hp < 0: return False
    cpp = [bd['pp0'], bd['pp1'], bd['pp2'], bd['pp3']]
    for i in range(4):
        if brain.turn_start_pp[i] > 0 and cpp[i] >= 0 and cpp[i] < brain.turn_start_pp[i]: return True
    phc = bd['player_hp'] != brain.turn_start_player_hp and brain.turn_start_player_hp >= 0
    ehc = bd['enemy_hp'] != brain.turn_start_enemy_hp and brain.turn_start_enemy_hp >= 0
    return phc and ehc


def on_battle_turn_end(brain):
    bd = brain.battle_data
    brain.turn_count += 1
    cpp = [bd['pp0'], bd['pp1'], bd['pp2'], bd['pp3']]
    used_slot = -1
    for i in range(4):
        if brain.turn_start_pp[i] > 0 and cpp[i] >= 0 and cpp[i] < brain.turn_start_pp[i]:
            used_slot = i; break
    move_id = bd.get(['move0','move1','move2','move3'][used_slot], -1) if used_slot >= 0 else -1
    dmg = max(0, brain.turn_start_enemy_hp - bd['enemy_hp']) if brain.turn_start_enemy_hp >= 0 and bd['enemy_hp'] >= 0 else 0

    missed = False
    if used_slot >= 0 and dmg == 0:
        esc = any(brain.turn_start_enemy_stats[j] >= 0 and bd.get('enemy_stat_stages',[-1]*7)[j] >= 0
                  and bd.get('enemy_stat_stages',[-1]*7)[j] != brain.turn_start_enemy_stats[j] for j in range(7))
        si = bd.get('enemy_status',0) != brain.turn_start_enemy_status and bd.get('enemy_status',0) != 0
        psc = any(brain.turn_start_player_stats[j] >= 0 and bd.get('player_stat_stages',[-1]*7)[j] >= 0
                  and bd.get('player_stat_stages',[-1]*7)[j] != brain.turn_start_player_stats[j] for j in range(7))
        if not esc and not si and not psc: missed = True

    if move_id > 0 and brain.battle_enemy_species > 0:
        cp = bd.get('player_stat_stages', [-1]*7)
        ce = bd.get('enemy_stat_stages', [-1]*7)
        ssc = sum(1 for j in range(7) if brain.turn_start_player_stats[j]>=0 and cp[j]>=0 and cp[j]!=brain.turn_start_player_stats[j])
        esc = sum(1 for j in range(7) if brain.turn_start_enemy_stats[j]>=0 and ce[j]>=0 and ce[j]!=brain.turn_start_enemy_stats[j])
        si = 1 if (bd.get('enemy_status',0) != brain.turn_start_enemy_status and bd.get('enemy_status',0) != 0) else 0
        record_move_result(brain, move_id, brain.battle_enemy_species, dmg, missed, ssc, esc, si)

    em = detect_enemy_move(brain)
    if em > 0:
        dt = max(0, brain.turn_start_player_hp - bd['player_hp']) if brain.turn_start_player_hp >= 0 and bd['player_hp'] >= 0 else 0
        ps = 1 if (bd.get('player_status',0) != brain.turn_start_player_status and bd.get('player_status',0) != 0) else 0
        record_enemy_move_observation(brain, em, dt, ps, 0)

    if dmg == 0 and used_slot >= 0: brain.battle_no_damage_turns += 1
    else: brain.battle_no_damage_turns = 0
    if bd['player_hp'] > 0: brain.battle_hp_trend.append(bd['player_hp'])

    if brain.battle_enemy_species > 0 and bd['enemy_species'] > 0 and bd['enemy_species'] != brain.battle_enemy_species:
        print(f"  ⚔️ ENEMY SWITCH: {brain.battle_enemy_species}→{bd['enemy_species']}")
        brain.battle_enemy_species = bd['enemy_species']; brain.battle_enemy_start_hp = bd['enemy_hp']

    brain.turn_start_player_hp = bd['player_hp']; brain.turn_start_enemy_hp = bd['enemy_hp']
    brain.turn_start_pp = [bd['pp0'],bd['pp1'],bd['pp2'],bd['pp3']]
    brain.turn_start_enemy_pp = [bd['enemy_pp0'],bd['enemy_pp1'],bd['enemy_pp2'],bd['enemy_pp3']]
    brain.turn_start_player_stats = list(bd.get('player_stat_stages',[-1]*7))
    brain.turn_start_enemy_stats = list(bd.get('enemy_stat_stages',[-1]*7))
    brain.turn_start_player_status = bd.get('player_status', 0)
    brain.turn_start_enemy_status = bd.get('enemy_status', 0)


def detect_enemy_move(brain):
    bd = brain.battle_data
    epp = [bd['enemy_pp0'],bd['enemy_pp1'],bd['enemy_pp2'],bd['enemy_pp3']]
    for i in range(4):
        if brain.turn_start_enemy_pp[i] > 0 and epp[i] >= 0 and epp[i] < brain.turn_start_enemy_pp[i]:
            return bd.get(['enemy_move0','enemy_move1','enemy_move2','enemy_move3'][i], -1)
    return -1


# ============================================================================
# ROSTER
# ============================================================================

def update_roster_from_battle(brain):
    bd = brain.battle_data
    if bd['player_species'] <= 0: return
    active = get_active_slot_index(brain)
    if active < 0:
        for i, s in enumerate(brain.party_data.get('slots', [])):
            if s.get('level',-1) == bd.get('player_level',-1) and s.get('max_hp',-1) == bd['player_max_hp']:
                active = i; break
    if active < 0: return
    brain.roster[active] = {
        'species': bd['player_species'],
        'moves': [bd[f'move{i}'] for i in range(4) if bd.get(f'move{i}',-1) > 0],
        'fingerprint': get_party_slot_fingerprint(brain, active),
        'level': bd.get('player_level', -1), 'last_updated': brain.timestep
    }
    brain.roster_dirty = True


def get_roster_moves_for_slot(brain, si):
    e = brain.roster.get(si); return e.get('moves', []) if e else []


def get_move_slot_index(brain, mid):
    for i in range(4):
        if brain.battle_data.get(f'move{i}', -1) == mid: return i
    return -1


# ============================================================================
# MOVE KNOWLEDGE
# ============================================================================

def record_move_result(brain, move_id, enemy_species, damage, missed, ssc, esc, si):
    if move_id <= 0: return
    mk = brain.move_knowledge
    if move_id not in mk:
        mk[move_id] = {'total_uses':0,'total_damage':0,'avg_damage':0.0,'misses':0,'vs_species':{}}
    e = mk[move_id]; e['total_uses'] += 1; e['total_damage'] += damage
    e['avg_damage'] = e['total_damage']/max(1,e['total_uses'])
    if missed: e['misses'] += 1
    if enemy_species not in e['vs_species']:
        e['vs_species'][enemy_species] = {'uses':0,'damage':0,'avg':0.0,'misses':0,
                                           'stat_changes_self':0,'stat_changes_enemy':0,'status_inflicted':0}
    v = e['vs_species'][enemy_species]; v['uses'] += 1; v['damage'] += damage
    v['avg'] = v['damage']/max(1,v['uses'])
    if missed: v['misses'] += 1
    v['stat_changes_self'] += ssc; v['stat_changes_enemy'] += esc; v['status_inflicted'] += si
    brain.move_knowledge_dirty = True


def record_enemy_move_observation(brain, emid, dtu, si, sc):
    if emid <= 0: return
    emk = brain.enemy_move_knowledge
    if emid not in emk: emk[emid] = {'observed_uses':0,'damage_to_us':0,'status_inflicted':0,'stat_changes':0}
    e = emk[emid]; e['observed_uses'] += 1; e['damage_to_us'] += dtu; e['status_inflicted'] += si; e['stat_changes'] += sc


# ============================================================================
# BATTLE RISK ASSESSMENT
# ============================================================================

def _assess_battle_risk(brain):
    bd = brain.battle_data
    if bd['player_hp'] <= 0 or bd['player_max_hp'] <= 0: return 'high'
    hp_ratio = bd['player_hp'] / bd['player_max_hp']
    enemy_hp_ratio = bd['enemy_hp'] / bd['enemy_max_hp'] if bd.get('enemy_max_hp', 0) > 0 else 1.0
    level_diff = bd.get('player_level', 0) - bd.get('enemy_level', 0)
    if brain.battle_no_damage_turns >= 2: return 'desperate'
    if hp_ratio > 0.6 and (enemy_hp_ratio < 0.5 or level_diff >= 3): return 'low'
    if hp_ratio < 0.25: return 'high'
    if is_trainer_battle(brain) and hp_ratio < 0.4: return 'high'
    return 'medium'


# ============================================================================
# MOVE SCORING — BEST MOVE FOR ENEMY
# ============================================================================

def get_best_move_for_enemy(brain, es):
    bd = brain.battle_data
    mids = [bd[f'move{i}'] for i in range(4)]
    pps = [bd[f'pp{i}'] for i in range(4)]

    # Tier 0: Pipeline query
    battle_state = build_learning_state_battle(bd, brain.party_data, brain.turn_count)
    pipeline_scores = query_battle_pipeline_move_scores(brain, battle_state)

    if pipeline_scores is not None:
        pipeline_cands = []
        for slot, score in pipeline_scores:
            mid = mids[slot] if slot < 4 else -1
            pp = pps[slot] if slot < 4 else 0
            if mid <= 0 or pp == 0: continue
            scaled = score * 50.0
            if pp <= 3 and pp > 0: scaled *= 0.8
            pipeline_cands.append((mid, slot, scaled))

        if pipeline_cands:
            knowledge_cands = _get_knowledge_move_scores(brain, es, mids, pps)
            knowledge_map = {mid: sc for mid, si, sc in knowledge_cands}
            for i, (mid, slot, p_score) in enumerate(pipeline_cands):
                k_score = knowledge_map.get(mid, 1.0)
                pipeline_cands[i] = (mid, slot, p_score * 0.6 + k_score * 0.4)
            pipeline_cands.sort(key=lambda x: x[2], reverse=True)
            return pipeline_cands

    return _get_knowledge_move_scores(brain, es, mids, pps)


def _get_knowledge_move_scores(brain, es, mids, pps):
    bd = brain.battle_data
    cands = []
    for si in range(4):
        mid, pp = mids[si], pps[si]
        if mid <= 0 or pp == 0: continue
        sc = 1.0; source = 'default'
        mk = brain.move_knowledge.get(mid)
        if mk:
            vs = mk.get('vs_species',{}).get(es)
            if vs and vs['uses'] >= 2:
                sc = vs['avg'] * 10.0
                if vs['uses'] > 0: sc *= (1.0 - vs['misses']/vs['uses']*0.5)
                if vs['status_inflicted'] > 0: sc += 2.0
                if vs['stat_changes_enemy'] > 0: sc += 1.0
                source = 'direct'
            else:
                if brain.type_data_loaded:
                    type_mult = get_type_effectiveness(brain.type_data, mid, es)
                    if type_mult is not None:
                        base = mk['avg_damage'] if mk['total_uses'] >= 2 else 5.0
                        sc = base * type_mult * 8.0
                        if mk['total_uses'] > 0: sc *= (1.0 - mk['misses']/mk['total_uses']*0.5)
                        source = 'type_b'
                if source == 'default':
                    cluster_eff = get_cluster_effectiveness_for_move(brain, mid, es)
                    if cluster_eff is not None:
                        base = mk['avg_damage'] if mk['total_uses'] >= 2 else 5.0
                        mult = cluster_eff / 0.5 if cluster_eff > 0 else 0.1
                        sc = base * mult * 8.0
                        if mk['total_uses'] > 0: sc *= (1.0 - mk['misses']/mk['total_uses']*0.5)
                        source = 'cluster'
                if source == 'default' and mk['total_uses'] >= 2:
                    sc = mk['avg_damage'] * 8.0
                    if mk['total_uses'] > 0: sc *= (1.0 - mk['misses']/mk['total_uses']*0.5)
                    source = 'avg'
        if pp <= 3 and pp > 0: sc *= 0.8
        cands.append((mid, si, sc))

    # Revenge penalty
    pos = brain.last_positions[-1] if brain.last_positions else (0, 0)
    target_id = f"map{brain.current_map_id}_pos{pos[0]}_{pos[1]}"
    revenge = brain.revenge_targets.get(target_id)
    if revenge and revenge.get('strategy_notes', {}).get('moves_that_failed'):
        failed_moves = revenge['strategy_notes']['moves_that_failed']
        for i, (mid, si, sc) in enumerate(cands):
            if mid in failed_moves: cands[i] = (mid, si, sc * 0.3)

    # Risk-based exploration
    best_known_score = max((sc for _, _, sc in cands), default=1.0)
    risk = _assess_battle_risk(brain)
    for i, (mid, si, sc) in enumerate(cands):
        mk = brain.move_knowledge.get(mid)
        has_vs_data = mk and es in mk.get('vs_species', {})
        has_any_data = mk and mk.get('total_uses', 0) > 0
        if not has_any_data:
            if risk == 'low': cands[i] = (mid, si, best_known_score * 0.8)
            elif risk == 'desperate': cands[i] = (mid, si, best_known_score * 1.2)
        elif not has_vs_data and has_any_data:
            if risk == 'low': cands[i] = (mid, si, max(sc, best_known_score * 0.6))
            elif risk == 'desperate': cands[i] = (mid, si, max(sc, best_known_score * 1.0))

    cands.sort(key=lambda x: x[2], reverse=True)
    return cands


def get_moves_with_pp(brain):
    bd = brain.battle_data
    return [(i, bd.get(f'move{i}',-1), bd.get(f'pp{i}',-1))
            for i in range(4) if bd.get(f'move{i}',-1) > 0 and bd.get(f'pp{i}',-1) > 0]


# ============================================================================
# PERSISTENCE
# ============================================================================

def load_roster(brain, filepath=None):
    filepath = filepath or ROSTER_FILE
    try:
        if Path(filepath).exists():
            with open(filepath, 'r') as f:
                brain.roster = {int(k): v for k, v in json.load(f).items()}
            for v in brain.roster.values():
                if isinstance(v.get('fingerprint'), list): v['fingerprint'] = tuple(v['fingerprint'])
            brain.roster_dirty = False
            print(f"  📋 Roster: {len(brain.roster)} slots")
        else: print(f"  📋 No roster file")
    except Exception as e: print(f"  ⚠️ Roster error: {e}"); brain.roster = {}


def save_roster(brain, filepath=None):
    filepath = filepath or ROSTER_FILE
    try:
        sd = {}
        for k, v in brain.roster.items():
            e = v.copy()
            if isinstance(e.get('fingerprint'), tuple): e['fingerprint'] = list(e['fingerprint'])
            sd[str(k)] = e
        with open(filepath, 'w') as f: json.dump(sd, f, indent=2)
        brain.roster_dirty = False
    except Exception as e: print(f"  ⚠️ Roster save error: {e}")


def load_move_knowledge(brain, filepath=None):
    filepath = filepath or MOVE_KNOWLEDGE_FILE
    try:
        if Path(filepath).exists():
            with open(filepath, 'r') as f: data = json.load(f)
            brain.move_knowledge = {}
            for mk, mv in data.get('player_moves', {}).items():
                mv['vs_species'] = {int(sk): sv for sk, sv in mv.get('vs_species', {}).items()}
                brain.move_knowledge[int(mk)] = mv
            brain.enemy_move_knowledge = {int(k): v for k, v in data.get('enemy_moves', {}).items()}
            brain.move_knowledge_dirty = False
            print(f"  📖 Moves: {len(brain.move_knowledge)} tracked")
        else: print(f"  📖 No move knowledge file")
    except Exception as e: print(f"  ⚠️ Move knowledge error: {e}"); brain.move_knowledge = {}; brain.enemy_move_knowledge = {}


def save_move_knowledge(brain, filepath=None):
    filepath = filepath or MOVE_KNOWLEDGE_FILE
    try:
        sd = {'player_moves': {}, 'enemy_moves': {str(k): v for k, v in brain.enemy_move_knowledge.items()}}
        for mk, mv in brain.move_knowledge.items():
            c = mv.copy(); c['vs_species'] = {str(sk): sv for sk, sv in mv.get('vs_species', {}).items()}
            sd['player_moves'][str(mk)] = c
        with open(filepath, 'w') as f: json.dump(sd, f, indent=2)
        brain.move_knowledge_dirty = False
    except Exception as e: print(f"  ⚠️ Move save error: {e}")


def load_map_battle_stats(brain, data=None):
    if data is None: return
    try:
        brain.map_battle_stats = {int(k): v for k, v in data.items()}
        brain.map_step_counters = {mid: s.get('total_steps_on_map', 0) for mid, s in brain.map_battle_stats.items()}
        brain.map_battle_stats_dirty = False
        mwd = len([s for s in brain.map_battle_stats.values() if s['battles_fought'] > 0])
        print(f"  📊 Map battle stats: {mwd} maps")
    except Exception as e: print(f"  ⚠️ Map stats error: {e}"); brain.map_battle_stats = {}


def get_map_battle_stats_for_save(brain):
    return {str(k): v for k, v in brain.map_battle_stats.items()}


# ============================================================================
# ATTACH ALL METHODS TO BRAIN CLASS
# ============================================================================

def attach_to_brain(BrainClass):
    """Attach all brain_data functions as methods on the Brain class."""
    # Chain helpers
    BrainClass.get_chain_error_history = get_chain_error_history
    BrainClass.get_chain_spawn_threshold = get_chain_spawn_threshold
    BrainClass.get_chain_entity_signal = get_chain_entity_signal

    # Pipeline signal
    BrainClass.get_pipeline_pool_signal = get_pipeline_pool_signal
    BrainClass.query_battle_pipeline_move_scores = query_battle_pipeline_move_scores

    # Memory monitoring
    BrainClass.get_total_activation_observations = get_total_activation_observations
    BrainClass.get_activation_observation_stats = get_activation_observation_stats
    BrainClass.get_knowledge_file_sizes = get_knowledge_file_sizes

    # Knowledge pruning
    BrainClass.prune_stale_move_knowledge = prune_stale_move_knowledge
    BrainClass.prune_stale_item_knowledge = prune_stale_item_knowledge

    # Type chart
    BrainClass.run_type_clustering = run_type_clustering
    BrainClass.get_cluster_effectiveness_for_move = get_cluster_effectiveness_for_move
    BrainClass.get_type_chart_status = get_type_chart_status
    BrainClass.load_type_clusters = load_type_clusters
    BrainClass.save_type_clusters = save_type_clusters
    BrainClass.load_ground_truth_types = load_ground_truth_types

    # Menu/bag/party data
    BrainClass.update_menu_data = update_menu_data
    BrainClass.update_bag_data = update_bag_data
    BrainClass.update_party_data = update_party_data

    # Bag thread
    BrainClass.open_bag_thread = open_bag_thread
    BrainClass.close_bag_thread = close_bag_thread
    BrainClass.is_bag_thread_active = is_bag_thread_active
    BrainClass.set_bag_thread_last_action = set_bag_thread_last_action
    BrainClass.update_bag_thread_state = update_bag_thread_state

    # Item knowledge
    BrainClass.get_item_knowledge = get_item_knowledge
    BrainClass.get_item_at_cursor = get_item_at_cursor
    BrainClass.snapshot_party_for_item = snapshot_party_for_item
    BrainClass.start_item_observation = start_item_observation
    BrainClass.check_item_observation = check_item_observation
    BrainClass.record_item_observation = record_item_observation
    BrainClass.load_item_knowledge = load_item_knowledge
    BrainClass.save_item_knowledge = save_item_knowledge

    # Party data
    BrainClass.get_party_slot_fingerprint = get_party_slot_fingerprint
    BrainClass.get_living_party_slots = get_living_party_slots
    BrainClass.get_active_slot_index = get_active_slot_index
    BrainClass.get_team_avg_level = get_team_avg_level

    # Battle data
    BrainClass.update_battle_data = update_battle_data
    BrainClass.on_battle_start_with_data = on_battle_start_with_data
    BrainClass.on_battle_end_with_data = on_battle_end_with_data
    BrainClass.has_battle_data = has_battle_data
    BrainClass.is_trainer_battle = is_trainer_battle
    BrainClass.infer_battle_menu_state = infer_battle_menu_state

    # Party menu
    BrainClass.open_party_menu = open_party_menu
    BrainClass.close_party_menu = close_party_menu
    BrainClass.is_party_menu_active = is_party_menu_active
    BrainClass.update_party_menu_state = update_party_menu_state
    BrainClass.set_party_menu_last_action = set_party_menu_last_action

    # Switch + running
    BrainClass.detect_forced_switch = detect_forced_switch
    BrainClass.get_best_switch_slot = get_best_switch_slot
    BrainClass.should_run = should_run

    # Turn tracking
    BrainClass.detect_turn_resolved = detect_turn_resolved
    BrainClass.on_battle_turn_end = on_battle_turn_end
    BrainClass.detect_enemy_move = detect_enemy_move

    # Roster
    BrainClass.update_roster_from_battle = update_roster_from_battle
    BrainClass.get_roster_moves_for_slot = get_roster_moves_for_slot
    BrainClass.get_move_slot_index = get_move_slot_index

    # Move knowledge
    BrainClass.record_move_result = record_move_result
    BrainClass.record_enemy_move_observation = record_enemy_move_observation
    BrainClass.get_best_move_for_enemy = get_best_move_for_enemy
    BrainClass.get_moves_with_pp = get_moves_with_pp

    # Persistence
    BrainClass.load_roster = load_roster
    BrainClass.save_roster = save_roster
    BrainClass.load_move_knowledge = load_move_knowledge
    BrainClass.save_move_knowledge = save_move_knowledge
    BrainClass.load_map_battle_stats = load_map_battle_stats
    BrainClass.get_map_battle_stats_for_save = get_map_battle_stats_for_save