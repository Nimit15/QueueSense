"""UVH-26 YOLOv11-S Vehicle Detector & Traffic State Engine for QueueSense.

Wraps the pre-trained IISc AIM UVH-26 YOLOv11-S checkpoint for vehicle
detection on Indian CCTV camera perspectives (Wi-TraC / CoSiCoSt / ICCC).
Integrates with:
- IRC SP:41 Passenger Car Unit (PCU) weighting for mixed traffic
- Brownfield Upstream Approach & Downstream Receiving Exit Polygons
- Multi-Frame Tracking (ByteTrack) for dwell time & inflow rate
- Downstream spillback gate for QueueSenseController
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
from ultralytics import YOLO

from queuesense.state import ApproachState, TrafficState
from queuesense.vision.roi import ROIConfig, ROIProcessor
from queuesense.vision.tracker import VehicleTracker

logger = logging.getLogger(__name__)

# Default model checkpoint
DEFAULT_MODEL_PATH = Path("data/incoming/models/UVH-26-MV-YOLOv11-S.pt")

# Standard Indian Roads Congress (IRC SP:41 / IRC 106) PCU Weights
IRC_SP41_PCU_WEIGHTS: Dict[str, float] = {
    "two-wheeler": 0.5,
    "bicycle": 0.2,
    "three-wheeler": 1.0,   # Corrected: Auto-rickshaw is 1.0 PCU (was previously 2.0)
    "auto-rickshaw": 1.0,
    "hatchback": 1.0,
    "sedan": 1.0,
    "car": 1.0,
    "suv": 1.0,
    "muv": 1.0,
    "van": 1.5,
    "lcv": 1.5,
    "tempo-traveller": 2.0,
    "mini-bus": 2.5,
    "bus": 3.0,
    "truck": 3.0,
    "others": 1.0,
}

# Color palette (BGR) for UVH-26 Indian vehicle classes (SEVA Specification)
CLASS_COLORS: Dict[str, Tuple[int, int, int]] = {
    # Two-Wheeler (0.5 PCU) -> Bright Cyan (#06b6d4 -> BGR: 212, 182, 6)
    "two-wheeler": (212, 182, 6),
    "bicycle": (212, 182, 6),
    # Auto / 3W (1.0 PCU) -> Bright Amber (#f59e0b -> BGR: 11, 158, 245)
    "three-wheeler": (11, 158, 245),
    # Car / Sedan / SUV (1.0 PCU) -> Bright Blue (#3b82f6 -> BGR: 246, 130, 59)
    "hatchback": (246, 130, 59),
    "sedan": (246, 130, 59),
    "suv": (246, 130, 59),
    "muv": (246, 130, 59),
    "van": (246, 130, 59),
    # Bus / Truck / Heavy (3.0 PCU) -> Bright Emerald / Orange (#10b981 -> BGR: 129, 185, 16)
    "bus": (129, 185, 16),
    "mini-bus": (129, 185, 16),
    "truck": (16, 140, 245),
    "lcv": (16, 140, 245),
    "tempo-traveller": (16, 140, 245),
    "others": (180, 180, 180),
}

# Default calibrated confidence threshold for cross-dataset Indian CCTV
DEFAULT_CONF_THRESHOLD = 0.12

# Minimum bounding box area in pixels to filter optical noise
MIN_BBOX_AREA = 80


class UVH26Detector:
    """YOLOv11-S detector for Indian CCTV traffic analysis."""

    def __init__(
        self,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        conf_threshold: float = DEFAULT_CONF_THRESHOLD,
        min_bbox_area: int = MIN_BBOX_AREA,
    ):
        self._model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.min_bbox_area = min_bbox_area
        self._model: Optional[YOLO] = None
        self.class_names: Dict[int, str] = {}
        self.pcu_map: Dict[int, float] = {}

        self._load_model()

    def _load_model(self) -> None:
        """Load YOLO checkpoint and read dynamic class names."""
        if not self._model_path.exists():
            raise FileNotFoundError(f"UVH-26 checkpoint not found at: {self._model_path}")
        try:
            import torch
            torch.set_num_threads(2)
        except Exception:
            pass
        self._model = YOLO(str(self._model_path))
        # Read class names directly from checkpoint metadata
        self.class_names = dict(self._model.names)
        self._build_pcu_map()
        logger.info(
            f"Loaded UVH-26 YOLOv11 model with {len(self.class_names)} classes: "
            f"{list(self.class_names.values())}"
        )

    def _build_pcu_map(self) -> None:
        """Map model class indices to calibrated IRC SP:41 PCU weights."""
        self.pcu_map = {}
        for cls_id, name in self.class_names.items():
            name_clean = name.lower().strip()
            # 1. Exact match first
            if name_clean in IRC_SP41_PCU_WEIGHTS:
                self.pcu_map[cls_id] = IRC_SP41_PCU_WEIGHTS[name_clean]
                continue
            # 2. Specific compound matches
            if "mini-bus" in name_clean or "minibus" in name_clean:
                self.pcu_map[cls_id] = 2.5
            elif "tempo" in name_clean:
                self.pcu_map[cls_id] = 2.0
            elif "bus" in name_clean:
                self.pcu_map[cls_id] = 3.0
            elif "truck" in name_clean:
                self.pcu_map[cls_id] = 3.0
            elif "three-wheeler" in name_clean or "rickshaw" in name_clean:
                self.pcu_map[cls_id] = 1.0
            elif "two-wheeler" in name_clean or "motorcycle" in name_clean or "scooter" in name_clean:
                self.pcu_map[cls_id] = 0.5
            elif "van" in name_clean or "lcv" in name_clean:
                self.pcu_map[cls_id] = 1.5
            elif "bicycle" in name_clean or "cycle" in name_clean:
                self.pcu_map[cls_id] = 0.2
            else:
                self.pcu_map[cls_id] = 1.0

    @property
    def model(self) -> YOLO:
        if self._model is None:
            self._load_model()
        return self._model

    def detect(self, image: np.ndarray, track: bool = False) -> List[Dict[str, Any]]:
        """Run vehicle detection on a BGR image frame.

        Args:
            image: BGR image numpy array.
            track: If True, uses ByteTrack multi-frame persistence.

        Returns:
            List of detection dictionaries with keys:
            - bbox: [x1, y1, x2, y2]
            - class_id: int
            - class_name: str
            - confidence: float
            - pcu_weight: float
            - area: float
            - track_id: Optional[int]
        """
        if image is None or image.size == 0:
            return []

        # Run inference
        if track:
            try:
                results = self.model.track(
                    image,
                    persist=True,
                    conf=self.conf_threshold,
                    verbose=False,
                )
            except Exception as e:
                logger.warning(f"Tracker error ({e}), falling back to standard detection")
                results = self.model(image, conf=self.conf_threshold, verbose=False)
        else:
            results = self.model(image, conf=self.conf_threshold, verbose=False)

        r = results[0]
        detections: List[Dict[str, Any]] = []

        if r.boxes is None or len(r.boxes) == 0:
            return detections

        has_tracks = hasattr(r.boxes, "id") and r.boxes.id is not None
        track_ids = r.boxes.id.cpu().numpy().tolist() if has_tracks else [None] * len(r.boxes)

        for i, box in enumerate(r.boxes):
            conf = float(box.conf[0])
            if conf < self.conf_threshold:
                continue

            xyxy = box.xyxy[0].cpu().numpy().tolist()
            x1, y1, x2, y2 = xyxy
            area = max(0.0, (x2 - x1) * (y2 - y1))
            if area < self.min_bbox_area:
                continue

            cls_id = int(box.cls[0])
            cls_name = self.class_names.get(cls_id, f"Class_{cls_id}")
            pcu = self.pcu_map.get(cls_id, 1.0)
            tid = int(track_ids[i]) if track_ids[i] is not None else None

            detections.append({
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "class_id": cls_id,
                "class_name": cls_name,
                "confidence": conf,
                "pcu_weight": pcu,
                "area": area,
                "track_id": tid,
            })

        return detections

    def build_traffic_state(
        self,
        frame: np.ndarray,
        roi_config: Optional[ROIConfig] = None,
        tracker: Optional[VehicleTracker] = None,
        timestamp: float = 0.0,
    ) -> Tuple[TrafficState, List[Dict[str, Any]], Dict[str, Any]]:
        """End-to-End Perception Pipeline: Frame -> Detections -> ROIs -> TrafficState.

        Returns:
            Tuple of:
            - TrafficState for QueueSenseController.step()
            - List of detections
            - Downstream status dict
        """
        config = roi_config or ROIConfig.default_quadrant()
        processor = ROIProcessor(config)

        h, w = frame.shape[:2]

        # Run detection with tracking if tracker is provided
        use_tracking = tracker is not None
        detections = self.detect(frame, track=use_tracking)

        # Assign detections to upstream approach polygons
        approach_detections = processor.assign_upstream(detections, w, h)

        # Update tracker with detections and approach assignments
        if tracker is not None:
            tracker.update_from_detections(detections, timestamp, approach_detections)

        # Evaluate downstream exit links (e.g. art_east, out_north)
        downstream_status = processor.evaluate_downstream_status(detections, w, h)

        # Construct ApproachState for each approach
        approaches: Dict[str, ApproachState] = {}
        for app_name in ["north", "south", "east", "west"]:
            dets = approach_detections.get(app_name, [])

            if tracker is not None:
                metrics = tracker.compute_approach_metrics(app_name, dets, timestamp)
                queue_count = metrics["queue_count"]
                mean_wait = metrics["mean_wait_seconds"]
                arrival_rate = metrics["arrival_rate"]
            else:
                queue_count = float(sum(d["pcu_weight"] for d in dets))
                mean_wait = queue_count * 0.5
                arrival_rate = float(len(dets)) * 2.0

            # Default downstream eligibility is True
            downstream_avail = True

            # Check if any feeding downstream exit is blocked
            for link_name, stat in downstream_status.items():
                if stat["is_blocked"] and app_name in stat["feeding_approaches"]:
                    downstream_avail = False
                    logger.warning(
                        f"Downstream link '{link_name}' saturated (occ={stat['occupancy']:.1%}); "
                        f"gating upstream approach '{app_name}' (downstream_available=False)"
                    )
                    break

            approaches[app_name] = ApproachState(
                queue_count=queue_count,
                mean_wait_seconds=mean_wait,
                arrival_rate=arrival_rate,
                downstream_available=downstream_avail,
                measurement_valid=True,
            )

        traffic_state = TrafficState(
            timestamp=timestamp,
            approaches=approaches,
            all_valid=True,
        )

        return traffic_state, detections, downstream_status

    def annotate_frame(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        roi_config: Optional[ROIConfig] = None,
        downstream_status: Optional[Dict[str, Any]] = None,
        active_phase_name: Optional[str] = None,
        spillback_override_active: bool = False,
        show_rois: bool = False,
    ) -> np.ndarray:
        """Annotate frame with pure, crisp vehicle detections and a sleek telemetry HUD.

        No giant tarp/polygon overlays by default. Clean, judge-ready display.
        """
        vis = frame.copy()
        h, w = vis.shape[:2]

        # 1. Category counters for live HUD
        SHORT_NAMES = {
            "two-wheeler": "2W", "bicycle": "Bike", "three-wheeler": "Auto",
            "hatchback": "Car", "sedan": "Car", "suv": "SUV", "muv": "MUV",
            "van": "Van", "lcv": "LCV", "tempo-traveller": "Tempo",
            "mini-bus": "MiniBus", "bus": "Bus", "truck": "Truck", "others": "Veh"
        }

        bikes = 0
        autos = 0
        cars = 0
        buses = 0
        tot_pcu = 0.0

        for det in detections:
            c = det.get("class_name", "Vehicle").lower()
            pcu = det.get("pcu_weight", 1.0)
            tot_pcu += pcu
            if c in ["two-wheeler", "bicycle"]:
                bikes += 1
            elif c in ["three-wheeler"]:
                autos += 1
            elif c in ["bus", "mini-bus", "truck", "lcv", "tempo-traveller"]:
                buses += 1
            else:
                cars += 1

        # 2. Draw crisp bounding boxes with clean pill labels
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            cls_raw = det.get("class_name", "Vehicle").lower()
            pcu = det.get("pcu_weight", 1.0)
            tid = det.get("track_id")

            color = CLASS_COLORS.get(cls_raw, (246, 130, 59))

            # Crisp high-contrast bounding box
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

            # Label pill
            short_cls = SHORT_NAMES.get(cls_raw, cls_raw.capitalize())
            label = f"{short_cls}: {pcu:.1f}"
            if tid is not None:
                label = f"#{tid} {label}"

            font_scale = 0.50
            thickness = 2
            t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
            pill_y1 = max(0, y1 - t_size[1] - 8)
            pill_y2 = y1
            pill_x2 = min(w, x1 + t_size[0] + 10)

            # Solid dark background pill with colored border
            cv2.rectangle(vis, (x1, pill_y1), (pill_x2, pill_y2), (10, 14, 20), -1)
            cv2.rectangle(vis, (x1, pill_y1), (pill_x2, pill_y2), color, 1)
            # High-contrast white text
            cv2.putText(
                vis, label, (x1 + 4, pill_y2 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA
            )

        # 3. Sleek Translucent Telemetry HUD Bar at the top of the video
        hud_h = 36
        overlay = vis.copy()
        cv2.rectangle(overlay, (0, 0), (w, hud_h), (8, 12, 18), -1)
        cv2.addWeighted(overlay, 0.85, vis, 0.15, 0, vis)
        cv2.line(vis, (0, hud_h), (w, hud_h), (40, 55, 75), 1)

        hud_text = f"Bikes: {bikes} | Autos: {autos} | Cars: {cars} | Buses: {buses} | Total Load: {tot_pcu:.1f} PCU"
        cv2.putText(
            vis, hud_text, (14, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 240, 255), 2, cv2.LINE_AA
        )

        return vis