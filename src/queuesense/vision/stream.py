"""Unified Stream Adapter for QueueSense.

Supports brownfield CCTV deployment:
- RTSP / ONVIF streams from existing city pole cameras (Wi-TraC / CoSiCoSt / ICCC)
- Video files (.mp4, .avi, .mkv) for post-incident analysis
- Directory of image frames (sorted numeric/timestamp order) for offline benchmarking
- Live USB/webcam devices for benchtop demonstration
- Automatic reconnect, frame integrity & blur watchdog
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class StreamAdapter:
    """Unified video and frame stream reader with health verification."""

    def __init__(
        self,
        source: str | Path,
        fps: float = 10.0,
        loop: bool = True,
        reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
    ):
        """Initialize StreamAdapter.

        Args:
            source: Path to directory of images, path to video file, 'rtsp://...', or 'webcam:N'.
            fps: Target playback frame rate for image directories.
            loop: Whether to loop frame directories and video files continuously.
            reconnect_attempts: Max reconnect attempts before declaring hard failure.
            reconnect_delay: Delay between reconnection attempts in seconds.
        """
        if isinstance(source, (list, tuple)):
            self._frame_files = [Path(p) for p in source if Path(p).exists()]
            self.source = f"list:{len(self._frame_files)}_frames"
            self._source_type = "directory"
        else:
            self.source = str(source)
            self._source_type = self._classify_source(self.source)

        self._cap: Optional[cv2.VideoCapture] = None
        if not hasattr(self, "_frame_files"):
            self._frame_files = []
        self._current_idx: int = 0
        self._last_frame_time: float = 0.0

        # Health monitoring
        self.consecutive_failures: int = 0
        self.max_failures_watchdog: int = 3
        self.total_frames_read: int = 0
        self.dropped_frames: int = 0
        self.is_paused: bool = False

        self._init_source()

    def _classify_source(self, src: str) -> str:
        s = src.lower()
        if s.startswith("rtsp://") or s.startswith("http://") or s.startswith("https://"):
            return "rtsp"
        if s.startswith("webcam:") or s.isdigit():
            return "webcam"
        p = Path(src)
        if p.suffix.lower() == ".json":
            return "directory"
        if p.is_dir():
            return "directory"
        if p.is_file():
            ext = p.suffix.lower()
            if ext in [".mp4", ".avi", ".mov", ".mkv"]:
                return "video"
            if ext in [".png", ".jpg", ".jpeg", ".bmp"]:
                return "image"
        return "directory" if not Path(src).suffix else "video"

    def _init_source(self) -> bool:
        """Initialize connection or frame listing."""
        self.consecutive_failures = 0
        if self._source_type == "directory":
            if self._frame_files:
                self._current_idx = 0
                return len(self._frame_files) > 0

            p = Path(self.source)
            if p.suffix.lower() == ".json" and p.exists():
                import json
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        paths = json.load(f)
                    self._frame_files = [Path(x) for x in paths if Path(x).exists()]
                    self._current_idx = 0
                    logger.info(f"Loaded {len(self._frame_files)} frames from JSON manifest: {p}")
                    return len(self._frame_files) > 0
                except Exception as e:
                    logger.error(f"Error loading frame JSON manifest {p}: {e}")

            if not p.exists():
                logger.error(f"Frame directory does not exist: {p}")
                return False

            # Find all images recursively or top-level
            valid_exts = {".png", ".jpg", ".jpeg", ".bmp"}
            # Check top level first
            files = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
            if not files:
                # Search recursively
                files = [f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in valid_exts]

            # Filter out empty scene frames if in UVH-26 dataset (empty scenes are < 1.8MB)
            if "uvh26" in str(p).lower():
                rich = [f for f in files if f.stat().st_size > 1800000]
                if rich:
                    files = rich

            # Natural sort
            self._frame_files = sorted(files, key=lambda x: x.name)
            self._current_idx = 0
            logger.info(f"Loaded {len(self._frame_files)} high-density traffic frames from directory: {self.source}")
            return len(self._frame_files) > 0

        elif self._source_type == "image":
            p = Path(self.source)
            self._frame_files = [p]
            self._current_idx = 0
            return p.exists()

        elif self._source_type == "webcam":
            dev_idx = 0
            if ":" in self.source:
                try:
                    dev_idx = int(self.source.split(":")[-1])
                except ValueError:
                    dev_idx = 0
            elif self.source.isdigit():
                dev_idx = int(self.source)
            self._cap = cv2.VideoCapture(dev_idx)
            return self._cap.isOpened()

        elif self._source_type in ["rtsp", "video"]:
            self._cap = cv2.VideoCapture(self.source)
            if not self._cap.isOpened():
                logger.warning(f"Failed to open video source: {self.source}")
                return False
            return True

        return False

    def is_healthy(self) -> bool:
        """Returns True if the stream is delivering valid frames without watchdog failure."""
        return self.consecutive_failures < self.max_failures_watchdog

    def verify_frame_validity(self, frame: Optional[np.ndarray]) -> Tuple[bool, str]:
        """Examine frame for black-screen, severe blur, or corruption."""
        if frame is None or frame.size == 0:
            return False, "Null or empty frame"
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            return False, "Invalid image dimensions"

        mean_val = float(np.mean(frame))
        if mean_val < 8.0:
            return False, f"Black or unpowered camera frame (mean brightness={mean_val:.1f})"

        # Check for lens blur / occlusion via Laplacian variance
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if lap_var < 20.0 and mean_val > 30.0:
            return False, f"Severe blur or optical occlusion (Laplacian variance={lap_var:.1f})"

        return True, "Valid"

    def read(self) -> Tuple[bool, Optional[np.ndarray], Dict[str, Any]]:
        """Read the next frame from the stream.

        Returns:
            Tuple of (is_valid, frame_bgr, metadata_dict)
        """
        metadata: Dict[str, Any] = {
            "source": self.source,
            "source_type": self._source_type,
            "frame_idx": self._current_idx,
            "timestamp": time.time(),
            "reason": "OK",
        }

        # Handle directory/still image reading
        if self._source_type in ["directory", "image"]:
            if not self._frame_files:
                self.consecutive_failures += 1
                metadata["reason"] = "No frame files found"
                return False, None, metadata

            if self._current_idx >= len(self._frame_files):
                if self.loop:
                    self._current_idx = 0
                else:
                    self.consecutive_failures += 1
                    metadata["reason"] = "End of frame sequence"
                    return False, None, metadata

            frame_path = self._frame_files[self._current_idx]
            frame = cv2.imread(str(frame_path))
            
            # If not paused, advance to next frame; if paused, keep current index
            if not self.is_paused:
                self._current_idx += 1

            self.total_frames_read += 1
            metadata["filename"] = frame_path.name
            metadata["filepath"] = str(frame_path)
            metadata["is_paused"] = self.is_paused

            valid, reason = self.verify_frame_validity(frame)
            if not valid:
                self.consecutive_failures += 1
                self.dropped_frames += 1
                metadata["reason"] = reason
                return False, frame, metadata

            self.consecutive_failures = 0
            return True, frame, metadata

        # Handle video/rtsp/webcam capture
        if self._cap is None or not self._cap.isOpened():
            success = self._attempt_reconnect()
            if not success:
                self.consecutive_failures += 1
                metadata["reason"] = "Capture device unavailable"
                return False, None, metadata

        ret, frame = self._cap.read()
        if not ret or frame is None:
            if self._source_type == "video" and self.loop:
                # Rewind video to start
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()

            if not ret or frame is None:
                self.consecutive_failures += 1
                self.dropped_frames += 1
                metadata["reason"] = "Stream read returned empty frame"
                return False, None, metadata

        self.total_frames_read += 1
        valid, reason = self.verify_frame_validity(frame)
        if not valid:
            self.consecutive_failures += 1
            self.dropped_frames += 1
            metadata["reason"] = reason
            return False, frame, metadata

        self.consecutive_failures = 0
        return True, frame, metadata

    def _attempt_reconnect(self) -> bool:
        """Attempt to re-establish dropped camera connection."""
        logger.warning(f"Attempting to reconnect to {self.source}...")
        for attempt in range(self.reconnect_attempts):
            time.sleep(self.reconnect_delay)
            if self._cap is not None:
                self._cap.release()
            if self._init_source():
                logger.info(f"Successfully reconnected to {self.source} on attempt {attempt + 1}")
                self.consecutive_failures = 0
                return True
        logger.critical(f"Failed to reconnect to {self.source} after {self.reconnect_attempts} attempts.")
        return False

    def toggle_pause(self) -> bool:
        """Toggle play/pause state. Returns True if paused."""
        self.is_paused = not self.is_paused
        return self.is_paused

    def step_next(self) -> None:
        """Step to next frame even when paused."""
        if self._source_type in ["directory", "image"] and self._frame_files:
            self._current_idx = (self._current_idx + 1) % len(self._frame_files)

    def release(self) -> None:
        """Release underlying video capture."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
