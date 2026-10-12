# Benchmark Protocol & Evaluation Methodology

## 1. Experimental Design
The goal is to scientifically evaluate whether QueueSense (Controller D) delivers statistically significant performance gains over conventional controllers under realistic mixed traffic and downstream spillback conditions.

---

## 2. Four Controllers (Ablation Benchmark)

| Controller | Name | Description | Purpose |
|------------|------|-------------|---------|
| **Controller A** | Fixed-Time | Preset 90s cycle (35s green, 5s clearance per phase). | Conventional Indian baseline without sensor automation. |
| **Controller B** | SUMO Actuated | Gap-based induction-loop controller (extends green while headway < threshold). | Standard automated industry benchmark. |
| **Controller C** | Queue-Pressure | Adaptive green allocation based on $P_i = \alpha Q_i + \beta W_i + \gamma A_i$, blind to exit blockage. | Tests if queue-pressure alone solves congestion. |
| **Controller D** | **QueueSense** | Queue-pressure + Downstream spillback constraint + Safety supervisor. | Full proposed innovation. Isolates the impact of exit-space awareness. |

---

## 3. Evaluation Scenarios

1. **Balanced Traffic:** Equal flow (600 veh/hr/approach). Tests if adaptive controllers introduce unnecessary jitter when fixed cycles are optimal.
2. **Asymmetric Traffic:** Heavy North-South corridor (1200 veh/hr) vs light East-West corridor (300 veh/hr). Tests dynamic split adaptation.
3. **Surge / Peak Period:** Sudden 2.5x traffic surge on one approach at $t=600\text{s}$. Tests reaction time and recovery speed.
4. **Downstream Bottleneck (Spillback):** Downstream link capacity choked (e.g. lane drop / red signal at next intersection). Causes queues to spill back into the primary junction. **Primary test of Controller D's core differentiator.**
5. **Sensor Fault:** 15% randomly dropped observations + complete vision loss at $t=1200\text{s}$ for 5 minutes. Tests fail-safe fallback to fixed-timing.

---

## 4. Key Performance Indicators (KPIs)

- **Mean Vehicle Delay (seconds):** Total time lost due to deceleration, stopped delay, and queue crawling.
- **95th-Percentile Delay (seconds):** Measures tail-end delays and extreme vehicle wait times.
- **Max Queue Length (meters & vehicles):** Peak physical queue per approach.
- **Intersection Throughput (veh/hr):** Total completed trips cleared through the junction.
- **Spillback Incidents & Blocked Duration (seconds):** Number of times vehicles enter an already choked exit, blocking the junction grid.
- **Fairness Index (Gini Coefficient / Max:Min Delay Ratio):** Ensures side streets are not starved.

---

## 5. Statistical Rigor
- Every scenario is evaluated across **10 matched random seeds** (e.g., seeds 42 to 51) so that all four controllers encounter the exact same vehicle arrival sequences, speeds, and mixed-vehicle compositions.
- Results are reported with mean $\pm$ standard deviation and 95% confidence intervals.
