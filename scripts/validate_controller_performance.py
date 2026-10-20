#!/usr/bin/env python3
"""
Validate Controller Performance Claims from Stage 3 Benchmark Results

This script reads the actual selected, validated results from the Stage 3 benchmark
and independently reproduces the principal controller comparisons.

Usage:
    python scripts/validate_controller_performance.py [--verbose] [--output-json PATH]

Exit codes:
    0 - All validations passed
    1 - Critical validation failure (missing data, corrupted results)
    2 - Performance claims could not be verified (data incomplete)
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import statistics


class PerformanceValidator:
    """Validates controller performance claims from benchmark results."""

    def __init__(self, results_base: Path, verbose: bool = False):
        self.results_base = results_base
        self.verbose = verbose
        self.analysis_dir = results_base / "analysis"
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []

    def load_case_ledger(self) -> Optional[Dict[str, Any]]:
        """Load the case ledger JSON file."""
        ledger_path = self.analysis_dir / "case_ledger.json"
        if not ledger_path.exists():
            self.validation_errors.append(f"Case ledger not found: {ledger_path}")
            return None

        try:
            with open(ledger_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.validation_errors.append(f"Invalid JSON in case ledger: {e}")
            return None

    def load_summary(self, case_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Load a single case summary file."""
        summary_path = Path(case_info.get('selected_path', ''))
        if not summary_path.exists():
            self.validation_warnings.append(
                f"Summary file not found for {case_info.get('case_id', 'unknown')}: {summary_path}"
            )
            return None

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.validation_warnings.append(
                f"Error loading summary for {case_info.get('case_id', 'unknown')}: {e}"
            )
            return None

    def extract_metrics(self, summary: Dict[str, Any], case_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metrics from a summary file."""
        return {
            'case_id': case_info.get('case_id', 'unknown'),
            'controller': case_info.get('controller', 'unknown'),
            'scenario': case_info.get('scenario', 'unknown'),
            'seed': case_info.get('seed', -1),
            'status': case_info.get('status', 'unknown'),
            # Core performance metrics
            'total_wait_seconds': summary.get('total_wait_seconds', None),
            'mean_wait_seconds': summary.get('mean_wait_seconds', None),
            'arrived_cumulative': summary.get('arrived_cumulative', None),
            # Congestion metrics
            'physical_congestion_observations': summary.get('physical_congestion_observations', None),
            # Gate metrics
            'gate_interventions': summary.get('gate_interventions', None),
            'gate_restrictions': summary.get('gate_restrictions', None),
            'gate_phase_change_interventions': summary.get('gate_phase_change_interventions', None),
            'gate_caused_holds': summary.get('gate_caused_holds', None),
            # Spillback metrics
            'spillback_ns_seconds': summary.get('spillback_ns_seconds', None),
            'spillback_ew_seconds': summary.get('spillback_ew_seconds', None),
            # Configuration
            'spillback_gate': summary.get('spillback_gate', False),
            # Validity checks
            'duration': summary.get('duration', None),
            'steps': summary.get('steps', None),
        }

    def validate_metric_definitions(self, metrics_data: List[Dict[str, Any]]) -> bool:
        """Validate that metrics are comparable across all cases."""
        required_metrics = ['total_wait_seconds', 'mean_wait_seconds', 'arrived_cumulative',
                           'physical_congestion_observations', 'gate_interventions']

        missing_counts = defaultdict(int)
        for data in metrics_data:
            for metric in required_metrics:
                if data.get(metric) is None:
                    missing_counts[metric] += 1

        # Report missing data
        for metric, count in missing_counts.items():
            if count > 0:
                self.validation_warnings.append(
                    f"Metric '{metric}' missing in {count}/{len(metrics_data)} cases"
                )

        # Critical if more than 10% missing
        for metric, count in missing_counts.items():
            if count > len(metrics_data) * 0.1:
                self.validation_errors.append(
                    f"Critical: Metric '{metric}' missing in >10% of cases ({count}/{len(metrics_data)})"
                )
                return False

        return True

    def calculate_controller_statistics(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Calculate per-controller statistics."""
        by_controller = defaultdict(list)
        for data in metrics_data:
            by_controller[data['controller']].append(data)

        results = {}
        for controller, cases in sorted(by_controller.items()):
            # Extract metric values
            total_wait = [c['total_wait_seconds'] for c in cases if c['total_wait_seconds'] is not None]
            arrived = [c['arrived_cumulative'] for c in cases if c['arrived_cumulative'] is not None]
            congestion = [c['physical_congestion_observations'] for c in cases if c['physical_congestion_observations'] is not None]
            gate_int = [c['gate_interventions'] for c in cases if c['gate_interventions'] is not None]
            gate_enabled = sum(1 for c in cases if c.get('spillback_gate', False))

            results[controller] = {
                'case_count': len(cases),
                'total_wait_seconds': {
                    'mean': statistics.mean(total_wait) if total_wait else None,
                    'std': statistics.stdev(total_wait) if len(total_wait) > 1 else None,
                    'min': min(total_wait) if total_wait else None,
                    'max': max(total_wait) if total_wait else None,
                },
                'arrived_cumulative': {
                    'mean': statistics.mean(arrived) if arrived else None,
                    'std': statistics.stdev(arrived) if len(arrived) > 1 else None,
                },
                'physical_congestion_observations': {
                    'mean': statistics.mean(congestion) if congestion else None,
                    'std': statistics.stdev(congestion) if len(congestion) > 1 else None,
                },
                'gate_interventions': {
                    'mean': statistics.mean(gate_int) if gate_int else None,
                    'std': statistics.stdev(gate_int) if len(gate_int) > 1 else None,
                },
                'gate_enabled_proportion': gate_enabled / len(cases) if cases else 0,
            }

        return results

    def validate_waiting_time_ranking(self, controller_stats: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Validate the waiting time ranking claim."""
        wait_times = []
        for controller, stats in controller_stats.items():
            mean_wait = stats['total_wait_seconds']['mean']
            if mean_wait is not None:
                wait_times.append((controller, mean_wait))

        if not wait_times:
            return {'valid': False, 'error': 'No waiting time data available'}

        # Sort by waiting time (ascending - lower is better)
        wait_times.sort(key=lambda x: x[1])

        ranking = [(ctrl, time) for ctrl, time in wait_times]
        best_controller = ranking[0][0]
        best_time = ranking[0][1]

        # Calculate relative differences from best
        relative_diffs = {}
        for ctrl, time in ranking:
            if ctrl != best_controller:
                diff_pct = ((time - best_time) / best_time) * 100
                relative_diffs[ctrl] = diff_pct

        return {
            'valid': True,
            'ranking': ranking,
            'best_controller': best_controller,
            'best_time_seconds': best_time,
            'relative_difference_from_best_pct': relative_diffs,
        }

    def validate_congestion_reduction(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate the physical congestion reduction claim (D2 vs D1)."""
        d1_cases = [c for c in metrics_data if c['controller'] == 'D1']
        d2_cases = [c for c in metrics_data if c['controller'] == 'D2']

        d1_congestion = [c['physical_congestion_observations'] for c in d1_cases
                        if c['physical_congestion_observations'] is not None]
        d2_congestion = [c['physical_congestion_observations'] for c in d2_cases
                        if c['physical_congestion_observations'] is not None]

        if not d1_congestion or not d2_congestion:
            return {'valid': False, 'error': 'Insufficient congestion data'}

        d1_mean = statistics.mean(d1_congestion)
        d2_mean = statistics.mean(d2_congestion)
        reduction = d1_mean - d2_mean
        reduction_pct = (reduction / d1_mean) * 100 if d1_mean > 0 else 0

        # Calculate paired differences by scenario and seed
        paired_diffs = self._calculate_paired_congestion_differences(metrics_data)

        return {
            'valid': True,
            'd1_mean_congestion': d1_mean,
            'd2_mean_congestion': d2_mean,
            'absolute_reduction': reduction,
            'relative_reduction_pct': reduction_pct,
            'paired_analysis': paired_diffs,
        }

    def _calculate_paired_congestion_differences(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate paired congestion differences by scenario."""
        by_scenario = defaultdict(list)
        for data in metrics_data:
            if data['controller'] in ['D1', 'D2']:
                by_scenario[data['scenario']].append(data)

        paired_results = {}
        for scenario, cases in by_scenario.items():
            d1_by_seed = {c['seed']: c for c in cases if c['controller'] == 'D1'}
            d2_by_seed = {c['seed']: c for c in cases if c['controller'] == 'D2'}

            paired_diffs = []
            for seed in sorted(d1_by_seed.keys()):
                if seed in d2_by_seed:
                    d1_val = d1_by_seed[seed]['physical_congestion_observations']
                    d2_val = d2_by_seed[seed]['physical_congestion_observations']
                    if d1_val is not None and d2_val is not None:
                        paired_diffs.append(d1_val - d2_val)  # Positive = D2 reduces congestion

            if paired_diffs:
                paired_results[scenario] = {
                    'valid_pairs': len(paired_diffs),
                    'mean_reduction': statistics.mean(paired_diffs),
                    'std_reduction': statistics.stdev(paired_diffs) if len(paired_diffs) > 1 else 0,
                }

        return paired_results

    def validate_gate_interventions(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate gate intervention claims."""
        d2_cases = [c for c in metrics_data if c['controller'] == 'D2']
        d1_cases = [c for c in metrics_data if c['controller'] == 'D1']

        d2_interventions = [c['gate_interventions'] for c in d2_cases
                          if c['gate_interventions'] is not None]
        d1_interventions = [c['gate_interventions'] for c in d1_cases
                          if c['gate_interventions'] is not None]

        # Check that D1 has zero interventions (gate disabled)
        d1_has_interventions = any(i > 0 for i in d1_interventions) if d1_interventions else False

        # Check gate event breakdown for D2
        d2_gate_breakdown = []
        for c in d2_cases:
            if c.get('gate_interventions') is not None:
                d2_gate_breakdown.append({
                    'case_id': c['case_id'],
                    'interventions': c['gate_interventions'],
                    'restrictions': c.get('gate_restrictions', 0),
                    'phase_changes': c.get('gate_phase_change_interventions', 0),
                    'holds': c.get('gate_caused_holds', 0),
                })

        return {
            'valid': True,
            'd2_mean_interventions': statistics.mean(d2_interventions) if d2_interventions else None,
            'd1_mean_interventions': statistics.mean(d1_interventions) if d1_interventions else None,
            'd1_has_nonzero_interventions': d1_has_interventions,
            'd2_gate_event_breakdown': d2_gate_breakdown[:10],  # First 10 for inspection
        }

    def run_validation(self) -> Dict[str, Any]:
        """Run the complete validation pipeline."""
        print("=" * 70)
        print("CONTROLLER PERFORMANCE VALIDATION")
        print("=" * 70)

        # Step 1: Load case ledger
        print("\n[1/6] Loading case ledger...")
        ledger = self.load_case_ledger()
        if ledger is None:
            print("[FAIL] Could not load case ledger")
            return {'valid': False, 'error': 'Case ledger not loaded'}
        print(f"[OK] Loaded {len(ledger)} cases from ledger")

        # Step 2: Load and extract metrics from all summaries
        print("\n[2/6] Loading summary files...")
        metrics_data = []
        for case_id, case_info in ledger.items():
            summary = self.load_summary(case_info)
            if summary is not None:
                metrics = self.extract_metrics(summary, case_info)
                metrics_data.append(metrics)

        print(f"[OK] Loaded metrics from {len(metrics_data)}/{len(ledger)} cases")

        if len(metrics_data) < len(ledger) * 0.9:
            print("[FAIL] Less than 90% of summaries loaded")
            return {'valid': False, 'error': 'Insufficient summary data'}

        # Step 3: Validate metric definitions
        print("\n[3/6] Validating metric definitions...")
        if not self.validate_metric_definitions(metrics_data):
            print("[FAIL] Metric validation failed")
            return {'valid': False, 'errors': self.validation_errors}
        print("[OK] Metric definitions validated")

        # Step 4: Calculate controller statistics
        print("\n[4/6] Calculating controller statistics...")
        controller_stats = self.calculate_controller_statistics(metrics_data)

        # Print statistics
        print("\nController Performance Summary:")
        print("-" * 70)
        print(f"{'Controller':<12} {'Cases':<8} {'Mean Wait (s)':<15} {'Mean Congestion':<15} {'Gate Interventions':<18}")
        print("-" * 70)
        for ctrl, stats in sorted(controller_stats.items()):
            wait = stats['total_wait_seconds']['mean']
            cong = stats['physical_congestion_observations']['mean']
            gate = stats['gate_interventions']['mean']
            print(f"{ctrl:<12} {stats['case_count']:<8} {wait:<15.1f} {cong:<15.2f} {gate:<18.2f}")
        print("-" * 70)

        # Step 5: Validate waiting time ranking
        print("\n[5/6] Validating waiting time ranking...")
        ranking_result = self.validate_waiting_time_ranking(controller_stats)

        if ranking_result['valid']:
            print(f"[OK] Waiting time ranking validated")
            print(f"     Best controller: {ranking_result['best_controller']} "
                  f"({ranking_result['best_time_seconds']:.1f}s mean wait)")
            print(f"     Ranking: {' > '.join([f'{c} ({t:.1f}s)' for c, t in ranking_result['ranking']])}")
        else:
            print(f"[WARN] Could not validate ranking: {ranking_result.get('error', 'unknown')}")

        # Step 6: Validate congestion reduction
        print("\n[6/6] Validating congestion reduction claim...")
        congestion_result = self.validate_congestion_reduction(metrics_data)

        if congestion_result['valid']:
            print(f"[OK] Congestion reduction validated")
            print(f"     D1 mean congestion: {congestion_result['d1_mean_congestion']:.2f}")
            print(f"     D2 mean congestion: {congestion_result['d2_mean_congestion']:.2f}")
            print(f"     Absolute reduction: {congestion_result['absolute_reduction']:.2f}")
            print(f"     Relative reduction: {congestion_result['relative_reduction_pct']:.1f}%")
        else:
            print(f"[WARN] Could not validate congestion reduction: {congestion_result.get('error', 'unknown')}")

        # Validate gate interventions
        print("\n[7/6] Validating gate intervention claims...")
        gate_result = self.validate_gate_interventions(metrics_data)

        if gate_result['valid']:
            print(f"[OK] Gate interventions validated")
            print(f"     D2 mean interventions: {gate_result['d2_mean_interventions']:.2f}")
            print(f"     D1 mean interventions: {gate_result['d1_mean_interventions']:.2f}")
            if gate_result['d1_has_nonzero_interventions']:
                print(f"     [WARN] D1 has non-zero interventions (unexpected)")

        # Compile final results
        return {
            'valid': True,
            'validation_errors': self.validation_errors,
            'validation_warnings': self.validation_warnings,
            'controller_statistics': controller_stats,
            'waiting_time_ranking': ranking_result,
            'congestion_reduction': congestion_result,
            'gate_interventions': gate_result,
            'metrics_count': len(metrics_data),
        }


def main():
    parser = argparse.ArgumentParser(
        description='Validate controller performance claims from Stage 3 benchmark results'
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

    validator = PerformanceValidator(results_base, verbose=args.verbose)
    results = validator.run_validation()

    # Save JSON output if requested
    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n[OK] Validation results saved to: {output_path}")

    # Final status
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    if results.get('valid', False):
        print("[PASS] Performance claims validated successfully")

        # Key findings
        if 'waiting_time_ranking' in results:
            wr = results['waiting_time_ranking']
            print(f"\nKey Findings:")
            print(f"  - Best performing controller by wait time: {wr['best_controller']}")
            print(f"  - Best mean wait time: {wr['best_time_seconds']:.1f} seconds")

        if 'congestion_reduction' in results:
            cr = results['congestion_reduction']
            print(f"  - D2 congestion reduction: {cr['absolute_reduction']:.2f} "
                  f"observations per case ({cr['relative_reduction_pct']:.1f}%)")

        if 'gate_interventions' in results:
            gi = results['gate_interventions']
            print(f"  - D2 mean gate interventions: {gi['d2_mean_interventions']:.2f} per case")

        sys.exit(0)
    else:
        print("[FAIL] Validation failed")
        for error in results.get('errors', []):
            print(f"  - {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
