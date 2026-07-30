"""Unit tests for src/infrastructure/video_service.py — VideoService class."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from tests.conftest import make_bar_image, make_solid_image
from src.infrastructure.video_service import VideoService


pytestmark = pytest.mark.unit


class TestMergeFrames:
    """Tests for VideoService.merge_frames()."""

    @pytest.fixture
    def svc(self):
        return VideoService()

    def test_identical_images_no_merge(self, svc):
        img = make_solid_image(800, 600, (100, 100, 100))
        mr = svc.merge_frames(img.copy(), img.copy())
        assert mr.merge_x == 0

    def test_identical_images_unchanged(self, svc):
        img = make_solid_image(800, 600, (100, 100, 100))
        mr = svc.merge_frames(img.copy(), img.copy())
        np.testing.assert_array_equal(mr.merged, img)

    def _make_two_spike_pair(self, w=800, h=600, gap_start=200, gap_end=300):
        """Create (frame_a, frame_b) where two separate diff spikes appear
        at gap_start and gap_end (before 640px scaling)."""
        bg = (200, 200, 200)
        frame_a = make_solid_image(w, h, bg)
        frame_b = make_solid_image(w, h, bg)
        stripe_top = int(h * 0.15)
        stripe_h = 30
        # Left stripe — produces first spike
        frame_b[stripe_top:stripe_top + stripe_h, gap_start - 30:gap_start] = (255, 50, 50)
        # Right stripe — produces second spike
        frame_b[stripe_top:stripe_top + stripe_h, gap_end:gap_end + 30] = (255, 50, 50)
        return frame_a, frame_b

    def test_two_spikes_sets_merge_x(self, svc):
        frame_a, frame_b = self._make_two_spike_pair()
        mr = svc.merge_frames(frame_a, frame_b)
        assert len(mr.spikes) == 2, f"Expected 2 spikes, got {len(mr.spikes)}"
        assert mr.merge_x > 0, "merge_x should be > 0 when 2 spikes detected"

    def test_merge_x_at_midpoint(self, svc):
        frame_a, frame_b = self._make_two_spike_pair()
        mr = svc.merge_frames(frame_a, frame_b)
        assert len(mr.spikes) == 2, f"Expected 2 spikes, got {len(mr.spikes)}"
        sorted_s = sorted(mr.spikes, key=lambda p: p[0])
        expected_mid_640 = (sorted_s[0][0] + sorted_s[1][0]) // 2
        expected_mid_full = int(expected_mid_640 * (frame_a.shape[1] / 640))
        assert abs(mr.merge_x - expected_mid_full) < 3, (
            f"merge_x {mr.merge_x} ≈ expected {expected_mid_full}"
        )

    def test_full_profile_used_regardless_of_overlay_ratio(self, svc):
        """Spike detection uses the full 640-column profile regardless of overlay_width_ratio."""
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        mr_narrow = svc.merge_frames(frame_a, frame_b, overlay_width_ratio=0.2)
        mr_wide = svc.merge_frames(frame_a, frame_b, overlay_width_ratio=0.8)
        assert len(mr_narrow.col_sums) == 640
        assert len(mr_wide.col_sums) == 640

    def test_no_spikes_with_very_small_images(self, svc):
        img = make_solid_image(32, 32, (100, 100, 100))
        mr = svc.merge_frames(img.copy(), img.copy())
        assert mr.merge_x == 0

    def test_debug_save_path_creates_file(self, svc, tmp_path):
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        debug_file = str(tmp_path / "debug_sum.txt")
        svc.merge_frames(frame_a, frame_b, debug_save_path=debug_file)
        assert os.path.exists(debug_file)
        assert os.path.getsize(debug_file) > 0

    def test_output_dimensions_match_input(self, svc):
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        mr = svc.merge_frames(frame_a, frame_b)
        assert mr.merged.shape == frame_a.shape

    def test_merge_result_contains_col_sums_and_spikes(self, svc):
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        mr = svc.merge_frames(frame_a, frame_b)
        assert len(mr.col_sums) == 640
        assert isinstance(mr.spikes, list)

    def test_different_image_sizes(self, svc):
        frame_a = make_solid_image(1024, 768, (100, 100, 100))
        frame_b = make_bar_image(1024, 768, bar_left=200, bar_right=600)
        mr = svc.merge_frames(frame_a, frame_b)
        assert mr.merged.shape == frame_a.shape
