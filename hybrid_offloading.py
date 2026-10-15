"""
⭐ Hybrid ANN + Fuzzy (ANFIS) decision layer for task offloading
================================================================

The physics engine (digital_twin_simulator.py) can compare the EXACT cost of LOCAL and
OFFLOAD because it knows everything. A real ESP32 does not: before sending a task it
cannot know the real network latency, the radio energy or how busy the edge will be.
This module builds decision makers that only use what the node knows, and grades them
against the exact comparison (the "oracle").

    ┌──────────────┐  predicted offload    ┌───────────────────┐  offload   ┌──────────┐
    │ 🧠 ANN       │  time + energy  ───►  │ 🔗 ANFIS          │  score ──► │ LOCAL /  │
    │ (predictor)  │                       │ (neuro-fuzzy      │   0..1     │ OFFLOAD  │
    └──────▲───────┘   SOC, server load ─► │  rule base)       │            └──────────┘
           │ task size, complexity,        └───────────────────┘
           │ last RSSI, last server load, hour

Four controllers are compared:
    🎯 Oracle          exact cost comparison with perfect knowledge (upper bound)
    🌫️ Fuzzy only      hand-written Mamdani rules on measured inputs
    🧠 ANN only        neural network classifier (black box)
    ⭐ ANN + ANFIS     ANN predictions → learned fuzzy rules (accurate AND explainable)

Run:  python hybrid_offloading.py
"""

import os
import time

import numpy as np
import pandas as pd

from anfis import ANFIS
from ann_models import T_DEADLINE_MS, AnnOffloadClassifier, OffloadPredictor, col
from digital_twin_simulator import DiagnosedIoTDigitalTwin
from fuzzy_logic import MamdaniOffloadController

PREFERENCE_SCALE = 0.25      # cost difference that counts as a "clear" preference

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "simulation_dataset.csv")


# ════════════════════════════════════════════════════════════════════════════
# 1. DECISION-TIME INPUTS  (only what the ESP32 knows when the task arrives)
# ════════════════════════════════════════════════════════════════════════════
def decision_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert dataset rows into decision-time inputs.
      SOC          : the dataset stores SOC AFTER the step, so subtract this step's change
      Last_RSSI    : RSSI measured during the PREVIOUS task (the current one is not known yet)
      Last_Server_Load: load reported by the edge with the PREVIOUS result
    The true offload time / energy and the oracle label are kept for training and grading.
    """
    return pd.DataFrame({
        "Hour": df["Hour"],
        "SOC": df["Battery_SOC"] - df["dSOC_dt"],
        "Solar_Power": df["Renewable_Power"],
        "Task_Size": df["Task_Size"],
        "Task_Complexity": df["Task_Complexity"],
        "Local_Exec_Time": df["Local_Exec_Time"],
        "Local_Energy": df["Local_Energy"],
        "Last_RSSI": df["RSSI"].shift(1).fillna(df["RSSI"]),
        "Last_Server_Load": df["Server_CPU_Load"].shift(1).fillna(df["Server_CPU_Load"]),
        # ground truth (NOT available to the controllers when deciding)
        "Offload_Total_Time": df["Offload_Total_Time"],
        "Offload_Energy": df["Offload_Energy"],
        "Oracle_Offload": (df["Decision"] == "OFFLOAD").astype(float),
        # Soft teaching signal for ANFIS: 0.5 ± how clearly one option is cheaper
        #   1 = OFFLOAD clearly cheaper, 0 = LOCAL clearly cheaper, 0.5 = tie
        "Offload_Preference": 0.5 + 0.5 * np.tanh(
            (df["Local_Execution_Cost"] - df["Offload_Execution_Cost"]) / PREFERENCE_SCALE),
    })


def inputs_from_records(previous: dict, current: dict) -> dict:
    """Decision-time inputs for ONE live step (previous record gives the last RSSI / server load)."""
    prev = previous or current
    return {
        "Hour": current["Hour"], "SOC": current["Battery_SOC"] - current["dSOC_dt"],
        "Solar_Power": current["Renewable_Power"],
        "Task_Size": current["Task_Size"], "Task_Complexity": current["Task_Complexity"],
        "Local_Exec_Time": current["Local_Exec_Time"], "Local_Energy": current["Local_Energy"],
        "Last_RSSI": prev["RSSI"], "Last_Server_Load": prev["Server_CPU_Load"],
    }


# ════════════════════════════════════════════════════════════════════════════
# 2. THE HYBRID CONTROLLER:  ANN predictor  →  ANFIS
# ════════════════════════════════════════════════════════════════════════════
ANFIS_INPUTS = ["Battery SOC", "Energy ratio", "Time gain", "Server load"]
ANFIS_SHORT = ["SOC", "Energy", "Time gain", "Server"]          # short names used in rule texts
ANFIS_LABELS = [
    ["Low", "Medium", "High"],                              # SOC [%]
    ["Offload cheaper", "Similar", "Local cheaper"],        # log10(E_offload_pred / E_local)
    ["Small", "Large"],                                     # (T_local − T_offload_pred) / deadline [%]
    ["Light", "Busy"],                                      # last edge load [%]
]
ANFIS_UNITS = ["%", "log₁₀(E_off / E_loc)", "% of deadline", "%"]


class HybridAnnAnfisController:
    """⭐ The ANN predicts what offloading will cost; ANFIS fuzzy rules turn that into a decision."""

    name = "⭐ ANN + ANFIS"

    def __init__(self, predictor: OffloadPredictor):
        self.predictor = predictor
        self.anfis = ANFIS(ANFIS_SHORT, ANFIS_LABELS)

    def anfis_features(self, inputs):
        """Build the 4 ANFIS inputs. Energy ratio and time gain come from the ANN prediction."""
        t_off, e_off = self.predictor.predict(inputs)
        return np.column_stack([
            col(inputs, "SOC"),
            np.log10(e_off / col(inputs, "Local_Energy")),
            100.0 * (col(inputs, "Local_Exec_Time") - t_off) / T_DEADLINE_MS,
            col(inputs, "Last_Server_Load"),
        ])

    def fit(self, train, val, epochs=30):
        # Trained on the ANN's PREDICTIONS (not the true values), so the rules learn to
        # live with the ANN's errors. Target: the soft oracle preference (0 = LOCAL … 1 = OFFLOAD).
        self.anfis.fit(self.anfis_features(train), train["Offload_Preference"].to_numpy(),
                       self.anfis_features(val), val["Offload_Preference"].to_numpy(), epochs=epochs)
        return self

    def score(self, inputs):
        return self.anfis.predict(self.anfis_features(inputs))

    def decide(self, inputs):
        return "OFFLOAD" if self.score(inputs)[0] > 0.5 else "LOCAL"

    def explain(self, inputs, top=5):
        """Everything the dashboard shows for one decision."""
        t_off, e_off = self.predictor.predict(inputs)
        x = self.anfis_features(inputs)
        return {"pred_time_ms": float(t_off[0]), "pred_energy_mJ": float(e_off[0]),
                "features": x[0], "score": float(self.anfis.predict(x)[0]),
                "rules": self.anfis.explain(x, top=top)}


# ════════════════════════════════════════════════════════════════════════════
# 3. TRAINING  (dataset of 10,080 oracle decisions, chronological 80 / 20 split)
# ════════════════════════════════════════════════════════════════════════════
def _r2(y, y_hat):
    return float(1 - np.sum((y - y_hat) ** 2) / np.sum((y - y.mean()) ** 2))


def train_all(df: pd.DataFrame = None, epochs=60) -> dict:
    """Train ANN predictor, ANN classifier and ANFIS; build the Mamdani controller. Returns a dict."""
    if df is None:
        df = pd.read_csv(CSV_PATH)
    data = decision_inputs(df)
    split = int(0.8 * len(data))
    train, val = data.iloc[:split], data.iloc[split:]
    y_train, y_val = train["Oracle_Offload"].to_numpy(), val["Oracle_Offload"].to_numpy()

    predictor = OffloadPredictor(seed=0).fit(train, val, epochs=epochs)
    ann = AnnOffloadClassifier(seed=1).fit(train, y_train, val, y_val, epochs=epochs)
    hybrid = HybridAnnAnfisController(predictor).fit(train, val)
    fuzzy = MamdaniOffloadController()

    # Offline quality on the validation days (never seen during training)
    t_pred, e_pred = predictor.predict(val)
    offline = pd.DataFrame([
        {"Controller": c.name, "Validation accuracy vs oracle (%)": 100 * np.mean((c.score(val) > 0.5) == (y_val > 0.5))}
        for c in (fuzzy, ann, hybrid)])
    predictor_quality = {
        "time_r2": _r2(np.log(val["Offload_Total_Time"].to_numpy()), np.log(t_pred)),
        "energy_r2": _r2(np.log(val["Offload_Energy"].to_numpy()), np.log(e_pred)),
        "time_mape": float(100 * np.median(np.abs(t_pred / val["Offload_Total_Time"] - 1))),
        "energy_mape": float(100 * np.median(np.abs(e_pred / val["Offload_Energy"] - 1))),
    }
    return {"predictor": predictor, "ann": ann, "fuzzy": fuzzy, "hybrid": hybrid,
            "train": train, "val": val, "offline": offline, "predictor_quality": predictor_quality}


# ════════════════════════════════════════════════════════════════════════════
# 4. CLOSED-LOOP COMPARISON on unseen days (each controller drives the battery)
# ════════════════════════════════════════════════════════════════════════════
class _TimedController:
    """Wraps a controller to measure how long one decision takes."""

    def __init__(self, controller):
        self.controller, self.seconds, self.calls = controller, 0.0, 0

    def decide(self, inputs):
        start = time.perf_counter()
        decision = self.controller.decide(inputs)
        self.seconds += time.perf_counter() - start
        self.calls += 1
        return decision


def closed_loop_comparison(models: dict, seed=7, days=7, initial_soc=25.0):
    """
    Run the same unseen week (new random seed) once per controller. The chosen action's
    REAL energy drains the battery, so a bad decision changes every later decision.
    Returns (summary table, per-step SOC traces).
    """
    controllers = {"🎯 Oracle": None, "🌫️ Fuzzy only": models["fuzzy"],
                   "🧠 ANN only": models["ann"], "⭐ ANN + ANFIS": models["hybrid"]}
    rows, soc_traces = [], {}
    for name, controller in controllers.items():
        twin = DiagnosedIoTDigitalTwin(seed=seed, initial_soc=initial_soc)
        timed = _TimedController(controller) if controller else None
        run = pd.DataFrame([twin.step(timed) for _ in range(days * 1440)])
        if "Oracle_Decision" not in run:
            run["Oracle_Decision"] = run["Decision"]

        off = run["Decision"] == "OFFLOAD"
        energy_mj = np.where(off, run["Offload_Energy"], run["Local_Energy"])
        time_ms = np.where(off, run["Offload_Total_Time"], run["Local_Exec_Time"])
        cost = np.where(off, run["Offload_Execution_Cost"], run["Local_Execution_Cost"])
        best = np.minimum(run["Offload_Execution_Cost"], run["Local_Execution_Cost"])
        soc_traces[name] = run["Battery_SOC"].to_numpy()
        rows.append({
            "Controller": name,
            "Agreement with oracle (%)": 100 * np.mean(run["Decision"] == run["Oracle_Decision"]),
            "OFFLOAD share (%)": 100 * off.mean(),
            "Task energy (J)": energy_mj.sum() / 1000,
            "Mean task time (ms)": time_ms.mean(),
            "Deadline misses": int((time_ms > T_DEADLINE_MS).sum()),
            "Min SOC (%)": run["Battery_SOC"].min(),
            "Final SOC (%)": run["Battery_SOC"].iloc[-1],
            "Mean regret (cost)": float(np.mean(cost - best)),
            "Decision time (µs)": 1e6 * timed.seconds / timed.calls if timed else np.nan,
        })
    return pd.DataFrame(rows), pd.DataFrame(soc_traces)


# ════════════════════════════════════════════════════════════════════════════
# 5. COMMAND LINE REPORT
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    start = time.time()
    models = train_all()
    q = models["predictor_quality"]
    print("=" * 78)
    print(f"TRAINING DONE in {time.time() - start:.1f} s")
    print("=" * 78)
    print(f"🧠 ANN predictor (validation): offload time R² = {q['time_r2']:.3f} "
          f"(median error {q['time_mape']:.1f} %), energy R² = {q['energy_r2']:.3f} "
          f"(median error {q['energy_mape']:.1f} %)")
    print(models["offline"].round(2).to_string(index=False))

    print("\n🔗 Most used learned ANFIS rules:")
    for r in models["hybrid"].anfis.rule_table(models["val"].pipe(models["hybrid"].anfis_features), top=8):
        print(f"  {r['rule']:>4}  IF {r['IF (· = AND)']}  →  {r['THEN']} (score {r['score']:.2f}, usage {r['usage_%']:.1f} %)")

    print("\n🏆 Closed-loop comparison on an UNSEEN week (seed 7):")
    summary, _ = closed_loop_comparison(models)
    print(summary.round(2).to_string(index=False))
    print("=" * 78)
