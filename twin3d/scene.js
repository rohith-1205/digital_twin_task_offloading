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
  const C = {                       // restrained equipment and telemetry palette
    sun: 0xffc53d, solar: 0x38bdf8, charge: 0xfacc15, power: 0x34d399,
    cpu: 0x22d3ee, packet: 0x60a5fa, result: 0x4ade80, wifi: 0x38bdf8,
    server: 0x94a3b8, local: 0x2dd4bf, danger: 0xf87171, warn: 0xfbbf24,
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
    .t3-cams{position:absolute;top:12px;right:12px;display:flex;gap:5px;max-width:56%;flex-wrap:wrap;justify-content:flex-end}
    .t3-cams button{background:rgba(10,14,35,.72);color:#e2e8f0;border:1px solid rgba(255,255,255,.18);border-radius:8px;
      padding:5px 10px;font-size:11px;font-weight:700;cursor:pointer}
    .t3-cams button:hover,.t3-cams button.is-active{background:#5f94a5;color:#fff}
    .t3-cams button:disabled{opacity:.42;cursor:not-allowed}
    .t3-view{background:#13212c;color:#f0f3f3;border:1px solid #66808b;border-radius:5px;font-size:11px;padding:5px 8px;max-width:145px}
    .t3-mode{position:absolute;right:12px;bottom:12px;background:#101b27dc;padding:7px 10px;color:#b8c9cd;font-size:10px;pointer-events:none;border-radius:4px}
    .t3-loading{position:absolute;top:118px;right:12px;padding:6px 9px;background:#17232bf0;color:#d5e1e4;font-size:11px;border-radius:4px;display:none}
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
    .t3-row span:last-child{font-family:'JetBrains Mono',monospace;font-weight:700;color:#f8fafc;text-align:right}
    .t3-inspector{position:absolute;bottom:10px;left:305px;right:12px;padding:9px 12px;background:#111c27e8;border:1px solid #415362;border-radius:6px;color:#c4d1dc;font-size:11px;line-height:1.5;pointer-events:none}
    .t3-pill,.t3-label,.t3-stage,.t3-card,.t3-cams button{border-radius:5px;box-shadow:none;background:#101b27e8}
    .t3-label{border-color:#435565;border-left:3px solid var(--c);font-weight:600;padding:6px 9px;opacity:.9}
    .t3-card-h{background:#233342}.t3-packet,.t3-packet.result{background:#185d78;box-shadow:none}
    .t3-hud{max-width:42%;gap:4px}.t3-pill{font-size:10px}.t3-stages{top:84px;max-width:95%;flex-wrap:wrap;justify-content:center}
    .t3-card{width:280px}.t3-stage.active{box-shadow:none}
    @media(max-width:760px){.t3-hud{max-width:42%}.t3-cams{max-width:55%}.t3-inspector,.t3-mode{display:none}.t3-label{font-size:9px;padding:3px}.t3-label small{font-size:9px}}
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
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    root.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xaab8bd, 48, 125);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.minDistance = 1.2; controls.maxDistance = 80;
    controls.enablePan = true; controls.screenSpacePanning = true;
    controls.addEventListener("start", () => { camTween = null; followSignal = false; demoMode = false; controls.minDistance=1.2; updateModeButtons(); });
    controls.maxPolarAngle = Math.PI - 0.08;
    const VIEWS = {
      overview: [[16, 15, 31], [0, 1.8, 0]],
      front: [[0, 5, 32], [0, 2, 0]], rear: [[0, 6, -32], [0, 2, 0]],
      left: [[-31, 7, 0], [0, 2, 0]], right: [[31, 7, 0], [0, 2, 0]],
      top: [[0, 35, 0.01], [0, 0, 0]],
      solar: [[-9.5, 4.2, 5.7], [-10, 1.8, -1.5]],
      battery: [[-4.4, 3.0, 5], [-5.2, 1.8, 0.5]],
      esp32: [[-0.1, 2.5, 5.2], [-0.8, .68, 1.8]],
      gateway: [[5.6, 5.7, 6.2], [4.2, 3.6, -1.2]],
      server: [[9.2, 2.8, 3.55], [9.2, 2.25, 0.5]],
    };
    let camTween = null, followSignal = false, demoMode = false, demoStart = 0, demoIndex = -1;
    function setView(name) {
      const view = VIEWS[name]; if (!view) return;
      followSignal = false; controls.minDistance=1.2;
      if (name === 'esp32') espLid.material.opacity = .16;
      else espLid.material.opacity = .42;
      const [p,t] = view;
      camTween = {from:camera.position.clone(),to:new THREE.Vector3(...p),
        tFrom:controls.target.clone(),tTo:new THREE.Vector3(...t),k:0};
      camera.near = name === 'esp32' || name === 'server' ? .035 : .1;
      camera.updateProjectionMatrix();
    }
    camera.position.set(...VIEWS.overview[0]);
    controls.target.set(...VIEWS.overview[1]);

    // ── Lights & sky ───────────────────────────────────────────────────────
    const hemi = new THREE.HemisphereLight(0xbfdcff, 0x1a2a1a, 0.5);
    scene.add(hemi);
    const sunLight = new THREE.DirectionalLight(0xfff1c1, 1.0);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.set(2048, 2048);
    Object.assign(sunLight.shadow.camera, { left: -18, right: 18, top: 18, bottom: -18 });
    scene.add(sunLight);
    sunLight.shadow.normalBias = 0.035;
    sunLight.shadow.radius = 3;
    const fill = new THREE.DirectionalLight(0xd9e7ec, .42);
    fill.position.set(-8, 9, 14);
    scene.add(fill);

    const sun = new THREE.Mesh(new THREE.SphereGeometry(1.1, 24, 24), new THREE.MeshBasicMaterial({ color: C.sun }));
    const sunGlow = new THREE.Mesh(new THREE.SphereGeometry(2.0, 24, 24),
      new THREE.MeshBasicMaterial({ color: C.sun, transparent: true, opacity: 0.25 }));
    sun.add(sunGlow);
    scene.add(sun);

    // Soft cloud sprites are visual presentation of the recorded weather and
    // irradiance. They do not affect the simulation's solar equations.
    const cloudTexture=new THREE.TextureLoader().load(SCRIPT_BASE+'assets/textures/cloud_soft.png',
      () => {}, undefined, () => console.warn('[twin3d] cloud texture unavailable'));
    cloudTexture.encoding=THREE.sRGBEncoding;
    const cloudMat=new THREE.MeshBasicMaterial({map:cloudTexture,color:0xe8edee,
      transparent:true,opacity:0,depthWrite:false,side:THREE.DoubleSide,fog:false});
    const clouds=new THREE.Group();
    [[-15,15,-17,9],[-3,17,-20,11],[10,15,-18,10],[20,13,-16,8]].forEach(([x,y,z,w])=>{
      const plane=new THREE.Mesh(new THREE.PlaneGeometry(w,w*.34),cloudMat);
      plane.position.set(x,y,z);plane.renderOrder=2;clouds.add(plane);
    });
    scene.add(clouds);
    sunGlow.visible=false;

    // Atmospheric gradient dome avoids a flat colour backdrop; colours follow time and weather telemetry.
    const skyUniforms={zenith:{value:new THREE.Color(0x253c53)},horizon:{value:new THREE.Color(0x718895)}};
    const skyDome=new THREE.Mesh(new THREE.SphereGeometry(100,40,24),new THREE.ShaderMaterial({
      side:THREE.BackSide,depthWrite:false,fog:false,uniforms:skyUniforms,
      vertexShader:'varying vec3 vWorld; void main(){vWorld=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader:'varying vec3 vWorld;uniform vec3 zenith;uniform vec3 horizon;void main(){float h=clamp(vWorld.y/100.0,0.0,1.0);gl_FragColor=vec4(mix(horizon,zenith,smoothstep(0.0,0.72,h)),1.0);}'
    }));
    skyDome.frustumCulled=false;scene.add(skyDome);
    // Outdoor service lights illuminate the equipment when the recorded timestamp is at night.
    const yardLights=[];
    for(const x of [-6,6]){
      const lamp=new THREE.Group();lamp.position.set(x,0,5.8);scene.add(lamp);
      lamp.add(new THREE.Mesh(new THREE.CylinderGeometry(.055,.075,5.2,12),
        new THREE.MeshStandardMaterial({color:0x6f7777,metalness:.72,roughness:.39})));
      lamp.children[0].position.y=2.6;
      const head=new THREE.Mesh(new THREE.BoxGeometry(.8,.12,.45),
        new THREE.MeshStandardMaterial({color:0x555f63,metalness:.55,roughness:.42}));
      head.position.set(0,5.22,-.23);lamp.add(head);
      const luminaire=new THREE.Mesh(new THREE.PlaneGeometry(.7,.34),
        new THREE.MeshBasicMaterial({color:0xfff5d8,side:THREE.DoubleSide}));
      luminaire.rotation.x=Math.PI/2;luminaire.position.set(0,5.14,-.23);lamp.add(luminaire);
      const light=new THREE.PointLight(0xffedc6,1.8,17,2);light.position.set(0,4.9,-.3);lamp.add(light);
      yardLights.push({light,luminaire});
    }

    // Tiled, locally bundled surface textures. The visual seed is unrelated to simulation RNG.
    const textureLoader = new THREE.TextureLoader();
    function tiledTexture(file, x, y, colorSpace = true) {
      const texture = textureLoader.load(SCRIPT_BASE+'assets/textures/'+file,
        () => {}, undefined, () => console.warn('[twin3d] Missing texture:',file));
      texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
      texture.repeat.set(x,y);
      if (colorSpace) texture.encoding = THREE.sRGBEncoding;
      texture.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
      return texture;
    }
    const gravelTexture = tiledTexture('gravel.png', 12, 12);
    const concreteTexture = tiledTexture('concrete.png', 2, 2);
    const sidingTexture = tiledTexture('galvanized.png', 1, 1);
    const pvTexture = tiledTexture('pv_cells.png', 1, 1);
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(95,95),
      new THREE.MeshStandardMaterial({map:gravelTexture,roughness:1,metalness:0}));
    ground.rotation.x=-Math.PI/2;ground.position.y=-.02;ground.receiveShadow=true;scene.add(ground);

    // ── Helpers to build meshes ────────────────────────────────────────────
    const std = (color, extra = {}) => new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.4, metalness: 0.5 }, extra));
    function box(w, h, d, mat, x = 0, y = 0, z = 0) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
      m.position.set(x, y, z);
      m.castShadow = true; m.receiveShadow = true;
      return m;
    }
    function cyl(rt, rb, h, mat, x = 0, y = 0, z = 0, seg = 16) {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), mat);
      m.position.set(x, y, z);
      m.castShadow = true; m.receiveShadow = true;
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
    const pvMat = std(0x152c42, { emissive: 0x17324c, emissiveIntensity: .01, metalness: .37, roughness:.22 });
    const panelMat = new THREE.MeshStandardMaterial({map:pvTexture, roughness:.17, metalness:.28,
      emissive:0x092037, emissiveIntensity:0, side:THREE.DoubleSide});
    const frameMat = std(0xb2bac0, {metalness:.84,roughness:.31});
    const glassMat = std(0xa9cee1,{transparent:true,opacity:.10,metalness:.22,roughness:.12,depthWrite:false});
    for (const i of [-1,1]) for (const j of [-1,1]) {
      const panel = new THREE.Group();panel.position.set(i*1,1.94,j*1.05);
      panel.rotation.x=.48;
      panel.add(box(1.9,.11,2.01,frameMat));
      const face = new THREE.Mesh(new THREE.PlaneGeometry(1.77,1.88),panelMat);
      face.rotation.x=-Math.PI/2;face.position.y=.063;face.castShadow=true;panel.add(face);
      panel.add(box(1.76,.009,1.87,glassMat,0,.068,0));
      for(const x of [-.94,.94])panel.add(box(.045,.045,2.02,frameMat,x,.09,0));
      for(const z of [-1,1])panel.add(box(1.9,.045,.045,frameMat,0,.09,z));
      solarG.add(panel);
    }
    for(const x of [-1.3,1.3]){
      const brace=box(.08,.08,3.15,steel,x,1.56,0);brace.rotation.x=.48;solarG.add(brace);
    }

    // ── 2. Battery (Li-ion pack in an enclosure) ───────────────────────────
    const batG = group(POS.battery);
    const cabinet = std(0x697885, {metalness:.65, roughness:.38});
    batG.add(box(2.2,3.4,1.8,cabinet,0,1.8,0));
    batG.add(box(2.35,.2,1.95,std(0x202a34),0,.1,0));
    batG.add(box(1.98,3.12,.07,std(0x42515e),0,1.8,.94));
    batG.add(box(.12,.6,.12,steel,.78,1.8,1.03));
    for(let i=0;i<9;i++) batG.add(box(1.15,.045,.03,std(0x101923),-.15,.48+i*.09,1));
    batG.add(box(.43,2.98,.08,std(0x101923),-.65,1.75,1.02));
    const fillMat = std(C.power, {emissive:C.power,emissiveIntensity:.25});
    const batFill = box(.24,1,.05,fillMat,-.65,.2,1.08);
    batG.add(batFill);
    for(let i=0;i<=10;i++) batG.add(box(.1,.014,.04,steel,-.34,.2+i*.29,1.08));
    batG.add(box(.65,.32,.05,std(0x102d37),.22,2.9,1.02));
    // Powder-coated cabinet seams, weather gasket, stainless hinges and label plate.
    for(const x of [-1.04,1.04])batG.add(box(.045,3.25,.05,steel,x,1.8,1));
    for(const y of [.22,3.39])batG.add(box(2.1,.05,.05,steel,0,y,1));
    for(const y of [.62,2.95])batG.add(box(.1,.25,.12,steel,-1.12,y,1));
    batG.add(box(.56,.31,.04,std(0xd4d4c9,{metalness:.06,roughness:.8}),.2,2.9,1.05));
    for(const x of [-.42,.42])batG.add(cyl(.14,.14,.14,std(0x292f31),x,.21,-.85));

    // ── 3. ESP32 IoT node on a pedestal ────────────────────────────────────
    const espG = group(POS.esp32);
    espG.add(box(3.05,.16,3.85,std(0x888e8c,{roughness:.82}),0,.09,0));
    espG.add(box(2.6, 0.12, 3.4, std(0x0d6b3a, { metalness: 0.2 }), 0, 0.46, 0));       // PCB
    espG.add(box(1.25, 0.2, 1.45, std(0xd1d5db, { metalness: 0.95, roughness: 0.15 }), 0, 0.62, -0.2)); // shield
    const chipMat = new THREE.MeshStandardMaterial({ color: 0x0b1020, emissive: C.cpu, emissiveIntensity: 0.3 });
    const chip = box(0.7, 0.05, 0.7, chipMat, 0, 0.75, -0.2);
    espG.add(chip);
    const pinMat = std(0xf59e0b, { metalness: 0.9 });
    for (let z = -1.5; z <= 1.5; z += 0.25) { espG.add(box(0.07, 0.3, 0.07, pinMat, -1.2, 0.42, z)); espG.add(box(0.07, 0.3, 0.07, pinMat, 1.2, 0.42, z)); }
    for(let i=0;i<6;i++) {
      espG.add(box(.06,.025,.46,pinMat,-.65+i*.25,.54,1.35));
      if(i<5) espG.add(box(.25,.025,.05,pinMat,-.525+i*.25,.54,i%2?1.55:1.15));
    }
    espG.add(box(.65,.22,.35,steel,0,.6,-1.65));
    espG.add(box(.47,.12,.04,std(0x101923),0,.6,-1.84));
    for(const x of [-.88,.88]) for(let z=-1.2;z<.8;z+=.36) {
      espG.add(box(.16,.08,.22,std(0x22272d),x,.57,z));
      espG.add(box(.055,.015,.18,pinMat,x,.62,z));
    }
    for(const x of [-1,1]) for(const z of [-1.4,1.4]) espG.add(cyl(.07,.07,.035,steel,x,.55,z));                         // PCB antenna
    // Local-processing ring (spins while the ESP32 executes a task)
    const localRing = new THREE.Mesh(new THREE.TorusGeometry(.32, .018, 8, 40),
      new THREE.MeshBasicMaterial({ color: C.local, transparent: true, opacity: 0 }));
    localRing.rotation.x = Math.PI / 2;
    localRing.position.set(0,.84,-.2);
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
    gwG.add(box(.8,.15,.7,std(0x283541),0,.1,0));
    for(let i=0;i<7;i++) gwG.add(box(.6,.022,.02,std(0x344656),-.15,4.2+i*.055,.26));
    for(let i=0;i<3;i++) gwG.add(box(.16,.12,.03,std(0x101923),-.4+i*.2,4.12,.27));
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
    for(const x of [-1.12,1.12]) srvG.add(box(.09,4.2,.12,steel,x,2.2,1.2));
    // Patch panel, power distribution strip, structured cabling and cooling grilles.
    for(let i=0;i<12;i++) srvG.add(box(.12,.095,.03,std(0x0b141a),-.87+i*.16,4.14,1.18));
    for(let i=0;i<5;i++){
      const cable = new THREE.CatmullRomCurve3([
        new THREE.Vector3(-.8+i*.22,4.1,1.22),new THREE.Vector3(-.7+i*.18,3.75,1.52),
        new THREE.Vector3(.7,3.53-i*.15,1.23)]);
      srvG.add(new THREE.Mesh(new THREE.TubeGeometry(cable,18,.018,5,false),std(i%2?0x3d6880:0x3c5268,{roughness:.75,metalness:0})));
    }
    for(let y=.8;y<3.8;y+=.6)for(let x=-.8;x<.8;x+=.15)
      srvG.add(box(.045,.12,.02,std(0x10191e),x,y,1.22));
    for(let y=.7;y<=3.9;y+=.6) {
      for(let i=0;i<12;i++) srvG.add(box(.055,.22,.025,std(0x080f16),-.85+i*.105,y,1.17));
      srvG.add(box(.25,.12,.035,steel,.86,y,1.18));
      srvG.add(box(.18,.075,.04,std(0x0c1420),.86,y,1.21));
      for(const x of [-1,1]) srvG.add(cyl(.035,.035,.04,steel,x,y,1.18));
    }
    // Equipment plinths and a low cable tray keep the installation readable.
    for(const [key,g] of Object.entries({solar:solarG,battery:batG,gateway:gwG,server:srvG})) {
      g.add(box(key==='solar'?4.5:2.8,.12,key==='solar'?4.5:2.7,std(0x3c4650),0,.02,0));
    }
    scene.add(box(22,.08,.32,std(0x35434f),0,.09,-3.4));
    for(const x of [-10,-5.2,4.2,9.2]) scene.add(box(.14,.09,2.5,std(0x35434f),x,.1,-2.2));
    const edgeRing = new THREE.Mesh(new THREE.TorusGeometry(1.9, 0.07, 10, 64),
      new THREE.MeshBasicMaterial({ color: C.server, transparent: true, opacity: 0 }));
    edgeRing.rotation.x = Math.PI / 2;
    edgeRing.position.y = 0.1;
    srvG.add(edgeRing);

    // Outdoor industrial installation; decorative geometry never enters the engine.
    const concrete = new THREE.MeshStandardMaterial({map:concreteTexture,roughness:.96,metalness:0});
    const galvanized = new THREE.MeshStandardMaterial({map:sidingTexture,roughness:.56,metalness:.48});
    const enclosure = std(0xcbd0ce,{roughness:.55,metalness:.12});
    const darkRubber=std(0x252c2d,{metalness:0,roughness:.88});
    const plinth=box(28,.16,8.4,concrete,0,.025,-.5);scene.add(plinth);
    // Shallow site drainage lip and equipment service walk.
    scene.add(box(29,.12,.2,std(0x727a77,{roughness:.9}),0,.07,3.72));
    const walkway=box(26,.024,1.65,concrete,0,.13,3.05);scene.add(walkway);
    for(let x=-12.5;x<=12.5;x+=2.6)scene.add(box(.035,.025,1.65,darkRubber,x,.15,3.05));
    // Weatherproof hinged IP65 electronics enclosure, transparent inspection cover.
    espG.add(box(3.05,.16,3.85,galvanized,0,.15,0));
    espG.add(box(.14,1.18,3.85,enclosure,-1.55,.79,0));
    espG.add(box(.14,1.18,3.85,enclosure,1.55,.79,0));
    espG.add(box(3.1,1.18,.14,enclosure,0,.79,-1.95));
    espG.add(box(3.1,1.18,.14,enclosure,0,.79,1.95));
    const lidFrame = new THREE.Group();lidFrame.position.set(-1.53,1.45,0);lidFrame.rotation.z=.2;espG.add(lidFrame);
    lidFrame.add(box(.12,.12,3.84,enclosure,1.53,0,-1.86));
    lidFrame.add(box(.12,.12,3.84,enclosure,1.53,0,1.86));
    for(const z of [-1.85,1.85])lidFrame.add(box(3.05,.12,.1,enclosure,1.53,0,z));
    const espLid=box(2.9,.025,3.65,std(0x99b9c1,{transparent:true,opacity:.42,
      metalness:.1,roughness:.11,depthWrite:false}),1.53,0,0);lidFrame.add(espLid);
    for(const z of [-1.3,0,1.3]){
      const gland=cyl(.16,.18,.18,darkRubber,1.47,.34,z);espG.add(gland);
      const wire=new THREE.CatmullRomCurve3([
        new THREE.Vector3(1.45,.36,z),new THREE.Vector3(1.0,.47,z*.8),new THREE.Vector3(.7,.55,z*.55)]);
      espG.add(new THREE.Mesh(new THREE.TubeGeometry(wire,14,.028,6,false),
        std(z<0?0x395b68:0x754d38,{metalness:0,roughness:.7})));
    }
    for(const x of [-1.4,1.4])for(const z of [-1.75,1.75])espG.add(cyl(.06,.06,.035,steel,x,1.4,z));
    // Gateway mast, conduit drop, service box and realistic antenna radomes.
    gwG.add(box(.78,.9,.55,enclosure,0,3.35,0));
    gwG.add(box(.66,.77,.03,darkRubber,0,3.35,.29));
    for(let i=0;i<4;i++)gwG.add(box(.045,.08,.025,std(0x697775),-.25+i*.17,3.15,.315));
    const mastCable=new THREE.CatmullRomCurve3([
      new THREE.Vector3(.24,4.3,0),new THREE.Vector3(.39,3.8,-.25),
      new THREE.Vector3(.38,2,-.25),new THREE.Vector3(.38,.18,-.25)]);
    gwG.add(new THREE.Mesh(new THREE.TubeGeometry(mastCable,30,.035,8,false),darkRubber));
    // Prefabricated weatherproof shelter: ribbed siding, fascia, open door, HVAC.
    const shelter = new THREE.Group(); shelter.position.copy(POS.server); scene.add(shelter);
    const wall = new THREE.MeshStandardMaterial({map:sidingTexture,roughness:.72,metalness:.26,side:THREE.DoubleSide});
    shelter.add(box(5.3,.22,5.2,concrete,0,.06,-.2));
    shelter.add(box(5.25,5.5,.12,wall,0,2.84,-2.82));
    shelter.add(box(.12,5.5,5.0,wall,-2.62,2.84,-.25));
    shelter.add(box(.12,5.5,5.0,wall,2.62,2.84,-.25));
    shelter.add(box(5.55,.25,5.35,galvanized,0,5.71,-.25));
    // Front wall frames the rack service entrance; transparent glazing preserves visibility.
    for(const x of [-2.55,2.55])shelter.add(box(.14,5.4,.14,enclosure,x,2.85,2.2));
    shelter.add(box(5.1,.45,.15,enclosure,0,5.45,2.2));
    shelter.add(box(1.3,4.8,.12,wall,1.95,2.75,2.2));
    const doorPivot=new THREE.Group();doorPivot.position.set(-2.48,.26,2.2);doorPivot.rotation.y=-1.17;shelter.add(doorPivot);
    doorPivot.add(box(2.0,4.85,.09,enclosure,1,2.43,0));
    doorPivot.add(box(1.72,.13,.055,darkRubber,1,4.62,.055));
    doorPivot.add(box(.12,.42,.07,steel,1.76,2.35,.085));
    for(const x of [-2.5,2.5])for(const z of [-2.7,2.15])
      shelter.add(box(.09,5.3,.09,galvanized,x,2.83,z));
    for(let y=.8;y<4.8;y+=.18) shelter.add(box(.025,.025,.7,galvanized,2.73,y,-1.1));
    const ac=box(.45,1.65,1.53,enclosure,2.89,3.66,-.92);shelter.add(ac);
    const fan=new THREE.Mesh(new THREE.TorusGeometry(.49,.055,8,36),darkRubber);
    fan.rotation.y=Math.PI/2;fan.position.set(3.15,3.66,-.92);shelter.add(fan);
    for(let n=0;n<6;n++){
      const blade=box(.48,.07,.09,darkRubber,3.17,3.66,-.92);
      blade.rotation.x=n*Math.PI/3;shelter.add(blade);
    }
    shelter.add(box(.52,.09,1.7,galvanized,2.9,2.72,-.92));
    // Underground conduits terminate at equipment; modeled data-path animation is separate.
    const conduitMat=std(0x495153,{roughness:.76,metalness:.16});
    const conduitPaths=[
      [[-9,.19,.4],[-7.3,.19,.5],[-6.4,.19,.5]],
      [[-4.2,.19,1.55],[-2.8,.19,1.75],[-2.25,.29,1.75]],
      [[4.2,.21,-.9],[5.7,.21,-.9],[6.7,.21,-.9]]];
    for(const path of conduitPaths){const curve=new THREE.CatmullRomCurve3(path.map(v=>new THREE.Vector3(...v)));
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(curve,36,.075,8,false),conduitMat));}
    // Instance-rendered scattered aggregate and sparse distant vegetation.
    const gravelGeometry=new THREE.DodecahedronGeometry(.075,0);
    const gravelMaterial=std(0x99998c,{roughness:1,metalness:0});
    const stones=new THREE.InstancedMesh(gravelGeometry,gravelMaterial,340);
    const matrix=new THREE.Matrix4(), tint=new THREE.Color();
    for(let i=0;i<340;i++){
      let x=((i*73)%431)/431*50-25,z=((i*137)%419)/419*37-18;
      if(Math.abs(x)<14 && Math.abs(z)<5.5) z=z<0?-6.2:6.2;
      matrix.makeTranslation(x,.025,z);matrix.multiply(new THREE.Matrix4().makeScale(.7+i%4*.15,.23,.5+i%3*.2));
      stones.setMatrixAt(i,matrix);tint.setHex([0x77766e,0xb1ad9f,0x5e635d,0x98988c][i%4]);stones.setColorAt(i,tint);
    }
    stones.instanceMatrix.needsUpdate=true;scene.add(stones);

    // Discreet illuminated radio link: only visible during actual transmit stages.
    const linkMaterial = new THREE.LineDashedMaterial({color:0x5fe8ff,dashSize:.24,gapSize:.18,transparent:true,opacity:.55});
    const signalPaths=[];
    [[PORT.esp32,PORT.gateway],[PORT.gateway,PORT.server]].forEach(([a,b])=>{
      const pts=[];for(let i=0;i<=40;i++)pts.push(along(a,b,i/40, i===0||i===40?0:1.0));
      const geo=new THREE.BufferGeometry().setFromPoints(pts);
      const line=new THREE.Line(geo,linkMaterial);line.computeLineDistances();line.visible=false;
      scene.add(line);signalPaths.push(line);
    });

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

    // Keep telemetry indicators alive when a user supplies optional models.
    [batFill,chip,gwLed,localRing,edgeRing,...leds].forEach(m=>{m.userData.telemetryOverlay=true;});
    // Optional licensed/custom GLB assets retain a visible procedural fallback.
    const loading=el('div','t3-loading',root);
    loadOptionalModels(options.glb || window.TWIN_GLB_MODELS || {},
      { solar: solarG, battery: batG, esp32: espG, gateway: gwG, server: srvG },
      message=>{loading.textContent=message;loading.style.display=message?'block':'none';});

    // ── HTML overlays ──────────────────────────────────────────────────────
    const hud = el('div', 't3-hud', root);
    const pillClock = el('div', 't3-pill', hud);
    const pillWeather = el('div', 't3-pill', hud);
    const pillProto = el('div', 't3-pill', hud);
    pillProto.textContent = 'MQTT over WiFi 802.11n (modelled)';

    const cams = el('div', 't3-cams', root);
    const cameraOptions = [
      ['overview','Isometric'],['front','Front'],['rear','Rear'],['left','Left'],
      ['right','Right'],['top','Top'],['solar','Solar focus'],['battery','Battery focus'],
      ['esp32','ESP32 focus'],['gateway','Wireless focus'],['server','Server focus']];
    const viewSelect = el('select','t3-view',cams);
    viewSelect.setAttribute('aria-label','Camera view');
    cameraOptions.forEach(([key,label])=>{
      const item=el('option','',viewSelect);item.value=key;item.textContent=label;
    });
    viewSelect.onchange=()=>{demoMode=false;setView(viewSelect.value);updateModeButtons();};
    const resetBtn=el('button','',cams);resetBtn.textContent='Reset camera';
    resetBtn.onclick=()=>{demoMode=false;setView('overview');viewSelect.value='overview';updateModeButtons();};
    const freeBtn=el('button','',cams);freeBtn.textContent='Free 360°';
    freeBtn.onclick=()=>{camTween=null;followSignal=false;demoMode=false;updateModeButtons();};
    const followBtn=el('button','',cams);followBtn.textContent='Follow signal';
    followBtn.title='Replay the recorded OFFLOAD route through the 3D scene';
    followBtn.onclick=()=>{
      if (!task || !task.offload)return;
      demoMode=false;followSignal=!followSignal;camTween=null;
      if(!followSignal)controls.minDistance=1.2;
      if(followSignal){task.start=performance.now();camera.near=.035;camera.updateProjectionMatrix();}
      updateModeButtons();
    };
    const demoBtn=el('button','',cams);demoBtn.textContent='Presentation';
    demoBtn.onclick=()=>{
      demoMode=!demoMode;followSignal=false;demoStart=performance.now();demoIndex=-1;camTween=null;
      if(demoMode){setView('overview');demoMode=true;demoStart=performance.now();}
      updateModeButtons();
    };
    const quality = el('select','t3-view',cams);
    quality.setAttribute('aria-label','Graphics quality');
    [['high','High quality'],['balanced','Balanced'],['low','Low quality']].forEach(([value,label])=>{
      const item=el('option','',quality);item.value=value;item.textContent=label;
    });
    quality.value='balanced';
    quality.onchange=()=>{
      const q=quality.value;
      renderer.setPixelRatio(Math.min(window.devicePixelRatio,q==='low'?1:q==='balanced'?1.5:2));
      renderer.shadowMap.enabled=q!=='low';
      sunLight.shadow.mapSize.set(q==='high'?2048:1024,q==='high'?2048:1024);
      stones.visible=q!=='low';
      renderer.shadowMap.needsUpdate=true;
      resize();
    };
    const modeNote=el('div','t3-mode',root);
    function updateModeButtons(){
      followBtn.disabled=!(task && task.offload);
      followBtn.classList.toggle('is-active',followSignal);
      demoBtn.classList.toggle('is-active',demoMode);
      modeNote.textContent=followSignal?'FOLLOW SIGNAL · visual replay of recorded OFFLOAD route':
        demoMode?'PRESENTATION · camera tour of the current recorded task':'3D scene · drag orbit · right-drag pan · wheel zoom';
    }

    const stageBar = el('div', 't3-stages', root);
    const card = el('div', 't3-card', root);

    const labels = {
      solar:   makeLabel('#facc15', new THREE.Vector3(-10, 3.6, -1.5)),
      battery: makeLabel('#34d399', new THREE.Vector3(-5.2, 4.0, 0.5)),
      esp32:   makeLabel('#22d3ee', new THREE.Vector3(-0.8, 1.6, 1.8)),
      gateway: makeLabel('#c084fc', new THREE.Vector3(4.2, 6.1, -1.2)),
      server:  makeLabel('#818cf8', new THREE.Vector3(9.2, 4.9, 0.5)),
    };
    const groups = {solar:solarG,battery:batG,esp32:espG,gateway:gwG,server:srvG};
    const names = {solar:'Solar photovoltaic array',battery:'Battery storage',esp32:'ESP32 IoT device',gateway:'Wireless gateway',server:'Edge server'};
    const inspector = el('div','t3-inspector',root);
    inspector.textContent = 'Select equipment to inspect · drag to orbit · right-drag to pan · scroll to zoom';
    const selection = new THREE.BoxHelper(espG,0x69cfe6); selection.visible=false; scene.add(selection);
    let selected = null;
    function inspect(key) {
      selected=key;selection.setFromObject(groups[key]);selection.visible=true;
      const r=lastRecord;
      const readings=r?{
        solar:`${fmt(r.Renewable_Power,2)} W output · ${fmt(r.Solar_Irradiance,0)} W/m² irradiance`,
        battery:`SOC ${fmt(r.Battery_SOC,1)}% · charge ${fmt(r.Battery_Charge_Power,2)} W · discharge ${fmt(r.Battery_Discharge_Power,2)} W`,
        esp32:`CPU ${fmt(r.CPU_Load,1)}% · ${r.Task_ID} · LOCAL ${fmt(r.Local_Exec_Time,1)} ms · ${fmt(r.Local_Energy,2)} mJ`,
        gateway:`RSSI ${fmt(r.RSSI,1)} dBm · WiFi MCS${r.WiFi_MCS} · transmission ${fmt(r.Transmission_Time,1)} ms`,
        server:`CPU ${fmt(r.Server_CPU_Load,1)}% · edge processing ${fmt(r.Edge_Processing_Time,1)} ms`,
      }[key]:'Awaiting first telemetry record';
      inspector.textContent = names[key] + ' | ' + readings;
    }
    Object.keys(labels).forEach(key => {
      labels[key].e.style.pointerEvents='auto'; labels[key].e.style.cursor='pointer';
      labels[key].e.tabIndex=0; labels[key].e.setAttribute('role','button');
      labels[key].e.title='Inspect '+names[key];
      labels[key].e.onclick=()=>{inspect(key);setView(key);viewSelect.value=key;};
      labels[key].e.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){inspect(key);setView(key);viewSelect.value=key;}};
    });
    const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
    let down = null;
    renderer.domElement.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});
    function pick(e,focus=false) {
      if(!down || Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;
      const rect=renderer.domElement.getBoundingClientRect();
      mouse.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
      ray.setFromCamera(mouse,camera);
      const hits=ray.intersectObjects([...Object.values(groups),shelter,...signalPaths],true);
      if(!hits.length)return;
      let obj=hits[0].object;
      if(signalPaths.includes(obj)){
        inspector.textContent = obj===signalPaths[0] ?
          'Wireless uplink · '+fmt(lastRecord?.RSSI,1)+' dBm · '+fmt(lastRecord?.Transmission_Time,1)+' ms recorded transmission' :
          'Gateway → edge · modeled path; physical link medium is not specified in the simulation';
        return;
      }
      while(obj && !Object.values(groups).includes(obj) && obj!==shelter)obj=obj.parent;
      const key=obj===shelter?'server':Object.keys(groups).find(k=>groups[k]===obj);
      if(!key)return;
      inspect(key);setView(key);viewSelect.value=key;
    }
    renderer.domElement.addEventListener('pointerup',e=>pick(e));
    renderer.domElement.addEventListener('pointermove',e=>{
      if(e.buttons)return;
      const rect=renderer.domElement.getBoundingClientRect();
      mouse.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
      ray.setFromCamera(mouse,camera);
      const hit=ray.intersectObjects([...Object.values(groups),shelter,...signalPaths],true)[0];
      renderer.domElement.style.cursor=hit?'pointer':'grab';
    });
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

      pillClock.textContent = `${r.Timestamp}`;
      pillWeather.textContent = `${r.Weather} · ${fmt(r.Solar_Irradiance, 0)} W/m²`;
      renderLabels(r);
      if(selected) inspect(selected);
      renderCard(r);
      task = planTask(r, intervalMs);
      if(followSignal && !task.offload){followSignal=false;controls.minDistance=1.2;}
      if(demoMode){demoStart=performance.now();demoIndex=-1;}
      updateModeButtons();
    }

    // Build the stage plan for this task. Visual durations ∝ log(1 + real ms).
    function planTask(r, intervalMs) {
      const total = clamp(intervalMs * 0.92, 500, 6000);
      const offload = r.Decision === 'OFFLOAD';
      if (!['LOCAL','OFFLOAD'].includes(r.Decision)) { stageBar.textContent = 'No execution path recorded'; return {stages:[], start:performance.now()}; }
      const gw = 3;   // gateway + broker processing [ms] (T_GATEWAY_S)
      const stages = offload ? [
        { key: 'gen',  name: 'Task generated', ms: 2,  color: '#facc15' },
        { key: 'pkt',  name: 'MQTT packet',     ms: 2,  color: '#fb923c' },
        { key: 'tx',   name: `WiFi uplink ${fmt(r.Transmission_Time, 0)} ms`, ms: +r.Transmission_Time, color: '#c084fc' },
        { key: 'gw',   name: 'Gateway → Edge',  ms: gw, color: '#a78bfa' },
        { key: 'edge', name: `Edge ${fmt(r.Edge_Processing_Time, 0)} ms`, ms: +r.Edge_Processing_Time, color: '#818cf8' },
        { key: 'ret',  name: 'Modeled return', ms: Math.max(1, r.Network_Latency - r.Transmission_Time - gw), color: '#4ade80' },
      ] : [
        { key: 'gen',  name: 'Task generated', ms: 2, color: '#facc15' },
        { key: 'cpu',  name: `ESP32 processing ${fmt(r.Local_Exec_Time, 0)} ms`, ms: +r.Local_Exec_Time, color: '#2dd4bf' },
        { key: 'done', name: 'Modeled local result', ms: 2, color: '#4ade80' },
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
      labels.solar.e.innerHTML = `${fmt(r.Renewable_Power, 2)} W<small>PV ARRAY · recorded output</small>`;
      labels.battery.e.innerHTML = `${fmt(r.Battery_SOC, 1)} %<small>${charge ? '▲ charging ' + fmt(r.Battery_Charge_Power, 2) : '▼ discharging ' + fmt(r.Battery_Discharge_Power, 2)} W</small>`;
      labels.esp32.e.innerHTML = `ESP32 · CPU ${fmt(r.CPU_Load, 0)} %<small>${r.Task_Type}</small>`;
      labels.gateway.e.innerHTML = `${fmt(r.RSSI, 0)} dBm · MCS${r.WiFi_MCS}<small>${fmt(r.Data_Rate, 1)} Mbps · PER ${fmt(100 * r.PER, 1)} %</small>`;
      labels.server.e.innerHTML = `Edge ${fmt(r.Server_CPU_Load, 0)} %<small>T_edge ${fmt(r.Edge_Processing_Time, 0)} ms</small>`;
    }

    function renderCard(r) {
      const off = r.Decision === 'OFFLOAD';
      const badge = `<span class="t3-badge" style="background:${off ? '#60a5fa' : '#2dd4bf'}">${r.Decision || 'UNKNOWN'}</span>`;
      const rows = [
        ['Task', `${r.Task_ID} · ${r.Task_Type}`],
        ['Outcome', 'Not exported · modeled path'],
        ['Task size', `${fmt(r.Task_Size, 1)} KB`],
        ['Complexity', `${fmt(r.Task_Complexity, 0)} cycles/B`],
        ['Protocol', 'MQTT PUBLISH · QoS 1'],
        ['RSSI / rate', `${fmt(r.RSSI, 1)} dBm · ${fmt(r.Data_Rate, 1)} Mbps`],
        ['Network latency', `${fmt(r.Network_Latency, 0)} ms`],
        ['Local: time / energy', `${fmt(r.Local_Exec_Time, 0)} ms · ${fmt(r.Local_Energy, 0)} mJ`],
        ['Offload: time / energy', `${fmt(r.Offload_Total_Time, 0)} ms · ${fmt(r.Offload_Energy, 0)} mJ`],
        ['Cost J_local / J_off', `${fmt(r.Local_Execution_Cost, 3)} / ${fmt(r.Offload_Execution_Cost, 3)}`],
      ];
      card.innerHTML = `<div class="t3-card-h"><span>Task Flow</span>${badge}</div>` +
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
      signalPaths.forEach(line => { line.visible=false; });
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
      resultTag.textContent = `${task.id} · modeled result`;

      switch (cur.key) {
        case 'gen': case 'pkt':
          packet.visible = true;
          packet.position.copy(PORT.esp32).add(new THREE.Vector3(0, 0.3 + k * 0.6, 0));
          packet.scale.setScalar(cur.key === 'gen' ? 0.3 + 0.7 * k : 1);
          placeTag(packetTag, packet);
          break;
        case 'tx':
          signalPaths[0].visible=true;
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
          signalPaths[1].visible=true;
          packet.visible = true;
          packet.position.copy(along(PORT.gateway, PORT.server, k, 0.8));
          placeTag(packetTag, packet);
          break;
        case 'edge':
          edgeRing.material.opacity = 0.55;
          edgeRing.rotation.z = now * 0.006;
          edgeRing.scale.setScalar(1 + 0.08 * Math.sin(now * 0.02));
          break;
        case 'ret':
          signalPaths.forEach(line=>line.visible=true);
          result.visible = true;
          result.position.copy(k < 0.5 ? along(PORT.server, PORT.gateway, k * 2, 0.8) : along(PORT.gateway, PORT.esp32, (k - 0.5) * 2, 1.5));
          placeTag(resultTag, result);
          break;
        case 'cpu':
          localRing.material.opacity = 0.55;
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

    const dayColor = new THREE.Color(0x263647), nightColor = new THREE.Color(0x101923), duskColor = new THREE.Color(0x3a3b40);
    const skyColor = new THREE.Color();
    let prev = performance.now();
    let disposed=false;
    function frame(now) {
      if(disposed)return;
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
      skyDome.position.copy(camera.position);
      skyUniforms.zenith.value.copy(skyColor);
      skyUniforms.horizon.value.copy(skyColor).lerp(new THREE.Color(0xb1aa9b),.34+dayness*.3);
      yardLights.forEach(({light,luminaire})=>{
        light.intensity=.4+(1-dayness)*2.2;
        luminaire.material.color.setHex(dayness>.5?0xd1d7d2:0xfff4cf);
      });
      cloudMat.opacity = clamp(shown.cloud * .82, 0, .82) * (dayness > 0 ? 1 : .35);
      cloudMat.color.setHex(shown.cloud > .65 ? 0xb9c1c4 : 0xe8edee);
      clouds.children.forEach(cloud=>cloud.quaternion.copy(camera.quaternion));
      clouds.position.x = Math.sin(now * 0.00005) * 3;

      // Glass-face highlight follows recorded generation; no energy calculation changes.
      panelMat.emissiveIntensity = .005 + shown.pv * .035;

      // Battery fill ∝ SOC (green > 60 %, amber 30–60 %, red < 30 %)
      const socFrac = clamp(target.soc / 100, 0, 1);
      batFill.scale.y = socFrac * 2.9;
      batFill.position.y = .22 + socFrac * 2.9 / 2;
      const col = shown.soc > 60 ? C.power : shown.soc >= 30 ? C.warn : C.danger;
      fillMat.color.setHex(col);
      fillMat.emissive.setHex(col);
      fillMat.emissiveIntensity = 0.25;

      // ESP32 chip glow ∝ CPU load
      chipMat.emissiveIntensity = 0.2 + (shown.cpu / 100) * (0.4 + 0.15 * Math.sin(now * (0.005 + shown.cpu * 0.0004)));

      // Edge server glow + LED activity ∝ utilisation
      rackMat.emissiveIntensity = 0.01 + (shown.srv / 100) * 0.04;
      leds.forEach((led, i) => {
        const on = Math.sin(now * 0.004 * (1 + shown.srv / 12) + i * 1.7) > 1 - 2 * shown.srv / 100;
        led.material.color.setHex(on ? (shown.srv > 80 ? 0xf87171 : 0x60a5fa) : 0x1e3a8a);
      });
      gwLed.material.color.setHex(shown.rssiQ > 0.55 ? C.result : shown.rssiQ > 0.3 ? C.warn : C.danger);

      // Energy flows
      flowStep(pvFlow, clamp(shown.charging / 0.8, 0, 1), dt);
      flowStep(loadFlow, clamp(shown.load / 0.3, 0.05, 1), dt);

      animateTask(now);

      // The tour visits only the equipment and decision represented by the current row.
      // It never calls the simulation or creates a fictitious LOCAL/OFFLOAD event.
      if(demoMode){
        const elapsed=performance.now()-demoStart;
        const order=['overview','solar','battery','esp32',
          task?.offload?'gateway':'esp32',task?.offload?'server':'esp32'];
        const idx=Math.min(order.length-1,Math.floor(elapsed/3000));
        if(demoIndex!==idx){
          demoIndex=idx;setView(order[idx]);demoMode=true;
          // Replay only the current recorded task's *visual* path during the tour.
          if(task && idx===3)task.start=performance.now();
          if(task?.offload && idx===5){
            const edge=task.stages.find(stage=>stage.key==='edge');
            if(edge)task.start=performance.now()-edge.start;
          }
        }
        if(elapsed>order.length*3000){demoMode=false;demoIndex=-1;updateModeButtons();}
      }
      if(followSignal && task?.offload){
        const elapsed=now-task.start;
        const active=task.stages.find(st=>elapsed>=st.start&&elapsed<st.start+st.dur);
        let point=PORT.esp32.clone();
        if(active){
          const k=clamp((elapsed-active.start)/active.dur,0,1);
          if(active.key==='tx')point=along(PORT.esp32,PORT.gateway,k,1.5);
          else if(active.key==='gw')point=along(PORT.gateway,PORT.server,k,.8);
          else if(active.key==='edge')point=PORT.server.clone();
          else if(active.key==='ret')point=k<.5?along(PORT.server,PORT.gateway,k*2,.8):
            along(PORT.gateway,PORT.esp32,(k-.5)*2,1.5);
        } else if(elapsed>task.total) point=PORT.server.clone();
        const inside=point.x>7.3;
        const desired=inside?new THREE.Vector3(POS.server.x+.55,2.55,2.08):
          point.clone().add(new THREE.Vector3(1.6,1.25,2.5));
        controls.minDistance=inside?.55:1.2;
        camera.position.lerp(desired,.07);
        controls.target.lerp(inside?new THREE.Vector3(POS.server.x,2.3,1.1):point,.07);
        if(elapsed>task.total+1100){followSignal=false;controls.minDistance=1.2;updateModeButtons();}
      }
      if (camTween) {
        camTween.k = Math.min(1, camTween.k + dt * 1.8);
        const e = 1 - Math.pow(1 - camTween.k, 3);
        camera.position.lerpVectors(camTween.from, camTween.to, e);
        controls.target.lerpVectors(camTween.tFrom, camTween.tTo, e);
        if (camTween.k >= 1) camTween = null;
      }
      controls.update();
      camera.updateMatrixWorld();
      for (const key in labels) {
        const L = labels[key];
        tmp.copy(L.at).project(camera);
        L.e.style.display = tmp.z < 1 && tmp.z > -1 ? 'block' : 'none';
        const half = L.e.offsetWidth / 2 || 65;
        L.e.style.left = `${clamp((tmp.x * 0.5 + 0.5) * root.clientWidth, half+6, root.clientWidth-half-6)}px`;
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
      if (w < 640 && !camTween && !followSignal) camera.position.set(0, 15, 36);
    }
    const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(root);
    resize();
    requestAnimationFrame(frame);

    updateModeButtons();
    function dispose() {
      if(disposed)return;disposed=true;resizeObserver.disconnect();controls.dispose();
      scene.traverse(obj=>{
        if(obj.geometry)obj.geometry.dispose();
        if(obj.material){(Array.isArray(obj.material)?obj.material:[obj.material]).forEach(m=>m.dispose());}
      });
      [gravelTexture,concreteTexture,sidingTexture,pvTexture,cloudTexture].forEach(t=>t.dispose());
      renderer.dispose();root.remove();
    }
    return {update,setView,dispose,get lastRecord(){return lastRecord;}};
  }

  // ── Optional GLB/GLTF models ─────────────────────────────────────────────
  // window.TWIN_GLB_MODELS = { solar: 'assets/solar_panel.glb', ... } (see twin3d/assets/models.js)
  // Paths are relative to the twin3d/ folder, so both front-ends use the same entries.
  // A loaded model replaces the procedural one, scaled to the same footprint.
  function loadOptionalModels(map, groups, status = () => {}) {
    if (!THREE.GLTFLoader) return;
    let pending=Object.entries(map).filter(([name,url])=>groups[name]&&url).length;
    if(pending)status('Loading optional 3D assets…');
    const finished=()=>{if(--pending<=0)status('');};
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
        const keep = g.children.filter(c => c.userData.telemetryOverlay || (c.material && c.material.transparent)); // keep animated rings
        g.children.slice().forEach(c => { if (!keep.includes(c)) g.remove(c); });
        g.add(model);finished();
      }, xhr => { if(xhr.total) status(`${name} model ${Math.round(xhr.loaded/xhr.total*100)}%`); },
        () => { console.info(`[twin3d] ${url} not found – using procedural ${name} model`);finished(); });
    });
  }

  window.createTwinScene = createTwinScene;
})();
