# ============================================================================
# state.py — State Parsing, Normalization, Learning State Builders, Game IO
# ============================================================================
# Pure functions — no class state, no side effects beyond file IO.
# Imports only from constants.py and standard libs.
# ============================================================================

import json
import time
import numpy as np
from pathlib import Path

from constants import (
    STATE_FILE, ACTION_FILE, TYPE_DATA_FILE,
    EXPECTED_STATE_DIM, PALETTE_DIM, TILE_DIM,
    BATTLE_CHAIN_DIM, PARTY_CHAIN_DIM, BAG_CHAIN_DIM,
    DEFAULT_BATTLE_DATA, DEFAULT_PARTY_DATA, DEFAULT_PARTY_SLOT,
    DEFAULT_MENU_DATA, DEFAULT_BAG_DATA,
)


# ============================================================================
# NORMALIZATION & DERIVED FEATURES
# ============================================================================

def normalize_game_state(raw_state):
    if len(raw_state) < 6:
        return raw_state
    normalized = raw_state.copy()
    normalized[0] = raw_state[0] / 255.0
    normalized[1] = raw_state[1] / 255.0
    normalized[2] = np.clip(raw_state[2], 0, 255)
    normalized[3] = 1.0 if raw_state[3] > 0 else 0.0
    normalized[4] = 1.0 if raw_state[4] > 0 else 0.0
    normalized[5] = int(raw_state[5]) % 4
    return normalized


def compute_derived_features(current, prev):
    if prev is None:
        return np.zeros(8)
    vel_x = current[0] - prev[0]
    vel_y = current[1] - prev[1]
    map_changed = 1.0 if abs(current[2] - prev[2]) > 0.5 else 0.0
    battle_started = 1.0 if current[3] > prev[3] else 0.0
    battle_ended = 1.0 if current[3] < prev[3] else 0.0
    menu_opened = 1.0 if current[4] > prev[4] else 0.0
    menu_closed = 1.0 if current[4] < prev[4] else 0.0
    direction_changed = 1.0 if current[5] != prev[5] else 0.0
    return np.array([vel_x, vel_y, map_changed, battle_started, battle_ended,
                     menu_opened, menu_closed, direction_changed])


# ============================================================================
# CHAIN-SPECIFIC LEARNING STATE BUILDERS
# ============================================================================

def build_learning_state_overworld(derived, palette, tiles, in_battle):
    """
    Overworld chain learning state.
    In battle: derived(8) + palette(768) = 776 dims
    In overworld: derived(8) + tiles(600) + palette(768) = 1376 dims
    """
    if in_battle > 0.5:
        state = np.concatenate([derived, palette])
    else:
        state = np.concatenate([derived, tiles, palette])
    noise = np.random.randn(len(state)) * 0.0001
    return state + noise


# Backward compatibility alias
build_learning_state = build_learning_state_overworld


def build_learning_state_battle(battle_data, party_data=None, turn_count=0):
    """
    Battle chain learning state — compact features from battle memory.
    Layout (41 dims): see Cell 1 docstring for full layout.
    """
    bd = battle_data
    state = np.zeros(BATTLE_CHAIN_DIM)

    # Player
    state[0] = max(0, bd.get('player_species', -1)) / 500.0
    php, pmhp = bd.get('player_hp', -1), bd.get('player_max_hp', -1)
    state[1] = php / pmhp if pmhp > 0 and php >= 0 else 0.0
    state[2] = max(0, bd.get('player_level', -1)) / 100.0
    state[3] = 1.0 if bd.get('player_status', 0) != 0 else 0.0

    for i, mk in enumerate(['move0', 'move1', 'move2', 'move3']):
        state[4 + i] = max(0, bd.get(mk, -1)) / 500.0

    for i, pk in enumerate(['pp0', 'pp1', 'pp2', 'pp3']):
        pp = bd.get(pk, -1)
        state[8 + i] = pp / 40.0 if pp >= 0 else 0.0

    pss = bd.get('player_stat_stages', [-1]*7)
    for i in range(7):
        state[12 + i] = pss[i] / 12.0 if pss[i] >= 0 else 0.5

    # Enemy
    state[19] = max(0, bd.get('enemy_species', -1)) / 500.0
    ehp, emhp = bd.get('enemy_hp', -1), bd.get('enemy_max_hp', -1)
    state[20] = ehp / emhp if emhp > 0 and ehp >= 0 else 0.0
    state[21] = max(0, bd.get('enemy_level', -1)) / 100.0
    state[22] = 1.0 if bd.get('enemy_status', 0) != 0 else 0.0

    for i, mk in enumerate(['enemy_move0', 'enemy_move1', 'enemy_move2', 'enemy_move3']):
        state[23 + i] = max(0, bd.get(mk, -1)) / 500.0

    for i, pk in enumerate(['enemy_pp0', 'enemy_pp1', 'enemy_pp2', 'enemy_pp3']):
        pp = bd.get(pk, -1)
        state[27 + i] = pp / 40.0 if pp >= 0 else 0.0

    ess = bd.get('enemy_stat_stages', [-1]*7)
    for i in range(7):
        state[31 + i] = ess[i] / 12.0 if ess[i] >= 0 else 0.5

    # Context
    state[38] = 1.0 if (bd.get('battle_type', 0) & 8) != 0 else 0.0
    state[39] = min(turn_count, 20) / 20.0
    state[40] = 0.0  # damage_trend placeholder

    state += np.random.randn(BATTLE_CHAIN_DIM) * 0.0001
    return state


def build_learning_state_party(party_data, active_slot=-1):
    """
    Party chain learning state.
    Layout (50 dims): per slot (6×8=48) + context (2).
    """
    state = np.zeros(PARTY_CHAIN_DIM)
    slots = party_data.get('slots', [])

    for i in range(min(6, len(slots))):
        slot = slots[i]
        base = i * 8
        mhp = slot.get('max_hp', 0)
        state[base + 0] = slot.get('hp', 0) / mhp if mhp > 0 else 0.0
        state[base + 1] = slot.get('level', 0) / 100.0
        state[base + 2] = 1.0 if slot.get('status', 0) != 0 else 0.0
        state[base + 3] = slot.get('atk', 0) / 500.0
        state[base + 4] = slot.get('def', 0) / 500.0
        state[base + 5] = slot.get('spd', 0) / 500.0
        state[base + 6] = slot.get('spatk', 0) / 500.0
        state[base + 7] = slot.get('spdef', 0) / 500.0

    state[48] = party_data.get('count', 0) / 6.0
    state[49] = active_slot / 6.0 if active_slot >= 0 else 0.0

    state += np.random.randn(PARTY_CHAIN_DIM) * 0.0001
    return state


def build_learning_state_bag(bag_data, party_data, menu_data, in_battle=False, item_knowledge=None):
    """
    Bag chain learning state.
    Layout (18 dims): bag navigation context + party needs.
    """
    state = np.zeros(BAG_CHAIN_DIM)

    pocket = bag_data.get('pocket', -1)
    cursor = bag_data.get('cursor', -1)
    items = bag_data.get('items', [])

    state[0] = max(0, pocket) / 4.0
    state[1] = max(0, cursor) / 20.0

    if 0 <= cursor < len(items):
        state[2] = items[cursor].get('id', 0) / 500.0
    else:
        state[2] = 0.0

    state[3] = len(items) / 20.0

    slots = party_data.get('slots', [])
    for i in range(min(6, len(slots))):
        mhp = slots[i].get('max_hp', 0)
        state[4 + i] = slots[i].get('hp', 0) / mhp if mhp > 0 else 0.0

    for i in range(min(6, len(slots))):
        state[10 + i] = 1.0 if slots[i].get('status', 0) != 0 else 0.0

    state[16] = 1.0 if in_battle else 0.0
    state[17] = max(0, menu_data.get('mc', -1)) / 6.0

    state += np.random.randn(BAG_CHAIN_DIM) * 0.0001
    return state


# ============================================================================
# ARRAY HELPERS
# ============================================================================

def _pad_or_trim(arr, target_dim):
    if arr.shape[0] < target_dim:
        return np.pad(arr, (0, target_dim - arr.shape[0]))
    elif arr.shape[0] > target_dim:
        return arr[:target_dim]
    return arr


# ============================================================================
# GROUND-TRUTH TYPE DATA LOADER (Track B)
# ============================================================================

def load_type_data(filepath=None):
    """
    Load ground-truth type data from Lua verification script output.
    Returns: dict with parsed data, or None if file not found/invalid.
    """
    filepath = filepath or TYPE_DATA_FILE
    try:
        if not Path(filepath).exists():
            return None

        with open(filepath, 'r') as f:
            raw = json.load(f)

        data = {
            'species_types': {},
            'move_types': {},
            'type_chart': {},
            'type_names': {},
            'loaded': True,
        }

        for sid, types in raw.get('species_types', {}).items():
            species_id = int(sid)
            if isinstance(types, list) and len(types) >= 1:
                t1 = types[0]
                t2 = types[1] if len(types) > 1 else -1
                data['species_types'][species_id] = [t1, t2]

        for mid, mtype in raw.get('move_types', {}).items():
            data['move_types'][int(mid)] = int(mtype)

        for key, mult in raw.get('type_chart', {}).items():
            data['type_chart'][key] = float(mult)

        for tid, tname in raw.get('type_names', {}).items():
            data['type_names'][int(tid)] = tname

        print(f"  🧬 Type data loaded (Track B):")
        print(f"     Species: {len(data['species_types'])}")
        print(f"     Moves: {len(data['move_types'])}")
        print(f"     Chart entries: {len(data['type_chart'])}")
        print(f"     Types: {len(data['type_names'])}")

        return data

    except Exception as e:
        print(f"  ⚠️ Error loading type data: {e}")
        return None


def get_type_effectiveness(type_data, move_id, species_id):
    """
    Look up type effectiveness for a move against a species.
    Returns: float multiplier or None if unknown.
    """
    if type_data is None or not type_data.get('loaded'):
        return None

    move_type = type_data['move_types'].get(move_id)
    if move_type is None:
        return None

    species_types = type_data['species_types'].get(species_id)
    if species_types is None:
        return None

    multiplier = 1.0
    for def_type in species_types:
        if def_type < 0:
            continue
        key = f"{move_type}_{def_type}"
        chart_mult = type_data['type_chart'].get(key)
        if chart_mult is not None:
            multiplier *= chart_mult

    return multiplier


# ============================================================================
# PARSERS
# ============================================================================

def parse_battle_data(data):
    b = data.get('b')
    if b is None:
        return DEFAULT_BATTLE_DATA.copy()

    pss = b.get('pss')
    if not isinstance(pss, list) or len(pss) != 7:
        pss = [-1, -1, -1, -1, -1, -1, -1]
    else:
        pss = list(pss)

    ess = b.get('ess')
    if not isinstance(ess, list) or len(ess) != 7:
        ess = [-1, -1, -1, -1, -1, -1, -1]
    else:
        ess = list(ess)

    return {
        'battle_cursor': b.get('bc', -1), 'move_cursor': b.get('mc', -1),
        'party_cursor': b.get('pc', -1),
        'player_species': b.get('ps', -1), 'enemy_species': b.get('es', -1),
        'player_hp': b.get('ph', -1), 'player_max_hp': b.get('pm', -1),
        'enemy_hp': b.get('eh', -1), 'enemy_max_hp': b.get('em', -1),
        'player_level': b.get('pl', -1), 'enemy_level': b.get('el', -1),
        'player_status': b.get('pst', 0), 'enemy_status': b.get('est', 0),
        'battle_type': b.get('bt', 0),
        'move0': b.get('m0', -1), 'move1': b.get('m1', -1),
        'move2': b.get('m2', -1), 'move3': b.get('m3', -1),
        'pp0': b.get('pp0', -1), 'pp1': b.get('pp1', -1),
        'pp2': b.get('pp2', -1), 'pp3': b.get('pp3', -1),
        'player_stat_stages': pss,
        'enemy_move0': b.get('em0', -1), 'enemy_move1': b.get('em1', -1),
        'enemy_move2': b.get('em2', -1), 'enemy_move3': b.get('em3', -1),
        'enemy_pp0': b.get('epp0', -1), 'enemy_pp1': b.get('epp1', -1),
        'enemy_pp2': b.get('epp2', -1), 'enemy_pp3': b.get('epp3', -1),
        'enemy_stat_stages': ess,
    }


def parse_party_data(data):
    pa = data.get('pa')
    if pa is None:
        return DEFAULT_PARTY_DATA.copy()
    count = pa.get('c', 0)
    raw_slots = pa.get('s', [])
    slots = []
    for s in raw_slots:
        if not isinstance(s, dict): continue
        slots.append({
            'level': s.get('l', 0), 'hp': s.get('h', 0), 'max_hp': s.get('m', 0),
            'atk': s.get('a', 0), 'def': s.get('d', 0), 'spd': s.get('sp', 0),
            'spatk': s.get('sa', 0), 'spdef': s.get('sd', 0), 'status': s.get('st', 0),
        })
    return {'count': count, 'slots': slots}


def parse_menu_data(data):
    mu = data.get('mu')
    if mu is None:
        return DEFAULT_MENU_DATA.copy()
    return {'mc': mu.get('mc', -1), 'mm': mu.get('mm', -1),
            'pc': mu.get('pc', -1), 'sc': mu.get('sc', -1)}


def parse_bag_data(data):
    bg = data.get('bg')
    if bg is None:
        return DEFAULT_BAG_DATA.copy()
    items = []
    for item in bg.get('it', []):
        if isinstance(item, dict) and 'id' in item:
            items.append({'id': item.get('id', 0), 'q': item.get('q', 0)})
    return {'pocket': bg.get('pk', -1), 'cursor': bg.get('bc', -1),
            'active': bg.get('a', 0), 'items': items}


def parse_game_state_data(data):
    """
    Parse all fields from game_state.json.
    Extracts "tf" (text_flag) — 0=no dialogue, 1=text box active.
    """
    raw = data.get("state") or data.get("s") or []
    palette_raw = data.get("palette") or data.get("p") or []
    tiles_raw = data.get("tiles") or data.get("t") or []
    dead = bool(data.get("dead", False))
    battle_data = parse_battle_data(data)
    party_data = parse_party_data(data)
    game_state_raw = data.get("gs", 0)
    menu_data = parse_menu_data(data)
    bag_data = parse_bag_data(data)
    text_flag = int(data.get("tf", 0))
    return raw, palette_raw, tiles_raw, dead, battle_data, party_data, game_state_raw, menu_data, bag_data, text_flag


# ============================================================================
# GAME STATE IO
# ============================================================================

def read_game_state(max_retries=3):
    """
    Read and parse game_state.json.
    Returns 11 values:
        (context_state, palette_state, tile_state, dead, raw_position,
         battle_data, party_data, game_state_raw, menu_data, bag_data,
         text_flag)
    """
    if not STATE_FILE.exists():
        return (np.zeros(EXPECTED_STATE_DIM), np.zeros(PALETTE_DIM), np.zeros(TILE_DIM),
                False, (0, 0), DEFAULT_BATTLE_DATA.copy(), DEFAULT_PARTY_DATA.copy(),
                0, DEFAULT_MENU_DATA.copy(), DEFAULT_BAG_DATA.copy(), 0)

    for attempt in range(max_retries):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.loads(f.read())

            (raw, palette_raw, tiles_raw, dead, battle_data, party_data,
             game_state_raw, menu_data, bag_data, text_flag) = parse_game_state_data(data)

            raw_x = int(raw[0]) if len(raw) > 0 else 0
            raw_y = int(raw[1]) if len(raw) > 1 else 0
            raw_position = (raw_x, raw_y)

            context_state = normalize_game_state(np.array(raw, dtype=float))
            palette_state = np.array(palette_raw, dtype=float) if palette_raw else np.zeros(PALETTE_DIM)
            tile_state = np.array(tiles_raw, dtype=float) if tiles_raw else np.zeros(TILE_DIM)

            context_state = _pad_or_trim(context_state, EXPECTED_STATE_DIM)
            palette_state = _pad_or_trim(palette_state, PALETTE_DIM)
            tile_state = _pad_or_trim(tile_state, TILE_DIM)

            return (context_state, palette_state, tile_state, dead, raw_position,
                    battle_data, party_data, game_state_raw, menu_data, bag_data,
                    text_flag)

        except (json.JSONDecodeError, ValueError):
            if attempt < max_retries - 1:
                time.sleep(0.001)
                continue
            return (np.zeros(EXPECTED_STATE_DIM), np.zeros(PALETTE_DIM), np.zeros(TILE_DIM),
                    False, (0, 0), DEFAULT_BATTLE_DATA.copy(), DEFAULT_PARTY_DATA.copy(),
                    0, DEFAULT_MENU_DATA.copy(), DEFAULT_BAG_DATA.copy(), 0)
        except Exception:
            return (np.zeros(EXPECTED_STATE_DIM), np.zeros(PALETTE_DIM), np.zeros(TILE_DIM),
                    False, (0, 0), DEFAULT_BATTLE_DATA.copy(), DEFAULT_PARTY_DATA.copy(),
                    0, DEFAULT_MENU_DATA.copy(), DEFAULT_BAG_DATA.copy(), 0)


def write_action(action_name):
    if action_name:
        action_name = action_name.upper()
    try:
        with open(ACTION_FILE, "w") as f:
            json.dump({"action": action_name}, f)
            f.flush()
    except Exception as e:
        print(f"[ERROR] Failed to write action: {e}")