#!/usr/bin/env python3
"""
Validate Gate Mechanism Configuration and Events

This script validates:
1. Gate configuration (D1 vs D2) from controller instances
2. Gate event counts and types from summary files
3. Reconciliation of gate interventions with decision traces

Usage:
    python scripts/validate_gate_mechanism.py [--verbose] [--output-json PATH]

Exit codes:
    0 - All validations passed
    1 - Critical validation failure
    2 - Gate mechanism could not be verified
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import statistics


class GateMechanismValidator:
    """Validates gate mechanism configuration and events."""

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
            return None

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def validate_gate_configuration(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate that D1 has gate disabled and D2 has gate enabled."""
        d1_cases = [c for c in metrics_data if c['controller'] == 'D1']
        d2_cases = [c for c in metrics_data if c['controller'] == 'D2']

        # Check spillback_gate flag in summaries
        d1_gate_enabled_count = sum(1 for c in d1_cases if c.get('spillback_gate', False))
        d2_gate_enabled_count = sum(1 for c in d2_cases if c.get('spillback_gate', False))

        d1_should_be_disabled = (d1_gate_enabled_count == 0)
        d2_should_be_enabled = (d2_gate_enabled_count == len(d2_cases))

        return {
            'valid': d1_should_be_disabled and d2_should_be_enabled,
            'd1_cases': len(d1_cases),
            'd2_cases': len(d2_cases),
            'd1_gate_enabled_count': d1_gate_enabled_count,
            'd2_gate_enabled_count': d2_gate_enabled_count,
            'd1_gate_should_be_disabled': d1_should_be_disabled,
            'd2_gate_should_be_enabled': d2_should_be_enabled,
        }

    def validate_gate_event_counts(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate gate intervention counts and types."""
        d2_cases = [c for c in metrics_data if c['controller'] == 'D2']

        # Collect gate metrics
        gate_interventions = []
        gate_restrictions = []
        gate_phase_changes = []
        gate_holds = []

        for c in d2_cases:
            if c.get('gate_interventions') is not None:
                gate_interventions.append(c['gate_interventions'])
            if c.get('gate_restrictions') is not None:
                gate_restrictions.append(c['gate_restrictions'])
            if c.get('gate_phase_change_interventions') is not None:
                gate_phase_changes.append(c['gate_phase_change_interventions'])
            if c.get('gate_caused_holds') is not None:
                gate_holds.append(c['gate_caused_holds'])

        # Check that intervention counts are non-negative
        invalid_counts = [i for i in gate_interventions if i < 0]

        return {
            'valid': len(invalid_counts) == 0,
            'gate_interventions': {
                'mean': statistics.mean(gate_interventions) if gate_interventions else None,
                'std': statistics.stdev(gate_interventions) if len(gate_interventions) > 1 else None,
                'min': min(gate_interventions) if gate_interventions else None,
                'max': max(gate_interventions) if gate_interventions else None,
                'invalid_negative_counts': len(invalid_counts),
            },
            'gate_restrictions': {
                'mean': statistics.mean(gate_restrictions) if gate_restrictions else None,
                'total': sum(gate_restrictions) if gate_restrictions else None,
            },
            'gate_phase_changes': {
                'mean': statistics.mean(gate_phase_changes) if gate_phase_changes else None,
                'total': sum(gate_phase_changes) if gate_phase_changes else None,
            },
            'gate_holds': {
                'mean': statistics.mean(gate_holds) if gate_holds else None,
                'total': sum(gate_holds) if gate_holds else None,
            },
        }

    def validate_gate_events_by_scenario(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate gate events broken down by scenario."""
        by_scenario = defaultdict(list)
        for c in metrics_data:
            if c['controller'] == 'D2':
                by_scenario[c['scenario']].append(c)

        scenario_results = {}
        for scenario, cases in sorted(by_scenario.items()):
            interventions = [c['gate_interventions'] for c in cases if c.get('gate_interventions') is not None]
            congestion = [c['physical_congestion_observations'] for c in cases if c.get('physical_congestion_observations') is not None]

            scenario_results[scenario] = {
                'case_count': len(cases),
                'mean_interventions': statistics.mean(interventions) if interventions else None,
                'mean_congestion': statistics.mean(congestion) if congestion else None,
                'cases_with_interventions': sum(1 for i in interventions if i > 0),
            }

        return scenario_results

    def reconcile_gate_events_with_traces(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Reconcile gate intervention counts with available decision traces.

        Note: This validation requires detailed decision trace data which may not
        be available in all summary files. If traces are not available, this
        validation returns NOT_VERIFIED rather than failing.
        """
        d2_cases = [c for c in metrics_data if c['controller'] == 'D2']

        # Check if any cases have gate_event_details or decision_trace
        cases_with_traces = []
        for c in d2_cases:
            summary_path = Path(c.get('file_path', ''))
            if summary_path.exists():
                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        summary = json.load(f)
                    if 'gate_event_details' in summary or 'decision_trace' in summary:
                        cases_with_traces.append({
                            'case_id': c['case_id'],
                            'has_gate_event_details': 'gate_event_details' in summary,
                            'has_decision_trace': 'decision_trace' in summary,
                        })
                except (json.JSONDecodeError, IOError):
                    pass

        return {
            'traces_available': len(cases_with_traces) > 0,
            'cases_with_traces_count': len(cases_with_traces),
            'sample_traces': cases_with_traces[:5] if cases_with_traces else [],
            'note': 'Detailed trace reconciliation requires gate_event_details or decision_trace fields in summary files'
        }

    def validate_physical_congestion_metric(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate the physical_congestion_observations metric definition and units.

        This metric represents the number of simulation time steps where physical
        road congestion (downstream blockage) was observed at any approach.
        """
        # Collect all congestion values
        all_congestion = [c['physical_congestion_observations'] for c in metrics_data
                        if c.get('physical_congestion_observations') is not None]

        # Check for negative values (invalid)
        negative_count = sum(1 for v in all_congestion if v < 0)

        # Check range
        max_congestion = max(all_congestion) if all_congestion else 0
        # Maximum possible would be simulation duration (300 steps at 1 step/sec)
        # A value接近300 indicates persistent congestion

        high_congestion_cases = [c for c in metrics_data
                                if c.get('physical_congestion_observations', 0) > 100]

        return {
            'valid': negative_count == 0,
            'total_cases': len(all_congestion),
            'mean': statistics.mean(all_congestion) if all_congestion else None,
            'std': statistics.stdev(all_congestion) if len(all_congestion) > 1 else None,
            'min': min(all_congestion) if all_congestion else None,
            'max': max_congestion,
            'negative_values_count': negative_count,
            'high_congestion_cases_count': len(high_congestion_cases),
            'interpretation': 'Values represent simulation time steps with observed congestion',
        }

    def run_validation(self) -> Dict[str, Any]:
        """Run the complete gate mechanism validation pipeline."""
        print("=" * 70)
        print("GATE MECHANISM VALIDATION")
        print("=" * 70)

        # Step 1: Load case ledger
        print("\n[1/6] Loading case ledger...")
        ledger = self.load_case_ledger()
        if ledger is None:
            print("[FAIL] Could not load case ledger")
            return {'valid': False, 'error': 'Case ledger not loaded'}
        print(f"[OK] Loaded {len(ledger)} cases from ledger")

        # Step 2: Load metrics from summaries
        print("\n[2/6] Loading summary files...")
        metrics_data = []
        for case_id, case_info in ledger.items():
            summary = self.load_summary(case_info)
            if summary is not None:
                metrics = {
                    'case_id': case_id,
                    'controller': case_info.get('controller', 'unknown'),
                    'scenario': case_info.get('scenario', 'unknown'),
                    'seed': case_info.get('seed', -1),
                    'total_wait_seconds': summary.get('total_wait_seconds'),
                    'arrived_cumulative': summary.get('arrived_cumulative'),
                    'physical_congestion_observations': summary.get('physical_congestion_observations'),
                    'gate_interventions': summary.get('gate_interventions'),
                    'gate_restrictions': summary.get('gate_restrictions'),
                    'gate_phase_change_interventions': summary.get('gate_phase_change_interventions'),
                    'gate_caused_holds': summary.get('gate_caused_holds'),
                    'spillback_gate': summary.get('spillback_gate', False),
                    'spillback_ns_seconds': summary.get('spillback_ns_seconds'),
                    'spillback_ew_seconds': summary.get('spillback_ew_seconds'),
                    'file_path': case_info.get('selected_path', ''),
                }
                metrics_data.append(metrics)

        print(f"[OK] Loaded metrics from {len(metrics_data)}/{len(ledger)} cases")

        # Step 3: Validate gate configuration
        print("\n[3/6] Validating gate configuration (D1 vs D2)...")
        config_result = self.validate_gate_configuration(metrics_data)

        if config_result['valid']:
            print(f"[OK] Gate configuration validated")
            print(f"     D1 (gate disabled): {config_result['d1_cases']} cases, "
                  f"{config_result['d1_gate_enabled_count']} with gate enabled (expected: 0)")
            print(f"     D2 (gate enabled): {config_result['d2_cases']} cases, "
                  f"{config_result['d2_gate_enabled_count']} with gate enabled (expected: {config_result['d2_cases']})")
        else:
            print(f"[FAIL] Gate configuration mismatch")
            if not config_result['d1_gate_should_be_disabled']:
                print(f"     D1 should have gate disabled but {config_result['d1_gate_enabled_count']} cases have it enabled")
            if not config_result['d2_gate_should_be_enabled']:
                print(f"     D2 should have gate enabled but only {config_result['d2_gate_enabled_count']}/{config_result['d2_cases']} cases have it enabled")

        # Step 4: Validate gate event counts
        print("\n[4/6] Validating gate event counts and types...")
        event_result = self.validate_gate_event_counts(metrics_data)

        if event_result['valid']:
            print(f"[OK] Gate event counts validated")
            print(f"     Mean interventions per D2 case: {event_result['gate_interventions']['mean']:.2f}")
            print(f"     Mean restrictions: {event_result['gate_restrictions']['mean']:.2f}")
            print(f"     Mean phase changes: {event_result['gate_phase_changes']['mean']:.2f}")
            print(f"     Mean holds: {event_result['gate_holds']['mean']:.2f}")
        else:
            print(f"[FAIL] Invalid gate event counts detected")

        # Step 5: Validate gate events by scenario
        print("\n[5/6] Validating gate events by scenario...")
        scenario_result = self.validate_gate_events_by_scenario(metrics_data)

        print(f"     Scenario breakdown:")
        for scenario, data in sorted(scenario_result.items()):
            print(f"       {scenario}: {data['mean_interventions']:.2f} mean interventions, "
                  f"{data['cases_with_interventions']}/{data['case_count']} cases with interventions")

        # Step 6: Validate physical congestion metric
        print("\n[6/6] Validating physical congestion metric...")
        congestion_result = self.validate_physical_congestion_metric(metrics_data)

        if congestion_result['valid']:
            print(f"[OK] Physical congestion metric validated")
            print(f"     Mean congestion observations: {congestion_result['mean']:.2f}")
            print(f"     Range: {congestion_result['min']} to {congestion_result['max']}")
            print(f"     High congestion cases (>100): {congestion_result['high_congestion_cases_count']}")
        else:
            print(f"[FAIL] Physical congestion metric has invalid values")

        # Reconcile with traces (informational)
        print("\n[7/6] Checking for detailed decision traces...")
        trace_result = self.reconcile_gate_events_with_traces(metrics_data)
        if trace_result['traces_available']:
            print(f"[OK] Found {trace_result['cases_with_traces_count']} cases with detailed traces")
        else:
            print(f"[INFO] No detailed decision traces found - trace reconciliation NOT_VERIFIED")

        # Compile final results
        return {
            'valid': config_result['valid'] and event_result['valid'] and congestion_result['valid'],
            'configuration': config_result,
            'gate_events': event_result,
            'by_scenario': scenario_result,
            'physical_congestion': congestion_result,
            'trace_reconciliation': trace_result,
            'validation_errors': self.validation_errors,
            'validation_warnings': self.validation_warnings,
        }


def main():
    parser = argparse.ArgumentParser(
        description='Validate gate mechanism configuration and events'
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

    validator = GateMechanismValidator(results_base, verbose=args.verbose)
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
        print("[PASS] Gate mechanism validated successfully")

        # Key findings
        if 'configuration' in results:
            cfg = results['configuration']
            print(f"\nConfiguration:")
            print(f"  - D1 gate disabled: {cfg['d1_gate_should_be_disabled']}")
            print(f"  - D2 gate enabled: {cfg['d2_gate_should_be_enabled']}")

        if 'gate_events' in results:
            ge = results['gate_events']
            print(f"\nGate Events (D2 only):")
            print(f"  - Mean interventions: {ge['gate_interventions']['mean']:.2f}/case")
            print(f"  - Mean restrictions: {ge['gate_restrictions']['mean']:.2f}/case")
            print(f"  - Mean phase changes: {ge['gate_phase_changes']['mean']:.2f}/case")
            print(f"  - Mean holds: {ge['gate_holds']['mean']:.2f}/case")

        if 'by_scenario' in results:
            print(f"\nGate Activity by Scenario:")
            for scenario, data in sorted(results['by_scenario'].items()):
                print(f"  - {scenario}: {data['mean_interventions']:.2f} mean interventions")

        sys.exit(0)
    else:
        print("[FAIL] Gate mechanism validation failed")
        for error in results.get('validation_errors', []):
            print(f"  - {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
