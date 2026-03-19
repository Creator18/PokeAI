# ============================================================================
# cache.py — MapCache, CacheManager, IOThread, SaveWorkerThread,
#             EventRecorderThread (Cell 5)
# ============================================================================
# Thread-safe caching layer between game IO and brain processing.
# ============================================================================

import threading
import queue
import time
import json
import gc
import numpy as np
from pathlib import Path

from constants import (
    EXPECTED_STATE_DIM, PALETTE_DIM, TILE_DIM,
    DEFAULT_BATTLE_DATA, DEFAULT_PARTY_DATA,
    DEFAULT_MENU_DATA, DEFAULT_BAG_DATA,
    EXPLORATION_MEMORY_FILE, AI_EVENT_TIMELINE_FILE,
)
from state import read_game_state, write_action


# ============================================================================
# MAP CACHE
# ============================================================================

class MapCache:
    """Thread-safe container for one map's data."""

    def __init__(self, map_id):
        self.map_id = map_id
        self.lock = threading.Lock()

        self.exploration_data = None
        self.taught_frames = []

        self.current_state = np.zeros(EXPECTED_STATE_DIM)
        self.palette = np.zeros(PALETTE_DIM)
        self.tiles = np.zeros(TILE_DIM)
        self.raw_position = (0, 0)
        self.dead = False
        self.battle_data = DEFAULT_BATTLE_DATA.copy()
        self.party_data = DEFAULT_PARTY_DATA.copy()
        self.game_state_raw = 0
        self.menu_data = DEFAULT_MENU_DATA.copy()
        self.bag_data = DEFAULT_BAG_DATA.copy()
        self.text_flag = 0
        self.state_fresh = False
        self.state_version = 0

        self.pending_action_out = None

    def get_state(self):
        with self.lock:
            return (
                self.current_state.copy(), self.palette.copy(), self.tiles.copy(),
                self.dead, self.raw_position,
                self.battle_data.copy(), self.party_data.copy(),
                self.game_state_raw, self.menu_data.copy(), self.bag_data.copy(),
                self.text_flag,
            )

    def update_state(self, context_state, palette, tiles, dead, raw_position,
                     battle_data=None, party_data=None,
                     game_state_raw=None, menu_data=None, bag_data=None,
                     text_flag=None):
        with self.lock:
            self.current_state = context_state; self.palette = palette
            self.tiles = tiles; self.dead = dead; self.raw_position = raw_position
            if battle_data is not None: self.battle_data = battle_data
            if party_data is not None: self.party_data = party_data
            if game_state_raw is not None: self.game_state_raw = game_state_raw
            if menu_data is not None: self.menu_data = menu_data
            if bag_data is not None: self.bag_data = bag_data
            if text_flag is not None: self.text_flag = text_flag
            self.state_fresh = True; self.state_version += 1

    def is_fresh(self):
        with self.lock: return self.state_fresh

    def mark_consumed(self):
        with self.lock: self.state_fresh = False

    def get_version(self):
        with self.lock: return self.state_version

    def set_pending_action(self, action_name):
        with self.lock: self.pending_action_out = action_name

    def get_pending_action(self):
        with self.lock:
            a = self.pending_action_out; self.pending_action_out = None; return a

    def get_taught_frames(self):
        return self.taught_frames


# ============================================================================
# CACHE MANAGER
# ============================================================================

class CacheManager:
    """Manages all MapCaches. Pre-indexes at startup, handles map switching."""

    def __init__(self, brain):
        self.brain = brain
        self.caches = {}
        self.active_cache = None
        self.active_map_id = None
        self.lock = threading.Lock()

    def load_all(self, exploration_path=None, taught_path=None):
        for map_id, mem_data in self.brain.exploration_memory.items():
            cache = self._get_or_create(map_id)
            cache.exploration_data = mem_data

        taught_by_map = {}
        for t in self.brain.taught_transitions:
            t_map = t.get('state', {}).get('map_id')
            if t_map is not None: taught_by_map.setdefault(t_map, []).append(t)

        for map_id, frames in taught_by_map.items():
            cache = self._get_or_create(map_id)
            cache.taught_frames = frames

        total_maps = len(self.caches)
        total_taught = sum(len(c.taught_frames) for c in self.caches.values())
        print(f"  📦 CacheManager: {total_maps} maps cached, {total_taught} taught frames indexed")

    def _get_or_create(self, map_id):
        if map_id not in self.caches: self.caches[map_id] = MapCache(map_id)
        return self.caches[map_id]

    def get_active(self):
        return self.active_cache

    def detect_and_set_initial_map(self):
        (ctx, pal, til, dead, raw_pos, battle_data, party_data,
         game_state_raw, menu_data, bag_data, text_flag) = read_game_state()
        map_id = int(ctx[2])
        self._switch_to(map_id)
        self.active_cache.update_state(ctx, pal, til, dead, raw_pos,
                                       battle_data, party_data,
                                       game_state_raw, menu_data, bag_data, text_flag)
        print(f"  📦 Initial map: {map_id}")
        return map_id

    def switch_map(self, new_map_id):
        if new_map_id == self.active_map_id: return
        self._sync_from_brain()
        self._switch_to(new_map_id)
        self._sync_to_brain()

    def _switch_to(self, map_id):
        with self.lock:
            cache = self._get_or_create(map_id)
            self.active_cache = cache; self.active_map_id = map_id

    def _sync_to_brain(self):
        cache = self.active_cache
        if cache and cache.exploration_data is not None:
            self.brain.exploration_memory[cache.map_id] = cache.exploration_data

    def _sync_from_brain(self):
        cache = self.active_cache
        if cache and cache.map_id in self.brain.exploration_memory:
            cache.exploration_data = self.brain.exploration_memory[cache.map_id]

    def sync_all_from_brain(self):
        for map_id, mem_data in self.brain.exploration_memory.items():
            cache = self._get_or_create(map_id)
            cache.exploration_data = mem_data

    def save_exploration_memory(self):
        self._sync_from_brain()
        self.brain.save_exploration_memory()

    def get_active_taught_frames(self):
        if self.active_cache: return self.active_cache.get_taught_frames()
        return []

    def get_map_density(self):
        if not self.active_cache:
            return {'taught_frames': 0, 'tier': 'sparse', 'coverage': 0.0, 'visited': 0}
        n_frames = len(self.active_cache.get_taught_frames())
        map_id = self.active_map_id
        coverage = self.brain.get_exploration_coverage(map_id) if map_id is not None else 0.0
        memory = self.brain.get_current_map_memory(map_id) if map_id is not None else {}
        visited = len(memory.get('visited_tiles', set()))
        if n_frames < 50: tier = 'sparse'
        elif n_frames < 200: tier = 'thin'
        elif n_frames < 1000: tier = 'medium'
        else: tier = 'dense'
        return {'taught_frames': n_frames, 'tier': tier, 'coverage': coverage, 'visited': visited}


# ============================================================================
# IO THREAD
# ============================================================================

class IOThread(threading.Thread):
    """Background thread: reads game_state.json, writes action.json."""

    def __init__(self, cache_manager, interval=0.02, gc_interval=300):
        super().__init__(daemon=True)
        self.cm = cache_manager; self.interval = interval
        self.gc_interval = gc_interval; self.running = False; self._iteration = 0

    def run(self):
        self.running = True
        print(f"  🔄 IOThread started (interval={self.interval*1000:.0f}ms)")
        while self.running:
            try:
                cache = self.cm.get_active()
                if cache is None: time.sleep(self.interval); continue

                (ctx, pal, til, dead, raw_pos, battle_data, party_data,
                 game_state_raw, menu_data, bag_data, text_flag) = read_game_state()
                cache.update_state(ctx, pal, til, dead, raw_pos,
                                   battle_data, party_data,
                                   game_state_raw, menu_data, bag_data, text_flag)

                action = cache.get_pending_action()
                if action is not None: write_action(action)

                self._iteration += 1
                if self._iteration % self.gc_interval == 0: gc.collect()
            except Exception as e:
                print(f"  [IOThread ERROR] {e}")
            time.sleep(self.interval)

    def stop(self):
        self.running = False; print("  🔄 IOThread stopped")


# ============================================================================
# SAVE WORKER THREAD
# ============================================================================

class SaveWorkerThread(threading.Thread):
    """Background thread for all brain state file I/O saves."""

    _SENTINEL = object()

    def __init__(self, maxsize=3):
        super().__init__(daemon=True)
        self.save_queue = queue.Queue(maxsize=maxsize)
        self.running = False; self.saves_completed = 0; self.saves_dropped = 0
        self.last_save_duration = 0.0; self.total_save_time = 0.0
        self._lock = threading.Lock()

    def run(self):
        self.running = True
        print(f"  💾 SaveWorkerThread started (queue maxsize={self.save_queue.maxsize})")
        while self.running:
            try:
                try: job = self.save_queue.get(timeout=1.0)
                except queue.Empty: continue
                if job is self._SENTINEL: self.save_queue.task_done(); break

                start_time = time.time()
                self._process_job(job)
                duration = time.time() - start_time
                with self._lock:
                    self.saves_completed += 1; self.last_save_duration = duration
                    self.total_save_time += duration
                self.save_queue.task_done(); gc.collect()
            except Exception as e:
                print(f"  [SaveWorker ERROR] {e}")
                try: self.save_queue.task_done()
                except ValueError: pass

        self.running = False
        print(f"  💾 SaveWorkerThread stopped ({self.saves_completed} saves, "
              f"{self.saves_dropped} dropped, {self.total_save_time:.1f}s total)")

    def _process_job(self, job):
        job_type = job.get('type', 'unknown')
        brain = job.get('brain'); cache_manager = job.get('cache_manager')
        filepath = job.get('filepath'); timestep = job.get('timestep', -1)
        if brain is None: return

        try:
            if job_type == 'checkpoint':
                if filepath: brain.save_model_checkpoint(filepath); print(f"  💾 Checkpoint saved (step {timestep}, bg)")
            elif job_type == 'exploration':
                if cache_manager: cache_manager.save_exploration_memory()
                else: brain.save_exploration_memory()
            elif job_type == 'roster': brain.save_roster()
            elif job_type == 'move_knowledge': brain.save_move_knowledge()
            elif job_type == 'item_knowledge': brain.save_item_knowledge()
            elif job_type == 'type_clusters': brain.save_type_clusters()
            elif job_type == 'all_knowledge':
                if cache_manager: cache_manager.save_exploration_memory()
                else: brain.save_exploration_memory()
                if brain.roster_dirty: brain.save_roster()
                if brain.move_knowledge_dirty: brain.save_move_knowledge()
                if brain.item_knowledge_dirty: brain.save_item_knowledge()
                if brain.type_clusters_dirty: brain.save_type_clusters()
                if filepath: brain.save_model_checkpoint(filepath)
                print(f"  💾 Full save completed (step {timestep}, bg)")
            else: print(f"  [SaveWorker] Unknown job type: {job_type}")
        except Exception as e: print(f"  [SaveWorker] Error in {job_type}: {e}")

    def submit_job(self, job):
        try: self.save_queue.put_nowait(job); return True
        except queue.Full:
            try:
                self.save_queue.get_nowait(); self.save_queue.task_done()
                with self._lock: self.saves_dropped += 1
            except queue.Empty: pass
            try: self.save_queue.put_nowait(job); return True
            except queue.Full:
                with self._lock: self.saves_dropped += 1
                return False

    def submit_checkpoint(self, brain, filepath, timestep, cache_manager=None):
        return self.submit_job({'type': 'checkpoint', 'brain': brain, 'filepath': filepath,
                                'timestep': timestep, 'cache_manager': cache_manager})

    def submit_exploration(self, brain, cache_manager=None):
        return self.submit_job({'type': 'exploration', 'brain': brain, 'cache_manager': cache_manager})

    def submit_all_knowledge(self, brain, filepath, timestep, cache_manager=None):
        return self.submit_job({'type': 'all_knowledge', 'brain': brain, 'filepath': filepath,
                                'timestep': timestep, 'cache_manager': cache_manager})

    def submit_dirty_knowledge(self, brain):
        submitted = 0
        if brain.roster_dirty: self.submit_job({'type': 'roster', 'brain': brain}); submitted += 1
        if brain.move_knowledge_dirty: self.submit_job({'type': 'move_knowledge', 'brain': brain}); submitted += 1
        if brain.item_knowledge_dirty: self.submit_job({'type': 'item_knowledge', 'brain': brain}); submitted += 1
        if brain.type_clusters_dirty: self.submit_job({'type': 'type_clusters', 'brain': brain}); submitted += 1
        return submitted

    def get_stats(self):
        with self._lock:
            return {
                'saves_completed': self.saves_completed, 'saves_dropped': self.saves_dropped,
                'last_save_duration': self.last_save_duration, 'total_save_time': self.total_save_time,
                'queue_size': self.save_queue.qsize(), 'running': self.running,
            }

    def stop(self):
        self.running = False
        try:
            while not self.save_queue.empty():
                try: self.save_queue.get_nowait(); self.save_queue.task_done()
                except queue.Empty: break
            self.save_queue.put_nowait(self._SENTINEL)
        except queue.Full: pass


# ============================================================================
# EVENT RECORDER THREAD
# ============================================================================

class EventRecorderThread(threading.Thread):
    """Background thread for recording AI-side events to ai_event_timeline.json."""

    _SENTINEL = object()

    def __init__(self, filepath=None, flush_interval=30, max_queue_size=100, max_events=5000):
        super().__init__(daemon=True)
        self.filepath = filepath or AI_EVENT_TIMELINE_FILE
        self.flush_interval = flush_interval; self.max_events = max_events
        self.event_queue = queue.Queue(maxsize=max_queue_size)
        self.events = []; self.running = False
        self.battle_count = 0; self.bag_count = 0; self.map_count = 0; self.levelup_count = 0
        self.maps_seen = set()
        self._last_flush_time = 0.0; self._lock = threading.Lock()

    def run(self):
        self.running = True; self._last_flush_time = time.time()
        self._load_existing()
        print(f"  📝 EventRecorderThread started (flush every {self.flush_interval}s, "
              f"max {self.max_events} events, existing: {len(self.events)})")

        while self.running:
            try:
                while True:
                    try: event = self.event_queue.get_nowait()
                    except queue.Empty: break
                    if event is self._SENTINEL:
                        self.event_queue.task_done(); self._flush_to_disk()
                        self.running = False; break
                    self._record_event(event); self.event_queue.task_done()
                if not self.running: break
                now = time.time()
                if now - self._last_flush_time >= self.flush_interval:
                    self._flush_to_disk(); self._last_flush_time = now
                time.sleep(0.5)
            except Exception as e: print(f"  [EventRecorder ERROR] {e}"); time.sleep(1.0)

        self.running = False
        print(f"  📝 EventRecorderThread stopped ({len(self.events)} events recorded)")

    def _load_existing(self):
        try:
            if Path(self.filepath).exists():
                with open(self.filepath, 'r') as f: data = json.load(f)
                self.events = data.get('events', [])
                summary = data.get('summary', {})
                self.battle_count = summary.get('battle_events', 0)
                self.bag_count = summary.get('bag_events', 0)
                self.map_count = summary.get('map_events', 0)
                self.levelup_count = summary.get('levelup_events', 0)
                self.maps_seen = set(summary.get('maps_visited', []))
        except Exception: self.events = []

    def _record_event(self, event):
        with self._lock:
            self.events.append(event)
            etype = event.get('type', '')
            if etype == 'battle_end': self.battle_count += 1
            elif etype == 'bag_session': self.bag_count += 1
            elif etype == 'map_transition': self.map_count += 1
            elif etype == 'level_up': self.levelup_count += 1
            map_id = event.get('map_id')
            if map_id is not None: self.maps_seen.add(map_id)
            if len(self.events) > self.max_events:
                self.events = self.events[self.max_events // 5:]

    def _flush_to_disk(self):
        with self._lock:
            if not self.events: return
            try:
                first_ts = self.events[0].get('timestep', 0) if self.events else 0
                last_ts = self.events[-1].get('timestep', 0) if self.events else 0
                data = {
                    'events': self.events,
                    'summary': {
                        'total_events': len(self.events),
                        'battle_events': self.battle_count, 'bag_events': self.bag_count,
                        'map_events': self.map_count, 'levelup_events': self.levelup_count,
                        'first_timestep': first_ts, 'last_timestep': last_ts,
                        'maps_visited': sorted(self.maps_seen),
                    }
                }
                with open(self.filepath, 'w') as f: json.dump(data, f, indent=2)
            except Exception as e: print(f"  [EventRecorder] Flush error: {e}")

    def get_queue(self): return self.event_queue

    def get_stats(self):
        with self._lock:
            return {
                'running': self.running, 'total_events': len(self.events),
                'battles': self.battle_count, 'bags': self.bag_count,
                'maps': self.map_count, 'levelups': self.levelup_count,
                'maps_visited': len(self.maps_seen), 'queue_size': self.event_queue.qsize(),
            }

    def stop(self):
        self.running = False
        try: self.event_queue.put_nowait(self._SENTINEL)
        except queue.Full: self._flush_to_disk()