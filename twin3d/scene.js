/* ============================================================================
   Shared 3D Digital Twin Scene  (Three.js r128)
   ----------------------------------------------------------------------------
   Used by BOTH front-ends, so there is only one 3D implementation:
     • twin3d/index.html  → Streamlit component (streamlit_app.py)
     • index.html         → web viewer (app.js)

   API
     const twin = createTwinScene(containerElement, { glb: {...} });
     twin.update(record, intervalMs);   // record = one row of the simulation dataset

   Everything shown here is driven by the simulation record:
     Solar_Irradiance / Renewable_Power → sun height, sky colour, panel glow, PV→battery flow
     Battery_SOC                        → battery fill level and colour
     CPU_Load                           → ESP32 chip glow
     RSSI                               → WiFi wave colour / strength
     Server_CPU_Load                    → server glow and LED activity
     Decision + timings                 → per-task animation (packet or local processing)

   Timing: the real task timings (ms) are shown in the labels. The animation
   compresses them logarithmically so every stage stays visible on screen.
   ========================================================================== */
(function () {
  'use strict';

  // Folder of this script → optional GLB paths are resolved relative to twin3d/
  const SCRIPT_BASE = document.currentScript ? document.currentScript.src.replace(/[^/]*$/, '') : '';

  // ── Layout of the physical chain: PV → Battery → ESP32 → Gateway → Edge ──
  const POS = {
    solar:   new THREE.Vector3(-10, 0, -1.5),
    battery: new THREE.Vector3(-5.2, 0, 0.5),
    esp32:   new THREE.Vector3(-0.8, 0, 1.8),
    gateway: new THREE.Vector3(4.2, 0, -1.2),
    server:  new THREE.Vector3(9.2, 0, 0.5),
  };
  // Points the packets fly between
  const PORT = {
    esp32:   new THREE.Vector3(-0.8, 1.0, 1.8),
    gateway: new THREE.Vector3(4.2, 4.6, -1.2),
    server:  new THREE.Vector3(9.2, 2.6, 1.7),
  };
  const C = {                       // vibrant palette
    sun: 0xffc53d, solar: 0x38bdf8, charge: 0xfacc15, power: 0x34d399,
    cpu: 0x22d3ee, packet: 0x60a5fa, result: 0x4ade80, wifi: 0xc084fc,
    server: 0x818cf8, local: 0x2dd4bf, danger: 0xf87171, warn: 0xfbbf24,
  };
  const P_RATED_W = 1.0;           // must match digital_twin_simulator.py

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const fmt = (v, d = 1) => (v === undefined || v === null || isNaN(v) ? '—' : Number(v).toFixed(d));

  // ── One-time CSS for the HTML overlays (labels, task card, stage bar) ────
  function injectStyles() {
    if (document.getElementById('twin3d-styles')) return;
    const css = `
    .t3-root{position:relative;width:100%;height:100%;overflow:hidden;font-family:Inter,system-ui,sans-serif;border-radius:14px}
    .t3-root canvas{display:block}
    .t3-hud{position:absolute;top:12px;left:12px;display:flex;gap:8px;flex-wrap:wrap;pointer-events:none}
    .t3-pill{background:rgba(10,14,35,.72);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.14);
      color:#f8fafc;border-radius:999px;padding:5px 12px;font-size:12px;font-weight:600}
    .t3-cams{position:absolute;top:12px;right:12px;display:flex;gap:6px}
    .t3-cams button{background:rgba(10,14,35,.72);color:#e2e8f0;border:1px solid rgba(255,255,255,.18);border-radius:8px;
      padding:5px 10px;font-size:11px;font-weight:700;cursor:pointer}
    .t3-cams button:hover{background:#22d3ee;color:#0b1020}
    .t3-label{position:absolute;transform:translate(-50%,-100%);pointer-events:none;white-space:nowrap;
      background:rgba(10,14,35,.78);border:1px solid var(--c);color:#fff;border-radius:8px;padding:3px 8px;
      font-size:11px;font-weight:700;box-shadow:0 0 12px var(--c)}
    .t3-label small{display:block;font-weight:500;color:#cbd5e1;font-size:10px}
    .t3-packet{position:absolute;transform:translate(-50%,-140%);pointer-events:none;white-space:nowrap;
      background:linear-gradient(135deg,#2563eb,#7c3aed);color:#fff;border-radius:6px;padding:2px 7px;
      font:700 10px 'JetBrains Mono',monospace;box-shadow:0 0 14px #60a5fa;display:none}
    .t3-packet.result{background:linear-gradient(135deg,#059669,#16a34a);box-shadow:0 0 14px #4ade80}
    .t3-stages{position:absolute;top:48px;left:50%;transform:translateX(-50%);display:flex;gap:4px;pointer-events:none}
    .t3-stage{background:rgba(10,14,35,.6);color:#94a3b8;border:1px solid rgba(255,255,255,.1);border-radius:999px;
      padding:3px 9px;font-size:10px;font-weight:700;transition:all .2s}
    .t3-stage.done{color:#e2e8f0;border-color:rgba(255,255,255,.3)}
    .t3-stage.active{background:var(--sc);color:#0b1020;border-color:var(--sc);box-shadow:0 0 12px var(--sc)}
    .t3-card{position:absolute;bottom:12px;left:12px;width:270px;background:rgba(10,14,35,.82);backdrop-filter:blur(10px);
      border:1px solid rgba(255,255,255,.14);border-radius:12px;color:#e2e8f0;font-size:11px;overflow:hidden}
    .t3-card-h{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;font-weight:800;font-size:12px;
      background:linear-gradient(90deg,rgba(34,211,238,.25),rgba(129,140,248,.25))}
    .t3-badge{padding:2px 9px;border-radius:999px;font-size:11px;font-weight:800;color:#0b1020}
    .t3-row{display:flex;justify-content:space-between;padding:3px 12px}
    .t3-row span:first-child{color:#94a3b8}
    .t3-row span:last-child{font-family:'JetBrains Mono',monospace;font-weight:700;color:#f8fafc}
    .t3-legend{position:absolute;bottom:12px;right:12px;display:flex;flex-direction:column;gap:4px;pointer-events:none}
    @media (max-width:640px){.t3-card{width:200px;font-size:10px}.t3-stages{display:none}.t3-legend{display:none}}`;
    const style = document.createElement('style');
    style.id = 'twin3d-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ═════════════════════════════════════════════════════════════════════════
  function createTwinScene(container, options = {}) {
    injectStyles();
    const root = document.createElement('div');
    root.className = 't3-root';
    container.appendChild(root);

    // ── Renderer, camera, controls ─────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    root.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0b1026, 30, 70);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI / 2 - 0.05;
    const VIEWS = {
      overview: [[0, 11, 21], [0, 1.5, 0]],
      energy:   [[-7, 6, 10], [-6, 1.5, 0]],
      network:  [[4, 7, 12], [4, 2, 0]],
    };
    let camTween = null;
    function setView(name) {
      const [p, t] = VIEWS[name];
      camTween = { from: camera.position.clone(), to: new THREE.Vector3(...p),
                   tFrom: controls.target.clone(), tTo: new THREE.Vector3(...t), k: 0 };
    }
    camera.position.set(...VIEWS.overview[0]);
    controls.target.set(...VIEWS.overview[1]);

    // ── Lights & sky ───────────────────────────────────────────────────────
    const hemi = new THREE.HemisphereLight(0xbfdcff, 0x1a2a1a, 0.5);
    scene.add(hemi);
    const sunLight = new THREE.DirectionalLight(0xfff1c1, 1.0);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.set(1024, 1024);
    Object.assign(sunLight.shadow.camera, { left: -18, right: 18, top: 18, bottom: -18 });
    scene.add(sunLight);
    const fill = new THREE.PointLight(0x7c3aed, 0.6, 40);
    fill.position.set(6, 8, 10);
    scene.add(fill);

    const sun = new THREE.Mesh(new THREE.SphereGeometry(1.1, 24, 24), new THREE.MeshBasicMaterial({ color: C.sun }));
    const sunGlow = new THREE.Mesh(new THREE.SphereGeometry(2.0, 24, 24),
      new THREE.MeshBasicMaterial({ color: C.sun, transparent: true, opacity: 0.25 }));
    sun.add(sunGlow);
    scene.add(sun);

    // Clouds: opacity follows the measured cloud attenuation (1 − G / G_clear)
    const clouds = new THREE.Group();
    const cloudMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, transparent: true, opacity: 0, roughness: 1 });
    [[-12, 13, -14], [-3, 15, -16], [7, 14, -15], [15, 12, -13]].forEach(([x, y, z]) => {
      const c = new THREE.Group();
      [[0, 0, 0, 1.6], [1.6, -0.2, 0, 1.2], [-1.5, -0.3, 0, 1.1], [0.5, 0.7, 0, 1.1]].forEach(([dx, dy, dz, r]) => {
        const s = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), cloudMat);
        s.position.set(dx, dy, dz);
        c.add(s);
      });
      c.position.set(x, y, z);
      clouds.add(c);
    });
    scene.add(clouds);

    // Ground
    const ground = new THREE.Mesh(new THREE.CircleGeometry(40, 64),
      new THREE.MeshStandardMaterial({ color: 0x14243a, roughness: 0.95 }));
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);
    const grid = new THREE.GridHelper(48, 48, 0x2b4a70, 0x1b304d);
    grid.position.y = 0.01;
    scene.add(grid);

    // ── Helpers to build meshes ────────────────────────────────────────────
    const std = (color, extra = {}) => new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.4, metalness: 0.5 }, extra));
    function box(w, h, d, mat, x = 0, y = 0, z = 0) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
      m.position.set(x, y, z);
      m.castShadow = true;
      return m;
    }
    function cyl(rt, rb, h, mat, x = 0, y = 0, z = 0, seg = 16) {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat);
      m.position.set(x, y, z);
      m.castShadow = true;
      return m;
    }
    function group(at) { const g = new THREE.Group(); g.position.copy(at); scene.add(g); return g; }

    // ── 1. Solar PV array ──────────────────────────────────────────────────
    const solarG = group(POS.solar);
    const steel = std(0x64748b, { metalness: 0.85, roughness: 0.3 });
    [-1.3, 1.3].forEach(x => {
      solarG.add(cyl(0.07, 0.07, 1.2, steel, x, 0.6, 1.0));
      solarG.add(cyl(0.07, 0.07, 2.6, steel, x, 1.3, -1.0));
    });
    const pvMat = std(0x0b2a5b, { emissive: C.solar, emissiveIntensity: 0, metalness: 0.7, roughness: 0.15 });
    const frameMat = std(0xcbd5e1, { metalness: 0.9, roughness: 0.25 });
    for (const i of [-1, 1]) for (const j of [-1, 1]) {
      const p = new THREE.Group();
      p.position.set(i * 1.0, 1.95, j * 1.05);
      p.rotation.x = 0.5;
      p.add(box(1.85, 0.1, 1.95, frameMat));
      const cell = box(1.72, 0.05, 1.82, pvMat, 0, 0.06, 0);
      cell.add(new THREE.LineSegments(new THREE.EdgesGeometry(cell.geometry),
        new THREE.LineBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.7 })));
      p.add(cell);
      solarG.add(p);
    }

    // ── 2. Battery (Li-ion pack in an enclosure) ───────────────────────────
    const batG = group(POS.battery);
    // Semi-transparent enclosure so the SOC fill inside stays visible
    const shell = box(2.2, 3.4, 1.8, std(0x94a3b8, { transparent: true, opacity: 0.22, metalness: 0.2, depthWrite: false }), 0, 1.7, 0);
    shell.castShadow = false;
    shell.add(new THREE.LineSegments(new THREE.EdgesGeometry(shell.geometry),
      new THREE.LineBasicMaterial({ color: 0xe2e8f0, transparent: true, opacity: 0.8 })));
    batG.add(shell);
    batG.add(box(2.3, 0.2, 1.9, std(0x1e293b), 0, 0.1, 0));                        // base plate
    for (const y of [0.925, 1.65, 2.375]) batG.add(box(1.85, 0.03, 1.45, std(0x0f172a), 0, y, 0)); // 25/50/75 % marks
    const fillMat = std(C.power, { emissive: C.power, emissiveIntensity: 0.7, roughness: 0.2, metalness: 0.1 });
    const batFill = box(1.8, 1, 1.4, fillMat, 0, 0.2, 0);
    batG.add(batFill);
    batG.add(box(0.6, 0.2, 0.4, std(0x94a3b8), 0, 3.5, 0));          // terminal

    // ── 3. ESP32 IoT node on a pedestal ────────────────────────────────────
    const espG = group(POS.esp32);
    espG.add(cyl(1.4, 1.7, 0.4, std(0x1e293b), 0, 0.2, 0, 32));
    espG.add(box(2.6, 0.12, 3.4, std(0x0d6b3a, { metalness: 0.2 }), 0, 0.46, 0));       // PCB
    espG.add(box(1.25, 0.2, 1.45, std(0xd1d5db, { metalness: 0.95, roughness: 0.15 }), 0, 0.62, -0.2)); // shield
    const chipMat = new THREE.MeshStandardMaterial({ color: 0x0b1020, emissive: C.cpu, emissiveIntensity: 0.3 });
    const chip = box(0.7, 0.05, 0.7, chipMat, 0, 0.75, -0.2);
    espG.add(chip);
    const pinMat = std(0xf59e0b, { metalness: 0.9 });
    for (let z = -1.5; z <= 1.5; z += 0.25) { espG.add(box(0.07, 0.3, 0.07, pinMat, -1.2, 0.42, z)); espG.add(box(0.07, 0.3, 0.07, pinMat, 1.2, 0.42, z)); }
    espG.add(box(1.5, 0.03, 0.5, std(0xf59e0b), 0, 0.53, 1.35));                         // PCB antenna
    // Local-processing ring (spins while the ESP32 executes a task)
    const localRing = new THREE.Mesh(new THREE.TorusGeometry(1.9, 0.07, 10, 64),
      new THREE.MeshBasicMaterial({ color: C.local, transparent: true, opacity: 0 }));
    localRing.rotation.x = Math.PI / 2;
    localRing.position.y = 0.8;
    espG.add(localRing);

    // ── 4. WiFi access point / gateway (MQTT broker host) ──────────────────
    const gwG = group(POS.gateway);
    gwG.add(cyl(0.12, 0.16, 4.2, steel, 0, 2.1, 0));
    gwG.add(box(1.3, 0.8, 0.5, std(0xf1f5f9, { metalness: 0.2, roughness: 0.5 }), 0, 4.4, 0));
    [-0.45, 0, 0.45].forEach((x, k) => {
      const a = cyl(0.05, 0.05, 1.1, std(0x0f172a), x, 5.3, 0);
      a.rotation.z = (k - 1) * 0.25;
      gwG.add(a);
    });
    const gwLed = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 12), new THREE.MeshBasicMaterial({ color: C.result }));
    gwLed.position.set(0.45, 4.4, 0.27);
    gwG.add(gwLed);

    // ── 5. Edge server rack ────────────────────────────────────────────────
    const srvG = group(POS.server);
    const rackMat = std(0x111827, { emissive: C.server, emissiveIntensity: 0.1, metalness: 0.6 });
    srvG.add(box(2.4, 4.4, 2.2, rackMat, 0, 2.2, 0));
    const leds = [];
    for (let y = 0.7; y <= 3.9; y += 0.6) {
      srvG.add(box(2.2, 0.46, 0.06, std(0x1f2937, { metalness: 0.8 }), 0, y, 1.12));
      for (let x = -0.6; x <= 0.61; x += 0.4) {
        const led = box(0.1, 0.08, 0.04, new THREE.MeshBasicMaterial({ color: 0x1e3a8a }), x, y, 1.16);
        srvG.add(led);
        leds.push(led);
      }
    }
    const edgeRing = new THREE.Mesh(new THREE.TorusGeometry(1.9, 0.07, 10, 64),
      new THREE.MeshBasicMaterial({ color: C.server, transparent: true, opacity: 0 }));
    edgeRing.rotation.x = Math.PI / 2;
    edgeRing.position.y = 0.1;
    srvG.add(edgeRing);

    // ── Power cables with flowing energy (PV → battery → ESP32) ───────────
    function makeFlow(points, color) {
      const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)));
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, 0.05, 6, false),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.35 }));
      scene.add(tube);
      const dots = [];
      for (let i = 0; i < 10; i++) {
        const d = new THREE.Mesh(new THREE.SphereGeometry(0.11, 10, 10), new THREE.MeshBasicMaterial({ color }));
        scene.add(d);
        dots.push(d);
      }
      return { curve, dots, tube, rate: 0, phase: 0 };
    }
    const pvFlow = makeFlow([[-9, 0.15, 0], [-7.5, 0.15, 0.8], [-6.2, 0.15, 1.2]], C.charge);
    const loadFlow = makeFlow([[-4.2, 0.15, 1.3], [-2.8, 0.15, 2.2], [-1.9, 0.3, 2.1]], C.power);

    // ── WiFi wave rings (emitted while the ESP32 transmits) ───────────────
    const waves = [];
    for (let i = 0; i < 3; i++) {
      const w = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.04, 8, 48),
        new THREE.MeshBasicMaterial({ color: C.wifi, transparent: true, opacity: 0 }));
      w.rotation.x = Math.PI / 2;
      scene.add(w);
      waves.push(w);
    }

    // ── Task packets ───────────────────────────────────────────────────────
    const packet = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.45, 0.45),
      new THREE.MeshStandardMaterial({ color: C.packet, emissive: C.packet, emissiveIntensity: 1.2 }));
    const result = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 16),
      new THREE.MeshStandardMaterial({ color: C.result, emissive: C.result, emissiveIntensity: 1.2 }));
    packet.visible = result.visible = false;
    scene.add(packet, result);

    // Optional realistic GLB/GLTF assets (fallback = procedural models above)
    loadOptionalModels(options.glb || window.TWIN_GLB_MODELS || {},
      { solar: solarG, battery: batG, esp32: espG, gateway: gwG, server: srvG });

    // ── HTML overlays ──────────────────────────────────────────────────────
    const hud = el('div', 't3-hud', root);
    const pillClock = el('div', 't3-pill', hud);
    const pillWeather = el('div', 't3-pill', hud);
    const pillProto = el('div', 't3-pill', hud);
    pillProto.textContent = '📡 MQTT over WiFi 802.11n (modelled)';

    const cams = el('div', 't3-cams', root);
    [['overview', '🛰 Overview'], ['energy', '⚡ Energy'], ['network', '📶 Network']].forEach(([k, t]) => {
      const b = el('button', '', cams);
      b.textContent = t;
      b.onclick = () => setView(k);
    });

    const stageBar = el('div', 't3-stages', root);
    const card = el('div', 't3-card', root);

    const labels = {
      solar:   makeLabel('#facc15', new THREE.Vector3(-10, 3.6, -1.5)),
      battery: makeLabel('#34d399', new THREE.Vector3(-5.2, 4.0, 0.5)),
      esp32:   makeLabel('#22d3ee', new THREE.Vector3(-0.8, 1.6, 1.8)),
      gateway: makeLabel('#c084fc', new THREE.Vector3(4.2, 6.1, -1.2)),
      server:  makeLabel('#818cf8', new THREE.Vector3(9.2, 4.9, 0.5)),
    };
    const packetTag = el('div', 't3-packet', root);
    const resultTag = el('div', 't3-packet result', root);

    function el(tag, cls, parent) { const e = document.createElement(tag); if (cls) e.className = cls; parent.appendChild(e); return e; }
    function makeLabel(color, at) {
      const e = el('div', 't3-label', root);
      e.style.setProperty('--c', color);
      return { e, at };
    }

    // ── Animated state (targets are set by update(), smoothed every frame) ─
    const target = { sunAngle: -0.3, irr: 0, cloud: 0, pv: 0, soc: 50, cpu: 10, srv: 20, rssiQ: 0.5, charging: 0, load: 0.14 };
    const shown = Object.assign({}, target);
    let task = null;            // current task animation plan
    let lastRecord = null;

    // ═══ update(): called once per simulation step ═════════════════════════
    function update(r, intervalMs = 1500) {
      if (!r) return;
      lastRecord = r;
      const h = Number(r.Hour);
      const clear = h > 6 && h < 18 ? 1000 * Math.sin(Math.PI * (h - 6) / 12) : 0;
      target.sunAngle = Math.PI * (h - 6) / 12;
      target.irr = Number(r.Solar_Irradiance) || 0;
      target.cloud = clear > 20 ? clamp(1 - target.irr / clear, 0, 1) : (r.Weather === 'Overcast' ? 0.7 : 0.2);
      target.pv = clamp((Number(r.Renewable_Power) || 0) / P_RATED_W, 0, 1);
      target.soc = Number(r.Battery_SOC);
      target.cpu = Number(r.CPU_Load);
      target.srv = Number(r.Server_CPU_Load);
      target.rssiQ = clamp((Number(r.RSSI) + 92) / 40, 0, 1);
      target.charging = Number(r.Battery_Charge_Power) || 0;
      target.load = Number(r.Load_Power) || 0.14;

      pillClock.textContent = `🕒 ${r.Timestamp}`;
      pillWeather.textContent = `${{ Sunny: '☀️', 'Partly Cloudy': '⛅', Overcast: '☁️' }[r.Weather] || '🌤'} ${r.Weather} · ${fmt(r.Solar_Irradiance, 0)} W/m²`;
      renderLabels(r);
      renderCard(r);
      task = planTask(r, intervalMs);
    }

    // Build the stage plan for this task. Visual durations ∝ log(1 + real ms).
    function planTask(r, intervalMs) {
      const total = clamp(intervalMs * 0.92, 500, 6000);
      const offload = r.Decision === 'OFFLOAD';
      const gw = 3;   // gateway + broker processing [ms] (T_GATEWAY_S)
      const stages = offload ? [
        { key: 'gen',  name: 'Task generated', ms: 2,  color: '#facc15' },
        { key: 'pkt',  name: 'MQTT packet',     ms: 2,  color: '#fb923c' },
        { key: 'tx',   name: `WiFi uplink ${fmt(r.Transmission_Time, 0)} ms`, ms: +r.Transmission_Time, color: '#c084fc' },
        { key: 'gw',   name: 'Gateway → Edge',  ms: gw, color: '#a78bfa' },
        { key: 'edge', name: `Edge ${fmt(r.Edge_Processing_Time, 0)} ms`, ms: +r.Edge_Processing_Time, color: '#818cf8' },
        { key: 'ret',  name: 'Result returned', ms: Math.max(1, r.Network_Latency - r.Transmission_Time - gw), color: '#4ade80' },
      ] : [
        { key: 'gen',  name: 'Task generated', ms: 2, color: '#facc15' },
        { key: 'cpu',  name: `ESP32 processing ${fmt(r.Local_Exec_Time, 0)} ms`, ms: +r.Local_Exec_Time, color: '#2dd4bf' },
        { key: 'done', name: 'Result ready', ms: 2, color: '#4ade80' },
      ];
      const weights = stages.map(s => Math.log1p(Math.max(0, s.ms)) + 0.6);
      const sum = weights.reduce((a, b) => a + b, 0);
      let t0 = 0;
      stages.forEach((s, i) => { s.start = t0; s.dur = total * weights[i] / sum; t0 += s.dur; });

      stageBar.innerHTML = '';
      stages.forEach(s => {
        const e = el('div', 't3-stage', stageBar);
        e.textContent = s.name;
        e.style.setProperty('--sc', s.color);
        s.el = e;
      });
      return { stages, offload, total, start: performance.now(), id: r.Task_ID, kb: r.Task_Size };
    }

    function renderLabels(r) {
      const charge = Number(r.Battery_Charge_Power) > 0;
      labels.solar.e.innerHTML = `☀️ ${fmt(r.Renewable_Power, 2)} W<small>P_PV = P_rated·G/G_STC·η</small>`;
      labels.battery.e.innerHTML = `🔋 ${fmt(r.Battery_SOC, 1)} %<small>${charge ? '▲ charging ' + fmt(r.Battery_Charge_Power, 2) : '▼ discharging ' + fmt(r.Battery_Discharge_Power, 2)} W</small>`;
      labels.esp32.e.innerHTML = `📟 ESP32 · CPU ${fmt(r.CPU_Load, 0)} %<small>${r.Task_Type}</small>`;
      labels.gateway.e.innerHTML = `📶 ${fmt(r.RSSI, 0)} dBm · MCS${r.WiFi_MCS}<small>${fmt(r.Data_Rate, 1)} Mbps · PER ${fmt(100 * r.PER, 1)} %</small>`;
      labels.server.e.innerHTML = `🖥️ Edge ${fmt(r.Server_CPU_Load, 0)} %<small>T_edge ${fmt(r.Edge_Processing_Time, 0)} ms</small>`;
    }

    function renderCard(r) {
      const off = r.Decision === 'OFFLOAD';
      const badge = `<span class="t3-badge" style="background:${off ? '#60a5fa' : '#2dd4bf'}">${off ? '⚡ OFFLOAD' : '💻 LOCAL'}</span>`;
      const rows = [
        ['Task', `${r.Task_ID} · ${r.Task_Type}`],
        ['Task size', `${fmt(r.Task_Size, 1)} KB`],
        ['Complexity', `${fmt(r.Task_Complexity, 0)} cycles/B`],
        ['Protocol', 'MQTT PUBLISH · QoS 1'],
        ['RSSI / rate', `${fmt(r.RSSI, 1)} dBm · ${fmt(r.Data_Rate, 1)} Mbps`],
        ['Network latency', `${fmt(r.Network_Latency, 0)} ms`],
        ['Local: time / energy', `${fmt(r.Local_Exec_Time, 0)} ms · ${fmt(r.Local_Energy, 0)} mJ`],
        ['Offload: time / energy', `${fmt(r.Offload_Total_Time, 0)} ms · ${fmt(r.Offload_Energy, 0)} mJ`],
        ['Cost J_local / J_off', `${fmt(r.Local_Execution_Cost, 3)} / ${fmt(r.Offload_Execution_Cost, 3)}`],
      ];
      card.innerHTML = `<div class="t3-card-h"><span>📦 Task Flow</span>${badge}</div>` +
        rows.map(([k, v]) => `<div class="t3-row"><span>${k}</span><span>${v}</span></div>`).join('') + '<div style="height:6px"></div>';
    }

    // ── Per-frame animation ────────────────────────────────────────────────
    const tmp = new THREE.Vector3();
    function placeTag(tag, obj) {
      tmp.copy(obj.position).project(camera);
      const w = root.clientWidth, h = root.clientHeight;
      tag.style.left = `${(tmp.x * 0.5 + 0.5) * w}px`;
      tag.style.top = `${(-tmp.y * 0.5 + 0.5) * h}px`;
      tag.style.display = tmp.z < 1 ? 'block' : 'none';
    }
    function along(a, b, k, arc) {
      const p = new THREE.Vector3().lerpVectors(a, b, k);
      p.y += Math.sin(k * Math.PI) * arc;
      return p;
    }

    function animateTask(now) {
      packet.visible = result.visible = false;
      packetTag.style.display = resultTag.style.display = 'none';
      localRing.material.opacity = 0;
      edgeRing.material.opacity = 0;
      waves.forEach(w => (w.material.opacity = 0));
      if (!task) return;

      const t = now - task.start;
      let cur = null;
      task.stages.forEach(s => {
        const active = t >= s.start && t < s.start + s.dur;
        s.el.classList.toggle('active', active);
        s.el.classList.toggle('done', t >= s.start + s.dur);
        if (active) cur = s;
      });
      if (!cur) return;
      const k = clamp((t - cur.start) / cur.dur, 0, 1);
      packetTag.textContent = `${task.id} · ${fmt(task.kb, 0)} KB`;
      resultTag.textContent = `${task.id} ✓ result`;

      switch (cur.key) {
        case 'gen': case 'pkt':
          packet.visible = true;
          packet.position.copy(PORT.esp32).add(new THREE.Vector3(0, 0.3 + k * 0.6, 0));
          packet.scale.setScalar(cur.key === 'gen' ? 0.3 + 0.7 * k : 1);
          placeTag(packetTag, packet);
          break;
        case 'tx':
          packet.visible = true;
          packet.scale.setScalar(1);
          packet.position.copy(along(PORT.esp32, PORT.gateway, k, 1.5));
          placeTag(packetTag, packet);
          waves.forEach((w, i) => {
            const ph = (k * 3 + i / 3) % 1;
            w.position.copy(PORT.esp32).add(new THREE.Vector3(0, 0.9, 0));
            w.scale.setScalar(1 + ph * 5);
            w.material.opacity = (1 - ph) * (0.25 + 0.6 * shown.rssiQ);
          });
          break;
        case 'gw':
          packet.visible = true;
          packet.position.copy(along(PORT.gateway, PORT.server, k, 0.8));
          placeTag(packetTag, packet);
          break;
        case 'edge':
          edgeRing.material.opacity = 0.9;
          edgeRing.rotation.z = now * 0.006;
          edgeRing.scale.setScalar(1 + 0.08 * Math.sin(now * 0.02));
          break;
        case 'ret':
          result.visible = true;
          result.position.copy(k < 0.5 ? along(PORT.server, PORT.gateway, k * 2, 0.8) : along(PORT.gateway, PORT.esp32, (k - 0.5) * 2, 1.5));
          placeTag(resultTag, result);
          break;
        case 'cpu':
          localRing.material.opacity = 0.95;
          localRing.rotation.z = now * 0.008;
          localRing.scale.setScalar(1 + 0.06 * Math.sin(now * 0.02));
          break;
        case 'done':
          result.visible = true;
          result.position.copy(PORT.esp32).add(new THREE.Vector3(0, 0.8 + k, 0));
          placeTag(resultTag, result);
          break;
      }
    }

    function flowStep(flow, rate, dt) {
      flow.phase = (flow.phase + dt * (0.15 + rate * 1.6)) % 1;
      flow.tube.material.opacity = rate > 0.01 ? 0.45 : 0.08;
      flow.dots.forEach((d, i) => {
        d.visible = rate > 0.01;
        d.position.copy(flow.curve.getPointAt(((flow.phase + i / flow.dots.length) % 1 + 1) % 1));
      });
    }

    const dayColor = new THREE.Color(0x3b82f6), nightColor = new THREE.Color(0x070b1f), duskColor = new THREE.Color(0xf97316);
    const skyColor = new THREE.Color();
    let prev = performance.now();
    function frame(now) {
      requestAnimationFrame(frame);
      const dt = clamp((now - prev) / 1000, 0, 0.05);   // first frame can be < prev
      prev = now;
      for (const k in target) shown[k] = lerp(shown[k], target[k], 0.06);

      // Sky + sun follow the simulated clock and irradiance
      const a = shown.sunAngle;
      const up = Math.sin(a);
      sun.visible = up > -0.05;
      sun.position.set(-26 * Math.cos(a), 2 + 20 * Math.max(0, up), -22);
      sunLight.position.copy(sun.position);
      const light = clamp(shown.irr / 1000, 0, 1);
      sunLight.intensity = 0.15 + 1.6 * light;
      hemi.intensity = 0.35 + 0.5 * light;
      const dayness = clamp(up * 1.6, 0, 1);
      skyColor.copy(nightColor).lerp(duskColor, clamp(1 - Math.abs(up) * 4, 0, 1) * (up > -0.2 ? 0.55 : 0));
      skyColor.lerp(dayColor, dayness * (1 - 0.55 * shown.cloud));
      scene.background = skyColor;
      scene.fog.color.copy(skyColor);
      cloudMat.opacity = clamp(0.15 + shown.cloud * 0.85, 0, 0.95) * (dayness > 0 ? 1 : 0.4);
      clouds.position.x = Math.sin(now * 0.00005) * 3;

      // Solar panel glow ∝ PV power
      pvMat.emissiveIntensity = 0.05 + shown.pv * 1.1;

      // Battery fill ∝ SOC (green > 60 %, amber 30–60 %, red < 30 %)
      const socFrac = clamp(shown.soc / 100, 0.02, 1);
      batFill.scale.y = socFrac * 2.9;
      batFill.position.y = 0.2 + socFrac * 2.9 / 2;
      const col = shown.soc > 60 ? C.power : shown.soc >= 30 ? C.warn : C.danger;
      fillMat.color.setHex(col);
      fillMat.emissive.setHex(col);
      fillMat.emissiveIntensity = 0.5 + 0.3 * Math.sin(now * 0.004);

      // ESP32 chip glow ∝ CPU load
      chipMat.emissiveIntensity = 0.2 + (shown.cpu / 100) * (1.6 + 0.6 * Math.sin(now * (0.005 + shown.cpu * 0.0004)));

      // Edge server glow + LED activity ∝ utilisation
      rackMat.emissiveIntensity = 0.05 + (shown.srv / 100) * 0.7;
      leds.forEach((led, i) => {
        const on = Math.sin(now * 0.004 * (1 + shown.srv / 12) + i * 1.7) > 1 - 2 * shown.srv / 100;
        led.material.color.setHex(on ? (shown.srv > 80 ? 0xf87171 : 0x60a5fa) : 0x1e3a8a);
      });
      gwLed.material.color.setHex(shown.rssiQ > 0.55 ? C.result : shown.rssiQ > 0.3 ? C.warn : C.danger);

      // Energy flows
      flowStep(pvFlow, clamp(shown.charging / 0.8, 0, 1), dt);
      flowStep(loadFlow, clamp(shown.load / 0.3, 0.05, 1), dt);

      animateTask(now);

      if (camTween) {
        camTween.k = Math.min(1, camTween.k + dt * 1.8);
        const e = 1 - Math.pow(1 - camTween.k, 3);
        camera.position.lerpVectors(camTween.from, camTween.to, e);
        controls.target.lerpVectors(camTween.tFrom, camTween.tTo, e);
        if (camTween.k >= 1) camTween = null;
      }
      controls.update();
      for (const key in labels) {
        const L = labels[key];
        tmp.copy(L.at).project(camera);
        L.e.style.left = `${(tmp.x * 0.5 + 0.5) * root.clientWidth}px`;
        L.e.style.top = `${(-tmp.y * 0.5 + 0.5) * root.clientHeight}px`;
      }
      renderer.render(scene, camera);
    }

    function resize() {
      const w = root.clientWidth || container.clientWidth || 800;
      const h = root.clientHeight || 520;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      if (w < 640 && !camTween) camera.position.set(0, 14, 30);
    }
    new ResizeObserver(resize).observe(root);
    resize();
    requestAnimationFrame(frame);

    return { update, setView, get lastRecord() { return lastRecord; } };
  }

  // ── Optional GLB/GLTF models ─────────────────────────────────────────────
  // window.TWIN_GLB_MODELS = { solar: 'assets/solar_panel.glb', ... } (see twin3d/assets/models.js)
  // Paths are relative to the twin3d/ folder, so both front-ends use the same entries.
  // A loaded model replaces the procedural one, scaled to the same footprint.
  function loadOptionalModels(map, groups) {
    if (!THREE.GLTFLoader) return;
    const loader = new THREE.GLTFLoader();
    Object.entries(map).forEach(([name, url]) => {
      const g = groups[name];
      if (!g || !url) return;
      loader.load(new URL(url, SCRIPT_BASE || window.location.href).href, gltf => {
        const model = gltf.scene;
        const size = new THREE.Box3().setFromObject(g).getSize(new THREE.Vector3());
        const mSize = new THREE.Box3().setFromObject(model).getSize(new THREE.Vector3());
        model.scale.setScalar(Math.max(size.x, size.y, size.z) / Math.max(mSize.x, mSize.y, mSize.z, 1e-6));
        const fit = new THREE.Box3().setFromObject(model);          // centre it and stand it on the ground
        const centre = fit.getCenter(new THREE.Vector3());
        model.position.set(-centre.x, -fit.min.y, -centre.z);
        const keep = g.children.filter(c => c.material && c.material.transparent); // keep animated rings
        g.children.slice().forEach(c => { if (!keep.includes(c)) g.remove(c); });
        g.add(model);
      }, undefined, () => console.info(`[twin3d] ${url} not found – using procedural ${name} model`));
    });
  }

  window.createTwinScene = createTwinScene;
})();
