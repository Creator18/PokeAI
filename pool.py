# ============================================================================
# pool.py — Pool and Pipeline Classes
# ============================================================================
# Fixed-width output pools and ordered pipeline sequences.
# Imports only from perceptron.py (for Perceptron class in type hints/restore)
# and numpy.
# ============================================================================

import numpy as np
from perceptron import Perceptron


# ============================================================================
# POOL CLASS — Fixed-Width Output Layer of Perceptrons
# ============================================================================

class Pool:
    """
    A pool is a layer within a pipeline. It contains zero or more perceptrons
    that share a semantic role. The pool produces a fixed-width output vector
    regardless of how many perceptrons it contains.

    When empty, it produces a neutral (zero) vector.
    """

    DEFAULT_OUTPUT_WIDTH = 8
    DEFAULT_MAX_PERCEPTRONS = 20
    AUTHORITY_FIT_THRESHOLD = 5.0
    AUTHORITY_MIN_FIT_SCORE = 0.1
    TOP_K_PER_DIM = 3
    RESIDUAL_MAX_ENTRIES = 50

    def __init__(self, pool_id, name, output_width=None, max_perceptrons=None):
        self.pool_id = pool_id
        self.name = name
        self.output_width = output_width or self.DEFAULT_OUTPUT_WIDTH
        self.max_perceptrons = max_perceptrons or self.DEFAULT_MAX_PERCEPTRONS

        self.perceptron_ids = []

        self.spawn_threshold = 0.0005
        self.spawn_count = 0
        self.last_spawn_timestep = 0

        self.authority = 0.0

        self.error_history = []
        self._error_history_maxlen = 200

        self.residual = {}

        self._cached_output = np.zeros(self.output_width)
        self._cached_output_valid = False

    def compute_output(self, input_vector, brain_perceptrons):
        """
        Compute fixed-width output from pool perceptrons.
        Top-k aggregation per output dimension.
        Authority quality gate: only fit perceptrons count.
        """
        pool_perceptrons = self._get_perceptrons(brain_perceptrons)

        if not pool_perceptrons:
            self._cached_output = np.zeros(self.output_width)
            self._cached_output_valid = True
            self.authority = 0.0
            return self._cached_output.copy()

        activations = []
        for p in pool_perceptrons:
            pred = p.predict(input_vector)
            weight = max(0.01, p.utility)
            activations.append((pred, weight, p))

        if not activations:
            self._cached_output = np.zeros(self.output_width)
            self._cached_output_valid = True
            return self._cached_output.copy()

        # Top-k aggregation per output dimension
        dim_candidates = [[] for _ in range(self.output_width)]
        for i, (pred, weight, p) in enumerate(activations):
            dim_idx = i % self.output_width
            dim_candidates[dim_idx].append((pred * weight, weight))

        output = np.zeros(self.output_width)
        for dim_idx in range(self.output_width):
            cands = dim_candidates[dim_idx]
            if not cands:
                continue
            cands.sort(key=lambda x: abs(x[0]), reverse=True)
            top_k = cands[:self.TOP_K_PER_DIM]
            total_weight = sum(w for _, w in top_k)
            if total_weight > 0:
                output[dim_idx] = sum(val for val, _ in top_k) / total_weight

        output_norm = np.linalg.norm(output)
        if output_norm > 0:
            output = output / max(1.0, output_norm)

        self._cached_output = output
        self._cached_output_valid = True

        # Authority quality gate
        good_perceptrons = [p for p in pool_perceptrons
                            if p.activation_fit_score > self.AUTHORITY_MIN_FIT_SCORE]
        if not good_perceptrons:
            self.authority = 0.0
        else:
            avg_fit = np.mean([p.activation_fit_score for p in good_perceptrons])
            n_good = len(good_perceptrons)
            self.authority = min(1.0, n_good * avg_fit / self.AUTHORITY_FIT_THRESHOLD)

        return output.copy()

    def get_cached_output(self):
        return self._cached_output.copy()

    def invalidate_cache(self):
        self._cached_output_valid = False

    def _get_perceptrons(self, brain_perceptrons):
        pool_id = self.pool_id
        return [p for p in brain_perceptrons if p.pool_id == pool_id]

    def get_perceptron_count(self, brain_perceptrons):
        return len(self._get_perceptrons(brain_perceptrons))

    def needs_spawn(self, error):
        return error > self.spawn_threshold

    def update_spawn_threshold(self, percentile=75):
        if len(self.error_history) >= 50:
            self.spawn_threshold = max(0.001, np.percentile(self.error_history, percentile))

    def record_error(self, error):
        self.error_history.append(error)
        if len(self.error_history) > self._error_history_maxlen:
            self.error_history = self.error_history[-self._error_history_maxlen:]

    def should_cluster(self, brain_perceptrons):
        return self.get_perceptron_count(brain_perceptrons) >= self.max_perceptrons

    # =================================================================
    # DIVERSIFIED INITIALIZATION
    # =================================================================

    def diversified_init(self, input_state, existing_count):
        """
        Initialize weights with diversity offset from existing perceptrons.
        Rotational offset + scaled noise for diverse initialization.
        """
        state_norm = np.linalg.norm(input_state)
        if state_norm > 0:
            base = (input_state / state_norm) * 0.1
        else:
            base = np.random.randn(len(input_state)) * 0.001

        if existing_count > 0:
            shift = existing_count * (len(input_state) // max(1, existing_count + 1))
            base = np.roll(base, shift)

        noise_scale = 0.001 * (1.0 + existing_count * 0.5)
        base += np.random.randn(len(input_state)) * noise_scale

        return base

    # =================================================================
    # RESIDUAL FILE (Memory Paging)
    # =================================================================

    def page_to_residual(self, perceptron):
        key = perceptron.trigger_context
        if key is None:
            key = f"_unnamed_{self.pool_id}_{perceptron.entity_type or perceptron.action or 'unknown'}"

        entry = {
            'kind': perceptron.kind,
            'action': perceptron.action,
            'group': perceptron.group,
            'entity_type': perceptron.entity_type,
            'chain': perceptron.chain,
            'utility': float(perceptron.utility),
            'familiarity': float(perceptron.familiarity),
            'learning_rate': float(perceptron.learning_rate),
            'active_activation': perceptron.active_activation,
            'activation_fit_score': float(perceptron.activation_fit_score),
            'trigger_context': perceptron.trigger_context,
            'weights_shape': len(perceptron.weights) if perceptron.weights is not None else 0,
            'weights_nonzero': [[i, float(v)] for i, v in enumerate(perceptron.weights)
                                if abs(v) > 1e-10] if perceptron.weights is not None else [],
            'paged_at': 0,
        }

        self.residual[str(key)] = entry

        if len(self.residual) > self.RESIDUAL_MAX_ENTRIES:
            oldest_key = min(self.residual.keys(),
                            key=lambda k: self.residual[k].get('paged_at', 0))
            del self.residual[oldest_key]

    def restore_from_residual(self, trigger_context):
        key = str(trigger_context)
        if key not in self.residual:
            return None

        entry = self.residual.pop(key)

        p = Perceptron(
            kind=entry['kind'],
            action=entry.get('action'),
            group=entry.get('group'),
            entity_type=entry.get('entity_type'),
            chain=entry.get('chain', 'shared'),
        )
        p.utility = entry.get('utility', 1.0)
        p.familiarity = entry.get('familiarity', 0.0)
        p.learning_rate = entry.get('learning_rate', 0.01)
        p.active_activation = entry.get('active_activation', 'linear')
        p.activation_fit_score = entry.get('activation_fit_score', 0.0)
        p.trigger_context = entry.get('trigger_context')
        p.pool_id = self.pool_id
        p.layer_index = None

        ws = entry.get('weights_shape', 0)
        if ws > 0 and entry.get('weights_nonzero'):
            p.weights = np.zeros(ws)
            for idx, val in entry['weights_nonzero']:
                if idx < ws:
                    p.weights[idx] = val

        return p

    def has_residual(self, trigger_context):
        return str(trigger_context) in self.residual

    # =================================================================
    # SERIALIZATION
    # =================================================================

    def get_save_state(self):
        return {
            'pool_id': self.pool_id,
            'name': self.name,
            'output_width': self.output_width,
            'max_perceptrons': self.max_perceptrons,
            'spawn_threshold': float(self.spawn_threshold),
            'spawn_count': self.spawn_count,
            'authority': float(self.authority),
            'residual': self.residual,
        }

    def load_save_state(self, state_dict):
        if state_dict is None:
            return
        self.output_width = state_dict.get('output_width', self.DEFAULT_OUTPUT_WIDTH)
        self.max_perceptrons = state_dict.get('max_perceptrons', self.DEFAULT_MAX_PERCEPTRONS)
        self.spawn_threshold = state_dict.get('spawn_threshold', 0.0005)
        self.spawn_count = state_dict.get('spawn_count', 0)
        self.authority = state_dict.get('authority', 0.0)
        self.residual = state_dict.get('residual', {})


# ============================================================================
# PIPELINE CLASS — Ordered Sequence of Pools
# ============================================================================

class Pipeline:
    """
    A pipeline is an ordered sequence of pools (layers) that process
    game state through increasing levels of abstraction.

    Layer 1 pools take raw game state as input.
    Layer N pools (N>1) take the fixed-width output of Layer N-1.
    Credit assignment flows backward with decay factor per layer.
    """

    DEFAULT_CREDIT_DECAY = 0.7

    def __init__(self, pipeline_id, name, pool_definitions, credit_decay=None):
        self.pipeline_id = pipeline_id
        self.name = name
        self.credit_decay = credit_decay or self.DEFAULT_CREDIT_DECAY

        self.pools = []
        for i, pdef in enumerate(pool_definitions):
            pool_id = f"{pipeline_id}_L{i}_{pdef['name']}"
            pool = Pool(
                pool_id=pool_id,
                name=pdef['name'],
                output_width=pdef.get('output_width', Pool.DEFAULT_OUTPUT_WIDTH),
                max_perceptrons=pdef.get('max_perceptrons', Pool.DEFAULT_MAX_PERCEPTRONS),
            )
            self.pools.append(pool)

        self.num_layers = len(self.pools)

        self._layer_inputs = []
        self._layer_outputs = []

        self.active = False

    def forward(self, raw_input, brain_perceptrons):
        """
        Run forward pass through all layers.
        Returns: (final_output, active)
        """
        self._layer_inputs = []
        self._layer_outputs = []

        current_input = raw_input
        any_active = False

        for i, pool in enumerate(self.pools):
            self._layer_inputs.append(current_input.copy())
            output = pool.compute_output(current_input, brain_perceptrons)
            self._layer_outputs.append(output.copy())

            if pool.authority > 0.0:
                any_active = True

            current_input = output

        self.active = any_active

        return self._layer_outputs[-1] if self._layer_outputs else np.zeros(
            self.pools[-1].output_width if self.pools else Pool.DEFAULT_OUTPUT_WIDTH
        ), any_active

    def backward(self, error_signal, brain_perceptrons):
        """
        Backward credit assignment through the pipeline.
        Error flows from last layer backward with decay.
        """
        if not self._layer_inputs:
            return

        for i in reversed(range(self.num_layers)):
            pool = self.pools[i]

            layers_from_output = self.num_layers - i - 1
            layer_error = error_signal * (self.credit_decay ** layers_from_output)

            pool.record_error(abs(layer_error))
            pool.update_spawn_threshold()

            layer_input = self._layer_inputs[i]
            pool_perceptrons = [p for p in brain_perceptrons if p.pool_id == pool.pool_id]

            for p in pool_perceptrons:
                p.update(layer_input, layer_error)

    def get_pool_at_layer(self, layer_index):
        if 0 <= layer_index < len(self.pools):
            return self.pools[layer_index]
        return None

    def get_input_width_for_layer(self, layer_index):
        if layer_index == 0:
            return None
        return self.pools[layer_index - 1].output_width

    def is_fallback_needed(self):
        return not self.active

    def get_total_authority(self):
        if not self.pools:
            return 0.0
        return np.mean([p.authority for p in self.pools])

    def get_layer_authorities(self):
        return {pool.name: pool.authority for pool in self.pools}

    # =================================================================
    # SPAWNING INTO POOLS
    # =================================================================

    def spawn_into_pool(self, layer_index, perceptron, brain):
        """
        Add a perceptron to a specific pool layer.
        Checks residual file first for reuse.
        Uses diversified initialization for fresh spawns.
        """
        pool = self.pools[layer_index]

        # Check residual first
        if perceptron.trigger_context and pool.has_residual(perceptron.trigger_context):
            restored = pool.restore_from_residual(perceptron.trigger_context)
            if restored is not None:
                restored.pool_id = pool.pool_id
                restored.layer_index = layer_index
                brain.add(restored)
                print(f"  🔄 RESTORED from residual: {pool.name} [{restored.trigger_context}]")
                return restored

        # Diversified initialization for fresh spawns
        existing_count = pool.get_perceptron_count(brain.perceptrons)
        if perceptron.weights is not None and len(perceptron.weights) > 0:
            perceptron.weights = pool.diversified_init(perceptron.weights, existing_count)

        perceptron.pool_id = pool.pool_id
        perceptron.layer_index = layer_index
        brain.add(perceptron)
        pool.spawn_count += 1

        return perceptron

    def prune_from_pool(self, layer_index, perceptron, brain_perceptrons, timestep=0):
        pool = self.pools[layer_index]
        entry = pool.page_to_residual(perceptron)
        if entry and hasattr(entry, 'get'):
            entry['paged_at'] = timestep
        perceptron.pool_id = None
        perceptron.layer_index = None
        return True

    # =================================================================
    # SERIALIZATION
    # =================================================================

    def get_save_state(self):
        return {
            'pipeline_id': self.pipeline_id,
            'name': self.name,
            'credit_decay': self.credit_decay,
            'pools': [pool.get_save_state() for pool in self.pools],
        }

    def load_save_state(self, state_dict):
        if state_dict is None:
            return
        self.credit_decay = state_dict.get('credit_decay', self.DEFAULT_CREDIT_DECAY)
        pool_states = state_dict.get('pools', [])
        for i, ps in enumerate(pool_states):
            if i < len(self.pools):
                self.pools[i].load_save_state(ps)

    def get_status(self, brain_perceptrons):
        status = {
            'pipeline': self.pipeline_id,
            'active': self.active,
            'total_authority': self.get_total_authority(),
            'layers': [],
        }
        for i, pool in enumerate(self.pools):
            n = pool.get_perceptron_count(brain_perceptrons)
            status['layers'].append({
                'name': pool.name,
                'perceptrons': n,
                'authority': pool.authority,
                'spawn_count': pool.spawn_count,
                'residual_size': len(pool.residual),
                'spawn_threshold': pool.spawn_threshold,
            })
        return status