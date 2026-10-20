"""
QueueSense Standardized State Definitions
Defines the shared data structures connecting Perception, Simulation, and Controllers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DownstreamObservation:
    """Per-receiving-edge downstream observation.

    Separates four distinct concepts that must never be conflated:

    1. Physical congestion -- measured road/link condition derived from a
       *valid* observation (``observation_valid=True``).
    2. Movement eligibility -- whether the movement's actual receiving links
       can accept traffic (``eligible``).
    3. Gate decision -- whether the controller restricts the movement
       (``gate_suppresses``).  Independent of physical congestion.
    4. Unknown state -- missing edge, invalid ID, TraCI exception, unavailable
       sensor or stale observation (``observation_valid=False``).

    An edge lookup exception must NEVER be recorded as proof of physical
    spillback.  It is an UNKNOWN state; the configured conservative safety
    policy applies, but the fault is logged separately as a
    sensing/configuration fault.

    Occupancy unit convention (verified for SUMO 1.28.0 edge API):
        ``edge_occupancy_fraction`` is the value returned by
        ``traci.edge.getLastStepOccupancy()``.  The official Python API
        docstring describes this as percent (0-100), but the observed
        runtime behaviour in SUMO 1.28.0 returns a normalized fraction in
        [0.0, 1.0].  Verified empirically: 14 vehicles (70.0 m total length)
        on a 276.63 m single-lane edge produced 0.2530 -- exactly matching
        the vehicle fill ratio (70/276.63).  The raw return is therefore
        treated directly as a fraction.  NO /100.0 conversion is applied.
        The configured ``threshold`` is expressed as a fraction
        (e.g. 0.30 = 30% normalized occupancy).

    Other occupancy sources (lane-area detectors, vision-derived occupancy)
    may use different scales.  Normalize each at its own boundary; do not
    assume every occupancy API shares the edge API's convention.
    """
    edge_id: str = ""                 # Receiving edge ID queried from SUMO
    observation_valid: bool = True    # False if edge lookup failed / sensor unavailable
    edge_occupancy_fraction: float = 0.0  # Raw traci.edge.getLastStepOccupancy() return (verified fraction)
    occupancy_fraction: float = 0.0   # Normalised fraction in [0.0, 1.0] (same as edge_occupancy_fraction for edge API)
    threshold: float = 0.30           # Configured spillback threshold (fraction)
    congested: bool = False           # Physical congestion: occupancy_fraction >= threshold
    eligible: bool = True             # Movement eligibility: at least one receiving edge clear
    gate_suppresses: bool = False     # Gate decision: controller restricts this movement
    error: str = ""                   # Non-empty only when observation_valid is False
    confidence: float = 1.0           # Detection confidence in [0.0, 1.0] (1.0 = trusted sensor)
    age_s: float = 0.0                # Seconds since observation was captured (freshness)


@dataclass
class ApproachState:
    """State of an individual junction approach."""
    queue_count: float = 0.0          # PCU-weighted or vehicle count
    mean_wait_seconds: float = 0.0    # Average waiting time of stopped vehicles
    arrival_rate: float = 0.0         # Vehicles per minute entering approach
    downstream_available: bool = True # False if exit road has reached spillback threshold
    measurement_valid: bool = True    # True if sensor observations are trustworthy
    downstream_observations: List[DownstreamObservation] = field(default_factory=list)


@dataclass
class TrafficState:
    """Overall traffic state across all intersection approaches at a timestamp."""
    timestamp: float
    approaches: Dict[str, ApproachState] = field(default_factory=dict)
    all_valid: bool = True

    def get_approach(self, name: str) -> Optional[ApproachState]:
        return self.approaches.get(name)


@dataclass
class DecisionReceipt:
    """Structured auditable decision receipt emitted by ContextAwareSelector every step.

    This is the government/ICCC deployment audit artifact: every control decision
    records its capacity regime, the ungated candidate, the gate check result, the
    safety-supervisor override flag, and the phase actually applied to SUMO.

    Capacity status is one of CLEAR / BLOCKED / UNKNOWN.  UNKNOWN is NEVER
    silently mapped to CLEAR -- it drives conservative gated selection and the
    3-strike watchdog fallback.
    """
    timestamp: float = 0.0
    junction_id: str = ""
    capacity_status: str = ""     # CLEAR | BLOCKED | UNKNOWN
    selected_mode: str = ""       # C | D2 | FALLBACK
    max_downstream_occupancy: float = 0.0
    trigger_edge_id: str = ""
    ungated_phase: str = ""
    gated_phase: str = ""
    gate_intervened: bool = False
    safety_override: bool = False
    applied_phase: str = ""
    reason_code: str = ""
    reason: str = ""