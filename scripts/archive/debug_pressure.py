#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from queuesense.state import TrafficState, ApproachState, DownstreamObservation
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.base import Phase

def create_synthetic_state_for_test():
    return TrafficState(
        timestamp=100.0,
        approaches={
            "north": ApproachState(
                queue_count=8.0,
                mean_wait_seconds=15.0,
                arrival_rate=12.0,
                downstream_available=True,
                measurement_valid=True,
                downstream_observations=[
                    DownstreamObservation(
                        edge_id="out_north",
                        observation_valid=True,
                        edge_occupancy_fraction=0.15,
                        occupancy_fraction=0.15,
                        threshold=0.30,
                        congested=False,
                        eligible=True,
                        gate_suppresses=False,
                        error=""
                    )
                ]
            ),
            "south": ApproachState(
                queue_count=6.0,
                mean_wait_seconds=12.0,
                arrival_rate=10.0,
                downstream_available=True,
                measurement_valid=True,
                downstream_observations=[
                    DownstreamObservation(
                        edge_id="out_north",
                        observation_valid=True,
                        edge_occupancy_fraction=0.12,
                        occupancy_fraction=0.12,
                        threshold=0.30,
                        congested=False,
                        eligible=True,
                        gate_suppresses=False,
                        error=""
                    )
                ]
            ),
            "east": ApproachState(
                queue_count=4.0,
                mean_wait_seconds=8.0,
                arrival_rate=8.0,
                downstream_available=True,
                measurement_valid=True,
                downstream_observations=[
                    DownstreamObservation(
                        edge_id="art_west_1",
                        observation_valid=True,
                        edge_occupancy_fraction=0.20,
                        occupancy_fraction=0.20,
                        threshold=0.30,
                        congested=False,
                        eligible=True,
                        gate_suppresses=False,
                        error=""
                    )
                ]
            ),
            "west": ApproachState(
                queue_count=10.0,
                mean_wait_seconds=20.0,
                arrival_rate=15.0,
                downstream_available=False,
                measurement_valid=True,
                downstream_observations=[
                    DownstreamObservation(
                        edge_id="art_east_1",
                        observation_valid=True,
                        edge_occupancy_fraction=0.45,
                        occupancy_fraction=0.45,
                        threshold=0.30,
                        congested=True,
                        eligible=False,
                        gate_suppresses=False,
                        error=""
                    )
                ]
            )
        },
        all_valid=True,
    )

state = create_synthetic_state_for_test()
controller = QueueSenseController()

print("=== Pressure Calculation Debug ===")
print("Approach data:")
for name, approach in state.approaches.items():
    obs = approach.downstream_observations[0]
    queue_norm = min(approach.queue_count / 20.0, 1.0)
    wait_norm = min(approach.mean_wait_seconds / controller.max_wait, 1.0)
    arrival_norm = min(approach.arrival_rate / 30.0, 1.0)
    pressure = controller.alpha * queue_norm + controller.beta * wait_norm + controller.gamma * arrival_norm
    print(f"  {name}: queue={approach.queue_count}->norm={queue_norm:.2f}, "
          f"wait={approach.mean_wait_seconds}->norm={wait_norm:.2f}, "
          f"arrival={approach.arrival_rate}->norm={arrival_norm:.2f} "
          f"-> pressure={pressure:.2f} (downstream occ={obs.edge_occupancy_fraction:.2f}, eligible={obs.eligible})")

print("\nPhase pressures:")
ns_pressure = controller._calculate_pressure(state, Phase.NORTH_SOUTH)
ew_pressure = controller._calculate_pressure(state, Phase.EAST_WEST)
print(f"  NORTH_SOUTH: {ns_pressure:.2f}")
print(f"  EAST_WEST: {ew_pressure:.2f}")

print(f"\nEligible approaches:")
eligible_all = controller._eligible_approaches(state)
print(f"  All eligible: {list(eligible_all.keys())}")

controller_gate_on = QueueSenseController(spillback_gate_enabled=True)
eligible_gate_on = controller_gate_on._eligible_approaches(state)
print(f"  Gate ON eligible: {list(eligible_gate_on.keys())}")

controller_gate_off = QueueSenseController(spillback_gate_enabled=False)
eligible_gate_off = controller_gate_off._eligible_approaches(state)
print(f"  Gate OFF eligible: {list(eligible_gate_off.keys())}")

# Calculate pressures with gate restrictions
print("\nPressure calculations with gate restrictions:")
# For NORTH_SOUTH phase: north + south
ns_pressure_gate_on = 0.0
if 'north' in eligible_gate_on:
    n_obs = state.approaches['north'].downstream_observations[0]
    n_queue_norm = min(state.approaches['north'].queue_count / 20.0, 1.0)
    n_wait_norm = min(state.approaches['north'].mean_wait_seconds / controller.max_wait, 1.0)
    n_arrival_norm = min(state.approaches['north'].arrival_rate / 30.0, 1.0)
    n_pressure = controller.alpha * n_queue_norm + controller.beta * n_wait_norm + controller.gamma * n_arrival_norm
    ns_pressure_gate_on += n_pressure
    print(f"  NORTH_SOUTH north component: {n_pressure:.2f}")
if 'south' in eligible_gate_on:
    s_obs = state.approaches['south'].downstream_observations[0]
    s_queue_norm = min(state.approaches['south'].queue_count / 20.0, 1.0)
    s_wait_norm = min(state.approaches['south'].mean_wait_seconds / controller.max_wait, 1.0)
    s_arrival_norm = min(state.approaches['south'].arrival_rate / 30.0, 1.0)
    s_pressure = controller.alpha * s_queue_norm + controller.beta * s_wait_norm + controller.gamma * s_arrival_norm
    ns_pressure_gate_on += s_pressure
    print(f"  NORTH_SOUTH south component: {s_pressure:.2f}")
print(f"  NORTH_SOUTH total (gate ON): {ns_pressure_gate_on:.2f}")

# For EAST_WEST phase: east + west
ew_pressure_gate_on = 0.0
if 'east' in eligible_gate_on:
    e_obs = state.approaches['east'].downstream_observations[0]
    e_queue_norm = min(state.approaches['east'].queue_count / 20.0, 1.0)
    e_wait_norm = min(state.approaches['east'].mean_wait_seconds / controller.max_wait, 1.0)
    e_arrival_norm = min(state.approaches['east'].arrival_rate / 30.0, 1.0)
    e_pressure = controller.alpha * e_queue_norm + controller.beta * e_wait_norm + controller.gamma * e_arrival_norm
    ew_pressure_gate_on += e_pressure
    print(f"  EAST_WEST east component: {e_pressure:.2f}")
if 'west' in eligible_gate_on:
    w_obs = state.approaches['west'].downstream_observations[0]
    w_queue_norm = min(state.approaches['west'].queue_count / 20.0, 1.0)
    w_wait_norm = min(state.approaches['west'].mean_wait_seconds / controller.max_wait, 1.0)
    w_arrival_norm = min(state.approaches['west'].arrival_rate / 30.0, 1.0)
    w_pressure = controller.alpha * w_queue_norm + controller.beta * w_wait_norm + controller.gamma * w_arrival_norm
    ew_pressure_gate_on += w_pressure
    print(f"  EAST_WEST west component: {w_pressure:.2f}")
print(f"  EAST_WEST total (gate ON): {ew_pressure_gate_on:.2f}")

# Gate OFF pressures (should be same as ungated)
print(f"\nGate OFF pressures (all approaches eligible):")
print(f"  NORTH_SOUTH: {ns_pressure:.2f} (same as ungated)")
print(f"  EAST_WEST: {ew_pressure:.2f} (same as ungated)")