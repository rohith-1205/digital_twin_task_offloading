import numpy as np
import pandas as pd

class UpgradedIoTDigitalTwin:
    def __init__(self, seed: int = 42, initial_soc: float = 25.0):
        np.random.seed(seed)
        self.soc = initial_soc
        self.tick = 0
        self.prev_cpu_load = 25.0
        self.distance = 25.0  # meters
        self.cloud_factor = np.random.beta(6, 2)
        self.cloud_timer = 0
        self.burst_timer = 0
        self.burst_intensity = 0.0

    def step(self) -> dict:
        self.tick += 1
        t = self.tick
        minute_of_day = t % 1440
        hour_of_day = minute_of_day / 60.0
        
        # 1. Solar Model — Cloud-cover factor Beta(6,2) updated every 30-60 min
        if self.cloud_timer <= 0:
            self.cloud_factor = float(np.random.beta(6, 2))
            self.cloud_timer = int(np.random.randint(30, 61))
        else:
            self.cloud_timer -= 1
            
        if 6.0 <= hour_of_day <= 18.0:
            solar_phase = (hour_of_day - 6.0) / 12.0
            solar_clear = max(0.0, np.sin(solar_phase * np.pi)) * 95.0
            renewable_avail = float(solar_clear * self.cloud_factor)
        else:
            renewable_avail = 0.0
            
        # 2. Task Parameters
        task_size = float(np.round(np.random.uniform(1.0, 10.0), 2))
        task_complexity = int(np.random.randint(1, 11))
        
        # 3. CPU Load AR(1) Short-Term Memory
        cpu_load_det = (task_size * task_complexity / 100.0) * 85.0 + 10.0
        cpu_load_raw = 0.70 * self.prev_cpu_load + 0.30 * cpu_load_det + np.random.normal(0.0, 2.5)
        cpu_load = float(np.clip(cpu_load_raw, 0.0, 100.0))
        self.prev_cpu_load = cpu_load
        
        # 4. Physical BESS Specs (Panel_W=2.4W, eff=0.90, Batt_Wh=12Wh)
        eff_charge_rate = (2.4 * (renewable_avail / 100.0) * 0.90) / 12.0 * (100.0 / 60.0)
        if self.soc > 90.0:
            eff_charge_rate *= 0.60  # 40% charge-tapering CC/CV near full
        renewable_charge = eff_charge_rate
        
        # ESP32 active power (0.15W idle to 0.8W max)
        esp32_power_w = 0.15 + (0.80 - 0.15) * (cpu_load / 100.0)
        cpu_discharge = (esp32_power_w / 12.0) * (100.0 / 60.0)
        self_discharge = 0.001  # 0.001%/min self-discharge
        
        dsoc_dt = renewable_charge - cpu_discharge - self_discharge
        self.soc = float(np.clip(self.soc + dsoc_dt, 0.0, 100.0))
        battery_soc = self.soc
        
        # 5. RSSI — Random Walk Virtual Distance & Log-Distance Path Loss
        dist_step = np.random.normal(0.0, 0.6)
        self.distance = float(np.clip(self.distance + dist_step, 4.0, 45.0))
        n_pathloss = 2.6
        d0 = 1.0
        shadow_fading = np.random.normal(0.0, 4.0)
        rssi_calc = -40.0 - 10.0 * n_pathloss * np.log10(self.distance / d0) + shadow_fading
        rssi = float(np.clip(rssi_calc, -90.0, -40.0))
        
        # 6. Network Latency
        network_latency_det = 150.0 - ((rssi + 90.0) / 50.0) * 140.0
        jitter_spike = np.random.uniform(20.0, 50.0) if np.random.rand() < 0.025 else 0.0
        network_latency = float(np.clip(network_latency_det + np.random.normal(0.0, 15.0) + jitter_spike, 10.0, 200.0))
        
        # 7. Edge Server Load Queueing & Burst Events
        server_phase = ((minute_of_day - 480) % 1440) / 1440.0
        server_base = 10.0 + 80.0 * max(0.0, np.sin(server_phase * 2 * np.pi))
        
        if self.burst_timer <= 0:
            if np.random.rand() < 0.03:
                self.burst_intensity = float(np.random.uniform(15.0, 25.0))
                self.burst_timer = int(np.random.randint(5, 16))
            else:
                self.burst_intensity = 0.0
        else:
            self.burst_timer -= 1
            self.burst_intensity *= 0.85
            
        server_cpu_load = float(np.clip(server_base + self.burst_intensity, 0.0, 100.0))
        
        # 8. Cost Functions (Non-linear battery depletion penalty)
        local_cost_det = 0.60 * (cpu_load / 100.0) + 0.40 * ((1.0 - battery_soc / 100.0) ** 1.5) + 0.25 * (task_complexity / 10.0)
        offload_cost_det = 0.40 * (network_latency / 150.0) + 0.40 * (server_cpu_load / 100.0) + 0.20 * (task_size / 10.0)
        
        local_cost = round(float(np.clip(local_cost_det + np.random.normal(0.0, 0.040), 0.0, 2.0)), 4)
        offload_cost = round(float(np.clip(offload_cost_det + np.random.normal(0.0, 0.040), 0.0, 2.0)), 4)
        
        # 9. Decision Engine
        if local_cost < offload_cost:
            decision = "LOCAL"
        else:
            decision = "OFFLOAD"
            
        day = (t // 1440) + 1
        hrs = minute_of_day // 60
        mins = minute_of_day % 60
        timestamp_str = f"Day {day:02d}, {hrs:02d}:{mins:02d}"

        return {
            "Step": t,
            "Timestamp": timestamp_str,
            "Hour": round(hour_of_day, 2),
            "Renewable_Availability": round(renewable_avail, 2),
            "Renewable_Charge": round(renewable_charge, 4),
            "CPU_Discharge": round(cpu_discharge, 4),
            "Battery_SOC": round(battery_soc, 2),
            "dSOC_dt": round(dsoc_dt, 4),
            "Task_Size": round(task_size, 2),
            "Task_Complexity": task_complexity,
            "CPU_Load": round(cpu_load, 2),
            "RSSI": round(rssi, 1),
            "Network_Latency": round(network_latency, 1),
            "Server_CPU_Load": round(server_cpu_load, 2),
            "Local_Execution_Cost": local_cost,
            "Offload_Execution_Cost": offload_cost,
            "Decision": decision
        }

def calc_r2(X_mat, y_vec):
    X_design = np.column_stack([np.ones(len(X_mat)), X_mat])
    beta, _, _, _ = np.linalg.lstsq(X_design, y_vec, rcond=None)
    y_pred = X_design @ beta
    ss_res = np.sum((y_vec - y_pred) ** 2)
    ss_tot = np.sum((y_vec - np.mean(y_vec)) ** 2)
    return 1.0 - (ss_res / ss_tot)

def validate():
    twin = UpgradedIoTDigitalTwin(seed=42, initial_soc=50.0)
    records = [twin.step() for _ in range(10080)]
    df = pd.DataFrame(records)

    # (a) Decision/cost mismatch count
    expected_decisions = np.where(df["Local_Execution_Cost"] < df["Offload_Execution_Cost"], "LOCAL", "OFFLOAD")
    mismatches = (df["Decision"] != expected_decisions).sum()

    # (b) R2 of linear fit Local_Cost
    X_local = df[["Battery_SOC", "CPU_Load", "Task_Complexity"]].values
    y_local = df["Local_Execution_Cost"].values
    r2_local = calc_r2(X_local, y_local)

    # (c) R2 of linear fit Offload_Cost
    X_offload = df[["Network_Latency", "Server_CPU_Load", "Task_Size"]].values
    y_offload = df["Offload_Execution_Cost"].values
    r2_offload = calc_r2(X_offload, y_offload)

    # (d) Correlation RSSI vs Latency
    corr_rssi_lat = df["RSSI"].corr(df["Network_Latency"])

    # (e) Decision distribution
    local_pct = (df["Decision"] == "LOCAL").mean() * 100
    offload_pct = (df["Decision"] == "OFFLOAD").mean() * 100

    # (f) Battery_SOC stats
    soc_min = df["Battery_SOC"].min()
    soc_max = df["Battery_SOC"].max()
    soc_mean = df["Battery_SOC"].mean()
    below_30_pct = (df["Battery_SOC"] < 30.0).mean() * 100

    # (g) Zero solar drain test at 50% CPU load
    p_active = 0.15 + (0.80 - 0.15) * 0.50
    rate_min = (p_active / 12.0) * (100.0 / 60.0) + 0.001
    hours_to_drain = 100.0 / (rate_min * 60.0)

    print("=" * 65)
    print("UPGRADED PHYSICS SIMULATION DIAGNOSTIC VERIFICATION")
    print("=" * 65)
    print(f"(a) Decision/Cost Mismatch Count: {mismatches} (Must be 0)")
    print(f"(b) R² Local_Cost ~ [SOC, CPU_Load, Task_Complexity]: {r2_local:.6f}")
    print(f"(c) R² Offload_Cost ~ [Latency, Server_CPU, Task_Size]: {r2_offload:.6f}")
    print(f"(d) Correlation RSSI vs Latency: r = {corr_rssi_lat:+.4f}")
    print(f"(e) Decision Ratio: {local_pct:.2f}% LOCAL | {offload_pct:.2f}% OFFLOAD")
    print(f"(f) Battery SOC Stats: Min={soc_min:.2f}%, Max={soc_max:.2f}%, Mean={soc_mean:.2f}%, Below 30%={below_30_pct:.2f}%")
    print(f"(g) Zero-Solar Drain Time (CPU=50%): {hours_to_drain:.2f} hours (Target 15-25h)")
    print("=" * 65)

if __name__ == "__main__":
    validate()
