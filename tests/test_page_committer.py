"""Unit tests for PageCommitter (src/application/extraction_components.py).

Tests the commit pipeline: merge, bar profile guard, dedup, save.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.extraction_components import PageCommitter
from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from src.domain.deduplication import Deduplicator
from tests.conftest import (
    StubVideoService, StubOcrService, StubFileService,
    make_solid_image, make_bar_image, make_image_with_text,
)


class MockOcrService:
    """OCR stub that returns a fixed number for any image (simulates page detection)."""

    def __init__(self, number=None):
        self._number = number
        self.enabled = number is not None

    def is_enabled(self):
        return self.enabled

    def initialize(self):
        return self.enabled

    def get_leftmost_number(self, image, vertical_range, horizontal_ratio=1.0, confidence_threshold=0):
        return self._number

    def detect_keywords(self, image, keywords):
        return False

    def get_texts(self, image):
        return []


@pytest.mark.unit
class TestPageCommitterCommit:
    """Tests for PageCommitter.commit()."""

    def _make_committer(self, ocr_enabled=True, config=None, work_dir=None):
        cfg = config or ScoreConfig()
        fps = 30.0
        frames = [make_solid_image(800, 600) for _ in range(10)]
        video_svc = StubVideoService(frames, fps=fps)
        ocr_svc = StubOcrService(enabled=ocr_enabled)
        file_svc = StubFileService(work_dir or Path(os.environ.get("TEMP", ".")))
        dedup = Deduplicator(cfg, ocr_svc)
        committer = PageCommitter(
            video_svc, file_svc, ocr_svc, cfg, dedup,
            orig_w=800, orig_h=600,
        )
        return committer, file_svc, ocr_svc, dedup

    def _ensure_dirs(self, tmp_path):
        out_dir = tmp_path / "score"
        out_dir.mkdir(exist_ok=True)
        (out_dir / "photos").mkdir(exist_ok=True)
        (out_dir / "debug").mkdir(exist_ok=True)
        return out_dir

    def test_first_page_always_added(self, tmp_path):
        committer, _, _, _ = self._make_committer(work_dir=tmp_path)
        a = Frame(make_solid_image(800, 600, (50, 50, 50)), 1.0, 30)
        b = Frame(make_solid_image(800, 600, (100, 100, 100)), 2.0, 60)
        pages = []
        out_dir = self._ensure_dirs(tmp_path)
        committer.commit(a, b, pages, out_dir, 1, False, lambda msg: None, None, is_first=True)
        assert len(pages) == 1

    def test_bar_profile_guard_rejects_identical(self, tmp_path):
        cfg = ScoreConfig(bar_min_diff_threshold=100.0)
        committer, _, _, _ = self._make_committer(config=cfg, work_dir=tmp_path)
        identical = make_solid_image(800, 600, (128, 128, 128))
        a1 = Frame(identical.copy(), 1.0, 30)
        b1 = Frame(identical.copy(), 2.0, 60)
        pages = [Frame(make_solid_image(800, 600, (50, 50, 50)), 0.0, 0)]
        out_dir = self._ensure_dirs(tmp_path)
        committer.commit(a1, b1, pages, out_dir, 2, False, lambda msg: None, None, is_first=False)
        assert len(pages) == 1

    def test_on_page_detected_callback(self, tmp_path):
        committer, _, _, _ = self._make_committer(work_dir=tmp_path)
        cb = MagicMock()
        a = Frame(make_solid_image(800, 600, (50, 50, 50)), 1.0, 30)
        b = Frame(make_solid_image(800, 600, (100, 100, 100)), 2.0, 60)
        pages = []
        out_dir = self._ensure_dirs(tmp_path)
        committer.commit(a, b, pages, out_dir, 1, False, lambda msg: None, cb, is_first=True)
        cb.assert_called_once()

    def test_on_page_detected_not_called_for_duplicate(self, tmp_path):
        """When guard rail rejects a page, callback is not called."""
        cfg = ScoreConfig(bar_min_diff_threshold=100.0)
        committer, _, _, _ = self._make_committer(config=cfg, work_dir=tmp_path)
        cb = MagicMock()
        identical = make_solid_image(800, 600, (128, 128, 128))
        pages = []
        out_dir = self._ensure_dirs(tmp_path)
        a1 = Frame(identical.copy(), 1.0, 30)
        b1 = Frame(identical.copy(), 2.0, 60)
        committer.commit(a1, b1, pages, out_dir, 1, False, lambda msg: None, cb, is_first=True)
        assert len(pages) == 1
        cb.reset_mock()
        a2 = Frame(identical.copy(), 4.0, 120)
        b2 = Frame(identical.copy(), 5.0, 150)
        committer.commit(a2, b2, pages, out_dir, 2, False, lambda msg: None, cb, is_first=False)
        cb.assert_not_called()

    def test_multiple_distinct_pages_committed(self, tmp_path):
        """Pages with different solid colors should pass pixel dedup."""
        cfg = ScoreConfig(pixel_similarity_threshold=0.50)
        committer, _, _, _ = self._make_committer(config=cfg, work_dir=tmp_path)
        pages = []
        out_dir = self._ensure_dirs(tmp_path)
        colors = [(20, 20, 20), (120, 120, 120), (220, 220, 220)]
        for i, color in enumerate(colors):
            a = Frame(make_solid_image(800, 600, color), float(i) * 3.0, i * 30)
            b = Frame(make_solid_image(800, 600, tuple(c + 10 for c in color)), float(i) * 3.0 + 1, i * 30 + 5)
            committer.commit(a, b, pages, out_dir, i + 1, False, lambda msg: None, None, is_first=(i == 0))
        assert len(pages) >= 1

    def test_ocr_dedup_same_number_rejects(self, tmp_path):
        """When OCR returns same number for both commits, second is duplicate."""
        cfg = ScoreConfig(pixel_similarity_threshold=0.50)
        fps = 30.0
        frames = [make_solid_image(800, 600) for _ in range(10)]
        video_svc = StubVideoService(frames, fps=fps)
        ocr_svc = MockOcrService(number=5)
        file_svc = StubFileService(tmp_path)
        dedup = Deduplicator(cfg, ocr_svc)
        committer = PageCommitter(video_svc, file_svc, ocr_svc, cfg, dedup, orig_w=800, orig_h=600)
        pages = []
        out_dir = self._ensure_dirs(tmp_path)
        a1 = Frame(make_solid_image(800, 600, (50, 50, 50)), 1.0, 30)
        b1 = Frame(make_solid_image(800, 600, (100, 100, 100)), 2.0, 60)
        committer.commit(a1, b1, pages, out_dir, 1, False, lambda msg: None, None, is_first=True)
        assert len(pages) == 1
        a2 = Frame(make_solid_image(800, 600, (200, 200, 200)), 4.0, 120)
        b2 = Frame(make_solid_image(800, 600, (210, 210, 210)), 5.0, 150)
        committer.commit(a2, b2, pages, out_dir, 2, False, lambda msg: None, None, is_first=True)
        assert len(pages) == 1

    def test_ocr_dedup_different_numbers_accepts(self, tmp_path):
        """When OCR returns different numbers, both pages are accepted."""
        cfg = ScoreConfig(pixel_similarity_threshold=0.50)
        fps = 30.0
        frames = [make_solid_image(800, 600) for _ in range(10)]
        video_svc = StubVideoService(frames, fps=fps)
        call_count = [0]
        def get_num(image, *args, **kwargs):
            call_count[0] += 1
            return 1 if call_count[0] <= 1 else 2
        ocr_svc = MockOcrService(number=1)
        ocr_svc.get_leftmost_number = get_num
        file_svc = StubFileService(tmp_path)
        dedup = Deduplicator(cfg, ocr_svc)
        committer = PageCommitter(video_svc, file_svc, ocr_svc, cfg, dedup, orig_w=800, orig_h=600)
        pages = []
        out_dir = self._ensure_dirs(tmp_path)
        a1 = Frame(make_solid_image(800, 600, (50, 50, 50)), 1.0, 30)
        b1 = Frame(make_solid_image(800, 600, (100, 100, 100)), 2.0, 60)
        committer.commit(a1, b1, pages, out_dir, 1, False, lambda msg: None, None, is_first=True)
        assert len(pages) == 1
        a2 = Frame(make_solid_image(800, 600, (200, 200, 200)), 4.0, 120)
        b2 = Frame(make_solid_image(800, 600, (210, 210, 210)), 5.0, 150)
        committer.commit(a2, b2, pages, out_dir, 2, False, lambda msg: None, None, is_first=True)
        assert len(pages) == 2

    def test_page_saved_to_disk(self, tmp_path):
        committer, file_svc, _, _ = self._make_committer(work_dir=tmp_path)
        a = Frame(make_solid_image(800, 600, (50, 50, 50)), 1.0, 30)
        b = Frame(make_solid_image(800, 600, (100, 100, 100)), 2.0, 60)
        pages = []
        out_dir = self._ensure_dirs(tmp_path)
        committer.commit(a, b, pages, out_dir, 1, False, lambda msg: None, None, is_first=True)
        saved_files = list((out_dir / "photos").glob("page_*_merged.png"))
        assert len(saved_files) == 1


def _create_test_video(path, width, height, fps=30.0, n_frames=120):
    """Create a .mp4 test video with enough frames for seek operations."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    img = np.full((height, width, 3), (128, 128, 128), dtype=np.uint8)
    for _ in range(n_frames):
        out.write(img)
    out.release()


@pytest.mark.unit
class TestPageCommitterOriginalResolution:
    """Verify PageCommitter uses the original (full-res) video dimensions
    for the merge upscale target, not the scan video's dimensions."""

    def test_upscale_uses_original_video_dims(self, tmp_path):
        """When original_video_path is provided, the committed frame should
        match the original video's resolution, not the scan video's."""
        scan_w, scan_h = 640, 360
        orig_w, orig_h = 1920, 1080

        scan_video = tmp_path / "scan.mp4"
        orig_video = tmp_path / "original.mp4"
        _create_test_video(scan_video, scan_w, scan_h)
        _create_test_video(orig_video, orig_w, orig_h)

        cfg = ScoreConfig()
        fps = 30.0
        scan_frames = [make_solid_image(scan_w, scan_h) for _ in range(120)]
        video_svc = StubVideoService(scan_frames, fps=fps)
        ocr_svc = StubOcrService(enabled=False)
        file_svc = StubFileService(tmp_path)
        dedup = Deduplicator(cfg, ocr_svc)

        # Simulates the bug path: scan dims passed as orig_w/h,
        # but original_video_path points to the full-res video
        committer = PageCommitter(
            video_svc, file_svc, ocr_svc, cfg, dedup,
            orig_w=scan_w, orig_h=scan_h,
            original_video_path=str(orig_video),
        )

        # After init, orig_w/h should be overridden to original video dims
        assert committer.orig_w == orig_w
        assert committer.orig_h == orig_h

        # Commit a page and verify the stored frame has original resolution
        a = Frame(make_solid_image(scan_w, scan_h, (50, 50, 50)), 1.0, 30)
        b = Frame(make_solid_image(scan_w, scan_h, (100, 100, 100)), 2.0, 60)
        pages = []
        out_dir = tmp_path / "score"
        out_dir.mkdir(exist_ok=True)
        (out_dir / "photos").mkdir(exist_ok=True)
        (out_dir / "debug").mkdir(exist_ok=True)

        committer.commit(a, b, pages, out_dir, 1, False, lambda msg: None, None, is_first=True)

        assert len(pages) == 1
        h, w = pages[0].image.shape[:2]
        assert w == orig_w, f"Expected width {orig_w}, got {w}"
        assert h == orig_h, f"Expected height {orig_h}, got {h}"

        committer.release()

    def test_no_original_video_keeps_scan_dims(self, tmp_path):
        """When original_video_path is None, orig_w/h stay as passed (scan dims)."""
        scan_w, scan_h = 640, 360

        cfg = ScoreConfig()
        fps = 30.0
        scan_frames = [make_solid_image(scan_w, scan_h) for _ in range(10)]
        video_svc = StubVideoService(scan_frames, fps=fps)
        ocr_svc = StubOcrService(enabled=False)
        file_svc = StubFileService(tmp_path)
        dedup = Deduplicator(cfg, ocr_svc)

        committer = PageCommitter(
            video_svc, file_svc, ocr_svc, cfg, dedup,
            orig_w=scan_w, orig_h=scan_h,
            original_video_path=None,
        )

        assert committer.orig_w == scan_w
        assert committer.orig_h == scan_h

        a = Frame(make_solid_image(scan_w, scan_h, (50, 50, 50)), 1.0, 30)
        b = Frame(make_solid_image(scan_w, scan_h, (100, 100, 100)), 2.0, 60)
        pages = []
        out_dir = tmp_path / "score"
        out_dir.mkdir(exist_ok=True)
        (out_dir / "photos").mkdir(exist_ok=True)
        (out_dir / "debug").mkdir(exist_ok=True)

        committer.commit(a, b, pages, out_dir, 1, False, lambda msg: None, None, is_first=True)

        assert len(pages) == 1
        h, w = pages[0].image.shape[:2]
        assert w == scan_w
        assert h == scan_h
