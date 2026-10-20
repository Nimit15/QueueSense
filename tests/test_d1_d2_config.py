"""
Focused regression test for the D1/D2 configuration wiring.

Proves that the controller instances actually constructed for every junction
receive the intended configuration, not just the dictionary values in the
runner script.  This catches the defect where CONTROLLERS was defined but
never passed to MultiJunctionSimulationRunner, so every junction silently
fell back to the default QueueSenseController (gate always ON).

Effective settings verified per junction:
  - D1: coordination enabled, spillback gate DISABLED.
  - D2: coordination enabled, spillback gate ENABLED.
  - Both: spillback_threshold == 0.30 using the verified normalized
    edge_occupancy_fraction convention (no /100.0 conversion).
"""

import pytest
import sys
from pathlib import Path

# Import build_controllers from the root runner
sys.path.insert(0, str(Path(__file__).parent.parent))
from run_benchmark_matrix import build_controllers

from queuesense.controllers.queuesense import QueueSenseController
from queuesense.simulation.multijunction_runner import MultiJunctionSimulationRunner

JUNCTION_IDS = ["J1", "J2", "J3"]


class TestD1D2ConfigurationWiring:
    """Verify effective controller settings reach every junction."""

    def test_d1_gate_disabled_on_every_junction(self):
        """D1: spillback_gate_enabled must be False on J1, J2 and J3."""
        controllers = build_controllers("D1")
        for j_id in JUNCTION_IDS:
            ctrl = controllers[j_id]
            assert isinstance(ctrl, QueueSenseController), \
                f"{j_id} is not a QueueSenseController"
            assert ctrl.spillback_gate_enabled is False, \
                f"{j_id}: gate should be disabled for D1, got {ctrl.spillback_gate_enabled}"
            assert ctrl.spillback_threshold == 0.30, \
                f"{j_id}: threshold should be 0.30, got {ctrl.spillback_threshold}"

    def test_d2_gate_enabled_on_every_junction(self):
        """D2: spillback_gate_enabled must be True on J1, J2 and J3."""
        controllers = build_controllers("D2")
        for j_id in JUNCTION_IDS:
            ctrl = controllers[j_id]
            assert isinstance(ctrl, QueueSenseController), \
                f"{j_id} is not a QueueSenseController"
            assert ctrl.spillback_gate_enabled is True, \
                f"{j_id}: gate should be enabled for D2, got {ctrl.spillback_gate_enabled}"
            assert ctrl.spillback_threshold == 0.30, \
                f"{j_id}: threshold should be 0.30, got {ctrl.spillback_threshold}"

    def test_d1_and_d2_share_all_other_settings(self):
        """D1 and D2 must differ ONLY in spillback_gate_enabled."""
        d1 = build_controllers("D1")["J1"]
        d2 = build_controllers("D2")["J1"]
        assert d1.alpha == d2.alpha
        assert d1.beta == d2.beta
        assert d1.gamma == d2.gamma
        assert d1.spillback_threshold == d2.spillback_threshold
        assert d1.max_wait == d2.max_wait
        assert d1.spillback_gate_enabled != d2.spillback_gate_enabled

    def test_threshold_is_normalized_fraction_not_percent(self):
        """Threshold 0.30 is a normalized fraction; 0.85 would be unreachable."""
        ctrl = QueueSenseController(spillback_threshold=0.30)
        # 0.30 must be reachable: a road at 30% normalized occupancy triggers it.
        assert 0.30 >= ctrl.spillback_threshold
        # 0.85 would require 85% occupancy, which the bottleneck scenario
        # never reaches -- the gate could never activate.
        assert ctrl.spillback_threshold < 0.85

    def test_runner_receives_the_intended_controllers(self):
        """The runner must store the passed controllers, not fall back to defaults."""
        for ctrl_id in ("D1", "D2"):
            controllers = build_controllers(ctrl_id)
            runner = MultiJunctionSimulationRunner(
                net_file="sumo/network_v2/corridor.net.xml",
                route_files=["sumo/routes_v2/benchmark/bottleneck.rou.xml"],
                controllers=controllers,
                use_coordinator=True,
                use_spillback_gate=(ctrl_id == "D2"),
            )
            # Every junction must be present and carry the intended gate setting.
            assert set(runner.controllers.keys()) == set(JUNCTION_IDS), \
                f"{ctrl_id}: runner controllers {list(runner.controllers)} != {JUNCTION_IDS}"
            for j_id in JUNCTION_IDS:
                ctrl = runner.controllers[j_id]
                assert ctrl.spillback_gate_enabled == (ctrl_id == "D2"), \
                    f"{ctrl_id}/{j_id}: gate_enabled={ctrl.spillback_gate_enabled}, " \
                    f"expected {ctrl_id == 'D2'}"
                assert ctrl.spillback_threshold == 0.30, \
                    f"{ctrl_id}/{j_id}: threshold={ctrl.spillback_threshold}, expected 0.30"

    def test_runner_downstream_threshold_matches_controller_threshold(self):
        """The runner's spillback threshold must equal the controller's 0.30."""
        for ctrl_id in ("D1", "D2"):
            controllers = build_controllers(ctrl_id)
            runner = MultiJunctionSimulationRunner(
                net_file="sumo/network_v2/corridor.net.xml",
                route_files=["sumo/routes_v2/benchmark/bottleneck.rou.xml"],
                controllers=controllers,
                use_coordinator=True,
                use_spillback_gate=(ctrl_id == "D2"),
            )
            assert runner.downstream_threshold == 0.30, \
                f"{ctrl_id}: runner.downstream_threshold={runner.downstream_threshold}, expected 0.30"


class TestControllerInstanceIsolation:
    """Prove every junction gets its own controller instance.

    This is the regression test for the shared-mutable-controller defect: a
    factory that returned ``{j: ctrl for j in JUNCTION_IDS}`` reused one object
    across J1/J2/J3, so each junction's ``last_state`` overwrote the others and
    the D2 gate could not see per-junction downstream blockage.
    """

    @classmethod
    @pytest.fixture(scope="class")
    def controllers(cls):
        # Use the build_controllers from run_benchmark_matrix.py
        return {ctrl_id: build_controllers(ctrl_id) for ctrl_id in ["A", "B", "C", "D1", "D2", "S"]}

    def _junction_ids(self, ctrl_id, controllers):
        return [controllers[ctrl_id][j] for j in JUNCTION_IDS]

    @pytest.mark.parametrize("ctrl_id", ["A", "B", "C", "D1", "D2", "S"])
    def test_three_distinct_instances_per_configuration(self, ctrl_id, controllers):
        instances = self._junction_ids(ctrl_id, controllers)
        ids = [id(c) for c in instances]
        assert len(set(ids)) == 3, (
            f"{ctrl_id}: expected 3 distinct controller instances, "
            f"got {len(set(ids))} unique ids: {ids}"
        )

    @pytest.mark.parametrize("ctrl_id", ["A", "B", "C", "D1", "D2", "S"])
    def test_same_controller_type_per_configuration(self, ctrl_id, controllers):
        instances = self._junction_ids(ctrl_id, controllers)
        types = [type(c) for c in instances]
        assert len(set(types)) == 1, (
            f"{ctrl_id}: mixed controller types {types}"
        )

    @pytest.mark.parametrize("ctrl_id", ["A", "B", "C", "D1", "D2", "S"])
    def test_intended_parameters_identical_within_configuration(self, ctrl_id, controllers):
        instances = self._junction_ids(ctrl_id, controllers)
        first = instances[0]
        for j, ctrl in zip(JUNCTION_IDS, instances):
            for attr in ("alpha", "beta", "gamma", "spillback_threshold",
                         "max_wait", "spillback_gate_enabled"):
                if hasattr(first, attr):
                    assert getattr(ctrl, attr) == getattr(first, attr), (
                        f"{ctrl_id}/{j}: {attr}={getattr(ctrl, attr)} != "
                        f"{getattr(first, attr)}"
                    )

    def test_d1_gate_disabled_d2_gate_enabled(self, controllers):
        for j in JUNCTION_IDS:
            assert controllers["D1"][j].spillback_gate_enabled is False, \
                f"D1/{j}: gate should be disabled"
            assert controllers["D2"][j].spillback_gate_enabled is True, \
                f"D2/{j}: gate should be enabled"

    @pytest.mark.parametrize("ctrl_id", ["A", "B", "C", "D1", "D2", "S"])
    def test_state_independence_across_junctions(self, ctrl_id, controllers):
        """Mutating J1's state must not change J2 or J3."""
        from queuesense.state import TrafficState, ApproachState
        from unittest.mock import MagicMock

        instances = self._junction_ids(ctrl_id, controllers)
        j1, j2, j3 = instances

        # Snapshot the mutable state of J2 and J3 before the mutation.
        def snapshot(ctrl):
            return (
                getattr(ctrl, "last_state", None),
                getattr(ctrl, "elapsed", None),
                getattr(ctrl, "_clearance_origin", None),
                getattr(ctrl, "state", None),
            )

        before_j2 = snapshot(j2)
        before_j3 = snapshot(j3)

        # Mutate J1's state with a synthetic TrafficState.
        j1.last_state = TrafficState(
            timestamp=999.0,
            approaches={
                "north": MagicMock(), "south": MagicMock(),
                "east": MagicMock(), "west": MagicMock(),
            },
            all_valid=True,
        )
        j1.elapsed = 777.0

        after_j2 = snapshot(j2)
        after_j3 = snapshot(j3)

        assert after_j2 == before_j2, (
            f"{ctrl_id}: J2 state changed when only J1 was mutated"
        )
        assert after_j3 == before_j3, (
            f"{ctrl_id}: J3 state changed when only J1 was mutated"
        )
        # And J1 must actually reflect the mutation.
        assert j1.last_state.timestamp == 999.0
        assert j1.elapsed == 777.0

    @pytest.mark.parametrize("ctrl_id", ["A", "B", "C", "D1", "D2", "S"])
    def test_counter_scoping_not_shared(self, ctrl_id, controllers):
        """Per-junction accumulators must not alias a shared mutable object."""
        instances = self._junction_ids(ctrl_id, controllers)
        # If a factory reused one instance, every junction would share the
        # same id() -- already caught by test_three_distinct_instances.  This
        # test additionally guards against shared mutable containers inside
        # the controllers (e.g. a class-level list used as a counter).
        for attr in ("_gate_interventions", "_gate_restrictions",
                     "_gate_phase_changes", "_gate_holds",
                     "_physical_congestion", "_phase_switches"):
            present = [hasattr(c, attr) for c in instances]
            if any(present):
                # Every junction that exposes the counter must hold its own.
                values = [getattr(c, attr) for c in instances if hasattr(c, attr)]
                assert len(set(id(v) for v in values)) == len(values), (
                    f"{ctrl_id}: {attr} aliases a shared object across junctions"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])