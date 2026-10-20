"""Deterministic test of D1 vs D2 pressure calculation with known values."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.controllers.base import Phase

def make_state(west_blocked, west_queue=10.0, east_queue=4.0, north_queue=8.0, south_queue=6.0):
    """Create a state where west is optionally blocked downstream."""
    return TrafficState(
        timestamp=100.0,
        approaches={
            "north": ApproachState(
                queue_count=north_queue, mean_wait_seconds=15.0, arrival_rate=12.0,
                downstream_available=True, measurement_valid=True
            ),
            "south": ApproachState(
                queue_count=south_queue, mean_wait_seconds=12.0, arrival_rate=10.0,
                downstream_available=True, measurement_valid=True
            ),
            "east": ApproachState(
                queue_count=east_queue, mean_wait_seconds=8.0, arrival_rate=8.0,
                downstream_available=True, measurement_valid=True
            ),
            "west": ApproachState(
                queue_count=west_queue, mean_wait_seconds=20.0, arrival_rate=15.0,
                downstream_available=not west_blocked, measurement_valid=True
            ),
        },
        all_valid=True,
    )

def test_pressure_calculation():
    """Test that D2 excludes blocked approaches from pressure calculation."""
    state_blocked = make_state(west_blocked=True)
    state_clear = make_state(west_blocked=False)

    # D1 (gate OFF) - all approaches eligible
    d1 = QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2,
                             spillback_threshold=0.30, max_wait=90.0,
                             spillback_gate_enabled=False)
    d1.last_state = state_clear
    d1_eligible = d1._eligible_approaches(state_clear)
    print(f"D1 (gate OFF) eligible approaches: {list(d1_eligible.keys())}")
    print(f"D1 (gate OFF) _next_phase: {d1._next_phase().name}")

    # D2 (gate ON) - west blocked
    d2 = QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2,
                             spillback_threshold=0.30, max_wait=90.0,
                             spillback_gate_enabled=True)
    d2.last_state = state_blocked
    d2_eligible = d2._eligible_approaches(state_blocked)
    print(f"\nD2 (gate ON) eligible approaches: {list(d2_eligible.keys())}")
    print(f"D2 (gate ON) _next_phase: {d2._next_phase().name}")

    # Verify pressure calculations
    print("\n--- Pressure calculations ---")
    for name in ["north", "south", "east", "west"]:
        p_d1 = d1._approach_pressure(state_clear, name)
        p_d2 = d2._approach_pressure(state_blocked, name)
        print(f"  {name}: D1 pressure={p_d1:.4f}, D2 pressure={p_d2:.4f}")

    # Verify phase selection
    phase_d1 = d1._next_phase()
    phase_d2 = d2._next_phase()
    print(f"\nPhase selection: D1={phase_d1.name}, D2={phase_d2.name}")

    # D2 should select NORTH_SOUTH because west is blocked
    assert phase_d2 == Phase.NORTH_SOUTH, f"D2 should select NORTH_SOUTH, got {phase_d2.name}"
    print("PASS: D2 correctly selects NORTH_SOUTH when west is blocked")

    # D1 should select EAST_WEST (higher pressure with west included)
    assert phase_d1 == Phase.EAST_WEST, f"D1 should select EAST_WEST, got {phase_d1.name}"
    print("PASS: D1 correctly selects EAST_WEST when gate is OFF")

def test_eligibility_mapping():
    """Test that _eligible_approaches correctly filters blocked approaches."""
    state_blocked = make_state(west_blocked=True)

    d2 = QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2,
                             spillback_threshold=0.30, max_wait=90.0,
                             spillback_gate_enabled=True)
    d2.last_state = state_blocked

    eligible = d2._eligible_approaches(state_blocked)
    print(f"\nEligible approaches (D2, gate ON, west blocked): {list(eligible.keys())}")
    assert "west" not in eligible, "West should not be eligible when blocked"
    assert "north" in eligible, "North should be eligible"
    assert "south" in eligible, "South should be eligible"
    assert "east" in eligible, "East should be eligible"
    print("PASS: Eligibility mapping correct")

if __name__ == "__main__":
    print("Testing pressure calculation and eligibility...")
    test_pressure_calculation()
    test_eligibility_mapping()
    print("\nAll pressure tests passed!")