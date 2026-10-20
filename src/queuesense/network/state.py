"""QueueSense Network State - Shared data structures for multi-junction coordination.

This module defines the standardized state structures that enable inter-junction
communication and coordination. Each junction publishes its TrafficState, and
the coordinator consumes neighboring junction states to make informed signal
allocation decisions.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from queuesense.controllers.base import Phase


@dataclass
class JunctionState:
    """State of a single signalized junction for network coordination.

    This is the published state that the coordinator consumes from each
    junction. It includes only the information needed for network-level
    decision-making, while each junction's local controller retains its own
    full internal state.
    """
    junction_id: str  # Unique identifier for the junction
    timestamp: float
    approaches: Dict[str, object]  # ApproachState summaries
    phase: Optional[Phase] = None  # Current signal phase
    all_valid: bool = True  # Sensor/measurement validity
    downstream_blocked: bool = False  # Overall downstream blockage status
    predicted_arrivals: Dict[str, float] = field(default_factory=dict)  # Predicted arrivals per approach in next N seconds


@dataclass
class NetworkReport:
    """Aggregated network report from the coordinator.

    This is consumed by the ICCC dashboard and contains metrics that reflect
    the coordinated behavior across all junctions.
    """
    timestamp: float
    total_arrivals: float
    total_departures: float
    aggregate_queue_length: float
    spillback_count: int  # Number of junctions with downstream blockage
    coordination_efficiency: float  # Ratio of successful coordinated departures
    phase_coordination: Dict[str, str]  # Per-junction current phase state
    warnings: List[str]  # Any coordination warnings or faults
