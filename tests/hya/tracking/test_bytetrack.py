"""Unit tests for module.hyakkiyakou.bytetrack.ByteTrack.

Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8
"""

from __future__ import annotations

import numpy as np
import pytest

from module.hyakkiyakou.bytetrack import ByteTrack


def _make_det(x1, y1, x2, y2, conf, cls):
    """Helper to create a single detection row."""
    return [x1, y1, x2, y2, conf, cls]


class TestByteTrackIdPersistence:
    """Test that track ids persist across consecutive frames."""

    def test_same_object_keeps_id(self):
        """An object in the same position across frames should keep its id."""
        tracker = ByteTrack(high_thresh=0.5)

        # Frame 1
        dets = np.array([_make_det(100, 100, 150, 150, 0.9, 0)], dtype=np.float32)
        tracks1 = tracker.update(dets)
        assert len(tracks1) == 1
        id1 = tracks1[0][0]

        # Frame 2: same position
        dets = np.array([_make_det(102, 100, 152, 150, 0.85, 0)], dtype=np.float32)
        tracks2 = tracker.update(dets)
        assert len(tracks2) == 1
        assert tracks2[0][0] == id1  # same id

    def test_multiple_objects_keep_ids(self):
        """Multiple objects should each maintain their own id."""
        tracker = ByteTrack(high_thresh=0.5)

        # Frame 1: two objects
        dets = np.array([
            _make_det(100, 100, 150, 150, 0.9, 0),
            _make_det(300, 300, 350, 350, 0.8, 1),
        ], dtype=np.float32)
        tracks1 = tracker.update(dets)
        assert len(tracks1) == 2
        ids1 = {t[0] for t in tracks1}

        # Frame 2: same objects, slightly moved
        dets = np.array([
            _make_det(105, 100, 155, 150, 0.9, 0),
            _make_det(305, 300, 355, 350, 0.8, 1),
        ], dtype=np.float32)
        tracks2 = tracker.update(dets)
        assert len(tracks2) == 2
        ids2 = {t[0] for t in tracks2}
        assert ids1 == ids2  # same ids


class TestByteTrackClassLock:
    """Test that class assignment is locked per track id."""

    def test_class_change_spawns_new_id(self):
        """If a detection's class changes, it should get a new track id."""
        tracker = ByteTrack(high_thresh=0.5, match_thresh=0.3)

        # Frame 1: object with class 0
        dets = np.array([_make_det(100, 100, 150, 150, 0.9, 0)], dtype=np.float32)
        tracks1 = tracker.update(dets)
        id1 = tracks1[0][0]
        class1 = tracks1[0][1]
        assert class1 == 0

        # Frame 2: same position but class 1
        dets = np.array([_make_det(100, 100, 150, 150, 0.9, 1)], dtype=np.float32)
        tracks2 = tracker.update(dets)
        # Should spawn a new track (different class)
        assert len(tracks2) >= 1
        # The new track should have class 1
        new_track = [t for t in tracks2 if t[1] == 1]
        assert len(new_track) == 1
        # It should have a different id
        assert new_track[0][0] != id1


class TestByteTrackEmpty:
    """Test handling of empty detections."""

    def test_empty_detections_returns_empty(self):
        """Empty detections should return empty list."""
        tracker = ByteTrack(high_thresh=0.5)
        dets = np.empty((0, 6), dtype=np.float32)
        tracks = tracker.update(dets)
        assert tracks == []

    def test_tracks_lost_after_empty_frames(self):
        """Tracks should be lost after receiving empty detections."""
        tracker = ByteTrack(high_thresh=0.5, track_buffer=5)

        # Frame 1: one object
        dets = np.array([_make_det(100, 100, 150, 150, 0.9, 0)], dtype=np.float32)
        tracker.update(dets)

        # Frame 2: empty
        tracks = tracker.update(np.empty((0, 6), dtype=np.float32))
        assert tracks == []


class TestByteTrackReset:
    """Test reset() method."""

    def test_reset_clears_all_tracks(self):
        """After reset(), all tracks should be cleared."""
        tracker = ByteTrack(high_thresh=0.5)

        # Add some tracks
        dets = np.array([_make_det(100, 100, 150, 150, 0.9, 0)], dtype=np.float32)
        tracker.update(dets)

        # Reset
        tracker.reset()

        # Next detection should get a new id starting from 1
        dets = np.array([_make_det(100, 100, 150, 150, 0.9, 0)], dtype=np.float32)
        tracks = tracker.update(dets)
        assert len(tracks) == 1
        assert tracks[0][0] == 1  # id reset to 1


class TestByteTrackVelocity:
    """Test velocity computation."""

    def test_velocity_computed_from_cx_delta(self):
        """Velocity should be the horizontal cx delta between frames."""
        tracker = ByteTrack(high_thresh=0.5)

        # Frame 1: object at cx=125
        dets = np.array([_make_det(100, 100, 150, 150, 0.9, 0)], dtype=np.float32)
        tracks1 = tracker.update(dets)
        # First frame: velocity should be 0
        assert tracks1[0][7] == 0.0

        # Frame 2: object moved to cx=135 (delta = 10)
        dets = np.array([_make_det(110, 100, 160, 150, 0.9, 0)], dtype=np.float32)
        tracks2 = tracker.update(dets)
        # Second frame: velocity may still be 0 (first update after creation)

        # Frame 3: object moved to cx=145 (delta = 10)
        dets = np.array([_make_det(120, 100, 170, 150, 0.9, 0)], dtype=np.float32)
        tracks3 = tracker.update(dets)
        # Third frame: velocity should be ~10 (cx delta from frame 2 to frame 3)
        assert abs(tracks3[0][7] - 10.0) < 1e-3


class TestByteTrackIdStability:
    """Test id stability on synthetic sequences."""

    def test_id_swap_rate_low(self):
        """On a simple linear motion sequence, id swap rate should be ≤ 0.05."""
        tracker = ByteTrack(high_thresh=0.5)

        # Simulate two objects moving linearly
        n_frames = 50
        id_history: list[dict[int, int]] = []  # frame -> {class: track_id}

        for frame in range(n_frames):
            obj1_x = 100 + frame * 5
            obj2_x = 500 - frame * 3
            dets = np.array([
                _make_det(obj1_x, 100, obj1_x + 50, 150, 0.9, 0),
                _make_det(obj2_x, 300, obj2_x + 50, 350, 0.85, 1),
            ], dtype=np.float32)
            tracks = tracker.update(dets)

            frame_ids = {}
            for t in tracks:
                frame_ids[t[1]] = t[0]  # class -> track_id
            id_history.append(frame_ids)

        # Count id swaps (id changes for same class between consecutive frames)
        swaps = 0
        total = 0
        for i in range(1, len(id_history)):
            for cls in id_history[i]:
                if cls in id_history[i - 1]:
                    total += 1
                    if id_history[i][cls] != id_history[i - 1][cls]:
                        swaps += 1

        swap_rate = swaps / max(total, 1)
        assert swap_rate <= 0.05, f"Id swap rate {swap_rate:.3f} > 0.05"
