"""OnnxDetector — ONNX Runtime inference wrapper for YOLOv8 detection.

Loads an ONNX model once, caches the session, and provides a simple
``infer(image)`` interface returning detections in original image coordinates.

Provider fall-through: CUDA → DirectML → CPU.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import cv2
import numpy as np

_logger = logging.getLogger(__name__)


class OnnxDetector:
    """ONNX Runtime detector for YOLOv8 models.

    Parameters:
        model_path: Path to the .onnx model file.
        conf_threshold: Minimum confidence to keep a detection.
        iou_threshold: IoU threshold for built-in NMS (if model has NMS).
    """

    def __init__(
        self,
        model_path: Union[str, Path],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> None:
        import onnxruntime as ort

        self._model_path = Path(model_path)
        self._conf_threshold = conf_threshold
        self._iou_threshold = iou_threshold

        # Provider fall-through
        available = ort.get_available_providers()
        providers: list[str] = []
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        if "DmlExecutionProvider" in available:
            providers.append("DmlExecutionProvider")
        providers.append("CPUExecutionProvider")

        self._session = ort.InferenceSession(
            str(self._model_path),
            providers=providers,
        )

        active_provider = self._session.get_providers()[0]
        _logger.info(f"OnnxDetector: loaded {self._model_path.name}, provider={active_provider}")

        # Get model input shape
        input_info = self._session.get_inputs()[0]
        self._input_name = input_info.name
        self._input_shape = input_info.shape  # e.g. [1, 3, 640, 640]
        self._imgsz = (self._input_shape[2], self._input_shape[3])

        # Get number of classes from output shape
        output_info = self._session.get_outputs()[0]
        output_shape = output_info.shape  # e.g. [1, 84, 8400] for YOLOv8
        # YOLOv8 output: [batch, 4+num_classes, num_boxes]
        self._num_classes = output_shape[1] - 4 if len(output_shape) == 3 else 0

    @property
    def num_classes(self) -> int:
        """Number of detection classes the model was trained on."""
        return self._num_classes

    def infer(self, image: np.ndarray) -> np.ndarray:
        """Run inference on an image.

        Parameters:
            image: BGR or RGB image of shape (H, W, 3), dtype uint8.

        Returns:
            Detections array of shape (N, 6) where each row is
            ``[x1, y1, x2, y2, confidence, class_id]`` in original image coords.
            Returns shape (0, 6) if no detections.
        """
        orig_h, orig_w = image.shape[:2]
        img_h, img_w = self._imgsz

        # Preprocess: resize with letterbox
        blob, ratio, (pad_w, pad_h) = self._preprocess(image, img_w, img_h)

        # Run inference
        outputs = self._session.run(None, {self._input_name: blob})
        output = outputs[0]  # shape: [1, 4+nc, num_boxes]

        # Postprocess
        detections = self._postprocess(output, ratio, pad_w, pad_h, orig_w, orig_h)
        return detections

    def _preprocess(
        self, image: np.ndarray, target_w: int, target_h: int
    ) -> tuple[np.ndarray, float, tuple[float, float]]:
        """Letterbox resize and normalize."""
        h, w = image.shape[:2]
        ratio = min(target_w / w, target_h / h)
        new_w, new_h = int(w * ratio), int(h * ratio)

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Pad to target size
        pad_w = (target_w - new_w) / 2
        pad_h = (target_h - new_h) / 2
        top = int(round(pad_h - 0.1))
        bottom = int(round(pad_h + 0.1))
        left = int(round(pad_w - 0.1))
        right = int(round(pad_w + 0.1))

        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right,
            cv2.BORDER_CONSTANT, value=(114, 114, 114),
        )

        # HWC -> CHW, BGR -> RGB, normalize
        blob = padded[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, axis=0)

        return blob, ratio, (pad_w, pad_h)

    def _postprocess(
        self,
        output: np.ndarray,
        ratio: float,
        pad_w: float,
        pad_h: float,
        orig_w: int,
        orig_h: int,
    ) -> np.ndarray:
        """Parse YOLOv8 output and convert to original image coordinates."""
        # output shape: [1, 4+nc, num_boxes] -> transpose to [num_boxes, 4+nc]
        predictions = output[0].T  # (num_boxes, 4+nc)

        # Extract boxes (cx, cy, w, h) and class scores
        boxes_cxcywh = predictions[:, :4]
        class_scores = predictions[:, 4:]

        # Get max class score and class id
        max_scores = class_scores.max(axis=1)
        class_ids = class_scores.argmax(axis=1)

        # Filter by confidence
        mask = max_scores >= self._conf_threshold
        boxes_cxcywh = boxes_cxcywh[mask]
        max_scores = max_scores[mask]
        class_ids = class_ids[mask]

        if len(boxes_cxcywh) == 0:
            return np.empty((0, 6), dtype=np.float32)

        # Convert cx,cy,w,h to x1,y1,x2,y2
        x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
        y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
        x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
        y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

        # Remove padding and rescale to original image
        x1 = (x1 - pad_w) / ratio
        y1 = (y1 - pad_h) / ratio
        x2 = (x2 - pad_w) / ratio
        y2 = (y2 - pad_h) / ratio

        # Clip to image bounds
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        # Stack results
        detections = np.column_stack([x1, y1, x2, y2, max_scores, class_ids])
        return detections.astype(np.float32)
