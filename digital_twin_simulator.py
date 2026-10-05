"""
Renewable-Aware IoT Task Offloading — Digital Twin Engine
=========================================================

Physical system that is mirrored by this twin:

    SOLAR PV  ->  BATTERY  ->  ESP32 IoT NODE  ->  WiFi (MQTT)  ->  EDGE SERVER

Every simulation step represents Δt = 60 s. In each step:

    1. The environment evolves      (sun position, clouds, weather, server traffic, node position)
    2. One IoT monitoring task arrives (type, data size, computational complexity)
    3. Both execution options are evaluated with physical models:
         LOCAL   -> CPU cycles / ESP32 clock  -> time  -> energy
         OFFLOAD -> bytes / WiFi data rate    -> time  -> radio energy, + edge processing time
    4. A cost J is computed for each option; the cheaper one is chosen
    5. The energy of the CHOSEN option is drawn from the battery (closed loop)

Randomness only enters through physical, exogenous processes (clouds, shadowing,
task arrivals, server traffic). No noise is ever added to costs or to the decision.

Run directly to generate `simulation_dataset.csv` (7 days) and `web_data.js`
(the same data, packaged for the web viewer in index.html):

    python digital_twin_simulator.py
"""

import json
import math
import os

import numpy as np
import pandas as pd

# ════════════════════════════════════════════════════════════════════════════
# 1. MODEL PARAMETERS  (all physical constants live here, with their units)
# ════════════════════════════════════════════════════════════════════════════
DT_S = 60.0                     # simulation time step [s]  (1 step = 1 minute)

# ── Solar PV ────────────────────────────────────────────────────────────────
P_RATED_W = 1.0                 # rated PV power at STC (small 6 V / 1 W IoT panel) [W]
G_STC = 1000.0                  # standard test condition irradiance [W/m²]
G_CLEAR_PEAK = 1000.0           # clear-sky irradiance at solar noon [W/m²]
ETA_PV = 0.85                   # PV derating: temperature, dust, MPPT losses [-]
SUNRISE_H, SUNSET_H = 6.0, 18.0 # [hour of day]

# Daily weather: mean cloud transmittance k̄ and a Markov chain between day types
WEATHER_TYPES = ["Sunny", "Partly Cloudy", "Overcast"]
WEATHER_MEAN_K = {"Sunny": 0.85, "Partly Cloudy": 0.60, "Overcast": 0.30}
WEATHER_TRANSITION = {           # P(tomorrow | today)
    "Sunny":         [0.60, 0.30, 0.10],
    "Partly Cloudy": [0.35, 0.40, 0.25],
    "Overcast":      [0.25, 0.40, 0.35],
}
CLOUD_REVERSION = 0.03          # how fast cloud factor returns to the daily mean [1/step]
CLOUD_SIGMA = 0.03              # minute-to-minute cloud variation [-]

# ── Battery (Li-ion energy storage) ────────────────────────────────────────
E_BAT_WH = 12.0                 # usable battery energy (e.g. 1S3P 18650 pack) [Wh]
E_BAT_J = E_BAT_WH * 3600.0     # [J]
ETA_CHARGE = 0.95               # charging efficiency [-]
ETA_DISCHARGE = 0.95            # discharging efficiency [-]
CV_TAPER_SOC = 90.0             # above this SOC the charger enters CV mode [%]
CV_TAPER_FACTOR = 0.60          # charge current is reduced to 60 % in CV mode [-]
SELF_DISCHARGE_PCT = 0.0001     # self-discharge per step [%/min]  (≈ 4 %/month)

# ── ESP32 IoT node ──────────────────────────────────────────────────────────
F_CPU_HZ = 240e6                # ESP32 core clock [cycles/s]
P_BASE_W = 0.14                 # always-on load: sensors + WiFi association (modem-sleep) [W]
P_CPU_IDLE_W = 0.10             # CPU awake at 240 MHz, radio off (~30 mA @ 3.3 V) [W]
ALPHA_CPU_W = 0.0012            # extra CPU power per % utilisation [W/%] (100 % -> ~0.22 W)
T_DEADLINE_S = 5.0              # result must be ready within this time [s]
BACKGROUND_MEAN = 12.0          # RTOS + WiFi stack + sensor sampling load [%]

# IoT monitoring task catalogue:  complexity [CPU cycles/byte], mean data size [KB]
TASK_TYPES = {
    "Sensor Aggregation":  {"cycles_per_byte": 60,   "mean_kb": 40},
    "Signal Filtering":    {"cycles_per_byte": 250,  "mean_kb": 80},
    "FFT Feature Extract": {"cycles_per_byte": 800,  "mean_kb": 160},
    "Anomaly Detection":   {"cycles_per_byte": 1800, "mean_kb": 160},
    "Image Preprocessing": {"cycles_per_byte": 3000, "mean_kb": 300},
}
TASK_TYPE_PERSISTENCE = 0.90    # probability that the next task is of the same type [-]
TASK_SIZE_MIN_KB, TASK_SIZE_MAX_KB = 4.0, 1024.0
RESULT_SIZE_KB = 1.0            # result returned by the edge (features / anomaly score) [KB]

# ── WiFi link (IEEE 802.11n, 2.4 GHz) ──────────────────────────────────────
RSSI_0_DBM = -40.0              # RSSI measured at reference distance d0 [dBm]
D0_M = 1.0                      # reference distance [m]
PATH_LOSS_N = 2.6               # path-loss exponent (indoor / industrial) [-]
SHADOW_SIGMA_DB = 4.0           # log-normal shadowing std-dev [dB]
SHADOW_CORR = 0.95              # step-to-step correlation of shadowing [-]
FAST_FADE_SIGMA_DB = 1.5        # small-scale fading std-dev [dB]
DIST_MEAN_M, DIST_MIN_M, DIST_MAX_M = 18.0, 3.0, 40.0

# 802.11n HT20 rate adaptation: (MCS, PHY rate [Mbps], receiver sensitivity [dBm])
# Sensitivities approximate the ESP32 datasheet values.
MCS_TABLE = [
    (7, 65.0, -72.0), (6, 58.5, -74.0), (5, 52.0, -77.0), (4, 39.0, -80.0),
    (3, 26.0, -83.0), (2, 19.5, -86.0), (1, 13.0, -88.0), (0, 6.5, -91.0),
]
ETA_MAC = 0.35                  # PHY -> application (TCP/MQTT) throughput efficiency [-]
PER_SLOPE = 0.7                 # PER sharpness vs. SNR margin [1/dB]  (PER = 10 % at sensitivity)
RETRY_LIMIT = 7                 # 802.11 maximum transmission attempts [-]
MSS_BYTES = 1460                # TCP maximum segment size [B]
HEADER_BYTES_PER_SEG = 40       # TCP + IP headers per segment [B]
MQTT_HEADER_BYTES = 20          # MQTT PUBLISH fixed + variable header (topic) [B]
T_GATEWAY_S = 0.003             # gateway forwarding + MQTT broker processing [s]
T_CONTENTION_S = 0.004          # mean channel access time at zero load [s]
P_TX_W = 0.60                   # ESP32 radio transmit power draw (~180 mA @ 3.3 V) [W]
P_RX_W = 0.33                   # ESP32 radio receive / listen power draw (~100 mA) [W]

# ── Edge server ─────────────────────────────────────────────────────────────
F_EDGE_HZ = 3.0e9               # CPU capacity allocated to IoT tasks (1 vCPU @ 3 GHz) [cycles/s]
SERVER_LOAD_MAX = 97.0          # utilisation is kept below 100 % (stable queue) [%]
BURST_PROBABILITY = 0.02        # chance per step that a traffic burst starts [-]

# ── Decision cost function ──────────────────────────────────────────────────
E_REF_J = 1.0                   # energy normalisation: ~ solar energy surplus per task [J]
K_BATTERY_RISK = 4.0            # how strongly a low SOC raises the price of energy [-]
W_ENERGY = 1.0                  # weight of (battery-priced) energy
W_TIME = 1.0                    # weight of completion time (relative to the deadline)
W_NETWORK = 0.3                 # extra reliability risk of a lossy link (its time / energy are already counted)
W_SERVER = 0.3                  # weight of edge congestion risk
W_DEADLINE = 2.0                # penalty when the option misses the task deadline


# ════════════════════════════════════════════════════════════════════════════
# 2. SUB-MODELS  (small pure functions -> easy to read, test and explain)
# ════════════════════════════════════════════════════════════════════════════
def clear_sky_irradiance(hour: float) -> float:
    """Clear-sky irradiance G_clear(t) [W/m²]: half-sine between sunrise and sunset, 0 at night."""
    if hour <= SUNRISE_H or hour >= SUNSET_H:
        return 0.0
    phase = (hour - SUNRISE_H) / (SUNSET_H - SUNRISE_H)
    return G_CLEAR_PEAK * math.sin(math.pi * phase)


def pv_power(irradiance: float) -> float:
    """P_PV = P_rated · G / G_STC · η_PV   [W]"""
    return P_RATED_W * irradiance / G_STC * ETA_PV


def update_soc(soc: float, p_pv: float, p_load: float):
    """
    Discrete battery energy balance (SOC in %):
        P_net = P_PV − P_load
        P_net > 0 :  SOC += η_c · P_charge · Δt / E_bat        (CV taper above 90 %)
        P_net < 0 :  SOC −= P_discharge · Δt / (η_d · E_bat)
    Returns (new_soc, accepted charge power [W], discharge power [W]).
    """
    p_net = p_pv - p_load
    p_charge = max(0.0, p_net)
    p_discharge = max(0.0, -p_net)
    if soc >= CV_TAPER_SOC:
        p_charge *= CV_TAPER_FACTOR          # CC/CV charging: current tapers near full
    if soc >= 100.0:
        p_charge = 0.0                       # battery full: surplus PV is curtailed

    d_soc = (ETA_CHARGE * p_charge * DT_S / E_BAT_J
             - p_discharge * DT_S / (ETA_DISCHARGE * E_BAT_J)) * 100.0
    d_soc -= SELF_DISCHARGE_PCT
    new_soc = min(100.0, max(0.0, soc + d_soc))
    return new_soc, p_charge, p_discharge


def rssi_from_distance(distance_m: float, shadowing_db: float, fading_db: float) -> float:
    """Log-distance path loss:  RSSI(d) = RSSI_0 − 10·n·log10(d/d0) + X_σ   [dBm]"""
    return RSSI_0_DBM - 10.0 * PATH_LOSS_N * math.log10(distance_m / D0_M) + shadowing_db + fading_db


def wifi_link(rssi: float):
    """
    802.11n rate adaptation + packet errors.
      1. Choose the fastest MCS whose receiver sensitivity is below the RSSI.
      2. PER from the SNR margin above that sensitivity (PER = 10 % at the sensitivity limit).
      3. Expected transmissions per packet  N_tx = 1 / (1 − PER), capped at the retry limit.
    Returns (mcs, phy_rate_mbps, per, n_tx).
    """
    mcs, phy_rate, sensitivity = MCS_TABLE[-1]           # fall back to the most robust MCS
    for entry in MCS_TABLE:
        if rssi >= entry[2]:
            mcs, phy_rate, sensitivity = entry
            break
    margin_db = rssi - sensitivity
    per = 1.0 / (1.0 + 9.0 * math.exp(PER_SLOPE * margin_db))
    n_tx = min(1.0 / (1.0 - per), RETRY_LIMIT)
    return mcs, phy_rate, per, n_tx


def bytes_on_air(payload_bytes: float) -> float:
    """Application payload + MQTT header + TCP/IP header per segment [B]."""
    segments = math.ceil((payload_bytes + MQTT_HEADER_BYTES) / MSS_BYTES)
    return payload_bytes + MQTT_HEADER_BYTES + segments * HEADER_BYTES_PER_SEG


def battery_price(soc: float) -> float:
    """Battery-risk price of energy:  λ(SOC) = 1 + K·(1 − SOC/100)^1.5   (rises as SOC falls)."""
    return 1.0 + K_BATTERY_RISK * (1.0 - soc / 100.0) ** 1.5


def wifi_channel_utilisation(hour: float) -> float:
    """Share of airtime used by other WiFi devices (busier during working hours) [0..1]."""
    busy = max(0.0, math.sin(math.pi * (hour - 7.0) / 14.0)) if 7.0 < hour < 21.0 else 0.0
    return 0.15 + 0.35 * busy


def evaluate_options(size_kb: float, cycles_per_byte: float, background: float, rssi: float,
                     channel_util: float, server_load: float, soc: float) -> dict:
    """
    Physical model of BOTH execution options for one task, plus their costs.
    Pure function: the same inputs always give the same outputs (used by the twin
    and by the validation script for controlled what-if experiments).
    """
    size_bytes = size_kb * 1024.0
    cpu_cycles = size_bytes * cycles_per_byte                                 # C_required = D · c

    # LOCAL: ESP32 executes the task
    cpu_load = min(100.0, background + 100.0 * cpu_cycles / (F_CPU_HZ * T_DEADLINE_S))
    t_local = cpu_cycles / (F_CPU_HZ * (1.0 - background / 100.0))           # [s]
    e_local = (P_CPU_IDLE_W + ALPHA_CPU_W * cpu_load) * t_local               # E_local [J]

    # OFFLOAD: WiFi uplink (MQTT publish) -> gateway -> edge server -> result back
    mcs, phy_rate, per, n_tx = wifi_link(rssi)
    data_rate_bps = phy_rate * 1e6 * ETA_MAC * (1.0 - channel_util) / n_tx    # effective goodput
    t_tx = bytes_on_air(size_bytes) * 8.0 / data_rate_bps                     # T_tx = Data / Rate
    t_result = bytes_on_air(RESULT_SIZE_KB * 1024.0) * 8.0 / data_rate_bps    # downlink [s]
    t_queue = channel_util / (1.0 - channel_util) * T_CONTENTION_S            # channel access [s]
    t_network = t_tx + t_result + T_GATEWAY_S + t_queue                       # T_network [s]
    t_edge = cpu_cycles / (F_EDGE_HZ * (1.0 - server_load / 100.0))           # T_edge [s]
    t_offload = t_network + t_edge
    e_tx = P_TX_W * t_tx                                                      # E_tx = P_tx · T_tx
    e_offload = e_tx + P_RX_W * (t_edge + t_result + T_GATEWAY_S + t_queue)   # + listening for result

    # COSTS: energy is priced by battery risk λ(SOC); time relative to the deadline
    price = battery_price(soc)
    j_local = (W_ENERGY * price * e_local / E_REF_J
               + W_TIME * t_local / T_DEADLINE_S
               + W_DEADLINE * (t_local > T_DEADLINE_S))
    j_offload = (W_ENERGY * price * e_offload / E_REF_J
                 + W_TIME * t_offload / T_DEADLINE_S
                 + W_NETWORK * per
                 + W_SERVER * (server_load / 100.0) ** 2
                 + W_DEADLINE * (t_offload > T_DEADLINE_S))

    return {
        "cpu_cycles": cpu_cycles, "cpu_load": cpu_load, "t_local": t_local, "e_local": e_local,
        "mcs": mcs, "per": per, "n_tx": n_tx, "data_rate_bps": data_rate_bps,
        "t_tx": t_tx, "t_network": t_network, "t_edge": t_edge, "t_offload": t_offload,
        "e_tx": e_tx, "e_offload": e_offload, "price": price,
        "j_local": j_local, "j_offload": j_offload,
        "decision": "LOCAL" if j_local < j_offload else "OFFLOAD",   # the cheaper option wins
    }


# ════════════════════════════════════════════════════════════════════════════
# 3. THE DIGITAL TWIN
# ════════════════════════════════════════════════════════════════════════════
class DiagnosedIoTDigitalTwin:
    """Stateful twin: call step() once per simulated minute; it returns one dataset row."""

    def __init__(self, seed: int = 42, initial_soc: float = 25.0):
        self.rng = np.random.default_rng(seed)
        self.tick = 0
        self.soc = initial_soc                       # battery state of charge [%]

        # Environment states (each evolves continuously from step to step)
        self.weather = "Partly Cloudy"
        self.cloud_k = WEATHER_MEAN_K[self.weather]  # cloud transmittance [0..1]
        self.distance = DIST_MEAN_M                  # ESP32 ↔ access-point distance [m]
        self.shadowing = 0.0                         # slow shadowing component [dB]
        self.server_base = 20.0                      # edge load from other users [%]
        self.burst = 0.0                             # decaying traffic burst [%]
        self.background = BACKGROUND_MEAN            # ESP32 background CPU load [%]

        # Task generator states
        self.task_type = "Sensor Aggregation"
        self.size_state = 0.0                        # AR(1) log-size deviation [-]

    # ── Environment ─────────────────────────────────────────────────────────
    def _update_weather(self, minute_of_day: int):
        """At midnight pick tomorrow's weather from the Markov chain."""
        if minute_of_day == 0:
            probs = WEATHER_TRANSITION[self.weather]
            self.weather = str(self.rng.choice(WEATHER_TYPES, p=probs))

    def _update_clouds(self):
        """Ornstein–Uhlenbeck cloud factor: drifts smoothly around today's mean (no jumps)."""
        mean_k = WEATHER_MEAN_K[self.weather]
        self.cloud_k += CLOUD_REVERSION * (mean_k - self.cloud_k) + self.rng.normal(0.0, CLOUD_SIGMA)
        self.cloud_k = min(1.0, max(0.05, self.cloud_k))

    def _update_position(self):
        """Node mounted on moving equipment: mean-reverting random walk of the distance [m]."""
        self.distance += 0.005 * (DIST_MEAN_M - self.distance) + self.rng.normal(0.0, 0.8)
        self.distance = min(DIST_MAX_M, max(DIST_MIN_M, self.distance))
        # Correlated (Gudmundson) shadowing: obstacles appear / disappear gradually
        innovation = SHADOW_SIGMA_DB * math.sqrt(1.0 - SHADOW_CORR ** 2)
        self.shadowing = SHADOW_CORR * self.shadowing + self.rng.normal(0.0, innovation)

    def _update_server_load(self, hour: float) -> float:
        """Edge utilisation = daily usage profile + slow drift + decaying traffic bursts [%]."""
        office_hours = max(0.0, math.sin(math.pi * (hour - 7.0) / 14.0)) if 7.0 < hour < 21.0 else 0.0
        target = 15.0 + 55.0 * office_hours
        self.server_base += 0.05 * (target - self.server_base) + self.rng.normal(0.0, 2.0)
        self.server_base = min(90.0, max(5.0, self.server_base))

        self.burst *= 0.85                                   # existing burst decay is preserved
        if self.rng.random() < BURST_PROBABILITY:
            self.burst += self.rng.uniform(15.0, 30.0)
        return min(SERVER_LOAD_MAX, self.server_base + self.burst)

    # ── Task arrival ────────────────────────────────────────────────────────
    def _new_task(self, hour: float):
        """
        One IoT monitoring task per minute.
          Task_Size       = data collected in the sensing window [KB]
          Task_Complexity = processing effort for that data [CPU cycles / byte]
        """
        if self.rng.random() > TASK_TYPE_PERSISTENCE:
            self.task_type = str(self.rng.choice(list(TASK_TYPES)))
        spec = TASK_TYPES[self.task_type]

        # Plant activity is higher in working hours -> more data per window
        activity = 0.7 + 0.3 * (max(0.0, math.sin(math.pi * (hour - 6.0) / 14.0)) if 6.0 < hour < 20.0 else 0.0)
        self.size_state = 0.9 * self.size_state + self.rng.normal(0.0, 0.12)   # AR(1) continuity
        size_kb = spec["mean_kb"] * activity * math.exp(self.size_state)
        size_kb = min(TASK_SIZE_MAX_KB, max(TASK_SIZE_MIN_KB, size_kb))

        cycles_per_byte = spec["cycles_per_byte"] * math.exp(self.rng.normal(0.0, 0.08))
        return size_kb, cycles_per_byte

    # ── One simulation step ─────────────────────────────────────────────────
    def step(self) -> dict:
        self.tick += 1
        t = self.tick
        minute_of_day = t % 1440
        hour = minute_of_day / 60.0

        # ─── 1. Renewable energy ───────────────────────────────────────────
        self._update_weather(minute_of_day)
        self._update_clouds()
        irradiance = clear_sky_irradiance(hour) * self.cloud_k          # G(t) [W/m²]
        p_pv = pv_power(irradiance)                                     # P_PV [W]

        # ─── 2. Task model ─────────────────────────────────────────────────
        size_kb, cycles_per_byte = self._new_task(hour)

        # ─── 3. ESP32 background load + 4. wireless channel + 5. edge load ─
        self.background += 0.1 * (BACKGROUND_MEAN - self.background) + self.rng.normal(0.0, 1.5)
        self.background = min(30.0, max(5.0, self.background))
        self._update_position()
        rssi = rssi_from_distance(self.distance, self.shadowing, self.rng.normal(0.0, FAST_FADE_SIGMA_DB))
        channel_util = wifi_channel_utilisation(hour)
        server_load = self._update_server_load(hour)

        # ─── 6–8. Evaluate LOCAL vs OFFLOAD with the physical models ───────
        m = evaluate_options(size_kb, cycles_per_byte, self.background, rssi,
                             channel_util, server_load, self.soc)
        decision = m["decision"]

        # ─── 9. Battery update with the energy that was actually spent ─────
        e_task = m["e_local"] if decision == "LOCAL" else m["e_offload"]
        p_load = P_BASE_W + e_task / DT_S
        soc_before = self.soc
        self.soc, p_charge, p_discharge = update_soc(self.soc, p_pv, p_load)

        day = (t // 1440) + 1
        return {
            "Step": t,
            "Timestamp": f"Day {day:02d}, {minute_of_day // 60:02d}:{minute_of_day % 60:02d}",
            "Hour": round(hour, 3),
            "Weather": self.weather,
            # Renewable + battery
            "Solar_Irradiance": round(irradiance, 1),                 # W/m²
            "Renewable_Power": round(p_pv, 4),                        # W
            "Renewable_Availability": round(100.0 * p_pv / P_RATED_W, 2),  # % of rated PV power
            "Load_Power": round(p_load, 4),                           # W
            "Battery_Charge_Power": round(p_charge, 4),               # W (accepted by battery)
            "Battery_Discharge_Power": round(p_discharge, 4),         # W
            "Battery_SOC": round(self.soc, 3),                        # %
            "dSOC_dt": round(self.soc - soc_before, 5),               # %/min
            # Task + ESP32
            "Task_ID": f"T{t:05d}",
            "Task_Type": self.task_type,
            "Task_Size": round(size_kb, 2),                           # KB
            "Task_Complexity": round(cycles_per_byte, 1),             # CPU cycles / byte
            "CPU_Cycles": round(m["cpu_cycles"] / 1e6, 3),                 # Mcycles
            "Background_Load": round(self.background, 2),             # %
            "CPU_Load": round(m["cpu_load"], 2),                           # %
            "Local_Exec_Time": round(m["t_local"] * 1000.0, 2),            # ms
            "Local_Energy": round(m["e_local"] * 1000.0, 3),               # mJ
            # Network
            "Distance": round(self.distance, 2),                      # m
            "RSSI": round(rssi, 2),                                   # dBm
            "WiFi_MCS": m["mcs"],
            "Data_Rate": round(m["data_rate_bps"] / 1e6, 3),               # Mbps (effective)
            "PER": round(m["per"], 4),                                     # packet error rate
            "Transmissions": round(m["n_tx"], 3),                          # expected attempts / packet
            "Transmission_Time": round(m["t_tx"] * 1000.0, 2),             # ms
            "Network_Latency": round(m["t_network"] * 1000.0, 2),          # ms
            "Transmission_Energy": round(m["e_tx"] * 1000.0, 3),           # mJ
            "Offload_Energy": round(m["e_offload"] * 1000.0, 3),           # mJ (tx + waiting for result)
            # Edge
            "Server_CPU_Load": round(server_load, 2),                 # %
            "Edge_Processing_Time": round(m["t_edge"] * 1000.0, 2),        # ms
            "Offload_Total_Time": round(m["t_offload"] * 1000.0, 2),       # ms
            # Decision
            "Battery_Price": round(m["price"], 4),
            "Local_Execution_Cost": round(m["j_local"], 5),
            "Offload_Execution_Cost": round(m["j_offload"], 5),
            "Decision": decision,
        }


# ════════════════════════════════════════════════════════════════════════════
# 4. DATASET GENERATION
# ════════════════════════════════════════════════════════════════════════════
def export_web_data(df: pd.DataFrame, path: str = "web_data.js") -> None:
    """Package the dataset as a JS file so index.html can play it back (also from file://)."""
    payload = {"columns": list(df.columns), "rows": df.values.tolist()}
    with open(path, "w", encoding="utf-8") as f:
        f.write("// Generated by digital_twin_simulator.py — do not edit by hand.\n")
        f.write("window.TWIN_DATA = ")
        json.dump(payload, f, separators=(",", ":"))
        f.write(";\n")


def run_simulation(n_days: int = 7, output_csv: str = "simulation_dataset.csv",
                   seed: int = 42, initial_soc: float = 25.0,
                   web_js: str = "web_data.js") -> pd.DataFrame:
    twin = DiagnosedIoTDigitalTwin(seed=seed, initial_soc=initial_soc)
    df = pd.DataFrame([twin.step() for _ in range(n_days * 1440)])
    df.to_csv(output_csv, index=False)
    if web_js:
        export_web_data(df, web_js)

    local_share = (df["Decision"] == "LOCAL").mean() * 100
    print("=" * 65)
    print(f"DIGITAL TWIN SIMULATION COMPLETE — {len(df):,} steps ({n_days} days) -> {output_csv}")
    print("=" * 65)
    print(f"Battery SOC        : min {df['Battery_SOC'].min():.1f} %  "
          f"mean {df['Battery_SOC'].mean():.1f} %  max {df['Battery_SOC'].max():.1f} %")
    print(f"Network latency    : median {df['Network_Latency'].median():.0f} ms")
    print(f"Decisions          : {local_share:.1f} % LOCAL | {100 - local_share:.1f} % OFFLOAD (emergent)")
    print("=" * 65)
    return df


if __name__ == "__main__":
    run_simulation(n_days=7)
