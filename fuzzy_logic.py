"""
🌫️ Fuzzy logic for task offloading (Mamdani inference, NumPy only)
==================================================================

Humans describe the offloading problem with vague words:
    "the battery is FAIRLY LOW, the signal is OKAY, the server is a BIT BUSY…"
Fuzzy logic turns such words into numbers and reasons with IF–THEN rules.

The 4 steps of a Mamdani fuzzy controller:
    1. FUZZIFY   each crisp input → degree of membership (0..1) in each word
                 e.g. RSSI = −76 dBm → Poor 0.0 · Fair 0.9 · Good 0.2
    2. RULES     AND = minimum of the memberships → firing strength of each rule
    3. AGGREGATE every rule cuts its output set at its strength; take the maximum
    4. DEFUZZIFY centre of gravity of the aggregated shape → offload score 0..1
                 score > 0.5 → OFFLOAD, otherwise LOCAL

This "Fuzzy only" controller uses measured inputs and hand-written expert rules.
It is fully explainable but cannot know the real offload cost, which the ANN predicts.
"""

import numpy as np

from ann_models import col


# ════════════════════════════════════════════════════════════════════════════
# 1. MEMBERSHIP FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════
def trapmf(x, a, b, c, d):
    """Trapezoid: 0 below a, rises to 1 at b, stays 1 until c, falls to 0 at d."""
    x = np.asarray(x, float)
    rise = np.ones_like(x) if b == a else np.clip((x - a) / (b - a), 0, 1)
    fall = np.ones_like(x) if d == c else np.clip((d - x) / (d - c), 0, 1)
    return np.minimum(rise, fall)


def trimf(x, a, b, c):
    """Triangle: peak 1 at b, 0 at a and c."""
    return trapmf(x, a, b, b, c)


class FuzzyVariable:
    """A linguistic variable: a name, a unit, a range and its fuzzy sets (words)."""

    def __init__(self, name, unit, low, high, sets, log_axis=False):
        self.name, self.unit, self.low, self.high = name, unit, low, high
        self.sets = sets                   # {"Low": ("trap", a, b, c, d), "Medium": ("tri", a, b, c)}
        self.log_axis = log_axis

    def membership(self, label, x):
        kind, *p = self.sets[label]
        return trapmf(x, *p) if kind == "trap" else trimf(x, *p)

    def fuzzify(self, x):
        """Crisp value(s) → {label: membership degree array}."""
        return {label: self.membership(label, x) for label in self.sets}


# ════════════════════════════════════════════════════════════════════════════
# 2. THE "FUZZY ONLY" OFFLOADING CONTROLLER
# ════════════════════════════════════════════════════════════════════════════
INF = 1e9

FUZZY_INPUTS = {
    # key in the inputs dict  →  linguistic variable
    "SOC": FuzzyVariable("Battery SOC", "%", 0, 100, {
        "Low":    ("trap", 0, 0, 20, 35),
        "Medium": ("tri", 20, 40, 60),
        "High":   ("trap", 45, 65, 100, 100)}),
    "Local_Exec_Time": FuzzyVariable("Task load", "local execution time (ms)", 1, 20000, {
        "Light":  ("trap", 0, 0, 150, 300),
        "Medium": ("trap", 150, 350, 800, 1600),
        "Heavy":  ("trap", 800, 2000, INF, INF)}, log_axis=True),
    "Last_RSSI": FuzzyVariable("WiFi link", "last RSSI (dBm)", -95, -40, {
        "Poor":   ("trap", -120, -120, -86, -80),
        "Fair":   ("tri", -86, -77, -68),
        "Good":   ("trap", -74, -66, 0, 0)}),
    "Last_Server_Load": FuzzyVariable("Server load", "last edge load (%)", 0, 100, {
        "Light":  ("trap", 0, 0, 30, 50),
        "Busy":   ("tri", 35, 55, 75),
        "Overloaded": ("trap", 60, 80, 100, 100)}),
}

FUZZY_OUTPUT = FuzzyVariable("Offload score", "", 0, 1, {
    "LOCAL":   ("trap", 0, 0, 0.2, 0.45),
    "MAYBE":   ("tri", 0.3, 0.5, 0.7),
    "OFFLOAD": ("trap", 0.55, 0.8, 1, 1)})

# Expert rules:  ({input: word, ...}  joined by AND,  output word)
FUZZY_RULES = [
    ({"Local_Exec_Time": "Light"}, "LOCAL"),                                         # tiny job: radio costs more than CPU
    ({"Local_Exec_Time": "Medium", "Last_RSSI": "Poor"}, "LOCAL"),                   # retransmissions waste energy
    ({"Local_Exec_Time": "Medium", "Last_Server_Load": "Overloaded"}, "LOCAL"),      # edge would be slow
    ({"Local_Exec_Time": "Medium", "Last_Server_Load": "Busy"}, "LOCAL"),            # waiting for the edge costs RX energy
    ({"Local_Exec_Time": "Medium", "Last_Server_Load": "Light", "Last_RSSI": "Good"}, "OFFLOAD"),
    ({"Local_Exec_Time": "Medium", "Last_Server_Load": "Light", "Last_RSSI": "Fair"}, "OFFLOAD"),
    ({"Local_Exec_Time": "Medium", "SOC": "Low", "Last_Server_Load": "Light"}, "OFFLOAD"),  # save the battery
    ({"Local_Exec_Time": "Heavy", "Last_RSSI": "Good"}, "OFFLOAD"),                  # heavy job + good link
    ({"Local_Exec_Time": "Heavy", "Last_RSSI": "Fair"}, "OFFLOAD"),
    ({"Local_Exec_Time": "Heavy", "Last_RSSI": "Poor"}, "MAYBE"),                    # heavy job but bad link
    ({"Local_Exec_Time": "Heavy", "Last_Server_Load": "Overloaded"}, "MAYBE"),       # heavy job but edge saturated
    ({"Local_Exec_Time": "Heavy", "SOC": "Low"}, "OFFLOAD"),                         # local would drain the battery
]


def rule_text(conditions, output):
    parts = [f"{FUZZY_INPUTS[k].name} is {v}" for k, v in conditions.items()]
    return "IF " + " AND ".join(parts) + f"  →  {output}"


class MamdaniOffloadController:
    """Hand-written Mamdani fuzzy controller on measured inputs (the 'Fuzzy only' baseline)."""

    name = "🌫️ Fuzzy only"
    inputs, output, rules = FUZZY_INPUTS, FUZZY_OUTPUT, FUZZY_RULES

    def __init__(self, resolution=101):
        self.universe = np.linspace(0, 1, resolution)                 # output axis for defuzzification
        self.out_sets = {k: self.output.membership(k, self.universe) for k in self.output.sets}

    def firing_strengths(self, data):
        """Step 1 + 2: fuzzify every input and AND (min) the conditions of each rule → (N, rules)."""
        fuzzy = {key: var.fuzzify(col(data, key)) for key, var in self.inputs.items()}
        strengths = [np.minimum.reduce([fuzzy[k][word] for k, word in cond.items()]) for cond, _ in self.rules]
        return np.column_stack(strengths)

    def score(self, data):
        """Steps 3 + 4: clip each rule's output set, aggregate with max, take the centroid."""
        w = self.firing_strengths(data)                                      # (N, R)
        shapes = np.stack([self.out_sets[out] for _, out in self.rules])     # (R, U)
        aggregated = np.max(np.minimum(w[:, :, None], shapes[None]), axis=1)  # (N, U)
        area = aggregated.sum(1)
        centroid = (aggregated * self.universe).sum(1) / np.maximum(area, 1e-12)
        return np.where(area > 0, centroid, 0.5)

    def decide(self, inputs):
        return "OFFLOAD" if self.score(inputs)[0] > 0.5 else "LOCAL"

    def explain(self, inputs):
        """Fired rules for ONE input, strongest first: [(rule text, strength)]."""
        w = self.firing_strengths(inputs)[0]
        fired = [(rule_text(c, o), float(s)) for (c, o), s in zip(self.rules, w) if s > 0]
        return sorted(fired, key=lambda r: -r[1])
