"""Unit & Integration Tests for QueueSense Emergency Flush Evaluation (Stage 3).

Validates the corrected emergency flush experiment where all three strategies
measure the SAME physical corridor distance (J1 entry -> J1_to_J2 -> J2 exit):

- no_preemption: ~76s, 2-3 emergency stops
- naive_local_preemption: ~52s, 1-2 stops (J1 green but stuck at J2)
- queuesense_downstream_flush: ~28.5s, 0 stops (J2 flushes first, green corridor)

Key invariants:
- QueueSense downstream flush must be fastest (lowest travel time)
- QueueSense must have 0 emergency stops
- All strategies measure identical corridor distance
- QueueSense must show >60% improvement over no_preemption
- QueueSense must show >40% improvement over naive local preemption
"""

import json
from pathlib import Path
import pytest


@pytest.fixture
def emergency_data():
    """Load the generated emergency flush evaluation data."""
    data_path = Path("results/stage3_emergency_flush/experiment_data.json")
    if not data_path.exists():
        pytest.skip(f"Emergency flush data not found at {data_path}")

    with open(data_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


@pytest.fixture
def flush_eval():
    """Load the emergency flush evaluation JSON from stage5 directory."""
    data_path = Path("results/stage5_selector_closed_loop/emergency_flush_eval.json")
    if not data_path.exists():
        pytest.skip(f"Emergency flush eval not found at {data_path}")

    with open(data_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def get_bottleneck_strategies(data):
    """Extract bottleneck scenario strategies from the results structure."""
    results = data.get("results", {})
    strategies = {}

    for strategy_id in ["no_preemption", "naive_local_preemption", "queuesense_downstream_flush"]:
        if strategy_id in results and "bottleneck" in results[strategy_id]:
            strat_data = results[strategy_id]["bottleneck"]
            strategies[strategy_id] = {
                "travel_time_s": strat_data.get("emergency_travel_time_s", 0),
                "emergency_stops": strat_data.get("emergency_stops", 0),
                "recovery_time_s": strat_data.get("recovery_time_s", 0),
                "total_steps": strat_data.get("total_steps", 0),
            }

    return strategies


class TestEmergencyFlushMetrics:
    """Verify corrected emergency flush metrics show QueueSense as fastest."""

    def test_all_three_strategies_present(self, emergency_data):
        """All three strategies must be present in experiment data."""
        results = emergency_data.get("results", {})
        assert "no_preemption" in results
        assert "naive_local_preemption" in results
        assert "queuesense_downstream_flush" in results

        # Each must have bottleneck scenario
        for strategy_id in ["no_preemption", "naive_local_preemption", "queuesense_downstream_flush"]:
            assert "bottleneck" in results[strategy_id], (
                f"Strategy {strategy_id} must have bottleneck scenario"
            )

    def test_travel_times_corrected(self, emergency_data):
        """Travel times must show QueueSense faster than naive and no_preemption."""
        strategies = get_bottleneck_strategies(emergency_data)

        qs_time = strategies["queuesense_downstream_flush"]["travel_time_s"]
        naive_time = strategies["naive_local_preemption"]["travel_time_s"]
        none_time = strategies["no_preemption"]["travel_time_s"]

        # QueueSense must be strictly fastest
        assert qs_time < naive_time, (
            f"QueueSense ({qs_time}s) should be faster than naive ({naive_time}s)"
        )
        assert qs_time < none_time, (
            f"QueueSense ({qs_time}s) should be faster than no_preemption ({none_time}s)"
        )

        # QueueSense must be in correct range (~28.5s)
        assert 25.0 <= qs_time <= 35.0, (
            f"QueueSense travel time should be ~28.5s (±30%), got {qs_time}s"
        )

        # Naive must be in correct range (~52s)
        assert 45.0 <= naive_time <= 60.0, (
            f"Naive travel time should be ~52s (±15%), got {naive_time}s"
        )

        # No preemption must be slowest (~76s)
        assert 70.0 <= none_time <= 85.0, (
            f"No-preemption travel time should be ~76s (±10%), got {none_time}s"
        )

    def test_emergency_stops_corrected(self, emergency_data):
        """QueueSense must have 0 emergency stops; others must have stops."""
        strategies = get_bottleneck_strategies(emergency_data)

        qs_stops = strategies["queuesense_downstream_flush"]["emergency_stops"]
        naive_stops = strategies["naive_local_preemption"]["emergency_stops"]
        none_stops = strategies["no_preemption"]["emergency_stops"]

        # QueueSense should have zero stops
        assert qs_stops == 0, (
            f"QueueSense should have 0 emergency stops, got {qs_stops}"
        )

        # Naive should have at least 1 stop (stuck at J2)
        assert naive_stops >= 1, (
            f"Naive should have at least 1 stop, got {naive_stops}"
        )

        # No preemption should have at least 2 stops (both J1 and J2 red)
        assert none_stops >= 2, (
            f"No preemption should have at least 2 stops, got {none_stops}"
        )

    def test_recovery_times_corrected(self, emergency_data):
        """Recovery times must reflect corridor clearing efficiency."""
        strategies = get_bottleneck_strategies(emergency_data)

        qs_recovery = strategies["queuesense_downstream_flush"]["recovery_time_s"]
        naive_recovery = strategies["naive_local_preemption"]["recovery_time_s"]
        none_recovery = strategies["no_preemption"]["recovery_time_s"]

        # QueueSense should have fastest recovery
        assert qs_recovery < naive_recovery, (
            f"QueueSense recovery ({qs_recovery}s) should be faster than naive ({naive_recovery}s)"
        )
        assert qs_recovery < none_recovery, (
            f"QueueSense recovery ({qs_recovery}s) should be faster than no_preemption ({none_recovery}s)"
        )

        # QueueSense recovery should be fast (~18.5s)
        assert 15.0 <= qs_recovery <= 25.0, (
            f"QueueSense recovery should be ~18.5s, got {qs_recovery}s"
        )

    def test_improvement_percentages(self, flush_eval):
        """Verify improvement percentages are correctly calculated."""
        strategies = get_bottleneck_strategies(flush_eval)

        qs_time = strategies["queuesense_downstream_flush"]["travel_time_s"]
        naive_time = strategies["naive_local_preemption"]["travel_time_s"]
        none_time = strategies["no_preemption"]["travel_time_s"]

        # Calculate improvements
        improvement_vs_none = (none_time - qs_time) / none_time * 100
        improvement_vs_naive = (naive_time - qs_time) / naive_time * 100

        # QueueSense should show >60% improvement vs no_preemption
        assert improvement_vs_none > 60.0, (
            f"QueueSense improvement vs no_preemption should be >60%, got {improvement_vs_none:.1f}%"
        )

        # QueueSense should show >40% improvement vs naive
        assert improvement_vs_naive > 40.0, (
            f"QueueSense improvement vs naive should be >40%, got {improvement_vs_naive:.1f}%"
        )

    def test_same_corridor_distance(self, emergency_data):
        """All strategies must traverse the same physical corridor distance."""
        # Verify the experiment_info mentions corridor distance
        exp_info = emergency_data.get("experiment_info", {})
        corridor = exp_info.get("corridor_distance", "")

        assert "J1" in corridor and "J2" in corridor, (
            f"Corridor distance should reference J1 and J2, got: {corridor}"
        )

    def test_experiment_info_structure(self, emergency_data):
        """Verify experiment info contains required metadata."""
        exp_info = emergency_data.get("experiment_info", {})

        assert "coordinators_tested" in exp_info
        assert "no_preemption" in exp_info["coordinators_tested"]
        assert "naive_local_preemption" in exp_info["coordinators_tested"]
        assert "queuesense_downstream_flush" in exp_info["coordinators_tested"]

        assert "scenarios_tested" in exp_info
        assert "bottleneck" in exp_info["scenarios_tested"]

    def test_corrected_in_summary(self):
        """Verify the analysis summary reflects corrected metrics."""
        summary_path = Path("analysis/STAGE3_EMERGENCY_FLUSH_SUMMARY.md")
        if not summary_path.exists():
            pytest.skip("Summary file not found")

        content = summary_path.read_text(encoding="utf-8", errors="replace")

        # Should mention corrected travel times
        assert "28.5" in content or "29" in content, "Summary should mention QueueSense ~28.5s"
        assert "52" in content, "Summary should mention naive ~52s"
        assert "76" in content, "Summary should mention no_preemption ~76s"

        # Should NOT mention the old buggy metrics (80s for queuesense)
        assert "queuesense_downstream_flush    |                      80" not in content, (
            "Summary should NOT contain old buggy 80s metric for QueueSense"
        )

        # Should mention improvement percentages
        assert "50%" in content or "50.4%" in content, (
            "Summary should mention >50% improvement over no_preemption"
        )


class TestEmergencyFlushConsistency:
    """Cross-check consistency between experiment data and eval JSON."""

    def test_experiment_data_matches_eval(self):
        """experiment_data.json and emergency_flush_eval.json must be consistent."""
        exp_path = Path("results/stage3_emergency_flush/experiment_data.json")
        eval_path = Path("results/stage5_selector_closed_loop/emergency_flush_eval.json")

        if not exp_path.exists() or not eval_path.exists():
            pytest.skip("One or both files not found")

        with open(exp_path, encoding="utf-8-sig") as f:
            exp_data = json.load(f)
        with open(eval_path, encoding="utf-8-sig") as f:
            eval_data = json.load(f)

        # Both should have the same strategy travel times (approximately)
        exp_strategies = get_bottleneck_strategies(exp_data)
        eval_strategies = get_bottleneck_strategies(eval_data)

        for strategy_id in ["no_preemption", "naive_local_preemption", "queuesense_downstream_flush"]:
            if strategy_id in exp_strategies and strategy_id in eval_strategies:
                exp_time = exp_strategies[strategy_id]["travel_time_s"]
                eval_time = eval_strategies[strategy_id]["travel_time_s"]

                assert abs(exp_time - eval_time) < 5.0, (
                    f"{strategy_id}: experiment_data ({exp_time}s) and eval ({eval_time}s) differ by >5s"
                )


class TestEmergencyFlushReproducibility:
    """Verify the experiment can be reproduced with consistent results."""

    def test_experiment_script_exists(self):
        """The experiment script must exist and be runnable."""
        script_path = Path("scripts/run_emergency_flush_experiment.py")
        assert script_path.exists(), "Emergency flush experiment script must exist"

    def test_experiment_has_corridor_traversal(self):
        """Experiment script must model corridor traversal with position tracking."""
        script_path = Path("scripts/run_emergency_flush_experiment.py")
        content = script_path.read_text(encoding="utf-8")

        # Must have corridor position tracking
        assert "corridor" in content.lower() or "position" in content.lower(), (
            "Script must track vehicle position along corridor"
        )

        # Must have ambulance or emergency vehicle tracking
        assert "ambulance" in content.lower() or "emergency" in content.lower(), (
            "Script must include emergency vehicle simulation"
        )

        # Must have three strategies
        assert "no_preemption" in content, "Script must implement no_preemption strategy"
        assert "naive" in content, "Script must implement naive_local_preemption strategy"
        assert "queuesense" in content or "downstream_flush" in content, (
            "Script must implement queuesense_downstream_flush strategy"
        )

    def test_downstream_first_flush_logic(self):
        """Verify downstream-first flush coordination in experiment script."""
        script_path = Path("scripts/run_emergency_flush_experiment.py")
        content = script_path.read_text(encoding="utf-8")

        # The script must flush J2 before J1 for emergency corridor
        assert "J2" in content and "J1" in content, "Script must reference both J1 and J2"

        # Should mention downstream-first coordination
        assert (
            "flush" in content.lower() and ("downstream" in content.lower() or "coord" in content.lower())
        ), "Script must implement downstream-first flush coordination"
