# ============================================================================
# main.py — Brain Construction, Data Loading, Main Loop, Shutdown
# ============================================================================
# Entry point. Wires all modules together, attaches methods to Brain,
# creates threads, runs the main processing loop.
# ============================================================================

import time
import gc
import tracemalloc
import numpy as np

# === PROJECT IMPORTS ===
from constants import (
    BASE_PATH, MODEL_CHECKPOINT_FILE, ROSTER_FILE, MOVE_KNOWLEDGE_FILE,
    ITEM_KNOWLEDGE_FILE, TYPE_CLUSTERS_FILE, TYPE_DATA_FILE,
    AI_EVENT_TIMELINE_FILE, TAUGHT_MODELS_DIR,
    MARKOV_FAMILIARITY_THRESHOLD,
    BATTLE_MARKOV_THRESHOLD_LOW, BATTLE_MARKOV_THRESHOLD_HIGH,
    BAG_MARKOV_THRESHOLD, START_MENU_MARKOV_THRESHOLD,
)
from state import compute_derived_features, build_learning_state_overworld
from perceptron import Perceptron, ACTIVATION_LIBRARY
from pool import Pool, Pipeline
from brain_core import Brain

# === ATTACH ALL SUBSYSTEM METHODS TO BRAIN ===
import brain_systems
import brain_data
import markov
import exploration
import navigation
import stagnation
import learning

brain_systems.attach_to_brain(Brain)
brain_data.attach_to_brain(Brain)
markov.attach_to_brain(Brain)
exploration.attach_to_brain(Brain)
navigation.attach_to_brain(Brain)
stagnation.attach_to_brain(Brain)
learning.attach_to_brain(Brain)

from action_selection import anticipatory_action, text_dialogue_action
from cache import CacheManager, IOThread, SaveWorkerThread, EventRecorderThread


# ============================================================================
# STARTUP
# ============================================================================

tracemalloc.start()

brain = Brain()

# === CREATE ACTION PERCEPTRONS ===
for b in ["UP", "DOWN", "LEFT", "RIGHT"]:
    brain.add(Perceptron("action", action=b, group="move", chain="shared"))
for b in ["A", "B", "Start", "Select"]:
    brain.add(Perceptron("action", action=b, group="interact", chain="shared"))

# === LOAD EXPLORATION MEMORY (deferred from __init__) ===
brain.load_exploration_memory()

# === LOAD ALL TAUGHT MODELS ===
brain.load_all_taught_models()

# === LOAD MODEL (3-way: resume → bootstrap → fresh) ===
bootstrapped_from_taught = False
taught_timestep = 0

if MODEL_CHECKPOINT_FILE.exists():
    loaded_ts = brain.load_taught_model(MODEL_CHECKPOINT_FILE)
    print(f"🤖 AI MODEL: Resumed from timestep {loaded_ts}")
    print(f"   Utils: {[f'{a.action}:{a.utility:.3f}' for a in brain.actions()]}")
else:
    if brain.best_taught_checkpoint_path is not None:
        taught_timestep = brain.initialize_from_taught_model(brain.best_taught_checkpoint_path)
        bootstrapped_from_taught = True
    else:
        print("🤖 AI MODEL: Starting fresh (no taught models found)")

# === LOAD TAUGHT REFERENCE ===
if brain.best_taught_checkpoint_path is not None:
    brain.load_taught_reference(brain.best_taught_checkpoint_path)
else:
    print("  📖 No taught reference available (no model folders)")

# === LOAD ALL AI-OWNED DATA ===
brain.load_roster(ROSTER_FILE)
brain.load_move_knowledge(MOVE_KNOWLEDGE_FILE)
brain.load_item_knowledge(ITEM_KNOWLEDGE_FILE)
brain.load_type_clusters(TYPE_CLUSTERS_FILE)
brain.load_ground_truth_types(TYPE_DATA_FILE)
brain.load_residual_file()

map_graph = brain.build_map_graph()
graph_edges = sum(len(v) for v in map_graph.values())
graph_maps = list(map_graph.keys())

cache_manager = CacheManager(brain)
cache_manager.load_all()
cache_manager.detect_and_set_initial_map()

# === START THREADS ===
io_thread = IOThread(cache_manager, interval=0.02, gc_interval=300)
io_thread.start()

save_worker = SaveWorkerThread(maxsize=3)
save_worker.start()

event_recorder = EventRecorderThread(
    filepath=AI_EVENT_TIMELINE_FILE,
    flush_interval=brain.EVENT_RECORDER_FLUSH_INTERVAL,
    max_queue_size=100, max_events=5000
)
event_recorder.start()

brain.event_queue = event_recorder.get_queue()
brain.event_recorder_active = True

exploration_weight = 1.3
prev_context_state = None
prev_raw_position = None
last_processed_version = -1
battle_outcomes = {'win': 0, 'loss': 0, 'run': 0, 'catch': 0, 'unknown': 0}

_mem_baseline = tracemalloc.get_traced_memory()

# ============================================================================
# STARTUP BANNER
# ============================================================================

print("="*70)
print("AI CONTROL — Markov + Taught Navigation (No Forced Exploration)")
print("="*70)

print("BOOTSTRAP STATUS:")
if bootstrapped_from_taught:
    cs = brain.get_chain_stats()
    cs_str = ' | '.join(f"{c}:{s['actions']}a+{s['entities']}e" for c, s in cs.items())
    print(f"  🎓 Bootstrapped from taught model ({taught_timestep} human steps)")
    print(f"  Perceptrons: {len(brain.perceptrons)} ({cs_str})")
    print(f"  AI starts at timestep 0 — will refine through play")
else:
    if MODEL_CHECKPOINT_FILE.exists(): print(f"  Resumed own checkpoint (no bootstrap needed)")
    else: print(f"  No bootstrap (fresh start)")
print(f"  📚 Taught models: {brain.taught_model_count} loaded from {TAUGHT_MODELS_DIR}")

print("="*70)
print("ARCHITECTURE:")
print(f"  Chains: overworld(visual/spatial) | battle(compact) | party | bag")
print(f"  Empirical activation discovery: {', '.join(ACTIVATION_LIBRARY.get_names())}")
chain_stats = brain.get_chain_stats()
if chain_stats:
    for c, s in chain_stats.items(): print(f"    {c}: {s['actions']}actions {s['entities']}entities")
act_counts = {}
for p in brain.perceptrons: act_counts[p.active_activation] = act_counts.get(p.active_activation, 0) + 1
if act_counts:
    print(f"  Activations: {' '.join(f'{k}:{v}' for k,v in sorted(act_counts.items(), key=lambda x:x[1], reverse=True))}")

print("="*70)
print("NAVIGATION MODE:")
print(f"  Primary: Markov matching from taught demonstrations")
print(f"  Secondary: A* navigation to taught targets / revenge targets")
print(f"  No autonomous exploration — AI only navigates to specific targets")
print(f"  Nav trigger: when Markov doesn't match, check for taught targets")

print("="*70)
print("PIPELINES:")
for pid, pipeline in brain.pipelines.items():
    layers_str = ' → '.join(pool.name for pool in pipeline.pools)
    total_p = sum(pool.get_perceptron_count(brain.perceptrons) for pool in pipeline.pools)
    total_r = sum(len(pool.residual) for pool in pipeline.pools)
    print(f"  {pid} ({pipeline.num_layers}L, decay={pipeline.credit_decay}): {layers_str}")
    print(f"    perceptrons: {total_p} | residual: {total_r} | authority: {pipeline.get_total_authority():.0%}")
print(f"  Fallback chain: Pipeline → Markov → Hardcoded (graceful degradation)")

print("="*70)
print("THREADS:")
print(f"  IOThread: game state I/O (20ms)")
print(f"  SaveWorkerThread: background file saves (queue=3)")
print(f"  EventRecorderThread: AI event recording (flush={brain.EVENT_RECORDER_FLUSH_INTERVAL}s)")
print(f"  Priority: PartyMenu → Dialogue → StartMenu → Bag → Battle → Prep → Overworld")

print("="*70)
print("DIALOGUE:")
print(f"  TextFlag: ADDR_DIALOGUE 0x0202004F (0=no text, 1=text active)")
print(f"  Pure text → A/B skip (no utility tracking)")
print(f"  Dialogue choice → mm≤{brain.DIALOGUE_CHOICE_MM_MAX} with valid cursor (real decision)")
print(f"  Battle text → dialog priority over battle cursor when both active")

print("="*70)
print("START MENU:")
print(f"  Transitions: {'LOADED' if brain.start_menu_loaded else 'NOT FOUND'} | Markov: {START_MENU_MARKOV_THRESHOLD:.2f}")
if brain.start_menu_loaded:
    print(f"  Frames: {len(brain.start_menu_transitions)} | Sessions: {brain.start_menu_metadata.get('sessions_recorded', 0)}")

print("="*70)
print("TYPE CHART:")
tc_status = brain.get_type_chart_status()
print(f"  Track A (empirical): {tc_status['move_clusters']}mc {tc_status['species_clusters']}sc "
      f"{tc_status['effectiveness_entries']}eff | runs: {tc_status['clustering_runs']}")
print(f"  Track B (ground truth): {'LOADED' if tc_status['track_b_loaded'] else 'NOT FOUND'}")

print("="*70)
print("REVENGE MODULE:")
rs = brain.get_revenge_status()
if rs['targets'] > 0:
    print(f"  Targets: {rs['targets']} ({rs['by_status']})")
    tid, target = brain.get_active_revenge_target()
    if target: print(f"  Active: {tid} → target Lv{target['target_avg_level']:.0f} "
                     f"(losses: {target['losses_here']}, status: {target['status']})")
else: print(f"  No revenge targets")

print("="*70)
print("PREPARATION:")
tl = brain.get_timeline_status()
if tl['loaded']: print(f"  Timeline: {tl['events']}ev {tl['segments']}seg {tl['prep_points']}prep")
else: print(f"  Timeline: NOT LOADED")
mbs = brain.get_map_battle_stats_summary()
print(f"  Map stats: {mbs['maps_with_data']}maps {mbs['total_battles']}battles")

print("="*70)
print("BAG:")
print(f"  Transitions: {'LOADED' if brain.bag_loaded else 'NOT FOUND'} | Markov: {BAG_MARKOV_THRESHOLD:.2f}")
print(f"  Items: {len(brain.item_knowledge)} tracked")

print("="*70)
print("BATTLE:")
print(f"  Transitions: {'LOADED' if brain.battle_loaded else 'NOT FOUND'} | "
      f"Markov: {BATTLE_MARKOV_THRESHOLD_LOW:.2f}-{BATTLE_MARKOV_THRESHOLD_HIGH:.2f}")
print(f"  Move scoring: pipeline → direct → Track B → Track A clusters → avg damage")
print(f"  Dialog priority: text_flag checked before battle cursor actions")

print("="*70)
print("KNOWLEDGE:")
print(f"  Roster: {len(brain.roster)} | Moves: {len(brain.move_knowledge)} | Enemy: {len(brain.enemy_move_knowledge)}")

print("="*70)
print("CACHE | NAV:")
print(f"  Maps: {len(cache_manager.caches)} | Active: {cache_manager.active_map_id}")
ns = brain.get_nav_targets_status()
if ns['loaded']: print(f"  Nav: {ns['total']} targets ({ns['remaining']} remaining)")
print(f"  Graph: {len(graph_maps)}maps {graph_edges}edges")

print("="*70)
print("TAUGHT DATA (merged):")
print(f"  Models: {brain.taught_model_count}")
print(f"  OW frames: {len(brain.taught_transitions)} | Battle: {len(brain.battle_transitions)}")
print(f"  Bag: {len(brain.bag_transitions)} | Start menu: {len(brain.start_menu_transitions)}")
print(f"  Events: {len(brain.event_timeline)} | Nav targets: "
      f"{sum(len(t) for t in brain.taught_nav_targets.values())}")

print("="*70)
print("MEMORY:")
print(f"  tracemalloc: active | gc: milestones")
obs_stats = brain.get_activation_observation_stats()
print(f"  Activation obs: {obs_stats['_total']['observations']} (~{obs_stats['_total']['estimated_mb']:.2f}MB)")
print("="*70)


# ============================================================================
# MAIN LOOP
# ============================================================================

try:
    while True:
        active_cache = cache_manager.get_active()
        current_version = active_cache.get_version()
        if current_version == last_processed_version:
            time.sleep(0.005); continue

        (context_state, palette_state, tile_state, dead, raw_position,
         battle_data, party_data, game_state_raw, menu_data, bag_data,
         text_flag) = active_cache.get_state()
        last_processed_version = current_version

        if np.sum(np.abs(context_state)) < 0.001: time.sleep(0.01); continue

        raw_x, raw_y = raw_position
        in_battle = context_state[3]
        current_map = int(context_state[2])
        current_dir = int(context_state[5])

        brain.update_battle_data(battle_data)
        brain.update_party_data(party_data)
        brain.update_menu_data(menu_data)
        brain.update_bag_data(bag_data)
        brain.game_state_raw = game_state_raw
        brain.text_flag = text_flag
        brain.update_dialogue_state(context_state)

        brain.update_party_menu_state(context_state)
        brain.update_bag_thread_state(context_state)
        brain.update_start_menu_state(context_state)
        brain.check_item_observation()

        currently_in_battle = in_battle > 0.5

        if not currently_in_battle and game_state_raw == 0:
            brain.increment_map_steps(current_map)

        # === BATTLE START/END ===
        if currently_in_battle and not brain.in_battle_last_frame:
            brain.current_battle_id += 1; brain.battle_frame_count = 0
            brain.battle_action_history.clear(); brain.on_battle_start_with_data()
            bd = brain.battle_data
            bt_str = "TR" if (bd.get('battle_type',0) & 8) != 0 else "WD"
            sp = f" {bd['player_species']}v{bd['enemy_species']}" if bd['player_species'] > 0 else ""
            hp = f" HP:{bd['player_hp']}/{bd['player_max_hp']}" if bd['player_hp'] > 0 else ""
            print(f"\n  ⚔️ START #{brain.current_battle_id} {bt_str} Map{current_map}({raw_x},{raw_y}){sp}{hp}")
            if brain.has_battle_data() and bd['enemy_species'] > 0:
                ranked = brain.get_best_move_for_enemy(bd['enemy_species'])
                if ranked: print(f"     📖 {', '.join(f'm{m}(s{s} {sc:.1f})' for m,s,sc in ranked[:4])}")
            bp_auth = brain.battle_pipeline.get_total_authority()
            if bp_auth > 0: print(f"     🔗 Battle pipeline: {bp_auth:.0%} authority")
            mbs_cur = brain.map_battle_stats.get(current_map)
            if mbs_cur and mbs_cur['battles_fought'] > 0: print(f"     📊 Map: {mbs_cur['battles_fought']}bat avg{mbs_cur['avg_hp_cost']:.0%}")
            rs = brain.get_revenge_status()
            if rs['active']:
                tid, target = brain.get_active_revenge_target()
                if target and target['map_id'] == current_map:
                    print(f"     ⚔️🔥 REVENGE ZONE: {tid} (target Lv{target['target_avg_level']:.0f})")
            if brain.is_nav_active(): brain.abort_navigation("battle")

        elif currently_in_battle:
            if brain.has_battle_data() and brain.detect_turn_resolved():
                brain.on_battle_turn_end(); bd = brain.battle_data
                mi = f" m{brain.last_move_used}(s{brain.last_move_slot})" if brain.last_move_used > 0 else ""
                em = brain.detect_enemy_move(); ei = f" em{em}" if em > 0 else ""
                ri = " 🏃" if brain.should_run() else ""
                print(f"  ⚔️ T{brain.turn_count} {bd['player_hp']}/{bd['player_max_hp']} "
                      f"E:{bd['enemy_hp']}/{bd.get('enemy_max_hp','?')}{mi}{ei}{ri}")

        elif not currently_in_battle and brain.in_battle_last_frame:
            outcome = brain.on_battle_end_with_data()
            battle_outcomes[outcome] = battle_outcomes.get(outcome, 0) + 1
            emoji = {'win':'🏆','loss':'💀','run':'🏃','catch':'🎊','unknown':'❓'}.get(outcome,'❓')
            bmr = brain.battle_markov_action_count / max(1, brain.battle_action_count)
            print(f"\n  ⚔️ END #{brain.current_battle_id} {brain.turn_count}t {emoji}{outcome.upper()} "
                  f"Mk:{bmr:.0%} Cur:{brain.battle_cursor_action_count}")
            mbs_cur = brain.map_battle_stats.get(current_map)
            if mbs_cur: print(f"     📊 Map{current_map}: {mbs_cur['battles_fought']}bat "
                              f"avg{mbs_cur['avg_hp_cost']:.0%} rate{mbs_cur['encounter_rate']:.4f}")
            if outcome == 'loss':
                rs = brain.get_revenge_status()
                if rs['active']:
                    tid, target = brain.get_active_revenge_target()
                    if target: print(f"     ⚔️🔥 REVENGE: losses={target['losses_here']} "
                                     f"target Lv{target['target_avg_level']:.0f} status={target['status']}")
            brain.battle_frame_count = 0
            brain.push_event('battle_end', {
                'battle_id': brain.current_battle_id, 'outcome': outcome, 'turns': brain.turn_count,
                'enemy_species': brain.prev_battle_data.get('enemy_species', -1),
                'enemy_level': brain.prev_battle_data.get('enemy_level', -1),
                'is_trainer': brain.is_trainer_battle(),
                'player_hp_start': brain.battle_start_hp,
                'player_hp_end': brain.prev_battle_data.get('player_hp', -1),
                'party_snapshot': [{'hp': s.get('hp',0), 'max_hp': s.get('max_hp',0)}
                                   for s in brain.party_data.get('slots', [])],
            })
            if brain.battles_since_last_clustering >= brain.CLUSTERING_BATTLE_INTERVAL:
                brain.run_type_clustering()
                if brain.type_clusters_dirty: save_worker.submit_job({'type': 'type_clusters', 'brain': brain})
            save_worker.submit_dirty_knowledge(brain)

        brain.in_battle_last_frame = currently_in_battle

        # === MAP CHANGE ===
        if not currently_in_battle and current_map != cache_manager.active_map_id:
            prev_map = cache_manager.active_map_id
            cache_manager.switch_map(current_map); active_cache = cache_manager.get_active()
            print(f"  📦 Map{current_map} ({len(active_cache.get_taught_frames())}f)")
            brain.push_event('map_transition', {'from_map': prev_map, 'to_map': current_map, 'position': (raw_x, raw_y)})
            if brain.nav_map_chain and brain.is_nav_active() and not brain.is_nav_paused():
                if not brain.advance_map_chain(current_map, (raw_x, raw_y)):
                    brain.abort_navigation("chain broken")

        brain.update_position(raw_x, raw_y)
        derived = compute_derived_features(context_state, prev_context_state)
        learning_state = build_learning_state_overworld(derived, palette_state, tile_state, in_battle)
        brain.log_state(learning_state, context_state)
        brain.confirm_action_executed(context_state, prev_context_state)

        if brain.should_send_new_action():
            action = anticipatory_action(
                brain, learning_state, context_state,
                exploration_weight=exploration_weight,
                raw_position=raw_position,
                taught_frames=cache_manager.get_active_taught_frames(),
                map_density=cache_manager.get_map_density(),
                palette_state=palette_state
            )
            if action is not None:
                active_cache.set_pending_action(action.action)
                brain.last_action = action.action; brain.set_pending_action(action.action)
                if not currently_in_battle and not brain.is_dialogue_skip_state():
                    brain.update_menu_trap_tracking(context_state, action.action, raw_position=raw_position)
            else: active_cache.set_pending_action("NONE")
        else:
            if brain.pending_action: active_cache.set_pending_action(brain.pending_action)

        # === PERIODIC SAVES ===
        if brain.timestep % 200 == 0 and brain.timestep > 0:
            save_worker.submit_exploration(brain, cache_manager)
            save_worker.submit_dirty_knowledge(brain)

        # === 100-STEP LOGGING ===
        if brain.timestep % 100 == 0:
            memory = brain.get_current_map_memory(current_map)
            coverage = brain.get_exploration_coverage(current_map)
            density = cache_manager.get_map_density()
            gs_str = {0:"OW",1:"MENU",14:"BAG"}.get(game_state_raw, f"GS{game_state_raw}")
            dir_name = brain.DIRECTION_NAMES.get(current_dir, '?')
            ta = brain.markov_action_count + brain.curiosity_action_count
            mr = brain.markov_action_count / max(1, ta)
            tf_str = " TXT" if brain.text_flag == 1 else ""

            print(f"\n{'='*70}")
            print(f"Step {brain.timestep} | Map{current_map} ({raw_x},{raw_y}) {dir_name} | gs={gs_str}{tf_str}")
            print(f"  Mode: {'BOTH⚡' if brain.should_use_both_mode() else brain.control_mode} | Stag: {brain.state_stagnation_count}")

            ds = brain.get_dialogue_status()
            if ds['active']:
                dtype = 'CHOICE' if ds.get('is_choice') else ('BATTLE_TXT' if ds.get('is_battle_text') else 'PURE_TXT')
                print(f"  💬 DIALOGUE: {dtype} ({ds.get('frames_in_current',0)}f)")
            if ds['total_skip_actions'] > 0 or ds['total_choice_actions'] > 0:
                print(f"  💬 Dialogue totals: {ds['total_skip_actions']}skip {ds['total_choice_actions']}choice {ds['total_frames']}f")

            p_summary = brain.get_pipeline_summary()
            if p_summary != 'all empty': print(f"  🔗 Pipelines: {p_summary}")

            rs = brain.get_revenge_status()
            if rs['targets'] > 0:
                tid, target = brain.get_active_revenge_target()
                if target: print(f"  ⚔️🔥 Revenge: {tid} → Lv{target['target_avg_level']:.0f} ({target['status']}, {target['losses_here']}L)")
                else: print(f"  ⚔️ Revenge: {rs['targets']} targets ({rs['by_status']})")

            if brain.bounding_rect_debt > 0.5:
                br_info = brain.get_bounding_rect_info()
                print(f"  📐 BoundingRect: debt={br_info['debt']:.1f} area={br_info.get('area','?')} density={br_info.get('density',0):.1f}")

            if brain.is_party_menu_active(): print(f"  📋 PARTY: {brain.party_menu_context} ({brain.timestep-brain.party_menu_entered_at}f)")
            if brain.is_start_menu_active():
                sms = brain.get_start_menu_status()
                print(f"  📋 START MENU: {sms['context']} mc→{sms.get('target_mc',-1)} ({sms['frames']}f {sms['actions']}act)")
            if brain.is_bag_thread_active():
                bf = brain.timestep - brain.bag_thread_entered_at; ci = brain.get_item_at_cursor()
                print(f"  🎒 BAG: {brain.bag_thread_context} ({bf}f {brain.bag_thread_action_count}act){f' item={ci}' if ci>0 else ''}")
            ps = brain.get_preparation_status()
            if ps['active']:
                sm_nav = " (StartMenu nav)" if ps.get('start_menu_nav') else ""
                print(f"  🎯 PREP: {ps['phase']}→{ps['target']} ({ps['frames']}f){sm_nav} | {ps['reason']}")
            elif brain.prep_total_count > 0: print(f"  🎯 Prep idle ({brain.prep_total_count}att {brain.prep_success_count}suc)")

            if currently_in_battle and brain.has_battle_data():
                bd = brain.battle_data; bt = "TR" if (bd.get('battle_type',0)&8)!=0 else "WD"
                cn = {0:'FIGHT',1:'BAG',2:'PKMN',3:'RUN'}.get(bd['battle_cursor'],'?')
                cr = brain.battle_cursor_action_count / max(1, brain.battle_action_count)
                print(f"\n  ⚔️ #{brain.current_battle_id} {bt} t{brain.turn_count} cursor={cn}")
                if bd['player_species']>0: print(f"     👤 sp{bd['player_species']} {bd['player_hp']}/{bd['player_max_hp']}")
                if bd['enemy_species']>0: print(f"     👾 sp{bd['enemy_species']} {bd['enemy_hp']}/{bd.get('enemy_max_hp','?')}")
                if brain.should_run(): print(f"     🏃 RUN nodmg={brain.battle_no_damage_turns}")
                print(f"     Cur:{brain.battle_cursor_action_count}({cr:.0%}) Mk:{brain.battle_markov_action_count}")
                bp_auth = brain.battle_pipeline.get_total_authority()
                if bp_auth > 0: print(f"     🔗 Pipeline: {bp_auth:.0%}")
            elif not currently_in_battle:
                if brain.is_nav_active():
                    xms = brain.get_cross_map_status()
                    if xms['active']:
                        ch = '→'.join(str(m) for m in xms['chain'])
                        print(f"\n  🧭🌍 {'PAUSED: '+xms['paused_reason'] if brain.is_nav_paused() else ch}")
                    elif brain.nav_target:
                        print(f"\n  🧭 →({brain.nav_target[0]},{brain.nav_target[1]}) "
                              f"{brain.nav_path_index}/{len(brain.nav_path)} {brain.nav_steps_taken}s")
                else:
                    ns = brain.get_nav_targets_status()
                    tgt_str = f" tgt:{ns['remaining']}/{ns['total']}" if ns['loaded'] else ""
                    print(f"\n  🧭 Nav idle (Markov primary){tgt_str}")

            smr = brain.start_menu_markov_actions / max(1, brain.start_menu_total_actions)
            print(f"\n  🧠 OW:{brain.markov_action_count}Mk({mr:.0%}) {brain.curiosity_action_count}cur | "
                  f"Bat:{brain.battle_action_count} Bag:{brain.bag_thread_total_actions} "
                  f"SM:{brain.start_menu_total_actions}({smr:.0%}Mk) | {density['tier']}")
            if any(v>0 for v in battle_outcomes.values()):
                print(f"  🏆 W:{battle_outcomes['win']} L:{battle_outcomes['loss']} R:{battle_outcomes['run']} C:{battle_outcomes['catch']}")

            tc_st = brain.get_type_chart_status()
            if tc_st['clustering_runs'] > 0 or tc_st['track_b_loaded']:
                print(f"\n  🧬 Types: {tc_st['move_clusters']}mc {tc_st['species_clusters']}sc "
                      f"{tc_st['effectiveness_entries']}eff | runs:{tc_st['clustering_runs']} "
                      f"next:{brain.CLUSTERING_BATTLE_INTERVAL - tc_st['battles_since_clustering']}bat"
                      f"{' +TrackB' if tc_st['track_b_loaded'] else ''}")

            cn = brain.get_nearest_nav_order(raw_x, raw_y, current_map)
            if cn >= 0:
                if brain.event_timeline_loaded:
                    up = brain.get_upcoming_events(cn, 5); hc = brain.get_estimated_hp_cost_ahead(cn, 5)
                    pp = brain.get_preparation_point(cn); lh = brain.get_lowest_hp_ratio()
                    ub = [e for e in up if e.get('type')=='battle']
                    print(f"\n  📅 Nav#{cn} | {len(up)}ev {len(ub)}bat | cost:{hc:.0%} HP:{lh:.0%}")
                    if pp:
                        need = "⚠️PREP" if lh < pp.get('party_hp_threshold',1.0) else "✅"
                        print(f"     Prep: {pp.get('reason','?')} | {need}")
                ac, acf = brain.get_autonomous_hp_estimate(raw_x, raw_y, current_map)
                if acf > 0: lh = brain.get_lowest_hp_ratio(); print(f"  🔮 Auto: cost{ac:.0%} conf{acf:.0%} HP:{lh:.0%} {'⚠️HEAL' if lh < ac else '✅'}")

            cms = brain.map_battle_stats.get(current_map)
            if cms and cms['battles_fought'] > 0:
                print(f"\n  📊 Map{current_map}: {cms['battles_fought']}bat {cms['avg_hp_cost']:.0%}cost Lv{cms['avg_enemy_level']:.0f} rate{cms['encounter_rate']:.4f}")

            cst = brain.get_chain_stats()
            if cst: print(f"\n  🧬 Chains: {' | '.join(f'{c}:{s['actions']}a+{s['entities']}e' for c, s in cst.items())}")
            act_counts = {}
            for p in brain.perceptrons: act_counts[p.active_activation] = act_counts.get(p.active_activation, 0) + 1
            if len(act_counts) > 1: print(f"  🧬 Act: {' '.join(f'{k}:{v}' for k, v in sorted(act_counts.items(), key=lambda x: x[1], reverse=True))}")

            known_items = [(iid,ik) for iid,ik in brain.item_knowledge.items() if ik.get('category','unknown')!='unknown']
            if known_items: print(f"\n  🎒 {len(known_items)} items categorized")

            if brain.party_data.get('count', 0) > 0:
                print(f"\n  👥 Party({brain.party_data['count']}):")
                for i, s in enumerate(brain.party_data.get('slots', [])):
                    hp, mhp = s.get('hp',0), s.get('max_hp',0)
                    r = f"{hp/mhp:.0%}" if mhp>0 else "?"; st = f" ⚠️{s['status']}" if s.get('status',0)!=0 else ""
                    print(f"     [{i}] Lv{s.get('level',0)} {hp}/{mhp}({r}){st}")

            vc = len(memory['visited_tiles']); ts = brain.get_tile_interaction_stats(current_map)
            print(f"\n  📊 V:{vc} Cov:{coverage:.0%} Probe:{ts['probed']} Exh:{ts['exhausted']}")
            utils = sorted([(a.action, a.utility) for a in brain.actions()], key=lambda x: x[1], reverse=True)
            print(f"  ⚡ {' '.join(f'{k}:{v:.2f}' for k,v in utils)}")
            print(f"  🧩 {len(brain.perceptrons)}p ({len(brain.actions())}a {len(brain.entities())}e)")
            if brain.state_stagnation_count > 10: print(f"  ⚠️ Stag:{brain.state_stagnation_count}/{brain.STATE_STAGNATION_THRESHOLD}")
            if brain.detected_pattern: print(f"  🔄 {'-'.join(str(a) for a in brain.detected_pattern)} x{brain.pattern_repeat_count}")

        # === 500-STEP MILESTONES ===
        if brain.timestep % 500 == 0 and brain.timestep > 0:
            tv = sum(len(m['visited_tiles']) for m in brain.exploration_memory.values())
            tt = sum(len(m.get('transitions',[])) for m in brain.exploration_memory.values())
            ta = brain.markov_action_count + brain.curiosity_action_count
            mr = brain.markov_action_count / max(1, ta)
            bmr = brain.battle_markov_action_count / max(1, brain.battle_action_count)
            bgmr = brain.bag_thread_markov_actions / max(1, brain.bag_thread_total_actions)
            smr = brain.start_menu_markov_actions / max(1, brain.start_menu_total_actions)
            mg = brain.build_map_graph(); mbs_s = brain.get_map_battle_stats_summary()

            print(f"\n{'#'*70}")
            print(f"# MILESTONE {brain.timestep}")
            if bootstrapped_from_taught: print(f"# Bootstrapped from taught model ({taught_timestep} human steps)")
            print(f"# Taught models: {brain.taught_model_count}")
            print(f"# Maps:{len(brain.exploration_memory)} Tiles:{tv} Trans:{tt}")
            gs_n = {0:"OW",1:"MENU",14:"BAG"}.get(brain.game_state_raw, "?")
            tf_n = " TXT" if brain.text_flag == 1 else ""
            print(f"# gs={gs_n}{tf_n} party={'ON' if brain.party_menu_active else 'off'} "
                  f"bag={'ON' if brain.bag_thread_active else 'off'} "
                  f"start_menu={'ON' if brain.start_menu_active else 'off'} "
                  f"prep={'ON('+brain.prep_phase+')' if brain.prep_active else 'off'}")
            ds = brain.get_dialogue_status()
            print(f"# dialogue={'ACTIVE('+('choice' if ds.get('is_choice') else 'skip')+')' if ds['active'] else 'off'} "
                  f"skip:{ds['total_skip_actions']} choice:{ds['total_choice_actions']} frames:{ds['total_frames']}")
            print(f"#\n# DECISIONS:")
            print(f"#   OW:{brain.markov_action_count}Mk({mr:.1%}) {brain.curiosity_action_count}cur")
            print(f"#   Bat:{brain.battle_action_count} Mk:{brain.battle_markov_action_count}({bmr:.1%})")
            print(f"#   Bag:{brain.bag_thread_total_actions} Mk:{brain.bag_thread_markov_actions}({bgmr:.1%})")
            print(f"#   SM:{brain.start_menu_total_actions} Mk:{brain.start_menu_markov_actions}({smr:.1%})")
            print(f"#   Dialogue: {ds['total_skip_actions']}skip {ds['total_choice_actions']}choice")
            print(f"#   Prep:{brain.prep_total_count}att {brain.prep_success_count}suc")
            print(f"#\n# BATTLES: {brain.current_battle_id}")
            print(f"#   W:{battle_outcomes['win']} L:{battle_outcomes['loss']} R:{battle_outcomes['run']} C:{battle_outcomes['catch']}")
            print(f"#\n# KNOWLEDGE:")
            print(f"#   Roster:{len(brain.roster)} Moves:{len(brain.move_knowledge)} Items:{len(brain.item_knowledge)} Enemy:{len(brain.enemy_move_knowledge)}")
            print(f"#   MapStats: {mbs_s['maps_with_data']}maps {mbs_s['total_battles']}bat")

            tc_st = brain.get_type_chart_status()
            print(f"#\n# TYPE CHART:")
            print(f"#   Track A: {tc_st['move_clusters']}mc {tc_st['species_clusters']}sc {tc_st['effectiveness_entries']}eff | runs:{tc_st['clustering_runs']}")
            print(f"#   Track B: {'LOADED' if tc_st['track_b_loaded'] else 'not available'}")

            print(f"#\n# PIPELINES:")
            for pid, pipeline in brain.pipelines.items():
                p_status = pipeline.get_status(brain.perceptrons)
                total_p = sum(l['perceptrons'] for l in p_status['layers'])
                total_r = sum(l['residual_size'] for l in p_status['layers'])
                print(f"#   {pid}: {total_p}p {total_r}r auth={p_status['total_authority']:.0%}")

            print(f"#\n# REVENGE MODULE:")
            rs = brain.get_revenge_status()
            if rs['targets'] > 0:
                print(f"#   Targets: {rs['targets']} ({rs['by_status']})")
                for tid, target in brain.revenge_targets.items():
                    print(f"#   {tid}: {target['enemy_type']} Lv{target['enemy_avg_level']:.0f} "
                          f"→Lv{target['target_avg_level']:.0f} losses={target['losses_here']} status={target['status']}")
            else: print(f"#   No revenge targets")

            br_info = brain.get_bounding_rect_info()
            if br_info['debt'] > 0.1: print(f"#\n# BOUNDING RECT: debt={br_info['debt']:.1f} area={br_info.get('area','?')}")

            cst = brain.get_chain_stats()
            print(f"#\n# CHAINS:")
            for c, s in cst.items():
                cap = brain.ENTITY_CAPACITY.get(c, '?'); sc = brain.entity_spawn_counts.get(c, 0); mc = brain.entity_merge_counts.get(c, 0)
                print(f"#   {c}: {s['actions']}a {s['entities']}e (cap:{cap} spawn:{sc} merge:{mc})")

            act_counts = {}; act_changes = 0
            for p in brain.perceptrons: act_counts[p.active_activation] = act_counts.get(p.active_activation, 0) + 1; act_changes += p.activation_change_count
            print(f"# ACTIVATIONS: {act_changes} total changes")
            for k, v in sorted(act_counts.items(), key=lambda x: x[1], reverse=True): print(f"#   {k}: {v} perceptrons")

            print(f"#\n# MEMORY:")
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            print(f"#   RSS current: {current_mem/(1024*1024):.1f}MB  peak: {peak_mem/(1024*1024):.1f}MB")
            obs_stats = brain.get_activation_observation_stats()
            print(f"#   Activation obs: {obs_stats['_total']['observations']} (~{obs_stats['_total']['estimated_mb']:.2f}MB)")
            sw_stats = save_worker.get_stats()
            print(f"#   SaveWorker: {sw_stats['saves_completed']}saves {sw_stats['saves_dropped']}dropped {sw_stats['total_save_time']:.1f}s")
            er_stats = event_recorder.get_stats()
            print(f"#   EventRecorder: {er_stats['total_events']}ev ({er_stats['battles']}bat {er_stats['maps']}map)")
            print(f"#")
            if brain.event_timeline_loaded: tl = brain.get_timeline_status(); print(f"# Timeline: {tl['events']}ev {tl['segments']}seg {tl['prep_points']}prep")
            ac, acf = brain.get_autonomous_hp_estimate(raw_x, raw_y, current_map)
            if acf > 0: print(f"# Auto: cost{ac:.0%} conf{acf:.0%}")
            print(f"# Nav:{'active' if brain.is_nav_active() else 'idle (Markov primary)'} Graph:{len(mg)}maps")
            ns = brain.get_nav_targets_status()
            if ns['loaded']: print(f"# Targets:{ns['remaining']}/{ns['total']}")
            print(f"# Blend: t{brain.blend_tier} #{brain.blend_count}")
            print(f"{'#'*70}")

            save_worker.submit_all_knowledge(brain, filepath=BASE_PATH / "model_checkpoint.json",
                                              timestep=brain.timestep, cache_manager=cache_manager)
            print(f"# Save queued (bg)"); gc.collect()

        # === WAIT + LEARN ===
        for _ in range(10):
            time.sleep(0.005)
            if active_cache.get_version() > last_processed_version: break

        (next_ctx, next_pal, next_til, dead, next_raw_pos,
         next_bd, next_pd, next_gs, next_md, next_bgd, next_tf) = active_cache.get_state()
        last_processed_version = active_cache.get_version()

        next_derived = compute_derived_features(next_ctx, context_state)
        next_ls = build_learning_state_overworld(next_derived, next_pal, next_til, next_ctx[3])

        if brain.is_dialogue_skip_state():
            saved_stagnation = brain.state_stagnation_count
            brain.learn(learning_state, next_ls, context_state, next_ctx, dead=dead,
                        raw_position=raw_position, next_raw_position=next_raw_pos)
            brain.state_stagnation_count = saved_stagnation
        else:
            brain.learn(learning_state, next_ls, context_state, next_ctx, dead=dead,
                        raw_position=raw_position, next_raw_position=next_raw_pos)

        prev_context_state = context_state.copy()
        prev_raw_position = raw_position
        brain.timestep += 1

except KeyboardInterrupt:
    print("\n\n🛑 Stopping...")
    io_thread.stop(); io_thread.join(timeout=2)
    event_recorder.stop(); event_recorder.join(timeout=3)
    save_worker.stop(); save_worker.join(timeout=5)

    print("  💾 Final synchronous save...")
    cache_manager.save_exploration_memory()
    brain.save_model_checkpoint(BASE_PATH / "model_checkpoint.json")
    brain.save_roster(); brain.save_move_knowledge()
    brain.save_item_knowledge(); brain.save_type_clusters()
    brain.save_residual_file()

    cst = brain.get_chain_stats()
    print(f"  Chains: {' | '.join(f'{c}:{s['actions']}a+{s['entities']}e' for c, s in cst.items())}")
    print(f"  Pipelines: {brain.get_pipeline_summary()}")
    print(f"  Activation changes: {sum(p.activation_change_count for p in brain.perceptrons)}")
    if bootstrapped_from_taught: print(f"  Bootstrapped from taught model ({taught_timestep} human steps)")
    print(f"  Taught models: {brain.taught_model_count}")
    print(f"  Bag:{brain.bag_thread_total_actions}act SM:{brain.start_menu_total_actions}act "
          f"Prep:{brain.prep_total_count}att/{brain.prep_success_count}suc")
    ds = brain.get_dialogue_status()
    print(f"  Dialogue: {ds['total_skip_actions']}skip {ds['total_choice_actions']}choice {ds['total_frames']}f")
    rs = brain.get_revenge_status()
    if rs['targets'] > 0: print(f"  Revenge: {rs['targets']} targets ({rs['by_status']})")
    for pid, pipeline in brain.pipelines.items():
        total_p = sum(pool.get_perceptron_count(brain.perceptrons) for pool in pipeline.pools)
        total_r = sum(len(pool.residual) for pool in pipeline.pools)
        if total_p > 0 or total_r > 0: print(f"  Pipeline {pid}: {total_p}p {total_r}r auth={pipeline.get_total_authority():.0%}")
    print(f"  MapStats: {brain.get_map_battle_stats_summary()['maps_with_data']}maps")
    print(f"  W:{battle_outcomes['win']} L:{battle_outcomes['loss']} R:{battle_outcomes['run']} C:{battle_outcomes['catch']}")
    tc_st = brain.get_type_chart_status()
    print(f"  TypeChart: {tc_st['clustering_runs']}runs {tc_st['move_clusters']}mc{' +TrackB' if tc_st['track_b_loaded'] else ''}")
    sw_stats = save_worker.get_stats()
    print(f"  SaveWorker: {sw_stats['saves_completed']}saves {sw_stats['saves_dropped']}dropped {sw_stats['total_save_time']:.1f}s")
    er_stats = event_recorder.get_stats()
    print(f"  EventRecorder: {er_stats['total_events']}ev ({er_stats['battles']}bat {er_stats['maps']}map)")
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    print(f"  Memory: current={current_mem/(1024*1024):.1f}MB peak={peak_mem/(1024*1024):.1f}MB")
    tracemalloc.stop(); print("✅ Done.")