"""
Diagnosed & Validated Renewable-Aware IoT Task Offloading Digital Twin Engine
=============================================================================
Physically Grounded Upgraded Simulation Architecture:
  1. Solar Irradiance: Diurnal Sine Curve × Beta(6,2) Cloud-Cover Factor
  2. BESS Battery: Physical Specs (2.4W Panel, 12Wh Pack, CC/CV Tapering >90%, Self-Discharge)
  3. CPU Load: AR(1) Task Memory Continuity (0.7 * CPU(t-1) + 0.3 * CPU_det)
  4. RSSI / Network: Random-Walk Distance + Log-Distance Path Loss + Log-Normal Shadowing
  5. Edge Server Load: Diurnal Base Curve + Queueing Burst Surge Events (3% prob, 15-25% spike)
  6. Cost Equations: Non-Linear Battery Depletion Penalty (1 - SOC/100)^1.5
  7. Decision Rule: Step Threshold Optimal Boundary Rule (IF Local_Cost < Offload_Cost THEN LOCAL ELSE OFFLOAD)
"""

import os
import numpy as np
import pandas as pd

class DiagnosedIoTDigitalTwin:
    def __init__(self, seed: int = 42, initial_soc: float = 25.0):
        np.random.seed(seed)
        self.soc = initial_soc          # Initial Battery State of Charge [%]
        self.tick = 0                   # Minute step counter
        self.prev_cpu_load = 25.0       # AR(1) CPU Memory State
        self.distance = 25.0            # Random-walk virtual distance [meters]
        self.cloud_factor = np.random.beta(6, 2)
        self.cloud_timer = 0
        self.burst_timer = 0
        self.burst_intensity = 0.0

    def step(self) -> dict:
        self.tick += 1
        t = self.tick
        minute_of_day = t % 1440
        hour_of_day = minute_of_day / 60.0
        
        # 1. Solar Model — Cloud-Cover Factor Beta(6,2) updated every 30-60 min
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
            
        # 2. Task Parameters (Task_Size & Task_Complexity)
        task_size = float(np.round(np.random.uniform(1.0, 10.0), 2))
        task_complexity = int(np.random.randint(1, 11))
        
        # 3. CPU_Load — AR(1) Short-Term Memory Continuity
        cpu_load_det = (task_size * task_complexity / 100.0) * 85.0 + 10.0
        cpu_load_raw = 0.70 * self.prev_cpu_load + 0.30 * cpu_load_det + np.random.normal(0.0, 2.5)
        cpu_load = float(np.clip(cpu_load_raw, 0.0, 100.0))
        self.prev_cpu_load = cpu_load
        
        # 4. Physical BESS Specs (Panel_W = 2.4W, eff = 0.90, Battery_Wh = 12Wh)
        eff_charge_rate = (2.4 * (renewable_avail / 100.0) * 0.90) / 12.0 * (100.0 / 60.0)
        if self.soc > 90.0:
            eff_charge_rate *= 0.60  # 40% charge-tapering CC/CV near full
        renewable_charge = eff_charge_rate
        
        # ESP32 active power scaling (0.15W idle to 0.80W max)
        esp32_power_w = 0.15 + (0.80 - 0.15) * (cpu_load / 100.0)
        cpu_discharge = (esp32_power_w / 12.0) * (100.0 / 60.0)
        self_discharge = 0.001  # 0.001%/min self-discharge
        
        dsoc_dt = renewable_charge - cpu_discharge - self_discharge
        self.soc = float(np.clip(self.soc + dsoc_dt, 0.0, 100.0))
        battery_soc = self.soc
        
        # 5. RSSI — Random-Walk Virtual Distance & Log-Distance Path Loss
        dist_step = np.random.normal(0.0, 0.6)
        self.distance = float(np.clip(self.distance + dist_step, 4.0, 45.0))
        n_pathloss = 2.6
        d0 = 1.0
        shadow_fading = np.random.normal(0.0, 4.0)
        rssi_calc = -40.0 - 10.0 * n_pathloss * np.log10(self.distance / d0) + shadow_fading
        rssi = float(np.clip(rssi_calc, -90.0, -40.0))
        
        # 6. Network_Latency (Consumes updated RSSI)
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
        
        # 8. Cost Functions (Non-Linear Battery Depletion Risk)
        local_cost_det = 0.60 * (cpu_load / 100.0) + 0.40 * ((1.0 - battery_soc / 100.0) ** 1.5) + 0.25 * (task_complexity / 10.0)
        offload_cost_det = 0.40 * (network_latency / 150.0) + 0.40 * (server_cpu_load / 100.0) + 0.20 * (task_size / 10.0)
        
        local_cost = round(float(np.clip(local_cost_det + np.random.normal(0.0, 0.040), 0.0, 2.0)), 4)
        offload_cost = round(float(np.clip(offload_cost_det + np.random.normal(0.0, 0.040), 0.0, 2.0)), 4)
        
        # 9. Decision Engine Boundary Rule (100% consistent with noisy costs)
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

def run_simulation(n_days: int = 7, output_csv: str = "simulation_dataset.csv") -> pd.DataFrame:
    n_steps = n_days * 1440
    twin = DiagnosedIoTDigitalTwin(seed=42)
    records = [twin.step() for _ in range(n_steps)]
    df = pd.DataFrame(records)
    df.to_csv(output_csv, index=False)
    
    if os.path.exists(output_csv):
        print(f"SUCCESS: File '{output_csv}' created and verified on disk.")
        
    print("\n" + "="*65)
    print(f"PHYSICALLY GROUNDED SIMULATION COMPLETE — {len(df):,} Records Saved")
    print("="*65)
    print(f"Average Local_Cost:   {df['Local_Execution_Cost'].mean():.4f}")
    print(f"Average Offload_Cost: {df['Offload_Execution_Cost'].mean():.4f}")
    print(f"LOCAL Decisions:      {(df['Decision'] == 'LOCAL').sum():,} ({(df['Decision'] == 'LOCAL').mean()*100:.2f}%)")
    print(f"OFFLOAD Decisions:    {(df['Decision'] == 'OFFLOAD').sum():,} ({(df['Decision'] == 'OFFLOAD').mean()*100:.2f}%)")
    print(f"Renewable vs dSOC/dt Correlation: r = {df['Renewable_Availability'].corr(df['dSOC_dt']):+.4f}")
    print("="*65)
    
    return df

if __name__ == "__main__":
    run_simulation(n_days=7, output_csv="simulation_dataset.csv")
