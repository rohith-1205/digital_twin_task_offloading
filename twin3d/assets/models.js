/* Optional realistic 3D assets (GLB / GLTF).
   ---------------------------------------------------------------
   Drop a .glb file into this folder and point to it below; the scene
   replaces the procedural model with it (auto-scaled to the same size).
   Leave an entry out to keep the built-in procedural model.
   Paths are relative to the twin3d/ folder (works for Streamlit and the web viewer).
   Keys: solar, battery, esp32, gateway, server.
   Note: browsers block GLB loading from file:// — serve the folder
   (python -m http.server) when using the web viewer with GLB files.
   Example:
     window.TWIN_GLB_MODELS = { solar: 'assets/solar_panel.glb' };
*/
window.TWIN_GLB_MODELS = window.TWIN_GLB_MODELS || {};
