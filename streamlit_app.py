import time
import os
import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIGURATION & INDUSTRIAL THEME STYLING
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Industrial IoT Digital Twin Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Industrial Telemetry Platform
st.markdown("""
<style>
    /* Dark Industrial Palette */
    .stApp {
        background-color: #070a12;
        color: #e2e8f0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Header Container */
    .platform-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 16px 24px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .platform-title {
        font-size: 1.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.5px;
    }
    
    .platform-subtitle {
        font-size: 0.85rem;
        color: #94a3b8;
        margin-top: 2px;
    }

    /* Metric Cards */
    .kpi-card {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 10px;
        padding: 14px 16px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
        transition: transform 0.2s, border-color 0.2s;
    }
    .kpi-card:hover {
        border-color: rgba(56, 189, 248, 0.3);
        transform: translateY(-2px);
    }
    .kpi-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #64748b;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.4rem;
        font-weight: 800;
        color: #f8fafc;
        font-family: 'JetBrains Mono', monospace;
    }
    .kpi-subtext {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-top: 4px;
    }

    /* Decision Badges */
    .badge-offload {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #ffffff;
        padding: 12px;
        border-radius: 8px;
        font-weight: 800;
        font-size: 1.2rem;
        text-align: center;
        box-shadow: 0 0 20px rgba(37, 99, 235, 0.45);
        border: 1px solid #3b82f6;
        letter-spacing: 1px;
    }
    .badge-local {
        background: linear-gradient(135deg, #059669, #047857);
        color: #ffffff;
        padding: 12px;
        border-radius: 8px;
        font-weight: 800;
        font-size: 1.2rem;
        text-align: center;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.45);
        border: 1px solid #10b981;
        letter-spacing: 1px;
    }

    /* Control Panel */
    .clock-display {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.05rem;
        color: #38bdf8;
        background: #0f172a;
        padding: 8px 16px;
        border-radius: 8px;
        border: 1px solid #1e293b;
        display: inline-block;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f1f5f9;
        margin: 20px 0 12px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Container Box */
    .content-box {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 20px;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION ENGINE STATE & LOGIC (UNTOUCHED FINAL SIMULATION ENGINE)
# ─────────────────────────────────────────────────────────────────────────────
if "running" not in st.session_state:
    st.session_state.running = False
if "sim_speed" not in st.session_state:
    st.session_state.sim_speed = 0.25
if "step_count" not in st.session_state:
    st.session_state.step_count = 0
if "history" not in st.session_state:
    st.session_state.history = []
if "twin_engine" not in st.session_state:
    from digital_twin_simulator import DiagnosedIoTDigitalTwin
    st.session_state.twin_engine = DiagnosedIoTDigitalTwin(seed=42, initial_soc=25.0)

def run_simulation_step():
    record = st.session_state.twin_engine.step()
    st.session_state.step_count = record["Step"]
    st.session_state.soc = record["Battery_SOC"]
    st.session_state.history.append(record)
    return record

# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM HEADER & SIMULATION CONTROLS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="platform-header">
    <div>
        <div class="platform-title">⚡ RENEWABLE IOT DIGITAL TWIN PLATFORM</div>
        <div class="platform-subtitle">Autonomous Renewable-Aware Edge Computing & Fog Offloading Telemetry</div>
    </div>
</div>
""", unsafe_allow_html=True)

ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([1.2, 1.2, 1.2, 2.2, 2.5])

with ctrl_col1:
    if st.button("▶ Start Twin", use_container_width=True, type="primary"):
        st.session_state.running = True

with ctrl_col2:
    if st.button("⏸ Pause Twin", use_container_width=True):
        st.session_state.running = False

with ctrl_col3:
    if st.button("🔄 Reset Twin", use_container_width=True):
        st.session_state.running = False
        st.session_state.step_count = 0
        st.session_state.history = []
        st.session_state.soc = 25.0
        st.rerun()

with ctrl_col4:
    st.session_state.sim_speed = st.slider("Step Speed (s)", 0.05, 1.0, 0.2, 0.05)

with ctrl_col5:
    curr_time = "Day 01, 00:00"
    if st.session_state.history:
        curr_time = st.session_state.history[-1]["Timestamp"]
    st.markdown(f"<div class=\"clock-display\">🕒 Simulation Clock: <b>{curr_time}</b> (Step {st.session_state.step_count})</div>", unsafe_allow_html=True)

# Step Execution Loop
if st.session_state.running:
    latest = run_simulation_step()
elif st.session_state.history:
    latest = st.session_state.history[-1]
else:
    latest = run_simulation_step()

# ─────────────────────────────────────────────────────────────────────────────
# 1. SYSTEM OVERVIEW & REAL-TIME KPI METRICS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class=\"section-header\">📡 Real-Time System Telemetry KPI Summary</div>", unsafe_allow_html=True)

kpi1, kpi2, kpi3, kpi4, kpi5, kpi6, kpi7 = st.columns(7)

kpi1.markdown(f"""<div class="kpi-card">
    <div class="kpi-label">☀️ Solar Gen</div>
    <div class="kpi-value" style="color: #f59e0b;">{latest['Renewable_Availability']}%</div>
    <div class="kpi-subtext">+{(latest['Renewable_Charge']):.4f} %/min</div>
</div>""", unsafe_allow_html=True)

bat_clr = "#10b981" if latest['Battery_SOC'] > 60 else "#f59e0b" if latest['Battery_SOC'] >= 30 else "#ef4444"
kpi2.markdown(f"""<div class="kpi-card">
    <div class="kpi-label">🔋 Battery SOC</div>
    <div class="kpi-value" style="color: {bat_clr};">{latest['Battery_SOC']}%</div>
    <div class="kpi-subtext">dSOC: {latest['dSOC_dt']:+.4f}</div>
</div>""", unsafe_allow_html=True)

kpi3.markdown(f"""<div class="kpi-card">
    <div class="kpi-label">💻 ESP32 CPU</div>
    <div class="kpi-value" style="color: #38bdf8;">{latest['CPU_Load']}%</div>
    <div class="kpi-subtext">Task: {latest['Task_Size']} MB</div>
</div>""", unsafe_allow_html=True)

kpi4.markdown(f"""<div class="kpi-card">
    <div class="kpi-label">📡 WiFi RSSI</div>
    <div class="kpi-value" style="color: #a855f7;">{latest['RSSI']} dBm</div>
    <div class="kpi-subtext">Signal Strength</div>
</div>""", unsafe_allow_html=True)

kpi5.markdown(f"""<div class="kpi-card">
    <div class="kpi-label">⏱️ Latency</div>
    <div class="kpi-value" style="color: #ec4899;">{latest['Network_Latency']} ms</div>
    <div class="kpi-subtext">Network Delay</div>
</div>""", unsafe_allow_html=True)

kpi6.markdown(f"""<div class="kpi-card">
    <div class="kpi-label">🖥️ Server CPU</div>
    <div class="kpi-value" style="color: #6366f1;">{latest['Server_CPU_Load']}%</div>
    <div class="kpi-subtext">Fog Node Load</div>
</div>""", unsafe_allow_html=True)

with kpi7:
    if latest["Decision"] == "OFFLOAD":
        st.markdown('<div class="badge-offload">⚡ OFFLOAD</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="badge-local">💻 LOCAL</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# 2. HIGH-FIDELITY 3D INDUSTRIAL DIGITAL TWIN VIEWPORT (Three.js WebGL Engine)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class=\"section-header\">🌐 3D Rendered Industrial Digital Twin Scene</div>", unsafe_allow_html=True)

solar_val = latest["Renewable_Availability"]
soc_val = latest["Battery_SOC"]
cpu_val = latest["CPU_Load"]
rssi_val = latest["RSSI"]
srv_val = latest["Server_CPU_Load"]
is_offload = (latest["Decision"] == "OFFLOAD")

three_js_code = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ margin: 0; overflow: hidden; background: #060911; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}
        #container {{ width: 100vw; height: 480px; position: relative; }}
        
        .hud-overlay {{
            position: absolute; top: 12px; left: 16px;
            background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px;
            padding: 8px 14px; color: #38bdf8; font-size: 11px; font-weight: 600;
            pointer-events: none; box-shadow: 0 4px 14px rgba(0,0,0,0.5);
            display: flex; align-items: center; gap: 8px;
        }}
        
        .camera-toolbar {{
            position: absolute; top: 12px; right: 16px;
            display: flex; gap: 6px; background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 6px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.5); z-index: 10;
        }}
        
        .cam-btn {{
            background: #1e293b; color: #e2e8f0; border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: 600;
            cursor: pointer; transition: all 0.2s ease;
        }}
        .cam-btn:hover {{
            background: #38bdf8; color: #0f172a; border-color: #38bdf8;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
        }}

        /* Floating Asset Telemetry Inspector Overlay */
        .inspector-card {{
            position: absolute; bottom: 16px; left: 16px; width: 300px;
            background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(14px);
            border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.6); z-index: 100;
            overflow: hidden; transition: all 0.3s ease;
        }}
        .inspector-header {{
            background: linear-gradient(90deg, #1e293b, #0f172a); padding: 10px 14px;
            font-weight: 700; font-size: 12px; color: #38bdf8; display: flex;
            justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08);
        }}
        .insp-close {{
            background: none; border: none; color: #94a3b8; font-size: 14px; cursor: pointer;
        }}
        .insp-close:hover {{ color: #f43f5e; }}
        .inspector-body {{ padding: 12px 14px; font-size: 11px; color: #e2e8f0; }}
        .insp-row {{ display: flex; justify-content: space-between; margin-bottom: 6px; border-bottom: 1px dashed rgba(255,255,255,0.06); padding-bottom: 4px; }}
        .insp-label {{ color: #94a3b8; }}
        .insp-val {{ font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #f8fafc; }}
        
        .legend-overlay {{
            position: absolute; bottom: 12px; right: 16px;
            background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px;
            padding: 8px 14px; color: #94a3b8; font-size: 11px;
            pointer-events: none; display: flex; gap: 14px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .dot-green {{ width: 8px; height: 8px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981; }}
        .dot-blue {{ width: 8px; height: 8px; background: #3b82f6; border-radius: 50%; box-shadow: 0 0 8px #3b82f6; }}
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
</head>
<body>
    <div id="container">
        <div class="hud-overlay">
            ⚡ INDUSTRIAL DIGITAL TWIN — Click / Double-Click Asset to Inspect
        </div>
        
        <div class="camera-toolbar">
            <button class="cam-btn" onclick="setCamera('iso')">📐 Isometric</button>
            <button class="cam-btn" onclick="setCamera('top')">⬇ Top View</button>
            <button class="cam-btn" onclick="setCamera('side')">➡️ Side View</button>
            <button class="cam-btn" onclick="setCamera('reset')">🔄 Reset</button>
            <button class="cam-btn" onclick="zoomCam(0.8)">🔍+ Zoom In</button>
            <button class="cam-btn" onclick="zoomCam(1.25)">🔍- Zoom Out</button>
        </div>

        <!-- Floating Telemetry Inspector Window -->
        <div id="inspector-card" class="inspector-card" style="display: none;">
            <div class="inspector-header">
                <span id="insp-title">🔍 Asset Inspector</span>
                <button class="insp-close" onclick="closeInspector()">✕</button>
            </div>
            <div id="insp-content" class="inspector-body"></div>
        </div>

        <div class="legend-overlay">
            <div class="legend-item"><div class="dot-green"></div> Local Processing Halo</div>
            <div class="legend-item"><div class="dot-blue"></div> Offload Telemetry Stream</div>
        </div>
    </div>

    <script>
        const container = document.getElementById('container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x060911);
        scene.fog = new THREE.FogExp2(0x060911, 0.018);

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / 480, 0.1, 1000);
        camera.position.set(0, 10, 18);

        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setSize(window.innerWidth, 480);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.maxPolarAngle = Math.PI / 2 - 0.01;
        controls.target.set(0, 1.5, 0);

        const gltfLoader = new THREE.GLTFLoader();
        const selectableObjects = [];

        // ─────────────────────────────────────────────────────────────────────
        // CAMERA CONTROL & INSPECTOR FUNCTIONS
        // ─────────────────────────────────────────────────────────────────────
        window.setCamera = function(type) {{
            if (type === 'top') {{
                animateCamera(0, 24, 0.1, 0, 0, 0);
            }} else if (type === 'side') {{
                animateCamera(22, 4, 0, 0, 2, 0);
            }} else if (type === 'iso' || type === 'reset') {{
                animateCamera(0, 10, 18, 0, 1.5, 0);
                closeInspector();
            }}
        }};

        window.zoomCam = function(factor) {{
            const vec = new THREE.Vector3().subVectors(camera.position, controls.target);
            vec.multiplyScalar(factor);
            camera.position.copy(controls.target).add(vec);
            controls.update();
        }};

        window.closeInspector = function() {{
            document.getElementById('inspector-card').style.display = 'none';
            if (window.selectionRing) window.selectionRing.visible = false;
        }};

        function animateCamera(px, py, pz, tx, ty, tz) {{
            const startP = camera.position.clone();
            const startT = controls.target.clone();
            const endP = new THREE.Vector3(px, py, pz);
            const endT = new THREE.Vector3(tx, ty, tz);
            let duration = 500;
            let startTime = performance.now();

            function step(now) {{
                let elapsed = now - startTime;
                let progress = Math.min(elapsed / duration, 1.0);
                let ease = 1 - Math.pow(1 - progress, 3);

                camera.position.lerpVectors(startP, endP, ease);
                controls.target.lerpVectors(startT, endT, ease);
                controls.update();

                if (progress < 1.0) {{
                    requestAnimationFrame(step);
                }}
            }}
            requestAnimationFrame(step);
        }}

        // ─────────────────────────────────────────────────────────────────────
        // SELECTION RING HIGHLIGHT
        // ─────────────────────────────────────────────────────────────────────
        const selGeo = new THREE.RingGeometry(1.6, 1.9, 32);
        const selMat = new THREE.MeshBasicMaterial({{ color: 0x38bdf8, side: THREE.DoubleSide, transparent: true, opacity: 0.85 }});
        window.selectionRing = new THREE.Mesh(selGeo, selMat);
        window.selectionRing.rotation.x = Math.PI / 2;
        window.selectionRing.visible = false;
        scene.add(window.selectionRing);

        // ─────────────────────────────────────────────────────────────────────
        // LIGHTING & INDUSTRIAL SCENE ENVIRONMENT
        // ─────────────────────────────────────────────────────────────────────
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.45);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xfffaed, 0.6 + ({solar_val} / 100.0) * 1.5);
        sunLight.position.set(-12, 18, -6);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 1024;
        sunLight.shadow.mapSize.height = 1024;
        scene.add(sunLight);

        const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.4);
        fillLight.position.set(12, 10, 12);
        scene.add(fillLight);

        const gridHelper = new THREE.GridHelper(36, 36, 0x1e293b, 0x0f172a);
        gridHelper.position.y = 0.0;
        scene.add(gridHelper);

        // Cable Conduit Path Line Overlay (Cyan Conduit Striping)
        const pathPoints = [
            new THREE.Vector3(-8.5, 0.02, -2.0),
            new THREE.Vector3(-4.5, 0.02, -1.0),
            new THREE.Vector3(-0.5, 0.02, 1.5),
            new THREE.Vector3(4.0, 0.02, -1.5),
            new THREE.Vector3(8.5, 0.02, 0.0)
        ];
        const pathGeo = new THREE.BufferGeometry().setFromPoints(pathPoints);
        const pathMat = new THREE.LineDashedMaterial({{ color: 0x38bdf8, dashSize: 0.4, gapSize: 0.2, linewidth: 2 }});
        const pathLine = new THREE.Line(pathGeo, pathMat);
        pathLine.computeLineDistances();
        scene.add(pathLine);

        function addContactShadow(x, z, radiusX, radiusZ) {{
            const shadowGeo = new THREE.PlaneGeometry(radiusX * 2, radiusZ * 2);
            const shadowMat = new THREE.MeshBasicMaterial({{
                color: 0x020408,
                transparent: true,
                opacity: 0.65,
                depthWrite: false
            }});
            const shadowMesh = new THREE.Mesh(shadowGeo, shadowMat);
            shadowMesh.rotation.x = -Math.PI / 2;
            shadowMesh.position.set(x, 0.005, z);
            scene.add(shadowMesh);
        }}

        // ─────────────────────────────────────────────────────────────────────
        // 1. SOLAR PANEL ARRAY (2.4W Photovoltaic Harvester + Spec Plate + Junction Box)
        // ─────────────────────────────────────────────────────────────────────
        const solarGroup = new THREE.Group();
        solarGroup.position.set(-8.5, 0, -2);
        solarGroup.userData.assetType = 'solar';
        addContactShadow(-8.5, -2, 2.5, 2.5);

        const rackSteelMat = new THREE.MeshStandardMaterial({{ color: 0x475569, roughness: 0.3, metalness: 0.85 }});

        // Tubular Steel Mounting Frame & Diagonal Bracing
        for (let xOff of [-1.2, 1.2]) {{
            const postFront = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 1.2), rackSteelMat);
            postFront.position.set(xOff, 0.6, 0.8);
            solarGroup.add(postFront);

            const postBack = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 2.4), rackSteelMat);
            postBack.position.set(xOff, 1.2, -0.8);
            solarGroup.add(postBack);
        }}

        const panelCellMat = new THREE.MeshStandardMaterial({{
            color: 0x071328,
            roughness: 0.12,
            metalness: 0.75,
            emissive: 0x38bdf8,
            emissiveIntensity: ({solar_val} / 100.0) * 0.4
        }});

        const alumFrameMat = new THREE.MeshStandardMaterial({{ color: 0x94a3b8, roughness: 0.25, metalness: 0.85 }});
        const jBoxMat = new THREE.MeshStandardMaterial({{ color: 0x1e293b, roughness: 0.5, metalness: 0.3 }});

        for (let i = -1; i <= 1; i += 2) {{
            for (let j = -1; j <= 1; j += 2) {{
                const pGroup = new THREE.Group();
                pGroup.position.set(i * 1.0, 1.8, j * 1.4);
                pGroup.rotation.x = 0.42;

                // Aluminum Frame Border
                const pBox = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.12, 2.6), alumFrameMat);
                pGroup.add(pBox);

                // Dark Blue PV Cell Surface
                const pvSurface = new THREE.Mesh(new THREE.BoxGeometry(1.68, 0.04, 2.48), panelCellMat);
                pvSurface.position.y = 0.05;
                pGroup.add(pvSurface);

                // Busbars & PV Cell Boundaries Grid
                const gridLines = new THREE.LineSegments(
                    new THREE.EdgesGeometry(pvSurface.geometry),
                    new THREE.LineBasicMaterial({{ color: 0x38bdf8, transparent: true, opacity: 0.55 }})
                );
                pvSurface.add(gridLines);

                // Rear Junction Box
                const jBox = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.12, 0.45), jBoxMat);
                jBox.position.set(0, -0.08, 0);
                pGroup.add(jBox);

                solarGroup.add(pGroup);
            }}
        }}

        // Spec Plate "2.4W PHOTOVOLTAIC HARVESTER"
        const solarPlate = new THREE.Mesh(
            new THREE.BoxGeometry(1.4, 0.18, 0.04),
            new THREE.MeshStandardMaterial({{ color: 0xc0c0c0, metalness: 0.9, roughness: 0.2 }})
        );
        solarPlate.position.set(0, 0.2, 0.9);
        solarGroup.add(solarPlate);

        scene.add(solarGroup);
        selectableObjects.push(solarGroup);

        // ─────────────────────────────────────────────────────────────────────
        // 2. BATTERY STORAGE SYSTEM (12Wh BESS Enclosure + SOC LED Bar)
        // ─────────────────────────────────────────────────────────────────────
        const bessGroup = new THREE.Group();
        bessGroup.position.set(-4.5, 0, -1);
        bessGroup.userData.assetType = 'bess';
        addContactShadow(-4.5, -1, 1.5, 1.4);

        const cabMat = new THREE.MeshStandardMaterial({{ color: 0x1e293b, roughness: 0.35, metalness: 0.5 }});
        const bessCabinet = new THREE.Mesh(new THREE.BoxGeometry(2.2, 3.6, 1.8), cabMat);
        bessCabinet.position.y = 1.8;
        bessCabinet.castShadow = true;
        bessGroup.add(bessCabinet);

        // Side Cooling Vents
        for (let yRib = 0.6; yRib <= 3.0; yRib += 0.4) {{
            const ribLeft = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.1, 1.4), cabMat);
            ribLeft.position.set(-1.12, yRib, 0);
            bessGroup.add(ribLeft);
            const ribRight = ribLeft.clone();
            ribRight.position.x = 1.12;
            bessGroup.add(ribRight);
        }}

        // Front Tempered Glass Window
        const glassFront = new THREE.Mesh(
            new THREE.PlaneGeometry(1.9, 3.2),
            new THREE.MeshPhysicalMaterial({{ color: 0xffffff, transparent: true, opacity: 0.28, roughness: 0.05, metalness: 0.1 }})
        );
        glassFront.position.set(0, 1.8, 0.91);
        bessGroup.add(glassFront);

        // Interior 18650 Li-ion Battery Canisters
        for (let cX of [-0.5, 0.5]) {{
            for (let cZ of [-0.3, 0.3]) {{
                const cellTube = new THREE.Mesh(
                    new THREE.CylinderGeometry(0.25, 0.25, 3.0, 16),
                    new THREE.MeshStandardMaterial({{ color: 0x334155, metalness: 0.85, roughness: 0.25 }})
                );
                cellTube.position.set(cX, 1.7, cZ);
                bessGroup.add(cellTube);
            }}
        }}

        // Integrated SOC Fill Column & Multi-Color Status LED Bar
        const socPct = {soc_val};
        const batColorHex = socPct > 60 ? 0x10b981 : socPct >= 30 ? 0xf59e0b : 0xef4444;
        const fillHeight = Math.max(0.15, (socPct / 100.0) * 3.0);

        const fillMesh = new THREE.Mesh(
            new THREE.BoxGeometry(1.85, fillHeight, 1.4),
            new THREE.MeshStandardMaterial({{
                color: batColorHex,
                emissive: batColorHex,
                emissiveIntensity: 0.65,
                roughness: 0.2
            }})
        );
        fillMesh.position.set(0, 0.2 + fillHeight / 2, 0);
        bessGroup.add(fillMesh);

        // Front Status LED & Nameplate "12Wh LITHIUM-ION BESS"
        const plateMesh = new THREE.Mesh(
            new THREE.BoxGeometry(1.3, 0.25, 0.04),
            new THREE.MeshStandardMaterial({{ color: 0x94a3b8, metalness: 0.9, roughness: 0.2 }})
        );
        plateMesh.position.set(0, 3.3, 0.92);
        bessGroup.add(plateMesh);

        const statusLed = new THREE.Mesh(
            new THREE.SphereGeometry(0.08, 12, 12),
            new THREE.MeshBasicMaterial({{ color: batColorHex }})
        );
        statusLed.position.set(0.8, 3.3, 0.93);
        bessGroup.add(statusLed);

        scene.add(bessGroup);
        selectableObjects.push(bessGroup);

        // ─────────────────────────────────────────────────────────────────────
        // 3. ESP32 IOT EDGE NODE (Green PCB, ESP32 Shield, Pins, USB, CPU Glow)
        // ─────────────────────────────────────────────────────────────────────
        const espGroup = new THREE.Group();
        espGroup.position.set(-0.5, 0, 1.5);
        espGroup.userData.assetType = 'esp32';
        addContactShadow(-0.5, 1.5, 1.8, 2.2);

        // Mounting Pedestal Platform
        const pedStand = new THREE.Mesh(
            new THREE.CylinderGeometry(1.5, 1.8, 0.4, 24),
            new THREE.MeshStandardMaterial({{ color: 0x1e293b, roughness: 0.5, metalness: 0.5 }})
        );
        pedStand.position.y = 0.2;
        espGroup.add(pedStand);

        // Deep Green Solder-Mask PCB Substrate
        const pcbMesh = new THREE.Mesh(
            new THREE.BoxGeometry(2.8, 0.14, 3.8),
            new THREE.MeshStandardMaterial({{ color: 0x044722, roughness: 0.35, metalness: 0.25 }})
        );
        pcbMesh.position.y = 0.47;
        espGroup.add(pcbMesh);

        // Metallic ESP32-WROOM SoC Shield Can
        const socShield = new THREE.Mesh(
            new THREE.BoxGeometry(1.3, 0.22, 1.5),
            new THREE.MeshStandardMaterial({{ color: 0xc0c0c0, roughness: 0.18, metalness: 0.95 }})
        );
        socShield.position.set(0, 0.63, -0.2);
        espGroup.add(socShield);

        // CPU Core Die Activity Glow
        const cpuCore = new THREE.Mesh(
            new THREE.BoxGeometry(0.7, 0.05, 0.7),
            new THREE.MeshBasicMaterial({{ color: 0x38bdf8 }})
        );
        cpuCore.position.set(0, 0.75, -0.2);
        espGroup.add(cpuCore);

        // Gold Dual-Row Pin Headers
        const pinMat = new THREE.MeshStandardMaterial({{ color: 0xd97706, metalness: 0.9, roughness: 0.2 }});
        for (let zPin = -1.6; zPin <= 1.6; zPin += 0.25) {{
            const pinL = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.4, 0.08), pinMat);
            pinL.position.set(-1.25, 0.47, zPin);
            espGroup.add(pinL);
            const pinR = pinL.clone();
            pinR.position.x = 1.25;
            espGroup.add(pinR);
        }}

        // Micro-USB Port & Antenna Meander Trace
        const usbPort = new THREE.Mesh(
            new THREE.BoxGeometry(0.45, 0.2, 0.5),
            new THREE.MeshStandardMaterial({{ color: 0x94a3b8, metalness: 0.9, roughness: 0.2 }})
        );
        usbPort.position.set(0, 0.57, -1.7);
        espGroup.add(usbPort);

        const antTrace = new THREE.Mesh(
            new THREE.BoxGeometry(1.6, 0.04, 0.6),
            new THREE.MeshStandardMaterial({{ color: 0xd97706, metalness: 0.8, roughness: 0.3 }})
        );
        antTrace.position.set(0, 0.55, 1.4);
        espGroup.add(antTrace);

        // Local Processing Green Ring Halo
        const localHalo = new THREE.Mesh(
            new THREE.RingGeometry(1.8, 2.1, 32),
            new THREE.MeshBasicMaterial({{
                color: 0x10b981,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: { "0.85" if not is_offload else "0.08" }
            }})
        );
        localHalo.rotation.x = Math.PI / 2;
        localHalo.position.y = 0.06;
        espGroup.add(localHalo);

        scene.add(espGroup);
        selectableObjects.push(espGroup);

        // ─────────────────────────────────────────────────────────────────────
        // 4. TELECOM TOWER GATEWAY (Lattice Mast, 3 Sector Antennas, RRU Box)
        // ─────────────────────────────────────────────────────────────────────
        const towerGroup = new THREE.Group();
        towerGroup.position.set(4.0, 0, -1.5);
        towerGroup.userData.assetType = 'tower';
        addContactShadow(4.0, -1.5, 1.2, 1.2);

        const mastSteelMat = new THREE.MeshStandardMaterial({{ color: 0x64748b, roughness: 0.3, metalness: 0.85 }});

        // 4 Corner Truss Legs
        const botW = 0.7, topW = 0.2, hMast = 5.2;
        for (let angle of [Math.PI/4, 3*Math.PI/4, 5*Math.PI/4, 7*Math.PI/4]) {{
            const x1 = Math.cos(angle) * botW, z1 = Math.sin(angle) * botW;
            const x2 = Math.cos(angle) * topW, z2 = Math.sin(angle) * topW;

            const legGeo = new THREE.CylinderGeometry(0.05, 0.06, hMast, 8);
            const legMesh = new THREE.Mesh(legGeo, mastSteelMat);
            legMesh.position.set((x1 + x2) / 2, hMast / 2, (z1 + z2) / 2);
            towerGroup.add(legMesh);
        }}

        // Horizontal Truss Rings
        for (let yLvl = 0.8; yLvl <= hMast; yLvl += 0.8) {{
            const braceRing = new THREE.Mesh(
                new THREE.TorusGeometry(botW - (yLvl / hMast) * (botW - topW), 0.03, 6, 4),
                mastSteelMat
            );
            braceRing.rotation.x = Math.PI / 2;
            braceRing.position.y = yLvl;
            towerGroup.add(braceRing);
        }}

        // 3 Sector Antenna Panels Angled Downward at 120°
        for (let aIdx = 0; aIdx < 3; aIdx++) {{
            const rotA = (aIdx * Math.PI * 2) / 3;
            const antPanel = new THREE.Mesh(
                new THREE.BoxGeometry(0.25, 1.1, 0.45),
                new THREE.MeshStandardMaterial({{ color: 0xe2e8f0, roughness: 0.35 }})
            );
            antPanel.position.set(Math.cos(rotA) * 0.45, 4.8, Math.sin(rotA) * 0.45);
            antPanel.rotation.y = -rotA;
            antPanel.rotation.z = 0.08; // 5 degree downward tilt
            towerGroup.add(antPanel);
        }}

        // Remote Radio Unit (RRU) Base Equipment Box
        const rruBox = new THREE.Mesh(
            new THREE.BoxGeometry(0.8, 1.0, 0.6),
            new THREE.MeshStandardMaterial({{ color: 0x334155, metalness: 0.7, roughness: 0.3 }})
        );
        rruBox.position.set(0, 0.5, 0);
        towerGroup.add(rruBox);

        // Red Collision Beacon
        const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 16), new THREE.MeshBasicMaterial({{ color: 0xef4444 }}));
        beacon.position.y = 5.3;
        towerGroup.add(beacon);

        // Wireless RSSI Pulsing Signal Waves
        const rssiScale = (({rssi_val} + 90) / 50.0);
        const waveRings = [];
        for (let r = 1; r <= 3; r++) {{
            const ring = new THREE.Mesh(
                new THREE.TorusGeometry(r * 0.7, 0.03, 8, 24),
                new THREE.MeshBasicMaterial({{ color: 0xa855f7, transparent: true, opacity: Math.max(0.15, rssiScale * 0.75) }})
            );
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 4.8;
            towerGroup.add(ring);
            waveRings.push(ring);
        }}

        scene.add(towerGroup);
        selectableObjects.push(towerGroup);

        // ─────────────────────────────────────────────────────────────────────
        // 5. EDGE SERVER RACK (42U Chassis, Server Blades, Mesh Door, Fan Spin)
        // ─────────────────────────────────────────────────────────────────────
        const rackGroup = new THREE.Group();
        rackGroup.position.set(8.5, 0, 0);
        rackGroup.userData.assetType = 'server';
        addContactShadow(8.5, 0, 1.6, 1.5);

        // 42U Server Cabinet Frame
        const rackFrame = new THREE.Mesh(
            new THREE.BoxGeometry(2.4, 4.4, 2.2),
            new THREE.MeshStandardMaterial({{
                color: 0x0f172a,
                roughness: 0.3,
                emissive: 0x3b82f6,
                emissiveIntensity: ({srv_val} / 100.0) * 0.4
            }})
        );
        rackFrame.position.y = 2.2;
        rackGroup.add(rackFrame);

        // Top Exhaust Fan Geometry
        const fanDisc = new THREE.Mesh(
            new THREE.CylinderGeometry(0.6, 0.6, 0.1, 16),
            new THREE.MeshStandardMaterial({{ color: 0x334155, metalness: 0.8, roughness: 0.2 }})
        );
        fanDisc.position.set(0, 4.45, 0);
        rackGroup.add(fanDisc);

        const fanBladeMesh = new THREE.Mesh(
            new THREE.BoxGeometry(1.0, 0.04, 0.2),
            new THREE.MeshStandardMaterial({{ color: 0x94a3b8, metalness: 0.9 }})
        );
        fanBladeMesh.position.set(0, 4.51, 0);
        rackGroup.add(fanBladeMesh);

        // 6 Server Blades Stack with Front Intake Handles & LED Arrays
        const leds = [];
        for (let bY = 0.7; bY <= 3.9; bY += 0.6) {{
            const blade = new THREE.Mesh(
                new THREE.BoxGeometry(2.22, 0.48, 0.08),
                new THREE.MeshStandardMaterial({{ color: 0x1e293b, metalness: 0.75, roughness: 0.25 }})
            );
            blade.position.set(0, bY, 1.11);
            rackGroup.add(blade);

            // Blade Handles
            for (let hX of [-0.95, 0.95]) {{
                const handle = new THREE.Mesh(
                    new THREE.BoxGeometry(0.08, 0.3, 0.12),
                    new THREE.MeshStandardMaterial({{ color: 0x94a3b8, metalness: 0.9 }})
                );
                handle.position.set(hX, bY, 1.15);
                rackGroup.add(handle);
            }}

            // LED Array per Unit
            for (let lX = -0.6; lX <= 0.6; lX += 0.4) {{
                const led = new THREE.Mesh(
                    new THREE.BoxGeometry(0.1, 0.08, 0.04),
                    new THREE.MeshBasicMaterial({{ color: 0x3b82f6 }})
                );
                led.position.set(lX, bY, 1.16);
                rackGroup.add(led);
                leds.push(led);
            }}
        }}

        scene.add(rackGroup);
        selectableObjects.push(rackGroup);

        // ─────────────────────────────────────────────────────────────────────
        // RAYCASTING OBJECT INSPECTION & DOUBLE CLICK AUTO-FOCUS
        // ─────────────────────────────────────────────────────────────────────
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();

        container.addEventListener('click', onAssetClick);
        container.addEventListener('dblclick', onAssetClick);

        function onAssetClick(event) {{
            const rect = renderer.domElement.getBoundingClientRect();
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(selectableObjects, true);

            if (intersects.length > 0) {{
                let obj = intersects[0].object;
                while (obj.parent && !obj.userData.assetType && obj.parent !== scene) {{
                    obj = obj.parent;
                }}
                if (obj.userData.assetType) {{
                    const aType = obj.userData.assetType;
                    const pos = obj.position;

                    window.selectionRing.position.set(pos.x, 0.02, pos.z);
                    window.selectionRing.visible = true;

                    animateCamera(pos.x + 3.5, pos.y + 4.5, pos.z + 6.5, pos.x, pos.y + 1.5, pos.z);
                    showInspectorCard(aType);
                }}
            }}
        }}

        function showInspectorCard(type) {{
            const card = document.getElementById('inspector-card');
            const titleEl = document.getElementById('insp-title');
            const bodyEl = document.getElementById('insp-content');

            if (type === 'solar') {{
                titleEl.innerHTML = '☀️ Solar Panel Array Telemetry';
                bodyEl.innerHTML = `
                    <div class="insp-row"><span class="insp-label">Renewable Availability</span><span class="insp-val" style="color:#f59e0b;">{solar_val}%</span></div>
                    <div class="insp-row"><span class="insp-label">Power Generation</span><span class="insp-val">{round(solar_val * 0.025, 2)} kW</span></div>
                    <div class="insp-row"><span class="insp-label">Diurnal Solar Phase</span><span class="insp-val">{"Daylight Peak" if solar_val > 0 else "Night (0 kW)"}</span></div>
                    <div class="insp-row"><span class="insp-label">Panel Temperature</span><span class="insp-val">38.4 °C</span></div>
                `;
            }} else if (type === 'bess') {{
                titleEl.innerHTML = '🔋 BESS Energy Storage Cabinet';
                bodyEl.innerHTML = `
                    <div class="insp-row"><span class="insp-label">Battery SOC</span><span class="insp-val" style="color:${{batColorHex}};">{soc_val}%</span></div>
                    <div class="insp-row"><span class="insp-label">Net Charge dSOC/dt</span><span class="insp-val">{latest['dSOC_dt']:+.4f}</span></div>
                    <div class="insp-row"><span class="insp-label">Solar Input Power</span><span class="insp-val">+{latest['Renewable_Charge']:.4f} W</span></div>
                    <div class="insp-row"><span class="insp-label">Device Load Discharge</span><span class="insp-val">-{latest['CPU_Discharge']:.4f} W</span></div>
                `;
            }} else if (type === 'esp32') {{
                titleEl.innerHTML = '💻 ESP32 IoT Edge Node';
                bodyEl.innerHTML = `
                    <div class="insp-row"><span class="insp-label">ESP32 CPU Load</span><span class="insp-val" style="color:#38bdf8;">{cpu_val}%</span></div>
                    <div class="insp-row"><span class="insp-label">Current Task Payload</span><span class="insp-val">{latest['Task_Size']} MB</span></div>
                    <div class="insp-row"><span class="insp-label">Task Complexity</span><span class="insp-val">{latest['Task_Complexity']}/10</span></div>
                    <div class="insp-row"><span class="insp-label">Decision Strategy</span><span class="insp-val" style="color:{"#10b981" if not is_offload else "#3b82f6"};">{latest['Decision']}</span></div>
                `;
            }} else if (type === 'tower') {{
                titleEl.innerHTML = '📡 Telecom Tower Node';
                bodyEl.innerHTML = `
                    <div class="insp-row"><span class="insp-label">WiFi RSSI Signal</span><span class="insp-val" style="color:#a855f7;">{rssi_val} dBm</span></div>
                    <div class="insp-row"><span class="insp-label">Network Latency</span><span class="insp-val" style="color:#ec4899;">{latest['Network_Latency']} ms</span></div>
                    <div class="insp-row"><span class="insp-label">Active Transceivers</span><span class="insp-val">3 Sector Antennas</span></div>
                    <div class="insp-row"><span class="insp-label">Signal Quality</span><span class="insp-val">{"Excellent" if rssi_val > -60 else "Moderate" if rssi_val > -75 else "Poor"}</span></div>
                `;
            }} else if (type === 'server') {{
                titleEl.innerHTML = '🖥️ Edge Data-Center Server Rack';
                bodyEl.innerHTML = `
                    <div class="insp-row"><span class="insp-label">Server CPU Load</span><span class="insp-val" style="color:#6366f1;">{srv_val}%</span></div>
                    <div class="insp-row"><span class="insp-label">Offload Execution Cost</span><span class="insp-val">{latest['Offload_Execution_Cost']}</span></div>
                    <div class="insp-row"><span class="insp-label">Local Execution Cost</span><span class="insp-val">{latest['Local_Execution_Cost']}</span></div>
                    <div class="insp-row"><span class="insp-label">Exhaust Fan Status</span><span class="insp-val">Active ({int(200 + srv_val * 15)} RPM)</span></div>
                `;
            }}
            card.style.display = 'block';
        }}

        // ─────────────────────────────────────────────────────────────────────
        // 6. ANIMATED TELEMETRY PARTICLES (LOCAL = Green Loop, OFFLOAD = Blue Stream)
        // ─────────────────────────────────────────────────────────────────────
        const particleCount = 32;
        const particleGeo = new THREE.BufferGeometry();
        const particlePos = new Float32Array(particleCount * 3);
        particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));

        const particleColor = { "0x3b82f6" if is_offload else "0x10b981" };
        const particleMat = new THREE.PointsMaterial({{
            color: particleColor,
            size: 0.38,
            transparent: true,
            opacity: 0.95
        }});

        const particleSystem = new THREE.Points(particleGeo, particleMat);
        scene.add(particleSystem);

        const isOff = { "true" if is_offload else "false" };
        let pProgress = new Array(particleCount).fill(0).map((_, i) => i / particleCount);

        let clock = new THREE.Clock();
        function animate() {{
            requestAnimationFrame(animate);
            controls.update();
            const elapsed = clock.getElapsedTime();

            cpuCore.material.emissiveIntensity = 0.5 + Math.sin(elapsed * (({cpu_val} / 8.0) + 1.0)) * 0.5;
            fanBladeMesh.rotation.y = elapsed * (2.0 + ({srv_val} / 10.0));

            waveRings.forEach((ring, idx) => {{
                ring.scale.setScalar(1 + ((elapsed * 1.5 + idx * 0.4) % 1.5));
            }});

            leds.forEach((led, idx) => {{
                led.material.color.setHex((Math.sin(elapsed * 10 + idx) > 0) ? 0x38bdf8 : 0x1d4ed8);
            }});

            const positions = particleSystem.geometry.attributes.position.array;
            for (let i = 0; i < particleCount; i++) {{
                pProgress[i] = (pProgress[i] + 0.015) % 1.0;
                const prg = pProgress[i];

                if (isOff) {{
                    if (prg < 0.5) {{
                        const sub = prg * 2.0;
                        positions[i * 3] = -0.5 + (4.0 - (-0.5)) * sub;
                        positions[i * 3 + 1] = 0.6 + (4.8 - 0.6) * sub + Math.sin(sub * Math.PI) * 1.2;
                        positions[i * 3 + 2] = 1.5 + (-1.5 - 1.5) * sub;
                    }} else {{
                        const sub = (prg - 0.5) * 2.0;
                        positions[i * 3] = 4.0 + (8.5 - 4.0) * sub;
                        positions[i * 3 + 1] = 4.8 + (2.2 - 4.8) * sub;
                        positions[i * 3 + 2] = -1.5 + (0.0 - (-1.5)) * sub;
                    }}
                }} else {{
                    const angle = prg * Math.PI * 2;
                    positions[i * 3] = -0.5 + Math.cos(angle) * 1.35;
                    positions[i * 3 + 1] = 0.65 + Math.sin(elapsed * 4 + i) * 0.15;
                    positions[i * 3 + 2] = 1.5 + Math.sin(angle) * 1.35;
                }}
            }}
            particleSystem.geometry.attributes.position.needsUpdate = true;

            renderer.render(scene, camera);
        }}
        animate();
    </script>
</body>
</html>
"""
components.html(three_js_code, height=500)

# ─────────────────────────────────────────────────────────────────────────────
# 3. INDUSTRIAL ANALYTICS & GRAPH GRID (LAST 200 SAMPLES ONLY)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class=\"section-header\">📈 Real-Time Industrial Telemetry Analytics (Last 200 Samples)</div>", unsafe_allow_html=True)

if st.session_state.history:
    df_all = pd.DataFrame(st.session_state.history)
    df_window = df_all.tail(200).copy()
    
    paper_bg = "rgba(15, 23, 42, 0.75)"
    plot_bg = "rgba(15, 23, 42, 0.3)"
    
    col_g1, col_g2, col_g3 = st.columns(3)
    
    with col_g1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=df_window["Step"], y=df_window["Renewable_Availability"],
            mode="lines", name="Solar Renewable (%)",
            line=dict(color="#f59e0b", width=2.5),
            fill="tozeroy", fillcolor="rgba(245, 158, 11, 0.15)"
        ))
        fig1.update_layout(
            title="1. Renewable Availability vs Time (%)",
            paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
            margin=dict(l=30, r=20, t=40, b=30), height=250,
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)", range=[0, 105])
        )
        st.plotly_chart(fig1, use_container_width=True)
        
    with col_g2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df_window["Step"], y=df_window["Battery_SOC"],
            mode="lines", name="Battery SOC (%)",
            line=dict(color="#10b981", width=2.5),
            fill="tozeroy", fillcolor="rgba(16, 185, 129, 0.15)"
        ))
        fig2.update_layout(
            title="2. Battery SOC vs Time (%)",
            paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
            margin=dict(l=30, r=20, t=40, b=30), height=250,
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)", range=[0, 105])
        )
        st.plotly_chart(fig2, use_container_width=True)
        
    with col_g3:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=df_window["Step"], y=df_window["CPU_Load"],
            mode="lines", name="CPU Load (%)",
            line=dict(color="#38bdf8", width=2.5),
            fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.15)"
        ))
        fig3.update_layout(
            title="3. ESP32 CPU Load vs Time (%)",
            paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
            margin=dict(l=30, r=20, t=40, b=30), height=250,
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)", range=[0, 105])
        )
        st.plotly_chart(fig3, use_container_width=True)

    col_g4, col_g5, col_g6 = st.columns(3)
    
    with col_g4:
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(
            x=df_window["RSSI"], y=df_window["Network_Latency"],
            mode="markers", name="Transmission Latency",
            marker=dict(color=df_window["Network_Latency"], colorscale="Purples", size=7, opacity=0.85)
        ))
        fig4.update_layout(
            title="4. RSSI vs Network Latency",
            xaxis_title="RSSI (dBm)", yaxis_title="Latency (ms)",
            paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
            margin=dict(l=40, r=20, t=40, b=40), height=250,
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)")
        )
        st.plotly_chart(fig4, use_container_width=True)

    with col_g5:
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(
            x=df_window["Step"], y=df_window["Local_Execution_Cost"],
            mode="lines", name="Local Cost", line=dict(color="#06b6d4", width=2)
        ))
        fig5.add_trace(go.Scatter(
            x=df_window["Step"], y=df_window["Offload_Execution_Cost"],
            mode="lines", name="Offload Cost", line=dict(color="#3b82f6", width=2, dash="dash")
        ))
        fig5.update_layout(
            title="5. Local vs Offload Execution Cost",
            paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
            margin=dict(l=30, r=20, t=40, b=30), height=250,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)")
        )
        st.plotly_chart(fig5, use_container_width=True)

    with col_g6:
        decision_counts = df_all["Decision"].value_counts()
        labels = decision_counts.index.tolist()
        values = decision_counts.values.tolist()
        
        fig6 = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=0.55,
            marker_colors=["#10b981" if l == "LOCAL" else "#3b82f6" for l in labels],
            textinfo="percent+label", insidetextorientation="radial"
        )])
        fig6.update_layout(
            title="6. Decision Distribution Ratio",
            paper_bgcolor=paper_bg, plot_bgcolor=plot_bg,
            margin=dict(l=20, r=20, t=40, b=20), height=250,
            showlegend=False
        )
        st.plotly_chart(fig6, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# 4. SUBSYSTEM TELEMETRY TABS & DATASET EXPORTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<div class=\"section-header\">💾 Subsystem Telemetry & Dataset Exporter (`simulation_dataset.csv`)</div>", unsafe_allow_html=True)

csv_file_path = "simulation_dataset.csv"

col_ex1, col_ex2 = st.columns([2, 1])

with col_ex1:
    if st.button("⚙️ Generate 10,080-Step Dataset (7 Days)", type="primary"):
        with st.spinner("Executing simulation engine..."):
            from digital_twin_simulator import DiagnosedIoTDigitalTwin
            twin = DiagnosedIoTDigitalTwin(seed=42)
            records = [twin.step() for _ in range(10080)]
            df_gen = pd.DataFrame(records)
            df_gen.to_csv(csv_file_path, index=False)
            st.session_state.history = records
            st.success(f"Successfully generated `{csv_file_path}` ({len(df_gen):,} records)!")
            st.rerun()

with col_ex2:
    if os.path.exists(csv_file_path):
        with open(csv_file_path, "rb") as f:
            csv_bytes = f.read()
        df_check = pd.read_csv(csv_file_path)
        st.download_button(
            label=f"📥 Export Dataset ({len(df_check):,} Records)",
            data=csv_bytes,
            file_name="simulation_dataset.csv",
            mime="text/csv",
            use_container_width=True
        )

if st.session_state.history:
    with st.expander("🔍 View Recent Telemetry Records (Last 15 Steps)", expanded=False):
        df_export = pd.DataFrame(st.session_state.history)
        st.dataframe(df_export.tail(15), use_container_width=True)

# Auto-loop execution
if st.session_state.running:
    time.sleep(st.session_state.sim_speed)
    st.rerun()
