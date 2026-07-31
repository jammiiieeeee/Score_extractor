"""
Full end-to-end integration tests for the Piano Score Extractor.

Creates synthetic .mp4 videos, runs extraction, generates PDFs, and
validates the entire pipeline with no real video files needed.

Run: pytest tests/test_integration_e2e.py -v --timeout=120
"""

import os
import shutil
import time
import json
from pathlib import Path
from threading import Event
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest

from src.api.gui_api import GuiApi, VideoInfo, ExtractionState
from src.domain.models import Frame
from src.domain.value_objects.config import ScoreConfig


# ── Helpers ──────────────────────────────────────────────────────────────


REAL_VIDEO = str(Path(__file__).parent / "fixtures" / "test_video.mp4")


def create_synthetic_video(path, scenes=None, fps=30.0, width=800, height=600):
    """Create a synthetic .mp4 with distinct scenes for page-change detection.

    Each scene has 60 frames (~2s at 30fps) to ensure the extraction
    algorithm has enough data to detect page transitions.
    """
    if scenes is None:
        scenes = [
            {"color": (0, 0, 0), "label": "Page 1"},
            {"color": (250, 250, 250), "label": "Page 2"},
            {"color": (0, 0, 0), "label": "Page 3"},
            {"color": (250, 250, 250), "label": "Page 4"},
        ]

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    for scene in scenes:
        for j in range(60):
            img = np.full((height, width, 3), scene["color"], dtype=np.uint8)
            cv2.putText(img, scene["label"], (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, (200, 200, 200) if scene["color"][0] < 128 else (30, 30, 30), 3)
            cv2.rectangle(img, (50, 150), (750, 550),
                          (150, 150, 150) if scene["color"][0] < 128 else (50, 50, 50), 2)
            out.write(img)
    out.release()
    return path


def wait_for(condition_fn, timeout=30.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(interval)
    return False


class CallbackCollector:
    """Records all callbacks emitted by GuiApi."""

    def __init__(self, api):
        self.logs = []
        self.progress_events = []
        self.page_events = []
        self.errors = []
        self.completed_count = [0]
        self.cancelled = Event()

        api.set_on_log(lambda m: self.logs.append(m))
        api.set_on_progress(lambda p, pc, d: self.progress_events.append((p, pc, d)))
        api.set_on_page_detected(lambda idx, img: self.page_events.append((idx, len(img))))
        api.set_on_error(lambda m: self.errors.append(m))
        api.set_on_completed(lambda c: self.completed_count.__setitem__(0, c))
        api.set_on_cancelled(lambda: self.cancelled.set())


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def api():
    a = GuiApi()
    yield a
    a.cleanup()


@pytest.fixture
def synthetic_video(tmp_path):
    """A 4-scene synthetic .mp4 for page-change detection."""
    path = str(tmp_path / "e2e_video.mp4")
    return create_synthetic_video(path)


@pytest.fixture
def synthetic_video_long(tmp_path):
    """A longer synthetic video (6 scenes) for extended extraction tests."""
    scenes = [
        {"color": (0, 0, 0), "label": "Page 1"},
        {"color": (100, 100, 100), "label": "Page 2"},
        {"color": (200, 200, 200), "label": "Page 3"},
        {"color": (0, 0, 0), "label": "Page 4"},
        {"color": (200, 200, 200), "label": "Page 5"},
        {"color": (0, 0, 0), "label": "Page 6"},
    ]
    path = str(tmp_path / "e2e_video_long.mp4")
    return create_synthetic_video(path, scenes=scenes)


@pytest.fixture
def synthetic_images():
    """5 synthetic test images for direct page manipulation."""
    images = []
    for i in range(5):
        img = np.ones((600, 800, 3), dtype=np.uint8) * 240
        cv2.putText(img, f"Page {i+1}", (50, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
        cv2.rectangle(img, (50, 150), (750, 550), (100, 100, 100), 2)
        images.append(img)
    return images


@pytest.fixture
def real_video():
    """Path to the real test video (backnumber_theta.mp4)."""
    assert os.path.exists(REAL_VIDEO), f"Test video not found at {REAL_VIDEO}"
    return REAL_VIDEO


@pytest.fixture
def work_dir(tmp_path):
    """Temporary working directory for extraction output."""
    path = tmp_path / "e2e_work"
    path.mkdir()
    return path


# ═══════════════════════════════════════════════════════════════════════════
#  End-to-End: Synthetic Video -> Extraction -> Pages
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.slow
class TestExtractionFromSyntheticVideo:
    """Create synthetic video, extract pages, verify detection."""

    def test_extraction_detects_pages(self, api, real_video, work_dir):
        cb = CallbackCollector(api)
        api.update_config({"change_detection_threshold": 0.90})

        api.start_extraction(
            real_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="e2e_extract"
        )

        assert wait_for(lambda: not api.is_busy(), timeout=120.0)
        state = api.get_extraction_state()

        assert state.phase in ("done", "error"), f"Phase: {state.phase}"
        assert api.get_page_count() > 0, f"Expected pages, got 0. Errors: {cb.errors}"
        assert cb.completed_count[0] > 0
        assert len(cb.progress_events) > 0
        assert len(cb.logs) > 0
        assert len(cb.page_events) == api.get_page_count(), (
            f"on_page_detected should fire once per captured page "
            f"({len(cb.page_events)} events for {api.get_page_count()} pages)")
        assert all(size > 0 for _, size in cb.page_events), "page bytes should be non-empty"

    def test_extraction_with_different_threshold(self, api, real_video, work_dir):
        api.update_config({"change_detection_threshold": 0.85})
        cb = CallbackCollector(api)

        api.start_extraction(
            real_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="threshold_test"
        )

        assert wait_for(lambda: not api.is_busy(), timeout=120.0)
        state = api.get_extraction_state()
        assert state.phase in ("done", "error")

    def test_extraction_long_video(self, api, real_video, work_dir):
        cb = CallbackCollector(api)
        api.update_config({"change_detection_threshold": 0.90})

        api.start_extraction(
            real_video, no_ocr=True, start_time=2.0, end_offset=0.0,
            output_folder=str(work_dir), score_name="long_extract"
        )

        assert wait_for(lambda: not api.is_busy(), timeout=180.0)
        state = api.get_extraction_state()
        assert state.phase in ("done", "error")
        assert api.get_page_count() > 0, f"Expected pages, got 0. Errors: {cb.errors}"


# ═══════════════════════════════════════════════════════════════════════════
#  End-to-End: Extraction -> PDF Generation
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.slow
class TestExtractionToPdf:
    """Extract pages from video, then generate PDF, verify output."""

    def test_extract_then_generate_pdf(self, api, real_video, work_dir, tmp_path):
        cb = CallbackCollector(api)
        api.update_config({"change_detection_threshold": 0.90})

        # Extract
        api.start_extraction(
            real_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="pdf_test"
        )
        assert wait_for(lambda: not api.is_busy(), timeout=120.0)
        assert api.get_extraction_state().phase == "done"
        assert api.get_page_count() > 0, f"Expected pages, got 0. Errors: {cb.errors}"

        # Generate PDF
        pdf_path = str(tmp_path / "output_score.pdf")
        api.generate_pdf(pdf_path)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)

        assert os.path.exists(pdf_path), f"PDF not found at {pdf_path}"
        assert os.path.getsize(pdf_path) > 1000

        # Metadata saved alongside the PDF in its parent directory
        meta_path = Path(pdf_path).parent / "metadata.json"
        assert meta_path.exists(), f"metadata.json should exist at {meta_path}"

    def test_generate_pdf_from_synthetic_images(self, api, synthetic_images, tmp_path):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        pdf_path = str(tmp_path / "synthetic.pdf")
        api.generate_pdf(pdf_path)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)

        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 1000


# ═══════════════════════════════════════════════════════════════════════════
#  End-to-End: Extraction with OCR (Mocked)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestExtractionWithMockedOcr:
    """Verify extraction flow when OCR is mocked (no PaddleOCR needed)."""

    def test_extraction_with_stub_ocr(self, api, synthetic_video, work_dir):
        """Run extraction with OCR enabled but using a stub."""
        cb = CallbackCollector(api)

        # Mock the OCR initialization to succeed without PaddleOCR
        with patch('src.api.gui_api.OcrService') as MockOcr:
            mock_ocr = MagicMock()
            mock_ocr.initialize.return_value = False  # Simulate init failure (graceful fallback)
            mock_ocr.is_enabled.return_value = False
            MockOcr.return_value = mock_ocr

            api.start_extraction(
                synthetic_video, no_ocr=False, end_offset=0.0,
                output_folder=str(work_dir), score_name="ocr_mock_test"
            )
            assert wait_for(lambda: not api.is_busy(), timeout=120.0)

        state = api.get_extraction_state()
        assert state.phase in ("done", "error")


# ═══════════════════════════════════════════════════════════════════════════
#  End-to-End: GuiApi Full Workflow
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.slow
class TestGuiApiFullWorkflow:
    """Complete user journey: open video -> extract -> review -> generate PDF."""

    def test_complete_workflow(self, api, real_video, work_dir, tmp_path):
        cb = CallbackCollector(api)

        # 1. Tweak config
        api.update_config({"change_detection_threshold": 0.90})
        assert api.get_config()["change_detection_threshold"] == 0.90

        # 2. Open video
        info = api.open_video(real_video)
        assert info.duration > 0
        assert info.fps > 0

        # 3. Preview a frame
        frame = api.read_frame_at(0.5)
        assert frame is not None

        # 4. Extract
        api.start_extraction(
            real_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="full_e2e"
        )
        assert wait_for(lambda: not api.is_busy(), timeout=120.0)
        state = api.get_extraction_state()
        assert state.phase == "done", f"Phase: {state.phase}"
        assert api.get_page_count() > 0, f"Expected pages, got 0. Errors: {cb.errors}"

        # 5. Review pages
        thumb = api.get_page_thumbnail(0)
        assert thumb is not None
        full = api.get_page_full(0)
        assert full is not None

        # 6. Remove a page (if we have more than 1)
        page_count_before = api.get_page_count()
        if page_count_before > 1:
            api.remove_page(page_count_before - 1)
            assert api.get_page_count() == page_count_before - 1

        # 7. Reorder pages
        n = api.get_page_count()
        if n >= 2:
            api.reorder_pages(list(range(n - 1, -1, -1)))

        # 8. Generate PDF
        pdf_path = str(tmp_path / "full_workflow.pdf")
        api.generate_pdf(pdf_path)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 1000

    def test_extract_then_regenerate_with_different_crop(self, api, real_video, work_dir, tmp_path):
        """Extract once, then regenerate PDF with a different crop ratio."""
        cb = CallbackCollector(api)

        api.update_config({"default_crop_ratio": 0.30})
        api.start_extraction(
            real_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="crop_e2e"
        )
        assert wait_for(lambda: not api.is_busy(), timeout=120.0)
        assert api.get_extraction_state().phase == "done"
        assert api.get_page_count() > 0, f"Expected pages, got 0. Errors: {cb.errors}"

        # First PDF
        pdf_v1 = str(tmp_path / "crop_v1.pdf")
        api.generate_pdf(pdf_v1)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(pdf_v1)
        size_v1 = os.path.getsize(pdf_v1)

        # Regenerate with different crop
        pdf_v2 = str(tmp_path / "crop_v2.pdf")
        api.update_config({"default_crop_ratio": 0.25})
        api.regenerate_from_dir(str(work_dir / "crop_e2e"), pdf_v2)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(pdf_v2)
        size_v2 = os.path.getsize(pdf_v2)

        # Both should exist and be valid PDFs
        assert size_v1 > 1000
        assert size_v2 > 1000


# ═══════════════════════════════════════════════════════════════════════════
#  End-to-End: Regenerate from Directory
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestRegenerateFromDirectory:
    """Load existing page images from a directory and regenerate PDF."""

    def test_regenerate_creates_pdf(self, api, synthetic_images, work_dir, tmp_path):
        photos_dir = work_dir / "regen_score" / "photos"
        photos_dir.mkdir(parents=True)
        for i, img in enumerate(synthetic_images):
            cv2.imwrite(str(photos_dir / f"page_{i:03d}_merged.png"), img)

        pdf_path = str(tmp_path / "regenerated.pdf")
        api.regenerate_from_dir(str(work_dir / "regen_score"), pdf_path)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 1000
        assert api.get_page_count() == 5

    def test_regenerate_empty_dir_raises(self, api, tmp_path):
        empty_dir = tmp_path / "empty_score"
        empty_dir.mkdir()

        with pytest.raises(RuntimeError, match="No page images"):
            api.regenerate_from_dir(str(empty_dir), str(tmp_path / "fail.pdf"))


# ═══════════════════════════════════════════════════════════════════════════
#  End-to-End: Score Management Round-Trip
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestScoreManagementRoundTrip:
    """Save a score, load it, verify metadata and page count."""

    def test_save_load_delete_score(self, api, synthetic_images, tmp_path):
        # Create a score directory with pages
        score_dir = tmp_path / "roundtrip_score"
        photos_dir = score_dir / "photos"
        photos_dir.mkdir(parents=True)
        for i, img in enumerate(synthetic_images):
            cv2.imwrite(str(photos_dir / f"page_{i:03d}_merged.png"), img)

        # Save metadata
        GuiApi.save_metadata(str(score_dir), {
            "score_name": "roundtrip_score",
            "page_count": 5,
            "crop_ratio": 0.35,
        })

        # List scores
        scores = api.list_saved_scores(str(tmp_path))
        assert len(scores) >= 1
        names = [s.score_name for s in scores]
        assert "roundtrip_score" in names

        # Load score
        count = api.load_saved_score(str(score_dir))
        assert count == 5
        assert api.get_page_count() == 5

        # Metadata
        meta = api.get_loaded_score_metadata()
        assert meta.get("score_name") == "roundtrip_score"
        assert meta.get("page_count") == 5

        # Delete score
        api.delete_saved_score(str(score_dir))
        assert not score_dir.exists()

        # Verify deleted
        scores_after = api.list_saved_scores(str(tmp_path))
        names_after = [s.score_name for s in scores_after]
        assert "roundtrip_score" not in names_after
