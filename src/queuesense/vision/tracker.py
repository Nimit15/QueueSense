"""Multi-Frame Vehicle Tracker for QueueSense.

Tracks vehicle trajectories across sequential CCTV video frames to measure:
- Real dwell time / waiting time (mean_wait_seconds) for queuing vehicles
- Rolling inflow rate (arrival_rate in veh/min) per approach
- Persistent vehicle counting with IRC SP:41 PCU weighting
- Graceful single-frame heuristic fallback for still images
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrackedVehicle:
    """State of an individual tracked vehicle across frames."""
    track_id: int
    class_id: int
    class_name: str
    pcu_weight: float
    bbox: List[float]  # [x_min, y_min, x_max, y_max]
    first_seen: float
    last_seen: float
    dwell_seconds: float = 0.0
    confidence: float = 0.0
    assigned_approach: Optional[str] = None
    is_stopped: bool = True  # In red-light approach, stopped or queuing


class VehicleTracker:
    """Multi-object tracker with approach-level dwell and arrival aggregation."""

    def __init__(self, fps: float = 10.0, arrival_window_sec: float = 60.0):
        self.fps = fps
        self.arrival_window_sec = arrival_window_sec
        # track_id -> TrackedVehicle
        self._tracks: Dict[int, TrackedVehicle] = {}
        # approach -> deque of (timestamp, track_id)
        self._arrivals: Dict[str, deque] = {
            "north": deque(),
            "south": deque(),
            "east": deque(),
            "west": deque(),
        }
        self._seen_track_ids: set[int] = set()
        self._frame_count: int = 0
        self._last_timestamp: float = 0.0

    def reset(self) -> None:
        """Clear all tracking state."""
        self._tracks.clear()
        self._seen_track_ids.clear()
        for d in self._arrivals.values():
            d.clear()
        self._frame_count = 0
        self._last_timestamp = 0.0

    def update_from_detections(
        self,
        detections: List[Dict],
        timestamp: Optional[float] = None,
        approach_assignments: Optional[Dict[str, List[Dict]]] = None,
    ) -> List[TrackedVehicle]:
        """Update tracker with frame detections.

        If detections already have 'track_id' (from YOLO model.track), use it;
        otherwise apply an IoU centroid fallback match.
        """
        now = timestamp if timestamp is not None else time.time()
        self._last_timestamp = now
        self._frame_count += 1

        active_track_ids = set()
        updated_vehicles: List[TrackedVehicle] = []

        # Map detection to approach if provided
        det_to_approach: Dict[int, str] = {}
        if approach_assignments:
            for app_name, app_dets in approach_assignments.items():
                for d in app_dets:
                    det_to_approach[id(d)] = app_name

        for det in detections:
            track_id = det.get("track_id")
            if track_id is None:
                # Fallback: synthesize track_id from spatial position if missing
                track_id = self._match_or_create_track(det, now)
                det["track_id"] = track_id

            track_id = int(track_id)
            active_track_ids.add(track_id)

            approach = det_to_approach.get(id(det))

            if track_id in self._tracks:
                veh = self._tracks[track_id]
                veh.bbox = det["bbox"]
                veh.confidence = det.get("confidence", 0.0)
                veh.last_seen = now
                veh.dwell_seconds = max(0.0, now - veh.first_seen)
                if approach:
                    veh.assigned_approach = approach
            else:
                veh = TrackedVehicle(
                    track_id=track_id,
                    class_id=det.get("class_id", 0),
                    class_name=det.get("class_name", "Vehicle"),
                    pcu_weight=det.get("pcu_weight", 1.0),
                    bbox=det["bbox"],
                    first_seen=now,
                    last_seen=now,
                    dwell_seconds=0.0,
                    confidence=det.get("confidence", 0.0),
                    assigned_approach=approach,
                )
                self._tracks[track_id] = veh

                # Record arrival event for this approach
                if approach and approach in self._arrivals:
                    self._arrivals[approach].append((now, track_id))

            updated_vehicles.append(veh)

        # Prune old tracks not seen for > 5.0 seconds
        stale_ids = [
            tid for tid, v in self._tracks.items()
            if (now - v.last_seen) > 5.0
        ]
        for tid in stale_ids:
            del self._tracks[tid]

        return updated_vehicles

    def _match_or_create_track(self, det: Dict, now: float) -> int:
        """Simple IoU/Centroid tracker fallback when ByteTrack ID is absent."""
        bbox = det["bbox"]
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0

        best_id = None
        best_dist = 60.0  # max pixel distance for match

        for tid, v in self._tracks.items():
            if (now - v.last_seen) < 1.0:
                vcx = (v.bbox[0] + v.bbox[2]) / 2.0
                vcy = (v.bbox[1] + v.bbox[3]) / 2.0
                dist = np.hypot(cx - vcx, cy - vcy)
                if dist < best_dist:
                    best_dist = dist
                    best_id = tid

        if best_id is not None:
            return best_id

        # Generate new track ID
        new_id = (max(self._tracks.keys(), default=0) + 1)
        return new_id

    def compute_approach_metrics(
        self, approach: str, detections: List[Dict], current_time: Optional[float] = None
    ) -> Dict[str, float]:
        """Compute queue count (PCU), mean wait time, and arrival rate for an approach.

        Supports both multi-frame video tracking and single-frame still image fallback.
        """
        now = current_time if current_time is not None else self._last_timestamp
        if not detections:
            return {
                "queue_count": 0.0,
                "mean_wait_seconds": 0.0,
                "arrival_rate": 0.0,
                "vehicle_count": 0.0,
            }

        vehicle_count = float(len(detections))
        # Total PCU weight
        queue_count_pcu = float(sum(d.get("pcu_weight", 1.0) for d in detections))

        # Check dwell times of tracked vehicles
        dwell_times = []
        for det in detections:
            tid = det.get("track_id")
            if tid is not None and tid in self._tracks:
                dwell_times.append(self._tracks[tid].dwell_seconds)

        # If we have tracked dwell times and multiple frames processed
        if dwell_times and self._frame_count > 3:
            mean_wait = float(np.mean(dwell_times))
        else:
            # Single-frame heuristic fallback: proportional to PCU queue
            mean_wait = queue_count_pcu * 0.5

        # Compute rolling arrival rate (vehicles entering per minute)
        app_arrivals = self._arrivals.get(approach)
        if app_arrivals and self._frame_count > 3:
            # Prune arrivals older than arrival_window_sec
            cutoff = now - self.arrival_window_sec
            while app_arrivals and app_arrivals[0][0] < cutoff:
                app_arrivals.popleft()
            elapsed_win = min(self.arrival_window_sec, max(1.0, now - (app_arrivals[0][0] if app_arrivals else now)))
            arrival_rate = (len(app_arrivals) / elapsed_win) * 60.0
        else:
            # Single-frame heuristic: len(detections) * 2.0
            arrival_rate = float(len(detections)) * 2.0

        return {
            "queue_count": queue_count_pcu,
            "mean_wait_seconds": mean_wait,
            "arrival_rate": arrival_rate,
            "vehicle_count": vehicle_count,
        }
