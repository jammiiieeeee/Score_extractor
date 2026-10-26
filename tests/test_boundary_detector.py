"""Unit tests for BoundaryDetector (src/domain/boundary_detector.py).

Covers the region-contrast measurement (staff-line robustness), global
redetect, narrow tracking with hysteresis, and the sanity guard.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.boundary_detector import BoundaryDetector


def _split_frame(height=400, width=200, split=250, top=230, bottom=30, seed=0):
    """Bright top region above ``split``, dark bottom region below it."""
    rng = np.random.default_rng(seed)
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:split] = top
    frame[split:] = bottom
    noise = rng.integers(-3, 4, size=(height, width, 3))
    return np.clip(frame.astype(int) + noise, 0, 255).astype(np.uint8)


@pytest.mark.unit
class TestRedetect:

    def test_finds_bright_dark_split(self):
        d = BoundaryDetector(band_ratio=0.05, min_contrast=20.0)
        row = d.redetect(_split_frame(split=250))
        assert row is not None
        assert abs(row - 250) <= 12

    def test_unlocked_properties(self):
        d = BoundaryDetector()
        assert d.boundary_row is None
        assert not d.is_locked

    def test_locked_after_redetect(self):
        d = BoundaryDetector(min_contrast=20.0)
        d.redetect(_split_frame())
        assert d.is_locked
        assert d.boundary_row is not None

    def test_staff_lines_do_not_fool_detector(self):
        """A bright region with dark horizontal staff lines above a bright
        region — the staff lines must NOT be chosen as the boundary."""
        h, w = 400, 200
        frame = np.full((h, w, 3), 230, dtype=np.uint8)
        for y in range(60, 200, 10):
            frame[y:y + 2] = 40          # staff line inside the bright region
        frame[250:] = 30                 # the real boundary
        d = BoundaryDetector(band_ratio=0.05, min_contrast=20.0)
        row = d.redetect(frame)
        assert row is not None
        assert abs(row - 250) <= 15

    def test_below_min_contrast_keeps_none(self):
        flat = np.full((400, 200, 3), 128, dtype=np.uint8)
        d = BoundaryDetector(min_contrast=50.0)
        assert d.redetect(flat) is None
        assert not d.is_locked


@pytest.mark.unit
class TestTrack:

    def test_track_without_lock_falls_back_to_redetect(self):
        d = BoundaryDetector(min_contrast=20.0)
        row = d.track(_split_frame(split=250))
        assert row is not None
        assert abs(row - 250) <= 12

    def test_track_holds_against_single_noise_spike(self):
        d = BoundaryDetector(min_contrast=20.0)
        d.redetect(_split_frame(split=250))
        base = d.boundary_row

        # A bright falling note just below the line would pull the raw
        # argmax — the median + hysteresis must hold the boundary.
        noisy = _split_frame(split=250)
        noisy[base + 2:base + 10] = 255
        row = d.track(noisy)
        assert abs(row - base) <= d._hysteresis_px

    def test_track_follows_sustained_small_drift(self):
        d = BoundaryDetector(min_contrast=20.0, track_window=0.10,
                             hysteresis_px=3, median_window=3)
        d.redetect(_split_frame(split=250))
        moved = 250 + 20
        for _ in range(5):
            row = d.track(_split_frame(split=moved))
        assert abs(row - moved) <= 6

    def test_redetect_accepts_page_jump(self):
        """jump-then-hold: a new page can move the boundary far away."""
        d = BoundaryDetector(min_contrast=20.0)
        d.redetect(_split_frame(split=250))
        new_row = d.redetect(_split_frame(split=150))
        assert abs(new_row - 150) <= 12

    def test_redetect_resets_median_window(self):
        d = BoundaryDetector(min_contrast=20.0)
        d.redetect(_split_frame(split=250))
        d.track(_split_frame(split=250))
        d.redetect(_split_frame(split=150))
        assert len(d._recent) == 1


@pytest.mark.unit
class TestSanityGuard:

    def test_bright_bottom_region_rejected(self):
        """A frame bright top-to-bottom (no visualizer) must not be cropped."""
        d = BoundaryDetector(min_contrast=5.0, min_dark_mean=120.0)
        frame = _split_frame(split=250, top=230, bottom=200)
        assert d.redetect(frame) is None
        assert not d.is_locked

    def test_dark_bottom_region_accepted(self):
        d = BoundaryDetector(min_contrast=5.0, min_dark_mean=120.0)
        frame = _split_frame(split=250, top=230, bottom=20)
        assert d.redetect(frame) is not None


@pytest.mark.unit
class TestConfigIntegration:

    def test_config_defaults_exist(self):
        from src.domain.value_objects.config import ScoreConfig
        c = ScoreConfig()
        assert c.boundary_mode == "auto"
        assert c.boundary_offset_px == 0
        assert 0.0 <= c.boundary_offset_ratio < 0.1
        assert 0.0 < c.boundary_band_ratio < 1.0
        assert c.boundary_track_window > 0
        assert c.boundary_hysteresis_px >= 0
        assert c.boundary_median_window >= 1
