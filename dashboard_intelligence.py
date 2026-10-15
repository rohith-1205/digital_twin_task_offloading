"""
Dashboard section for the intelligent decision layer (ANN + Fuzzy + ANFIS).
Used by streamlit_app.py:

    render_intelligence(history, styled, csv_path)   → live decisions + 4 tabs of charts
    render_explanation()                             → always-visible "how it works" guide

Kept in its own file so streamlit_app.py stays short and easy to read.
"""

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hybrid_offloading import (ANFIS_INPUTS, ANFIS_UNITS, closed_loop_comparison, decision_inputs,
                               inputs_from_records, train_all)

# One colour per controller, reused in every chart
CTRL_COLORS = {"🎯 Oracle": "#facc15", "🌫️ Fuzzy only": "#c084fc",
               "🧠 ANN only": "#22d3ee", "⭐ ANN + ANFIS": "#34d399"}
WORD_COLORS = ["#f87171", "#fbbf24", "#34d399", "#60a5fa", "#c084fc"]

CSS = """
<style>
  .ctrl { border-radius: 14px; padding: 12px 14px; background: rgba(15,23,42,.75);
          border: 1px solid rgba(255,255,255,.08); border-left: 5px solid var(--c);
          box-shadow: 0 0 22px -10px var(--c); }
  .ctrl .n { font-size: .78rem; font-weight: 800; color: #cbd5e1; }
  .ctrl .d { font-size: 1.25rem; font-weight: 900; color: var(--c); margin: 2px 0; }
  .ctrl .bar { height: 7px; border-radius: 6px; background: rgba(255,255,255,.08); overflow: hidden; }
  .ctrl .bar > div { height: 100%; background: linear-gradient(90deg, #2dd4bf, #60a5fa); }
  .ctrl .s { font-size: .7rem; color: #94a3b8; margin-top: 4px; }
  .pipe { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 6px 0 14px; }
  .pipe .box { padding: 9px 13px; border-radius: 12px; font-weight: 800; font-size: .82rem; color: #0b1026; }
  .pipe .arrow { color: #94a3b8; font-weight: 900; }
  .explain { border-radius: 16px; padding: 16px 20px; margin-bottom: 12px; background: rgba(15,23,42,.8);
             border: 1px solid rgba(255,255,255,.08); border-top: 4px solid var(--c); }
  .explain h3 { margin: 0 0 6px; color: var(--c); font-size: 1.05rem; }
  .explain p, .explain li { color: #e2e8f0; font-size: .88rem; line-height: 1.55; }
  .explain code { color: #fde68a; background: rgba(250,204,21,.08); }
  .explain table { width: 100%; font-size: .84rem; border-collapse: collapse; }
  .explain td, .explain th { padding: 5px 8px; border-bottom: 1px solid rgba(255,255,255,.08); text-align: left; }
</style>
"""


# ════════════════════════════════════════════════════════════════════════════
# CACHED TRAINING  (re-runs only when simulation_dataset.csv changes)
# ════════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner="🧠 Training the ANN, fuzzy and ANFIS models on the 7-day dataset…")
def load_models(csv_path, csv_mtime):
    return train_all(pd.read_csv(csv_path))


@st.cache_data(show_spinner="🏆 Running each controller on an unseen week (closed loop)…")
def load_comparison(_models, csv_mtime):
    return closed_loop_comparison(_models)


# ════════════════════════════════════════════════════════════════════════════
# SMALL UI HELPERS
# ════════════════════════════════════════════════════════════════════════════
def controller_card(col, name, decision, score, note):
    color = CTRL_COLORS[name]
    icon = "⚡" if decision == "OFFLOAD" else "💻"
    col.markdown(f'<div class="ctrl" style="--c:{color}"><div class="n">{name}</div>'
                 f'<div class="d">{icon} {decision}</div>'
                 f'<div class="bar"><div style="width:{100 * score:.0f}%"></div></div>'
                 f'<div class="s">offload score {score:.2f} · {note}</div></div>', unsafe_allow_html=True)


def membership_figure(title, x, curves, unit, current=None, log_x=False, styled=None):
    """Plot fuzzy sets (one coloured line per word) and mark the current input value."""
    fig = go.Figure()
    for i, (label, y) in enumerate(curves.items()):
        c = WORD_COLORS[i % len(WORD_COLORS)]
        fig.add_trace(go.Scatter(x=x, y=y, name=label, mode="lines", line=dict(color=c, width=3),
                                 fill="tozeroy", fillcolor=c + "22"))
    if current is not None:
        fig.add_vline(x=current, line=dict(color="#f8fafc", width=2, dash="dash"),
                      annotation_text=f"now {current:.1f}", annotation_font_color="#f8fafc")
    if log_x:
        fig.update_xaxes(type="log")
    fig.update_yaxes(range=[0, 1.05])
    return styled(fig, title, unit, "membership μ", height=290)


# ════════════════════════════════════════════════════════════════════════════
# MAIN SECTION
# ════════════════════════════════════════════════════════════════════════════
def render_intelligence(history, styled, csv_path):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="section">🤖 Intelligent decision layer: 🧠 ANN + 🌫️ Fuzzy logic + 🔗 ANFIS</div>',
                unsafe_allow_html=True)
    if not os.path.exists(csv_path):
        st.info("Generate the 7-day dataset (💾 Dataset section) to train the intelligent controllers.")
        return

    models = load_models(csv_path, os.path.getmtime(csv_path))
    fuzzy, ann, hybrid, predictor = models["fuzzy"], models["ann"], models["hybrid"], models["predictor"]

    st.markdown("""
<div class="pipe">
  <div class="box" style="background:#22d3ee">🧠 ANN predicts offload time + energy</div><div class="arrow">➜</div>
  <div class="box" style="background:#c084fc">🌫️ Fuzzify: SOC · energy ratio · time gain · server load</div><div class="arrow">➜</div>
  <div class="box" style="background:#34d399">🔗 ANFIS learned rules → offload score</div><div class="arrow">➜</div>
  <div class="box" style="background:#facc15">💻 LOCAL / ⚡ OFFLOAD</div>
</div>""", unsafe_allow_html=True)

    # ── 1. Live: what would every controller decide for the current task? ──
    latest = history[-1]
    previous = history[-2] if len(history) > 1 else None
    inputs = inputs_from_records(previous, latest)
    hyb = hybrid.explain(inputs)
    fz_score = float(fuzzy.score(inputs)[0])
    ann_score = float(ann.score(inputs)[0])

    st.markdown(f"**Live task {latest['Task_ID']}** · {latest['Task_Type']} · {latest['Task_Size']:.0f} KB  "
                f"— the twin uses the 🎯 oracle; the other three only see what the ESP32 knows before deciding.")
    cards = st.columns(4)
    oracle_off = latest["Decision"] == "OFFLOAD"
    controller_card(cards[0], "🎯 Oracle", latest["Decision"], 1.0 if oracle_off else 0.0, "exact costs, perfect knowledge")
    controller_card(cards[1], "🌫️ Fuzzy only", "OFFLOAD" if fz_score > 0.5 else "LOCAL", fz_score, "hand-written rules")
    controller_card(cards[2], "🧠 ANN only", "OFFLOAD" if ann_score > 0.5 else "LOCAL", ann_score, "black-box network")
    controller_card(cards[3], "⭐ ANN + ANFIS", "OFFLOAD" if hyb["score"] > 0.5 else "LOCAL", hyb["score"], "predict → reason")

    left, right = st.columns([1, 1.6])
    with left:
        st.markdown("**🧠 ANN prediction vs reality** (for this task)")
        err_t = 100 * (hyb["pred_time_ms"] / latest["Offload_Total_Time"] - 1)
        err_e = 100 * (hyb["pred_energy_mJ"] / latest["Offload_Energy"] - 1)
        m1, m2 = st.columns(2)
        m1.metric("Offload time", f'{hyb["pred_time_ms"]:.0f} ms', f"{err_t:+.1f} % vs real {latest['Offload_Total_Time']:.0f} ms",
                  delta_color="off")
        m2.metric("Offload energy", f'{hyb["pred_energy_mJ"]:.1f} mJ', f"{err_e:+.1f} % vs real {latest['Offload_Energy']:.1f} mJ",
                  delta_color="off")
        st.markdown("**🌫️ ANFIS inputs (crisp values)**")
        st.dataframe(pd.DataFrame({"Input": ANFIS_INPUTS, "Value": np.round(hyb["features"], 2), "Unit": ANFIS_UNITS}),
                     hide_index=True, use_container_width=True)
    with right:
        st.markdown("**🔗 ANFIS rules that fired for this task** (weight = share of the final decision)")
        st.dataframe(pd.DataFrame([{"IF (· = AND)": r, "weight": w, "THEN offload score": f} for r, w, f in hyb["rules"]]),
                     hide_index=True, use_container_width=True, column_config={
                         "weight": st.column_config.ProgressColumn("weight", min_value=0, max_value=1, format="%.2f"),
                         "THEN offload score": st.column_config.ProgressColumn("THEN offload score", min_value=0,
                                                                               max_value=1, format="%.2f")})
        st.markdown("**🌫️ Mamdani expert rules that fired** (fuzzy-only controller)")
        fired = fuzzy.explain(inputs)
        st.dataframe(pd.DataFrame(fired, columns=["Rule", "strength"]) if fired else pd.DataFrame({"Rule": ["(none)"]}),
                     hide_index=True, use_container_width=True, column_config={
                         "strength": st.column_config.ProgressColumn("strength", min_value=0, max_value=1, format="%.2f")})

    # Live agreement over the last 24 simulated hours
    if len(history) > 2:
        recent = pd.DataFrame(history[-1440:])
        data = decision_inputs(recent).iloc[1:]
        oracle = data["Oracle_Offload"].to_numpy() > 0.5
        agree = {name: 100 * np.mean((c.score(data) > 0.5) == oracle)
                 for name, c in (("🌫️ Fuzzy only", fuzzy), ("🧠 ANN only", ann), ("⭐ ANN + ANFIS", hybrid))}
        st.caption("Agreement with the oracle over the live run (last 24 h): " +
                   " · ".join(f"{k} **{v:.1f} %**" for k, v in agree.items()))

    # ── 2. Tabs with the inside of each model ────────────────────────────────
    t_ann, t_fuzzy, t_anfis, t_cmp = st.tabs(["🧠 ANN predictor", "🌫️ Fuzzy logic (Mamdani)",
                                              "🔗 ANFIS (neuro-fuzzy)", "🏆 Controller comparison"])
    val = models["val"]

    with t_ann:
        q = models["predictor_quality"]
        a, b, c, d = st.columns(4)
        a.metric("Offload time R²", f"{q['time_r2']:.3f}")
        b.metric("Time median error", f"{q['time_mape']:.1f} %")
        c.metric("Offload energy R²", f"{q['energy_r2']:.3f}")
        d.metric("Energy median error", f"{q['energy_mape']:.1f} %")
        cols = st.columns(3)
        fig = go.Figure()
        for label, hist, color in (("predictor train", predictor.net.history["train"], "#22d3ee"),
                                   ("predictor validation", predictor.net.history["val"], "#f472b6"),
                                   ("classifier train", ann.net.history["train"], "#facc15"),
                                   ("classifier validation", ann.net.history["val"], "#fb923c")):
            fig.add_trace(go.Scatter(y=hist, name=label, mode="lines", line=dict(color=color, width=2.5)))
        fig.update_yaxes(type="log")
        cols[0].plotly_chart(styled(fig, "Learning curves (loss per epoch)", "Epoch", "Loss (log)"),
                             use_container_width=True, theme=None)
        t_pred, e_pred = predictor.predict(val)
        for col, real, pred, title, unit, color in (
                (cols[1], val["Offload_Total_Time"], t_pred, "Offload time: predicted vs real", "ms", "#22d3ee"),
                (cols[2], val["Offload_Energy"], e_pred, "Offload energy: predicted vs real", "mJ", "#34d399")):
            fig = go.Figure(go.Scatter(x=real, y=pred, mode="markers", name="validation tasks",
                                       marker=dict(size=4, opacity=.5, color=color)))
            lo, hi = float(min(real.min(), pred.min())), float(max(real.max(), pred.max()))
            fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="perfect prediction",
                                     line=dict(color="#f8fafc", dash="dash")))
            fig.update_xaxes(type="log")
            fig.update_yaxes(type="log")
            col.plotly_chart(styled(fig, title, f"real ({unit})", f"predicted ({unit})"),
                             use_container_width=True, theme=None)
        st.caption("Inputs: task size, task complexity, last RSSI, last server load, hour of day. "
                   "Network: 6 → 24 → 16 → 2 neurons (tanh), trained with Adam. Validation = last 1.4 days, never seen in training.")

    with t_fuzzy:
        cols = st.columns(2)
        grids = {"SOC": np.linspace(0, 100, 300), "Local_Exec_Time": np.logspace(0, 4.3, 300),
                 "Last_RSSI": np.linspace(-95, -40, 300), "Last_Server_Load": np.linspace(0, 100, 300)}
        for i, (key, var) in enumerate(fuzzy.inputs.items()):
            x = grids[key]
            cols[i % 2].plotly_chart(membership_figure(f"{var.name}", x, var.fuzzify(x), var.unit,
                                                       current=float(inputs[key]), log_x=var.log_axis, styled=styled),
                                     use_container_width=True, theme=None)
        x = fuzzy.universe
        st.plotly_chart(membership_figure("Output: offload score (defuzzified by centre of gravity)", x,
                                          fuzzy.output.fuzzify(x), "score", current=fz_score, styled=styled),
                        use_container_width=True, theme=None)
        from fuzzy_logic import rule_text
        st.markdown("**📜 Expert rule base (12 rules, AND = minimum)**")
        st.dataframe(pd.DataFrame({"#": range(1, len(fuzzy.rules) + 1),
                                   "Rule": [rule_text(c, o) for c, o in fuzzy.rules]}),
                     hide_index=True, use_container_width=True)

    with t_anfis:
        anfis = hybrid.anfis
        h = anfis.history
        a, b, c = st.columns(3)
        a.metric("Rules learned", f"{len(anfis.rules)}")
        b.metric("Validation accuracy vs oracle", f"{100 * h['val_acc'][-1]:.1f} %",
                 f"validation MSE {100 * (h['val_mse'][-1] / h['val_mse'][0] - 1):+.0f} % from tuning",
                 delta_color="inverse")
        c.metric("Trainable parameters", f"{sum(len(x) for x in anfis.c) * 2 + anfis.theta.size}")
        cols = st.columns(2)
        X_train = hybrid.anfis_features(models["train"])
        for i, name in enumerate(ANFIS_INPUTS):
            x = np.linspace(X_train[:, i].min(), X_train[:, i].max(), 300)
            cols[i % 2].plotly_chart(membership_figure(f"Learned sets: {name}", x, anfis.membership_curve(i, x),
                                                       ANFIS_UNITS[i], current=float(hyb["features"][i]), styled=styled),
                                     use_container_width=True, theme=None)
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=h["train_mse"], name="train MSE", line=dict(color="#34d399", width=3)))
        fig.add_trace(go.Scatter(y=h["val_mse"], name="validation MSE", line=dict(color="#f472b6", width=3)))
        st.plotly_chart(styled(fig, "Hybrid learning: least squares (consequents) + gradient descent (membership shapes)",
                               "Epoch", "MSE"), use_container_width=True, theme=None)
        st.caption("The words are relative to the range seen in training (e.g. SOC 15–57 %), and the shapes are learned. "
                   "Inputs outside that range are clipped to its edge, so ANFIS never extrapolates wildly.")
        st.markdown("**📜 Most used learned rules** (usage = share of all firing on the validation days)")
        st.dataframe(pd.DataFrame(anfis.rule_table(hybrid.anfis_features(val), top=12)),
                     hide_index=True, use_container_width=True, column_config={
                         "score": st.column_config.ProgressColumn("offload score", min_value=0, max_value=1, format="%.2f"),
                         "usage_%": st.column_config.ProgressColumn("usage %", min_value=0, max_value=30, format="%.1f")})

    with t_cmp:
        st.markdown("**Offline: accuracy on the validation data (last 1.4 days of the dataset)** (same inputs, no closed loop)")
        st.dataframe(models["offline"].round(2), hide_index=True, use_container_width=True)
        summary, soc = load_comparison(models, os.path.getmtime(csv_path))
        st.markdown("**Closed loop on an UNSEEN week** (new random seed). Each controller drives the battery itself, "
                    "so every mistake changes the energy left for later tasks.")
        st.dataframe(summary.round(2), hide_index=True, use_container_width=True)
        cols = st.columns(4)
        bar_colors = [CTRL_COLORS[n] for n in summary["Controller"]]
        for col, metric, title in ((cols[0], "Agreement with oracle (%)", "Agreement with oracle (%) ↑"),
                                   (cols[1], "Task energy (J)", "Energy spent on tasks (J) ↓"),
                                   (cols[2], "Deadline misses", "Deadline misses ↓"),
                                   (cols[3], "Mean regret (cost)", "Extra cost vs oracle ↓")):
            fig = go.Figure(go.Bar(x=summary["Controller"], y=summary[metric], marker_color=bar_colors,
                                   text=summary[metric].round(2), textposition="outside", cliponaxis=False))
            fig.update_yaxes(range=[0, 1.2 * max(summary[metric].max(), 1e-9)])     # room for the labels
            col.plotly_chart(styled(fig, title, "", "", height=300), use_container_width=True, theme=None)
        fig = go.Figure()
        for name in soc.columns:
            fig.add_trace(go.Scatter(x=np.arange(len(soc)) / 60, y=soc[name], name=name, mode="lines",
                                     line=dict(color=CTRL_COLORS[name], width=2)))
        st.plotly_chart(styled(fig, "Battery SOC when each controller is in charge (unseen week)", "Simulated time (h)",
                               "SOC (%)", height=340), use_container_width=True, theme=None)
        st.caption("The SOC curves almost overlap: task energy is small next to the base load and the solar input, "
                   "so the controllers differ mainly in task energy, deadline misses and regret (bars above).")


# ════════════════════════════════════════════════════════════════════════════
# ALWAYS-VISIBLE EXPLANATION (bottom of the dashboard)
# ════════════════════════════════════════════════════════════════════════════
def render_explanation():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="section">📚 How ANN, fuzzy logic and ANFIS work together in this project</div>',
                unsafe_allow_html=True)
    st.markdown("""
<div class="explain" style="--c:#facc15">
  <h3>🎯 1 · Why add an intelligent layer?</h3>
  <p>The physics engine decides by comparing the <b>exact</b> cost of LOCAL and OFFLOAD. It can do that because a
  simulator knows everything. A real ESP32 <b>does not</b>: before it sends a task it cannot know the real network
  latency, how much radio energy the retransmissions will cost, or how busy the edge server will be.
  It only knows its battery SOC, the task, the <i>last</i> measured RSSI and the <i>last</i> load reported by the server.</p>
  <p>So the exact comparison becomes the <b>🎯 oracle</b> (the best possible answer), and we build controllers that
  decide with realistic, incomplete information and grade them against it.</p>
</div>

<div class="explain" style="--c:#22d3ee">
  <h3>🧠 2 · ANN: the predictor ("what will offloading cost?")</h3>
  <p>An <b>Artificial Neural Network</b> learns a function from examples. Our multilayer perceptron
  (6 → 24 → 16 → 2 neurons, tanh activations, Adam optimiser, written in plain NumPy) is trained on the 10,080 simulated tasks.</p>
  <ul>
    <li><b>Inputs:</b> task size, task complexity, last RSSI, last server load, hour of day</li>
    <li><b>Outputs:</b> predicted <code>Offload_Total_Time</code> (ms) and <code>Offload_Energy</code> (mJ)</li>
    <li><b>Why an ANN:</b> the link → rate → retransmission → latency chain is strongly non-linear and noisy. A network
        learns it from data without hand-written equations.</li>
    <li><b>Weakness:</b> used alone as a decision maker (🧠 ANN only), it is a <b>black box</b>: it cannot say <i>why</i> it chose.</li>
  </ul>
</div>

<div class="explain" style="--c:#c084fc">
  <h3>🌫️ 3 · Fuzzy logic: the reasoner ("what should I do about it?")</h3>
  <p>Fuzzy logic reasons with vague words instead of hard thresholds. "SOC = 34 %" is not simply <i>low</i> or
  <i>medium</i>: it is <b>Low 0.07</b> and <b>Medium 0.70</b> at the same time.</p>
  <table>
    <tr><th>Step</th><th>What happens</th><th>Example</th></tr>
    <tr><td>1 · Fuzzify</td><td>number → membership degree of each word</td><td>RSSI −76 dBm → Fair 0.9, Good 0.0</td></tr>
    <tr><td>2 · Rules</td><td>IF … AND … THEN …; AND = minimum</td><td>IF task Heavy AND link Fair → OFFLOAD</td></tr>
    <tr><td>3 · Aggregate</td><td>each rule clips its output set at its strength; take the max</td><td>OFFLOAD cut at 0.6</td></tr>
    <tr><td>4 · Defuzzify</td><td>centre of gravity → one crisp score</td><td>score 0.78 → OFFLOAD</td></tr>
  </table>
  <p><b>🌫️ Fuzzy only</b> uses 12 hand-written expert rules on measured values. It is fully explainable, but the expert's
  thresholds are guesses, and it has no idea what offloading will really cost.</p>
</div>

<div class="explain" style="--c:#34d399">
  <h3>🔗 4 · ANFIS: the bridge ("fuzzy rules that learn like a neural network")</h3>
  <p><b>ANFIS</b> (Adaptive Neuro-Fuzzy Inference System, Jang 1993) is a fuzzy system built as a 5-layer network,
  so its rules can be <b>trained from data</b>:</p>
  <table>
    <tr><th>Layer</th><th>Role</th><th>Learned?</th></tr>
    <tr><td>1 · Fuzzification</td><td>Gaussian sets μ(x) = exp(−(x−c)²/2σ²) for each word</td><td>✅ c, σ (gradient descent)</td></tr>
    <tr><td>2 · Rule strength</td><td>w = product of the memberships (AND)</td><td>—</td></tr>
    <tr><td>3 · Normalise</td><td>w̄ = w / Σw</td><td>—</td></tr>
    <tr><td>4 · Rule output</td><td>f = p·x + q (Takagi–Sugeno)</td><td>✅ p, q (least squares)</td></tr>
    <tr><td>5 · Output</td><td>offload score = Σ w̄·f</td><td>—</td></tr>
  </table>
  <p>Our ANFIS has 4 inputs: <b>Battery SOC</b> (Low/Medium/High), <b>Energy ratio</b> E_offload/E_local
  (Offload cheaper/Similar/Local cheaper), <b>Time gain</b> (Small/Large) and <b>Server load</b> (Light/Busy).
  That gives 3·3·2·2 = <b>36 rules</b>. Each epoch of <b>hybrid learning</b> solves the rule outputs exactly by least squares,
  then nudges the membership shapes by gradient descent. It is taught by a soft oracle preference
  (0 = LOCAL clearly cheaper, 1 = OFFLOAD clearly cheaper).</p>
</div>

<div class="explain" style="--c:#fb923c">
  <h3>⭐ 5 · The hybrid: ANN ➜ ANFIS</h3>
  <p><b>Predict → Reason → Decide.</b> The ANN turns uncertain network and server conditions into two predicted numbers.
  These become the <i>Energy ratio</i> and <i>Time gain</i> inputs of ANFIS, whose learned fuzzy rules make the final call.
  ANFIS is trained on the ANN's <b>predictions</b> (not the true values), so its rules learn to cope with the ANN's errors.</p>
  <ul>
    <li>From the <b>ANN</b> it gets accuracy: it knows what offloading will cost.</li>
    <li>From <b>fuzzy logic</b> it gets explainability: every decision shows the IF–THEN rules that fired.</li>
    <li>From <b>ANFIS</b> learning, the rules and their thresholds are tuned from data instead of guessed.</li>
  </ul>
</div>

<div class="explain" style="--c:#f472b6">
  <h3>🏆 6 · How to read the comparison</h3>
  <table>
    <tr><th>Metric</th><th>Meaning</th></tr>
    <tr><td>Agreement with oracle</td><td>% of tasks where the controller made the same choice as the exact comparison</td></tr>
    <tr><td>Task energy</td><td>battery energy actually spent on tasks during the unseen week (lower is better)</td></tr>
    <tr><td>Deadline misses</td><td>tasks whose result arrived after 5 s</td></tr>
    <tr><td>Mean regret</td><td>average extra cost J compared with the best option (0 = perfect)</td></tr>
    <tr><td>Decision time</td><td>Python time for one decision. On an ESP32, a 36-rule ANFIS + small MLP fits in a few KB of RAM</td></tr>
  </table>
  <p>The test week uses a <b>different random seed</b> from the training data, and each controller drives the battery
  itself (closed loop). The scores therefore measure generalisation, not memorisation.</p>
</div>
""", unsafe_allow_html=True)
