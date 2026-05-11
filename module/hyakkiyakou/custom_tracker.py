"""Custom Tracker — drop-in replacement for the legacy oashya.tracker.Tracker.

Composes OnnxDetector + per_class_nms + ByteTrack into a single callable
that matches the legacy call signature:
    tracker = Tracker(args)
    tracks = tracker(image=img, response=last_action)
    tracker.clear_tracks()

Attributes:
    detect_time: timedelta of last detection pass.
    track_time: timedelta of last tracking pass.
"""

from __future__ import annotations

import logging
import hashlib
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np

from module.exception import RequestHumanTakeover
from module.hyakkiyakou.bytetrack import ByteTrack
from module.hyakkiyakou.detector import OnnxDetector
from module.hyakkiyakou.nms import per_class_nms

_logger = logging.getLogger(__name__)

# Default model search paths
_MODEL_SEARCH_PATHS = [
    Path("./models/hya_current.onnx"),
    Path("./bin/oashya_fp32.onnx"),
]


def _find_model() -> Path:
    """Find the ONNX model file."""
    for p in _MODEL_SEARCH_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"No ONNX model found. Searched: {[str(p) for p in _MODEL_SEARCH_PATHS]}"
    )


def _verify_sha256(model_path: Path) -> None:
    """Verify SHA256 checksum if .sha256 sibling exists."""
    sha_path = model_path.with_suffix(model_path.suffix + ".sha256")
    if not sha_path.exists():
        _logger.warning(f"No SHA256 file found for {model_path.name}, skipping verification")
        return

    expected_hash = sha_path.read_text(encoding="utf-8").strip().lower()
    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest().lower()

    if actual_hash != expected_hash:
        raise RequestHumanTakeover(
            f"SHA256 mismatch for {model_path.name}: "
            f"expected {expected_hash[:16]}..., got {actual_hash[:16]}..."
        )


class Tracker:
    """Custom tracker matching the legacy oashya.tracker.Tracker interface.

    Parameters:
        args: Configuration dict with keys:
            - conf_threshold (float): Detection confidence threshold.
            - iou_threshold (float): NMS IoU threshold.
            - inference_engine (str): Must be 'onnxruntime'.
            - precision (str): Must be 'fp32'.
            - debug (bool): Enable debug logging.
    """

    def __init__(self, args: dict[str, Any] | None = None) -> None:
        args = args or {}

        conf_threshold = args.get("conf_threshold", 0.25)
        iou_threshold = args.get("iou_threshold", 0.45)
        inference_engine = args.get("inference_engine", "onnxruntime")
        precision = args.get("precision", "fp32")

        # Validate unsupported configurations
        if inference_engine == "tensorrt":
            raise RequestHumanTakeover("TensorRT is not supported by custom tracker")
        if precision == "int8":
            raise RequestHumanTakeover("INT8 precision is not supported by custom tracker")

        # Find and verify model
        try:
            model_path = _find_model()
        except FileNotFoundError as e:
            raise RequestHumanTakeover(str(e))

        _verify_sha256(model_path)

        # Initialize components
        self._detector = OnnxDetector(
            model_path=model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
        )
        self._nms_threshold = iou_threshold
        self._bytetrack = ByteTrack(
            high_thresh=conf_threshold,
            low_thresh=max(0.1, conf_threshold * 0.4),
            match_thresh=0.3,
            track_buffer=30,
        )

        # Timing
        self.detect_time: timedelta = timedelta(0)
        self.track_time: timedelta = timedelta(0)

        # Warm-up inference
        _logger.info("Custom tracker: performing warm-up inference...")
        dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
        self._detector.infer(dummy)
        _logger.info(f"Custom tracker: ready (model={model_path.name}, "
                     f"num_classes={self._detector.num_classes})")

    @property
    def num_classes(self) -> int:
        """Number of classes the model detects."""
        return self._detector.num_classes

    def __call__(self, image: np.ndarray, response: list) -> list[tuple]:
        """Run detection + tracking on one frame.

        Parameters:
            image: RGB image of shape (H, W, 3), dtype uint8.
            response: Last action [x, y, throw, bean] — used for context
                but not consumed by the tracker itself.

        Returns:
            List of 8-tuples: (track_id, class_id, conf, cx, cy, w, h, v).
        """
        import time

        # Validate input
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"Expected (H, W, 3) image, got shape {image.shape}")
        if image.dtype != np.uint8:
            raise ValueError(f"Expected uint8 image, got dtype {image.dtype}")

        # Detection
        t0 = time.perf_counter()
        raw_dets = self._detector.infer(image)
        t1 = time.perf_counter()
        self.detect_time = timedelta(seconds=t1 - t0)

        # NMS
        if raw_dets.size > 0:
            dets = per_class_nms(raw_dets, iou_threshold=self._nms_threshold)
        else:
            dets = raw_dets

        # Tracking
        t2 = time.perf_counter()
        tracks = self._bytetrack.update(dets)
        t3 = time.perf_counter()
        self.track_time = timedelta(seconds=t3 - t2)

        return tracks

    def clear_tracks(self) -> None:
        """Reset the tracker state (between game rounds)."""
        self._bytetrack.reset()
