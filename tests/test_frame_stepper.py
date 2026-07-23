"""Unit tests for FrameStepper (src/application/extraction_components.py).

Tests the extraction loop state machine: SSIM detection, A/B capture,
blank content detection, end offset, and tail scan.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.extraction_components import FrameStepper
from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from tests.conftest import StubVideoService, StubOcrService, make_solid_image


@pytest.mark.unit
class TestFrameStepperInitialize:
    """Tests for FrameStepper.initialize()."""

    def _make_stepper(self, frames, config=None, is_cancelled=None):
        fps = 30.0
        svc = StubVideoService([f.image for f in frames], fps=fps)
        cfg = config or ScoreConfig(frame_check_interval=0.01)
        stepper = FrameStepper(
            svc, cfg,
            on_log=lambda msg: None,
            on_progress=None,
            is_cancelled=is_cancelled or (lambda: False),
        )
        return stepper, svc

    def test_initialize_without_start_time(self):
        frames = [Frame(make_solid_image(), 0.0, i) for i in range(5)]
        stepper, svc = self._make_stepper(frames)
        result = stepper.initialize(-1.0)
        assert result is None
        assert stepper.current_idx == 0
        assert stepper.last_stable_frame is not None

    def test_initialize_with_start_time(self):
        frames = [Frame(make_solid_image(), float(i) / 30.0, i) for i in range(100)]
        stepper, svc = self._make_stepper(frames)
        result = stepper.initialize(1.0)
        assert result is not None
        a_frame, b_frame = result
        assert isinstance(a_frame, Frame)
        assert isinstance(b_frame, Frame)
        assert a_frame.timestamp >= 1.0 - 0.1

    def test_initialize_sets_last_stable_frame(self):
        frames = [Frame(make_solid_image(), 0.0, i) for i in range(5)]
        stepper, _ = self._make_stepper(frames)
        stepper.initialize(-1.0)
        assert stepper.last_stable_frame is not None
        assert stepper.last_stable_frame.image is not None


@pytest.mark.unit
class TestFrameStepperStep:
    """Tests for FrameStepper.step()."""

    def _make_stepper(self, n_frames=50, config=None, is_cancelled=None):
        fps = 30.0
        frames = []
        for i in range(n_frames):
            shade = int(50 + (i * 20) % 200)
            img = make_solid_image(800, 600, (shade, shade, shade))
            frames.append(Frame(img, float(i) / fps, i))
        svc = StubVideoService([f.image for f in frames], fps=fps)
        cfg = config or ScoreConfig(frame_check_interval=0.01)
        stepper = FrameStepper(
            svc, cfg,
            on_log=lambda msg: None,
            on_progress=None,
            is_cancelled=is_cancelled or (lambda: False),
        )
        stepper.initialize(-1.0)
        stepper.set_unique_pages_ref([])
        return stepper

    def test_step_returns_frame_and_ssim(self):
        stepper = self._make_stepper(50)
        result = stepper.step()
        assert result is not None
        frame, ssim_score = result
        assert isinstance(frame, Frame)
        assert ssim_score is None or isinstance(ssim_score, float)

    def test_step_returns_none_when_exhausted(self):
        stepper = self._make_stepper(2)
        stepper.step()
        stepper.step()
        result = stepper.step()
        assert result is None

    def test_step_returns_none_when_cancelled(self):
        cancel = MagicMock(return_value=True)
        stepper = self._make_stepper(50, is_cancelled=cancel)
        result = stepper.step()
        assert result is None

    def test_step_blank_content_detection(self):
        blank_img = make_solid_image(800, 600, (128, 128, 128))
        frames = [
            Frame(make_solid_image(800, 600, (50, 50, 50)), 0.0, 0),
            Frame(make_solid_image(800, 600, (100, 100, 100)), 1.0, 30),
            Frame(blank_img, 2.0, 60),
        ]
        fps = 30.0
        svc = StubVideoService([f.image for f in frames], fps=fps)
        cfg = ScoreConfig(frame_check_interval=0.01)
        stepper = FrameStepper(svc, cfg, on_log=lambda msg: None)
        stepper.initialize(-1.0)
        existing = [Frame(make_solid_image(800, 600, (50, 50, 50)), 0.0, 0)]
        stepper.set_unique_pages_ref(existing)
        stepper.step()
        result = stepper.step()
        assert result is None


@pytest.mark.unit
class TestFrameStepperShouldTrigger:
    """Tests for FrameStepper.should_trigger()."""

    def _make_stepper(self):
        frames = [Frame(make_solid_image(), 0.0, i) for i in range(5)]
        svc = StubVideoService([f.image for f in frames], fps=30.0)
        return FrameStepper(svc, ScoreConfig(), on_log=lambda msg: None)

    def test_trigger_below_threshold(self):
        stepper = self._make_stepper()
        assert stepper.should_trigger(0.80) is True

    def test_no_trigger_above_threshold(self):
        stepper = self._make_stepper()
        assert stepper.should_trigger(0.98) is False

    def test_no_trigger_at_threshold(self):
        stepper = self._make_stepper()
        assert stepper.should_trigger(0.96) is False

    def test_no_trigger_none(self):
        stepper = self._make_stepper()
        assert stepper.should_trigger(None) is False


@pytest.mark.unit
class TestFrameStepperCaptureAB:
    """Tests for FrameStepper.capture_a_b()."""

    def test_capture_a_b_returns_tuple(self):
        frames = [Frame(make_solid_image(), float(i) / 30.0, i) for i in range(100)]
        svc = StubVideoService([f.image for f in frames], fps=30.0)
        stepper = FrameStepper(svc, ScoreConfig(), on_log=lambda msg: None)
        trigger = Frame(make_solid_image(), 1.0, 30)
        a, b = stepper.capture_a_b(trigger)
        assert isinstance(a, Frame)
        assert isinstance(b, Frame)

    def test_capture_a_b_b_index_after_a(self):
        frames = [Frame(make_solid_image(), float(i) / 30.0, i) for i in range(100)]
        svc = StubVideoService([f.image for f in frames], fps=30.0)
        cfg = ScoreConfig(a_capture_delay=0.3, b_capture_delay=3.0)
        stepper = FrameStepper(svc, cfg, on_log=lambda msg: None)
        trigger = Frame(make_solid_image(), 1.0, 30)
        a, b = stepper.capture_a_b(trigger)
        assert b.index >= a.index


@pytest.mark.unit
class TestFrameStepperCheckEndOffset:
    """Tests for FrameStepper.check_end_offset()."""

    def _make_stepper(self):
        frames = [Frame(make_solid_image(), 0.0, i) for i in range(5)]
        svc = StubVideoService([f.image for f in frames], fps=30.0)
        return FrameStepper(svc, ScoreConfig(), on_log=lambda msg: None)

    def test_past_end_offset(self):
        stepper = self._make_stepper()
        assert stepper.check_end_offset(56.0, 5.0, 60.0) is True

    def test_before_end_offset(self):
        stepper = self._make_stepper()
        assert stepper.check_end_offset(30.0, 5.0, 60.0) is False

    def test_no_offset(self):
        stepper = self._make_stepper()
        assert stepper.check_end_offset(50.0, 0.0, 60.0) is False

    def test_zero_duration(self):
        stepper = self._make_stepper()
        assert stepper.check_end_offset(50.0, 5.0, 0.0) is False


@pytest.mark.unit
class TestFrameStepperTailScan:
    """Tests for FrameStepper.tail_scan()."""

    def _make_stepper(self, n_frames=100):
        fps = 30.0
        frames = [Frame(make_solid_image(), float(i) / fps, i) for i in range(n_frames)]
        svc = StubVideoService([f.image for f in frames], fps=fps)
        return FrameStepper(svc, ScoreConfig(), on_log=lambda msg: None), svc

    def test_tail_scan_with_end_offset_skips(self):
        stepper, _ = self._make_stepper()
        pages = [Frame(make_solid_image(), 5.0, 150)]
        ocr = StubOcrService(enabled=True)
        stepper.tail_scan(ocr, pages, 90, end_offset=5.0)
        assert len(pages) == 1

    def test_tail_scan_with_ocr_detection(self):
        stepper, svc = self._make_stepper(200)
        pages = [Frame(make_solid_image(), 5.0, 150)]
        ocr = StubOcrService(enabled=True)
        ocr.set_keywords_found(True)
        stepper.tail_scan(ocr, pages, 100, end_offset=0.0)
        assert len(pages) <= 1

    def test_tail_scan_no_ocr(self):
        stepper, _ = self._make_stepper(200)
        pages = [Frame(make_solid_image(), 5.0, 150)]
        ocr = StubOcrService(enabled=False)
        stepper.tail_scan(ocr, pages, 100, end_offset=0.0)
        assert len(pages) == 1
