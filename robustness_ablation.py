"""
Robustness and ablation study for the intelligent offloading layer
==================================================================
1. Robustness : every controller runs closed loop on 11 unseen weeks (new seeds);
                hybrid vs baselines compared with the exact Wilcoxon signed-rank test
2. Ablation A : retrain the ANN predictor with one input removed (validation R²)
3. Ablation B : change one design choice of the hybrid (target, MF tuning, no ANN)
4. ANFIS only : the no-ANN ANFIS controller on the same 11 unseen weeks, vs the hybrid

Uses the project modules unchanged.  Run:  python robustness_ablation.py   (~4 min)
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ann_models as am
import hybrid_offloading as ho

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 20)


def wilcoxon_exact(x, y):
    """Two-sided exact Wilcoxon signed-rank test (zero differences dropped, ties get average ranks)."""
    d = np.asarray(x, float) - np.asarray(y, float)
    d = d[d != 0]
    n = len(d)
    if n == 0:
        return 0.0, 1.0, 0
    ranks = pd.Series(np.abs(d)).rank().to_numpy()
    w_plus = ranks[d > 0].sum()
    total = ranks.sum()
    stat = min(w_plus, total - w_plus)
    count = sum(1 for signs in itertools.product([0, 1], repeat=n)
                if min(s := np.dot(signs, ranks), total - s) <= stat + 1e-9)
    return stat, count / 2 ** n, n


models = ho.train_all()

# ── 1. Robustness: 11 unseen weeks ──────────────────────────────────────────
SEEDS = [7, 11, 23, 99, 2024, 3, 5, 13, 17, 31, 101]
runs = []
for seed in SEEDS:
    table, _ = ho.closed_loop_comparison(models, seed=seed)
    table["seed"] = seed
    runs.append(table)
runs = pd.concat(runs)
metrics = ["Agreement with oracle (%)", "Task energy (J)", "Deadline misses", "Mean regret (cost)"]
print("=== 11 UNSEEN WEEKS: mean ± std ===")
print(runs.groupby("Controller", sort=False)[metrics].agg(["mean", "std"]).round(3).to_string())

piv = {m: runs.pivot(index="seed", columns="Controller", values=m) for m in metrics}
hyb, ann, fz = "⭐ ANN + ANFIS", "🧠 ANN only", "🌫️ Fuzzy only"
print("\n=== WILCOXON SIGNED-RANK (exact, two-sided, n = 11 weeks) ===")
for other in (ann, fz):
    for m in metrics:
        a, b = piv[m][hyb], piv[m][other]
        stat, p, n = wilcoxon_exact(a, b)
        better = (a > b).sum() if m.startswith("Agreement") else (a < b).sum()
        print(f"Hybrid vs {other:14s} {m:27s} hybrid better in {better:2d}/11 weeks · "
              f"mean diff {np.mean(a - b):+8.3f} · W = {stat:5.1f} · p = {p:.4f} (n≠0 = {n})")

# ── 2. Ablation A: ANN predictor inputs ──────────────────────────────────────
train, val = models["train"], models["val"]
FEATURES = ["ln Task_Size", "ln Task_Complexity", "Last_RSSI", "Last_Server_Load", "sin hour", "cos hour"]


def predictor_r2(drop):
    keep = [i for i in range(6) if i not in drop]
    net = am.TinyMLP(n_inputs=len(keep), n_outputs=2, hidden=(24, 16), task="regression", seed=0)
    y_tr, y_va = am.OffloadPredictor._targets(train), am.OffloadPredictor._targets(val)
    net.fit(am.network_features(train)[:, keep], y_tr, am.network_features(val)[:, keep], y_va, epochs=60)
    out = net.predict(am.network_features(val)[:, keep])
    return [ho._r2(y_va[:, k], out[:, k]) for k in (0, 1)]


print("\n=== ABLATION A: ANN predictor inputs (validation R², log space) ===")
for label, drop in [("All 6 inputs (full model)", []), ("− Task_Size", [0]), ("− Task_Complexity", [1]),
                    ("− Last_RSSI", [2]), ("− Last_Server_Load", [3]), ("− hour (sin, cos)", [4, 5])]:
    t, e = predictor_r2(drop)
    print(f"{label:28s} time R² = {t:.3f}   energy R² = {e:.3f}")


# ── 3. Ablation B: hybrid decision layer ─────────────────────────────────────
class Variant(ho.HybridAnnAnfisController):
    """Hybrid with one design choice changed."""

    def __init__(self, name, target="Offload_Preference", epochs=30, features=None):
        super().__init__(models["predictor"])
        self.name, self.target, self.epochs, self.custom = name, target, epochs, features

    def anfis_features(self, inputs):
        return self.custom(inputs) if self.custom else super().anfis_features(inputs)

    def fit(self, train, val, epochs=None):
        self.anfis.fit(self.anfis_features(train), train[self.target].to_numpy(),
                       self.anfis_features(val), val[self.target].to_numpy(), epochs=self.epochs)
        return self


def no_ann_features(inputs):
    """ANFIS fed raw measurements instead of the ANN's predicted offload cost."""
    c = am.col
    return np.column_stack([c(inputs, "SOC"), np.log10(c(inputs, "Local_Energy")),
                            c(inputs, "Last_RSSI"), c(inputs, "Last_Server_Load")])


variants = [
    Variant("Full hybrid (soft target, tuned MFs)"),
    Variant("Hard 0/1 target instead of soft", target="Oracle_Offload"),
    Variant("No MF tuning (least squares only)", epochs=0),
    Variant("No ANN: raw RSSI + local energy", features=no_ann_features),
]
y_val = val["Oracle_Offload"].to_numpy()
rows = []
for v in variants:
    v.fit(train, val)
    acc = 100 * np.mean((v.score(val) > 0.5) == (y_val > 0.5))
    week, _ = ho.closed_loop_comparison({"fuzzy": v, "ann": v, "hybrid": v}, seed=7)
    r = week.iloc[1]
    rows.append({"Variant": v.name, "Val. accuracy (%)": acc, "Agreement (%)": r["Agreement with oracle (%)"],
                 "Task energy (J)": r["Task energy (J)"], "Deadline misses": r["Deadline misses"],
                 "Mean regret": r["Mean regret (cost)"]})
print("\n=== ABLATION B: hybrid decision layer (offline validation + closed loop, unseen week seed 7) ===")
print(pd.DataFrame(rows).round(3).to_string(index=False))

# ── 4. ANFIS on its own (algorithm 3) over the same 11 unseen weeks ─────────
anfis_only = variants[3]                                   # ANFIS fed raw measurements, no ANN
rows = []
for seed in SEEDS:
    week, _ = ho.closed_loop_comparison({"fuzzy": anfis_only, "ann": anfis_only, "hybrid": anfis_only}, seed=seed)
    rows.append({m: week.iloc[1][m] for m in metrics})
alone = pd.DataFrame(rows, index=SEEDS)
print("\n=== 11 UNSEEN WEEKS: 🔗 ANFIS only (no ANN), mean ± std ===")
print(alone.agg(["mean", "std"]).round(3).to_string())
for m in metrics:
    a, b = piv[m][hyb].loc[SEEDS], alone[m]
    stat, p, n = wilcoxon_exact(a, b)
    better = (a > b).sum() if m.startswith("Agreement") else (a < b).sum()
    print(f"Hybrid vs ANFIS only     {m:27s} hybrid better in {better:2d}/11 weeks · "
          f"mean diff {np.mean(a.to_numpy() - b.to_numpy()):+8.3f} · W = {stat:5.1f} · p = {p:.4f} (n≠0 = {n})")
