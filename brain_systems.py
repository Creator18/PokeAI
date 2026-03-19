# ============================================================================
# brain_systems.py — Brain Subsystem Methods (Cell 3.1B)
# ============================================================================
# All methods here take `brain` as first argument (standalone functions that
# operate on Brain state). They are attached to Brain in main.py or via a
# setup function.
#
# Contains:
#   - Event timeline (load + query)
#   - Map battle statistics
#   - Text dialogue state
#   - Start menu thread
#   - Preparation state machine
#   - Party menu open/close (not detection — that's in brain_data)
#   - Chain-specific entity spawning + innate entities
#   - Pool-aware entity spawning
#   - Pipeline pool clustering
#   - Residual file persistence
#   - Menu trap B-boost tracking
#   - Event recorder helpers
# ============================================================================

import json
import time
import numpy as np
from pathlib import Path

from constants import AI_EVENT_TIMELINE_FILE
from perceptron import Perceptron
from pool import Pool


# ============================================================================
# EVENT TIMELINE
# ============================================================================

def load_event_timeline(brain, filepath=None):
    filepath = filepath or AI_EVENT_TIMELINE_FILE
    try:
        if not Path(filepath).exists():
            brain.event_timeline_loaded = False
            print(f"  📅 No event timeline found at {filepath}")
            return
        with open(filepath, 'r') as f:
            data = json.load(f)
        brain.event_timeline = data.get('events', [])
        brain.event_segments = data.get('segments', [])
        brain.event_preparation_points = data.get('preparation_points', [])
        brain.event_timeline_metadata = data.get('metadata', {})
        brain.event_timeline_loaded = True
        n_ev = len(brain.event_timeline)
        n_seg = len(brain.event_segments)
        n_prep = len(brain.event_preparation_points)
        type_counts = {}
        for e in brain.event_timeline:
            t = e.get('type', 'unknown')
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"  📅 Event timeline loaded: {n_ev} events, {n_seg} segments, {n_prep} prep")
        if type_counts:
            print(f"     Types: {', '.join(f'{k}:{v}' for k, v in type_counts.items())}")
        for pp in brain.event_preparation_points[:3]:
            print(f"     Prep #{pp.get('before_nav_order','?')}: {pp.get('reason','?')} (HP<{pp.get('party_hp_threshold','?')})")
    except Exception as e:
        print(f"  ⚠️ Error loading event timeline: {e}")
        brain.event_timeline = []
        brain.event_segments = []
        brain.event_preparation_points = []
        brain.event_timeline_metadata = {}
        brain.event_timeline_loaded = False


def get_nearest_nav_order(brain, raw_x, raw_y, map_id):
    if not brain.taught_nav_loaded: return -1
    map_targets = brain.taught_nav_targets.get(map_id, [])
    if map_targets:
        best_order, best_dist = -1, float('inf')
        for t in map_targets:
            pos = t.get('position', [0, 0])
            dist = abs(raw_x - pos[0]) + abs(raw_y - pos[1])
            if dist < best_dist:
                best_dist, best_order = dist, t.get('order', -1)
        return best_order
    if brain.nav_visited_targets:
        return max(brain.nav_visited_targets)
    return -1


def get_upcoming_events(brain, current_nav_order, lookahead=5):
    if not brain.event_timeline_loaded or current_nav_order < 0: return []
    upcoming = [e for e in brain.event_timeline
                if 0 <= e.get('nav_target_order', -1) - current_nav_order <= lookahead]
    upcoming.sort(key=lambda e: (e.get('nav_target_order', 0), e.get('order', 0)))
    return upcoming


def get_upcoming_battles(brain, current_nav_order, lookahead=5):
    return [e for e in get_upcoming_events(brain, current_nav_order, lookahead) if e.get('type') == 'battle']


def get_upcoming_trainer_battles(brain, current_nav_order, lookahead=5):
    return [b for b in get_upcoming_battles(brain, current_nav_order, lookahead)
            if b.get('battle_info', {}).get('battle_type') == 'trainer']


def get_segment_difficulty(brain, from_nav_order, to_nav_order):
    if not brain.event_timeline_loaded: return None
    for seg in brain.event_segments:
        if seg.get('from_nav_order') == from_nav_order and seg.get('to_nav_order') == to_nav_order:
            return seg
    for seg in brain.event_segments:
        if seg.get('from_nav_order', -1) <= from_nav_order and seg.get('to_nav_order', -1) >= to_nav_order:
            return seg
    return None


def get_preparation_point(brain, nav_order):
    if not brain.event_timeline_loaded: return None
    for pp in brain.event_preparation_points:
        if abs(nav_order - pp.get('before_nav_order', -999)) <= 1:
            return pp
    return None


def get_estimated_hp_cost_ahead(brain, current_nav_order, lookahead=5):
    if not brain.event_timeline_loaded: return 0.0
    for seg in brain.event_segments:
        sf, st = seg.get('from_nav_order', -1), seg.get('to_nav_order', -1)
        if sf >= 0 and st >= 0 and sf <= current_nav_order and st <= current_nav_order + lookahead:
            return seg.get('total_hp_cost', 0.0)
    return sum(b.get('battle_info', {}).get('hp_cost', 0.15)
               for b in get_upcoming_battles(brain, current_nav_order, lookahead))


def get_timeline_status(brain):
    if not brain.event_timeline_loaded: return {'loaded': False}
    return {'loaded': True, 'events': len(brain.event_timeline),
            'segments': len(brain.event_segments),
            'prep_points': len(brain.event_preparation_points),
            'nav_covered': brain.event_timeline_metadata.get('nav_targets_covered', [])}


# ============================================================================
# MAP BATTLE STATISTICS
# ============================================================================

def get_map_battle_stats(brain, map_id):
    if map_id not in brain.map_battle_stats:
        brain.map_battle_stats[map_id] = {
            'battles_fought': 0, 'wild_battles': 0, 'trainer_battles': 0, 'losses': 0,
            'total_hp_cost': 0.0, 'avg_hp_cost': 0.0,
            'total_enemy_levels': 0, 'avg_enemy_level': 0.0,
            'species_seen': [], 'total_steps_on_map': 0,
            'encounter_rate': 0.0, 'last_updated': 0,
        }
    return brain.map_battle_stats[map_id]


def update_map_battle_stats(brain, map_id, enemy_species, enemy_level,
                             hp_cost, is_trainer, outcome):
    stats = get_map_battle_stats(brain, map_id)
    stats['battles_fought'] += 1
    if is_trainer: stats['trainer_battles'] += 1
    else: stats['wild_battles'] += 1
    if outcome == 'loss': stats['losses'] += 1
    stats['total_hp_cost'] += hp_cost
    stats['avg_hp_cost'] = stats['total_hp_cost'] / max(1, stats['battles_fought'])
    if enemy_level > 0:
        stats['total_enemy_levels'] += enemy_level
        stats['avg_enemy_level'] = stats['total_enemy_levels'] / max(1, stats['battles_fought'])
    if enemy_species > 0 and enemy_species not in stats['species_seen']:
        stats['species_seen'].append(enemy_species)
    steps = brain.map_step_counters.get(map_id, 0)
    if steps > 0:
        stats['total_steps_on_map'] = steps
        stats['encounter_rate'] = stats['battles_fought'] / steps
    stats['last_updated'] = brain.timestep
    brain.map_battle_stats_dirty = True


def increment_map_steps(brain, map_id):
    brain.map_step_counters[map_id] = brain.map_step_counters.get(map_id, 0) + 1


def predict_hp_cost_for_map(brain, map_id, steps=50):
    stats = brain.map_battle_stats.get(map_id)
    if stats is None or stats['battles_fought'] == 0: return 0.0
    rate, cost = stats['encounter_rate'], stats['avg_hp_cost']
    if rate <= 0 or cost <= 0: return 0.0
    return rate * steps * cost


def predict_hp_cost_for_route(brain, map_chain, steps_per_map=50):
    total = 0.0
    for mid in map_chain:
        mc = predict_hp_cost_for_map(brain, mid, steps_per_map)
        if mc > 0:
            total += mc
        else:
            all_stats = [s for s in brain.map_battle_stats.values() if s['battles_fought'] >= 3]
            if all_stats:
                ga = sum(s['avg_hp_cost'] for s in all_stats) / len(all_stats)
                gr = sum(s['encounter_rate'] for s in all_stats) / len(all_stats)
                total += gr * steps_per_map * ga
            else:
                total += 0.30
    return total


def get_autonomous_hp_estimate(brain, raw_x, raw_y, map_id):
    stats = brain.map_battle_stats.get(map_id)
    if stats and stats['battles_fought'] >= 3:
        mc = predict_hp_cost_for_map(brain, map_id, 50)
        conf = min(1.0, stats['battles_fought'] / 10.0)
        if brain.nav_map_chain and len(brain.nav_map_chain) > 1:
            remaining = []
            for i, cm in enumerate(brain.nav_map_chain):
                if cm == map_id:
                    remaining = brain.nav_map_chain[i+1:]
                    break
            if remaining:
                mc += predict_hp_cost_for_route(brain, remaining, 40)
        return mc, conf
    elif stats and stats['battles_fought'] >= 1:
        return predict_hp_cost_for_map(brain, map_id, 50), stats['battles_fought'] / 10.0
    else:
        all_stats = [s for s in brain.map_battle_stats.values() if s['battles_fought'] >= 3]
        if all_stats:
            ga = sum(s['avg_hp_cost'] for s in all_stats) / len(all_stats)
            gr = sum(s['encounter_rate'] for s in all_stats) / len(all_stats)
            return gr * 50 * ga, 0.2
        return 0.0, 0.0


def get_map_battle_stats_summary(brain):
    if not brain.map_battle_stats: return {'maps_with_data': 0, 'total_battles': 0, 'unique_species': 0}
    mwd = len([s for s in brain.map_battle_stats.values() if s['battles_fought'] > 0])
    tb = sum(s['battles_fought'] for s in brain.map_battle_stats.values())
    species = set()
    for s in brain.map_battle_stats.values():
        species.update(s.get('species_seen', []))
    return {'maps_with_data': mwd, 'total_battles': tb, 'unique_species': len(species)}


# ============================================================================
# TEXT DIALOGUE STATE
# ============================================================================

def update_dialogue_state(brain, context_state):
    brain.prev_text_flag = brain.text_flag
    in_battle = context_state[3] > 0.5
    tf = brain.text_flag

    brain.dialogue_active = False
    brain.dialogue_is_battle_text = False
    brain.dialogue_is_choice = False
    brain.dialogue_is_pure_text = False

    if tf != 1:
        if brain.prev_text_flag == 1 and brain.dialogue_entered_at > 0:
            duration = brain.timestep - brain.dialogue_entered_at
            if duration >= 3:
                brain.dialogue_entered_at = 0
        return

    brain.dialogue_active = True

    if brain.prev_text_flag != 1:
        brain.dialogue_entered_at = brain.timestep

    brain.dialogue_frames_total += 1

    if in_battle:
        bc = brain.battle_data.get('battle_cursor', -1)
        mc = brain.battle_data.get('move_cursor', -1)
        if not (0 <= bc <= 3) and not (0 <= mc <= 3):
            brain.dialogue_is_battle_text = True
            return
        else:
            brain.dialogue_active = False
            return

    mm = brain.menu_data.get('mm', -1)
    mc = brain.menu_data.get('mc', -1)
    gs = brain.game_state_raw
    pc = brain.menu_data.get('pc', -1)

    if (0 <= mm <= brain.DIALOGUE_CHOICE_MM_MAX and
            0 <= mc <= mm and
            gs != 14 and
            not (gs == 1 and mm >= 4) and
            not (0 <= pc <= 5)):
        brain.dialogue_is_choice = True
        return

    brain.dialogue_is_pure_text = True


def is_dialogue_skip_state(brain):
    return brain.dialogue_is_pure_text or brain.dialogue_is_battle_text


def is_dialogue_choice_state(brain):
    return brain.dialogue_is_choice


def get_dialogue_status(brain):
    if not brain.dialogue_active:
        return {
            'active': False,
            'total_skip_actions': brain.dialogue_skip_action_count,
            'total_choice_actions': brain.dialogue_choice_action_count,
            'total_frames': brain.dialogue_frames_total,
        }
    return {
        'active': True,
        'is_pure_text': brain.dialogue_is_pure_text,
        'is_choice': brain.dialogue_is_choice,
        'is_battle_text': brain.dialogue_is_battle_text,
        'frames_in_current': brain.timestep - brain.dialogue_entered_at if brain.dialogue_entered_at > 0 else 0,
        'total_skip_actions': brain.dialogue_skip_action_count,
        'total_choice_actions': brain.dialogue_choice_action_count,
        'total_frames': brain.dialogue_frames_total,
    }


# ============================================================================
# START MENU THREAD
# ============================================================================

def open_start_menu(brain, context, target_mc=-1):
    brain.start_menu_active = True
    brain.start_menu_context = context
    brain.start_menu_entered_at = brain.timestep
    brain.start_menu_action_count = 0
    brain.start_menu_last_action = None
    brain.start_menu_target_mc = target_mc
    brain.start_menu_action_history.clear()
    target_name = "?"
    for name, mc_val in brain.START_MENU_OPTIONS.items():
        if mc_val == target_mc:
            target_name = name; break
    print(f"  📋 START MENU OPEN: {context}"
          f"{f' → {target_name}(mc={target_mc})' if target_mc >= 0 else ' (Markov)'}")


def close_start_menu(brain, reason=""):
    if brain.start_menu_active:
        duration = brain.timestep - brain.start_menu_entered_at
        print(f"  📋 START MENU CLOSED: {reason} ({brain.start_menu_context} "
              f"{duration}f {brain.start_menu_action_count}act)")
    brain.start_menu_active = False
    brain.start_menu_context = "none"
    brain.start_menu_entered_at = 0
    brain.start_menu_action_count = 0
    brain.start_menu_last_action = None
    brain.start_menu_target_mc = -1


def is_start_menu_active(brain):
    return brain.start_menu_active


def set_start_menu_last_action(brain, action_name):
    brain.start_menu_last_action = action_name


def update_start_menu_state(brain, context_state):
    in_battle = context_state[3] > 0.5
    gs = brain.game_state_raw
    mc = brain.menu_data.get('mc', -1)
    mm = brain.menu_data.get('mm', -1)
    pc = brain.menu_data.get('pc', -1)
    prev_gs = getattr(brain, '_prev_game_state_raw', 0)

    if brain.start_menu_active:
        if brain.timestep - brain.start_menu_entered_at > brain.START_MENU_TIMEOUT:
            close_start_menu(brain, "timeout"); return
        if in_battle:
            close_start_menu(brain, "battle_started"); return
        if gs != 1:
            if gs == 14 and brain.start_menu_context == "preparation":
                close_start_menu(brain, "bag_opened_success"); return
            close_start_menu(brain, "gs_left_1"); return
        if 0 <= pc <= 5:
            close_start_menu(brain, "party_took_over"); return
        return

    if brain.party_menu_active or brain.bag_thread_active: return
    if in_battle: return
    if brain.prep_active: return

    if gs == 1 and prev_gs != 1:
        if 0 <= mc <= 6 and mm >= 4:
            if not (0 <= pc <= 5):
                open_start_menu(brain, "unknown"); return

    if gs == 1 and not brain.start_menu_active:
        if 0 <= mc <= 6 and mm >= 4 and not (0 <= pc <= 5):
            if brain.state_stagnation_count >= 3:
                open_start_menu(brain, "unknown"); return


def get_start_menu_status(brain):
    if not brain.start_menu_active: return {'active': False}
    return {
        'active': True, 'context': brain.start_menu_context,
        'target_mc': brain.start_menu_target_mc,
        'frames': brain.timestep - brain.start_menu_entered_at,
        'actions': brain.start_menu_action_count,
        'total_actions': brain.start_menu_total_actions,
        'markov_actions': brain.start_menu_markov_actions,
    }


# ============================================================================
# PREPARATION
# ============================================================================

def should_prepare(brain, raw_x, raw_y, map_id):
    if brain.prep_active or brain.party_menu_active or brain.bag_thread_active: return False, "", ""
    if brain.start_menu_active: return False, "", ""
    if brain.game_state_raw != 0: return False, "", ""
    if brain.timestep - brain.prep_last_attempt_at < brain.PREP_COOLDOWN: return False, "", ""

    lowest_hp = get_lowest_hp_ratio(brain)
    has_status = has_status_condition_in_party(brain)
    healing = get_healing_items(brain)
    has_healing = len(healing) > 0

    # Tier 1: Timeline
    if brain.event_timeline_loaded:
        cn = get_nearest_nav_order(brain, raw_x, raw_y, map_id)
        if cn >= 0:
            pp = get_preparation_point(brain, cn)
            if pp:
                thr = pp.get('party_hp_threshold', 0.8)
                if lowest_hp < thr and has_healing:
                    return True, f"timeline prep #{pp.get('before_nav_order','?')}: {pp.get('reason','')} HP {lowest_hp:.0%}<{thr:.0%}", "bag"
            hc = get_estimated_hp_cost_ahead(brain, cn, 5)
            if hc > 0:
                if lowest_hp < hc and has_healing:
                    return True, f"timeline survival: HP {lowest_hp:.0%}<cost {hc:.0%}", "bag"
                tr = get_upcoming_trainer_battles(brain, cn, 3)
                if tr and lowest_hp < 0.5 and has_healing:
                    return True, f"timeline trainer: {len(tr)} ahead HP {lowest_hp:.0%}", "bag"

    # Tier 2: Autonomous
    ac, acf = get_autonomous_hp_estimate(brain, raw_x, raw_y, map_id)
    if acf >= 0.3 and ac > 0:
        if lowest_hp < ac and has_healing:
            return True, f"autonomous: HP {lowest_hp:.0%}<cost {ac:.0%} (conf {acf:.0%})", "bag"
        stats = brain.map_battle_stats.get(map_id)
        if stats and stats['trainer_battles'] > 0 and lowest_hp < 0.5 and has_healing:
            return True, f"autonomous trainer map: HP {lowest_hp:.0%}", "bag"

    # Universal
    if lowest_hp < 0.25 and has_healing:
        return True, f"critical HP: {lowest_hp:.0%}", "bag"
    if has_status:
        for iid, qty, cat, conf in healing:
            if cat in ('heal_status', 'heal_both') and conf >= 0.4:
                return True, f"status condition, cure item {iid}", "bag"

    return False, "", ""


def start_preparation(brain, reason, target="bag"):
    brain.prep_active = True
    brain.prep_reason = reason
    brain.prep_started_at = brain.timestep
    brain.prep_last_attempt_at = brain.timestep
    brain.prep_target = target
    brain.prep_phase_entered_at = brain.timestep
    brain.prep_total_count += 1

    if target == "bag": brain.prep_target_mc = 2
    elif target == "pokemon": brain.prep_target_mc = 1
    else: brain.prep_target_mc = 2

    brain.prep_phase = "pressing_start"
    print(f"  🎯 PREP START: {target} | {reason}"
          f"{' (Markov nav)' if brain.start_menu_loaded else ' (hardcoded)'}")


def abort_preparation(brain, reason=""):
    if brain.prep_active:
        print(f"  🎯 PREP ABORT: {reason} ({brain.prep_phase} {brain.timestep - brain.prep_started_at}f)")
    brain.prep_active = False
    brain.prep_phase = "idle"
    brain.prep_reason = ""
    if brain.start_menu_active and brain.start_menu_context == "preparation":
        close_start_menu(brain, "prep_aborted")


def is_preparation_active(brain):
    return brain.prep_active


def update_preparation_state(brain, context_state):
    if not brain.prep_active: return
    in_battle = context_state[3] > 0.5
    gs = brain.game_state_raw
    mc = brain.menu_data.get('mc', -1)

    if brain.bag_thread_active and brain.prep_target == "bag":
        brain.prep_success_count += 1
        print(f"  🎯 PREP SUCCESS: bag ({brain.timestep - brain.prep_started_at}f)")
        brain.prep_active = False; brain.prep_phase = "idle"; return
    if brain.party_menu_active and brain.prep_target == "party":
        brain.prep_success_count += 1
        print(f"  🎯 PREP SUCCESS: party ({brain.timestep - brain.prep_started_at}f)")
        brain.prep_active = False; brain.prep_phase = "idle"; return

    if in_battle: abort_preparation(brain, "battle"); return
    if brain.timestep - brain.prep_started_at > brain.PREP_TIMEOUT: abort_preparation(brain, "timeout"); return
    if brain.timestep - brain.prep_phase_entered_at > brain.PREP_PHASE_TIMEOUT: abort_preparation(brain, f"phase_timeout({brain.prep_phase})"); return

    if gs == 1 and brain.start_menu_loaded:
        if not brain.start_menu_active:
            open_start_menu(brain, "preparation", target_mc=brain.prep_target_mc)
            brain.prep_phase = "start_menu_navigating"
            brain.prep_phase_entered_at = brain.timestep; return
        elif brain.start_menu_active and brain.start_menu_context == "preparation":
            if mc == brain.prep_target_mc:
                brain.prep_phase = "pressing_a"
                brain.prep_phase_entered_at = brain.timestep
            return

    if brain.prep_phase == "pressing_start":
        if gs == 1: brain.prep_phase = "navigating_menu"; brain.prep_phase_entered_at = brain.timestep
    elif brain.prep_phase == "waiting_for_menu":
        if gs == 1: brain.prep_phase = "navigating_menu"; brain.prep_phase_entered_at = brain.timestep
    elif brain.prep_phase == "navigating_menu":
        if mc == brain.prep_target_mc: brain.prep_phase = "pressing_a"; brain.prep_phase_entered_at = brain.timestep
        elif gs != 1: abort_preparation(brain, "menu_closed")
    elif brain.prep_phase == "pressing_a":
        if gs == 14 and brain.prep_target == "bag": brain.prep_phase = "waiting_for_open"; brain.prep_phase_entered_at = brain.timestep
        elif gs != 1: brain.prep_phase = "waiting_for_open"; brain.prep_phase_entered_at = brain.timestep
    elif brain.prep_phase == "start_menu_navigating":
        if gs != 1:
            brain.prep_phase = "waiting_for_open"
            brain.prep_phase_entered_at = brain.timestep


def get_preparation_action(brain):
    if not brain.prep_active: return None
    if brain.start_menu_active and brain.start_menu_context == "preparation": return None
    mc = brain.menu_data.get('mc', -1)
    if brain.prep_phase in ("pressing_start", "waiting_for_menu"): return "START"
    elif brain.prep_phase == "navigating_menu":
        if mc < 0: return "START"
        if mc == brain.prep_target_mc: return "A"
        return "DOWN" if mc < brain.prep_target_mc else "UP"
    elif brain.prep_phase == "pressing_a": return "A"
    elif brain.prep_phase == "start_menu_navigating":
        if not brain.start_menu_active: return "START"
        return None
    return None


def get_preparation_status(brain):
    if not brain.prep_active: return {'active': False}
    return {'active': True, 'phase': brain.prep_phase, 'target': brain.prep_target,
            'reason': brain.prep_reason, 'frames': brain.timestep - brain.prep_started_at,
            'total_count': brain.prep_total_count, 'success_count': brain.prep_success_count,
            'start_menu_nav': brain.start_menu_active and brain.start_menu_context == "preparation"}


# ============================================================================
# PARTY HP / STATUS HELPERS (used by preparation + bag)
# ============================================================================

def get_party_hp_ratios(brain):
    return [s.get('hp',0)/s.get('max_hp',1) if s.get('max_hp',0) > 0 else 0.0
            for s in brain.party_data.get('slots', [])]


def get_party_status_flags(brain):
    return [s.get('status', 0) for s in brain.party_data.get('slots', [])]


def get_lowest_hp_ratio(brain):
    living = [r for r in get_party_hp_ratios(brain) if r > 0.0]
    return min(living) if living else 0.0


def has_status_condition_in_party(brain):
    return any(s.get('hp',0) > 0 and s.get('status',0) != 0 for s in brain.party_data.get('slots', []))


def get_healing_items(brain):
    return [(it.get('id',0), it.get('q',0), brain.item_knowledge[it['id']]['category'],
             brain.item_knowledge[it['id']]['confidence'])
            for it in brain.bag_data.get('items', [])
            if it.get('id',0) > 0 and it.get('q',0) > 0 and
            it['id'] in brain.item_knowledge and
            brain.item_knowledge[it['id']]['category'] in ('heal_hp','heal_status','heal_both')]


def get_catch_items(brain):
    return [(it.get('id',0), it.get('q',0), brain.item_knowledge[it['id']]['confidence'])
            for it in brain.bag_data.get('items', [])
            if it.get('id',0) > 0 and it.get('q',0) > 0 and
            it['id'] in brain.item_knowledge and
            brain.item_knowledge[it['id']]['category'] == 'catch']


# ============================================================================
# CHAIN-SPECIFIC ENTITY SPAWNING (legacy)
# ============================================================================

def spawn_innate_overworld_entities(brain, learning_state):
    if brain.innate_entities_spawned_overworld: return
    for etype, indices in [("sense_menu", [5, 6]), ("sense_battle", [3, 4]),
                            ("sense_movement", [0, 1]), ("sense_map_transition", [2])]:
        entity = Perceptron("entity", entity_type=etype, chain="overworld")
        entity.ensure_weights(len(learning_state))
        entity.weights = np.zeros(len(learning_state))
        for idx in indices:
            entity.weights[idx] = 0.5 if len(indices) > 1 else 1.0
        brain.add(entity)
    brain.innate_entities_spawned_overworld = True
    brain.innate_entities_spawned = True
    print(f"  🧬 Innate overworld entities spawned (4)")


def spawn_innate_battle_entities(brain, learning_state):
    if brain.innate_entities_spawned_battle: return
    innate_battle = [
        ("battle_hp_crisis", [1]), ("battle_enemy_weak", [20]),
        ("battle_species_match", [0, 19]), ("battle_status", [3, 22]),
        ("battle_trainer", [38]),
    ]
    for etype, indices in innate_battle:
        entity = Perceptron("entity", entity_type=etype, chain="battle")
        entity.ensure_weights(len(learning_state))
        entity.weights = np.zeros(len(learning_state))
        for idx in indices:
            if idx < len(learning_state):
                entity.weights[idx] = 0.5 if len(indices) > 1 else 1.0
        brain.add(entity)
    brain.innate_entities_spawned_battle = True
    print(f"  🧬 Innate battle entities spawned ({len(innate_battle)})")


def spawn_entity_for_chain(brain, chain, learning_state, context_state=None, raw_position=None):
    count = brain.entity_spawn_counts.get(chain, 0)
    entity = Perceptron("entity", entity_type=f"{chain}_spawned_{count}", chain=chain)
    entity.ensure_weights(len(learning_state))
    state_norm = np.linalg.norm(learning_state)
    if state_norm > 0:
        entity.weights = (learning_state / state_norm) * 0.1
    else:
        entity.weights = np.random.randn(len(learning_state)) * 0.001
    entity.utility = 1.0
    brain.add(entity)
    brain.entity_spawn_counts[chain] = count + 1
    if chain == "overworld":
        brain.entity_spawn_count = brain.entity_spawn_counts['overworld']
    check_chain_entity_capacity(brain, chain)


def check_chain_entity_capacity(brain, chain):
    n_entities = brain.get_chain_entity_count(chain)
    capacity = brain.get_chain_entity_capacity(chain)
    if n_entities < capacity: return
    before = n_entities
    cluster_chain_entities(brain, chain)
    after = brain.get_chain_entity_count(chain)
    if after >= before * 0.9:
        old_cap = brain.ENTITY_CAPACITY[chain]
        brain.ENTITY_CAPACITY[chain] = int(old_cap * brain.ENTITY_CAPACITY_GROWTH)
        print(f"  🧩 [{chain}] Entity capacity: {old_cap} → {brain.ENTITY_CAPACITY[chain]} "
              f"(clustering {before} → {after})")


def cluster_chain_entities(brain, chain):
    chain_entities = brain.entities(chain=chain)
    innate_types = {"sense_menu", "sense_battle", "sense_movement", "sense_map_transition",
                    "battle_hp_crisis", "battle_enemy_weak", "battle_species_match",
                    "battle_status", "battle_trainer"}
    spawned = [e for e in chain_entities if e.entity_type not in innate_types]
    innate = [e for e in chain_entities if e.entity_type in innate_types]
    if len(spawned) < 2: return

    clusterable = [e for e in spawned if len(e.cluster_activations) >= brain.ENTITY_MIN_ACTIVATIONS]
    too_young = [e for e in spawned if len(e.cluster_activations) < brain.ENTITY_MIN_ACTIVATIONS]
    if len(clusterable) < 2: return

    max_len = max(len(e.cluster_activations) for e in clusterable)
    activation_vecs = []
    for e in clusterable:
        vec = list(e.cluster_activations)
        while len(vec) < max_len: vec.append(0.0)
        activation_vecs.append(np.array(vec))

    merged_indices = set()
    merge_groups = []
    for i in range(len(clusterable)):
        if i in merged_indices: continue
        group = [i]
        vec_i = activation_vecs[i]
        norm_i = np.linalg.norm(vec_i)
        if norm_i < 1e-10: continue
        for j in range(i + 1, len(clusterable)):
            if j in merged_indices: continue
            vec_j = activation_vecs[j]
            norm_j = np.linalg.norm(vec_j)
            if norm_j < 1e-10: continue
            cosine_sim = np.dot(vec_i, vec_j) / (norm_i * norm_j)
            if cosine_sim >= brain.ENTITY_CLUSTER_SIMILARITY:
                group.append(j); merged_indices.add(j)
        if len(group) > 1:
            merged_indices.add(i); merge_groups.append(group)

    if not merge_groups: return

    new_entities = []
    merged_set = set()
    for group in merge_groups:
        group_ents = [clusterable[idx] for idx in group]
        min_dim = min(len(e.weights) for e in group_ents if e.weights is not None)
        if min_dim == 0: continue
        avg_w = np.zeros(min_dim)
        for e in group_ents: avg_w += e.weights[:min_dim]
        avg_w /= len(group_ents)

        merge_count = brain.entity_merge_counts.get(chain, 0)
        merged = Perceptron("entity", entity_type=f"{chain}_merged_{merge_count}", chain=chain)
        merged.weights = avg_w
        merged.utility = max(e.utility for e in group_ents)
        merged.familiarity = np.mean([e.familiarity for e in group_ents])
        merged.learning_rate = np.mean([e.learning_rate for e in group_ents])
        best_ent = max(group_ents, key=lambda e: e.activation_fit_score)
        merged.active_activation = best_ent.active_activation
        merged.activation_fit_score = best_ent.activation_fit_score
        new_entities.append(merged)
        brain.entity_merge_counts[chain] = merge_count + 1
        for idx in group: merged_set.add(id(clusterable[idx]))

    kept_spawned = [e for e in clusterable if id(e) not in merged_set]
    other_perceptrons = [p for p in brain.perceptrons if p.kind != "entity" or p.chain != chain]
    brain.perceptrons = other_perceptrons + innate + kept_spawned + too_young + new_entities
    brain._cache_valid = False

    total_merged = sum(len(g) for g in merge_groups)
    print(f"  🧩 [{chain}] CLUSTERED: {total_merged} → {len(new_entities)} | "
          f"Total: {brain.get_chain_entity_count(chain)}")


# ============================================================================
# POOL-AWARE ENTITY SPAWNING
# ============================================================================

def get_pool_spawn_context(brain, pipeline_id, layer_index, game_state_data=None):
    if game_state_data is None: game_state_data = {}

    if pipeline_id == "battle":
        if layer_index == 0:
            es = game_state_data.get('enemy_species', -1)
            ps = game_state_data.get('player_species', -1)
            return f"battle_id_es{es}" if es > 0 else f"battle_id_ps{ps}"
        elif layer_index == 1:
            es = game_state_data.get('enemy_species', -1)
            ps = game_state_data.get('player_species', -1)
            return f"battle_threat_{ps}v{es}"
        else:
            return f"battle_L{layer_index}_{brain.current_battle_id}"
    elif pipeline_id == "overworld":
        map_id = game_state_data.get('map_id', brain.current_map_id or 0)
        if layer_index == 0: return f"ow_spatial_map{map_id}"
        elif layer_index == 1: return f"ow_area_map{map_id}"
        else: return f"ow_L{layer_index}_map{map_id}_{brain.timestep}"
    elif pipeline_id == "bag":
        pocket = game_state_data.get('pocket', brain.bag_data.get('pocket', -1))
        return f"bag_L{layer_index}_pk{pocket}"
    elif pipeline_id == "party":
        return f"party_L{layer_index}_{brain.timestep}"
    return f"{pipeline_id}_L{layer_index}_{brain.timestep}"


def spawn_into_pipeline_pool(brain, pipeline_id, layer_index, input_state,
                              game_state_data=None, entity_type=None):
    pipeline = brain.pipelines.get(pipeline_id)
    if pipeline is None: return None
    if layer_index < 0 or layer_index >= pipeline.num_layers: return None

    pool = pipeline.pools[layer_index]
    n_current = pool.get_perceptron_count(brain.perceptrons)
    if n_current >= pool.max_perceptrons:
        cluster_pipeline_pool(brain, pipeline_id, layer_index)
        n_current = pool.get_perceptron_count(brain.perceptrons)
        if n_current >= pool.max_perceptrons:
            pool.max_perceptrons = int(pool.max_perceptrons * 1.5)
            print(f"  🧩 [{pipeline_id}.{pool.name}] Pool capacity grown to {pool.max_perceptrons}")

    trigger_context = get_pool_spawn_context(brain, pipeline_id, layer_index, game_state_data)
    if entity_type is None:
        entity_type = f"{pipeline_id}_{pool.name}_{pool.spawn_count}"

    p = Perceptron("entity", entity_type=entity_type, chain=pipeline_id)
    p.trigger_context = trigger_context
    p.ensure_weights(len(input_state))
    state_norm = np.linalg.norm(input_state)
    if state_norm > 0:
        p.weights = (input_state / state_norm) * 0.1
    else:
        p.weights = np.random.randn(len(input_state)) * 0.001
    p.utility = 1.0

    result = pipeline.spawn_into_pool(layer_index, p, brain)
    return result


def cluster_pipeline_pool(brain, pipeline_id, layer_index):
    pipeline = brain.pipelines.get(pipeline_id)
    if pipeline is None: return
    pool = pipeline.pools[layer_index]
    pool_perceptrons = [p for p in brain.perceptrons if p.pool_id == pool.pool_id]
    if len(pool_perceptrons) < 2: return

    clusterable = [p for p in pool_perceptrons if len(p.cluster_activations) >= brain.ENTITY_MIN_ACTIVATIONS]
    too_young = [p for p in pool_perceptrons if len(p.cluster_activations) < brain.ENTITY_MIN_ACTIVATIONS]
    if len(clusterable) < 2: return

    max_len = max(len(p.cluster_activations) for p in clusterable)
    activation_vecs = []
    for p in clusterable:
        vec = list(p.cluster_activations)
        while len(vec) < max_len: vec.append(0.0)
        activation_vecs.append(np.array(vec))

    merged_indices = set()
    merge_groups = []
    for i in range(len(clusterable)):
        if i in merged_indices: continue
        group = [i]
        vec_i = activation_vecs[i]
        norm_i = np.linalg.norm(vec_i)
        if norm_i < 1e-10: continue
        for j in range(i + 1, len(clusterable)):
            if j in merged_indices: continue
            vec_j = activation_vecs[j]
            norm_j = np.linalg.norm(vec_j)
            if norm_j < 1e-10: continue
            cosine_sim = np.dot(vec_i, vec_j) / (norm_i * norm_j)
            if cosine_sim >= brain.ENTITY_CLUSTER_SIMILARITY:
                group.append(j); merged_indices.add(j)
        if len(group) > 1:
            merged_indices.add(i); merge_groups.append(group)

    if not merge_groups: return

    new_perceptrons = []
    paged_set = set()
    for group in merge_groups:
        group_ents = [clusterable[idx] for idx in group]
        min_dim = min(len(p.weights) for p in group_ents if p.weights is not None)
        if min_dim == 0: continue
        avg_w = np.zeros(min_dim)
        for p in group_ents: avg_w += p.weights[:min_dim]
        avg_w /= len(group_ents)

        merged = Perceptron("entity",
                           entity_type=f"{pipeline_id}_{pool.name}_merged_{pool.spawn_count}",
                           chain=pipeline_id)
        merged.weights = avg_w
        merged.utility = max(p.utility for p in group_ents)
        merged.familiarity = np.mean([p.familiarity for p in group_ents])
        merged.learning_rate = np.mean([p.learning_rate for p in group_ents])
        best_ent = max(group_ents, key=lambda p: p.activation_fit_score)
        merged.active_activation = best_ent.active_activation
        merged.activation_fit_score = best_ent.activation_fit_score
        merged.pool_id = pool.pool_id
        merged.layer_index = layer_index
        merged.trigger_context = best_ent.trigger_context
        pool.spawn_count += 1
        new_perceptrons.append(merged)

        for idx in group:
            p = clusterable[idx]
            pool.page_to_residual(p)
            paged_set.add(id(p))

    kept = [p for p in clusterable if id(p) not in paged_set]
    other = [p for p in brain.perceptrons if p.pool_id != pool.pool_id]
    brain.perceptrons = other + kept + too_young + new_perceptrons
    brain._cache_valid = False

    total_merged = sum(len(g) for g in merge_groups)
    print(f"  🧩 [{pipeline_id}.{pool.name}] POOL CLUSTERED: "
          f"{total_merged} → {len(new_perceptrons)} | residual: {len(pool.residual)}")


# ============================================================================
# RESIDUAL FILE PERSISTENCE
# ============================================================================

def save_residual_file(brain, filepath=None):
    filepath = filepath or brain.RESIDUAL_FILE
    try:
        data = {}
        for pid, pipeline in brain.pipelines.items():
            pipeline_residuals = {}
            for i, pool in enumerate(pipeline.pools):
                if pool.residual:
                    pipeline_residuals[pool.pool_id] = pool.residual
            if pipeline_residuals:
                data[pid] = pipeline_residuals
        if data:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
    except Exception as e:
        print(f"  ⚠️ Error saving residual file: {e}")


def load_residual_file(brain, filepath=None):
    filepath = filepath or brain.RESIDUAL_FILE
    try:
        if not Path(filepath).exists(): return
        with open(filepath, 'r') as f:
            data = json.load(f)
        total_loaded = 0
        for pid, pipeline_residuals in data.items():
            pipeline = brain.pipelines.get(pid)
            if pipeline is None: continue
            for pool_id, residual_entries in pipeline_residuals.items():
                for pool in pipeline.pools:
                    if pool.pool_id == pool_id:
                        pool.residual = residual_entries
                        total_loaded += len(residual_entries)
                        break
        if total_loaded > 0:
            print(f"  🔄 Residual file loaded: {total_loaded} paged perceptrons")
    except Exception as e:
        print(f"  ⚠️ Error loading residual file: {e}")


# ============================================================================
# MENU TRAP B-BOOST
# ============================================================================

def update_menu_trap_tracking(brain, context_state, action_taken, raw_position=None):
    if context_state[3] > 0.5: reset_menu_trap_boost(brain); return
    if brain.party_menu_active: reset_menu_trap_boost(brain); return
    if brain.bag_thread_active: reset_menu_trap_boost(brain); return
    if brain.start_menu_active: reset_menu_trap_boost(brain); return
    if brain.dialogue_active: reset_menu_trap_boost(brain); return

    gs = brain.game_state_raw
    if gs == 14: reset_menu_trap_boost(brain); return

    if gs == 1:
        mc = brain.menu_data.get('mc', -1)
        mm = brain.menu_data.get('mm', -1)
        pc = brain.menu_data.get('pc', -1)
        if 0 <= pc <= 6: reset_menu_trap_boost(brain); return
        if 0 <= mc <= 6 and mm >= 4: reset_menu_trap_boost(brain); return

    current_pos = raw_position if raw_position else (round(context_state[0] * 255), round(context_state[1] * 255))
    if brain.menu_trap_position is not None and current_pos != brain.menu_trap_position:
        reset_menu_trap_boost(brain); return

    ctx_hash = (round(context_state[0], 2), round(context_state[1], 2), int(context_state[2]),
                int(context_state[3]), round(context_state[4], 2), int(context_state[5]))
    if ctx_hash == brain.last_context_state_hash:
        if action_taken in ["A", "B", "Start", "Select"]:
            brain.menu_trap_frames += 1
            brain.menu_trap_position = current_pos
            if brain.menu_trap_frames > brain.MENU_TRAP_THRESHOLD:
                if brain.original_b_utility is None:
                    for a in brain.actions():
                        if a.action == 'B':
                            brain.original_b_utility = a.utility; break
                brain.menu_trap_b_boost = min(brain.B_BOOST_MAX, brain.menu_trap_b_boost + brain.B_BOOST_INCREMENT)
    elif current_pos != brain.menu_trap_position:
        reset_menu_trap_boost(brain)


def reset_menu_trap_boost(brain):
    if brain.menu_trap_b_boost > 1.0 and brain.original_b_utility is not None:
        for a in brain.actions():
            if a.action == 'B':
                a.utility = brain.original_b_utility; break
    brain.menu_trap_frames = 0
    brain.menu_trap_b_boost = 1.0
    brain.menu_trap_position = None
    brain.original_b_utility = None


# ============================================================================
# EVENT RECORDER HELPERS
# ============================================================================

def push_event(brain, event_type, event_data):
    if brain.event_queue is None or not brain.event_recorder_active:
        return False
    event = {
        'type': event_type, 'timestep': brain.timestep,
        'time': time.time(), 'map_id': brain.current_map_id,
        'data': event_data,
    }
    try:
        brain.event_queue.put_nowait(event)
        if event_type == 'battle_end': brain.recorded_battle_events += 1
        elif event_type == 'bag_session': brain.recorded_bag_events += 1
        elif event_type == 'map_transition': brain.recorded_map_events += 1
        elif event_type == 'level_up': brain.recorded_levelup_events += 1
        return True
    except Exception:
        return False


def get_event_recorder_stats(brain):
    return {
        'active': brain.event_recorder_active,
        'battles': brain.recorded_battle_events,
        'bags': brain.recorded_bag_events,
        'maps': brain.recorded_map_events,
        'levelups': brain.recorded_levelup_events,
        'total': (brain.recorded_battle_events + brain.recorded_bag_events +
                  brain.recorded_map_events + brain.recorded_levelup_events),
    }


# ============================================================================
# ATTACH ALL METHODS TO BRAIN CLASS
# ============================================================================

def attach_to_brain(BrainClass):
    """
    Attach all brain_systems functions as methods on the Brain class.
    Call this once at import time: attach_to_brain(Brain)
    """
    # Event timeline
    BrainClass.load_event_timeline = load_event_timeline
    BrainClass.get_nearest_nav_order = get_nearest_nav_order
    BrainClass.get_upcoming_events = get_upcoming_events
    BrainClass.get_upcoming_battles = get_upcoming_battles
    BrainClass.get_upcoming_trainer_battles = get_upcoming_trainer_battles
    BrainClass.get_segment_difficulty = get_segment_difficulty
    BrainClass.get_preparation_point = get_preparation_point
    BrainClass.get_estimated_hp_cost_ahead = get_estimated_hp_cost_ahead
    BrainClass.get_timeline_status = get_timeline_status

    # Map battle stats
    BrainClass.get_map_battle_stats = get_map_battle_stats
    BrainClass.update_map_battle_stats = update_map_battle_stats
    BrainClass.increment_map_steps = increment_map_steps
    BrainClass.predict_hp_cost_for_map = predict_hp_cost_for_map
    BrainClass.predict_hp_cost_for_route = predict_hp_cost_for_route
    BrainClass.get_autonomous_hp_estimate = get_autonomous_hp_estimate
    BrainClass.get_map_battle_stats_summary = get_map_battle_stats_summary

    # Dialogue
    BrainClass.update_dialogue_state = update_dialogue_state
    BrainClass.is_dialogue_skip_state = is_dialogue_skip_state
    BrainClass.is_dialogue_choice_state = is_dialogue_choice_state
    BrainClass.get_dialogue_status = get_dialogue_status

    # Start menu
    BrainClass.open_start_menu = open_start_menu
    BrainClass.close_start_menu = close_start_menu
    BrainClass.is_start_menu_active = is_start_menu_active
    BrainClass.set_start_menu_last_action = set_start_menu_last_action
    BrainClass.update_start_menu_state = update_start_menu_state
    BrainClass.get_start_menu_status = get_start_menu_status

    # Preparation
    BrainClass.should_prepare = should_prepare
    BrainClass.start_preparation = start_preparation
    BrainClass.abort_preparation = abort_preparation
    BrainClass.is_preparation_active = is_preparation_active
    BrainClass.update_preparation_state = update_preparation_state
    BrainClass.get_preparation_action = get_preparation_action
    BrainClass.get_preparation_status = get_preparation_status

    # Party HP helpers
    BrainClass.get_party_hp_ratios = get_party_hp_ratios
    BrainClass.get_party_status_flags = get_party_status_flags
    BrainClass.get_lowest_hp_ratio = get_lowest_hp_ratio
    BrainClass.has_status_condition_in_party = has_status_condition_in_party
    BrainClass.get_healing_items = get_healing_items
    BrainClass.get_catch_items = get_catch_items

    # Entity spawning (chain)
    BrainClass.spawn_innate_overworld_entities = spawn_innate_overworld_entities
    BrainClass.spawn_innate_battle_entities = spawn_innate_battle_entities
    BrainClass.spawn_entity_for_chain = spawn_entity_for_chain
    BrainClass.check_chain_entity_capacity = check_chain_entity_capacity
    BrainClass.cluster_chain_entities = cluster_chain_entities

    # Entity spawning (pool)
    BrainClass.get_pool_spawn_context = get_pool_spawn_context
    BrainClass.spawn_into_pipeline_pool = spawn_into_pipeline_pool
    BrainClass.cluster_pipeline_pool = cluster_pipeline_pool

    # Residual persistence
    BrainClass.save_residual_file = save_residual_file
    BrainClass.load_residual_file = load_residual_file

    # Menu trap
    BrainClass.update_menu_trap_tracking = update_menu_trap_tracking
    BrainClass.reset_menu_trap_boost = reset_menu_trap_boost

    # Event recorder
    BrainClass.push_event = push_event
    BrainClass.get_event_recorder_stats = get_event_recorder_stats