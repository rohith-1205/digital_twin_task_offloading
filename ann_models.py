"""
🧠 ANN models for the intelligent offloading layer (NumPy only, no ML framework)
================================================================================

Two small neural networks are used:

1. OffloadPredictor  (ANN regressor  → feeds the fuzzy / ANFIS layer)
   Before a task is sent, the ESP32 does NOT know how long offloading will take or
   how much radio energy it will cost: the WiFi link and the edge server keep changing.
   This network PREDICTS those two values from what the node does know:
       task size, task complexity, last measured RSSI, last reported server load, hour
   Outputs: predicted Offload_Total_Time [ms] and Offload_Energy [mJ]

2. AnnOffloadClassifier  (ANN classifier → "ANN only" baseline controller)
   Learns LOCAL / OFFLOAD directly from the same known inputs + battery SOC.
   It is accurate but a black box: it cannot say WHY it chose an option.

Both use the same tiny multilayer perceptron (TinyMLP) defined below.
"""

import numpy as np

T_DEADLINE_MS = 5000.0     # task deadline (same as the twin) [ms]


# ════════════════════════════════════════════════════════════════════════════
# 1. A TINY MULTILAYER PERCEPTRON
# ════════════════════════════════════════════════════════════════════════════
class TinyMLP:
    """
    Fully-connected network:  inputs → [tanh hidden layers] → output
      task = "regression"     : linear output, mean-squared-error loss
      task = "classification" : sigmoid output (probability), cross-entropy loss
    Trained with mini-batch gradient descent + the Adam optimiser.
    Inputs (and regression targets) are standardised internally.
    """

    def __init__(self, n_inputs, n_outputs=1, hidden=(16, 16), task="regression", seed=0):
        self.task = task
        rng = np.random.default_rng(seed)
        sizes = [n_inputs, *hidden, n_outputs]
        # Xavier initialisation: keeps tanh activations in their sensitive range
        self.W = [rng.normal(0, np.sqrt(1.0 / a), (a, b)) for a, b in zip(sizes[:-1], sizes[1:])]
        self.b = [np.zeros(b) for b in sizes[1:]]
        self.history = {"train": [], "val": []}

    # ── forward pass ────────────────────────────────────────────────────────
    def _forward(self, Xs):
        """Return the activations of every layer (needed for back-propagation)."""
        acts = [Xs]
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            z = acts[-1] @ W + b
            last = i == len(self.W) - 1
            if not last:
                acts.append(np.tanh(z))
            elif self.task == "classification":
                acts.append(1.0 / (1.0 + np.exp(-np.clip(z, -30, 30))))
            else:
                acts.append(z)
        return acts

    def _loss(self, out, Ys):
        if self.task == "classification":
            p = np.clip(out, 1e-7, 1 - 1e-7)
            return float(-np.mean(Ys * np.log(p) + (1 - Ys) * np.log(1 - p)))
        return float(np.mean((out - Ys) ** 2))

    # ── training ────────────────────────────────────────────────────────────
    def fit(self, X, Y, X_val=None, Y_val=None, epochs=60, lr=0.01, batch=128, seed=0):
        X = np.asarray(X, float)
        Y = np.asarray(Y, float).reshape(len(X), -1)
        self.x_mean, self.x_std = X.mean(0), X.std(0) + 1e-9
        if self.task == "regression":
            self.y_mean, self.y_std = Y.mean(0), Y.std(0) + 1e-9
        else:
            self.y_mean, self.y_std = np.zeros(Y.shape[1]), np.ones(Y.shape[1])
        Xs, Ys = (X - self.x_mean) / self.x_std, (Y - self.y_mean) / self.y_std

        # Adam optimiser state
        params = self.W + self.b
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        beta1, beta2, step = 0.9, 0.999, 0
        rng = np.random.default_rng(seed)

        for _ in range(epochs):
            order = rng.permutation(len(Xs))
            for start in range(0, len(Xs), batch):
                idx = order[start:start + batch]
                acts = self._forward(Xs[idx])

                # Back-propagation. For both (linear+MSE) and (sigmoid+cross-entropy)
                # the output error is simply (prediction − target).
                delta = (acts[-1] - Ys[idx]) / len(idx)
                grads_W, grads_b = [], []
                for layer in reversed(range(len(self.W))):
                    grads_W.insert(0, acts[layer].T @ delta)
                    grads_b.insert(0, delta.sum(0))
                    if layer > 0:
                        delta = (delta @ self.W[layer].T) * (1 - acts[layer] ** 2)   # tanh'

                step += 1
                for i, (p, g) in enumerate(zip(params, grads_W + grads_b)):
                    m[i] = beta1 * m[i] + (1 - beta1) * g
                    v[i] = beta2 * v[i] + (1 - beta2) * g * g
                    m_hat, v_hat = m[i] / (1 - beta1 ** step), v[i] / (1 - beta2 ** step)
                    p -= lr * m_hat / (np.sqrt(v_hat) + 1e-8)

            self.history["train"].append(self._loss(self._forward(Xs)[-1], Ys))
            if X_val is not None:
                Xv = (np.asarray(X_val, float) - self.x_mean) / self.x_std
                Yv = (np.asarray(Y_val, float).reshape(len(Xv), -1) - self.y_mean) / self.y_std
                self.history["val"].append(self._loss(self._forward(Xv)[-1], Yv))
        return self

    def predict(self, X):
        Xs = (np.atleast_2d(np.asarray(X, float)) - self.x_mean) / self.x_std
        return self._forward(Xs)[-1] * self.y_std + self.y_mean


# ════════════════════════════════════════════════════════════════════════════
# 2. HELPERS: read decision-time inputs from a DataFrame OR a dict of scalars
# ════════════════════════════════════════════════════════════════════════════
def col(inputs, name):
    """inputs[name] as a 1-D float array (works for DataFrames and plain dicts)."""
    return np.atleast_1d(np.asarray(inputs[name], dtype=float))


def network_features(inputs):
    """What the node knows about the task and the link BEFORE offloading."""
    hour = col(inputs, "Hour")
    return np.column_stack([
        np.log(col(inputs, "Task_Size")),             # data to send   (log: spans 4 KB … 1 MB)
        np.log(col(inputs, "Task_Complexity")),       # work per byte  (drives edge processing time)
        col(inputs, "Last_RSSI"),                     # last measured signal strength [dBm]
        col(inputs, "Last_Server_Load"),              # last load reported by the edge [%]
        np.sin(2 * np.pi * hour / 24),                # time of day (WiFi channel is busier by day)
        np.cos(2 * np.pi * hour / 24),
    ])


# ════════════════════════════════════════════════════════════════════════════
# 3. ANN #1 — PREDICTS THE COST OF OFFLOADING
# ════════════════════════════════════════════════════════════════════════════
class OffloadPredictor:
    """ANN regressor:  known inputs  →  predicted offload time [ms] and energy [mJ]."""

    def __init__(self, seed=0):
        self.net = TinyMLP(n_inputs=6, n_outputs=2, hidden=(24, 16), task="regression", seed=seed)

    def fit(self, train, val=None, epochs=60):
        Y = self._targets(train)
        Yv = self._targets(val) if val is not None else None
        Xv = network_features(val) if val is not None else None
        self.net.fit(network_features(train), Y, Xv, Yv, epochs=epochs)
        return self

    @staticmethod
    def _targets(data):
        # Log scale: times range from ~10 ms to seconds, the network learns ratios
        return np.column_stack([np.log(col(data, "Offload_Total_Time")), np.log(col(data, "Offload_Energy"))])

    def predict(self, inputs):
        """Returns (predicted offload time [ms], predicted offload energy [mJ]) as arrays."""
        out = self.net.predict(network_features(inputs))
        return np.exp(out[:, 0]), np.exp(out[:, 1])


# ════════════════════════════════════════════════════════════════════════════
# 4. ANN #2 — "ANN ONLY" DECISION (black-box baseline)
# ════════════════════════════════════════════════════════════════════════════
class AnnOffloadClassifier:
    """ANN classifier: known inputs + SOC + local cost  →  P(OFFLOAD)."""

    name = "🧠 ANN only"

    def __init__(self, seed=1):
        self.net = TinyMLP(n_inputs=9, n_outputs=1, hidden=(24, 16), task="classification", seed=seed)

    @staticmethod
    def _features(inputs):
        return np.column_stack([
            network_features(inputs),
            col(inputs, "SOC"),
            np.log(col(inputs, "Local_Exec_Time")),
            np.log(col(inputs, "Local_Energy")),
        ])

    def fit(self, train, labels, val=None, val_labels=None, epochs=60):
        Xv = self._features(val) if val is not None else None
        self.net.fit(self._features(train), labels, Xv, val_labels, epochs=epochs)
        return self

    def score(self, inputs):
        """Offload score in [0, 1] (here: the predicted probability of OFFLOAD)."""
        return self.net.predict(self._features(inputs))[:, 0]

    def decide(self, inputs):
        return "OFFLOAD" if self.score(inputs)[0] > 0.5 else "LOCAL"
