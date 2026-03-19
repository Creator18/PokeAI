# ============================================================================
# brain_core.py — Brain Class: __init__ + Accessor Methods
# ============================================================================
# The Brain is the central coordinator. All state lives here.
# Subsystem methods (navigation, markov, learning, etc.) will be attached
# via composition in future refactoring. For now this file contains:
#   - __init__ (all state variables)
#   - Chain-specific perceptron access
#   - Pool/pipeline access
#   - Revenge module access + mutation methods
# ============================================================================

import numpy as np
from collections import deque

from constants import (
    BASE_PATH,
    DEFAULT_BATTLE_DATA, DEFAULT_PARTY_DATA,
    DEFAULT_MENU_DATA, DEFAULT_BAG_DATA,
)
from perceptron import Perceptron, ControlSwapPerceptron
from pool import Pool, Pipeline


class Brain:
    def __init__(self):
        # === MASTER PERCEPTRON LIST ===
        self.perceptrons = []

        # =================================================================
        # PIPELINE DEFINITIONS
        # =================================================================

        self.battle_pipeline = Pipeline(
            pipeline_id="battle",
            name="Battle Pipeline",
            pool_definitions=[
                {'name': 'identification',    'output_width': 8, 'max_perceptrons': 15},
                {'name': 'threat_assessment',  'output_width': 8, 'max_perceptrons': 20},
                {'name': 'stay_or_bail',       'output_width': 8, 'max_perceptrons': 15},
                {'name': 'action_selection',   'output_width': 8, 'max_perceptrons': 20},
                {'name': 'execution',          'output_width': 8, 'max_perceptrons': 10},
                {'name': 'outcome_observation','output_width': 8, 'max_perceptrons': 10},
            ],
            credit_decay=0.7,
        )

        self.overworld_pipeline = Pipeline(
            pipeline_id="overworld",
            name="Overworld Pipeline",
            pool_definitions=[
                {'name': 'spatial_awareness',    'output_width': 8, 'max_perceptrons': 15},
                {'name': 'area_classification',  'output_width': 8, 'max_perceptrons': 10},
                {'name': 'frontier_detection',   'output_width': 8, 'max_perceptrons': 15},
                {'name': 'objective_management', 'output_width': 8, 'max_perceptrons': 15},
                {'name': 'pathfinding',          'output_width': 8, 'max_perceptrons': 10},
                {'name': 'execution',            'output_width': 8, 'max_perceptrons': 10},
                {'name': 'outcome_observation',  'output_width': 8, 'max_perceptrons': 10},
            ],
            credit_decay=0.7,
        )

        self.bag_pipeline = Pipeline(
            pipeline_id="bag",
            name="Bag Pipeline",
            pool_definitions=[
                {'name': 'inventory_awareness', 'output_width': 8, 'max_perceptrons': 10},
                {'name': 'item_selection',      'output_width': 8, 'max_perceptrons': 10},
                {'name': 'execution',           'output_width': 8, 'max_perceptrons': 8},
            ],
            credit_decay=0.7,
        )

        self.party_pipeline = Pipeline(
            pipeline_id="party",
            name="Party Pipeline",
            pool_definitions=[
                {'name': 'assessment', 'output_width': 8, 'max_perceptrons': 10},
                {'name': 'execution',  'output_width': 8, 'max_perceptrons': 8},
            ],
            credit_decay=0.7,
        )

        self.pipelines = {
            'battle': self.battle_pipeline,
            'overworld': self.overworld_pipeline,
            'bag': self.bag_pipeline,
            'party': self.party_pipeline,
        }

        # =================================================================
        # RESIDUAL PERCEPTRONS FILE
        # =================================================================
        self.RESIDUAL_FILE = BASE_PATH / "residual_perceptrons.json"

        # =================================================================
        # REVENGE MODULE
        # =================================================================
        self.revenge_targets = {}
        self.REVENGE_BASE_MARGIN = 2
        self.REVENGE_MARGIN_PER_LOSS = 2
        self.REVENGE_MAX_MARGIN = 15
        self.REVENGE_MAX_TARGETS = 10

        # =================================================================
        # PER-CHAIN LEARNING STATE HISTORY
        # =================================================================
        self.prev_learning_states = deque(maxlen=50)
        self.prev_battle_learning_states = deque(maxlen=50)
        self.prev_party_learning_states = deque(maxlen=20)
        self.prev_bag_learning_states = deque(maxlen=20)

        self.prev_context_states = deque(maxlen=10)
        self.last_positions = deque(maxlen=30)
        self.action_history = deque(maxlen=100)

        self.control_mode = "move"
        self.timestep = 0
        self.last_action = None
        self.last_direction = 0

        self.MOVE_UTILITY_FLOOR = 0.05
        self.INTERACT_UTILITY_FLOOR = 0.15

        # === PER-CHAIN ENTITY CAPACITY ===
        self.ENTITY_CAPACITY = {
            'overworld': 20, 'battle': 10, 'party': 5, 'bag': 5, 'shared': 10,
        }
        self.ENTITY_CAPACITY_GROWTH = 1.5

        self.entity_spawn_counts = {'overworld': 0, 'battle': 0, 'party': 0, 'bag': 0, 'shared': 0}
        self.entity_merge_counts = {'overworld': 0, 'battle': 0, 'party': 0, 'bag': 0, 'shared': 0}
        self.ENTITY_CLUSTER_SIMILARITY = 0.85
        self.ENTITY_MIN_ACTIVATIONS = 10

        self.innate_entities_spawned_overworld = False
        self.innate_entities_spawned_battle = False

        # Legacy compatibility
        self.entity_capacity = self.ENTITY_CAPACITY['overworld']
        self.entity_spawn_count = 0
        self.entity_merge_count = 0
        self.innate_entities_spawned = False

        # === PERSISTENT EXPLORATION MEMORY ===
        self.EXPLORATION_MEMORY_FILE = BASE_PATH / "exploration_memory.json"
        self.exploration_memory = {}
        self.current_map_id = None
        self.SAVE_INTERVAL = 100

        self.DIRECTION_NAMES = {0: "DOWN", 1: "UP", 2: "LEFT", 3: "RIGHT"}
        self.DIRECTION_TO_INT = {"DOWN": 0, "UP": 1, "LEFT": 2, "RIGHT": 3}
        self.INT_TO_ACTION = {0: "DOWN", 1: "UP", 2: "LEFT", 3: "RIGHT"}

        self.DIRECTION_DELTAS_INT = {0: (0, 1), 1: (0, -1), 2: (-1, 0), 3: (1, 0)}
        self.ACTION_DELTAS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
        self.DELTA_TO_DIRECTION = {(0, 1): 0, (0, -1): 1, (-1, 0): 2, (1, 0): 3}

        # NOTE: load_exploration_memory() called by main.py after construction

        # =================================================================
        # MARKOV TRANSITION SYSTEM (OVERWORLD)
        # =================================================================
        self.taught_transitions = []
        self.taught_batches = []
        self.taught_metadata = {}
        self.markov_enabled = True
        self.markov_action_count = 0
        self.curiosity_action_count = 0
        self.last_markov_score = 0.0
        self.last_markov_action = None

        # =================================================================
        # MULTI-MODEL TAUGHT DATA
        # =================================================================
        self.all_taught_transitions = []
        self.all_taught_batches = []
        self.all_battle_transitions = []
        self.all_battle_sequences = []
        self.all_bag_transitions = []
        self.all_start_menu_transitions = []
        self.taught_model_count = 0
        self.best_taught_checkpoint_path = None

        # === BATTLE THREAD STATE ===
        self.battle_transitions = []
        self.battle_sequences = []
        self.battle_metadata = {}
        self.battle_loaded = False
        self.battle_action_count = 0
        self.battle_markov_action_count = 0
        self.current_battle_id = 0
        self.battle_frame_count = 0
        self.last_battle_markov_score = 0.0
        self.last_battle_markov_action = None
        self.in_battle_last_frame = False
        self.battle_action_history = deque(maxlen=100)

        # === BATTLE DATA ===
        self.battle_data = DEFAULT_BATTLE_DATA.copy()
        self.prev_battle_data = DEFAULT_BATTLE_DATA.copy()

        # === PARTY DATA ===
        self.party_data = DEFAULT_PARTY_DATA.copy()
        self.prev_party_data = DEFAULT_PARTY_DATA.copy()

        # === MENU DATA ===
        self.menu_data = DEFAULT_MENU_DATA.copy()
        self.prev_menu_data = DEFAULT_MENU_DATA.copy()

        # === BAG DATA ===
        self.bag_data = DEFAULT_BAG_DATA.copy()
        self.prev_bag_data = DEFAULT_BAG_DATA.copy()

        # === RAW GAME STATE ===
        self.game_state_raw = 0

        # === BAG THREAD STATE ===
        self.bag_thread_active = False
        self.bag_thread_context = "none"
        self.bag_thread_entered_at = 0
        self.bag_thread_action_count = 0
        self.bag_thread_last_action = None
        self.BAG_THREAD_TIMEOUT = 180
        self.bag_thread_total_actions = 0
        self.bag_thread_markov_actions = 0

        self.bag_transitions = []
        self.bag_metadata = {}
        self.bag_loaded = False
        self.bag_action_history = deque(maxlen=50)
        self.last_bag_markov_score = 0.0
        self.last_bag_markov_action = None

        # === ITEM KNOWLEDGE ===
        self.item_knowledge = {}
        self.item_knowledge_dirty = False
        self.pending_item_observation = None
        self.ITEM_OBSERVE_WAIT_FRAMES = 15

        # === EVENT TIMELINE ===
        self.event_timeline = []
        self.event_segments = []
        self.event_preparation_points = []
        self.event_timeline_metadata = {}
        self.event_timeline_loaded = False

        # === MAP BATTLE STATISTICS ===
        self.map_battle_stats = {}
        self.map_battle_stats_dirty = False
        self.map_step_counters = {}

        # === PREPARATION STATE MACHINE ===
        self.prep_active = False
        self.prep_phase = "idle"
        self.prep_reason = ""
        self.prep_started_at = 0
        self.prep_target = "bag"
        self.prep_target_mc = 2
        self.PREP_TIMEOUT = 60
        self.PREP_COOLDOWN = 200
        self.prep_last_attempt_at = 0
        self.prep_phase_entered_at = 0
        self.PREP_PHASE_TIMEOUT = 15
        self.prep_total_count = 0
        self.prep_success_count = 0

        # === PARTY MENU THREAD ===
        self.party_menu_active = False
        self.party_menu_context = "none"
        self.party_menu_entered_at = 0
        self.party_menu_target_slot = -1
        self.party_menu_action_count = 0
        self.PARTY_MENU_TIMEOUT = 120
        self.party_menu_battle_cursor_on_entry = -1
        self.party_menu_awaiting_entry = False
        self.party_menu_last_action = None

        # === BATTLE AWARENESS ===
        self.battle_player_species = -1
        self.battle_enemy_species = -1
        self.battle_start_hp = -1
        self.battle_enemy_start_hp = -1
        self.battle_menu_state = "unknown"
        self.battle_cursor_action_count = 0

        self.turn_start_player_hp = -1
        self.turn_start_enemy_hp = -1
        self.turn_start_pp = [-1, -1, -1, -1]
        self.turn_start_enemy_pp = [-1, -1, -1, -1]
        self.turn_start_player_stats = [-1] * 7
        self.turn_start_enemy_stats = [-1] * 7
        self.turn_start_player_status = 0
        self.turn_start_enemy_status = 0
        self.turn_count = 0
        self.last_move_used = -1
        self.last_move_slot = -1

        # === RUNNING DECISION ===
        self.battle_no_damage_turns = 0
        self.battle_hp_trend = deque(maxlen=10)
        self.battle_low_hp_exits = 0
        self.BATTLE_RUN_NO_DAMAGE_THRESHOLD = 4
        self.BATTLE_RUN_HP_RATIO_THRESHOLD = 0.25
        self.BATTLE_RUN_ENABLED = True

        # === FORCED SWITCH ===
        self.forced_switch_pending = False
        self.forced_switch_target_slot = -1

        # === ROSTER ===
        self.roster = {}
        self.roster_dirty = False

        # === MOVE KNOWLEDGE ===
        self.move_knowledge = {}
        self.move_knowledge_dirty = False
        self.enemy_move_knowledge = {}

        # === TAUGHT MODEL REFERENCE ===
        self.taught_reference = {'utilities': {}, 'weights': {}, 'loaded': False}

        # === BLEND SYSTEM ===
        self.blend_tier = 0
        self.last_blend_timestep = 0
        self.BLEND_COOLDOWN = 50
        self.blend_count = 0
        self.BLEND_RATIOS = {1: (0.80, 0.20), 2: (0.60, 0.40), 3: (0.40, 0.60)}
        self.BLEND_TIER_TRIGGERS = {
            1: {'pattern_repeats': 3, 'pos_stagnation': 8, 'consecutive': 12},
            2: {'pattern_repeats': 6, 'pos_stagnation': 15, 'consecutive': 15},
            3: {'pattern_repeats': 10, 'state_stagnation_mult': 2.0}
        }

        # === ACTION EXECUTION CONFIRMATION ===
        self.pending_action = None
        self.pending_action_frames = 0
        self.ACTION_CONFIRM_FRAMES = 3
        self.last_confirmed_action = None

        # === TILE INTERACTION PROBING ===
        self.INTERACTION_VERIFY_FRAMES = 8
        self.MIN_SUCCESS_RATE_THRESHOLD = 0.1
        self.pending_interaction_verify = None
        self.interaction_verify_countdown = 0

        # === MENU ESCAPE B-BOOST ===
        self.menu_trap_frames = 0
        self.menu_trap_b_boost = 1.0
        self.menu_trap_position = None
        self.B_BOOST_INCREMENT = 0.15
        self.B_BOOST_MAX = 3.0
        self.MENU_TRAP_THRESHOLD = 5
        self.original_b_utility = None

        # === ADAPTIVE MODE SWAPPING ===
        self.DEFAULT_MOVE_TO_INTERACT_THRESHOLD = 15
        self.DEFAULT_INTERACT_TO_MOVE_THRESHOLD = 25
        self.move_to_interact_threshold = self.DEFAULT_MOVE_TO_INTERACT_THRESHOLD
        self.interact_to_move_threshold = self.DEFAULT_INTERACT_TO_MOVE_THRESHOLD
        self.THRESHOLD_INCREMENT = 15
        self.MAX_THRESHOLD = 150
        self.frames_in_current_mode = 0
        self.swap_chain_count = 0
        self.position_at_mode_swap = None
        self.last_map_id = None
        self.last_battle_state = None

        # === UNPRODUCTIVE MODE SWAP ===
        self.UNPRODUCTIVE_SWAP_THRESHOLD = 3
        self.unproductive_swap_count = 0
        self.utilities_before_swapping = {}
        self.swap_chain_active = False

        # === STATE STAGNATION ===
        self.STATE_STAGNATION_THRESHOLD = 20
        self.state_stagnation_count = 0
        self.last_context_state_hash = None
        self.stagnation_initiator_action = None
        self.STAGNATION_INITIATOR_PENALTY = 0.7

        # === BOTH MODE ===
        self.BOTH_MODE_STAGNATION_THRESHOLD = 35
        self.BOTH_MODE_SWAP_THRESHOLD = 5

        # === PROGRESS TRACKING ===
        self.last_direction_for_progress = None
        self.direction_change_counts_as_progress = True

        # === NOVELTY WEIGHTS ===
        self.UNVISITED_TILE_BONUS = 1.5
        self.OBSTRUCTION_PENALTY = 0.25

        # === TRANSITION SYSTEM ===
        self.TRANSITION_ATTRACTION_WEIGHT = 0.6
        self.TEMP_DEBT_ACCUMULATION = 0.5
        self.TEMP_DEBT_DECAY = 0.02
        self.TEMP_DEBT_MAX = 15.0

        # === DEBT ===
        self.MAX_MAP_DEBT = 10.0
        self.MAX_LOCATION_DEBT = 5.0
        self.DEBT_DECAY_RATE = 0.005

        # === TRANSITION BANS ===
        self.transition_bans = {}
        self.BAN_VICINITY_RADIUS = 3
        self.BAN_COVERAGE_LIFT_THRESHOLD = 0.6
        self.BAN_TIMEOUT_STEPS = 300

        # Multi-scale memory
        self.visited_maps = {}
        self.map_novelty_debt = {}
        self.location_memory = {}
        self.location_novelty = {}
        self.action_execution_count = {}

        self.swap_perceptron = ControlSwapPerceptron()
        self.error_history = deque(maxlen=1000)
        self.numeric_error_history = deque(maxlen=1000)
        self.visual_error_history = deque(maxlen=1000)
        self._entity_norms_cache = {}
        self._cache_valid = False

        # === PER-CHAIN ERROR HISTORY ===
        self.battle_error_history = deque(maxlen=500)
        self.party_error_history = deque(maxlen=200)
        self.bag_error_history = deque(maxlen=200)

        # === REPETITION ===
        self.consecutive_action_count = 0
        self.current_repeated_action = None
        self.LEARNING_SLOWDOWN_START = 3
        self.LEARNING_SLOWDOWN_MAX = 10
        self.PENALTY_THRESHOLD = 12
        self.HARD_RESET_THRESHOLD = 18

        # === PATTERN DETECTION ===
        self.PATTERN_CHECK_WINDOW = 50
        self.PATTERN_MIN_REPEATS = 3
        self.PATTERN_MAX_LENGTH = 10
        self.detected_pattern = None
        self.pattern_repeat_count = 0

        # === PROBE CACHE ===
        self._cached_probe_action = None
        self._cached_probe_dir = None
        self._probe_cache_position = None

        # === NAVIGATION ===
        self.nav_active = False
        self.nav_path = []
        self.nav_path_index = 0
        self.nav_target = None
        self.nav_target_list = []
        self.nav_target_index = 0
        self.nav_struck_targets = set()
        self.nav_steps_taken = 0
        self.nav_stagnation_count = 0
        self.nav_last_position = None

        self.nav_struck_tile_counts = {}

        self.NAV_STAGNATION_LIMIT = 8
        self.NAV_MAX_STEPS = 100
        self.NAV_LEARNING_DAMPENING = 0.3

        # === CROSS-MAP NAV ===
        self.nav_map_chain = []
        self.nav_chain_index = 0
        self.nav_cross_map_target = None
        self.nav_cross_map_target_data = None
        self.nav_paused = False
        self.nav_paused_reason = ""
        self.nav_paused_target_map = None
        self.NAV_PAUSE_CHECK_INTERVAL = 50
        self.nav_pause_check_countdown = 0
        self.NAV_CROSS_MAP_REFRESH_INTERVAL = 40
        self.nav_cross_map_refresh_countdown = 0
        self._map_graph = {}
        self._map_graph_dirty = True

        # === TAUGHT NAV TARGETS ===
        self.taught_nav_targets = {}
        self.taught_nav_global_order = []
        self.nav_visited_targets = set()
        self.taught_nav_loaded = False

        # === BOUNDING RECTANGLE DEBT ===
        self.recent_movement_positions = deque(maxlen=200)
        self.bounding_rect_debt = 0.0
        self.BOUNDING_RECT_DEBT_INCREMENT = 0.3
        self.BOUNDING_RECT_DEBT_MAX = 10.0
        self.BOUNDING_RECT_STAGNATION_THRESHOLD = 50

        # === EVENT RECORDER STATE ===
        self.event_queue = None
        self.event_recorder_active = False

        self.recorded_battle_events = 0
        self.recorded_bag_events = 0
        self.recorded_map_events = 0
        self.recorded_levelup_events = 0

        self.EVENT_RECORDER_FLUSH_INTERVAL = 30

        # === START MENU THREAD STATE ===
        self.start_menu_active = False
        self.start_menu_context = "none"
        self.start_menu_entered_at = 0
        self.start_menu_action_count = 0
        self.start_menu_last_action = None
        self.start_menu_target_mc = -1
        self.START_MENU_TIMEOUT = 90
        self.start_menu_total_actions = 0
        self.start_menu_markov_actions = 0

        self.start_menu_transitions = []
        self.start_menu_metadata = {}
        self.start_menu_loaded = False
        self.start_menu_action_history = deque(maxlen=50)
        self.last_start_menu_markov_score = 0.0
        self.last_start_menu_markov_action = None

        self.START_MENU_OPTIONS = {
            'pokedex': 0, 'pokemon': 1, 'bag': 2, 'trainer_card': 3,
            'save': 4, 'option': 5, 'exit': 6
        }

        # === EMPIRICAL TYPE CHART DISCOVERY STATE ===
        self.move_type_clusters = {}
        self.species_type_clusters = {}
        self.cluster_effectiveness = {}
        self.move_to_cluster = {}
        self.species_to_cluster = {}

        self.CLUSTERING_BATTLE_INTERVAL = 50
        self.CLUSTERING_MIN_MOVES = 3
        self.CLUSTERING_MIN_SPECIES_PER_MOVE = 3
        self.CLUSTERING_SIMILARITY_THRESHOLD = 0.80
        self.battles_since_last_clustering = 0
        self.clustering_run_count = 0
        self.last_clustering_timestep = 0

        self.type_clusters_dirty = False

        self.type_data = None
        self.type_data_loaded = False

        # === TEXT DIALOGUE STATE ===
        self.text_flag = 0
        self.prev_text_flag = 0

        self.dialogue_active = False
        self.dialogue_is_choice = False
        self.dialogue_is_pure_text = False
        self.dialogue_is_battle_text = False

        self.DIALOGUE_CHOICE_MM_MAX = 3

        self.dialogue_skip_action_count = 0
        self.dialogue_choice_action_count = 0
        self.dialogue_frames_total = 0
        self.dialogue_entered_at = 0
        self.dialogue_last_action = None

    # =========================================================================
    # CHAIN-SPECIFIC PERCEPTRON ACCESS
    # =========================================================================

    def actions(self, chain=None):
        if chain is None:
            return [p for p in self.perceptrons if p.kind == "action"]
        return [p for p in self.perceptrons if p.kind == "action" and p.chain == chain]

    def entities(self, chain=None):
        if chain is None:
            return [p for p in self.perceptrons if p.kind == "entity"]
        return [p for p in self.perceptrons if p.kind == "entity" and p.chain == chain]

    def add(self, p):
        self.perceptrons.append(p)
        self._cache_valid = False

    def get_chain_entity_count(self, chain):
        return len(self.entities(chain=chain))

    def get_chain_entity_capacity(self, chain):
        return self.ENTITY_CAPACITY.get(chain, 10)

    def get_chain_stats(self):
        stats = {}
        for chain in ['overworld', 'battle', 'party', 'bag', 'shared']:
            n_act = len(self.actions(chain=chain))
            n_ent = len(self.entities(chain=chain))
            if n_act > 0 or n_ent > 0:
                stats[chain] = {'actions': n_act, 'entities': n_ent}
        return stats

    # =========================================================================
    # POOL-SPECIFIC PERCEPTRON ACCESS
    # =========================================================================

    def pool_perceptrons(self, pool_id):
        return [p for p in self.perceptrons if p.pool_id == pool_id]

    def get_pipeline(self, pipeline_id):
        return self.pipelines.get(pipeline_id)

    def get_pipeline_stats(self):
        stats = {}
        for pid, pipeline in self.pipelines.items():
            p_stats = pipeline.get_status(self.perceptrons)
            stats[pid] = p_stats
        return stats

    def get_pipeline_summary(self):
        parts = []
        for pid, pipeline in self.pipelines.items():
            total_p = sum(pool.get_perceptron_count(self.perceptrons) for pool in pipeline.pools)
            total_auth = pipeline.get_total_authority()
            if total_p > 0 or total_auth > 0:
                parts.append(f"{pid}:{total_p}p({total_auth:.0%})")
        return ' | '.join(parts) if parts else 'all empty'

    # =========================================================================
    # REVENGE MODULE ACCESS
    # =========================================================================

    def get_active_revenge_target(self):
        active = [
            (tid, t) for tid, t in self.revenge_targets.items()
            if t['status'] in ('grinding', 'ready')
        ]
        if not active:
            return None, None
        active.sort(key=lambda x: (
            0 if x[1]['status'] == 'ready' else 1,
            -x[1]['losses_here']
        ))
        return active[0]

    def get_revenge_status(self):
        if not self.revenge_targets:
            return {'active': False, 'targets': 0}
        by_status = {}
        for t in self.revenge_targets.values():
            s = t['status']
            by_status[s] = by_status.get(s, 0) + 1
        return {
            'active': any(t['status'] in ('grinding', 'ready') for t in self.revenge_targets.values()),
            'targets': len(self.revenge_targets),
            'by_status': by_status,
        }

    def record_revenge_loss(self, map_id, position, enemy_species, enemy_avg_level,
                            my_avg_level, is_trainer=False, is_gym=False):
        target_id = f"map{map_id}_pos{position[0]}_{position[1]}"
        enemy_type = 'gym' if is_gym else ('trainer' if is_trainer else 'wild')

        if target_id in self.revenge_targets:
            t = self.revenge_targets[target_id]
            t['losses_here'] += 1
            t['my_avg_level_at_loss'] = my_avg_level
            t['enemy_avg_level'] = enemy_avg_level
            t['enemy_species'] = enemy_species
            margin = min(self.REVENGE_MAX_MARGIN,
                        self.REVENGE_BASE_MARGIN + self.REVENGE_MARGIN_PER_LOSS * t['losses_here'])
            t['target_avg_level'] = enemy_avg_level + margin
            t['status'] = 'grinding'
            t['last_updated'] = self.timestep
        else:
            margin = self.REVENGE_BASE_MARGIN
            self.revenge_targets[target_id] = {
                'map_id': map_id,
                'position': position,
                'enemy_type': enemy_type,
                'enemy_species': enemy_species if isinstance(enemy_species, list) else [enemy_species],
                'enemy_avg_level': enemy_avg_level,
                'my_avg_level_at_loss': my_avg_level,
                'target_avg_level': enemy_avg_level + margin,
                'losses_here': 1,
                'attempts': 0,
                'status': 'grinding',
                'strategy_notes': {
                    'moves_that_failed': [],
                    'types_that_worked': [],
                },
                'created_at': self.timestep,
                'last_updated': self.timestep,
            }

        if len(self.revenge_targets) > self.REVENGE_MAX_TARGETS:
            cleared = [(tid, t) for tid, t in self.revenge_targets.items() if t['status'] == 'cleared']
            if cleared:
                oldest = min(cleared, key=lambda x: x[1]['last_updated'])
                del self.revenge_targets[oldest[0]]

        print(f"  ⚔️🔥 REVENGE TARGET: {target_id} ({enemy_type}) "
              f"losses={self.revenge_targets[target_id]['losses_here']} "
              f"target_lv={self.revenge_targets[target_id]['target_avg_level']:.0f}")

    def check_revenge_readiness(self):
        if not self.revenge_targets:
            return
        party_levels = [s.get('level', 0) for s in self.party_data.get('slots', [])
                       if s.get('hp', 0) > 0]
        if not party_levels:
            return
        team_avg = np.mean(party_levels)
        for tid, t in self.revenge_targets.items():
            if t['status'] == 'grinding' and team_avg >= t['target_avg_level']:
                t['status'] = 'ready'
                t['last_updated'] = self.timestep
                print(f"  ⚔️✅ REVENGE READY: {tid} (team avg {team_avg:.0f} >= target {t['target_avg_level']:.0f})")

    def record_revenge_victory(self, map_id, position):
        target_id = f"map{map_id}_pos{position[0]}_{position[1]}"
        if target_id in self.revenge_targets:
            t = self.revenge_targets[target_id]
            t['status'] = 'cleared'
            t['last_updated'] = self.timestep
            print(f"  ⚔️🏆 REVENGE CLEARED: {target_id} after {t['losses_here']} losses, "
                  f"{t['attempts']} attempts")