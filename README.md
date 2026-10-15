# Renewable-Aware IoT Task Offloading — Digital Twin

A digital twin of a **solar-powered IoT edge node**. Every simulated minute an IoT
monitoring task arrives at an ESP32. The twin computes, with physical models, how much
**time** and **energy** it would cost to run the task **locally** on the ESP32 or to
**offload** it over WiFi (MQTT) to an **edge server**. It then picks the cheaper option.

```
☀️ SOLAR PV  →  🔋 BATTERY  →  📟 ESP32 IoT NODE  →  📶 WiFi / MQTT  →  🖥️ EDGE SERVER
```

There is no rule such as "if solar > 50 % then LOCAL". The LOCAL / OFFLOAD decision
**emerges** from energy, computation, network and server conditions. The chosen
option's energy is then drawn from the battery, which closes the loop.

---

## Quick start

```bash
pip install -r requirements.txt

python digital_twin_simulator.py      # 7-day dataset → simulation_dataset.csv + web_data.js
python validate_twin.py               # engineering verification of the relationships
python hybrid_offloading.py           # train ANN + fuzzy + ANFIS and compare the controllers
streamlit run streamlit_app.py        # live dashboard + 3D twin + intelligent decision layer
```

You can also open **`index.html`** directly in a browser. It plays back `web_data.js`
(the Python engine's output) in the architecture diagram, the 3D twin, the data-flow
view and the module reference. Three.js is bundled in `twin3d/vendor/`, so everything
works **offline**.

---

## Project structure

| File | Purpose |
|---|---|
| `digital_twin_simulator.py` | **The only simulation engine.** All physical parameters are at the top of the file |
| `validate_twin.py` | Engineering checks + "what-if" battery × network experiment |
| `streamlit_app.py` | Dashboard: controls, KPIs, 3D twin, 8 relationship plots, verification, CSV export |
| `ann_models.py` | 🧠 NumPy neural networks: offload time/energy **predictor** and the "ANN only" classifier |
| `fuzzy_logic.py` | 🌫️ Mamdani fuzzy controller: membership functions + 12 expert rules ("Fuzzy only") |
| `anfis.py` | 🔗 ANFIS neuro-fuzzy system (5 layers, hybrid least-squares + gradient learning) |
| `hybrid_offloading.py` | ⭐ ANN → ANFIS hybrid controller, training, and closed-loop comparison of all controllers |
| `dashboard_intelligence.py` | Dashboard section for the intelligent layer + always-visible explanation |
| `twin3d/scene.js` | Shared Three.js scene used by both the dashboard and the web viewer |
| `twin3d/index.html` | Streamlit component wrapper (scene is created once and only receives new data) |
| `twin3d/assets/models.js` | Optional GLB/GLTF models that replace the procedural 3D models |
| `index.html`, `app.js`, `style.css` | Web viewer (playback only, no physics) |
| `simulation_dataset.csv` | Generated dataset (7 days, 10,080 tasks) |
| `web_data.js` | The same dataset packaged for the web viewer |

---

## Mathematical model (Δt = 60 s)

### 1 · Solar PV
- Clear-sky irradiance: `G_clear(t) = 1000 · sin(π (h − 6) / 12)` W/m² between 06:00 and 18:00, and 0 at night.
- Clouds: `G(t) = G_clear(t) · k_cloud(t)`. `k_cloud` is an Ornstein–Uhlenbeck process that drifts smoothly around the day's mean (Sunny 0.85, Partly Cloudy 0.60, Overcast 0.30). The daily weather follows a Markov chain.
- PV power: **`P_PV = P_rated · G / G_STC · η_PV`**, with P_rated = 1 W, G_STC = 1000 W/m², η_PV = 0.85.

### 2 · Battery (12 Wh Li-ion)
- Net power: `P_net = P_PV − P_load`, where `P_load = P_base + E_task / Δt`.
  - P_base = 0.14 W covers the sensors plus keeping the WiFi association.
  - E_task is the energy of the option that was chosen.
- Charging (P_net > 0): **`SOC += η_c · P_charge · Δt / E_bat`**, with η_c = 0.95. The charge power drops to 60 % above 90 % SOC (CC/CV taper).
- Discharging: **`SOC −= P_discharge · Δt / (η_d · E_bat)`**, with η_d = 0.95. A small self-discharge also applies. SOC is limited to 0–100 %.

### 3 · IoT task (one per minute)

| Task type | Complexity c (cycles/byte) | Mean size |
|---|---|---|
| Sensor Aggregation | 60 | 40 KB |
| Signal Filtering | 250 | 80 KB |
| FFT Feature Extract | 800 | 160 KB |
| Anomaly Detection | 1800 | 160 KB |
| Image Preprocessing | 3000 | 300 KB |

- **Task_Size D**: the data collected in the sensing window. It follows an AR(1) process and is larger during working hours.
- **Task_Complexity c**: the processing effort per byte. The task type persists from one minute to the next with probability 0.9.
- **`C_required = D · c`** (CPU cycles).

### 4 · ESP32 local execution (240 MHz)
- **`CPU_Load = Background + C / (f_ESP32 · T_deadline) · 100`**, with T_deadline = 5 s and Background ≈ 12 %.
- `T_local = C / (f_ESP32 · (1 − Background))`.
- **`E_local = (P_idle + α · CPU_Load) · T_local`**, with P_idle = 0.10 W and α = 0.0012 W/%.

### 5 · WiFi link (802.11n, MQTT over TCP/IP)
- Distance: the node is on moving equipment, so its distance d to the access point follows a mean-reverting random walk between 3 and 40 m.
- RSSI: **`RSSI = RSSI_0 − 10 n log10(d/d0) + X_σ`**, with RSSI_0 = −40 dBm, n = 2.6, and correlated shadowing (σ = 4 dB).
- Rate adaptation: the fastest 802.11n MCS whose receiver sensitivity is below the RSSI (MCS7 at −72 dBm … MCS0 at −91 dBm).
- Packet errors: PER is 10 % at the sensitivity limit and falls with SNR margin. Expected transmissions are `N_tx = 1/(1 − PER)`, capped at 7 (the retry limit).
- Effective rate: `R_eff = R_MCS · η_MAC · (1 − U_channel) / N_tx`, where U_channel is the share of airtime used by other WiFi devices.
- Transmission time: **`T_tx = (payload + MQTT + TCP/IP headers) · 8 / R_eff`**.
- **`T_network = T_tx + T_result + T_gateway + T_queue`**.
- **`E_tx = P_tx · T_tx`**, with P_tx = 0.60 W. The offload energy also includes `P_rx = 0.33 W` while the ESP32 waits for the result.

MQTT is a **modelled** protocol: its header overhead and the broker hop are included in
the timings. The simulator does not run a real MQTT broker.

### 6 · Edge server (3 GHz vCPU)
- Utilisation U = a daily usage profile + slow drift + decaying traffic bursts.
- **`T_edge = C / (f_edge · (1 − U))`**. This is the M/M/1 sojourn-time form: processing time grows sharply as the server saturates.

### 7 · Decision
- Battery-risk price of energy: `λ(SOC) = 1 + 4 · (1 − SOC/100)^1.5`.
- Cost of local execution:
  ```
  J_local   = λ·E_local/E_ref   + T_local/T_dl   + 2·[T_local > T_dl]
  ```
- Cost of offloading:
  ```
  J_offload = λ·E_offload/E_ref + T_offload/T_dl + 0.3·PER + 0.3·U² + 2·[T_offload > T_dl]
  ```
- Decision rule:
  ```
  Decision  = LOCAL if J_local < J_offload else OFFLOAD
  ```

λ multiplies **both** energies, because offloading drains the battery too. As a result:
- **Low SOC with a good link:** offloading saves energy, so OFFLOAD becomes more attractive.
- **Low SOC with a poor link:** retransmissions make the radio cost more than the CPU, so LOCAL becomes more attractive.

Solar affects decisions **only** through the battery.

---

## 🤖 Intelligent decision layer: ANN + Fuzzy logic + ANFIS

The exact cost comparison above needs values that a real ESP32 **cannot know before it
sends a task**: the real network latency, the radio energy and the edge server's load. It is
therefore used as the **🎯 oracle** (best possible answer). Three controllers decide with
realistic information only (SOC, the task, the *last* measured RSSI and the *last* reported
server load) and are graded against it.

```
🧠 ANN predictor ──► predicted offload time + energy ──┐
                                                       ├─► 🔗 ANFIS (36 learned fuzzy rules) ─► offload score ─► LOCAL / OFFLOAD
   SOC, last server load ──────────────────────────────┘
```

| Controller | How it decides | Strength / weakness |
|---|---|---|
| 🎯 Oracle | Exact `J_local` vs `J_offload` with perfect knowledge | Upper bound, not realisable |
| 🌫️ Fuzzy only | Mamdani: 4 inputs (SOC, task load, RSSI, server load), 12 expert rules, centroid defuzzification | Explainable, but thresholds are guessed |
| 🧠 ANN only | MLP classifier (9 → 24 → 16 → 1) | Accurate, but a black box |
| ⭐ ANN + ANFIS | ANN predicts offload time & energy → ANFIS inputs *SOC, energy ratio, time gain, server load* | Accurate **and** explainable |

**ANN.** MLP 6 → 24 → 16 → 2 (tanh, Adam, NumPy). Inputs: task size, complexity, last RSSI,
last server load, hour. Outputs: `Offload_Total_Time` and `Offload_Energy` (R² ≈ 0.99 on validation).

**ANFIS.** First-order Takagi–Sugeno, Gaussian membership functions, 3·3·2·2 = 36 rules.
Hybrid learning: least squares for the rule outputs, gradient descent for the membership shapes.
It is trained on the ANN's **predictions**, so it learns to live with the ANN's errors. Its teacher is a
soft oracle preference `0.5 + 0.5·tanh((J_local − J_offload)/0.25)`.

**Evaluation.** Training uses the first 80 % of `simulation_dataset.csv` and validation the last 20 %.
Each controller then drives the battery itself for an **unseen week** (seed 7). Typical result:

| Controller | Agreement with oracle | Task energy | Deadline misses |
|---|---|---|---|
| 🎯 Oracle | 100 % | 911 J | 0 |
| 🌫️ Fuzzy only | 92.7 % | 978 J | 16 |
| 🧠 ANN only | 95.9 % | 951 J | 11 |
| ⭐ ANN + ANFIS | **96.6 %** | **932 J** | **9** |

The dashboard shows the live decision of all four controllers, the ANN predictions against reality,
the fuzzy rules that fired, the learned membership functions and the comparison charts. At the
bottom, an always-visible guide explains how the ANN, fuzzy logic and ANFIS work together.

---

## Dataset columns (`simulation_dataset.csv`)

| Column | Unit | Meaning |
|---|---|---|
| Step, Timestamp, Hour | – | Simulated minute, `Day dd, hh:mm`, hour of day |
| Weather | – | Day type (Sunny / Partly Cloudy / Overcast) |
| Solar_Irradiance | W/m² | G(t) on the panel |
| Renewable_Power | W | P_PV generated by the panel |
| Renewable_Availability | % | P_PV as a % of the rated panel power |
| Load_Power | W | Base load + energy of the chosen action / Δt |
| Battery_Charge_Power / Battery_Discharge_Power | W | Power into / out of the battery |
| Battery_SOC, dSOC_dt | %, %/min | State of charge and its change this minute |
| Task_ID, Task_Type | – | Task identifier and kind of monitoring task |
| Task_Size | KB | Data produced in the sensing window |
| Task_Complexity | cycles/byte | Processing effort per byte |
| CPU_Cycles | Mcycles | C_required = D · c |
| Background_Load, CPU_Load | % | ESP32 background load and load with this task |
| Local_Exec_Time, Local_Energy | ms, mJ | Cost of running locally |
| Distance, RSSI | m, dBm | Node ↔ access point distance and signal strength |
| WiFi_MCS, Data_Rate | –, Mbps | Selected 802.11n MCS and effective goodput |
| PER, Transmissions | –, – | Packet error rate and expected attempts per packet |
| Transmission_Time, Network_Latency | ms | Uplink time; total network time (uplink + result + gateway + queue) |
| Transmission_Energy, Offload_Energy | mJ | Radio TX energy; total ESP32 energy when offloading |
| Server_CPU_Load, Edge_Processing_Time | %, ms | Edge utilisation and processing time |
| Offload_Total_Time | ms | Network + edge time |
| Battery_Price | – | λ(SOC) |
| Local_Execution_Cost, Offload_Execution_Cost | – | J_local, J_offload |
| Decision | – | LOCAL or OFFLOAD (always the cheaper cost) |

---

## Verification (`python validate_twin.py`)

The script checks, on the generated data:
- Renewable ↑ → SOC ↑
- Task size ↑ → CPU workload ↑
- Complexity ↑ → CPU load ↑ → local energy ↑
- Task size ↑ → transmission energy ↑
- Distance ↑ → RSSI ↓ → latency and retransmissions ↑
- Server load ↑ → edge time ↑
- SOC ↓ → energy price ↑
- The battery energy balance closes
- Decision = argmin(cost)
- Every signal is continuous in time

It also prints a controlled **what-if** table (SOC × RSSI) that shows the battery × network
interaction. The dashboard shows the same results in a collapsed *Engineering verification* panel.

## Optional realistic 3D models

Put `.glb` files in `twin3d/assets/` and list them in `twin3d/assets/models.js`, for example:

```js
window.TWIN_GLB_MODELS = { solar: 'assets/solar_panel.glb', server: 'assets/server_rack.glb' };
```

Each model replaces the procedural one, scaled and placed at the same spot. Browsers block
GLB loading from `file://`, so serve the folder with `python -m http.server` when using
the web viewer with GLB files.

## Assumptions / limitations
- One task per minute.
- Every parameter value is a datasheet-level approximation, not a measurement.
- The node's distance to the access point drifts because the node is assumed to be on moving equipment.
- MQTT, TCP and 802.11 behaviour are modelled analytically (overheads, rates and PER), not packet-by-packet.
