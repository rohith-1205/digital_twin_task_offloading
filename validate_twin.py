"""
Engineering verification of the Digital Twin
============================================
Checks that the relationships required by the project emerge from the simulation
equations (nothing in the dataset is edited or forced).

    python validate_twin.py                 # validates simulation_dataset.csv
    python validate_twin.py my_data.csv     # validates another dataset

Correlations use Spearman's rank correlation ρ (monotonic trend, no linearity assumed).
"""

import sys

import numpy as np
import pandas as pd

import digital_twin_simulator as twin


def spearman(x: pd.Series, y: pd.Series) -> float:
    """Spearman ρ = Pearson correlation of the ranks (no SciPy needed)."""
    return float(x.rank().corr(y.rank()))


def _check(name, expected, measured, passed, detail=""):
    return {"Relationship": name, "Expected": expected, "Measured": measured,
            "Result": "PASS" if passed else "FAIL", "Detail": detail}


def run_validation(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per engineering check."""
    checks = []

    # 1. Renewable power ↑ → battery charging ↑ → SOC rises
    rho = spearman(df["Renewable_Power"], df["dSOC_dt"])
    checks.append(_check("Renewable Power ↑ → SOC rate ↑", "ρ > 0", f"ρ = {rho:+.2f}", rho > 0.5))

    day = (df["Step"] - 1) // 1440
    daily = pd.DataFrame({"pv_wh": df.groupby(day)["Renewable_Power"].sum() / 60.0,
                          "d_soc": df.groupby(day)["dSOC_dt"].sum()})
    if len(daily) >= 3:
        rho_d = spearman(daily["pv_wh"], daily["d_soc"])
        checks.append(_check("Daily solar energy ↑ → daily ΔSOC ↑", "ρ > 0", f"ρ = {rho_d:+.2f}",
                             rho_d > 0.5, f"{len(daily)} days"))

    # 2. Task size ↑ → CPU workload ↑ (within each task type, complexity fixed)
    rhos = [spearman(g["Task_Size"], g["CPU_Cycles"]) for _, g in df.groupby("Task_Type") if len(g) > 30]
    checks.append(_check("Task Size ↑ → CPU workload ↑", "ρ > 0 per task type",
                         f"min ρ = {min(rhos):+.2f}", min(rhos) > 0.8))

    # 3. Task complexity ↑ → CPU load ↑ → local energy ↑
    rho = spearman(df["Task_Complexity"], df["CPU_Load"])
    checks.append(_check("Task Complexity ↑ → CPU Load ↑", "ρ > 0", f"ρ = {rho:+.2f}", rho > 0.5))
    rho = spearman(df["CPU_Load"], df["Local_Energy"])
    checks.append(_check("CPU Load ↑ → Local Energy ↑", "ρ > 0", f"ρ = {rho:+.2f}", rho > 0.8))

    # 4. Task size ↑ → transmission energy ↑
    rho = spearman(df["Task_Size"], df["Transmission_Energy"])
    checks.append(_check("Task Size ↑ → Transmission Energy ↑", "ρ > 0", f"ρ = {rho:+.2f}", rho > 0.8))

    # 5. Distance ↑ → RSSI ↓ ;  RSSI ↓ → latency per KB ↑ (removes the task-size effect)
    rho = spearman(df["Distance"], df["RSSI"])
    checks.append(_check("Distance ↑ → RSSI ↓", "ρ < 0", f"ρ = {rho:+.2f}", rho < -0.5))
    # The WiFi rate saturates above the fastest-MCS sensitivity (−72 dBm), so compare
    # the median transmission time per KB in RSSI bins instead of one global ρ.
    bins = [-120, -86, -80, -74, -40]
    per_kb = (df["Transmission_Time"] / df["Task_Size"]).groupby(pd.cut(df["RSSI"], bins), observed=True).median()
    monotonic = bool(np.all(np.diff(per_kb.values) < 0))
    checks.append(_check("RSSI ↓ → Latency ↑ (ms per KB)", "falls as RSSI bin rises",
                         " > ".join(f"{v:.2f}" for v in per_kb.values), monotonic,
                         "bins: <−86, −86…−80, −80…−74, >−74 dBm"))
    rho = spearman(df["RSSI"], df["Transmissions"])
    checks.append(_check("RSSI ↓ → Retransmissions ↑", "ρ < 0", f"ρ = {rho:+.2f}", rho < -0.3))
    rho = spearman(df["RSSI"], df["Network_Latency"])
    checks.append(_check("RSSI ↓ → Network Latency ↑ (raw)", "ρ < 0", f"ρ = {rho:+.2f}", rho < 0,
                         "raw latency also depends on task size"))

    # 6. Server load ↑ → edge processing time per Mcycle ↑
    rho = spearman(df["Server_CPU_Load"], df["Edge_Processing_Time"] / df["CPU_Cycles"])
    checks.append(_check("Server Load ↑ → Edge Processing Time ↑", "ρ > 0", f"ρ = {rho:+.2f}", rho > 0.95,
                         "per Mcycle of work"))

    # 7. Battery SOC ↓ → energy becomes more expensive
    rho = spearman(df["Battery_SOC"], df["Battery_Price"])
    checks.append(_check("Battery SOC ↓ → energy price λ ↑", "ρ < 0", f"ρ = {rho:+.2f}", rho < -0.99))

    # 8. Energy conservation: SOC change must equal the logged power flows
    dt, e_bat = twin.DT_S, twin.E_BAT_J
    predicted = ((twin.ETA_CHARGE * df["Battery_Charge_Power"] * dt / e_bat
                  - df["Battery_Discharge_Power"] * dt / (twin.ETA_DISCHARGE * e_bat)) * 100.0
                 - twin.SELF_DISCHARGE_PCT)
    unclipped = (df["Battery_SOC"] > 0.01) & (df["Battery_SOC"] < 99.99)
    err = (predicted - df["dSOC_dt"])[unclipped].abs().max()
    checks.append(_check("Energy balance closes (ΔSOC = flows)", "error ≈ 0", f"max |err| = {err:.1e} %",
                         err < 1e-3, "rounding only"))

    # 9. Decisions come only from the cost comparison
    expected = np.where(df["Local_Execution_Cost"] < df["Offload_Execution_Cost"], "LOCAL", "OFFLOAD")
    match = (expected == df["Decision"]).mean() * 100
    checks.append(_check("Decision = argmin(cost)", "100 %", f"{match:.2f} %", match > 99.9,
                         "ties at 5-decimal rounding may differ"))

    # 10. Temporal continuity (no random jumps)
    for col, limit in [("Battery_SOC", 0.99), ("RSSI", 0.8), ("Task_Size", 0.8),
                       ("Server_CPU_Load", 0.8), ("Renewable_Power", 0.9)]:
        ac = df[col].autocorr(lag=1)
        checks.append(_check(f"{col} is temporally continuous", f"lag-1 autocorr > {limit}",
                             f"{ac:.3f}", ac > limit))
    full = (df["Battery_SOC"] >= 99.9).mean() * 100
    checks.append(_check("Battery is not stuck at 100 %", "< 50 % of time", f"{full:.1f} %", full < 50))

    return pd.DataFrame(checks)


def what_if_battery_network(task_type: str = "Anomaly Detection", size_kb: float = 160.0,
                            server_load: float = 40.0) -> pd.DataFrame:
    """
    Controlled experiment with the twin's own equations: keep the task and the edge
    fixed, vary only SOC and RSSI, and report  ΔJ = J_local − J_offload
    (ΔJ > 0 → offloading is cheaper).
    """
    cpb = twin.TASK_TYPES[task_type]["cycles_per_byte"]
    rssi_values = [-55, -65, -72, -80, -86, -90]
    rows = []
    for soc in [10, 30, 50, 70, 90]:
        row = {"Battery_SOC (%)": soc}
        for rssi in rssi_values:
            m = twin.evaluate_options(size_kb, cpb, twin.BACKGROUND_MEAN, rssi, 0.3, server_load, soc)
            row[f"RSSI {rssi} dBm"] = round(m["j_local"] - m["j_offload"], 3)
        rows.append(row)
    return pd.DataFrame(rows).set_index("Battery_SOC (%)")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "simulation_dataset.csv"
    data = pd.read_csv(path)
    report = run_validation(data)
    pd.set_option("display.width", 160)
    print(f"\nENGINEERING VERIFICATION — {path} ({len(data):,} rows)\n")
    print(report.to_string(index=False))
    print(f"\n{(report['Result'] == 'PASS').sum()} / {len(report)} checks passed")

    print("\nWHAT-IF: ΔJ = J_local − J_offload for an Anomaly Detection task (160 KB, server 40 %)")
    print("         positive → OFFLOAD cheaper, negative → LOCAL cheaper\n")
    print(what_if_battery_network().to_string())
    print("\nGood link : lower SOC → ΔJ grows  → offloading becomes MORE attractive")
    print("Poor link : lower SOC → ΔJ falls  → local execution becomes MORE attractive")
