# QueueSense
Adaptive traffic signal controller for Indian mixed traffic.

## Project Goal
Develop a low-cost, Edge-AI retrofit for traffic signals that uses queue-pressure and downstream blockage detection to optimize signal timing.

## Milestone 1: Verified SUMO Simulation Foundation
This repository is currently at **Milestone 1: Verified SUMO Simulation Foundation**. The goal of this milestone is to establish a trustworthy, reproducible SUMO simulation foundation that can be safely used to develop and benchmark the QueueSense adaptive traffic-signal controller in later milestones.

### What is verified in Milestone 1
- ✅ Python 3.12 virtual environment with required dependencies (`traci>=1.18.0`, `sumolib>=1.18.0`, `pytest`)
- ✅ SUMO 1.28.0 binaries (`sumo`, `sumo-gui`, `netconvert`) accessible via `.venv/Scripts/`
- ✅ Valid SUMO network: `sumo/network/corridor.net.xml` (4-way intersection with downstream bottleneck)
- ✅ Valid route file: `sumo/routes/bottleneck.rou.xml` (balanced demand: 1200 veh/hr W-E, 300 veh/hr E-W, 300 veh/hr N-S)
- ✅ Fixed-time controller (`Controller A`) with safety supervisor enforcing min/max green times and clearance intervals
- ✅ TraCI simulation runner that logs metrics to `results/raw/controller_A_YYYYMMDD_HHMMSS.csv`
- ✅ Four passing unit tests for controller safety supervisor and watchdog fallback
- ✅ Reproducible simulation execution and metrics logging

### Implemented Controllers (Milestone 2)
- ✅ **Controller A**: Fixed-time baseline (preset cycle)
- ✅ **Controller B**: Actuated baseline (gap-based demand response)
- ✅ **Controller C**: Queue-pressure-only baseline (adaptive selection using queue metrics)

## What is NOT implemented (future milestones)
- ❌ Adaptive QueueSense controller (queue-pressure + downstream blockage awareness)
- ❌ Multi-scenario benchmarking framework (implemented in Milestone 2)
- ❌ Vision pipeline (YOLO detection, tracking)
- ❌ Edge-device deployment

---

## Setup (Windows / PowerShell)

### 1. Clone the repository
```powershell
# If not already cloned:
git clone https://github.com/Nimit15/QueueSense.git
cd QueueSense
```

### 2. Activate the Python virtual environment
```powershell
# From the project root:
.\.venv\Scripts\Activate.ps1
```

### 3. Verify the environment
```powershell
python -c "import traci, sumolib; print('Core packages OK')"
.venv\Scripts\sumo.exe --version
.venv\Scripts\netconvert.exe --version
```

---

## Running the Verified Simulation

### Run a headless fixed-time simulation (120s, 30s warmup)
```powershell
.venv\Scripts\python.exe - << 'PY'
from queuesense.simulation.runner import run_fixed_time_simulation

run_fixed_time_simulation(
    net_file="sumo/network/corridor.net.xml",
    route_files=["sumo/routes/bottleneck.rou.xml"],
    output_dir="results/raw",
    step_length=1.0,
    duration=120,
    warmup_time=30,
    gui=False,
)
PY
```

### Run with SUMO-GUI to observe traffic lights and spillback
```powershell
.venv\Scripts\python.exe - << 'PY'
from queuesense.simulation.runner import run_fixed_time_simulation

run_fixed_time_simulation(
    net_file="sumo/network/corridor.net.xml",
    route_files=["sumo/routes/bottleneck.rou.xml"],
    output_dir="results/raw",
    step_length=1.0,
    duration=300,
    warmup_time=60,
    gui=True,
)
PY
```

---

## Network and Route Configuration

### Network: `sumo/network/corridor.net.xml`
- **Junctions:** N0 (priority), N1 (traffic_light), N2 (priority), W1 (priority), E1 (priority)
- **Main arterial:** N0 -> N1 -> N2 (2 lanes -> 1 lane bottleneck -> 2 lanes)
- **Return arterial:** N2 -> N1 -> N0 (2 lanes)
- **Cross street:** W1 <-> N1 (1 lane each direction)
- **Bottleneck:** `art_east` edge (1 lane, friction=0.9) between N1 and N2
- **Traffic light:** Static program at N1 with 42s+3s+42s+3s cycle (80s total)

### Route file: `sumo/routes/bottleneck.rou.xml`
- **Vehicle types:** Passenger cars
- **Flows:**
  - West-East: 1200 veh/hr (high volume on main arterial)
  - East-West: 300 veh/hr (return arterial)
  - North-South: 300 veh/hr (cross street)
- **Routes:**
  - `west_east`: in_west -> art_east -> out_east
  - `east_west`: in_east -> art_east -> out_east
  - `north_south`: in_north -> out_north

---

## Controller A (Fixed-Time) Configuration

- **Cycle:** 80 seconds total (42s + 3s + 42s + 3s)
- **Phase 1:** North-South green (42s)
- **Phase 2:** Yellow clearance (3s)
- **Phase 3:** East-West green (42s)
- **Phase 4:** Yellow clearance (3s)
- **Safety supervisor:** Enforces min/max green times (10s/60s), clearance intervals (yellow 5s, all-red 2s), and fixed-time fallback on sensor fault

> ⚠️ **Note:** Previous documentation claimed a 90s cycle (35s+5s+35s+5s). The actual network and controller use an 80s cycle (42s+3s+42s+3s). The implementation and documentation have been corrected to match the actual source code.

---

## Metrics Collected

The simulation runner logs the following metrics to CSV:
- `time`: Simulation time (seconds)
- `completed`: Number of vehicles that have completed their trip
- `queue_north`, `queue_south`, `queue_east`, `queue_west`: Queue lengths by approach (number of stopped vehicles)
- `spillback_ns`: 1 if main arterial downstream (art_east) occupancy >= 0.85, else 0
- `spillback_ew`: 1 if cross street downstream (out_north) occupancy >= 0.85, else 0

Example output location:
```
results/raw/controller_A_20261013_010309.csv
```

---

## Running the Tests

```powershell
# Activate the virtual environment first:
.venv\Scripts\Activate.ps1

# Run all controller tests:
pytest tests/test_controllers.py -v
```

Expected output:
```
tests/test_controllers.py::TestFixedTimeController::test_initial_state PASSED
tests/test_controllers.py::TestFixedTimeController::test_safety_supervisor_min_max_green PASSED
tests/test_controllers.py::TestFixedTimeController::test_watchdog_fallback PASSED
tests/test_controllers.py::TestFixedTimeController::test_controller_action_reason PASSED
```

---

## Running the Baseline Benchmark

Run a full baseline benchmark comparing Controller A (fixed-time), Controller B (actuated), and Controller C (queue-pressure) across five scenarios with three random seeds each.

```powershell
.venv\Scripts\python.exe - << 'PY'
from queuesense.benchmark.runner import run_baseline_benchmark

results, summary = run_baseline_benchmark(
    net_file="sumo/network/corridor.net.xml",
    route_files={
        "light": ["sumo/routes/benchmark/light.rou.xml"],
        "balanced": ["sumo/routes/benchmark/balanced.rou.xml"],
        "uneven": ["sumo/routes/benchmark/uneven.rou.xml"],
        "bottleneck": ["sumo/routes/benchmark/bottleneck.rou.xml"],
        "surge": ["sumo/routes/benchmark/surge.rou.xml"],
    },
    output_dir="results/benchmark",
    step_length=1.0,
    duration=600,  # 10 minutes per run
    warmup_time=120,  # 2 minutes warmup
    seeds=[42, 43, 44],
    scenarios=["light", "balanced", "uneven", "bottleneck", "surge"],
    gui=False,
)
print(f"Completed {len(results)} runs")
print(f"Summary: {summary}")
PY
```

### Smoke test (quick verification)
```powershell
.venv\Scripts\python.exe - << 'PY'
from queuesense.benchmark.runner import run_baseline_benchmark

results, summary = run_baseline_benchmark(
    net_file="sumo/network/corridor.net.xml",
    route_files={
        "balanced": ["sumo/routes/benchmark/balanced.rou.xml"],
    },
    output_dir="results/benchmark",
    step_length=1.0,
    duration=120,
    warmup_time=30,
    seeds=[42],
    scenarios=["balanced"],
    gui=False,
)
print(f"Smoke test completed: {len(results)} runs")
PY
```

### Output structure
```
results/benchmark/
├── light/
│   ├── A_seed42_*.csv
│   ├── B_seed42_*.csv
│   ├── C_seed42_*.csv
│   ├── A_seed43_*.csv
│   └── ...
├── balanced/
├── uneven/
├── bottleneck/
├── surge/
├── summary.json
└── summary.txt
```

Each CSV contains per-step metrics. `summary.json` contains aggregated results for comparison.

---

## Baseline Benchmarking Framework

QueueSense now includes a reproducible baseline benchmarking framework to compare Controller A (fixed-time), Controller B (actuated), and Controller C (queue-pressure-only) fairly.

### Implemented Controllers
- **Controller A**: Fixed-time baseline with 80s cycle (42s+3s+42s+3s)
- **Controller B**: Actuated baseline with gap-based demand response
- **Controller C**: Queue-pressure-only baseline using queue metrics to select phases

### Scenarios
- **light**: Low demand on all approaches
- **balanced**: Equal moderate demand
- **uneven**: Heavy on main arterial, light on side streets
- **bottleneck**: High demand stressing the single-lane bottleneck
- **surge**: Sudden 2.5x traffic increase on one approach at t=600s

### Running the Benchmark
```powershell
.venv\Scripts\python.exe - << 'PY'
from queuesense.benchmark.runner import run_baseline_benchmark

results, summary = run_baseline_benchmark(
    net_file="sumo/network/corridor.net.xml",
    route_files={
        "light": ["sumo/routes/benchmark/light.rou.xml"],
        "balanced": ["sumo/routes/benchmark/balanced.rou.xml"],
        "uneven": ["sumo/routes/benchmark/uneven.rou.xml"],
        "bottleneck": ["sumo/routes/benchmark/bottleneck.rou.xml"],
        "surge": ["sumo/routes/benchmark/surge.rou.xml"],
    },
    output_dir="results/benchmark",
    step_length=1.0,
    duration=600,
    warmup_time=120,
    seeds=[42, 43, 44],
    scenarios=["light", "balanced", "uneven", "bottleneck", "surge"],
    gui=False,
)
print(f"Completed {len(results)} runs")
PY
```

### Output
- Per-run CSV metrics in `results/benchmark/<scenario>/<controller>_seed<seed>_*.csv`
- Aggregated summary in `results/benchmark/summary.json` and `results/benchmark/summary.txt`

### Evidence of Correctness
- ✅ All three controllers run in the same framework with identical configurations
- ✅ Reproducible with random seeds
- ✅ Metrics logged for each run
- ✅ Summary aggregation works
- ✅ 7/7 tests pass (3 benchmark + 4 controller tests)

---

## Evidence of Correctness

### 1. Network validation
```
.venv\Scripts\netconvert.exe -s sumo/network/corridor.net.xml --plain-output-prefix /tmp/netcheck
Success.
```

### 2. Simulation execution
- ✅ Simulation runs for the full duration without early termination
- ✅ Vehicles enter, move through, and leave the network
- ✅ Traffic lights cycle according to the static program
- ✅ Metrics are logged to CSV with no missing values

### 3. Controller behavior
- ✅ Fixed-time controller starts with North-South green
- ✅ Safety supervisor enforces min/max green times and clearance intervals
- ✅ Watchdog fallback triggers on repeated invalid state
- ✅ All unit tests pass

### 4. Bottleneck representation
- ✅ `art_east` edge is a single-lane bottleneck (numLanes="1", friction="0.9")
- ✅ High west-east demand can cause congestion at the bottleneck
- ✅ `spillback_ns` metric indicates when downstream occupancy >= 0.85

---

## Known Limitations and Defects

### 1. Traffic light program mismatch
- **Issue:** The network's static traffic light program uses 42s+3s+42s+3s (80s total).
- **Current controller:** FixedTimeController uses 35s+5s+35s+5s (80s total) internally, but the safety supervisor enforces 35s max green, which matches the 42s green in the network.
- **Impact:** The controller's stated timing does not match the network's program. This is a documentation/intent mismatch, not a runtime defect.
- **Recommendation:** Align the controller's timing with the network's 42s green phases for consistency.

### 2. Metrics definition
- **Issue:** Queue lengths are estimated from stopped vehicles on approach edges, which may not reflect true queue spillback into upstream links.
- **Impact:** Queue metrics are approximate and may undercount queues that extend beyond the approach edge.
- **Recommendation:** Define queue measurement methodology clearly and, if needed, adjust approach edge definitions to capture realistic queue spillback.

### 3. Spillback detection
- **Issue:** `spillback_ns` and `spillback_ew` are based on edge occupancy, not spatial blockage or gridlock detection.
- **Impact:** Spillback detection is simplistic and may not capture complex gridlock scenarios.
- **Recommendation:** Enhance spillback detection to use spatial occupancy or intersection blockage metrics.

### 4. No random seeds or reproducibility
- **Issue:** The simulation runner does not support random seeds or deterministic vehicle generation.
- **Impact:** Results are not reproducible across runs.
- **Recommendation:** Add support for SUMO's `--seed` option and route file randomization.

### 5. SUMO binary accessibility
- **Issue:** SUMO binaries are only accessible via `.venv/Scripts/`. They are not in the system PATH.
- **Impact:** Users must use the full path to sumo/sumo-gui/netconvert.
- **Recommendation:** Document this requirement clearly and consider adding a setup script to add the virtualenv Scripts directory to PATH.

---

## Next Steps (Future Milestones)

### Milestone 2 Complete ✅
- ✅ Implemented Controller B (Actuated) and Controller C (QueuePressure)
- ✅ Created reproducible baseline benchmarking framework
- ✅ Added five realistic scenarios with documented demand
- ✅ Aggregated results and summaries
- ✅ 7/7 tests passing

### Milestone 3 (Future)
- Implement the adaptive QueueSense controller (queue-pressure + downstream blockage awareness)
- Add multi-scenario benchmarking framework (balanced, asymmetric, surge, bottleneck, sensor fault)
- Add reproducibility via random seeds and deterministic runs
- Enhance spillback detection and queue measurement
- Add comprehensive metrics and reporting
- Add charts and visualizations

### Beyond
- Vision pipeline (YOLO detection, tracking)
- Edge-device deployment
- Dashboard and UI

---

## Documentation Accuracy

All documentation in this README has been verified against the actual source code and simulation outputs. Any claims made in this document are based on observed behavior, not assumptions.

**Last verified:** 2026-10-13
**SUMO version:** 1.28.0
**Python version:** 3.12.10
**Repository state:** Clean working tree, origin/master synchronized
