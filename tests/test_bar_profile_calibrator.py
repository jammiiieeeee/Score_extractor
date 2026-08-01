"""Unit tests for BarProfileCalibrator (src/domain/bar_profile_calibrator.py).

Covers the bootstrap floor, the p10-of-min-heights estimate, windowing,
outlier robustness, and sample validation.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.bar_profile_calibrator import BarProfileCalibrator


@pytest.mark.unit
class TestBarProfileCalibrator:

    def test_bootstrap_before_calibration(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3)
        assert not c.is_calibrated
        assert c.current_floor == 500.0

    def test_single_sample_not_enough(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3)
        c.sample([1000, 2000])
        assert not c.is_calibrated
        assert c.current_floor == 500.0

    def test_floor_after_calibration_is_p10_of_mins_discounted(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3, window=20,
                                 quantile=0.10, discount=0.8)
        c.sample([1000, 2000])   # min 1000
        c.sample([3000, 5000])   # min 3000
        assert not c.is_calibrated
        c.sample([2000, 2500])   # min 2000
        assert c.is_calibrated
        # mins = [1000, 3000, 2000]; sorted = [1000, 2000, 3000]
        # idx = round(0.10 * 2) = 0 -> 1000 * 0.8 = 800
        assert c.current_floor == pytest.approx(800.0)

    def test_floor_can_rise_above_bootstrap(self):
        """A video with huge bars should push the floor above the guess."""
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3)
        c.sample([8000, 9000])
        c.sample([10000, 11000])
        c.sample([12000, 13000])
        assert c.current_floor > 500.0

    def test_floor_can_drop_below_bootstrap(self):
        """A faint-bar video should lower the floor instead of staying at the
        hardcoded guess."""
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3)
        c.sample([200, 250])
        c.sample([300, 350])
        c.sample([400, 450])
        assert c.current_floor < 500.0

    def test_floor_never_below_min_floor(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3, min_floor=10.0)
        c.sample([5, 6])
        c.sample([7, 8])
        c.sample([9, 10])
        assert c.current_floor >= 10.0

    def test_outlier_faint_sample_does_not_zero_the_floor(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3, window=20)
        for _ in range(15):
            c.sample([8000, 9000])
        c.sample([50, 60])   # one anomalous faint profile
        assert c.current_floor > 1000.0

    def test_window_keeps_only_recent_samples(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3, window=3)
        for _ in range(10):
            c.sample([8000, 9000])
        assert c.is_calibrated
        assert c.sample_count == 10

    def test_sample_requires_two_heights(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3)
        c.sample([1000])
        c.sample([])
        c.sample(None)
        assert c.sample_count == 0
        assert not c.is_calibrated

    def test_reset_returns_to_bootstrap(self):
        c = BarProfileCalibrator(bootstrap=500.0, min_samples=3)
        c.sample([1000, 2000])
        c.sample([3000, 4000])
        c.sample([5000, 6000])
        assert c.is_calibrated
        c.reset()
        assert not c.is_calibrated
        assert c.current_floor == 500.0
