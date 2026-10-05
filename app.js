/* ========================================================
   Renewable-Aware IoT Task Offloading Digital Twin
   app.js — WEB VIEWER (no physics here)
   --------------------------------------------------------
   All values come from the Python engine (digital_twin_simulator.py),
   which writes web_data.js. This file only plays that data back:
     • Architecture view : live module values + decision path
     • 3D Twin view      : shared Three.js scene (twin3d/scene.js)
     • Data Flow view    : per-task message sequence with real numbers
   ======================================================== */

'use strict';

// ────────────────────────────────────────────────
// DATA (one row per simulated minute)
// ────────────────────────────────────────────────
const DATA = window.TWIN_DATA || { columns: [], rows: [] };
const COL = Object.fromEntries(DATA.columns.map((c, i) => [c, i]));

/** Row i of the dataset as an object: { Step, Timestamp, Battery_SOC, ... } */
function record(i) {
  const row = DATA.rows[i];
  const r = {};
  for (const c in COL) r[c] = row[COL[c]];
  return r;
}

// Cumulative OFFLOAD count up to every row (for the "Tasks Offloaded" KPI)
const offloadedSoFar = [];
DATA.rows.reduce((n, row, i) => (offloadedSoFar[i] = n + (row[COL.Decision] === 'OFFLOAD' ? 1 : 0)), 0);

// ────────────────────────────────────────────────
// PLAYBACK STATE
// ────────────────────────────────────────────────
const state = {
  index: 0,            // current row
  playing: false,
  timer: null,
  speedMs: 1500,       // real time per simulated task
  current: null,       // current record object
};
let twin3d = null;     // created when the 3D tab is first opened

// ────────────────────────────────────────────────
// HELPERS
// ────────────────────────────────────────────────
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const fmt = (v, d = 1) => Number(v).toFixed(d);
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// ────────────────────────────────────────────────
// MODULE PANEL DEFINITIONS (values + the equation behind them)
// ────────────────────────────────────────────────
const moduleInfo = {
  renewable: {
    icon: '☀️', name: 'Solar PV', id: 'MODULE-01', color: '#facc15',
    desc: 'P_PV = P_rated · G/G_STC · η_PV. Irradiance follows the sun position and a smoothly drifting cloud factor; the daily weather follows a Markov chain.',
    metrics: r => [
      { label: 'Solar_Irradiance (G)',   value: `${fmt(r.Solar_Irradiance, 0)} W/m²`, bar: r.Solar_Irradiance / 1000 },
      { label: 'Renewable_Power (P_PV)', value: `${fmt(r.Renewable_Power, 3)} W`,     bar: r.Renewable_Power / 1.0 },
      { label: 'Weather',                value: r.Weather,                             bar: null },
    ],
  },
  battery: {
    icon: '🔋', name: 'Battery', id: 'MODULE-02', color: '#34d399',
    desc: 'SOC += η_c·P_charge·Δt/E_bat − P_discharge·Δt/(η_d·E_bat). The energy of the chosen action is part of P_load, so every decision changes the battery.',
    metrics: r => [
      { label: 'Battery_SOC',             value: `${fmt(r.Battery_SOC, 2)} %`,            bar: r.Battery_SOC / 100 },
      { label: 'Battery_Charge_Power',    value: `${fmt(r.Battery_Charge_Power, 3)} W`,   bar: r.Battery_Charge_Power / 0.85 },
      { label: 'Battery_Discharge_Power', value: `${fmt(r.Battery_Discharge_Power, 3)} W`, bar: r.Battery_Discharge_Power / 0.3 },
      { label: 'Load_Power',              value: `${fmt(r.Load_Power, 3)} W`,             bar: r.Load_Power / 0.3 },
      { label: 'dSOC/dt',                 value: `${fmt(r.dSOC_dt, 4)} %/min`,            bar: null },
    ],
  },
  esp32: {
    icon: '📟', name: 'ESP32 IoT Node', id: 'MODULE-03', color: '#22d3ee',
    desc: 'C = D·c cycles. CPU_Load = Background + C/(f·T_deadline)·100. E_local = (P_idle + α·CPU_Load)·T_local.',
    metrics: r => [
      { label: 'Task',            value: `${r.Task_ID} · ${r.Task_Type}`,           bar: null },
      { label: 'Task_Size',       value: `${fmt(r.Task_Size, 1)} KB`,               bar: r.Task_Size / 600 },
      { label: 'Task_Complexity', value: `${fmt(r.Task_Complexity, 0)} cycles/B`,   bar: r.Task_Complexity / 3500 },
      { label: 'CPU_Load',        value: `${fmt(r.CPU_Load, 1)} %`,                 bar: r.CPU_Load / 100 },
      { label: 'Local_Exec_Time', value: `${fmt(r.Local_Exec_Time, 0)} ms`,         bar: r.Local_Exec_Time / 5000 },
      { label: 'Local_Energy',    value: `${fmt(r.Local_Energy, 1)} mJ`,            bar: r.Local_Energy / 1000 },
    ],
  },
  wifi: {
    icon: '📶', name: 'WiFi / MQTT Link', id: 'MODULE-04', color: '#c084fc',
    desc: 'RSSI = RSSI_0 − 10·n·log10(d/d0) + X_σ → MCS rate, PER → retransmissions. T_tx = Data/R_eff, E_tx = P_tx·T_tx.',
    metrics: r => [
      { label: 'Distance',            value: `${fmt(r.Distance, 1)} m`,               bar: r.Distance / 40 },
      { label: 'RSSI',                value: `${fmt(r.RSSI, 1)} dBm (MCS${r.WiFi_MCS})`, bar: (r.RSSI + 95) / 45 },
      { label: 'Data_Rate',           value: `${fmt(r.Data_Rate, 2)} Mbps`,           bar: r.Data_Rate / 20 },
      { label: 'PER / transmissions', value: `${fmt(100 * r.PER, 1)} % / ${fmt(r.Transmissions, 2)}`, bar: r.PER },
      { label: 'Network_Latency',     value: `${fmt(r.Network_Latency, 0)} ms`,       bar: r.Network_Latency / 1000 },
      { label: 'Transmission_Energy', value: `${fmt(r.Transmission_Energy, 1)} mJ`,   bar: r.Transmission_Energy / 500 },
    ],
  },
  edge: {
    icon: '🖥️', name: 'Edge Server', id: 'MODULE-05', color: '#818cf8',
    desc: 'T_edge = C / (f_edge·(1 − U_server)) — the M/M/1 sojourn form: processing time explodes as the server saturates.',
    metrics: r => [
      { label: 'Server_CPU_Load',      value: `${fmt(r.Server_CPU_Load, 1)} %`,        bar: r.Server_CPU_Load / 100 },
      { label: 'Edge_Processing_Time', value: `${fmt(r.Edge_Processing_Time, 0)} ms`,  bar: r.Edge_Processing_Time / 2000 },
      { label: 'Offload_Total_Time',   value: `${fmt(r.Offload_Total_Time, 0)} ms`,    bar: r.Offload_Total_Time / 3000 },
      { label: 'Offload_Energy',       value: `${fmt(r.Offload_Energy, 1)} mJ`,        bar: r.Offload_Energy / 1000 },
    ],
  },
  decision: {
    icon: '⚙️', name: 'Decision Engine', id: 'MODULE-06', color: '#f59e0b',
    desc: 'J = λ(SOC)·E/E_ref + T/T_deadline (+ link and server risk for offloading). The cheaper option wins — no thresholds, no randomness.',
    metrics: r => [
      { label: 'Decision',            value: r.Decision,                                bar: null },
      { label: 'Battery price λ(SOC)', value: fmt(r.Battery_Price, 3),                  bar: (r.Battery_Price - 1) / 4 },
      { label: 'J_local',             value: fmt(r.Local_Execution_Cost, 4),            bar: null },
      { label: 'J_offload',           value: fmt(r.Offload_Execution_Cost, 4),          bar: null },
      { label: 'Tasks offloaded',     value: String(offloadedSoFar[state.index]),       bar: null },
      { label: 'Tasks local',         value: String(state.index + 1 - offloadedSoFar[state.index]), bar: null },
    ],
    chips: r => [r.Decision === 'OFFLOAD'
      ? '<span class="panel-chip chip-offload">⚡ OFFLOAD to Edge</span>'
      : '<span class="panel-chip chip-local">💻 LOCAL on ESP32</span>'],
  },
};

// ────────────────────────────────────────────────
// SHOW ONE RECORD EVERYWHERE
// ────────────────────────────────────────────────
function show(i) {
  if (!DATA.rows.length) return;
  state.index = clamp(i, 0, DATA.rows.length - 1);
  const r = state.current = record(state.index);

  updateDOM(r);
  updateSVG(r);
  animateDecisionPath(r.Decision === 'OFFLOAD');
  addFlowStep(r);
  if (twin3d) twin3d.update(r, state.speedMs);
}

function updateDOM(r) {
  setText('kv-solar',    `${fmt(r.Renewable_Power, 2)} W`);
  setText('kv-battery',  `${fmt(r.Battery_SOC, 1)} %`);
  setText('kv-decision', r.Decision);
  setText('kv-latency',  `${fmt(r.Network_Latency, 0)} ms`);
  setText('kv-tasks',    String(offloadedSoFar[state.index]));
  const dv = document.getElementById('kv-decision');
  if (dv) dv.style.color = r.Decision === 'OFFLOAD' ? 'var(--blue)' : 'var(--cyan)';

  setText('sim-clock', `${r.Timestamp} · ${r.Weather} (1 step = 1 min)`);
  const jr = document.getElementById('jump-range');
  if (jr) jr.value = state.index;
  setText('jump-label', r.Timestamp);
  setText('footer-time', `Task ${r.Task_ID}`);

  const panel = document.getElementById('module-panel');
  if (panel && panel.dataset.module) updatePanel(panel.dataset.module);
}

function updateSVG(r) {
  setText('svg-solar',    `${fmt(r.Renewable_Power, 2)} W`);
  setText('svg-wind',     r.Weather);
  setText('svg-irrad',    `${fmt(r.Solar_Irradiance, 0)} W/m²`);
  setText('svg-soc',      `${fmt(r.Battery_SOC, 1)} %`);
  setText('svg-volt',     `${fmt(r.Battery_Charge_Power, 2)} W`);
  setText('svg-curr',     `${fmt(r.Load_Power, 2)} W`);
  setText('svg-cpu',      `${fmt(r.CPU_Load, 1)} %`);
  setText('svg-mem',      `${fmt(r.Task_Size, 0)} KB`);
  setText('svg-esp-pwr',  `${fmt(r.Task_Complexity, 0)} cyc/B`);
  setText('svg-rssi',     `${fmt(r.RSSI, 0)} dBm`);
  setText('svg-bw',       `${fmt(r.Data_Rate, 1)} Mbps`);
  setText('svg-lat',      `${fmt(r.Network_Latency, 0)} ms`);
  setText('svg-edge-cpu', `${fmt(r.Server_CPU_Load, 1)} %`);
  setText('svg-queue',    `${fmt(r.Edge_Processing_Time, 0)} ms`);
  setText('svg-edge-lat', `${fmt(r.Offload_Total_Time, 0)} ms`);
  setText('svg-mode',     r.Decision);
  setText('svg-score',    fmt(r.Local_Execution_Cost, 3));
  setText('svg-thresh',   fmt(r.Offload_Execution_Cost, 3));
  setText('svg-tasks',    String(state.index + 1));
}

function animateDecisionPath(offload) {
  const local = document.getElementById('path-local');
  const off = document.getElementById('path-offload');
  if (local) local.style.opacity = offload ? '0' : '1';
  if (off) off.style.opacity = offload ? '1' : '0';
}

// ────────────────────────────────────────────────
// MODULE PANEL
// ────────────────────────────────────────────────
function selectModule(key) {
  if (!moduleInfo[key]) return;
  document.querySelectorAll('.arch-node').forEach(n => n.classList.remove('selected'));
  const node = document.getElementById(`node-${key}`);
  if (node) node.classList.add('selected');
  document.getElementById('module-panel').dataset.module = key;
  updatePanel(key);
}

function updatePanel(key) {
  const info = moduleInfo[key];
  const r = state.current;
  if (!info || !r) return;
  setText('panel-icon', info.icon);
  setText('panel-name', info.name);
  setText('panel-id', info.id);

  let html = '';
  const chips = info.chips ? info.chips(r) : [];
  if (chips.length) html += `<div class="panel-section"><div class="panel-section-title">Current State</div><div>${chips.join('')}</div></div>`;
  html += '<div class="panel-section"><div class="panel-section-title">Live Values</div>';
  info.metrics(r).forEach(m => {
    html += `<div class="panel-metric"><span class="pm-label">${m.label}</span>
      <span class="pm-value" style="color:${info.color}">${m.value}</span></div>`;
    if (m.bar !== null && m.bar !== undefined) {
      html += `<div class="progress-bar"><div class="progress-fill" style="width:${clamp(m.bar * 100, 0, 100)}%;background:${info.color}"></div></div>`;
    }
  });
  html += `</div><div class="panel-section"><div class="panel-section-title">Model</div><div class="panel-desc">${info.desc}</div></div>`;
  document.getElementById('panel-body').innerHTML = html;
}

function closePanel() { selectModule('decision'); }

// ────────────────────────────────────────────────
// PLAYBACK CONTROLS
// ────────────────────────────────────────────────
function nextTask() {
  show((state.index + 1) % DATA.rows.length);
}

function toggleSimulation() {
  state.playing = !state.playing;
  ['btn-sim', 'btn-sim-3d'].forEach(id => {
    const b = document.getElementById(id);
    if (!b) return;
    b.textContent = state.playing ? '⏸ Pause' : '▶ Play';
    b.classList.toggle('running', state.playing);
  });
  clearInterval(state.timer);
  if (state.playing) state.timer = setInterval(nextTask, state.speedMs);
}

function updateSpeed(val) {
  state.speedMs = Number(val);
  setText('speed-label', `${(val / 1000).toFixed(1)}s`);
  if (state.playing) {
    clearInterval(state.timer);
    state.timer = setInterval(nextTask, state.speedMs);
  }
}

function triggerTask() {
  nextTask();
  flashNode('node-esp32');
  flashNode('node-decision');
}

function jumpTo(val) { show(Number(val)); }

function flashNode(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.add('flash');
  setTimeout(() => el.classList.remove('flash'), 1000);
}

// ────────────────────────────────────────────────
// DATA FLOW (sequence diagram with the engine's real numbers)
// ────────────────────────────────────────────────
const MAX_STEPS = 24;
const colIndex = { renewable: 0, battery: 1, esp32: 2, decision: 3, wifi: 4, edge: 5 };
const colColors = ['#facc15', '#34d399', '#22d3ee', '#f59e0b', '#c084fc', '#818cf8'];

function addFlowStep(r) {
  const container = document.getElementById('flow-steps');
  if (!container) return;
  buildFlowSteps(r).forEach(step => {
    while (container.children.length >= MAX_STEPS) container.removeChild(container.firstChild);
    const row = document.createElement('div');
    row.className = 'flow-step';
    for (let c = 0; c < 6; c++) {
      const cell = document.createElement('div');
      cell.className = 'flow-step-cell';
      if (c === step.from || c === step.to) {
        cell.classList.add('active');
        const badge = document.createElement('span');
        badge.className = 'step-badge';
        badge.style.background = `${colColors[c]}22`;
        badge.style.color = colColors[c];
        badge.style.border = `1px solid ${colColors[c]}55`;
        badge.textContent = c === step.from ? step.label : '→ recv';
        badge.title = step.detail || '';
        cell.appendChild(badge);
      }
      row.appendChild(cell);
    }
    container.appendChild(row);
  });
  container.lastChild && container.lastChild.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function buildFlowSteps(r) {
  const off = r.Decision === 'OFFLOAD';
  const steps = [
    { from: colIndex.renewable, to: colIndex.battery,
      label: `P_PV ${fmt(r.Renewable_Power, 2)} W`, detail: `G = ${fmt(r.Solar_Irradiance, 0)} W/m²` },
    { from: colIndex.battery, to: colIndex.decision,
      label: `SOC ${fmt(r.Battery_SOC, 1)}% λ=${fmt(r.Battery_Price, 2)}`, detail: 'Battery-risk price of energy' },
    { from: colIndex.esp32, to: colIndex.decision,
      label: `${r.Task_ID} ${fmt(r.Task_Size, 0)}KB ${fmt(r.CPU_Cycles, 0)}Mc`,
      detail: `${r.Task_Type}: T_local ${fmt(r.Local_Exec_Time, 0)} ms, E_local ${fmt(r.Local_Energy, 0)} mJ` },
    { from: colIndex.wifi, to: colIndex.decision,
      label: `RSSI ${fmt(r.RSSI, 0)} → ${fmt(r.Data_Rate, 1)}Mbps`,
      detail: `T_net ${fmt(r.Network_Latency, 0)} ms, E_tx ${fmt(r.Transmission_Energy, 0)} mJ` },
    { from: colIndex.edge, to: colIndex.decision,
      label: `U ${fmt(r.Server_CPU_Load, 0)}% T_edge ${fmt(r.Edge_Processing_Time, 0)}ms`, detail: 'T_edge = C/(f(1−U))' },
  ];
  steps.push(off
    ? { from: colIndex.decision, to: colIndex.wifi, label: `⚡ OFFLOAD ${fmt(r.Offload_Execution_Cost, 3)} < ${fmt(r.Local_Execution_Cost, 3)}`,
        detail: 'MQTT PUBLISH → gateway → edge server, result returned' }
    : { from: colIndex.decision, to: colIndex.esp32, label: `💻 LOCAL ${fmt(r.Local_Execution_Cost, 3)} < ${fmt(r.Offload_Execution_Cost, 3)}`,
        detail: 'ESP32 processes the task itself' });
  return steps;
}

// ────────────────────────────────────────────────
// VIEW SWITCHING
// ────────────────────────────────────────────────
function switchView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(`view-${name}`).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-view="${name}"]`).classList.add('active');

  // Build the 3D scene the first time its tab becomes visible (needs a real size)
  if (name === 'twin3d' && !twin3d && window.createTwinScene && window.THREE) {
    twin3d = createTwinScene(document.getElementById('twin3d-container'));
    if (state.current) twin3d.update(state.current, state.speedMs);
  }
}

// ────────────────────────────────────────────────
// INIT
// ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (!DATA.rows.length) {
    document.getElementById('data-missing').style.display = 'block';
    return;
  }
  const jr = document.getElementById('jump-range');
  if (jr) jr.max = DATA.rows.length - 1;
  show(0);
  selectModule('decision');
});
