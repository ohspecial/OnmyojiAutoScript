"""Per-class Non-Maximum Suppression (NMS) for Hyakkiyakou detection.

Implements greedy per-class NMS: within each class, boxes are sorted by
confidence and greedily kept if their IoU with all previously kept boxes
of the same class is below the threshold.

Cross-class boxes are never suppressed against each other.
"""

from __future__ import annotations

import numpy as np


def _iou_matrix(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """Compute IoU between two sets of boxes in (x1, y1, x2, y2) format.

    Parameters:
        boxes_a: shape (M, 4)
        boxes_b: shape (N, 4)

    Returns:
        IoU matrix of shape (M, N).
    """
    x1 = np.maximum(boxes_a[:, 0:1], boxes_b[:, 0:1].T)
    y1 = np.maximum(boxes_a[:, 1:2], boxes_b[:, 1:2].T)
    x2 = np.minimum(boxes_a[:, 2:3], boxes_b[:, 2:3].T)
    y2 = np.minimum(boxes_a[:, 3:4], boxes_b[:, 3:4].T)

    inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

    area_a = (boxes_a[:, 2] - boxes_a[:, 0]) * (boxes_a[:, 3] - boxes_a[:, 1])
    area_b = (boxes_b[:, 2] - boxes_b[:, 0]) * (boxes_b[:, 3] - boxes_b[:, 1])

    union = area_a[:, None] + area_b[None, :] - inter
    return inter / np.maximum(union, 1e-6)


def per_class_nms(
    detections: np.ndarray,
    iou_threshold: float = 0.5,
) -> np.ndarray:
    """Greedy per-class Non-Maximum Suppression.

    Parameters:
        detections: Array of shape (N, 6) where each row is
            ``[x1, y1, x2, y2, confidence, class_id]``.
            The input array is NOT mutated.
        iou_threshold: IoU threshold above which a lower-confidence box
            of the same class is suppressed.

    Returns:
        Filtered detections of shape (K, 6) where K <= N.
        Returns shape (0, 6) if input is empty.
    """
    if detections.size == 0:
        return np.empty((0, 6), dtype=np.float32)

    # Work on a copy to avoid mutating input
    dets = detections.copy()

    # Get unique classes
    classes = np.unique(dets[:, 5].astype(int))

    keep_indices: list[int] = []

    for cls in classes:
        cls_mask = dets[:, 5].astype(int) == cls
        cls_indices = np.where(cls_mask)[0]
        cls_dets = dets[cls_indices]

        # Sort by confidence descending
        order = cls_dets[:, 4].argsort()[::-1]
        cls_indices = cls_indices[order]
        cls_dets = cls_dets[order]

        suppressed = np.zeros(len(cls_dets), dtype=bool)

        for i in range(len(cls_dets)):
            if suppressed[i]:
                continue
            keep_indices.append(cls_indices[i])

            # Compute IoU with remaining boxes
            if i + 1 < len(cls_dets):
                remaining_mask = ~suppressed[i + 1:]
                if remaining_mask.any():
                    remaining_indices = np.where(remaining_mask)[0] + i + 1
                    ious = _iou_matrix(
                        cls_dets[i:i+1, :4],
                        cls_dets[remaining_indices, :4],
                    )[0]
                    # Suppress boxes with IoU above threshold
                    suppress_mask = ious >= iou_threshold
                    suppressed[remaining_indices[suppress_mask]] = True

    if not keep_indices:
        return np.empty((0, 6), dtype=np.float32)

    return dets[sorted(keep_indices)]
