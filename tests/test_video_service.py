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

    def test_identical_images_no_bar(self, svc):
        img = make_solid_image(800, 600, (100, 100, 100))
        result, bar_x, bar_width = svc.merge_frames(img.copy(), img.copy())
        assert bar_x == 0
        assert bar_width == 0

    def test_identical_images_merge_x_zero(self, svc):
        img = make_solid_image(800, 600, (100, 100, 100))
        result, merge_x_unused, bar_width = svc.merge_frames(img.copy(), img.copy())
        h, w = img.shape[:2]
        result2, bar_x, bar_width2 = svc.merge_frames(img.copy(), img.copy())
        assert bar_x == 0

    def test_bar_detected_in_frame_b(self, svc):
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        result, bar_x, bar_width = svc.merge_frames(frame_a, frame_b)
        assert bar_x > 0, "bar_x should be > 0 when a bar is detected"

    def test_merge_x_respects_bar_padding_positive(self, svc):
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        _, bar_x_pos, _ = svc.merge_frames(frame_a, frame_b, bar_padding_px=15)
        _, bar_x_neg, _ = svc.merge_frames(frame_a, frame_b, bar_padding_px=-15)
        assert bar_x_pos >= bar_x_neg, "Positive padding should shift merge_x further right"

    def test_overlay_width_ratio_limits_search(self, svc):
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        _, bar_x_narrow, _ = svc.merge_frames(frame_a, frame_b, overlay_width_ratio=0.3)
        _, bar_x_wide, _ = svc.merge_frames(frame_a, frame_b, overlay_width_ratio=0.8)
        assert bar_x_wide >= bar_x_narrow, "Wider ratio should find bar at same or larger x"

    def test_high_min_diff_threshold_no_bar(self, svc):
        frame_a = make_solid_image(800, 600, (200, 200, 200))
        frame_b = make_bar_image(800, 600, bar_left=100, bar_right=400)
        result, bar_x, bar_width = svc.merge_frames(
            frame_a, frame_b, min_diff_threshold=999999.0
        )
        assert bar_x == 0
        assert bar_width == 0

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
        result, _, _ = svc.merge_frames(frame_a, frame_b)
        assert result.shape == frame_a.shape

    def test_no_bar_identical_merges_same_pixels(self, svc):
        img = make_solid_image(800, 600, (100, 100, 100))
        result, _, _ = svc.merge_frames(img.copy(), img.copy())
        np.testing.assert_array_equal(result, img)

    def test_bar_detected_merges_portion_of_frame_b(self, svc):
        bg = (200, 200, 200)
        frame_a = make_solid_image(800, 600, bg)
        frame_b = make_solid_image(800, 600, bg)
        bar_top = int(600 * 0.15)
        bar_bottom = bar_top + 18
        frame_b[bar_top:bar_bottom, 100:400] = (255, 50, 50)
        result, bar_x, bar_width = svc.merge_frames(frame_a, frame_b, bar_padding_px=0)
        assert bar_x > 0, "bar_x should be positive when bar exists"

    def test_different_image_sizes(self, svc):
        frame_a = make_solid_image(1024, 768, (100, 100, 100))
        frame_b = make_bar_image(1024, 768, bar_left=200, bar_right=600)
        result, bar_x, bar_width = svc.merge_frames(frame_a, frame_b)
        assert result.shape == frame_a.shape
