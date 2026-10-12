# CLAUDE.md - QueueSense Project Instructions

## Project Overview
QueueSense is an Edge-AI adaptive traffic-signal controller designed for mixed Indian traffic conditions, submitted to the **SEVA First Innovation Challenge 2026 (Category II: Diploma & Higher Education)**.

The core engineering hypothesis: In mixed, non-lane-based traffic, **queue pressure** (class-weighted queue + waiting time + arrival flow) combined with **downstream blockage prevention (spillback awareness)** outperforms conventional pre-timed and gap-based actuated signal control without requiring expensive centralized traffic management centers.

---

## Architectural Principles & Strict Rules

1. **Decoupled Perception and Control:**
   - The decision engine (`src/queuesense/controllers/`) and the vision pipeline (`src/queuesense/vision/`) communicate solely via a standardized `TrafficState` data structure (`src/queuesense/state.py`).
   - Do NOT tightly couple camera frame processing directly to SUMO step loops.
   - Benchmark the control logic using SUMO ground truth first. Benchmark perception separately. Then test end-to-end with injected sensor noise.

2. **No Double-Counting Vehicle Size:**
   - Do NOT multiply PCU (Passenger Car Unit) weight by bounding box pixel area.
   - PCU weights account for physical road footprint and sluggishness. Use calibrated vehicle-class counts OR calibrated spatial occupancy, never both multiplied together.

3. **Downstream Blockage is a Hard Constraint:**
   - Downstream receiving road space is an eligibility check, not an arbitrary term in the queue pressure formula.
   - If a receiving road is saturated (> threshold), the controller must suppress or delay the green phase for that movement, even if its approach queue score is the highest.
   - If all exits are blocked, execute the documented safe-state policy (clear intersection, hold phases or cycle to permissible non-conflicting movements).

4. **Identical Safety Rules Across All Baselines:**
   - All 4 benchmarked controllers MUST obey identical minimum green times (e.g. 10s), maximum green caps (e.g. 60s), yellow/all-red clearance intervals, and pedestrian safety phases.
   - Never skip clearance transitions. Never toggle directly between conflicting greens.
   - In case of sensor fault, dropped frames, or measurement uncertainty, fallback immediately to an approved fixed-time schedule.

5. **Ablation Benchmark Protocol (The Core Deliverable):**
   - **Controller A:** Fixed-Time (Preset cycle plan).
   - **Controller B:** SUMO Actuated (Standard gap-based induction-loop controller).
   - **Controller C:** Queue-Pressure Only (Adaptive on queue + wait time + arrivals, but blind to downstream blockage).
   - **Controller D (QueueSense):** Queue-Pressure + Downstream Blockage Awareness + Safety Constraints.
   - Run across 5 scenarios: Balanced, Asymmetric, Surge, Bottleneck (Spillback), and Sensor Fault.
   - Evaluate across 10 matched random seeds per scenario. Report mean, standard deviation, and 95th percentile metrics.

6. **Perception Strategy:**
   - Do NOT train YOLO from scratch or download the full 153 GB BMD-45 dataset.
   - Use the pre-trained IISc AIM UVH-26 YOLOv11-S checkpoint (`UVH-26-MV-YOLOv11-S.pt`) from `iisc-aim/UVH-26` on Hugging Face.
   - Evaluate detection on Indian CCTV camera perspectives.

---

## Standardized TrafficState Schema (`src/queuesense/state.py`)

```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class ApproachState:
    queue_count: float        # Class-weighted queue (PCU or count)
    mean_wait_seconds: float  # Average waiting time of stopped vehicles
    arrival_rate: float       # Vehicles arriving per minute
    downstream_available: bool # False if exit road is blocked/spilling back
    measurement_valid: bool   # False if camera failed or occluded

@dataclass
class TrafficState:
    timestamp: float
    approaches: Dict[str, ApproachState] # Keys: 'north', 'south', 'east', 'west'
    all_valid: bool
```

---

## Directory Structure & Responsibilities

```
QueueSense/
├── CLAUDE.md                   # This instruction file
├── README.md                   # High-level overview
├── requirements.txt            # Python dependencies
├── configs/
│   └── experiment.yaml         # Simulation, controller & scenario parameters
├── docs/
│   ├── architecture.md         # Full system architecture diagram & details
│   ├── controller_design.md    # Math formulas, state machine, safety logic
│   ├── benchmark_protocol.md   # Testing protocol, 5 scenarios, metrics, seeds
│   └── data_sources.md         # UVH-26, BMD-45, IRC 106 citations & licences
├── sumo/
│   ├── network/                # .net.xml and netconvert source files
│   ├── routes/                 # .rou.xml demand files for 5 scenarios
│   └── configs/                # .sumocfg simulation runtime configs
├── src/
│   └── queuesense/
│       ├── __init__.py
│       ├── state.py            # Standard TrafficState data structures
│       ├── controllers/
│       │   ├── base.py         # BaseController with safety supervisor
│       │   ├── fixed_time.py   # Controller A
│       │   ├── actuated.py     # Controller B (wrapper/native)
│       │   ├── queue_pressure.py # Controller C
│       │   └── queuesense.py   # Controller D (Full system)
│       ├── simulation/
│       │   ├── runner.py       # TraCI simulation runner
│       │   └── providers.py    # Ground truth & noisy sensor state providers
│       ├── metrics/
│       │   └── collector.py    # Delay, queue length, throughput, spillback logger
│       └── vision/
│           ├── detector.py     # UVH-26 YOLOv11-S inference wrapper
│           └── tracker.py      # ByteTrack / multi-object approach ROI tracking
├── scripts/
│   ├── generate_network.py     # Builds 2-junction corridor with bottleneck
│   ├── run_benchmark.py        # Runs 4 controllers across seeds & scenarios
│   ├── plot_results.py         # Generates comparative bar/line plots
│   └── download_model.py       # Downloads UVH-26-MV-YOLOv11-S.pt from HF
├── tests/
│   ├── test_state.py
│   ├── test_controllers.py
│   ├── test_safety.py
│   └── test_metrics.py
└── results/
    ├── raw/                    # Raw CSV logs per seed & controller
    └── summary/                # Aggregated tables and plots for Screen-1/2
```

---

## Development Workflow & Commands

1. **Environment Activation:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Verify Environment:**
   ```powershell
   python -c "import traci, sumolib, ultralytics; print('All core tools OK')"
   sumo --version
   ```

3. **Generate Network & Scenarios:**
   ```powershell
   python scripts/generate_network.py
   ```

4. **Run Smoke Test (Single seed, 1 scenario, Controller A vs D):**
   ```powershell
   python scripts/run_benchmark.py --scenario bottleneck --seeds 42 --controllers A,D --gui
   ```

5. **Run Full Benchmark (10 seeds, all 5 scenarios, 4 controllers):**
   ```powershell
   python scripts/run_benchmark.py --seeds 10 --controllers A,B,C,D
   python scripts/plot_results.py
   ```

6. **Run Unit Tests:**
   ```powershell
   pytest tests/ -v
   ```

---

## Coding Standards & Rules for Claude Code
- Always inspect existing code before editing. Do not overwrite or remove working modules.
- Use explicit type annotations and docstrings for all functions.
- Every decision made by `QueueSenseController` must log its rationale (`reason="Approach North selected: Score=18.4, Exit clear"`).
- Keep all numerical thresholds (min_green, max_green, alpha, beta, gamma, spillback_threshold) in `configs/experiment.yaml`. Never hardcode magic numbers.
- Write unit tests for every new controller logic or safety supervisor feature before integrating with TraCI.
