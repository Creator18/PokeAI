# ============================================================================
# constants.py — File Paths, Dimensions, Weights, Default Data
# ============================================================================
# Pure data — no logic, no imports beyond pathlib.
# Every other module imports from here.
# ============================================================================

from pathlib import Path

# ============================================================================
# FILE PATHS
# ============================================================================

BASE_PATH = Path("C:/Users/HP/Documents/cogai/")
ACTION_FILE = BASE_PATH / "action.json"
STATE_FILE = BASE_PATH / "game_state.json"

# === AI-OWNED FILE PATHS ===
EXPLORATION_MEMORY_FILE = BASE_PATH / "exploration_memory.json"
MODEL_CHECKPOINT_FILE = BASE_PATH / "model_checkpoint.json"
ROSTER_FILE = BASE_PATH / "roster.json"
MOVE_KNOWLEDGE_FILE = BASE_PATH / "move_knowledge.json"
ITEM_KNOWLEDGE_FILE = BASE_PATH / "item_knowledge.json"
TYPE_CLUSTERS_FILE = BASE_PATH / "type_clusters.json"
AI_EVENT_TIMELINE_FILE = BASE_PATH / "ai_event_timeline.json"
TYPE_DATA_FILE = BASE_PATH / "type_data.json"

# === MULTI-MODEL TAUGHT DATA FOLDER STRUCTURE ===
# taught_models/
#   model_1/
#     taught_model_checkpoint.json
#     taught_transitions.json
#     taught_battle_transitions.json
#     taught_bag_transitions.json
#     taught_start_menu_transitions.json
#     taught_exploration_memory.json
#     taught_nav_targets.json
#     event_timeline.json
#   model_2/ ...

TAUGHT_MODELS_DIR = BASE_PATH / "taught_models"

# File names within each model folder
TAUGHT_MODEL_CHECKPOINT_FILENAME = "taught_model_checkpoint.json"
TAUGHT_TRANSITIONS_FILENAME = "taught_transitions.json"
TAUGHT_BATTLE_TRANSITIONS_FILENAME = "taught_battle_transitions.json"
TAUGHT_BAG_TRANSITIONS_FILENAME = "taught_bag_transitions.json"
TAUGHT_START_MENU_TRANSITIONS_FILENAME = "taught_start_menu_transitions.json"
TAUGHT_EXPLORATION_FILENAME = "taught_exploration_memory.json"
TAUGHT_NAV_TARGETS_FILENAME = "taught_nav_targets.json"
TAUGHT_EVENT_TIMELINE_FILENAME = "event_timeline.json"


def get_taught_model_paths():
    """
    Discover all model_N folders and return sorted list of paths.
    Returns empty list if TAUGHT_MODELS_DIR doesn't exist.
    """
    if not TAUGHT_MODELS_DIR.exists():
        return []
    folders = sorted([
        d for d in TAUGHT_MODELS_DIR.iterdir()
        if d.is_dir() and d.name.startswith('model_')
    ], key=lambda d: int(d.name.split('_')[1]) if d.name.split('_')[1].isdigit() else 0)
    return folders


# ============================================================================
# MARKOV SIMILARITY WEIGHTS (OVERWORLD)
# ============================================================================

MARKOV_IMMEDIATE_WEIGHT = 0.5
MARKOV_SEQUENTIAL_WEIGHT = 0.3
MARKOV_PARTIAL_WEIGHT = 0.2
MARKOV_FAMILIARITY_THRESHOLD = 0.6

MARKOV_SEQ_FULL_WEIGHT = 1.0
MARKOV_SEQ_MEDIUM_WEIGHT = 0.6
MARKOV_SEQ_SHORT_WEIGHT = 0.3

MARKOV_POS_EXACT_BONUS = 0.35
MARKOV_POS_NEAR_BONUS = 0.25
MARKOV_POS_FAR_BONUS = 0.1
MARKOV_POS_MAX_DIST = 5

# ============================================================================
# BATTLE MARKOV WEIGHTS
# ============================================================================

BATTLE_MARKOV_ACTION_SEQ_WEIGHT = 0.70
BATTLE_MARKOV_PALETTE_WEIGHT = 0.20
BATTLE_MARKOV_MENU_STATE_WEIGHT = 0.10
BATTLE_MARKOV_THRESHOLD_LOW = 0.35
BATTLE_MARKOV_THRESHOLD_HIGH = 0.45

# ============================================================================
# BAG MARKOV WEIGHTS
# ============================================================================

BAG_MARKOV_MENU_STATE_WEIGHT = 0.40
BAG_MARKOV_ACTION_SEQ_WEIGHT = 0.35
BAG_MARKOV_PARTY_CONTEXT_WEIGHT = 0.25
BAG_MARKOV_THRESHOLD = 0.35

# ============================================================================
# START MENU MARKOV WEIGHTS
# ============================================================================

START_MENU_MARKOV_MENU_STATE_WEIGHT = 0.45
START_MENU_MARKOV_ACTION_SEQ_WEIGHT = 0.35
START_MENU_MARKOV_CONTEXT_WEIGHT = 0.20
START_MENU_MARKOV_THRESHOLD = 0.35

# ============================================================================
# STATE DIMENSIONS
# ============================================================================

EXPECTED_STATE_DIM = 6
PALETTE_DIM = 768
TILE_DIM = 600

# Per-chain learning state dimensions
OVERWORLD_STATE_DIM = 8 + TILE_DIM + PALETTE_DIM   # 1376
OVERWORLD_BATTLE_STATE_DIM = 8 + PALETTE_DIM        # 776
BATTLE_CHAIN_DIM = 41
PARTY_CHAIN_DIM = 50
BAG_CHAIN_DIM = 18

# ============================================================================
# DEFAULT BATTLE DATA
# ============================================================================

DEFAULT_BATTLE_DATA = {
    'battle_cursor': -1, 'move_cursor': -1, 'party_cursor': -1,
    'player_species': -1, 'enemy_species': -1,
    'player_hp': -1, 'player_max_hp': -1, 'enemy_hp': -1, 'enemy_max_hp': -1,
    'player_level': -1, 'enemy_level': -1,
    'player_status': 0, 'enemy_status': 0, 'battle_type': 0,
    'move0': -1, 'move1': -1, 'move2': -1, 'move3': -1,
    'pp0': -1, 'pp1': -1, 'pp2': -1, 'pp3': -1,
    'player_stat_stages': [-1, -1, -1, -1, -1, -1, -1],
    'enemy_move0': -1, 'enemy_move1': -1, 'enemy_move2': -1, 'enemy_move3': -1,
    'enemy_pp0': -1, 'enemy_pp1': -1, 'enemy_pp2': -1, 'enemy_pp3': -1,
    'enemy_stat_stages': [-1, -1, -1, -1, -1, -1, -1],
}

# ============================================================================
# DEFAULT PARTY DATA
# ============================================================================

DEFAULT_PARTY_SLOT = {
    'level': 0, 'hp': 0, 'max_hp': 0,
    'atk': 0, 'def': 0, 'spd': 0, 'spatk': 0, 'spdef': 0,
    'status': 0
}
DEFAULT_PARTY_DATA = {'count': 0, 'slots': []}

# ============================================================================
# DEFAULT MENU DATA
# ============================================================================

DEFAULT_MENU_DATA = {'mc': -1, 'mm': -1, 'pc': -1, 'sc': -1}

# ============================================================================
# DEFAULT BAG DATA
# ============================================================================

DEFAULT_BAG_DATA = {'pocket': -1, 'cursor': -1, 'active': 0, 'items': []}

# ============================================================================
# DEFAULT ITEM KNOWLEDGE ENTRY
# ============================================================================

DEFAULT_ITEM_KNOWLEDGE_ENTRY = {
    'uses': 0, 'category': 'unknown', 'confidence': 0.0,
    'avg_hp_restored': 0.0, 'total_hp_restored': 0,
    'status_cured': [], 'catch_attempts': 0,
    'catch_successes': 0, 'last_used_timestep': 0,
}

# ============================================================================
# ACTION SELECTION CONSTANTS
# ============================================================================

GBA_ACTIONS = ["Up", "Down", "Left", "Right", "A", "B", "Start", "Select"]

ACTION_DELTAS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
DIRECTION_TO_ACTION = {0: "DOWN", 1: "UP", 2: "LEFT", 3: "RIGHT"}
ACTION_TO_DIRECTION = {"DOWN": 0, "UP": 1, "LEFT": 2, "RIGHT": 3}

BATTLE_CURSOR_FIGHT = 0
BATTLE_CURSOR_BAG = 1
BATTLE_CURSOR_POKEMON = 2
BATTLE_CURSOR_RUN = 3

# Pipeline execution layer output → action mapping
# dims 0-7: UP, DOWN, LEFT, RIGHT, A, B, Start, Select
PIPELINE_ACTION_MAP = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "Start", "Select"]