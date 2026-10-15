"""
🔗 ANFIS — Adaptive Neuro-Fuzzy Inference System (NumPy only)
=============================================================

ANFIS is a fuzzy system that is trained like a neural network:
    • it keeps fuzzy IF–THEN rules  (readable, like the Mamdani controller)
    • the SHAPES of its membership functions and the rule OUTPUTS are LEARNED from data

It is a 5-layer network (first-order Takagi–Sugeno model):

    Layer 1  Fuzzification   μ(x) = exp(−(x − c)² / 2σ²)        ← c, σ are learned (premise)
    Layer 2  Rule strength   w_r  = Π μ                         (AND = product)
    Layer 3  Normalisation   w̄_r  = w_r / Σ w
    Layer 4  Rule output     f_r  = p_r·x + q_r                 ← p, q are learned (consequent)
    Layer 5  Output          y    = Σ w̄_r · f_r                 (offload score)

Hybrid learning (Jang, 1993), repeated every epoch:
    forward  pass: premise fixed  → consequents solved exactly by least squares
    backward pass: consequents fixed → c and σ updated by gradient descent
"""

import itertools

import numpy as np


class ANFIS:
    def __init__(self, input_names, mf_labels, ridge=1e-3):
        """
        input_names : display names of the inputs
        mf_labels   : one list of words per input, ordered from low to high values,
                      e.g. [["Low", "Medium", "High"], ["Cheaper", "Similar", "Dearer"], ...]
        Rules = every combination of one word per input (grid partition).
        """
        self.input_names, self.mf_labels, self.ridge = input_names, mf_labels, ridge
        self.n = len(input_names)
        self.rules = np.array(list(itertools.product(*[range(len(l)) for l in mf_labels])))  # (R, n)
        self.history = {"train_mse": [], "val_mse": [], "train_acc": [], "val_acc": []}

    # ── layers 1–3 ──────────────────────────────────────────────────────────
    def _standardise(self, X):
        """Scale inputs; values outside the training range are clipped (no wild extrapolation)."""
        X = np.clip(np.atleast_2d(np.asarray(X, float)), self.x_min, self.x_max)
        return (X - self.x_mean) / self.x_std

    def memberships(self, Xs):
        """Layer 1: list (one per input) of (N, M_i) Gaussian membership degrees."""
        return [np.exp(-0.5 * ((Xs[:, [i]] - self.c[i]) / self.s[i]) ** 2) for i in range(self.n)]

    def _strengths(self, Xs):
        """Layers 2–3: rule strengths w (N, R) and normalised strengths w̄."""
        mu = self.memberships(Xs)
        w = np.ones((len(Xs), len(self.rules)))
        for i in range(self.n):
            w *= mu[i][:, self.rules[:, i]]
        total = w.sum(1, keepdims=True) + 1e-12
        return w, w / total, total[:, 0]

    # ── layers 4–5 ──────────────────────────────────────────────────────────
    def _rule_outputs(self, Xs):
        """Layer 4: f_r = p_r · x + q_r for every rule → (N, R)."""
        Xa = np.column_stack([Xs, np.ones(len(Xs))])
        return Xa @ self.theta.reshape(len(self.rules), self.n + 1).T

    def _solve_consequents(self, Xs, y, w_bar):
        """Forward pass of hybrid learning: ridge least squares for all p, q at once."""
        Xa = np.column_stack([Xs, np.ones(len(Xs))])
        Phi = (w_bar[:, :, None] * Xa[:, None, :]).reshape(len(Xs), -1)    # (N, R·(n+1))
        A = Phi.T @ Phi + self.ridge * np.eye(Phi.shape[1])
        self.theta = np.linalg.solve(A, Phi.T @ y)

    def _raw_output(self, Xs):
        w, w_bar, _ = self._strengths(Xs)
        return (w_bar * self._rule_outputs(Xs)).sum(1)

    # ── training ────────────────────────────────────────────────────────────
    def fit(self, X, y, X_val=None, y_val=None, epochs=30, lr=30.0):
        X, y = np.asarray(X, float), np.asarray(y, float)
        self.x_mean, self.x_std = X.mean(0), X.std(0) + 1e-9
        self.x_min, self.x_max = X.min(0), X.max(0)
        Xs = self._standardise(X)

        # Initial membership functions: evenly spread over each input's range
        self.c, self.s = [], []
        for i, labels in enumerate(self.mf_labels):
            lo, hi = np.percentile(Xs[:, i], [5, 95])
            centres = np.linspace(lo, hi, len(labels))
            self.c.append(centres)
            self.s.append(np.full(len(labels), (hi - lo) / (2 * (len(labels) - 1))))

        for _ in range(epochs):
            # Forward pass: membership functions fixed → best consequents by least squares
            w, w_bar, total = self._strengths(Xs)
            self._solve_consequents(Xs, y, w_bar)
            f = self._rule_outputs(Xs)
            y_hat = (w_bar * f).sum(1)
            self._log(y, y_hat, X_val, y_val)

            # Backward pass: consequents fixed → gradient of the MSE w.r.t. c and σ
            err = 2 * (y_hat - y) / len(y)
            G = err[:, None] * (f - y_hat[:, None]) / total[:, None] * w      # ∂E/∂w_r · w_r   (N, R)
            for i in range(self.n):
                for j in range(len(self.c[i])):
                    g = G[:, self.rules[:, i] == j].sum(1)                     # rules that use word j
                    d = Xs[:, i] - self.c[i][j]
                    grad_c = np.sum(g * d / self.s[i][j] ** 2)
                    grad_s = np.sum(g * d ** 2 / self.s[i][j] ** 3)
                    self.c[i][j] -= lr * grad_c
                    self.s[i][j] = max(0.15, self.s[i][j] - lr * grad_s)

        # Final least-squares fit with the tuned membership functions
        _, w_bar, _ = self._strengths(Xs)
        self._solve_consequents(Xs, y, w_bar)
        self._log(y, self._raw_output(Xs), X_val, y_val)
        return self

    def _log(self, y, y_hat, X_val, y_val):
        self.history["train_mse"].append(float(np.mean((y_hat - y) ** 2)))
        self.history["train_acc"].append(float(np.mean((y_hat > 0.5) == (y > 0.5))))
        if X_val is not None:
            yv_hat = self._raw_output(self._standardise(X_val))
            self.history["val_mse"].append(float(np.mean((yv_hat - y_val) ** 2)))
            self.history["val_acc"].append(float(np.mean((yv_hat > 0.5) == (np.asarray(y_val) > 0.5))))

    # ── use ─────────────────────────────────────────────────────────────────
    def predict(self, X):
        """Offload score, clipped to [0, 1]."""
        return np.clip(self._raw_output(self._standardise(X)), 0, 1)

    def membership_curve(self, i, x_values):
        """Learned membership functions of input i on the ORIGINAL scale (for plots)."""
        xs = (np.asarray(x_values, float) - self.x_mean[i]) / self.x_std[i]
        return {label: np.exp(-0.5 * ((xs - c) / s) ** 2)
                for label, c, s in zip(self.mf_labels[i], self.c[i], self.s[i])}

    def rule_text(self, r):
        """e.g. 'SOC=Low · Energy=Offload cheaper · Time gain=Small · Server=Light'  (· means AND)"""
        return " · ".join(f"{name}={labels[k]}" for name, labels, k
                          in zip(self.input_names, self.mf_labels, self.rules[r]))

    def rule_table(self, X, top=None):
        """
        Learned rule base summarised on data X:
          usage   = share of the total firing strength this rule receives
          output  = its average offload score when it fires → LOCAL / OFFLOAD
        """
        Xs = self._standardise(X)
        _, w_bar, _ = self._strengths(Xs)
        f = self._rule_outputs(Xs)
        usage = w_bar.sum(0)
        out = (w_bar * f).sum(0) / np.maximum(usage, 1e-12)
        order = np.argsort(-usage)[:top]
        return [{"rule": f"R{r + 1}", "IF (· = AND)": self.rule_text(r),
                 "THEN": "OFFLOAD" if out[r] > 0.5 else "LOCAL",
                 "score": float(np.clip(out[r], 0, 1)), "usage_%": float(100 * usage[r] / usage.sum())}
                for r in order]

    def explain(self, x, top=5):
        """For ONE input: the strongest rules and how much each one contributed."""
        Xs = self._standardise(x)
        _, w_bar, _ = self._strengths(Xs)
        f = self._rule_outputs(Xs)[0]
        order = np.argsort(-w_bar[0])[:top]
        return [(self.rule_text(r), float(w_bar[0, r]), float(np.clip(f[r], 0, 1))) for r in order]
