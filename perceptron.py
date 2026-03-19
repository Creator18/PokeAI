# ============================================================================
# perceptron.py — ActivationLibrary, Perceptron, ControlSwapPerceptron
# ============================================================================
# Core learning units. No dependency on Brain or Pool — those import this.
# ============================================================================

import numpy as np
from collections import deque


# ============================================================================
# ACTIVATION LIBRARY
# ============================================================================

class ActivationLibrary:
    """
    Shared library of candidate activation functions.
    Each candidate: {name, func, category, suited_for, param}
    """

    def __init__(self):
        self.candidates = []
        self._build_standard_library()

    def _build_standard_library(self):
        self.candidates = [
            {
                'name': 'linear',
                'func': lambda x: x,
                'category': 'standard',
                'suited_for': ['action_continuous', 'entity'],
                'param': None,
            },
            {
                'name': 'tanh',
                'func': lambda x: np.tanh(x),
                'category': 'standard',
                'suited_for': ['entity', 'action_continuous'],
                'param': None,
            },
            {
                'name': 'relu',
                'func': lambda x: max(0.0, x),
                'category': 'standard',
                'suited_for': ['action_continuous'],
                'param': None,
            },
            {
                'name': 'sigmoid',
                'func': lambda x: 1.0 / (1.0 + np.exp(-np.clip(x, -20.0, 20.0))),
                'category': 'standard',
                'suited_for': ['action_binary', 'entity'],
                'param': None,
            },
            {
                'name': 'bounded_linear',
                'func': lambda x: np.clip(x, -1.0, 1.0),
                'category': 'standard',
                'suited_for': ['action_continuous', 'entity'],
                'param': None,
            },
            {
                'name': 'soft_threshold_0.1',
                'func': lambda x: x if abs(x) > 0.1 else 0.0,
                'category': 'standard',
                'suited_for': ['entity', 'action_continuous'],
                'param': 0.1,
            },
            {
                'name': 'soft_threshold_0.3',
                'func': lambda x: x if abs(x) > 0.3 else 0.0,
                'category': 'standard',
                'suited_for': ['entity'],
                'param': 0.3,
            },
            {
                'name': 'leaky_relu',
                'func': lambda x: x if x > 0 else 0.01 * x,
                'category': 'standard',
                'suited_for': ['action_continuous', 'entity'],
                'param': None,
            },
            {
                'name': 'abs',
                'func': lambda x: abs(x),
                'category': 'standard',
                'suited_for': ['entity'],
                'param': None,
            },
            {
                'name': 'squared',
                'func': lambda x: x * abs(x),
                'category': 'standard',
                'suited_for': ['entity', 'action_continuous'],
                'param': None,
            },
        ]

    def get_candidates(self, suited_for=None):
        if suited_for is None:
            return self.candidates
        return [c for c in self.candidates
                if suited_for in c.get('suited_for', [])]

    def get_by_name(self, name):
        for c in self.candidates:
            if c['name'] == name:
                return c
        return None

    def add_discovered(self, name, func, suited_for, param=None):
        if self.get_by_name(name) is not None:
            return
        self.candidates.append({
            'name': name,
            'func': func,
            'category': 'discovered',
            'suited_for': suited_for,
            'param': param,
        })

    def get_names(self):
        return [c['name'] for c in self.candidates]


# Global shared library — all perceptrons reference the same instance
ACTIVATION_LIBRARY = ActivationLibrary()


# ============================================================================
# PERCEPTRON
# ============================================================================

class Perceptron:
    def __init__(self, kind, action=None, group=None, entity_type=None, chain="shared"):
        self.kind = kind
        self.action = action
        self.group = group
        self.entity_type = entity_type
        self.chain = chain

        self.utility = 1.0
        self.weights = None

        self.eligibility_fast = 0.0
        self.eligibility_slow = 0.0

        self.familiarity = 0.0
        self.activation_history = deque(maxlen=10)
        self.cluster_activations = deque(maxlen=50)

        self.learning_rate = 0.01
        self.prediction_errors = deque(maxlen=50)

        # === POOL MEMBERSHIP ===
        self.pool_id = None
        self.layer_index = None
        self.trigger_context = None

        # === EMPIRICAL ACTIVATION DISCOVERY ===
        self.activation_observations = deque(maxlen=200)
        self.active_activation = 'linear'

        self.ACTIVATION_FIT_INTERVAL = 100
        self.ACTIVATION_MIN_OBSERVATIONS = 30
        self._activation_update_counter = 0

        self.activation_fit_score = 0.0
        self.activation_fit_history = deque(maxlen=10)
        self.activation_change_count = 0

    def _get_activation_func(self):
        candidate = ACTIVATION_LIBRARY.get_by_name(self.active_activation)
        if candidate is not None:
            return candidate['func']
        return lambda x: x

    def _apply_activation(self, x):
        func = self._get_activation_func()
        try:
            return func(x)
        except (ValueError, OverflowError):
            return x

    def _get_suited_for_hint(self):
        if self.kind == "entity":
            return "entity"
        if self.kind == "action":
            if self.group == "interact":
                return "action_binary"
            if self.group == "move":
                return "action_continuous"
        return "action_continuous"

    def _evaluate_activation_fit(self, candidate_func):
        if len(self.activation_observations) < self.ACTIVATION_MIN_OBSERVATIONS:
            return 0.0

        observations = list(self.activation_observations)
        raw_inputs = [obs[0] for obs in observations]
        errors = [obs[1] for obs in observations]

        try:
            candidate_outputs = [candidate_func(x) for x in raw_inputs]
        except (ValueError, OverflowError):
            return -1.0

        abs_outputs = np.array([abs(o) for o in candidate_outputs])
        abs_errors = np.array([abs(e) for e in errors])

        if np.std(abs_outputs) < 1e-10 or np.std(abs_errors) < 1e-10:
            return 0.0

        correlation = np.corrcoef(abs_outputs, abs_errors)[0, 1]

        if np.isnan(correlation):
            return 0.0

        output_variance = np.std(abs_outputs)
        variance_bonus = min(0.2, output_variance * 0.5)

        max_output = max(abs_outputs)
        if max_output > 100:
            return correlation * 0.5

        return correlation + variance_bonus

    def fit_activation(self):
        if len(self.activation_observations) < self.ACTIVATION_MIN_OBSERVATIONS:
            return

        hint = self._get_suited_for_hint()

        suited_candidates = ACTIVATION_LIBRARY.get_candidates(suited_for=hint)
        all_candidates = ACTIVATION_LIBRARY.candidates

        scored = []
        suited_names = {c['name'] for c in suited_candidates}

        for candidate in all_candidates:
            score = self._evaluate_activation_fit(candidate['func'])
            if candidate['name'] in suited_names:
                score += 0.05
            scored.append((candidate['name'], score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            return

        best_name, best_score = scored[0]
        current_score = self._evaluate_activation_fit(self._get_activation_func())

        self.activation_fit_score = current_score
        self.activation_fit_history.append(current_score)

        SWITCH_THRESHOLD = 0.1

        if best_name != self.active_activation and best_score > current_score + SWITCH_THRESHOLD:
            old_name = self.active_activation
            self.active_activation = best_name
            self.activation_change_count += 1

            if self.activation_change_count <= 5 or self.activation_change_count % 10 == 0:
                id_str = self.action or self.entity_type or "?"
                print(f"  🧬 ACTIVATION [{self.chain}:{id_str}]: {old_name} → {best_name} "
                      f"(score {current_score:.3f} → {best_score:.3f}, "
                      f"change #{self.activation_change_count})")

    def ensure_weights(self, dim):
        if self.weights is None:
            self.weights = np.random.randn(dim) * 0.001

    def predict(self, state):
        self.ensure_weights(len(state))

        if len(self.weights) != len(state):
            min_dim = min(len(self.weights), len(state))
            raw_dot = np.dot(self.weights[:min_dim], state[:min_dim])
        else:
            raw_dot = np.dot(self.weights, state)

        activated = self._apply_activation(raw_dot)

        if self.kind == "entity":
            novelty_factor = 1.0 / (1.0 + np.sqrt(self.familiarity * 0.5))
            decayed = activated * novelty_factor
            self.activation_history.append(abs(raw_dot))
            self.cluster_activations.append(abs(raw_dot))
            return decayed
        else:
            return activated

    def adapt_learning_rate(self):
        if len(self.prediction_errors) >= 50:
            avg_error = np.mean(self.prediction_errors)
            if avg_error < 0.1:
                self.learning_rate = max(0.001, self.learning_rate * 0.99)
            elif avg_error > 0.5:
                self.learning_rate = min(0.05, self.learning_rate * 1.01)

    def update(self, state, error, gamma_fast=0.5, gamma_slow=0.95, stagnation=0.0):
        self.ensure_weights(len(state))

        if len(self.weights) != len(state):
            min_dim = min(len(self.weights), len(state))
            state = state[:min_dim]
            self.weights = self.weights[:min_dim]

        self.eligibility_fast = gamma_fast * self.eligibility_fast + 1.0
        self.eligibility_slow = gamma_slow * self.eligibility_slow + 1.0

        self.adapt_learning_rate()

        fast_update = 0.7 * self.learning_rate * error * state * self.eligibility_fast
        slow_update = 0.3 * self.learning_rate * error * state * self.eligibility_slow
        self.weights += fast_update + slow_update

        if self.kind == "action":
            if error > 0.01:
                if stagnation > 0.5:
                    self.utility *= 0.97
                elif error > 0.2:
                    self.utility = min(self.utility * 1.02, 2.0)
                else:
                    self.utility *= 0.995

            if self.group == "move":
                self.utility = np.clip(self.utility, 0.1, 2.0)
            else:
                self.utility = np.clip(self.utility, 0.01, 2.0)

        if self.kind == "entity" and len(self.activation_history) > 0:
            recent_avg = np.mean(self.activation_history)
            if recent_avg > 0.1:
                self.familiarity += 0.03

        if self.kind == "entity":
            prediction = self.predict(state)
            self.prediction_errors.append(abs(prediction - error))

        # Record observation for activation fitting
        raw_dot = np.dot(self.weights, state) if len(self.weights) == len(state) else 0.0
        self.activation_observations.append((raw_dot, error))

        # Periodic activation fitting
        self._activation_update_counter += 1
        if self._activation_update_counter >= self.ACTIVATION_FIT_INTERVAL:
            self._activation_update_counter = 0
            self.fit_activation()

    def get_activation_state(self):
        return {
            'active_activation': self.active_activation,
            'fit_score': float(self.activation_fit_score),
            'change_count': self.activation_change_count,
            'observations_count': len(self.activation_observations),
        }

    def set_activation_state(self, state_dict):
        if state_dict is None:
            return
        self.active_activation = state_dict.get('active_activation', 'linear')
        self.activation_fit_score = state_dict.get('fit_score', 0.0)
        self.activation_change_count = state_dict.get('change_count', 0)

    def get_pool_state(self):
        return {
            'pool_id': self.pool_id,
            'layer_index': self.layer_index,
            'trigger_context': self.trigger_context,
        }

    def set_pool_state(self, state_dict):
        if state_dict is None:
            return
        self.pool_id = state_dict.get('pool_id')
        self.layer_index = state_dict.get('layer_index')
        self.trigger_context = state_dict.get('trigger_context')


# ============================================================================
# CONTROL SWAP PERCEPTRON
# ============================================================================

class ControlSwapPerceptron(Perceptron):
    def __init__(self):
        super().__init__(kind="control_swap", chain="shared")
        self.swap_history = deque(maxlen=100)
        self.confidence = 0.0

    def should_swap(self, state, movement_stagnation):
        if self.weights is None:
            return False, 0.0

        self.ensure_weights(len(state))
        swap_score = self.predict(state)
        stagnation_factor = np.tanh(movement_stagnation / 5.0)
        combined_score = swap_score * 0.7 + stagnation_factor * 0.3

        return combined_score > 0.5, abs(combined_score)

    def record_swap_outcome(self, state, swapped, novelty_gained):
        self.swap_history.append((swapped, novelty_gained))

        if len(self.swap_history) >= 20:
            recent = list(self.swap_history)[-20:]
            successful = sum(1 for swap, nov in recent if swap and nov > 0.2)
            self.confidence = successful / 20.0