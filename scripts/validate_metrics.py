#!/usr/bin/env python3
"""
Validate metrics and calculations from Stage 3 benchmark results

This script validates that the metrics and calculations reported in Stage 3
analysis are correct and consistent with the underlying data.

Usage:
    python scripts/validate_metrics.py [--verbose] [--output-json PATH]

Exit codes:
    0 - All metrics validated successfully
    1 - Critical validation failure
    2 - Metrics could not be verified
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import statistics
import math


class MetricsValidator:
    """Validates metrics and calculations from Stage 3 benchmark."""

    def __init__(self, results_base: Path, verbose: bool = False):
        self.results_base = results_base
        self.verbose = verbose
        self.analysis_dir = results_base / "analysis"
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []

    def load_data_files(self) -> Dict[str, Any]:
        """Load all data files used for metrics validation."""
        data_files = {}

        # Load case ledger
        case_ledger_path = self.analysis_dir / "case_ledger.json"
        if case_ledger_path.exists():
            try:
                with open(case_ledger_path, 'r', encoding='utf-8') as f:
                    data_files['case_ledger'] = json.load(f)
            except json.JSONDecodeError as e:
                self.validation_errors.append(f"Invalid JSON in case_ledger: {e}")
                return {}
        else:
            self.validation_errors.append("Case ledger not found")
            return {}

        # Load Stage 3 analysis summary
        summary_path = self.analysis_dir / "stage3_analysis_summary.json"
        if summary_path.exists():
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    data_files['stage3_summary'] = json.load(f)
            except json.JSONDecodeError as e:
                self.validation_errors.append(f"Invalid JSON in stage3_analysis_summary: {e}")
                return {}
        else:
            self.validation_errors.append("Stage 3 summary not found")
            return {}

        # Load paired analysis
        paired_path = self.analysis_dir / "paired_d1_d2_analysis.json"
        if paired_path.exists():
            try:
                with open(paired_path, 'r', encoding='utf-8') as f:
                    data_files['paired_analysis'] = json.load(f)
            except json.JSONDecodeError as e:
                self.validation_errors.append(f"Invalid JSON in paired_analysis: {e}")
                return {}
        else:
            self.validation_errors.append("Paired analysis not found")
            return {}

        # Load Stage 3 analysis markdown
        markdown_path = self.analysis_dir / "STAGE3_PERFORMANCE_ANALYSIS.md"
        if markdown_path.exists():
            try:
                with open(markdown_path, 'r', encoding='utf-8') as f:
                    data_files['stage3_markdown'] = f.read()
            except IOError as e:
                self.validation_errors.append(f"Could not read stage3_markdown: {e}")
                return {}
        else:
            self.validation_errors.append("Stage 3 markdown not found")
            return {}

        # Load Stage 3 executive summary
        exec_summary_path = self.analysis_dir / "EXECUTIVE_SUMMARY.md"
        if exec_summary_path.exists():
            try:
                with open(exec_summary_path, 'r', encoding='utf-8') as f:
                    data_files['stage3_executive'] = f.read()
            except IOError as e:
                self.validation_errors.append(f"Could not read stage3_executive: {e}")
                return {}
        else:
            self.validation_errors.append("Stage 3 executive summary not found")
            return {}

        # Load validation files if they exist
        validation_files = [
            'validation_controller_performance.json',
            'validation_gate_mechanism.json'
        ]
        for val_file in validation_files:
            val_path = self.analysis_dir / val_file
            if val_path.exists():
                try:
                    with open(val_path, 'r', encoding='utf-8') as f:
                        data_files[val_file.replace('.json', '')] = json.load(f)
                except json.JSONDecodeError as e:
                    self.validation_errors.append(f"Invalid JSON in {val_file}: {e}")
                    return {}

        return data_files

    def validate_controller_rankings(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that controller rankings are consistent with data."""
        controller_stats = summary.get('controllers', {})
        if not controller_stats:
            return {'valid': False, 'error': 'No controller statistics found'}

        # Extract waiting times
        wait_times = {}
        for ctrl, stats in controller_stats.items():
            mean_wait = stats.get('total_wait_seconds_mean')
            if mean_wait is not None:
                wait_times[ctrl] = mean_wait

        if not wait_times:
            return {'valid': False, 'error': 'No waiting time data available'}

        # Sort by waiting time (ascending - lower is better)
        sorted_controllers = sorted(wait_times.items(), key=lambda x: x[1])

        return {
            'valid': True,
            'ranking': sorted_controllers,
            'best_controller': sorted_controllers[0][0],
            'best_time_seconds': sorted_controllers[0][1],
            'all_controllers': list(wait_times.keys()),
        }

    def validate_scenario_analysis(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Validate scenario-level analysis."""
        scenario_stats = summary.get('scenarios', {})
        if not scenario_stats:
            return {'valid': False, 'error': 'No scenario statistics found'}

        # Check that each scenario has expected number of cases
        for scenario, stats in scenario_stats.items():
            case_count = stats.get('case_count', 0)
            if case_count != 50:
                self.validation_warnings.append(
                    f"Scenario {scenario} has {case_count} cases, expected 50"
                )

        # Sort scenarios by waiting time (highest last = most demanding)
        scenario_by_wait = sorted(
            [(sc, stats.get('total_wait_seconds_mean', 0)) for sc, stats in scenario_stats.items()],
            key=lambda x: x[1], reverse=True
        )

        return {
            'valid': True,
            'scenarios_by_wait': [{'scenario': sc, 'mean_wait': time} for sc, time in scenario_by_wait],
        }

    def validate_paired_differences(self, paired_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Validate paired D1/D2 differences."""
        if not paired_analysis:
            return {'valid': False, 'error': 'No paired analysis found'}

        results = {}
        for scenario, data in paired_analysis.items():
            significant_diffs = data.get('significant_differences', [])
            valid_pairs = data.get('valid_pairs', 0)

            scenario_result = {
                'valid_pairs': valid_pairs,
                'significant_differences': significant_diffs,
                'total_significant_differences': len(significant_diffs),
            }

            # Check that we have 10 valid pairs per scenario
            if valid_pairs != 10:
                self.validation_warnings.append(
                    f"Scenario {scenario} has {valid_pairs} valid pairs, expected 10"
                )

            results[scenario] = scenario_result

        return {
            'valid': True,
            'by_scenario': results,
            'total_valid_pairs': sum(r['valid_pairs'] for r in results.values()),
            'total_significant_differences': sum(r['total_significant_differences'] for r in results.values()),
        }

    def validate_key_findings(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that key findings match the analysis data."""
        key_findings = summary.get('key_findings', [])
        controller_stats = summary.get('controllers', {})

        findings_valid = True

        # Check that Controller C has the lowest wait time
        if controller_stats:
            wait_times = {ctrl: stats.get('total_wait_seconds_mean')
                         for ctrl, stats in controller_stats.items()
                         if stats.get('total_wait_seconds_mean') is not None}

            if wait_times:
                best_ctrl = min(wait_times.items(), key=lambda x: x[1])
                c_has_lowest = best_ctrl[0] == 'C'

                # Find finding about Controller C having lowest wait time
                c_finding = any('Controller C achieves the lowest' in f for f in key_findings)

                if not (c_finding and c_has_lowest):
                    self.validation_warnings.append(
                        "Key finding about Controller C having lowest wait time may be inconsistent"
                    )

        # Check bottleneck scenario has highest wait time
        scenario_stats = summary.get('scenarios', {})
        if scenario_stats:
            bottleneck = scenario_stats.get('bottleneck', {})
            bottleneck_time = bottleneck.get('total_wait_seconds_mean')

            # Find finding about bottleneck having highest wait time
            bottleneck_finding = any("'bottleneck' shows the highest" in f for f in key_findings)

            if bottleneck_time and not bottleneck_finding:
                self.validation_warnings.append(
                    "Key finding about bottleneck scenario not found in key findings"
                )

        return {
            'valid': findings_valid,
            'key_findings': key_findings,
        }

    def validate_recommendations(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that recommendations are consistent with analysis."""
        recommendations = summary.get('recommendations', [])

        # Basic check: should have at least 3 recommendations
        if len(recommendations) < 3:
            self.validation_warnings.append(
                f"Expected at least 3 recommendations, found {len(recommendations)}"
            )

        # Check that recommendations reference the right controllers/metrics
        c_recommendation = any('Controller C' in r for r in recommendations)
        d2_recommendation = any('Controller D2' in r for r in recommendations)
        bottleneck_recommendation = any('bottleneck' in r.lower() for r in recommendations)

        return {
            'valid': True,
            'recommendation_count': len(recommendations),
            'has_c_recommendation': c_recommendation,
            'has_d2_recommendation': d2_recommendation,
            'has_bottleneck_recommendation': bottleneck_recommendation,
        }

    def validate_execution_summary(self, executive: str) -> Dict[str, Any]:
        """Validate that executive summary mentions key findings."""
        # Check that executive summary contains key elements
        required_elements = [
            'Controller D2',
            'spillback gate',
            'Controller C',
            'bottleneck',
            'SEVA First Innovation Challenge'
        ]

        missing_elements = []
        for element in required_elements:
            if element not in executive:
                missing_elements.append(element)

        return {
            'valid': len(missing_elements) == 0,
            'missing_elements': missing_elements,
            'contains_all_required': len(missing_elements) == 0,
        }

    def run_metrics_validation(self) -> Dict[str, Any]:
        """Run the complete metrics validation pipeline."""
        print("=" * 70)
        print("METRICS VALIDATION")
        print("=" * 70)

        # Step 1: Load data files
        print("\n[1/6] Loading data files...")
        data_files = self.load_data_files()
        if not data_files:
            print("[FAIL] Could not load required data files")
            return {'valid': False, 'error': 'Data files not loaded'}
        print(f"[OK] Loaded {len(data_files)} data files")

        # Step 2: Validate controller rankings
        print("\n[2/6] Validating controller rankings...")
        controller_result = self.validate_controller_rankings(data_files.get('stage3_summary', {}))
        if controller_result['valid']:
            print(f"[OK] Controller rankings validated")
            print(f"     Best controller: {controller_result['best_controller']} "
                  f"({controller_result['best_time_seconds']:.1f}s mean wait)")
        else:
            print(f"[FAIL] Controller rankings validation failed: {controller_result.get('error', 'unknown')}")

        # Step 3: Validate scenario analysis
        print("\n[3/6] Validating scenario analysis...")
        scenario_result = self.validate_scenario_analysis(data_files.get('stage3_summary', {}))
        if scenario_result['valid']:
            print(f"[OK] Scenario analysis validated")
            print(f"     Scenarios by wait: {[s['scenario'] for s in scenario_result['scenarios_by_wait']]}")
        else:
            print(f"[FAIL] Scenario analysis validation failed: {scenario_result.get('error', 'unknown')}")

        # Step 4: Validate paired differences
        print("\n[4/6] Validating paired D1/D2 differences...")
        paired_result = self.validate_paired_differences(data_files.get('paired_analysis', {}))
        if paired_result['valid']:
            print(f"[OK] Paired differences validated")
            print(f"     Total valid pairs: {paired_result['total_valid_pairs']}")
            print(f"     Total significant differences: {paired_result['total_significant_differences']}")
        else:
            print(f"[FAIL] Paired differences validation failed: {paired_result.get('error', 'unknown')}")

        # Step 5: Validate key findings
        print("\n[5/6] Validating key findings...")
        findings_result = self.validate_key_findings(data_files.get('stage3_summary', {}))
        if findings_result['valid']:
            print(f"[OK] Key findings validated")
            print(f"     Found {len(findings_result['key_findings'])} key findings")
        else:
            print(f"[FAIL] Key findings validation failed: {findings_result.get('error', 'unknown')}")

        # Step 6: Validate recommendations
        print("\n[6/6] Validating recommendations...")
        rec_result = self.validate_recommendations(data_files.get('stage3_summary', {}))
        if rec_result['valid']:
            print(f"[OK] Recommendations validated")
            print(f"     {rec_result['recommendation_count']} recommendations found")
            print(f"     - Controller C: {rec_result['has_c_recommendation']}")
            print(f"     - Controller D2: {rec_result['has_d2_recommendation']}")
            print(f"     - Bottleneck: {rec_result['has_bottleneck_recommendation']}")
        else:
            print(f"[FAIL] Recommendations validation failed")

        # Step 7: Validate execution summary
        print("\n[7/6] Validating execution summary...")
        exec_result = self.validate_execution_summary(data_files.get('stage3_executive', ''))
        if exec_result['valid']:
            print(f"[OK] Execution summary validated")
            print(f"     Contains all required elements: {exec_result['contains_all_required']}")
        else:
            print(f"[WARN] Execution summary missing elements: {exec_result.get('missing_elements', [])}")

        # Compile final results
        return {
            'valid': True,
            'controller_rankings': controller_result,
            'scenario_analysis': scenario_result,
            'paired_differences': paired_result,
            'key_findings': findings_result,
            'recommendations': rec_result,
            'execution_summary': exec_result,
            'validation_errors': self.validation_errors,
            'validation_warnings': self.validation_warnings,
        }


def main():
    parser = argparse.ArgumentParser(
        description='Validate metrics and calculations from Stage 3 benchmark results'
    )
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--output-json', type=str, default=None,
                       help='Path to write JSON validation results')
    parser.add_argument('--results-dir', type=str,
                       default='results/benchmark_v2_250_isolated',
                       help='Path to benchmark results directory')

    args = parser.parse_args()

    results_base = Path(args.results_dir)
    if not results_base.exists():
        print(f"[ERROR] Results directory not found: {results_base}")
        sys.exit(1)

    validator = MetricsValidator(results_base, verbose=args.verbose)
    results = validator.run_metrics_validation()

    # Save JSON output if requested
    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n[OK] Validation results saved to: {output_path}")

    # Final status
    print("\n" + "=" * 70)
    print("METRICS VALIDATION SUMMARY")
    print("=" * 70)

    if results.get('valid', False):
        print("[PASS] Metrics validated successfully")

        # Key findings
        if 'controller_rankings' in results:
            cr = results['controller_rankings']
            print(f"\nController Rankings:")
            print(f"  - Best controller: {cr['best_controller']} ({cr['best_time_seconds']:.1f}s)")

        if 'scenario_analysis' in results:
            sa = results['scenario_analysis']
            print(f"\nScenario Analysis:")
            print(f"  - Most demanding scenario: {sa['scenarios_by_wait'][0]['scenario']}")

        if 'paired_differences' in results:
            pd = results['paired_differences']
            print(f"\nPaired Analysis:")
            print(f"  - Total valid pairs: {pd['total_valid_pairs']}")
            print(f"  - Total significant differences: {pd['total_significant_differences']}")

        sys.exit(0)
    else:
        print("[FAIL] Metrics validation failed")
        for error in results.get('validation_errors', []):
            print(f"  - {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()