"""Unit and property-based tests for module.hyakkiyakou.nms.per_class_nms.

Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5
Property P8: NMS correctness.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from module.hyakkiyakou.nms import per_class_nms


# ===========================================================================
# Unit tests
# ===========================================================================


class TestNmsBasic:
    """Basic unit tests for per_class_nms."""

    def test_empty_input_returns_empty(self):
        """Empty input should return shape (0, 6)."""
        dets = np.empty((0, 6), dtype=np.float32)
        result = per_class_nms(dets, iou_threshold=0.5)
        assert result.shape == (0, 6)

    def test_single_detection_kept(self):
        """A single detection should always be kept."""
        dets = np.array([[10, 10, 50, 50, 0.9, 0]], dtype=np.float32)
        result = per_class_nms(dets, iou_threshold=0.5)
        assert len(result) == 1
        np.testing.assert_array_almost_equal(result[0], dets[0])

    def test_same_class_overlapping_suppressed(self):
        """Two highly overlapping boxes of the same class: lower conf suppressed."""
        dets = np.array([
            [10, 10, 50, 50, 0.9, 0],  # high conf
            [12, 12, 52, 52, 0.7, 0],  # lower conf, high IoU
        ], dtype=np.float32)
        result = per_class_nms(dets, iou_threshold=0.5)
        assert len(result) == 1
        assert result[0, 4] == pytest.approx(0.9, abs=1e-6)  # kept the higher confidence one

    def test_same_class_non_overlapping_both_kept(self):
        """Two non-overlapping boxes of the same class: both kept."""
        dets = np.array([
            [10, 10, 50, 50, 0.9, 0],
            [200, 200, 250, 250, 0.8, 0],
        ], dtype=np.float32)
        result = per_class_nms(dets, iou_threshold=0.5)
        assert len(result) == 2

    def test_cross_class_not_suppressed(self):
        """Overlapping boxes of different classes should NOT be suppressed."""
        dets = np.array([
            [10, 10, 50, 50, 0.9, 0],
            [10, 10, 50, 50, 0.8, 1],  # same box, different class
        ], dtype=np.float32)
        result = per_class_nms(dets, iou_threshold=0.5)
        assert len(result) == 2

    def test_input_not_mutated(self):
        """The input array should not be modified."""
        dets = np.array([
            [10, 10, 50, 50, 0.9, 0],
            [12, 12, 52, 52, 0.7, 0],
        ], dtype=np.float32)
        original = dets.copy()
        per_class_nms(dets, iou_threshold=0.5)
        np.testing.assert_array_equal(dets, original)

    def test_multiple_classes_independent(self):
        """NMS should be applied independently per class."""
        dets = np.array([
            # Class 0: two overlapping
            [10, 10, 50, 50, 0.9, 0],
            [12, 12, 52, 52, 0.7, 0],
            # Class 1: two overlapping
            [100, 100, 150, 150, 0.85, 1],
            [102, 102, 152, 152, 0.6, 1],
        ], dtype=np.float32)
        result = per_class_nms(dets, iou_threshold=0.5)
        # Should keep 1 from each class
        assert len(result) == 2
        classes = set(result[:, 5].astype(int))
        assert classes == {0, 1}

    def test_threshold_boundary(self):
        """Boxes at exactly the IoU threshold should be suppressed."""
        # Create two boxes with known IoU
        # Box1: [0, 0, 100, 100] area=10000
        # Box2: [50, 0, 150, 100] area=10000, intersection=[50,0,100,100]=5000
        # IoU = 5000 / (10000 + 10000 - 5000) = 5000/15000 = 0.333
        dets = np.array([
            [0, 0, 100, 100, 0.9, 0],
            [50, 0, 150, 100, 0.7, 0],
        ], dtype=np.float32)
        # With threshold 0.3, IoU=0.333 > 0.3, should suppress
        result = per_class_nms(dets, iou_threshold=0.3)
        assert len(result) == 1
        # With threshold 0.4, IoU=0.333 < 0.4, should keep both
        result = per_class_nms(dets, iou_threshold=0.4)
        assert len(result) == 2


# ===========================================================================
# Property-based tests (hypothesis)
# ===========================================================================


def _compute_iou(box_a: np.ndarray, box_b: np.ndarray) -> float:
    """Compute IoU between two boxes [x1, y1, x2, y2]."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


@st.composite
def detection_array_st(draw, min_size=0, max_size=20, num_classes=3):
    """Generate a random detection array of shape (N, 6)."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    if n == 0:
        return np.empty((0, 6), dtype=np.float32)

    rows = []
    for _ in range(n):
        x1 = draw(st.floats(min_value=0, max_value=900))
        y1 = draw(st.floats(min_value=0, max_value=600))
        w = draw(st.floats(min_value=10, max_value=200))
        h = draw(st.floats(min_value=10, max_value=200))
        conf = draw(st.floats(min_value=0.1, max_value=1.0))
        cls = draw(st.integers(min_value=0, max_value=num_classes - 1))
        rows.append([x1, y1, x1 + w, y1 + h, conf, cls])

    return np.array(rows, dtype=np.float32)


class TestPropertyP8:
    """Property P8: NMS correctness.

    For all kept pairs of same class, IoU ≤ threshold.
    For all suppressed boxes, a dominating keeper exists.
    """

    @given(dets=detection_array_st(min_size=0, max_size=15))
    @settings(max_examples=200)
    def test_kept_pairs_iou_below_threshold(self, dets: np.ndarray):
        """For all kept pairs of the same class, IoU ≤ threshold."""
        threshold = 0.5
        result = per_class_nms(dets, iou_threshold=threshold)

        if len(result) <= 1:
            return

        # Check all pairs of same class
        for i in range(len(result)):
            for j in range(i + 1, len(result)):
                if int(result[i, 5]) == int(result[j, 5]):
                    iou = _compute_iou(result[i, :4], result[j, :4])
                    assert iou < threshold + 1e-6, (
                        f"Kept pair has IoU={iou:.4f} >= threshold={threshold}"
                    )

    @given(dets=detection_array_st(min_size=1, max_size=15))
    @settings(max_examples=200)
    def test_suppressed_has_dominating_keeper(self, dets: np.ndarray):
        """For all suppressed boxes, a dominating keeper of same class exists."""
        threshold = 0.5
        result = per_class_nms(dets, iou_threshold=threshold)

        if len(result) == len(dets):
            return  # nothing suppressed

        # Find suppressed detections
        kept_set = set()
        for row in result:
            kept_set.add(tuple(row.tolist()))

        for det in dets:
            det_tuple = tuple(det.tolist())
            if det_tuple in kept_set:
                continue
            # This detection was suppressed — find a dominating keeper
            det_class = int(det[5])
            det_conf = det[4]
            found_dominator = False
            for keeper in result:
                if int(keeper[5]) != det_class:
                    continue
                if keeper[4] < det_conf - 1e-6:
                    continue  # keeper must have >= confidence
                iou = _compute_iou(keeper[:4], det[:4])
                if iou >= threshold - 1e-6:
                    found_dominator = True
                    break
            assert found_dominator, (
                f"Suppressed box (conf={det_conf:.3f}, class={det_class}) "
                f"has no dominating keeper"
            )

    @given(dets=detection_array_st(min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_input_not_mutated_property(self, dets: np.ndarray):
        """Input array must never be mutated."""
        original = dets.copy()
        per_class_nms(dets, iou_threshold=0.5)
        np.testing.assert_array_equal(dets, original)
