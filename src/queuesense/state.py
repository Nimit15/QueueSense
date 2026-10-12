"""
QueueSense Standardized State Definitions
Defines the shared data structures connecting Perception, Simulation, and Controllers.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ApproachState:
    """State of an individual junction approach."""
    queue_count: float = 0.0          # PCU-weighted or vehicle count
    mean_wait_seconds: float = 0.0    # Average waiting time of stopped vehicles
    arrival_rate: float = 0.0         # Vehicles per minute entering approach
    downstream_available: bool = True # False if exit road has reached spillback threshold
    measurement_valid: bool = True    # True if sensor observations are trustworthy


@dataclass
class TrafficState:
    """Overall traffic state across all intersection approaches at a timestamp."""
    timestamp: float
    approaches: Dict[str, ApproachState] = field(default_factory=dict)
    all_valid: bool = True

    def get_approach(self, name: str) -> Optional[ApproachState]:
        return self.approaches.get(name)
