"""Unit tests for BarProfileService (src/domain/bar_profile_service.py).

Covers compute_column_sums and detect_spikes with various edge cases.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.bar_profile_service import BarProfileService
from tests.conftest import make_bar_image


@pytest.mark.unit
class TestComputeColumnSums:

    def test_returns_array_of_width_640(self):
        a = make_bar_image(800, 600, bar_left=100, bar_right=200)
        b = make_bar_image(800, 600, bar_left=500, bar_right=600)
        result = BarProfileService.compute_column_sums(a, b, analysis_ratio=0.35)
        assert result.shape == (640,)

    def test_identical_images_returns_zeros(self):
        img = make_bar_image(800, 600, bar_left=200, bar_right=400)
        result = BarProfileService.compute_column_sums(img, img, analysis_ratio=0.35)
        assert np.all(result == 0)

    def test_different_images_returns_nonzero(self):
        a = make_bar_image(800, 600, bar_left=50, bar_right=100)
        b = make_bar_image(800, 600, bar_left=700, bar_right=750)
        result = BarProfileService.compute_column_sums(a, b, analysis_ratio=0.35)
        assert np.any(result > 0)

    def test_analysis_ratio_affects_region(self):
        a = np.zeros((600, 800, 3), dtype=np.uint8)
        b = np.zeros((600, 800, 3), dtype=np.uint8)
        # Put a difference only in the top 10% of the image
        b[30:35, 100:200] = 255
        result_small_crop = BarProfileService.compute_column_sums(a, b, analysis_ratio=0.05)
        result_large_crop = BarProfileService.compute_column_sums(a, b, analysis_ratio=0.5)
        # Large crop should see more of the difference
        assert np.sum(result_large_crop) >= np.sum(result_small_crop)

    def test_different_image_sizes_produce_640_output(self):
        for w, h in [(640, 480), (1920, 1080), (320, 240)]:
            a = make_bar_image(w, h, bar_left=10, bar_right=20)
            b = make_bar_image(w, h, bar_left=30, bar_right=40)
            result = BarProfileService.compute_column_sums(a, b, analysis_ratio=0.35)
            assert result.shape == (640,), f"Failed for {w}x{h}"


@pytest.mark.unit
class TestDetectSpikes:

    def test_all_zero_returns_empty(self):
        col_sums = np.zeros(640, dtype=float)
        assert BarProfileService.detect_spikes(col_sums) == []

    def test_below_threshold_returns_empty(self):
        col_sums = np.full(640, 50.0)
        col_sums[320] = 99.0
        assert BarProfileService.detect_spikes(col_sums, min_diff_threshold=100.0) == []

    def test_single_spike_returns_one(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[200] = 5000.0
        spikes = BarProfileService.detect_spikes(col_sums)
        assert len(spikes) == 1
        assert spikes[0][0] == 200

    def test_two_far_apart_spikes_returns_two(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[100] = 5000.0
        col_sums[500] = 4000.0
        spikes = BarProfileService.detect_spikes(col_sums)
        assert len(spikes) == 2

    def test_close_peaks_filtered_to_strongest(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[200] = 5000.0
        col_sums[205] = 4500.0  # within min_dist of 200
        spikes = BarProfileService.detect_spikes(col_sums)
        assert len(spikes) == 1
        assert spikes[0][0] == 200

    def test_close_peaks_keep_taller_peak_on_the_right(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[200] = 4500.0  # shorter left shoulder
        col_sums[205] = 5000.0  # taller peak within min_dist
        spikes = BarProfileService.detect_spikes(col_sums)
        assert spikes == [(205, 5000.0)]

    def test_close_peaks_keep_taller_peak_on_the_left(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[200] = 5000.0  # taller peak
        col_sums[205] = 4500.0  # shorter right shoulder
        spikes = BarProfileService.detect_spikes(col_sums)
        assert spikes == [(200, 5000.0)]

    def test_two_groups_each_keep_their_tallest_peak(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[129] = 907.0  # first group, tallest
        col_sums[131] = 740.0  # first group, right shoulder
        col_sums[268] = 451.0  # second group, shorter left shoulder
        col_sums[274] = 599.0  # second group, tallest
        spikes = BarProfileService.detect_spikes(col_sums, min_diff_threshold=500.0)
        assert spikes == [(129, 907.0), (274, 599.0)]

    def test_tall_middle_peak_does_not_swallow_its_neighbours(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[100] = 500.0  # shorter, 30 cols from the middle
        col_sums[130] = 1000.0  # tallest, but the neighbours are 60 cols apart
        col_sums[160] = 500.0
        spikes = BarProfileService.detect_spikes(col_sums)
        assert [col for col, _ in sorted(spikes)] == [100, 160]

    def test_weak_shoulder_does_not_merge_distant_peaks(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[100] = 5000.0
        col_sums[137] = 3000.0
        col_sums[174] = 4500.0
        spikes = BarProfileService.detect_spikes(col_sums)
        assert spikes == [(100, 5000.0), (174, 4500.0)]

    def test_sorted_by_height_descending(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[100] = 3000.0
        col_sums[500] = 5000.0
        col_sums[300] = 4000.0
        spikes = BarProfileService.detect_spikes(col_sums)
        heights = [s[1] for s in spikes]
        assert heights == sorted(heights, reverse=True)

    def test_weak_peaks_below_30_percent_excluded(self):
        col_sums = np.zeros(640, dtype=float)
        col_sums[100] = 5000.0  # max
        col_sums[400] = 1400.0  # 28% of max → below 30% threshold
        spikes = BarProfileService.detect_spikes(col_sums)
        assert len(spikes) == 1
        assert spikes[0][0] == 100
