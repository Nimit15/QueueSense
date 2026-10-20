"""ROI (Region of Interest) Calibration & Downstream Blockage Evaluation for QueueSense.

Supports brownfield CCTV deployment at Indian intersections:
- Upstream Approach Polygons: Measure vehicle queue demand waiting before the stop-line.
- Downstream Receiving Exit Polygons: Measure exit road saturation beyond the junction (spillback risk).
- JSON configuration schema with click-to-draw calibration support.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ROIConfig:
    """Polygonal ROI configuration for an intersection camera."""
    camera_id: str = "RLVD_N1_CORRIDOR"
    resolution: Tuple[int, int] = (1920, 1080)  # (width, height)
    # Approach name -> list of normalized [x, y] coordinates in [0, 1]
    upstream_rois: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    # Downstream exit name -> list of normalized [x, y] coordinates in [0, 1]
    downstream_rois: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    # Mapping from downstream link name to feeding upstream approach names
    # e.g. {"art_east": ["east", "west"], "out_north": ["north", "south"]}
    downstream_to_upstream: Dict[str, List[str]] = field(default_factory=dict)
    # Occupancy ratio [0.0, 1.0] above which downstream is declared saturated/blocked
    spillback_threshold: float = 0.85

    @classmethod
    def default_quadrant(cls, resolution: Tuple[int, int] = (1920, 1080)) -> "ROIConfig":
        """Generate default road geometry with calibrated perspective trapezoid lane coordinates."""
        # Clean perspective trapezoid strictly on lower road surface (Waiting Queue Lane)
        waiting_trap = [(0.22, 0.42), (0.46, 0.42), (0.52, 0.82), (0.12, 0.82)]
        # Clean perspective trapezoid strictly on lower road surface (Downstream Exit Lane)
        exit_trap = [(0.54, 0.42), (0.78, 0.42), (0.90, 0.82), (0.58, 0.82)]

        return cls(
            camera_id="FIXED_POLE_MOUNTED_CCTV_CAM04",
            resolution=resolution,
            upstream_rois={
                "north": waiting_trap,
                "south": [(0.10, 0.50), (0.45, 0.50), (0.45, 0.85), (0.10, 0.85)],
                "east":  [(0.50, 0.40), (0.85, 0.40), (0.85, 0.80), (0.50, 0.80)],
                "west":  [(0.15, 0.45), (0.48, 0.45), (0.48, 0.82), (0.15, 0.82)],
                "waiting_queue": waiting_trap,
            },
            downstream_rois={
                "art_east": exit_trap,
                "downstream_exit": exit_trap,
                "out_north": [(0.45, 0.15), (0.80, 0.15), (0.80, 0.40), (0.45, 0.40)],
            },
            downstream_to_upstream={
                "art_east": ["east", "west"],
                "downstream_exit": ["east", "west"],
                "out_north": ["north", "south"],
            },
            spillback_threshold=0.85,
        )

    @classmethod
    def load(cls, path: str | Path) -> "ROIConfig":
        """Load ROI configuration from JSON file."""
        p = Path(path)
        if not p.exists():
            logger.warning(f"ROI config file not found at {p}, using default configuration.")
            return cls.default_quadrant()

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            def _clean_polygons(poly_dict: Dict[str, Any]) -> Dict[str, List[Tuple[float, float]]]:
                cleaned = {}
                for name, pts in poly_dict.items():
                    poly = []
                    for pt in pts:
                        poly.append((float(pt[0]), float(pt[1])))
                    cleaned[name] = poly
                return cleaned

            return cls(
                camera_id=data.get("camera_id", "CUSTOM_CAMERA"),
                resolution=tuple(data.get("resolution", [1920, 1080])),
                upstream_rois=_clean_polygons(data.get("upstream_rois", {})),
                downstream_rois=_clean_polygons(data.get("downstream_rois", {})),
                downstream_to_upstream=data.get("downstream_to_upstream", {
                    "art_east": ["east", "west"],
                    "out_north": ["north", "south"],
                }),
                spillback_threshold=float(data.get("spillback_threshold", 0.85)),
            )
        except Exception as e:
            logger.error(f"Error parsing ROI config {path}: {e}. Falling back to default.")
            return cls.default_quadrant()

    def save(self, path: str | Path) -> None:
        """Save ROI configuration to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "camera_id": self.camera_id,
            "resolution": list(self.resolution),
            "upstream_rois": {k: [list(pt) for pt in v] for k, v in self.upstream_rois.items()},
            "downstream_rois": {k: [list(pt) for pt in v] for k, v in self.downstream_rois.items()},
            "downstream_to_upstream": self.downstream_to_upstream,
            "spillback_threshold": self.spillback_threshold,
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved ROI config to {p}")


class ROIProcessor:
    """Evaluates vehicle detections against upstream approach & downstream exit ROIs."""

    def __init__(self, config: Optional[ROIConfig] = None):
        self.config = config or ROIConfig.default_quadrant()

    @staticmethod
    def point_in_polygon(cx: float, cy: float, polygon: List[Tuple[float, float]]) -> bool:
        """Ray-casting point-in-polygon algorithm on normalized [0, 1] coordinates."""
        inside = False
        n = len(polygon)
        if n < 3:
            return False
        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            if (y1 > cy) != (y2 > cy):
                x_intersect = x1 + (cy - y1) * (x2 - x1) / (y2 - y1) if (y2 - y1) != 0 else x1
                if cx < x_intersect:
                    inside = not inside
        return inside

    @staticmethod
    def polygon_area(polygon: List[Tuple[float, float]], img_w: int, img_h: int) -> float:
        """Calculate pixel area of a normalized polygon using the Shoelace formula."""
        n = len(polygon)
        if n < 3:
            return 1.0
        pts = np.array([[p[0] * img_w, p[1] * img_h] for p in polygon], dtype=np.float32)
        return float(cv2.contourArea(pts))

    def assign_upstream(
        self, detections: List[Dict], image_width: int, image_height: int
    ) -> Dict[str, List[Dict]]:
        """Map detections to upstream approach ROIs (North, South, East, West).

        Double-counting prevention: A detection is assigned to the first matching ROI.
        """
        result: Dict[str, List[Dict]] = {name: [] for name in self.config.upstream_rois}
        # Fallback keys if empty
        if not result:
            result = {"north": [], "south": [], "east": [], "west": []}

        for det in detections:
            x_min, y_min, x_max, y_max = det["bbox"]
            cx = (x_min + x_max) / 2.0 / image_width
            cy = (y_min + y_max) / 2.0 / image_height

            assigned = False
            for name, poly in self.config.upstream_rois.items():
                if self.point_in_polygon(cx, cy, poly):
                    result[name].append(det)
                    assigned = True
                    break

            if not assigned:
                # Geometric fallback quadrant
                if cy < 0.5 and 0.25 <= cx <= 0.75:
                    result.setdefault("north", []).append(det)
                elif cy >= 0.5 and 0.25 <= cx <= 0.75:
                    result.setdefault("south", []).append(det)
                elif cx >= 0.5:
                    result.setdefault("east", []).append(det)
                else:
                    result.setdefault("west", []).append(det)

        return result

    def compute_downstream_occupancy(
        self, detections: List[Dict], roi_name: str, image_width: int, image_height: int
    ) -> float:
        """Compute occupancy ratio [0.0, 1.0] of a downstream receiving link.

        Calculated as the cumulative footprint of detected vehicles inside the polygon
        normalized by the polygon's projected pixel road capacity.
        """
        poly = self.config.downstream_rois.get(roi_name)
        if not poly or len(poly) < 3:
            return 0.0

        poly_pixel_area = self.polygon_area(poly, image_width, image_height)
        if poly_pixel_area <= 1.0:
            return 0.0

        total_vehicle_area = 0.0
        for det in detections:
            x_min, y_min, x_max, y_max = det["bbox"]
            cx = (x_min + x_max) / 2.0 / image_width
            cy = (y_min + y_max) / 2.0 / image_height
            if self.point_in_polygon(cx, cy, poly):
                # Clamp bbox area to avoid camera perspective blowout
                w = max(1.0, x_max - x_min)
                h = max(1.0, y_max - y_min)
                # PCU weight scales physical vehicle space on the road
                pcu = det.get("pcu_weight", 1.0)
                total_vehicle_area += (w * h) * min(pcu, 2.0)

        # Capacity factor: road packing ratio (vehicles cannot pack 100% of road surface)
        # Saturated bumper-to-bumper queue achieves ~40-50% pixel fill in 2D perspective
        packing_saturation_factor = 0.45
        effective_capacity = poly_pixel_area * packing_saturation_factor
        occupancy = min(1.0, max(0.0, total_vehicle_area / effective_capacity))
        return float(occupancy)

    def evaluate_downstream_status(
        self, detections: List[Dict], image_width: int, image_height: int
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluate saturation and blockage for all configured downstream exit links.

        Returns:
            Dict mapping downstream_link -> {
                "occupancy": float in [0.0, 1.0],
                "is_blocked": bool,
                "feeding_approaches": List[str]
            }
        """
        status = {}
        for link_name in self.config.downstream_rois:
            occ = self.compute_downstream_occupancy(detections, link_name, image_width, image_height)
            is_blocked = occ >= self.config.spillback_threshold
            feeding = self.config.downstream_to_upstream.get(link_name, [])
            status[link_name] = {
                "occupancy": occ,
                "is_blocked": is_blocked,
                "feeding_approaches": feeding,
            }
        return status
