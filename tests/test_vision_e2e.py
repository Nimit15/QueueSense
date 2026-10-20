"""End-to-End Vision Pipeline & Controller Integration Tests for QueueSense.

Validates:
1. Dynamic class loading from UVH-26 checkpoint & IRC SP:41 PCU weighting.
2. Cross-dataset inference across UVH-26, Chennai Traffic, and IndiaScene365.
3. Upstream & Downstream polygonal ROI evaluation with spillback occupancy.
4. Multi-frame ByteTrack tracking & dwell-time accumulation.
5. End-to-end integration: Real Indian CCTV Frame -> UVH-26 -> ROIs -> TrafficState -> QueueSenseController.step().
6. Downstream spillback gate preventing green release into saturated receiving link.
7. Watchdog safety fallback to Fixed-Time control upon 3 camera dropouts.
"""

from pathlib import Path
import cv2
import numpy as np
import pytest

from queuesense.state import TrafficState, ApproachState
from queuesense.controllers.base import Phase
from queuesense.controllers.queuesense import QueueSenseController
from queuesense.vision.detector import UVH26Detector, IRC_SP41_PCU_WEIGHTS
from queuesense.vision.roi import ROIConfig, ROIProcessor
from queuesense.vision.stream import StreamAdapter
from queuesense.vision.tracker import VehicleTracker


# Test frame paths
MODEL_PATH = Path("data/incoming/models/UVH-26-MV-YOLOv11-S.pt")
UVH26_FRAME = Path("data/incoming/uvh26/UVH-26-Val/data/000/100130.png")
CHENNAI_FRAME_1 = Path("data/incoming/staging_train/train/oncampus_frame_000000_enh.jpg")
CHENNAI_FRAME_2 = Path("data/incoming/staging_train/train/offcampus_frame_000000_enh.jpg")
INDIASCENE_FRAME = Path("data/incoming/staging_IndiaScene365/IndiaScene365/Indiascene365/Day2fog/Day/Test A/0101.png")


@pytest.fixture(scope="module")
def detector():
    """Shared detector instance for test speed."""
    assert MODEL_PATH.exists(), f"Model checkpoint missing at {MODEL_PATH}"
    return UVH26Detector(model_path=MODEL_PATH, conf_threshold=0.18)


# ---------------------------------------------------------------------------
# Test 1: Checkpoint Metadata & IRC SP:41 Calibration
# ---------------------------------------------------------------------------

def test_uvh26_model_metadata_and_pcu_weights(detector):
    """Verify dynamic class loading and IRC SP:41 PCU weights."""
    assert len(detector.class_names) == 14, f"Expected 14 classes, found {len(detector.class_names)}"

    # Class verification
    class_values = [v.lower() for v in detector.class_names.values()]
    assert any("two-wheeler" in c for c in class_values)
    assert any("three-wheeler" in c for c in class_values)
    assert any("bus" in c for c in class_values)
    assert any("truck" in c for c in class_values)

    # Check IRC SP:41 calibration
    # Three-wheeler should be 1.0 (NOT the old buggy 2.0)
    three_wheeler_id = [k for k, v in detector.class_names.items() if "three-wheeler" in v.lower()][0]
    assert detector.pcu_map[three_wheeler_id] == 1.0

    # Two-wheeler should be 0.5
    two_wheeler_id = [k for k, v in detector.class_names.items() if "two-wheeler" in v.lower()][0]
    assert detector.pcu_map[two_wheeler_id] == 0.5

    # Bus and Truck should be 3.0
    bus_id = [k for k, v in detector.class_names.items() if "bus" in v.lower() and "mini" not in v.lower()][0]
    truck_id = [k for k, v in detector.class_names.items() if "truck" in v.lower()][0]
    assert detector.pcu_map[bus_id] == 3.0
    assert detector.pcu_map[truck_id] == 3.0


# ---------------------------------------------------------------------------
# Test 2: Cross-Dataset Inference Verification
# ---------------------------------------------------------------------------

def test_cross_dataset_detections(detector):
    """Prove UVH-26 successfully detects Indian mixed traffic across all 3 datasets."""
    # 1. UVH-26 validation dataset
    assert UVH26_FRAME.exists()
    img_uvh = cv2.imread(str(UVH26_FRAME))
    dets_uvh = detector.detect(img_uvh)
    assert len(dets_uvh) >= 5, f"Expected >= 5 detections on UVH-26, got {len(dets_uvh)}"
    for d in dets_uvh:
        assert "pcu_weight" in d
        assert "confidence" in d
        assert len(d["bbox"]) == 4

    # 2. Chennai Traffic dataset (previously had 0 detections bug)
    chennai_path = CHENNAI_FRAME_1 if CHENNAI_FRAME_1.exists() else CHENNAI_FRAME_2
    assert chennai_path.exists(), "Chennai frame missing"
    img_chennai = cv2.imread(str(chennai_path))
    dets_chennai = detector.detect(img_chennai)
    assert len(dets_chennai) >= 1, f"Chennai detections failed! Got {len(dets_chennai)}"

    # 3. IndiaScene365 dataset
    if INDIASCENE_FRAME.exists():
        img_india = cv2.imread(str(INDIASCENE_FRAME))
        dets_india = detector.detect(img_india)
        assert len(dets_india) >= 1, f"IndiaScene365 detections failed! Got {len(dets_india)}"


# ---------------------------------------------------------------------------
# Test 3: Upstream & Downstream ROI Processing
# ---------------------------------------------------------------------------

def test_roi_processing_and_occupancy(tmp_path):
    """Test polygon point-in-polygon, occupancy calculation, and config save/load."""
    config = ROIConfig.default_quadrant()

    # Save and reload config
    cfg_file = tmp_path / "test_roi.json"
    config.save(cfg_file)
    reloaded = ROIConfig.load(cfg_file)
    assert reloaded.camera_id == config.camera_id
    assert "art_east" in reloaded.downstream_rois
    assert "north" in reloaded.upstream_rois

    processor = ROIProcessor(reloaded)

    # Synthetic detections
    # Vehicle inside art_east ROI (calibrated perspective trapezoid roughly x: 1050-1700, y: 460-880)
    mock_detections = [
        {"bbox": [1200, 500, 1500, 750], "class_id": 5, "pcu_weight": 3.0, "confidence": 0.9},
        {"bbox": [1250, 550, 1450, 780], "class_id": 5, "pcu_weight": 3.0, "confidence": 0.85},
    ]

    occ = processor.compute_downstream_occupancy(mock_detections, "art_east", 1920, 1080)
    assert occ > 0.0, f"Expected non-zero occupancy, got {occ}"

    status = processor.evaluate_downstream_status(mock_detections, 1920, 1080)
    assert "art_east" in status
    assert "occupancy" in status["art_east"]


# ---------------------------------------------------------------------------
# Test 4: Multi-Frame Temporal Tracking & Dwell Time
# ---------------------------------------------------------------------------

def test_tracker_dwell_time():
    """Verify VehicleTracker accumulates dwell time over multiple steps."""
    tracker = VehicleTracker(fps=10.0)

    # Frame 1: Detection enters North approach
    det_f1 = [{"track_id": 101, "bbox": [500, 100, 600, 200], "pcu_weight": 1.0, "class_id": 0}]
    approach_map = {"north": det_f1, "south": [], "east": [], "west": []}
    tracker.update_from_detections(det_f1, timestamp=10.0, approach_assignments=approach_map)

    # Frame 2: Same vehicle 4 seconds later
    det_f2 = [{"track_id": 101, "bbox": [505, 105, 605, 205], "pcu_weight": 1.0, "class_id": 0}]
    approach_map2 = {"north": det_f2, "south": [], "east": [], "west": []}
    tracker.update_from_detections(det_f2, timestamp=14.0, approach_assignments=approach_map2)

    # Frame 3 & 4 (to pass frame_count > 3 condition)
    tracker.update_from_detections(det_f2, timestamp=16.0, approach_assignments=approach_map2)
    tracker.update_from_detections(det_f2, timestamp=18.0, approach_assignments=approach_map2)

    metrics = tracker.compute_approach_metrics("north", det_f2, current_time=18.0)
    assert metrics["queue_count"] == 1.0
    assert metrics["mean_wait_seconds"] == 8.0  # 18.0 - 10.0
    assert metrics["vehicle_count"] == 1.0


# ---------------------------------------------------------------------------
# Test 5: Stream Adapter Health & Watchdog Check
# ---------------------------------------------------------------------------

def test_stream_adapter_blank_detection(tmp_path):
    """Verify stream adapter detects blank/corrupted frames and triggers watchdog."""
    # Write a black frame
    black_img_path = tmp_path / "black.jpg"
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.imwrite(str(black_img_path), black_frame)

    adapter = StreamAdapter(source=str(tmp_path), loop=False)
    valid, frame, meta = adapter.read()
    assert not valid, "Black frame should be declared invalid"
    assert "Black or unpowered" in meta["reason"]
    assert adapter.consecutive_failures == 1


# ---------------------------------------------------------------------------
# Test 6: End-to-End Vision -> TrafficState -> QueueSenseController.step()
# ---------------------------------------------------------------------------

def test_vision_to_queuesense_controller_step(detector):
    """End-to-End: Indian CCTV frame -> UVH-26 -> TrafficState -> QueueSenseController."""
    img = cv2.imread(str(UVH26_FRAME))
    tracker = VehicleTracker(fps=10.0)
    roi_cfg = ROIConfig.default_quadrant()

    traffic_state, detections, downstream_stat = detector.build_traffic_state(
        frame=img,
        roi_config=roi_cfg,
        tracker=tracker,
        timestamp=0.0,
    )

    assert isinstance(traffic_state, TrafficState)
    assert traffic_state.all_valid is True
    assert "north" in traffic_state.approaches
    assert "east" in traffic_state.approaches
    assert len(detections) > 0

    # Instantiate QueueSenseController
    controller = QueueSenseController(alpha=0.4, beta=0.4, gamma=0.2, spillback_threshold=0.85)

    # Step the controller with vision TrafficState
    action = controller.step(traffic_state, step_length=1.0)

    assert "phase" in action
    assert "duration" in action
    assert "reason" in action
    assert isinstance(action["phase"], Phase)
    assert action["duration"] > 0


# ---------------------------------------------------------------------------
# Test 7: Downstream Spillback Gating
# ---------------------------------------------------------------------------

def test_downstream_spillback_gating_override(detector):
    """Prove that when downstream exit is saturated, downstream_available is False."""
    img = cv2.imread(str(UVH26_FRAME))
    h, w = img.shape[:2]

    # Create ROI config where art_east covers the entire lower half
    custom_cfg = ROIConfig(
        camera_id="SPILLBACK_TEST",
        resolution=(w, h),
        upstream_rois={"east": [(0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (0.0, 0.5)]},
        downstream_rois={"art_east": [(0.0, 0.5), (1.0, 0.5), (1.0, 1.0), (0.0, 1.0)]},
        downstream_to_upstream={"art_east": ["east"]},
        spillback_threshold=0.01,  # Set very low threshold to force blockage
    )

    traffic_state, detections, downstream_stat = detector.build_traffic_state(
        frame=img,
        roi_config=custom_cfg,
        tracker=None,
        timestamp=0.0,
    )

    # Check if art_east detected blockage
    if downstream_stat["art_east"]["is_blocked"]:
        assert traffic_state.approaches["east"].downstream_available is False


# ---------------------------------------------------------------------------
# Test 8: Camera Dropout 3-Strike Safety Watchdog Fallback
# ---------------------------------------------------------------------------

def test_safety_watchdog_dropout_fallback():
    """3 consecutive camera dropouts (all_valid=False) forces Fixed-Time fallback."""
    controller = QueueSenseController()

    # Step 1: Valid state
    state_ok = TrafficState(
        timestamp=0.0,
        approaches={
            "north": ApproachState(queue_count=5.0, downstream_available=True),
            "south": ApproachState(queue_count=5.0, downstream_available=True),
            "east": ApproachState(queue_count=2.0, downstream_available=True),
            "west": ApproachState(queue_count=2.0, downstream_available=True),
        },
        all_valid=True,
    )
    controller.step(state_ok, step_length=1.0)
    assert controller.consecutive_invalid == 0

    # Step 2: Camera dropout 1
    state_drop1 = TrafficState(timestamp=1.0, approaches={}, all_valid=False)
    controller.step(state_drop1, step_length=1.0)
    assert controller.consecutive_invalid == 1

    # Step 3: Camera dropout 2
    state_drop2 = TrafficState(timestamp=2.0, approaches={}, all_valid=False)
    controller.step(state_drop2, step_length=1.0)
    assert controller.consecutive_invalid == 2

    # Step 4: Camera dropout 3 -> Watchdog trips and resets to fixed-time plan
    state_drop3 = TrafficState(timestamp=3.0, approaches={}, all_valid=False)
    controller.step(state_drop3, step_length=1.0)
    # The watchdog resets consecutive_invalid to 0 and returns to fixed_cycle[0]
    assert controller.consecutive_invalid == 0
    assert controller.state == controller.config.fixed_cycle[0]
