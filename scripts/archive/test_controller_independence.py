"""Test to verify controller instances are independent per junction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from run_stage_c_benchmark import build_controllers

def test_controller_instances_independent():
    """Test that each junction gets its own controller instance."""
    # Get controllers
    controllers = build_controllers()

    # Verify all D2 controllers are separate instances
    d2_controllers = [controllers["D2"][j] for j in ["J1", "J2", "J3"]]
    instance_ids = [id(c) for c in d2_controllers]

    print(f"Controller instance IDs: {instance_ids}")
    print(f"All unique: {len(set(instance_ids)) == 3}")

    assert len(set(instance_ids)) == 3, f"Shared controller instances found! IDs: {instance_ids}"

    # Verify each has the correct configuration
    for j, ctrl in controllers["D2"].items():
        assert isinstance(ctrl, type(controllers["D2"]["J1"])), f"{j} controller type mismatch"
        assert ctrl.spillback_gate_enabled == True, f"{j} D2 controller should have gate enabled"
        assert ctrl.alpha == 0.4, f"{j} D2 controller alpha mismatch"
        print(f"PASS: {j} D2 controller: gate={ctrl.spillback_gate_enabled}, alpha={ctrl.alpha}")

def test_controller_state_independence():
    """Test that updating one junction's state doesn't affect others."""
    controllers = build_controllers()

    # Store original states
    original_states = {}
    for j, ctrl in controllers["D2"].items():
        original_states[j] = ctrl.last_state

    # Simulate state update for J1
    from queuesense.state import TrafficState
    from unittest.mock import MagicMock

    # Create mock state for J1
    j1_state = TrafficState(
        timestamp=100.0,
        approaches={
            "north": MagicMock(), "south": MagicMock(), "east": MagicMock(), "west": MagicMock()
        },
        all_valid=True
    )

    # Update J1 controller
    controllers["D2"]["J1"].last_state = j1_state

    # Verify only J1 was affected
    assert controllers["D2"]["J1"].last_state is j1_state, "J1 state not properly stored"
    assert controllers["D2"]["J2"].last_state == original_states["J2"], "J2 state unexpectedly modified"
    assert controllers["D2"]["J3"].last_state == original_states["J3"], "J3 state unexpectedly modified"

    print("PASS: Controller state independence verified")

def test_all_controllers_independent():
    """Test that all controller types (A, B, C, D1, D2) have independent instances."""
    controllers = build_controllers()

    for ctrl_id, junctions in controllers.items():
        print(f"\nChecking {ctrl_id} controllers...")
        instances = [junctions[j] for j in ["J1", "J2", "J3"]]

        # Check instance independence
        instance_ids = [id(c) for c in instances]
        unique_ids = set(instance_ids)

        if len(unique_ids) != 3:
            print(f"FAIL: {ctrl_id} controllers are shared!")
            print(f"  Instance IDs: {instance_ids}")
            print(f"  Unique IDs: {unique_ids}")
            assert False, f"Shared controller instances found for {ctrl_id}"
        else:
            print(f"PASS: {ctrl_id} controllers are independent")

        # Verify configuration is consistent across instances
        first_ctrl = instances[0]
        for j, ctrl in junctions.items():
            assert type(ctrl) == type(first_ctrl), f"Type mismatch in {ctrl_id} {j}"

    # Test D1 vs D2 specific configuration
    d1_controllers = [controllers["D1"][j] for j in ["J1", "J2", "J3"]]
    d2_controllers = [controllers["D2"][j] for j in ["J1", "J2", "J3"]]

    # Verify D1 gate is disabled and D2 gate is enabled
    for idx, j in enumerate(["J1", "J2", "J3"]):
        assert not d1_controllers[idx].spillback_gate_enabled, f"D1 {j} should have gate disabled"
        assert d2_controllers[idx].spillback_gate_enabled, f"D2 {j} should have gate enabled"

    print("\nPASS: All controller types verified for independence and configuration")

if __name__ == "__main__":
    print("Testing controller instance independence...")
    test_controller_instances_independent()
    test_controller_state_independence()
    test_all_controllers_independent()
    print("\nAll tests passed!")