"""
Streamlit dashboard for the Renewable-Aware IoT Task Offloading Digital Twin.

    streamlit run streamlit_app.py

Layout
  1. Controls          – start / pause / step / reset, speed, minutes per refresh
  2. Live KPIs         – current state of every subsystem
  3. 3D Digital Twin   – persistent Three.js scene (twin3d/), animates every task
  4. Relationship plots – the 8 graphs that prove the equations work
  5. Verification      – engineering checks (collapsed)
  6. Dataset           – generate / download the CSV
"""

import os
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from digital_twin_simulator import DiagnosedIoTDigitalTwin, export_web_data
from validate_twin import run_validation, what_if_battery_network

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "simulation_dataset.csv")

# ─────────────────────────────────────────────────────────────────────────────
# PAGE + THEME
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Renewable IoT Digital Twin", page_icon="⚡",
                   layout="wide", initial_sidebar_state="collapsed")

COLORS = {
    "solar": "#facc15", "battery": "#34d399", "cpu": "#22d3ee", "wifi": "#c084fc",
    "latency": "#f472b6", "server": "#818cf8", "local": "#2dd4bf", "offload": "#60a5fa",
    "energy": "#fb923c",
}

st.markdown("""
<style>
  .stApp { background: radial-gradient(1200px 600px at 10% -10%, #312e81 0%, transparent 60%),
                       radial-gradient(1000px 500px at 100% 0%, #0e7490 0%, transparent 55%), #0b1026;
           color: #e2e8f0; }
  .hero { padding: 18px 24px; border-radius: 16px; margin-bottom: 14px;
          background: linear-gradient(120deg, rgba(250,204,21,.18), rgba(34,211,238,.18), rgba(192,132,252,.22));
          border: 1px solid rgba(255,255,255,.12); }
  .hero h1 { margin: 0; font-size: 1.6rem; font-weight: 900;
             background: linear-gradient(90deg, #facc15, #34d399, #22d3ee, #c084fc);
             -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .hero p { margin: 4px 0 0; color: #cbd5e1; font-size: .9rem; }
  .chain { font-family: 'JetBrains Mono', monospace; font-size: .8rem; color: #f8fafc; margin-top: 6px; }
  .kpi { border-radius: 14px; padding: 12px 14px; background: rgba(15,23,42,.7);
         border: 1px solid rgba(255,255,255,.08); border-top: 3px solid var(--c);
         box-shadow: 0 0 22px -8px var(--c); }
  .kpi .l { font-size: .7rem; font-weight: 800; letter-spacing: .6px; text-transform: uppercase; color: #94a3b8; }
  .kpi .v { font-size: 1.35rem; font-weight: 900; color: var(--c); font-family: 'JetBrains Mono', monospace; }
  .kpi .s { font-size: .72rem; color: #cbd5e1; }
  .badge { text-align: center; padding: 16px 8px; border-radius: 14px; font-weight: 900; font-size: 1.2rem;
           color: #0b1026; letter-spacing: 1px; }
  .section { font-size: 1.15rem; font-weight: 800; margin: 18px 0 8px; color: #f8fafc; }
  .clock { font-family: 'JetBrains Mono', monospace; color: #22d3ee; background: rgba(15,23,42,.8);
           padding: 8px 14px; border-radius: 10px; border: 1px solid #1e3a5f; display: inline-block; }
  #MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# The 3D scene is a custom component: created once, then only receives new data
twin3d = components.declare_component("twin3d", path=os.path.join(HERE, "twin3d"))


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def reset_twin():
    st.session_state.engine = DiagnosedIoTDigitalTwin(seed=42, initial_soc=25.0)
    st.session_state.history = []
    st.session_state.running = False


if "engine" not in st.session_state:
    reset_twin()

# ─────────────────────────────────────────────────────────────────────────────
# HEADER + CONTROLS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>⚡ Renewable-Aware IoT Task Offloading — Digital Twin</h1>
  <p>Every minute an IoT monitoring task arrives at a solar-powered ESP32. The twin computes the time and
     energy of running it locally versus offloading it over WiFi to an edge server, and picks the cheaper option.</p>
  <div class="chain">☀️ Solar PV → 🔋 Battery → 📟 ESP32 → 📶 WiFi / MQTT → 🖥️ Edge Server</div>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 1.6, 1.6])
if c1.button("▶ Start", use_container_width=True, type="primary"):
    st.session_state.running = True
if c2.button("⏸ Pause", use_container_width=True):
    st.session_state.running = False
step_once = c3.button("⏭ Step", use_container_width=True)
if c4.button("🔄 Reset", use_container_width=True):
    reset_twin()
speed = c5.slider("Refresh interval (s)", 0.5, 3.0, 1.5, 0.25)
minutes_per_refresh = c6.select_slider("Simulated minutes per refresh", [1, 5, 15, 30, 60], value=1)

# Advance the simulation
engine = st.session_state.engine
if st.session_state.running or step_once or not st.session_state.history:
    for _ in range(minutes_per_refresh if st.session_state.running else 1):
        st.session_state.history.append(engine.step())

history = st.session_state.history
latest = history[-1]
df = pd.DataFrame(history)

st.markdown(f'<div class="clock">🕒 {latest["Timestamp"]} &nbsp;·&nbsp; step {latest["Step"]:,} '
            f'&nbsp;·&nbsp; {latest["Weather"]}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 1. LIVE KPIs
# ─────────────────────────────────────────────────────────────────────────────
def kpi(col, label, value, sub, color):
    col.markdown(f'<div class="kpi" style="--c:{color}"><div class="l">{label}</div>'
                 f'<div class="v">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


soc = latest["Battery_SOC"]
soc_color = "#34d399" if soc > 60 else "#fbbf24" if soc >= 30 else "#f87171"
charging = latest["Battery_Charge_Power"] > 0
k = st.columns(8)
kpi(k[0], "☀️ Solar power", f'{latest["Renewable_Power"]:.2f} W', f'G = {latest["Solar_Irradiance"]:.0f} W/m²', COLORS["solar"])
kpi(k[1], "🔋 Battery SOC", f"{soc:.1f} %",
    f'{"▲ charging" if charging else "▼ discharging"} '
    f'{latest["Battery_Charge_Power"] if charging else latest["Battery_Discharge_Power"]:.2f} W', soc_color)
kpi(k[2], "📦 Task", f'{latest["Task_Size"]:.0f} KB', f'{latest["Task_Type"]} · {latest["Task_Complexity"]:.0f} cyc/B', COLORS["energy"])
kpi(k[3], "📟 ESP32 CPU", f'{latest["CPU_Load"]:.0f} %', f'{latest["CPU_Cycles"]:.0f} Mcycles', COLORS["cpu"])
kpi(k[4], "📶 RSSI", f'{latest["RSSI"]:.0f} dBm', f'{latest["Distance"]:.0f} m · {latest["Data_Rate"]:.1f} Mbps', COLORS["wifi"])
kpi(k[5], "⏱️ Latency", f'{latest["Network_Latency"]:.0f} ms', f'PER {100 * latest["PER"]:.1f} %', COLORS["latency"])
kpi(k[6], "🖥️ Edge load", f'{latest["Server_CPU_Load"]:.0f} %', f'T_edge {latest["Edge_Processing_Time"]:.0f} ms', COLORS["server"])
with k[7]:
    off = latest["Decision"] == "OFFLOAD"
    st.markdown(f'<div class="badge" style="background:{COLORS["offload"] if off else COLORS["local"]};'
                f'box-shadow:0 0 24px {COLORS["offload"] if off else COLORS["local"]}">'
                f'{"⚡ OFFLOAD" if off else "💻 LOCAL"}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 2. 3D DIGITAL TWIN (persistent component)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">🌐 3D Digital Twin — live task flow</div>', unsafe_allow_html=True)
twin3d(record=latest, interval_ms=int(speed * 1000), height=560, key="twin3d", default=None)

# ─────────────────────────────────────────────────────────────────────────────
# 3. RELATIONSHIP PLOTS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">📈 Engineering relationships (generated by the equations, not drawn)</div>',
            unsafe_allow_html=True)

hours = df["Step"] / 60.0
recent = df[df["Step"] > df["Step"].max() - 1440]          # last 24 simulated hours
sample = df.sample(min(len(df), 3000), random_state=0) if len(df) > 3000 else df


def styled(fig, title, x, y, height=300):
    fig.update_layout(title=dict(text=title, font=dict(size=14)), template="plotly_dark", height=height,
                      paper_bgcolor="rgba(15,23,42,.75)", plot_bgcolor="rgba(15,23,42,.35)",
                      margin=dict(l=50, r=20, t=45, b=95 if len(fig.data) > 1 else 40), title_x=0.01, xaxis_title=x, yaxis_title=y,
                      legend=dict(orientation="h", y=-0.28, x=0, yanchor="top"))
    return fig


def decision_colors(d):
    return [COLORS["offload"] if v == "OFFLOAD" else COLORS["local"] for v in d]


row1 = st.columns(2)
fig = go.Figure(go.Scatter(x=hours, y=df["Renewable_Power"], mode="lines", fill="tozeroy",
                           line=dict(color=COLORS["solar"], width=2), fillcolor="rgba(250,204,21,.2)",
                           name="P_PV"))
row1[0].plotly_chart(styled(fig, "1 · Solar power vs time   P_PV = P_rated·G/G_STC·η_PV",
                            "Simulated time (h)", "P_PV (W)"), use_container_width=True, theme=None)

fig = go.Figure(go.Scatter(x=hours, y=df["Battery_SOC"], mode="lines", line=dict(color=COLORS["battery"], width=2.5),
                           fill="tozeroy", fillcolor="rgba(52,211,153,.15)", name="SOC"))
fig.update_yaxes(range=[0, 100])
row1[1].plotly_chart(styled(fig, "2 · Battery SOC vs time   (energy balance)", "Simulated time (h)", "SOC (%)"),
                     use_container_width=True, theme=None)

row2 = st.columns(2)
fig = go.Figure()
for t_type, g in sample.groupby("Task_Type"):
    fig.add_trace(go.Scatter(x=g["Task_Size"], y=g["CPU_Load"], mode="markers", name=t_type,
                             marker=dict(size=6, opacity=.75)))
row2[0].plotly_chart(styled(fig, "3 · Task size vs CPU load   (C = D · c, per task type)", "Task size (KB)",
                            "CPU load (%)", height=360), use_container_width=True, theme=None)

fig = go.Figure(go.Scatter(x=sample["RSSI"], y=sample["Network_Latency"], mode="markers", name="tasks",
                           marker=dict(size=6, opacity=.7, color=sample["Task_Size"], colorscale="Plasma",
                                       colorbar=dict(title="KB"))))
bins = pd.cut(df["RSSI"], range(-96, -44, 4))
med = df.groupby(bins, observed=True)["Network_Latency"].median()
fig.add_trace(go.Scatter(x=[b.mid for b in med.index], y=med.values, mode="lines+markers", name="median",
                         line=dict(color="#f8fafc", width=3)))
fig.update_yaxes(type="log")
row2[1].plotly_chart(styled(fig, "4 · RSSI vs network latency   (weaker signal → lower MCS → slower)", "RSSI (dBm)",
                            "Latency (ms, log)"), use_container_width=True, theme=None)

row3 = st.columns(2)
fig = go.Figure(go.Scatter(x=sample["Task_Size"], y=sample["Transmission_Energy"], mode="markers",
                           marker=dict(size=6, opacity=.7, color=sample["RSSI"], colorscale="Viridis",
                                       colorbar=dict(title="dBm"))))
fig.update_yaxes(type="log")
row3[0].plotly_chart(styled(fig, "5 · Task size vs transmission energy   E_tx = P_tx · D / R", "Task size (KB)",
                            "E_tx (mJ, log)"), use_container_width=True, theme=None)

fig = go.Figure(go.Scatter(x=sample["Server_CPU_Load"], y=sample["Edge_Processing_Time"] / sample["CPU_Cycles"],
                           mode="markers", marker=dict(size=6, opacity=.75, color=COLORS["server"])))
row3[1].plotly_chart(styled(fig, "6 · Server load vs edge processing time   T = C / (f·(1−U))", "Server CPU load (%)",
                            "Edge time per Mcycle (ms)"), use_container_width=True, theme=None)

row4 = st.columns(2)
fig = go.Figure(go.Scatter(x=sample["Local_Execution_Cost"], y=sample["Offload_Execution_Cost"], mode="markers",
                           marker=dict(size=6, opacity=.7, color=decision_colors(sample["Decision"])),
                           text=sample["Decision"], name="tasks (colour = decision)",
                           hovertemplate="J_local %{x:.3f}<br>J_off %{y:.3f}<br>%{text}"))
lo = max(1e-3, min(sample["Local_Execution_Cost"].min(), sample["Offload_Execution_Cost"].min()))
hi = max(sample["Local_Execution_Cost"].max(), sample["Offload_Execution_Cost"].max())
fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color="#f8fafc", dash="dash"),
                         name="J_local = J_offload"))
fig.update_xaxes(type="log")
fig.update_yaxes(type="log")
row4[0].plotly_chart(styled(fig, "7 · Local cost vs offload cost   (above line → LOCAL, below → OFFLOAD)",
                            "J_local", "J_offload"), use_container_width=True, theme=None)

counts = df["Decision"].value_counts()
fig = go.Figure(go.Scatter(x=recent["Step"] / 60.0, y=recent["Decision"], mode="markers",
                           marker=dict(size=7, symbol="line-ns-open", color=decision_colors(recent["Decision"]))))
fig.update_yaxes(categoryorder="array", categoryarray=["LOCAL", "OFFLOAD"])
row4[1].plotly_chart(styled(fig, f"8 · Decisions over the last 24 h   (total: {counts.get('LOCAL', 0):,} LOCAL · "
                                 f"{counts.get('OFFLOAD', 0):,} OFFLOAD)", "Simulated time (h)", ""),
                     use_container_width=True, theme=None)

# ─────────────────────────────────────────────────────────────────────────────
# 4. ENGINEERING VERIFICATION (collapsed so the dashboard stays clean)
# ─────────────────────────────────────────────────────────────────────────────
with st.expander("🧪 Engineering verification — are the relationships really in the data?", expanded=False):
    if len(df) < 1440:
        st.info("Run at least one simulated day (or generate the 7-day dataset below) to verify the relationships.")
    else:
        report = run_validation(df)
        passed = (report["Result"] == "PASS").sum()
        st.markdown(f"**{passed} / {len(report)} checks passed** on {len(df):,} simulated minutes")
        st.dataframe(report, use_container_width=True, hide_index=True)

    st.markdown("**What-if experiment** — same task (Anomaly Detection, 160 KB) and edge load; only SOC and RSSI "
                "change. Cell = J_local − J_offload (positive → offloading is cheaper).")
    wi = what_if_battery_network()
    fig = go.Figure(go.Heatmap(z=wi.values, x=list(wi.columns), y=[f"SOC {s} %" for s in wi.index],
                               colorscale="RdBu", zmid=0, text=wi.values, texttemplate="%{text:.2f}"))
    st.plotly_chart(styled(fig, "Battery × network interaction", "", "", height=320), use_container_width=True, theme=None)
    st.caption("Good link: lower SOC → offloading becomes more attractive. Poor link: lower SOC → local execution "
               "becomes more attractive, because retransmissions make the radio cost more energy than the CPU.")

# ─────────────────────────────────────────────────────────────────────────────
# 5. DATASET
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section">💾 Dataset</div>', unsafe_allow_html=True)
d1, d2, d3 = st.columns([1.4, 1, 1])
if d1.button("⚙️ Generate 7-day dataset (10,080 tasks)", type="primary", use_container_width=True):
    with st.spinner("Running the digital twin for 7 simulated days..."):
        fresh = DiagnosedIoTDigitalTwin(seed=42, initial_soc=25.0)
        records = [fresh.step() for _ in range(7 * 1440)]
        generated = pd.DataFrame(records)
        generated.to_csv(CSV_PATH, index=False)
        export_web_data(generated, os.path.join(HERE, "web_data.js"))
        st.session_state.engine = fresh          # continue live from the end of day 7
        st.session_state.history = records
        st.session_state.running = False
    st.rerun()

d2.download_button("📥 Download current run (CSV)", df.to_csv(index=False).encode(), "twin_live_run.csv",
                   "text/csv", use_container_width=True)
if os.path.exists(CSV_PATH):
    with open(CSV_PATH, "rb") as f:
        d3.download_button("📥 Download simulation_dataset.csv", f.read(), "simulation_dataset.csv", "text/csv",
                           use_container_width=True)

with st.expander("🔍 Latest records", expanded=False):
    st.dataframe(df.tail(15), use_container_width=True, hide_index=True)

# Auto-advance
if st.session_state.running:
    time.sleep(speed)
    st.rerun()
