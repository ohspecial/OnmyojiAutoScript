"""ByteTrack — multi-object tracker with two-pass association.

Implements the ByteTrack algorithm:
1. High-confidence detections are matched to existing tracks via IoU + Hungarian.
2. Unmatched tracks are then matched against low-confidence detections.
3. Unmatched high-conf detections spawn new tracks.
4. Lost tracks are kept in a buffer for re-association.

Each track has a locked class assignment — if a detection's class differs
from the track's class, it spawns a new track instead of updating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment


@dataclass
class Track:
    """A single tracked object."""

    track_id: int
    class_id: int
    bbox: np.ndarray  # [x1, y1, x2, y2]
    confidence: float
    cx: float = 0.0
    cy: float = 0.0
    w: float = 0.0
    h: float = 0.0
    v: float = 0.0  # horizontal velocity (cx delta per frame)
    frames_since_seen: int = 0
    _prev_cx: Optional[float] = field(default=None, repr=False)

    def update(self, bbox: np.ndarray, confidence: float, class_id: int) -> None:
        """Update track state with a new detection."""
        self.bbox = bbox
        self.confidence = confidence
        x1, y1, x2, y2 = bbox
        new_cx = (x1 + x2) / 2
        new_cy = (y1 + y2) / 2
        self.w = x2 - x1
        self.h = y2 - y1

        # Compute velocity as delta from previous cx
        if self._prev_cx is not None:
            self.v = new_cx - self._prev_cx
        else:
            self.v = 0.0

        self._prev_cx = new_cx
        self.cx = new_cx
        self.cy = new_cy
        self.frames_since_seen = 0

    def mark_lost(self) -> None:
        """Mark track as lost for this frame."""
        self.frames_since_seen += 1


def _iou_batch(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """Compute IoU between two sets of boxes.

    Parameters:
        boxes_a: (M, 4) in [x1, y1, x2, y2]
        boxes_b: (N, 4) in [x1, y1, x2, y2]

    Returns:
        IoU matrix (M, N).
    """
    if len(boxes_a) == 0 or len(boxes_b) == 0:
        return np.empty((len(boxes_a), len(boxes_b)), dtype=np.float32)

    x1 = np.maximum(boxes_a[:, 0:1], boxes_b[:, 0:1].T)
    y1 = np.maximum(boxes_a[:, 1:2], boxes_b[:, 1:2].T)
    x2 = np.minimum(boxes_a[:, 2:3], boxes_b[:, 2:3].T)
    y2 = np.minimum(boxes_a[:, 3:4], boxes_b[:, 3:4].T)

    inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    area_a = (boxes_a[:, 2] - boxes_a[:, 0]) * (boxes_a[:, 3] - boxes_a[:, 1])
    area_b = (boxes_b[:, 2] - boxes_b[:, 0]) * (boxes_b[:, 3] - boxes_b[:, 1])
    union = area_a[:, None] + area_b[None, :] - inter

    return inter / np.maximum(union, 1e-6)


class ByteTrack:
    """ByteTrack multi-object tracker.

    Parameters:
        high_thresh: Confidence threshold for high-confidence detections.
        low_thresh: Confidence threshold for low-confidence detections.
        match_thresh: IoU threshold for matching (cost = 1 - IoU).
        track_buffer: Number of frames to keep lost tracks before removal.
    """

    def __init__(
        self,
        high_thresh: float = 0.6,
        low_thresh: float = 0.1,
        match_thresh: float = 0.3,
        track_buffer: int = 30,
    ) -> None:
        self.high_thresh = high_thresh
        self.low_thresh = low_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer

        self._tracks: list[Track] = []
        self._lost_tracks: list[Track] = []
        self._next_id: int = 1

    def reset(self) -> None:
        """Clear all tracks and reset id counter."""
        self._tracks = []
        self._lost_tracks = []
        self._next_id = 1

    def update(self, detections: np.ndarray) -> list[tuple]:
        """Process one frame of detections and return active tracks.

        Parameters:
            detections: (N, 6) array of [x1, y1, x2, y2, conf, class_id].
                Empty array is handled gracefully.

        Returns:
            List of 8-tuples: (track_id, class_id, conf, cx, cy, w, h, v)
            for all currently active (visible) tracks.
        """
        if detections.size == 0:
            # Mark all tracks as lost
            for track in self._tracks:
                track.mark_lost()
            self._lost_tracks.extend(self._tracks)
            self._tracks = []
            self._prune_lost()
            return []

        # Split into high and low confidence
        confs = detections[:, 4]
        high_mask = confs >= self.high_thresh
        low_mask = (confs >= self.low_thresh) & (~high_mask)

        high_dets = detections[high_mask]
        low_dets = detections[low_mask]

        # --- First pass: match high-conf detections to active tracks ---
        active_tracks = self._tracks + self._lost_tracks
        matched_track_indices, matched_det_indices, unmatched_tracks, unmatched_dets = (
            self._match(active_tracks, high_dets)
        )

        # Update matched tracks
        new_active: list[Track] = []
        for t_idx, d_idx in zip(matched_track_indices, matched_det_indices):
            track = active_tracks[t_idx]
            det = high_dets[d_idx]
            # Class lock: only update if class matches
            det_class = int(det[5])
            if det_class == track.class_id:
                track.update(det[:4], det[4], det_class)
                new_active.append(track)
            else:
                # Class mismatch — treat detection as unmatched, track as lost
                unmatched_dets.append(d_idx)
                unmatched_tracks.append(t_idx)

        # --- Second pass: match remaining tracks with low-conf detections ---
        remaining_tracks = [active_tracks[i] for i in unmatched_tracks]
        if len(remaining_tracks) > 0 and len(low_dets) > 0:
            mt2, md2, still_unmatched_tracks, _ = self._match(remaining_tracks, low_dets)
            for t_idx, d_idx in zip(mt2, md2):
                track = remaining_tracks[t_idx]
                det = low_dets[d_idx]
                det_class = int(det[5])
                if det_class == track.class_id:
                    track.update(det[:4], det[4], det_class)
                    new_active.append(track)
                else:
                    still_unmatched_tracks.append(t_idx)
            lost_tracks = [remaining_tracks[i] for i in still_unmatched_tracks]
        else:
            lost_tracks = remaining_tracks

        # Mark unmatched tracks as lost
        for track in lost_tracks:
            track.mark_lost()

        # --- Spawn new tracks for unmatched high-conf detections ---
        for d_idx in unmatched_dets:
            det = high_dets[d_idx]
            track = self._create_track(det)
            new_active.append(track)

        self._tracks = new_active
        self._lost_tracks = lost_tracks
        self._prune_lost()

        # Return active tracks as 8-tuples
        return [
            (t.track_id, t.class_id, t.confidence, t.cx, t.cy, t.w, t.h, t.v)
            for t in self._tracks
        ]

    def _match(
        self,
        tracks: list[Track],
        detections: np.ndarray,
    ) -> tuple[list[int], list[int], list[int], list[int]]:
        """Match tracks to detections using IoU + Hungarian algorithm.

        Returns:
            (matched_track_indices, matched_det_indices,
             unmatched_track_indices, unmatched_det_indices)
        """
        if len(tracks) == 0 or len(detections) == 0:
            return [], [], list(range(len(tracks))), list(range(len(detections)))

        track_boxes = np.array([t.bbox for t in tracks])
        det_boxes = detections[:, :4]

        iou_matrix = _iou_batch(track_boxes, det_boxes)
        cost_matrix = 1.0 - iou_matrix

        # Hungarian assignment
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        matched_tracks: list[int] = []
        matched_dets: list[int] = []
        unmatched_tracks = list(range(len(tracks)))
        unmatched_dets = list(range(len(detections)))

        for r, c in zip(row_indices, col_indices):
            if iou_matrix[r, c] >= self.match_thresh:
                matched_tracks.append(r)
                matched_dets.append(c)
                if r in unmatched_tracks:
                    unmatched_tracks.remove(r)
                if c in unmatched_dets:
                    unmatched_dets.remove(c)

        return matched_tracks, matched_dets, unmatched_tracks, unmatched_dets

    def _create_track(self, detection: np.ndarray) -> Track:
        """Create a new track from a detection."""
        x1, y1, x2, y2, conf, cls = detection
        track = Track(
            track_id=self._next_id,
            class_id=int(cls),
            bbox=detection[:4].copy(),
            confidence=conf,
            cx=(x1 + x2) / 2,
            cy=(y1 + y2) / 2,
            w=x2 - x1,
            h=y2 - y1,
            v=0.0,
        )
        self._next_id += 1
        return track

    def _prune_lost(self) -> None:
        """Remove lost tracks that exceed the track buffer."""
        self._lost_tracks = [
            t for t in self._lost_tracks
            if t.frames_since_seen <= self.track_buffer
        ]
