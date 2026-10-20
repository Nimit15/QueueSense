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

# Test D1
print("=== Testing D1 (gate OFF) ===")
controller_d1 = QueueSenseController(
    alpha=0.4, beta=0.4, gamma=0.2,
    spillback_threshold=0.30, max_wait=90.0,
    spillback_gate_enabled=False
)
controller_d1.last_state = create_synthetic_state_for_test()
controller_d1.state = Phase.EAST_WEST
controller_d1.elapsed = 15.0

print(f"State: {controller_d1.state}")
print(f"Elapsed: {controller_d1.elapsed}")
print(f"Min green: {controller_d1.config.min_green}")
should_end = controller_d1._should_end_phase()
print(f"Should end phase: {should_end}")

if should_end:
    next_phase = controller_d1._next_phase()
    print(f"Next phase: {next_phase}")

    # Let's also check the pressure calculations
    ns_pressure = controller_d1._calculate_pressure(controller_d1.last_state, Phase.NORTH_SOUTH)
    ew_pressure = controller_d1._calculate_pressure(controller_d1.last_state, Phase.EAST_WEST)
    print(f"NORTH_SOUTH pressure: {ns_pressure:.2f}")
    print(f"EAST_WEST pressure: {ew_pressure:.2f}")

    # Check eligibility
    eligible = controller_d1._eligible_approaches(controller_d1.last_state)
    print(f"Eligible approaches: {list(eligible.keys())}")

action_d1 = controller_d1.compute_action(1.0)
print(f"Action: {action_d1['phase']} - {action_d1['reason']}")

# Test D2
print("\n=== Testing D2 (gate ON) ===")
controller_d2 = QueueSenseController(
    alpha=0.4, beta=0.4, gamma=0.2,
    spillback_threshold=0.30, max_wait=90.0,
    spillback_gate_enabled=True
)
controller_d2.last_state = create_synthetic_state_for_test()
controller_d2.state = Phase.EAST_WEST
controller_d2.elapsed = 15.0

print(f"State: {controller_d2.state}")
print(f"Elapsed: {controller_d2.elapsed}")
print(f"Min green: {controller_d2.config.min_green}")
should_end = controller_d2._should_end_phase()
print(f"Should end phase: {should_end}")

if should_end:
    next_phase = controller_d2._next_phase()
    print(f"Next phase: {next_phase}")

    # Let's also check the pressure calculations
    ns_pressure = controller_d2._calculate_pressure(controller_d2.last_state, Phase.NORTH_SOUTH)
    ew_pressure = controller_d2._calculate_pressure(controller_d2.last_state, Phase.EAST_WEST)
    print(f"NORTH_SOUTH pressure: {ns_pressure:.2f}")
    print(f"EAST_WEST pressure: {ew_pressure:.2f}")

    # Check eligibility
    eligible = controller_d2._eligible_approaches(controller_d2.last_state)
    print(f"Eligible approaches: {list(eligible.keys())}")

action_d2 = controller_d2.compute_action(1.0)
print(f"Action: {action_d2['phase']} - {action_d2['reason']}")