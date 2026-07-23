"""
GUI workflow integration tests for GuiApi.

Simulates realistic user workflows by driving the GuiApi through its
callback-driven, threaded interface — just like the real PyQt6 GUI does.

Run: pytest tests/test_gui_workflow.py -v --timeout=120
     pytest tests/test_gui_workflow.py -v -x --timeout=120   (stop on first failure)
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path
from threading import Event

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.gui_api import GuiApi, VideoInfo, ExtractionState


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def api():
    api = GuiApi()
    yield api
    api.cleanup()


@pytest.fixture
def test_video():
    """Path to the real test video."""
    path = Path(__file__).parent / "fixtures" / "test_video.mp4"
    if path.exists():
        return str(path.resolve())
    pytest.skip("No test video file found")


@pytest.fixture
def synthetic_images():
    """Return 5 synthetic test images as a list of ndarrays."""
    images = []
    for i in range(5):
        img = np.ones((600, 800, 3), dtype=np.uint8) * 240
        cv2.putText(img, f"Page {i+1}", (50, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
        cv2.rectangle(img, (50, 150), (750, 550), (100, 100, 100), 2)
        images.append(img)
    return images


@pytest.fixture
def work_dir():
    """Temporary working directory for extraction output."""
    path = Path(tempfile.mkdtemp(prefix="gui_test_"))
    yield path
    shutil.rmtree(str(path), ignore_errors=True)


# ── Helpers ──────────────────────────────────────────────────────────────


def wait_for(condition_fn, timeout=30.0, interval=0.1):
    """Poll *condition_fn* until it returns truthy or *timeout* seconds pass."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = condition_fn()
        if result:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Condition not met within {timeout}s")


class CallbackCollector:
    """Records all callbacks emitted by GuiApi for later inspection."""

    def __init__(self, api: GuiApi):
        self.logs = []
        self.progress_events = []
        self.page_events = []       # (index, byte_count)
        self.errors = []
        self.completed_count = [0]
        self.cancelled = Event()

        api.set_on_log(lambda m: self.logs.append(m))
        api.set_on_progress(lambda p, pc, d: self.progress_events.append((p, pc, d)))
        api.set_on_page_detected(lambda idx, img: self.page_events.append((idx, len(img))))
        api.set_on_error(lambda m: self.errors.append(m))
        api.set_on_completed(lambda c: self.completed_count.__setitem__(0, c))
        api.set_on_cancelled(lambda: self.cancelled.set())


# ═══════════════════════════════════════════════════════════════════════════
#  Config Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestConfigWorkflow:
    """User story: tweaking settings before extraction."""

    def test_get_and_update_config_roundtrip(self, api):
        cfg = api.get_config()
        assert cfg["change_detection_threshold"] == 0.96

        api.update_config({"change_detection_threshold": 0.85})
        assert api.get_config()["change_detection_threshold"] == 0.85

    def test_update_config_with_invalid_key_shows_error(self, api):
        with pytest.raises(ValueError, match="Unknown config key"):
            api.update_config({"bogus_field": 1.0})

    def test_update_config_with_oob_value_shows_error(self, api):
        with pytest.raises(ValueError, match="must be between"):
            api.update_config({"change_detection_threshold": 99.0})

    def test_reset_restores_defaults(self, api):
        api.update_config({"change_detection_threshold": 0.50})
        api.reset_config()
        assert api.get_config()["change_detection_threshold"] == 0.96

    def test_save_and_load_config_file(self, api, tmp_path):
        api.update_config({"change_detection_threshold": 0.77})
        path = str(tmp_path / "test_config.json")
        api.save_config_file(path)

        api2 = GuiApi()
        api2.load_config_file(path)
        assert api2.get_config()["change_detection_threshold"] == 0.77
        api2.cleanup()

    def test_config_persists_across_restart(self, api, tmp_path):
        config_path = str(tmp_path / "persist_test.json")
        api.save_config_file(config_path)

        api2 = GuiApi(config_path)
        cfg = api2.get_config()
        assert cfg["change_detection_threshold"] == 0.96
        api2.cleanup()


# ═══════════════════════════════════════════════════════════════════════════
#  Video Management Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestVideoWorkflow:
    """User story: loading a video and previewing frames."""

    def test_open_video_returns_metadata(self, api, test_video):
        info = api.open_video(test_video)
        assert isinstance(info, VideoInfo)
        assert info.fps > 0
        assert info.width > 0
        assert info.height > 0
        assert info.frame_count > 0
        assert info.duration > 0

    def test_open_video_twice_replaces(self, api, test_video):
        api.open_video(test_video)
        info2 = api.open_video(test_video)
        assert info2 is api.get_video_info()
        assert info2.fps > 0

    def test_get_video_info_returns_none_when_no_video(self, api):
        assert api.get_video_info() is None

    def test_read_frame_at_seeks_correctly(self, api, test_video):
        api.open_video(test_video)
        img = api.read_frame_at(0.0)
        assert img is not None
        assert img.shape[2] == 3

    def test_read_frame_at_invalid_timestamp(self, api, test_video):
        api.open_video(test_video)
        # Attempt to read beyond end — OpenCV returns None after EOF
        info = api.get_video_info()
        assert info is not None
        img = api.read_frame_at(info.duration + 999.0)
        assert img is None

    def test_close_video_clears_state(self, api, test_video):
        api.open_video(test_video)
        api.close_video()
        assert api.get_video_info() is None

    def test_has_video_true_after_open(self, api, test_video):
        api.open_video(test_video)
        assert api.has_video() is True

    def test_has_video_false_by_default(self, api):
        assert api.has_video() is False


# ═══════════════════════════════════════════════════════════════════════════
#  Full Extraction Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractionWorkflow:
    """User story: running extraction from start to finish."""

    def test_full_extraction_with_callbacks(self, api, test_video, work_dir):
        cb = CallbackCollector(api)

        api.start_extraction(
            test_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="test_extract"
        )

        wait_for(lambda: not api.is_busy(), timeout=120.0)
        state = api.get_extraction_state()

        assert state.phase in ("done", "error"), f"Phase: {state.phase}"
        if state.phase == "done":
            assert cb.completed_count[0] > 0, "on_completed should fire with page count"
            assert state.pages_detected > 0, "Should have detected pages"
            assert api.get_page_count() == state.pages_detected

        # Progress should have fired
        assert len(cb.progress_events) > 0, "on_progress should fire"
        assert len(cb.logs) > 0, "on_log should fire"

    def test_extraction_with_ocr(self, api, test_video, work_dir):
        try:
            import paddleocr  # noqa
        except ImportError:
            pytest.skip("paddleocr not installed")
        pytest.skip("OCR extraction too slow for CI — covered by test_gui_api.py::TestInitOcr")

    def test_cancel_extraction_midway(self, api, test_video, work_dir):
        cb = CallbackCollector(api)

        api.start_extraction(
            test_video, no_ocr=True, start_time=2.0, end_offset=0.0,
            output_folder=str(work_dir), score_name="test_cancel"
        )

        # Let it run a bit, then cancel
        time.sleep(3.0)
        assert api.is_busy()
        api.cancel_extraction()

        cancelled = cb.cancelled.wait(timeout=15.0)
        assert cancelled, "on_cancelled should fire"

        state = api.get_extraction_state()
        assert state.phase == "idle"
        assert not api.is_busy()

    def test_extraction_rejects_while_busy(self, api, test_video, work_dir):
        api.start_extraction(
            test_video, no_ocr=True, start_time=2.0, end_offset=0.0,
            output_folder=str(work_dir), score_name="test_busy"
        )
        time.sleep(1.0)

        with pytest.raises(RuntimeError, match="already in progress"):
            api.start_extraction(
                test_video, no_ocr=True, start_time=2.0, end_offset=10.0,
                output_folder=str(work_dir), score_name="test_busy2"
            )

        api.cancel_extraction()
        wait_for(lambda: not api.is_busy(), timeout=15.0)

    def test_extraction_requires_output_and_name(self, api, test_video):
        with pytest.raises(RuntimeError, match="output_folder and score_name are required"):
            api.start_extraction(test_video, no_ocr=True, start_time=2.0, end_offset=10.0)


# ═══════════════════════════════════════════════════════════════════════════
#  Page Management Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestPageManagementWorkflow:
    """User story: reviewing, reordering, and removing pages before PDF export."""

    @pytest.fixture(autouse=True)
    def setup_pages(self, api, synthetic_images):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

    def test_page_count_matches(self, api):
        assert api.get_page_count() == 5

    def test_get_thumbnail_is_resized(self, api):
        thumb = api.get_page_thumbnail(0)
        assert thumb is not None
        decoded = cv2.imdecode(np.frombuffer(thumb, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert decoded.shape[1] == 320, "Thumbnail should be 320px wide"

    def test_get_full_image_returns_bytes(self, api):
        full = api.get_page_full(0)
        assert full is not None
        assert len(full) > 100

    def test_remove_page_updates_count(self, api):
        api.remove_page(0)
        assert api.get_page_count() == 4

    def test_remove_page_raises_on_invalid(self, api):
        with pytest.raises(IndexError):
            api.remove_page(999)

    def test_reorder_pages(self, api):
        api.reorder_pages([4, 3, 2, 1, 0])
        assert api.get_page_count() == 5
        # Verify the first page is now from index 4
        assert api._pages[0].index == 4

    def test_reorder_pages_invalid_length(self, api):
        with pytest.raises(ValueError, match="must match"):
            api.reorder_pages([0, 1])

    def test_reorder_pages_invalid_permutation(self, api):
        with pytest.raises(ValueError, match="permutation"):
            api.reorder_pages([0, 0, 0, 0, 0])

    def test_clear_pages(self, api):
        api.clear_pages()
        assert api.get_page_count() == 0

    def test_remove_then_add_cycle(self, api):
        api.remove_page(0)
        assert api.get_page_count() == 4
        api.clear_pages()
        assert api.get_page_count() == 0


# ═══════════════════════════════════════════════════════════════════════════
#  PDF Generation Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestPdfWorkflow:
    """User story: generating PDF from detected pages."""

    def test_generate_pdf_from_synthetic_pages(self, api, synthetic_images, tmp_path):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        output = str(tmp_path / "test_output.pdf")
        api.generate_pdf(output)

        wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(output), f"PDF not found at {output}"
        assert os.path.getsize(output) > 1000

    def test_generate_pdf_requires_pages(self, api, tmp_path):
        with pytest.raises(RuntimeError, match="No pages to generate PDF"):
            api.generate_pdf(str(tmp_path / "empty.pdf"))

    def test_generate_pdf_rejects_when_busy(self, api, synthetic_images, tmp_path):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        # is_busy() checks thread aliveness, not _state.phase
        # So we need to actually have a running thread
        import threading
        api._pdf_thread = threading.Thread(target=lambda: time.sleep(10), daemon=True)
        api._pdf_thread.start()
        try:
            with pytest.raises(RuntimeError, match="already in progress"):
                api.generate_pdf(str(tmp_path / "busy.pdf"))
        finally:
            api._pdf_thread = None

    def test_regenerate_pdf_from_directory(self, api, synthetic_images, work_dir, tmp_path):
        photos_dir = work_dir / "photos"
        photos_dir.mkdir(parents=True)
        for i, img in enumerate(synthetic_images):
            cv2.imwrite(str(photos_dir / f"page_{i:03d}_merged.png"), img)

        output = str(tmp_path / "regenerated.pdf")
        api.regenerate_from_dir(str(work_dir), output)

        wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(output)
        assert api.get_page_count() == 5


# ═══════════════════════════════════════════════════════════════════════════
#  Score Management Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreManagementWorkflow:
    """User story: loading/saving scores and re-extracting with different crops."""

    def test_save_and_load_metadata_roundtrip(self, api, tmp_path):
        meta = {"score_name": "test", "page_count": 7, "crop_ratio": 0.28}
        GuiApi.save_metadata(str(tmp_path), meta)

        # Load it via load_saved_score -> calls _read_metadata internally
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir(parents=True)
        img = np.ones((600, 800, 3), dtype=np.uint8) * 240
        cv2.imwrite(str(photos_dir / "page_000_merged.png"), img)

        api.load_saved_score(str(tmp_path))
        result = api.get_loaded_score_metadata()
        assert result.get("score_name") == "test"
        assert result.get("page_count") == 7
        assert result.get("crop_ratio") == 0.28

    def test_reapply_crop_uses_original_pages(self, api, synthetic_images):
        from src.domain.models import Frame
        originals = [Frame(img.copy(), float(i), i) for i, img in enumerate(synthetic_images)]
        api._pages.set_originals(originals)

        api.reapply_crop(0.15)
        assert api.get_page_count() == 5
        for f in api._pages:
            h = f.image.shape[0]
            assert h <= 600, "Crop should reduce height"

    def test_has_loaded_score(self, api, tmp_path):
        assert api.has_loaded_score() is False
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir(parents=True)
        img = np.ones((600, 800, 3), dtype=np.uint8) * 240
        cv2.imwrite(str(photos_dir / "page_000_merged.png"), img)

        from src.domain.models import Frame
        api._loaded_score_path = str(tmp_path)
        api._pages.set_originals([Frame(img, 0.0, 0)])
        assert api.has_loaded_score() is True

    def test_delete_saved_score(self, api, tmp_path):
        score_dir = tmp_path / "to_delete"
        score_dir.mkdir()
        (score_dir / "photos").mkdir()

        assert score_dir.exists()
        api.delete_saved_score(str(score_dir))
        assert not score_dir.exists()

    def test_is_loading_from_scratch(self, api):
        assert api.is_loading_from_scratch() is True
        api._loaded_score_path = "/some/path"
        # Still False because _original_pages is empty
        assert api.is_loading_from_scratch() is True


# ═══════════════════════════════════════════════════════════════════════════
#  Lifecycle Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestLifecycleWorkflow:
    """User story: cleanup and state queries."""

    def test_cleanup_resets_everything(self, api, synthetic_images):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        api.cleanup()
        assert api.get_page_count() == 0
        assert api.get_video_info() is None

    def test_is_busy_false_when_idle(self, api):
        assert api.is_busy() is False

    def test_get_extraction_state_has_correct_structure(self, api):
        state = api.get_extraction_state()
        assert isinstance(state, ExtractionState)
        assert state.phase == "idle"
        assert isinstance(state.pages_detected, int)
        assert isinstance(state.elapsed_seconds, float)
        assert isinstance(state.current_timestamp, float)

    def test_set_debug_mode(self, api):
        assert api.is_debug_mode() is False
        api.set_debug_mode(True)
        assert api.is_debug_mode() is True


# ═══════════════════════════════════════════════════════════════════════════
#  Error-Handling Workflows
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandlingWorkflow:
    """User story: graceful handling of invalid inputs and failures."""

    def test_open_invalid_video(self, api):
        with pytest.raises(ValueError, match="Could not open video"):
            api.open_video(r"C:\nonexistent_video.mkv")

    def test_read_frame_without_open_video(self, api):
        img = api.read_frame_at(0.0)
        assert img is None

    def test_get_page_thumbnail_out_of_range(self, api):
        assert api.get_page_thumbnail(999) is None

    def test_get_page_full_out_of_range(self, api):
        assert api.get_page_full(999) is None

    def test_remove_page_out_of_range(self, api):
        with pytest.raises(IndexError):
            api.remove_page(-1)

    def test_cleanup_is_idempotent(self, api):
        api.cleanup()
        api.cleanup()
        api.cleanup()

    def test_ocr_preview_without_init(self, api):
        result = api.ocr_preview(b"not a png")
        assert result == []

    def test_busy_during_both_operations(self, api, test_video, work_dir):
        """Simulate user trying to start extraction while another is running."""
        cb = CallbackCollector(api)
        api._debug_mode = True

        api.start_extraction(
            test_video, no_ocr=True, start_time=2.0, end_offset=0.0,
            output_folder=str(work_dir), score_name="test_err_busy"
        )
        time.sleep(1.0)

        with pytest.raises(RuntimeError):
            api.start_extraction(
                test_video, no_ocr=True, start_time=2.0, end_offset=10.0,
                output_folder=str(work_dir), score_name="test_err_busy2"
            )

        api.cancel_extraction()
        wait_for(lambda: not api.is_busy(), timeout=30.0)


# ═══════════════════════════════════════════════════════════════════════════
#  Full End-to-End Workflow
# ═══════════════════════════════════════════════════════════════════════════

class TestEndToEndWorkflow:
    """Complete user journey: configure -> open video -> extract -> review pages -> generate PDF."""

    def test_complete_workflow(self, api, test_video, work_dir):
        cb = CallbackCollector(api)

        # 1. Tweak config
        api.update_config({"change_detection_threshold": 0.90})
        api.update_config({"min_screenshot_interval": 2.0})
        assert api.get_config()["change_detection_threshold"] == 0.90

        # 2. Open video
        info = api.open_video(test_video)
        assert info.duration > 0

        # 3. Preview a frame
        frame = api.read_frame_at(1.0)
        assert frame is not None

        # 4. Extract (short duration for speed)
        api.start_extraction(
            test_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="e2e_test"
        )

        wait_for(lambda: not api.is_busy(), timeout=120.0)
        state = api.get_extraction_state()
        assert state.phase == "done", f"Phase: {state.phase}"
        assert api.get_page_count() > 0

        # 5. Review pages: thumbnails, full, remove a bad one
        thumb = api.get_page_thumbnail(0)
        assert thumb is not None
        full = api.get_page_full(0)
        assert full is not None

        page_count_before = api.get_page_count()
        if page_count_before > 1:
            api.remove_page(page_count_before - 1)
            assert api.get_page_count() == page_count_before - 1

        # 6. Reorder pages
        n = api.get_page_count()
        if n >= 3:
            api.reorder_pages(list(range(n - 1, -1, -1)))  # reverse

        # 7. Generate PDF
        output_path = str(work_dir / "final_score.pdf")
        api.generate_pdf(output_path)

        wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 1000

        # 8. Metadata should have been saved to the output's parent directory
        meta_path = work_dir / "metadata.json"
        assert meta_path.exists(), f"metadata.json should exist at {meta_path}"

    def test_extract_then_regenerate_with_different_crop(self, api, test_video, work_dir):
        """Extract once, then regenerate PDF with a different crop ratio."""
        cb = CallbackCollector(api)

        api.update_config({"default_crop_ratio": 0.30})
        api.start_extraction(
            test_video, no_ocr=True, start_time=2.0, end_offset=10.0,
            output_folder=str(work_dir), score_name="crop_test"
        )
        wait_for(lambda: not api.is_busy(), timeout=120.0)
        assert api.get_extraction_state().phase == "done"
        assert api.get_page_count() > 0

        score_dir = work_dir / "crop_test"

        # Now try a different crop via regenerate
        output_path = str(work_dir / "crop_test_v2.pdf")
        api.update_config({"default_crop_ratio": 0.25})
        api.regenerate_from_dir(str(score_dir), output_path)

        wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(output_path)
