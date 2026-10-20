#!/usr/bin/env python3
"""
Test the Context-Aware Controller Selector

This script tests the selector's behavior across representative traffic states
without rerunning the full 250-case benchmark.

Usage:
    python scripts/test_selector.py [--verbose]

Exit codes:
    0 - All tests passed
    1 - Test failure
"""

import sys
import argparse
from typing import Dict, List, Any
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.selector import ContextAwareSelector, ControllerType


def create_test_state(
    blocked_approaches: List[str] = None,
    high_queues: List[str] = None,
) -> TrafficState:
    """
    Create a test TrafficState with specified conditions.

    Args:
        blocked_approaches: List of approach names with downstream_available=False
        high_queues: List of approach names with high queue counts

    Returns:
        TrafficState for testing
    """
    if blocked_approaches is None:
        blocked_approaches = []
    if high_queues is None:
        high_queues = []

    approaches = {}
    for name in ["north", "south", "east", "west"]:
        queue_count = 15.0 if name in high_queues else 5.0
        mean_wait = 30.0 if name in high_queues else 10.0
        downstream_available = name not in blocked_approaches

        approaches[name] = ApproachState(
            queue_count=queue_count,
            mean_wait_seconds=mean_wait,
            arrival_rate=20.0,
            downstream_available=downstream_available,
            measurement_valid=True,
        )

    return TrafficState(
        timestamp=0.0,
        approaches=approaches,
        all_valid=True,
    )


class SelectorTester:
    """Test suite for ContextAwareSelector."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results: List[Dict[str, Any]] = []

    def record_result(self, test_name: str, passed: bool, reason: str = ""):
        """Record a test result."""
        self.test_results.append({
            "test_name": test_name,
            "passed": passed,
            "reason": reason,
        })
        if passed:
            self.tests_passed += 1
            print(f"  [PASS] {test_name}")
        else:
            self.tests_failed += 1
            print(f"  [FAIL] {test_name}: {reason}")

    def test_selector_initialization(self):
        """Test that selector initializes correctly."""
        test_name = "test_selector_initialization"
        try:
            selector = ContextAwareSelector(
                spillback_threshold=0.25,
                alpha=0.5,
                beta=0.3,
                gamma=0.2,
            )

            # Check that both controllers are initialized
            assert selector.controller_c is not None
            assert selector.controller_d2 is not None
            assert selector._active_controller == ControllerType.C  # Default

            self.record_result(test_name, True)
        except Exception as e:
            self.record_result(test_name, False, str(e))

    def test_selector_chooses_c_when_clear(self):
        """Test that selector chooses C when downstream is clear."""
        test_name = "test_selector_chooses_c_when_clear"
        try:
            selector = ContextAwareSelector()
            state = create_test_state(blocked_approaches=[])

            selected = selector.select_controller(state)

            if selected == ControllerType.C:
                self.record_result(test_name, True)
            else:
                self.record_result(
                    test_name, False,
                    f"Expected C when downstream clear, got {selected.name}"
                )
        except Exception as e:
            self.record_result(test_name, False, str(e))

    def test_selector_chooses_d2_when_blocked(self):
        """Test that selector chooses D2 when downstream is blocked."""
        test_name = "test_selector_chooses_d2_when_blocked"
        try:
            selector = ContextAwareSelector()
            # Block one approach - should trigger D2
            state = create_test_state(blocked_approaches=["north"])

            selected = selector.select_controller(state)

            if selected == ControllerType.D2:
                self.record_result(test_name, True)
            else:
                self.record_result(
                    test_name, False,
                    f"Expected D2 when downstream blocked, got {selected.name}"
                )
        except Exception as e:
            self.record_result(test_name, False, str(e))

    def test_selector_chooses_d2_when_multiple_blocked(self):
        """Test that selector chooses D2 when multiple approaches blocked."""
        test_name = "test_selector_chooses_d2_when_multiple_blocked"
        try:
            selector = ContextAwareSelector()
            # Block multiple approaches - should definitely trigger D2
            state = create_test_state(blocked_approaches=["north", "east"])

            selected = selector.select_controller(state)

            if selected == ControllerType.D2:
                self.record_result(test_name, True)
            else:
                self.record_result(
                    test_name, False,
                    f"Expected D2 when multiple blocked, got {selected.name}"
                )
        except Exception as e:
            self.record_result(test_name, False, str(e))

    def test_selector_switches_from_c_to_d2(self):
        """Test that selector can switch from C to D2 when conditions change."""
        test_name = "test_selector_switches_from_c_to_d2"
        try:
            selector = ContextAwareSelector()

            # Start with clear conditions
            state_clear = create_test_state(blocked_approaches=[])
            selected_clear = selector.select_controller(state_clear)

            # Then introduce blockage
            state_blocked = create_test_state(blocked_approaches=["south"])
            selected_blocked = selector.select_controller(state_blocked)

            if selected_clear == ControllerType.C and selected_blocked == ControllerType.D2:
                self.record_result(test_name, True)
            else:
                self.record_result(
                    test_name, False,
                    f"Expected C->D2 switch, got {selected_clear.name}->{selected_blocked.name}"
                )
        except Exception as e:
            self.record_result(test_name, False, str(e))

    def test_selector_step_integration(self):
        """Test that selector.step() works end-to-end."""
        test_name = "test_selector_step_integration"
        try:
            selector = ContextAwareSelector()
            state = create_test_state(blocked_approaches=["west"])

            action = selector.step(state, step_length=1.0)

            # Check action has expected keys
            assert "phase" in action
            assert "duration" in action
            assert "reason" in action
            assert "selector_controller" in action
            assert "selector_reason" in action

            # Should have selected D2 due to blockage
            if action["selector_controller"] == "D2":
                self.record_result(test_name, True)
            else:
                self.record_result(
                    test_name, False,
                    f"Expected D2 controller in action, got {action['selector_controller']}"
                )
        except Exception as e:
            self.record_result(test_name, False, str(e))

    def test_selector_statistics(self):
        """Test that selector provides statistics."""
        test_name = "test_selector_statistics"
        try:
            selector = ContextAwareSelector()
            stats = selector.get_statistics()

            assert "active_controller" in stats
            assert "last_selection_reason" in stats
            assert "spillback_threshold" in stats

            self.record_result(test_name, True)
        except Exception as e:
            self.record_result(test_name, False, str(e))

    def run_all_tests(self):
        """Run all tests."""
        print("=" * 70)
        print("CONTEXT-AWARE CONTROLLER SELECTOR: TEST SUITE")
        print("=" * 70)

        print("\nRunning tests...\n")

        self.test_selector_initialization()
        self.test_selector_chooses_c_when_clear()
        self.test_selector_chooses_d2_when_blocked()
        self.test_selector_chooses_d2_when_multiple_blocked()
        self.test_selector_switches_from_c_to_d2()
        self.test_selector_step_integration()
        self.test_selector_statistics()

        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"  Passed: {self.tests_passed}")
        print(f"  Failed: {self.tests_failed}")
        print(f"  Total:  {self.tests_passed + self.tests_failed}")

        if self.tests_failed == 0:
            print("\n[PASS] All tests passed!")
            return True
        else:
            print(f"\n[FAIL] {self.tests_failed} test(s) failed")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Test the Context-Aware Controller Selector"
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose output")
    args = parser.parse_args()

    tester = SelectorTester(verbose=args.verbose)
    success = tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()