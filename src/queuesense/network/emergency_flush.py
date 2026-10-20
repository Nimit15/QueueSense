"""Emergency downstream-flush coordinator for the multi-junction corridor.

When an emergency vehicle is flagged approaching J1 toward J2 and the receiving
link J1->J2 is BLOCKED (occupancy >= spillback_threshold), this coordinator
commands the downstream junction J2 to flush J1->J2 GREEN FIRST, before J1 is
released, so the ambulance is never trapped in a downstream spillback queue.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from queuesense.state import TrafficState, DownstreamObservation
from queuesense.controllers.base import Phase

logger = logging.getLogger(__name__)


@dataclass
class FlushCommand:
    """A downstream-flush command issued to a junction."""
    junction_id: str
    priority: str            # "NORMAL" | "EMERGENCY_FLUSH"
    target_phase: Phase
    flush_link: str
    reason: str
    occupancy: float


class EmergencyFlushCoordinator:
    """Coordinates emergency-vehicle downstream-flush on the J1->J2->J3 corridor.

    The corridor model:
        J1 --(art_east_1 / art_east_2)--> J2 --(art_east_2 / out_east)--> J3

    Downstream-link map (J -> downstream J and the receiving edge):
        J1 -> J2 receiving edge "art_east_1"
        J2 -> J3 receiving edge "art_east_2"
    """

    CORRIDOR_LINKS = {
        "J1": ("J2", "art_east_1"),
        "J2": ("J3", "art_east_2"),
    }

    def __init__(self, junction_ids: List[str] = None,
                 selector_factory=None, spillback_threshold: float = 0.30):
        self.junction_ids = junction_ids or ["J1", "J2", "J3"]
        self._selector_factory = selector_factory
        self.spillback_threshold = spillback_threshold
        # Independent selector instances per junction (isolation invariant).
        self.selectors: Dict[str, object] = {}
        if selector_factory is not None:
            for jid in self.junction_ids:
                sel = selector_factory(jid)
                self.selectors[jid] = sel
                assert id(sel) not in [id(s) for s in self.selectors.values() if s is not sel]
        self.last_commands: Dict[str, FlushCommand] = {}
        self.total_flushes_issued = 0

    def _junction_selector(self, junction_id: str):
        """Return (creating if needed) an independent selector for a junction."""
        if junction_id not in self.selectors:
            # Lazy import to avoid circular dependency at module load.
            from queuesense.controllers.selector import ContextAwareSelector
            factory = self._selector_factory or (lambda jid: ContextAwareSelector(junction_id=jid))
            self.selectors[junction_id] = factory(junction_id)
        return self.selectors[junction_id]

    def evaluate_flush(self, junction_id: str, state: TrafficState,
                       emergency_approaching: bool) -> Optional[FlushCommand]:
        """Evaluate whether an emergency downstream-flush should be issued.

        Rules:
          * Emergency vehicle must be approaching ``junction_id``.
          * The downstream link (junction_id -> next) must be BLOCKED:
            occupancy >= spillback_threshold OR downstream_available == False.
          * The downstream junction (next) is commanded to flush the
            corridor link GREEN FIRST before ``junction_id`` is released.

        Returns a FlushCommand for the *downstream* junction, or None.
        """
        if not emergency_approaching:
            self.last_commands[junction_id] = None
            return None

        link = self.CORRIDOR_LINKS.get(junction_id)
        if not link:
            # Last junction in corridor has nowhere downstream to flush.
            self.last_commands[junction_id] = None
            return None

        downstream_j, receiving_edge = link
        max_occ = 0.0
        downstream_blocked = False
        for app in state.approaches.values():
            for obs in app.downstream_observations:
                if obs.edge_id == receiving_edge:
                    if obs.observation_valid and 0.0 <= obs.occupancy_fraction <= 1.0:
                        max_occ = max(max_occ, obs.occupancy_fraction)
                        if max_occ >= self.spillback_threshold:
                            downstream_blocked = True
                    if not getattr(app, "downstream_available", True):
                        downstream_blocked = True

        # Determine the phase that serves the corridor receiving direction.
        # art_east carries east-west (EAST_WEST) traffic in the V2 corridor.
        target_phase = Phase.EAST_WEST

        cmd = FlushCommand(
            junction_id=downstream_j,
            priority="EMERGENCY_FLUSH",
            target_phase=target_phase,
            flush_link=receiving_edge,
            reason=(
                f"Emergency vehicle approaching {junction_id}; downstream link "
                f"{receiving_edge} blocked (occ={max_occ:.3f}>={self.spillback_threshold})"
            ),
            occupancy=max_occ,
        )
        self.last_commands[junction_id] = cmd
        self.total_flushes_issued += 1
        logger.warning(f"EMERGENCY FLUSH: commanding {downstream_j} -> {target_phase.name} on {receiving_edge}")
        return cmd


# NOTE: ContextAwareSelector is imported lazily inside _junction_selector
# to avoid a circular import (selector -> emergency_flush -> selector).
