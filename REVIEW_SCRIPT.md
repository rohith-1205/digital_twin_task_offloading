# 🎤 Review Presentation Script — Fuzzy-ANN-ANFIS Adaptive Task Offloading Engine for Battery-Aware Fog/Edge IoT Nodes

> **Deck:** PROJECT_REVIEW_DECK.pptx (34 slides) · **Course:** 19CSE362 Fundamentals of Soft Computing · **Mentor:** Dr. M. Venkatesh Kumar
> **Total speaking time ≈ 10.7 minutes** at 140 words per minute, with about 2 s per slide change. Each member explains one algorithm. The same lines are in each slide's speaker notes.

---

## 0 · Timing plan

| # | Clock | Presenter | Slides | Part | Time |
|---|---|---|---|---|---|
| 1 | 0:00 – 2:10 | **Rohith S** | 1–7 | Opening, motivation and literature survey | 2:10 |
| 2 | 2:10 – 4:45 | **Sanjith M P** | 8–15 | Gap, problem, objectives, system and digital twin | 2:35 |
| 3 | 4:45 – 5:45 | **Rohith S** | 16–18 | Algorithms overview and Algorithm 1 (ANN) | 1:00 |
| 4 | 5:45 – 6:20 | **Darshan R** | 19 | Algorithm 2 (Fuzzy logic) | 0:35 |
| 5 | 6:20 – 6:55 | **Vishaanth R** | 20 | Algorithm 3 (ANFIS) | 0:35 |
| 6 | 6:55 – 7:25 | **Sanjith M P** | 21 | Algorithm 4 (ANN-ANFIS hybrid) | 0:30 |
| 7 | 7:25 – 9:10 | **Darshan R** | 22–27 | Evaluation and results | 1:45 |
| 8 | 9:10 – 10:40 | **Vishaanth R** | 28–34 | Dashboard, scope and conclusion | 1:35 |

| Presenter | Slides | Algorithm explained | Total time |
|---|---|---|---|
| **Rohith S** | 1–7, 16–18 | ANN | 3:15 |
| **Sanjith M P** | 8–15, 21 | Hybrid | 3:05 |
| **Darshan R** | 19, 22–27 | Fuzzy logic | 2:15 |
| **Vishaanth R** | 20, 28–34 | ANFIS | 2:05 |

**Speaking order:** Rohith → Sanjith → Rohith → Darshan → Vishaanth → Sanjith → Darshan → Vishaanth.

---

# PART 1 — Rohith S · Opening, motivation and literature survey

⏱️ **0:00 – 2:10 · Slides 1–7 · about 274 words**

### 🗣️ Spoken script

**[0:00]** **Slide 1 · Title.** "Good morning, respected faculty. We present the Fuzzy–ANN–ANFIS Adaptive Task Offloading Engine for Battery-Aware Fog and Edge IoT Nodes, our project for Fundamentals of Soft Computing under the guidance of Dr. M. Venkatesh Kumar. It supports SDG 7, 9 and 13."

**[0:20]** **Slide 2 · Batch Details.** "I am Rohith; I worked on the ANN predictor and the paper. Sanjith built the digital twin and the dataset, Darshan modelled the network and ran the closed-loop tests, and Vishaanth built the ANFIS layer and the dashboard."

**[0:40]** **Slide 3 · Motivation.** "Why does this matter? A solar-powered IoT node runs on a small battery. Every task drains either the CPU or the radio, results are due within five seconds, and the WiFi signal and server load keep changing. The core problem is to decide whether to run each task on the ESP32 or offload it to an edge server, without knowing the true offload cost in advance."

**[1:10]** **Slide 4 · Abstract.** "In short, a physics-based digital twin generates 10,080 labelled tasks. An ANN predicts what offloading will cost, and ANFIS with 36 learned rules decides and explains why. On unseen weeks this hybrid reaches 96.8 percent agreement with the best decision while using the least energy."

**[1:30]** **Slide 5 · Literature Survey (Papers 1–5).** "We surveyed the fifteen papers referenced in our paper. Papers one to five study offloading trade-offs, energy-harvesting offloading and deep reinforcement learning. They either optimise numerically or act as black boxes."

**[1:45]** **Slide 6 · Literature Survey (Papers 6–10).** "Papers six to ten cover digital twins and fuzzy offloaders across edge, fog and cloud. The fuzzy ones reason only on measured inputs and ignore the battery."

**[2:00]** **Slide 7 · Literature Survey (Papers 11–15).** "Papers eleven to fifteen include an ANFIS offloader, twin-assisted offloading with energy harvesting, and two energy-system works. Sanjith will now summarise what these papers leave open."

### 🔁 Handover
"Hand over to Sanjith with the last sentence above."

---

# PART 2 — Sanjith M P · Gap, problem, objectives, system and digital twin

⏱️ **2:10 – 4:45 · Slides 8–15 · about 319 words**

### 🗣️ Spoken script

**[2:10]** **Slide 8 · Literature Summary.** "Thank you, Rohith. The papers fall into six themes: offloading trade-offs, energy-harvesting schemes, deep-learning offloaders, digital twins, fuzzy and neuro-fuzzy offloaders, and energy-system reasoning."

**[2:25]** **Slide 9 · Research Gap.** "The gap is this. Fuzzy and ANFIS offloaders use measured inputs and ignore the battery. Harvesting-aware schemes cannot explain their decisions, learning offloaders are black boxes, and twins are rarely paired with interpretable control or tested in a closed loop."

**[2:45]** **Slide 10 · Problem Statement.** "So our problem: every minute the ESP32 must choose. It knows its battery, the task and its own local cost, but only the last measured signal and the last reported server load. It cannot know the offload time and energy before sending."

**[3:05]** **Slide 11 · Objectives.** "Our objectives are to build a digital twin and a labelled dataset, integrate four soft-computing algorithms, predict the offload cost from decision-time information, make every decision explainable, and evaluate everything in a closed loop with statistical tests."

**[3:20]** **Slide 12 · System Block Diagram.** "This is the full system. The twin chains the solar panel, battery, ESP32, WiFi and edge server. It gives us what the node knows and a labelled dataset. The ANN and ANFIS form the hybrid that decides, and the chosen option's energy is drawn from the battery, which closes the loop."

**[3:45]** **Slide 13 · Methodology – Overview.** "Our method has four stages: the digital twin, the dataset with oracle labels, the four algorithms, and closed-loop evaluation with a dashboard."

**[3:55]** **Slide 14 · Methodology – Digital Twin.** "The twin runs in one-minute steps. Solar power is one watt times sunlight over a thousand times 0.85. A 12 watt-hour battery charges and drains. ESP32 work is data size times work per byte, a weak signal slows the link, and a busy edge server is much slower. All twenty engineering checks pass."

**[4:20]** **Slide 15 · Methodology – Dataset and Oracle Labels.** "Seven simulated days give 10,080 tasks with 38 features. For each task we cost both options: energy times a battery price that rises as the battery empties, plus time against the five-second deadline. The cheaper option becomes the label, which we call the oracle. Rohith will now introduce the algorithms."

### 🔁 Handover
"Hand over to Rohith with the last sentence above."

---

# PART 3 — Rohith S · Algorithms overview and Algorithm 1 (ANN)

⏱️ **4:45 – 5:45 · Slides 16–18 · about 131 words**

### 🗣️ Spoken script

**[4:45]** **Slide 16 · Methodology – Four Soft-Computing Algorithms.** "We integrate four algorithms: an ANN, Mamdani fuzzy logic, ANFIS, and our proposed ANN–ANFIS hybrid, which uses the first and the third together."

**[4:55]** **Slide 17 · Methodology – Algorithm Workflows.** "Here is how each one flows. The ANN maps inputs through two hidden layers to the offload cost. Fuzzy logic fuzzifies, applies twelve rules and takes the centroid. ANFIS uses learned curves and thirty-six rules. The hybrid feeds the ANN's prediction into ANFIS."

**[5:15]** **Slide 18 · Methodology – Algorithm 1: ANN Predictor.** "Algorithm one is the ANN. It takes six inputs the node knows: task size, work per byte, last signal, last server load, and the hour as sine and cosine. Two hidden layers of 24 and 16 tanh neurons predict the offload time and energy. It has 602 weights, trained with Adam for 60 epochs on the first 5.6 days. Darshan will explain the fuzzy controller."

### 🔁 Handover
"Hand over to Darshan with the last sentence above."

---

# PART 4 — Darshan R · Algorithm 2 (Fuzzy logic)

⏱️ **5:45 – 6:20 · Slide 19 · about 74 words**

### 🗣️ Spoken script

**[5:45]** **Slide 19 · Methodology – Algorithm 2: Fuzzy Logic (Mamdani).** "Thank you, Rohith. Algorithm two is Mamdani fuzzy logic. Each input is described with words: battery Low, Medium or High; task Light, Medium or Heavy; WiFi Poor, Fair or Good. Twelve expert rules, such as 'if the task is heavy and WiFi is good, offload', are combined, and the centre of the resulting shape gives the score. It is fully explainable, but its thresholds are guesses. Vishaanth will show how ANFIS learns them instead."

### 🔁 Handover
"Hand over to Vishaanth with the last sentence above."

---

# PART 5 — Vishaanth R · Algorithm 3 (ANFIS)

⏱️ **6:20 – 6:55 · Slide 20 · about 72 words**

### 🗣️ Spoken script

**[6:20]** **Slide 20 · Methodology – Algorithm 3: ANFIS.** "Thank you, Darshan. Algorithm three is ANFIS, a fuzzy system built as a five-layer network. It fuzzifies with bell-shaped curves, multiplies them into rule strengths, normalises, computes a straight-line output for each rule, and adds them up. Its four inputs give three times three times two times two, which is thirty-six rules, and it learns 200 numbers by least squares and gradient descent. Sanjith will show how it combines with the ANN."

### 🔁 Handover
"Hand over to Sanjith with the last sentence above."

---

# PART 6 — Sanjith M P · Algorithm 4 (ANN-ANFIS hybrid)

⏱️ **6:55 – 7:25 · Slide 21 · about 70 words**

### 🗣️ Spoken script

**[6:55]** **Slide 21 · Methodology – Algorithm 4: ANN-ANFIS Hybrid.** "Thank you, Vishaanth. Algorithm four, our hybrid, is predict, then reason. The ANN predicts the offload time and energy, and ANFIS turns that, with the battery and server load, into a decision. For task T09206 the ANN predicted 353 milliseconds and 149 millijoules, close to the real 361 and 151. The strongest rule said offloading was cheaper, and the score of 0.9965 meant offload. Darshan will now present the results."

### 🔁 Handover
"Hand over to Darshan with the last sentence above."

---

# PART 7 — Darshan R · Evaluation and results

⏱️ **7:25 – 9:10 · Slides 22–27 · about 212 words**

### 🗣️ Spoken script

**[7:25]** **Slide 22 · Methodology – Evaluation.** "We trained on the first 5.6 days, then ran every algorithm on 11 unseen weeks, each one driving the battery itself. We measure agreement with the oracle, task energy, deadline misses and regret, and compare week by week with the Wilcoxon signed-rank test."

**[7:45]** **Slide 23 · Results – Model Performance.** "The hybrid has the best agreement at 96.8 percent, the least energy at 1007 joules per week, the fewest deadline misses at 8.4 per week, and the lowest regret. The ANN alone comes close only on accuracy."

**[8:05]** **Slide 24 · Results – ANN Predictor and Ablation.** "The ANN predicts offload time with R-squared 0.989 and energy with 0.987, a median error of about five percent. Removing task size hurts most, and without the ANN the hybrid's agreement drops from 96.6 to 93.6 percent."

**[8:20]** **Slide 25 · Results – Comparison of the Four Algorithms.** "Side by side, the hybrid matches the ANN's accuracy and spends the least energy of all four algorithms."

**[8:30]** **Slide 26 · Results – Statistical Significance and Design Checks.** "The hybrid uses less energy than each algorithm on its own in all eleven weeks, with p about 0.001. On accuracy it beats fuzzy logic and ANFIS alone and ties the ANN. The soft target and the ANN inputs matter most."

**[8:50]** **Slide 27 · Results – Key Observations.** "So we recommend the hybrid. The ANN alone is accurate but a black box, fuzzy logic alone loses accuracy, and ANFIS alone misses many deadlines without the cost prediction. Vishaanth will show the dashboard and conclude."

### 🔁 Handover
"Hand over to Vishaanth with the last sentence above."

---

# PART 8 — Vishaanth R · Dashboard, scope and conclusion

⏱️ **9:10 – 10:40 · Slides 28–34 · about 185 words**

### 🗣️ Spoken script

**[9:10]** **Slide 28 · GUI – Streamlit Dashboard (1/2).** "Thank you, Darshan. Our Streamlit dashboard shows every algorithm's decision for the live task, the ANN's prediction against reality, and the ANFIS rules that fired, with their weights. It also tracks each algorithm's agreement with the oracle over the last 24 simulated hours, so every decision can be explained and checked."

**[9:30]** **Slide 29 · GUI – Streamlit Dashboard (2/2).** "The ANFIS tab shows the thirty-six learned rules, the learned curves with the current input marked, and the training curve over thirty rounds."

**[9:45]** **Slide 30 · Scope and Applications.** "The work is simulation-based, for one node and one edge server. It applies to solar-powered monitoring in agriculture, structural health and remote industrial sites."

**[9:55]** **Slide 31 · Conclusion and Future Work.** "To conclude, we built a digital twin and a dataset, and integrated four soft-computing algorithms. Our hybrid is as accurate as the ANN, uses the least energy, and explains itself. It needs fewer than 800 parameters, about 3 kilobytes, so it fits on a microcontroller. Next we will calibrate the twin on real hardware, add a cloud tier, and run the model on the ESP32 itself."

**[10:25]** **Slide 32 · References I.** "Our references, the same fifteen as in our paper, are listed here."

**[10:35]** **Slide 33 · References II.** *(no speech, just move on)*

**[10:35]** **Slide 34 · Thank You.** "Thank you. We are happy to take your questions."

### 🔁 Handover
"End of the talk: invite questions."

---

# PART 9 — Reviewer questions and cheat sheet

### ❓ Questions for everyone

| Question | Crisp answer |
|---|---|
| What exactly are the four algorithms? | 1 · ANN (multilayer perceptron), 2 · Mamdani fuzzy logic, 3 · ANFIS (neuro-fuzzy), 4 · the ANN-ANFIS hybrid (proposed), which combines 1 and 3. |
| What is your main contribution? | An explainable controller that reasons on learned estimates of the unknown offload cost for a battery-powered node, developed and tested in a closed loop with a physics-based digital twin. |

### ❓ Rohith S (ANN) is likely to be asked

| Question | Crisp answer |
|---|---|
| What is task offloading? | Deciding where a computation runs: on the weak device itself or on a stronger edge server over the network. It trades CPU energy and time against radio energy and network and server delay. |
| Why is this a soft-computing problem? | The node decides with incomplete, changing information (only the last signal and server load), and the trade-off is naturally stated in vague terms. Neural learning plus fuzzy reasoning handles both. |
| Why an ANN for the cost? | The chain from signal strength to WiFi speed, packet errors and retries, plus the server slow-down near full load, is strongly non-linear. An MLP learns it from data; it reaches R² 0.989 for time and 0.987 for energy. |
| Why log targets and sine/cosine for the hour? | Offload times span 10 ms to seconds, so logs make the network learn relative error. Sine and cosine keep 23:59 and 00:00 next to each other. |
| How is overfitting avoided? | The split is chronological (first 5.6 days train, last 1.4 days test), inputs are only decision-time values, and the validation loss stays at or below the training loss. |
| How is your work different from the ANFIS offloader in [11]? | Earlier fuzzy and ANFIS offloaders [8]–[11] reason on measured inputs only. Ours reasons on the ANN's learned estimate of the unknown offload cost, models the battery, and is tested in a closed loop. |
| Why these SDGs? | SDG 7: we save solar-battery energy. SDG 9: smarter IoT and edge infrastructure. SDG 13: less wasted energy. |

### ❓ Sanjith M P (Hybrid) is likely to be asked

| Question | Crisp answer |
|---|---|
| Why a digital twin instead of a public dataset? | We need the true cost of both options for every task, and a closed loop where each choice drains the battery. Public datasets record only one outcome per task. |
| Is the twin validated? | It is verified for internal consistency: 20 engineering checks pass (for example, distance up means signal down, and the energy balance closes). It is not yet calibrated on real hardware; that is future work. |
| What is the oracle? | The exact cost comparison with perfect knowledge. The cheaper option is the label. It is an upper bound, not something a real node can run. |
| Why does the battery price rise as the battery empties? | Spending energy is riskier on a low battery. The price goes from 1 when full to 5 when empty and applies to both options, so a low battery favours offloading on a good link and local work on a poor one. |
| Where is the 'fog' in Fog/Edge? | The edge server is the fog/edge tier one hop from the IoT node. We model the node-to-edge decision; adding a cloud tier is future work. |
| How does the hybrid work, in one line? | Predict, then reason: the ANN predicts offload time and energy, and ANFIS turns that, with the battery and server load, into a decision with readable rules. |
| Why train ANFIS on the ANN's predictions? | At run time ANFIS only ever sees predictions, so training on them lets the rules learn to tolerate the predictor's errors. |
| What is the soft target? | Instead of a hard 0/1 label, ANFIS learns 0.5 + 0.5·tanh(cost difference / 0.25): how strongly one option is cheaper. Near-ties carry little weight. With hard labels agreement fell from 96.6 % to 92.5 %. |

### ❓ Darshan R (Fuzzy logic) is likely to be asked

| Question | Crisp answer |
|---|---|
| How did you choose the fuzzy membership functions? | Expert design on physical units: the WiFi breakpoints follow the rate-adaptation sensitivities (−86, −80, −74 dBm), and task load is measured in milliseconds against the 5 s deadline. |
| Mamdani or Sugeno, and why? | The baseline is Mamdani, with words on both sides of each rule, which suits hand-written expert rules. ANFIS uses Sugeno (straight-line rule outputs) because it can be trained. |
| Why a closed-loop test instead of test accuracy alone? | In a closed loop each wrong choice drains the battery and changes every later decision, which is how the node really operates. |
| Why the Wilcoxon test? | We compare the same weeks in pairs, the sample is small (11 weeks), and normality cannot be assumed. With 11 weeks, p ≈ 0.001 is the smallest value possible, meaning every week favours one side. |
| What is regret? | The average extra cost of the chosen option compared with the best option. Zero means oracle-perfect. |
| The hybrid ties the ANN on accuracy. Why is it better? | It makes cheaper mistakes: less energy than each algorithm alone in all 11 weeks (p ≈ 0.001), the lowest regret, the fewest misses, and it explains every decision. |
| Why do the battery curves look the same for every algorithm? | Task energy is about 1 % of the node's weekly use (the 0.14 W always-on load dominates), so the algorithms differ in task energy, misses and regret, not in battery level. |
| Why are your numbers slightly different from the paper? | The slides use an 11-week re-run; the paper reports ten weeks with seeds 101–110 (hybrid 97.08 %, 993 J). Both runs agree: the hybrid uses the least energy and the lowest regret. |

### ❓ Vishaanth R (ANFIS) is likely to be asked

| Question | Crisp answer |
|---|---|
| Explain the five ANFIS layers. | (1) Fuzzify with learned bell-shaped curves, (2) multiply to get rule strengths, (3) normalise, (4) a learned straight-line output per rule, (5) weighted sum = offload score. |
| Why 36 rules, and does that scale? | It is a grid of 3 × 3 × 2 × 2 words. More inputs grow the rules quickly, so clustering-based rule generation is future work. |
| What is hybrid learning? | Each round, least squares solves the 180 rule-output numbers exactly, then gradient descent nudges the 20 curve centres and widths; 30 rounds in total. |
| Why bell-shaped (Gaussian) curves? | They are smooth everywhere, so the gradients for the centres and widths exist. |
| Why ANFIS instead of just the ANN? | Same accuracy, plus readable IF–THEN rules for every decision, and lower energy and regret. |
| Can it run on an ESP32? | Yes. The ANN has 602 weights and ANFIS 200 parameters, about 3.2 KB, and one decision is under 1,000 arithmetic operations. |
| What are the limitations? | It is simulation-based with datasheet-level parameters, one node and one edge server, one task per minute, and no cloud tier. |

### 🔢 Numbers everyone must know

| Item | Value |
|---|---|
| Dataset | 7 days · 10,080 tasks × 38 features · 54 % LOCAL / 46 % OFFLOAD |
| Twin | 1 W PV · 12 Wh battery · ESP32 240 MHz · WiFi 802.11n · edge 3 GHz · 20/20 checks |
| Algorithm 1 · ANN | 6 → 24 → 16 → 2 · 602 weights · Adam · 60 epochs · R² 0.989 / 0.987 |
| Algorithm 2 · Fuzzy | Mamdani · 4 inputs × 3 words · 12 rules · centroid · 92.5 % |
| Algorithm 3 · ANFIS | 5 layers · 36 rules · 200 parameters · 30 rounds · alone 93.7 % |
| Algorithm 4 · Hybrid | 96.8 % · 1007 J/week · 8.4 misses/week · regret 0.007 |
| Significance | Less energy than each algorithm alone in 11/11 weeks, p ≈ 0.001; ties the ANN on accuracy (p = 0.83) |
| Worked example | T09206 · ANN 353 ms / 149 mJ (real 361 / 151) · score 0.9965 → OFFLOAD |
| Paper (10 weeks, seeds 101–110) | Hybrid 97.08 % · 993.0 J · beats the ANN on agreement in 9/10 weeks (p = 0.0098) |

### ⏱️ Rehearsal tips
- Rehearse with a stopwatch. Each part's time is in its header; the bracketed marks show where you should be.
- Slides 19, 20 and 21 change speaker on every slide (Darshan → Vishaanth → Sanjith). Practise those handovers together.
- Use the same example everywhere: task T09206 (Sanjith introduces the dataset, Rohith's ANN predicts its cost, Sanjith's hybrid decides it).
- If time runs short, shorten the literature slides (5–7) and the references; never cut the algorithm or results slides.
- Results slides show the 11-week re-run. If asked about the paper's numbers, use Darshan's answer above.
