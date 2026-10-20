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

print("=== Detailed Debug ===")
print("Approach data:")
for name, approach in state.approaches.items():
    obs = approach.downstream_observations[0]
    print(f"  {name}: queue={approach.queue_count}, wait={approach.mean_wait_seconds}, arrival={approach.arrival_rate}")
    print(f"    downstream: {obs.edge_occupancy_fraction:.2f} (threshold=0.30, congested={obs.congested}, eligible={obs.eligible})")

# Test D1 (gate OFF)
print("\n--- D1 (gate OFF) ---")
controller_d1 = QueueSenseController(
    alpha=0.4, beta=0.4, gamma=0.2,
    spillback_threshold=0.30, max_wait=90.0,
    spillback_gate_enabled=False  # D1: gate OFF
)
controller_d1.last_state = state
eligible_d1 = controller_d1._eligible_approaches(state)
print(f"Eligible approaches: {list(eligible_d1.keys())}")

# Manual pressure calculation for D1
north_pressure_d1 = 0.0
if "north" in eligible_d1:
    north_pressure_d1 += controller_d1._approach_pressure(state, "north")
    print(f"  North pressure: {controller_d1._approach_pressure(state, 'north'):.2f}")
if "south" in eligible_d1:
    north_pressure_d1 += controller_d1._approach_pressure(state, "south")
    print(f"  South pressure: {controller_d1._approach_pressure(state, 'south'):.2f}")
print(f"  NORTH_SOUTH total: {north_pressure_d1:.2f}")

east_pressure_d1 = 0.0
if "east" in eligible_d1:
    east_pressure_d1 += controller_d1._approach_pressure(state, "east")
    print(f"  East pressure: {controller_d1._approach_pressure(state, 'east'):.2f}")
if "west" in eligible_d1:
    east_pressure_d1 += controller_d1._approach_pressure(state, "west")
    print(f"  West pressure: {controller_d1._approach_pressure(state, 'west'):.2f}")
print(f"  EAST_WEST total: {east_pressure_d1:.2f}")

if north_pressure_d1 >= east_pressure_d1:
    print(f"  D1 should select: NORTH_SOUTH ({north_pressure_d1:.2f} >= {east_pressure_d1:.2f})")
else:
    print(f"  D1 should select: EAST_WEST ({east_pressure_d1:.2f} > {north_pressure_d1:.2f})")

# Test D2 (gate ON)
print("\n--- D2 (gate ON) ---")
controller_d2 = QueueSenseController(
    alpha=0.4, beta=0.4, gamma=0.2,
    spillback_threshold=0.30, max_wait=90.0,
    spillback_gate_enabled=True   # D2: gate ON
)
controller_d2.last_state = state
eligible_d2 = controller_d2._eligible_approaches(state)
print(f"Eligible approaches: {list(eligible_d2.keys())}")

# Manual pressure calculation for D2
north_pressure_d2 = 0.0
if "north" in eligible_d2:
    north_pressure_d2 += controller_d2._approach_pressure(state, "north")
    print(f"  North pressure: {controller_d2._approach_pressure(state, 'north'):.2f}")
if "south" in eligible_d2:
    north_pressure_d2 += controller_d2._approach_pressure(state, "south")
    print(f"  South pressure: {controller_d2._approach_pressure(state, 'south'):.2f}")
print(f"  NORTH_SOUTH total: {north_pressure_d2:.2f}")

east_pressure_d2 = 0.0
if "east" in eligible_d2:
    east_pressure_d2 += controller_d2._approach_pressure(state, "east")
    print(f"  East pressure: {controller_d2._approach_pressure(state, 'east'):.2f}")
if "west" in eligible_d2:
    east_pressure_d2 += controller_d2._approach_pressure(state, "west")
    print(f"  West pressure: {controller_d2._approach_pressure(state, 'west'):.2f}")
print(f"  EAST_WEST total: {east_pressure_d2:.2f}")

if north_pressure_d2 >= east_pressure_d2:
    print(f"  D2 should select: NORTH_SOUTH ({north_pressure_d2:.2f} >= {east_pressure_d2:.2f})")
else:
    print(f"  D2 should select: EAST_WEST ({east_pressure_d2:.2f} > {north_pressure_d2:.2f})")

# Now test the actual controller methods
print("\n--- Actual Controller Methods ---")
print(f"D1 _select_phase_from_pressure: {controller_d1._select_phase_from_pressure(state)}")
print(f"D2 _select_phase_from_pressure: {controller_d2._select_phase_from_pressure(state)}")

print(f"D1 _calculate_pressure NORTH_SOUTH: {controller_d1._calculate_pressure(state, Phase.NORTH_SOUTH):.2f}")
print(f"D1 _calculate_pressure EAST_WEST: {controller_d1._calculate_pressure(state, Phase.EAST_WEST):.2f}")
print(f"D2 _calculate_pressure NORTH_SOUTH: {controller_d2._calculate_pressure(state, Phase.NORTH_SOUTH):.2f}")
print(f"D2 _calculate_pressure EAST_WEST: {controller_d2._calculate_pressure(state, Phase.EAST_WEST):.2f}")