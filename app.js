/* ========================================================
   Renewable-Aware IoT Task Offloading Digital Twin
   app.js — Simulation, Module Selection, Data Flow
   ======================================================== */

'use strict';

// ────────────────────────────────────────────────
// STATE
// ────────────────────────────────────────────────
// ── Canonical State Vector (8 state variables) ──────────────────────────────
//
//  s = [ Renewable_Availability, Battery_SOC, CPU_Load, Task_Size,
//         Task_Complexity, RSSI, Network_Latency, Server_CPU_Load ]
//
const sv = {
  Renewable_Availability : 65,   // 0 – 100 %
  Battery_SOC            : 72,   // 0 – 100 %
  CPU_Load               : 30,   // 0 – 100 %
  Task_Size              : 4.0,  // 1 – 10 MB
  Task_Complexity        : 5,    // 1 – 10  (ordinal)
  RSSI                   : -62,  // −90 to −40 dBm
  Network_Latency        : 35,   // 10 – 150 ms
  Server_CPU_Load        : 45,   // 0 – 100 %
};

const state = {
  simRunning: false,
  simInterval: null,
  simSpeed: 1500,
  tick: 0,
  tasksOffloaded: 0,
  tasksLocal: 0,

  // Derived / internal module data (supplements canonical sv)
  renewable: { solar: 0, wind: 0, irradiance: 0 },
  battery:   { voltage: 3.7, current: 0.4 },
  esp32:     { mem: 0, power: 0 },
  wifi:      { bw: 54, cost: 0 },
  edge:      { queue: 2, latency: 8 },
  decision:  { mode: '—', score: 0, threshold: 0.30 },
};

// ────────────────────────────────────────────────
// MODULE PANEL DEFINITIONS
// ────────────────────────────────────────────────
const moduleInfo = {
  renewable: {
    icon: '🌱',
    name: 'Renewable Availability',
    id: 'MODULE-01',
    color: '#34d399',
    desc: 'Monitors solar irradiance and wind speed to estimate instantaneous renewable power generation. Supplies an availability score (0–1) to the Decision Engine.',
    metrics: () => [
      { label: 'Renewable_Availability', value: `${sv.Renewable_Availability.toFixed(1)} %`,      bar: sv.Renewable_Availability / 100 },
      { label: 'Solar Power',            value: `${state.renewable.solar.toFixed(1)} W`,           bar: state.renewable.solar / 200 },
      { label: 'Wind Power',             value: `${state.renewable.wind.toFixed(1)} W`,            bar: state.renewable.wind / 100 },
      { label: 'Irradiance',             value: `${state.renewable.irradiance.toFixed(0)} W/m²`,  bar: state.renewable.irradiance / 1000 },
    ],
  },
  battery: {
    icon: '🔋',
    name: 'Battery Module',
    id: 'MODULE-02',
    color: '#fbbf24',
    desc: 'Tracks the battery State of Charge and enforces safe thresholds. Low SoC triggers conservative local execution to avoid deep discharge.',
    metrics: () => [
      { label: 'Battery_SOC',  value: `${sv.Battery_SOC.toFixed(1)} %`,           bar: sv.Battery_SOC / 100 },
      { label: 'Voltage',      value: `${state.battery.voltage.toFixed(2)} V`,     bar: (state.battery.voltage - 3.0) / 1.2 },
      { label: 'Current',      value: `${state.battery.current.toFixed(2)} A`,     bar: Math.min(Math.abs(state.battery.current) / 2, 1) },
      { label: 'Est. Runtime', value: estRuntime(),                                bar: sv.Battery_SOC / 100 },
    ],
  },
  esp32: {
    icon: '📟',
    name: 'ESP32 Device',
    id: 'MODULE-03',
    color: '#22d3ee',
    desc: 'Constrained IoT device that generates tasks and reports CPU, memory, and power consumption. High CPU load favours offloading.',
    metrics: () => [
      { label: 'CPU_Load',         value: `${sv.CPU_Load.toFixed(1)} %`,        bar: sv.CPU_Load / 100 },
      { label: 'Task_Size',        value: `${sv.Task_Size.toFixed(2)} MB`,       bar: (sv.Task_Size - 1) / 9 },
      { label: 'Task_Complexity',  value: `${sv.Task_Complexity} / 10`,          bar: (sv.Task_Complexity - 1) / 9 },
      { label: 'Free Memory',      value: `${state.esp32.mem.toFixed(0)} KB`,    bar: state.esp32.mem / 320 },
      { label: 'Power Draw',       value: `${state.esp32.power.toFixed(0)} mW`, bar: state.esp32.power / 500 },
    ],
  },
  wifi: {
    icon: '📶',
    name: 'WiFi Network',
    id: 'MODULE-04',
    color: '#a78bfa',
    desc: 'Measures RSSI, bandwidth, and round-trip latency. Poor signal quality increases transfer energy cost and may discourage offloading.',
    metrics: () => [
      { label: 'RSSI',            value: `${sv.RSSI.toFixed(0)} dBm`,              bar: (sv.RSSI + 90) / 50 },
      { label: 'Network_Latency', value: `${sv.Network_Latency.toFixed(1)} ms`,    bar: 1 - (sv.Network_Latency - 10) / 140 },
      { label: 'Bandwidth',       value: `${state.wifi.bw.toFixed(1)} Mbps`,       bar: state.wifi.bw / 100 },
      { label: 'Transfer Cost',   value: `${state.wifi.cost.toFixed(2)} mJ`,       bar: Math.min(state.wifi.cost / 50, 1) },
    ],
  },
  edge: {
    icon: '🖥️',
    name: 'Edge Server',
    id: 'MODULE-05',
    color: '#60a5fa',
    desc: 'Mobile Edge Computing server that processes offloaded tasks. If overloaded, the Decision Engine falls back to local execution.',
    metrics: () => [
      { label: 'Server_CPU_Load', value: `${sv.Server_CPU_Load.toFixed(1)} %`,
        bar: sv.Server_CPU_Load / 100 },
      { label: 'ρ (utilization)',  value: clamp(sv.Server_CPU_Load/100, 0, MODEL.rho_max).toFixed(3),
        bar: clamp(sv.Server_CPU_Load/100, 0, MODEL.rho_max) },
      { label: 'D_queue (M/M/1)', value: `${MODEL.D_queue.toFixed(1)} ms`,
        bar: Math.min(MODEL.D_queue / 500, 1) },
      { label: 'T_exec',          value: `${MODEL.T_exec.toFixed(0)} ms`,
        bar: Math.min(MODEL.T_exec / 200, 1) },
      { label: 'T_offload total', value: `${MODEL.T_offload.toFixed(0)} ms`,
        bar: Math.min(MODEL.T_offload / 600, 1) },
    ],
  },
  decision: {
    icon: '⚙️',
    name: 'Decision Engine',
    id: 'MODULE-06',
    color: '#f59e0b',
    desc: 'Aggregates telemetry from all modules and computes a weighted offloading score. Emits LOCAL or OFFLOAD directive each cycle.',
    metrics: () => [
      { label: 'Decision Mode',   value: state.decision.mode,                              bar: null },
      { label: 'Offload Score',   value: state.decision.score.toFixed(4),                  bar: clamp(state.decision.score, 0, 1) },
      { label: 'Threshold',       value: state.decision.threshold.toFixed(2),              bar: state.decision.threshold },
      { label: 'Deadline',        value: `${MODEL.Deadline} ms`,                           bar: null },
      { label: 'T_offload',       value: `${MODEL.T_offload.toFixed(0)} ms`,               bar: Math.min(MODEL.T_offload / MODEL.Deadline, 1) },
      { label: 'Deadline OK?',    value: MODEL.T_offload < MODEL.Deadline ? '✅ Yes' : '❌ No', bar: null },
      { label: 'Tasks Offloaded', value: String(state.tasksOffloaded),                     bar: null },
      { label: 'Tasks Local',     value: String(state.tasksLocal),                         bar: null },
    ],
    chips: () => state.decision.mode === 'OFFLOAD'
      ? ['<span class="panel-chip chip-offload">⚡ OFFLOAD to Edge</span>']
      : state.decision.mode === 'LOCAL'
        ? ['<span class="panel-chip chip-local">💻 LOCAL on ESP32</span>']
        : [],
  },
};

// ────────────────────────────────────────────────
// HELPERS
// ────────────────────────────────────────────────
function rand(min, max) { return Math.random() * (max - min) + min; }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function lerp(a, b, t) { return a + (b - a) * t; }

function estRuntime() {
  const h = Math.max(0, (sv.Battery_SOC / 100) * 6).toFixed(1);
  return `${h} h`;
}

// ════════════════════════════════════════════════════════════════════════════
// PHYSICAL CONSTANTS & MODEL PARAMETERS
// ════════════════════════════════════════════════════════════════════════════
const MODEL = {
  // Battery model
  eta_c       : 0.92,    // Charging efficiency
  eta_d       : 0.95,    // Discharging efficiency
  C_bat       : 20,      // Battery capacity [Wh]
  P_idle      : 150,     // ESP32 idle power [mW]
  P_max       : 560,     // ESP32 peak power [mW]
  P_rated     : 300,     // Total rated renewable power [W]
  k_charge    : 0.04,    // SoC gain per unit RA per tick (net)
  soc_min     : 5,       // Minimum safe SoC [%]
  soc_max     : 100,

  // CPU load model
  alpha_cpu   : 0.55,    // Exponential smoothing factor
  CPU_base    : 8,       // OS + firmware baseline [%]
  sigma_cpu   : 3,       // Process noise std dev [%]

  // WiFi / Latency model (Relationship 4)
  N0          : -95,     // Noise floor [dBm]
  B0          : 20,      // Channel bandwidth [MHz]
  L_prop      : 2,       // Propagation delay [ms]
  k_retry     : 1.5,     // Retry penalty coefficient [ms]
  sigma_lat   : 3,       // Latency process noise [ms]

  // M/M/1 queuing model (Relationship 5)
  D_svc       : 20,      // Mean edge service time per task [ms]
  rho_max     : 0.99,    // Clamp to avoid D_queue → ∞

  // Derived variables (computed each tick)
  P_esp32     : 150,     // [mW]  ESP32 instantaneous power
  C_wifi      : 54,      // [Mbps] Shannon throughput
  D_queue     : 0,       // [ms]  M/M/1 queuing delay
  T_exec      : 20,      // [ms]  Edge execution time
  T_offload   : 50,      // [ms]  Total offloading delay
  Deadline    : 300,     // [ms]  Task deadline
};

// ════════════════════════════════════════════════════════════════════════════
// SIMULATION TICK  — implements all 5 causal relationships
// ════════════════════════════════════════════════════════════════════════════
function simTick() {
  state.tick++;
  const t   = state.tick;
  const m   = MODEL;           // shorthand
  const dt  = 60;              // timestep [seconds] — 1 step = 1 minute

  // ─────────────────────────────────────────────────────────────────────────
  // EXOGENOUS INPUTS (driven by environment, 1440-min diurnal solar cycle)
  // ─────────────────────────────────────────────────────────────────────────

  // Minute of day [0 – 1439]: Sunrise 06:00 (t=360), Solar Noon 12:00 (t=720), Sunset 18:00 (t=1080)
  const minuteOfDay = t % 1440;
  const solarPhase  = (minuteOfDay - 360) / 720;
  const sunFactor   = (minuteOfDay >= 360 && minuteOfDay <= 1080)
    ? Math.max(0, Math.sin(solarPhase * Math.PI))
    : 0;

  state.renewable.solar      = clamp(sunFactor * 200 + rand(-10, 10), 0, 250);
  state.renewable.wind       = clamp(40 + rand(-25, 25), 0, 120);
  state.renewable.irradiance = clamp(sunFactor * 950 + rand(-30, 30), 0, 1000);

  // Renewable_Availability [0–100%] — fraction of P_rated being generated
  const P_gen = state.renewable.solar + state.renewable.wind;   // [W]
  sv.Renewable_Availability = clamp((P_gen / m.P_rated) * 100, 0, 100);

  // New task arrives each tick: Task_Size [1–10 MB], Task_Complexity [1–10]
  sv.Task_Size       = clamp(parseFloat(rand(1, 10).toFixed(2)), 1, 10);
  sv.Task_Complexity = clamp(Math.round(rand(1, 10)), 1, 10);
  m.Deadline         = Math.round(rand(150, 600));   // [ms]

  // RSSI drifts slowly (shadow fading model)  [−90 to −40 dBm]
  sv.RSSI = clamp(sv.RSSI + rand(-3, 3), -90, -40);

  // Server_CPU_Load drifts (Ornstein–Uhlenbeck mean-revert toward 50%)
  sv.Server_CPU_Load = clamp(
    sv.Server_CPU_Load + 0.15 * (50 - sv.Server_CPU_Load) + rand(-6, 6),
    0, 100
  );

  // ─────────────────────────────────────────────────────────────────────────
  // REL 3: Task_Size × Task_Complexity → CPU_Load
  //   C_target = (TS × TC / 100) × 100 + CPU_base
  //   CPU_Load[t+1] = α·CPU_Load[t] + (1−α)·C_target + ε
  // ─────────────────────────────────────────────────────────────────────────
  const C_target = clamp(
    (sv.Task_Size * sv.Task_Complexity / 100) * 100 + m.CPU_base,
    m.CPU_base, 100
  );
  sv.CPU_Load = clamp(
    m.alpha_cpu * sv.CPU_Load + (1 - m.alpha_cpu) * C_target + rand(-m.sigma_cpu, m.sigma_cpu),
    0, 100
  );

  // ─────────────────────────────────────────────────────────────────────────
  // REL 2: CPU_Load → ESP32 Power Draw
  //   P_esp32 = P_idle + (CPU_Load/100) × (P_max − P_idle)   [mW]
  // ─────────────────────────────────────────────────────────────────────────
  m.P_esp32     = m.P_idle + (sv.CPU_Load / 100) * (m.P_max - m.P_idle);
  state.esp32.power = m.P_esp32;

  // ─────────────────────────────────────────────────────────────────────────
  // REL 1 + REL 2: Renewable_Availability → Battery_SOC (charge)
  //                CPU_Load           → Battery_SOC (discharge)
  //
  //   P_charge  = max(0, RA/100 × P_rated − P_esp32/1000)   [W]
  //   ΔSOC_chg  = η_c × P_charge × dt / (C_bat × 3600) × 100
  //   ΔSOC_drn  = P_esp32 × dt / (η_d × C_bat × 3600 × 1000) × 100
  //   SOC[t+1]  = SOC[t] + ΔSOC_chg − ΔSOC_drn
  // ─────────────────────────────────────────────────────────────────────────
  const P_charge_W = Math.max(0, (sv.Renewable_Availability / 100) * m.P_rated - m.P_esp32 / 1000);
  const dSOC_chg   = (m.eta_c * P_charge_W * dt) / (m.C_bat * 3600) * 100;
  const dSOC_drn   = (m.P_esp32 * dt) / (m.eta_d * m.C_bat * 3600 * 1000) * 100;   // mW→W conversion

  sv.Battery_SOC = clamp(sv.Battery_SOC + dSOC_chg - dSOC_drn, m.soc_min, m.soc_max);

  // Derived battery state
  state.battery.current = parseFloat(((P_charge_W - m.P_esp32 / 1000) / 3.7).toFixed(3));   // [A]
  state.battery.voltage = clamp(3.0 + (sv.Battery_SOC / 100) * 1.2 + rand(-0.02, 0.02), 3.0, 4.2);
  state.esp32.mem       = clamp(rand(60, 300), 0, 320);

  // ─────────────────────────────────────────────────────────────────────────
  // REL 4: RSSI → Network_Latency  (Shannon + exponential retry penalty)
  //
  //   SNR      = RSSI − N0                                [dB]
  //   C_WiFi   = B0 × log2(1 + 10^(SNR/10))              [Mbps]
  //   L_tx     = Task_Size × 8 / C_WiFi                  [ms]
  //   P_retry  = k_retry × exp(−(RSSI+40)/20)            [ms]
  //   Latency  = L_prop + L_tx + P_retry + ε
  // ─────────────────────────────────────────────────────────────────────────
  const SNR      = sv.RSSI - m.N0;                                          // always ≥ 5 dB
  m.C_wifi       = clamp(m.B0 * Math.log2(1 + Math.pow(10, SNR / 10)), 1, 300);  // [Mbps]
  state.wifi.bw  = m.C_wifi;

  const L_tx     = (sv.Task_Size * 8) / m.C_wifi;                           // [ms]
  const P_retry  = m.k_retry * Math.exp(-(sv.RSSI + 40) / 20);              // [ms]
  const eps_lat  = rand(-m.sigma_lat, m.sigma_lat);
  sv.Network_Latency = clamp(m.L_prop + L_tx + P_retry + eps_lat, 10, 150);

  // WiFi transfer energy cost [mJ]
  state.wifi.cost = clamp((sv.Task_Size * 8 / m.C_wifi) * 250 / 1000, 0, 80);  // 250 mW radio power

  // ─────────────────────────────────────────────────────────────────────────
  // REL 5: Server_CPU_Load → Offloading Delay  (M/M/1 queuing model)
  //
  //   ρ         = Server_CPU_Load / 100            (utilization, clamped < 1)
  //   D_queue   = ρ / (1 − ρ) × D_svc             [ms]  M/M/1 mean waiting time
  //   T_exec    = D_svc × Task_Complexity          [ms]
  //   T_offload = Network_Latency + D_queue + T_exec
  // ─────────────────────────────────────────────────────────────────────────
  const rho      = clamp(sv.Server_CPU_Load / 100, 0, m.rho_max);
  m.D_queue      = (rho / (1 - rho)) * m.D_svc;
  m.T_exec       = m.D_svc * sv.Task_Complexity;
  m.T_offload    = sv.Network_Latency + m.D_queue + m.T_exec;

  state.edge.queue   = clamp(Math.floor(rho / (1 - rho) * 3), 0, 20);
  state.edge.latency = clamp(m.D_queue, 0, 500);

  // ─────────────────────────────────────────────────────────────────────────
  // DECISION ENGINE
  // ─────────────────────────────────────────────────────────────────────────
  //  Normalize all inputs to [0, 1]:
  //    R̂   = Renewable_Availability / 100
  //    B̂   = max(0, Battery_SOC − 20) / 80
  //    T̂c  = (Task_Complexity − 1) / 9      ← high complexity → reward offload
  //    Ŝ   = (RSSI + 90) / 50               ← signal quality
  //    L̂   = 1 − (Latency − 10) / 140       ← latency quality
  //    Ê   = 1 − ρ / (1 + ρ)               ← M/M/1-aware server availability
  //
  const alpha = 0.40, beta = 0.25, epsilon = 0.10;
  const gamma = 0.15, delta = 0.10;

  const R_hat  = sv.Renewable_Availability / 100;
  const B_hat  = clamp((sv.Battery_SOC - 20) / 80, 0, 1);
  const Tc_hat = (sv.Task_Complexity - 1) / 9;
  const S_hat  = clamp((sv.RSSI + 90) / 50, 0, 1);
  const L_hat  = clamp(1 - (sv.Network_Latency - 10) / 140, 0, 1);
  const E_hat  = clamp(1 - rho / (1 + rho), 0, 1);   // M/M/1-aware (non-linear)

  state.decision.score = clamp(
    alpha   * R_hat
    + beta  * B_hat
    + epsilon * Tc_hat
    - gamma * (1 - S_hat)
    - gamma * (1 - L_hat)
    - delta * (1 - E_hat),
    0, 1
  );

  // Hard gates
  const deadlineFeasible = m.T_offload < m.Deadline;
  const canOffload = sv.Battery_SOC > 30
    && state.decision.score >= state.decision.threshold
    && deadlineFeasible;

  state.decision.mode = canOffload ? 'OFFLOAD' : 'LOCAL';

  if (canOffload) state.tasksOffloaded++;
  else            state.tasksLocal++;

  updateDOM();
  updateSVG();
  animateDecisionPath(canOffload);
  addFlowStep();
}



// ────────────────────────────────────────────────
// DOM UPDATES
// ────────────────────────────────────────────────
function updateDOM() {
  // KPI bar — uses canonical state variables
  setText('kv-solar',    `${sv.Renewable_Availability.toFixed(1)} %`);
  setText('kv-battery',  `${sv.Battery_SOC.toFixed(1)} %`);
  setText('kv-decision', state.decision.mode);
  setText('kv-latency',  `${sv.Network_Latency.toFixed(0)} ms`);
  setText('kv-tasks',    String(state.tasksOffloaded));

  // Decision chip color
  const dv = document.getElementById('kv-decision');
  if (dv) {
    dv.style.color = state.decision.mode === 'OFFLOAD'
      ? 'var(--blue)' : state.decision.mode === 'LOCAL'
      ? 'var(--cyan)' : 'var(--text-primary)';
  }

  // Update simulation clock element
  const totalMins = state.tick;
  const days = Math.floor(totalMins / 1440) + 1;
  const hrs = Math.floor((totalMins % 1440) / 60).toString().padStart(2, '0');
  const mins = ((totalMins % 60)).toString().padStart(2, '0');
  setText('sim-clock', `Day ${days}, ${hrs}:${mins} (1 step = 1 min)`);

  // Footer time
  const ft = document.getElementById('footer-time');
  if (ft) ft.textContent = new Date().toLocaleTimeString();

  // Update panel if open
  const panel = document.getElementById('module-panel');
  if (panel && panel.dataset.module) updatePanel(panel.dataset.module);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function updateSVG() {
  // Renewable module node
  setText('svg-solar',    `${state.renewable.solar.toFixed(0)} W`);
  setText('svg-wind',     `${state.renewable.wind.toFixed(0)} W`);
  setText('svg-irrad',    `${sv.Renewable_Availability.toFixed(1)} %`);
  // Battery module node
  setText('svg-soc',      `${sv.Battery_SOC.toFixed(1)} %`);
  setText('svg-volt',     `${state.battery.voltage.toFixed(2)} V`);
  setText('svg-curr',     `${state.battery.current.toFixed(2)} A`);
  // ESP32 module node
  setText('svg-cpu',      `${sv.CPU_Load.toFixed(1)} %`);
  setText('svg-mem',      `${sv.Task_Size.toFixed(2)} MB`);
  setText('svg-esp-pwr',  `Cmplx: ${sv.Task_Complexity}/10`);
  // WiFi module node
  setText('svg-rssi',     `${sv.RSSI.toFixed(0)} dBm`);
  setText('svg-bw',       `${state.wifi.bw.toFixed(1)} Mbps`);
  setText('svg-lat',      `${sv.Network_Latency.toFixed(0)} ms`);
  // Edge module node
  setText('svg-edge-cpu', `${sv.Server_CPU_Load.toFixed(1)} %`);
  setText('svg-queue',    `${state.edge.queue} tasks`);
  setText('svg-edge-lat', `${state.edge.latency.toFixed(1)} ms`);
  // Decision node
  setText('svg-mode',     state.decision.mode);
  setText('svg-score',    state.decision.score.toFixed(3));
  setText('svg-thresh',   `${(state.decision.threshold * 100).toFixed(0)} %`);
  setText('svg-tasks',    String(state.tasksOffloaded + state.tasksLocal));
}

function animateDecisionPath(offload) {
  const local   = document.getElementById('path-local');
  const offloadP = document.getElementById('path-offload');
  if (offload) {
    if (offloadP) offloadP.style.opacity = '1';
    if (local)    local.style.opacity    = '0';
  } else {
    if (local)    local.style.opacity    = '1';
    if (offloadP) offloadP.style.opacity = '0';
  }
}

// ────────────────────────────────────────────────
// MODULE PANEL
// ────────────────────────────────────────────────
let selectedModule = 'decision';

function selectModule(key) {
  selectedModule = key;
  const info = moduleInfo[key];
  if (!info) return;

  // Highlight selected node
  document.querySelectorAll('.arch-node').forEach(n => n.classList.remove('selected'));
  const node = document.getElementById(`node-${key}`);
  if (node) node.classList.add('selected');

  updatePanel(key);
  document.getElementById('module-panel').dataset.module = key;
}

function updatePanel(key) {
  const info = moduleInfo[key];
  if (!info) return;

  setText('panel-icon', info.icon);
  setText('panel-name', info.name);
  setText('panel-id',   info.id);

  const metrics = info.metrics();
  const chips   = info.chips ? info.chips() : [];

  let html = '';

  if (chips.length) {
    html += `<div class="panel-section"><div class="panel-section-title">Current State</div><div>${chips.join('')}</div></div>`;
  }

  html += '<div class="panel-section"><div class="panel-section-title">Live Metrics</div>';
  metrics.forEach(m => {
    html += `<div class="panel-metric">
      <span class="pm-label">${m.label}</span>
      <span class="pm-value" style="color:${info.color}">${m.value}</span>
    </div>`;
    if (m.bar !== null && m.bar !== undefined) {
      const pct = clamp(m.bar * 100, 0, 100);
      html += `<div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${info.color}"></div></div>`;
    }
  });
  html += '</div>';

  html += `<div class="panel-section"><div class="panel-section-title">Description</div>
    <div class="panel-desc">${info.desc}</div>
  </div>`;

  document.getElementById('panel-body').innerHTML = html;
}

function closePanel() {
  document.querySelectorAll('.arch-node').forEach(n => n.classList.remove('selected'));
  const node = document.getElementById('node-decision');
  if (node) node.classList.add('selected');
  selectModule('decision');
}

// ────────────────────────────────────────────────
// SIMULATION CONTROLS
// ────────────────────────────────────────────────
function toggleSimulation() {
  state.simRunning = !state.simRunning;
  const btn = document.getElementById('btn-sim');
  if (state.simRunning) {
    btn.textContent = '⏸ Pause Simulation';
    btn.classList.add('running');
    state.simInterval = setInterval(simTick, state.simSpeed);
  } else {
    btn.textContent = '▶ Start Simulation';
    btn.classList.remove('running');
    clearInterval(state.simInterval);
  }
}

function updateSpeed(val) {
  state.simSpeed = Number(val);
  document.getElementById('speed-label').textContent = `${(val / 1000).toFixed(1)}s`;
  if (state.simRunning) {
    clearInterval(state.simInterval);
    state.simInterval = setInterval(simTick, state.simSpeed);
  }
}

function triggerTask() {
  // Single manual tick
  simTick();
  flashNode('node-esp32');
  flashNode('node-decision');
}

function flashNode(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('flash');
  setTimeout(() => el.classList.remove('flash'), 1000);
}

// ────────────────────────────────────────────────
// DATA FLOW STEPS (SEQUENCE DIAGRAM)
// ────────────────────────────────────────────────
const MAX_STEPS = 20;
let flowStepCount = 0;

const colIndex = {
  renewable: 0,
  battery:   1,
  esp32:     2,
  decision:  3,
  wifi:      4,
  edge:      5,
};
const colColors = ['#34d399', '#fbbf24', '#22d3ee', '#f59e0b', '#a78bfa', '#60a5fa'];
const colLabels = ['Renewable', 'Battery', 'ESP32', 'Decision', 'WiFi', 'Edge'];

function addFlowStep() {
  const container = document.getElementById('flow-steps');
  if (!container) return;

  // Build the sequence of micro-steps for this tick
  const steps = buildFlowSteps();
  steps.forEach(step => {
    if (flowStepCount >= MAX_STEPS) {
      // Remove oldest
      if (container.firstChild) container.removeChild(container.firstChild);
      flowStepCount--;
    }

    const row = document.createElement('div');
    row.className = 'flow-step';

    for (let c = 0; c < 6; c++) {
      const cell = document.createElement('div');
      cell.className = 'flow-step-cell';

      if (c === step.from || c === step.to) {
        cell.classList.add('active');
        const badge = document.createElement('span');
        badge.className = 'step-badge';
        badge.style.background = `${colColors[c]}18`;
        badge.style.color       = colColors[c];
        badge.style.border      = `1px solid ${colColors[c]}40`;

        if (c === step.from) {
          badge.textContent = step.label;
          badge.title       = step.detail || '';
        } else {
          badge.textContent = '→ recv';
        }
        cell.appendChild(badge);
      }

      row.appendChild(cell);
    }

    container.appendChild(row);
    flowStepCount++;
    row.scrollIntoView({ behavior: 'smooth', block: 'end' });
  });
}

function buildFlowSteps() {
  const isOffload = state.decision.mode === 'OFFLOAD';
  return [
    // Each row: canonical variable name → Decision Engine
    { from: colIndex.renewable, to: colIndex.decision,
      label:  `RA: ${sv.Renewable_Availability.toFixed(0)}%`,
      detail: `Renewable_Availability = ${sv.Renewable_Availability.toFixed(1)} %` },
    { from: colIndex.battery,   to: colIndex.decision,
      label:  `SOC: ${sv.Battery_SOC.toFixed(0)}%`,
      detail: `Battery_SOC = ${sv.Battery_SOC.toFixed(1)} %` },
    { from: colIndex.esp32,     to: colIndex.decision,
      label:  `CPU: ${sv.CPU_Load.toFixed(0)}% Tc:${sv.Task_Complexity}`,
      detail: `CPU_Load=${sv.CPU_Load.toFixed(0)}%  Task_Size=${sv.Task_Size.toFixed(1)}MB  Complexity=${sv.Task_Complexity}` },
    { from: colIndex.wifi,      to: colIndex.decision,
      label:  `RSSI:${sv.RSSI.toFixed(0)} Lat:${sv.Network_Latency.toFixed(0)}ms`,
      detail: `RSSI = ${sv.RSSI} dBm  |  Network_Latency = ${sv.Network_Latency.toFixed(0)} ms` },
    { from: colIndex.edge,      to: colIndex.decision,
      label:  `Srv: ${sv.Server_CPU_Load.toFixed(0)}%`,
      detail: `Server_CPU_Load = ${sv.Server_CPU_Load.toFixed(1)} %` },
    isOffload
      ? { from: colIndex.decision, to: colIndex.edge,
          label:  `⚡ OFFLOAD`,
          detail: `Score ${state.decision.score.toFixed(3)} ≥ ${state.decision.threshold} AND SOC > 30%` }
      : { from: colIndex.decision, to: colIndex.esp32,
          label:  `💻 LOCAL`,
          detail: `Score ${state.decision.score.toFixed(3)} < ${state.decision.threshold} OR SOC ≤ 30%` },
  ];
}

// ────────────────────────────────────────────────
// VIEW SWITCHING
// ────────────────────────────────────────────────
function switchView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(`view-${name}`).classList.add('active');

  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-view="${name}"]`).classList.add('active');
}

// ────────────────────────────────────────────────
// INIT
// ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Initial static render
  selectModule('decision');

  // Run one tick immediately to populate values
  simTick();

  // Footer clock
  setInterval(() => {
    const ft = document.getElementById('footer-time');
    if (ft) ft.textContent = new Date().toLocaleTimeString();
  }, 1000);
});
