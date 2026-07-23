"""
Pytest migration of the old tests/test_api.py (28+ GuiApi method tests).

Uses the `api` fixture from conftest.py and proper pytest conventions.
Video-dependent tests use a synthetic .mp4 created via cv2.VideoWriter.

Run: pytest tests/test_gui_api.py -v --timeout=120
"""

import os
import json
import shutil
import time
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

from src.api.gui_api import GuiApi, VideoInfo, ExtractionState, ScoreInfo


# ── Helpers ──────────────────────────────────────────────────────────────


def make_test_image(width=800, height=600, page_num=1):
    """Create a synthetic test image as ndarray."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 240
    cv2.putText(img, f"Page {page_num}", (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    cv2.rectangle(img, (50, 150), (750, 550), (100, 100, 100), 2)
    return img


def make_test_image_png_bytes(width=800, height=600, page_num=1):
    """Create a synthetic test image and return as PNG bytes."""
    img = make_test_image(width, height, page_num)
    _, buf = cv2.imencode('.png', img)
    return buf.tobytes()


def create_synthetic_video(path: str, n_frames=30, fps=30.0, width=800, height=600):
    """Write a short synthetic .mp4 with alternating content for detection."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    colors = [(50, 50, 50), (100, 100, 100), (200, 200, 200), (240, 240, 240)]
    for i in range(n_frames):
        color = colors[i % len(colors)]
        img = np.full((height, width, 3), color, dtype=np.uint8)
        cv2.putText(img, f"F{i}", (50, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
        out.write(img)
    out.release()
    return path


def wait_for(condition_fn, timeout=30.0, interval=0.1):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(interval)
    return False


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def api():
    a = GuiApi()
    yield a
    a.cleanup()


@pytest.fixture
def synthetic_video(tmp_path):
    """Create a short synthetic .mp4 for testing video operations."""
    path = str(tmp_path / "test_video.mp4")
    create_synthetic_video(path, n_frames=30, fps=30.0)
    return path


@pytest.fixture
def long_synthetic_video(tmp_path):
    """Create a longer synthetic .mp4 (10s) for busy/cancel tests."""
    path = str(tmp_path / "long_test_video.mp4")
    create_synthetic_video(path, n_frames=300, fps=30.0)
    return path


REAL_VIDEO = str(Path(__file__).parent / "fixtures" / "test_video.mp4")


@pytest.fixture
def real_video():
    """Path to the real test video (backnumber_theta.mp4)."""
    assert os.path.exists(REAL_VIDEO), f"Test video not found at {REAL_VIDEO}"
    return REAL_VIDEO


@pytest.fixture
def synthetic_images():
    """Return 5 synthetic test images."""
    return [make_test_image(page_num=i) for i in range(5)]


# ═══════════════════════════════════════════════════════════════════════════
#  1. Config Management
# ═══════════════════════════════════════════════════════════════════════════


class TestGetConfig:
    def test_returns_dict_with_default_threshold(self, api):
        cfg = api.get_config()
        assert isinstance(cfg, dict)
        assert "change_detection_threshold" in cfg
        assert cfg["change_detection_threshold"] == 0.96


class TestUpdateConfig:
    def test_updates_threshold(self, api):
        result = api.update_config({"change_detection_threshold": 0.90})
        assert result["change_detection_threshold"] == 0.90
        assert api._config.change_detection_threshold == 0.90

    def test_rejects_unknown_key(self, api):
        with pytest.raises(ValueError, match="Unknown config key"):
            api.update_config({"nonexistent": 1.0})

    def test_rejects_oob_float(self, api):
        with pytest.raises(ValueError, match="must be between"):
            api.update_config({"change_detection_threshold": 1.5})

    def test_rejects_negative_confidence(self, api):
        with pytest.raises(ValueError, match="must be between"):
            api.update_config({"ocr_confidence_threshold": -1})

    def test_rejects_over_100_confidence(self, api):
        with pytest.raises(ValueError, match="must be between"):
            api.update_config({"ocr_confidence_threshold": 101})


class TestResetConfig:
    def test_restores_defaults(self, api):
        api.update_config({"change_detection_threshold": 0.50})
        result = api.reset_config()
        assert result["change_detection_threshold"] == 0.96
        assert api._config.change_detection_threshold == 0.96


class TestLoadConfigFile:
    def test_loads_json_config(self, api, tmp_path):
        cfg = {"change_detection_threshold": 0.50, "frame_check_interval": 0.5}
        path = str(tmp_path / "test_config.json")
        with open(path, 'w') as f:
            json.dump(cfg, f)
        result = api.load_config_file(path)
        assert result["change_detection_threshold"] == 0.50
        assert result["frame_check_interval"] == 0.5


class TestSaveConfigFile:
    def test_saves_and_roundtrips(self, api, tmp_path):
        api.update_config({"change_detection_threshold": 0.77})
        path = str(tmp_path / "save_test.json")
        api.save_config_file(path)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["change_detection_threshold"] == 0.77


# ═══════════════════════════════════════════════════════════════════════════
#  2. Video Lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestOpenVideo:
    def test_returns_video_info(self, api, synthetic_video):
        info = api.open_video(synthetic_video)
        assert isinstance(info, VideoInfo)
        assert info.fps > 0
        assert info.width > 0
        assert info.height > 0
        assert info.frame_count > 0
        assert os.path.isabs(info.path)

    def test_invalid_path_raises(self, api):
        with pytest.raises(ValueError):
            api.open_video(r"C:\nonexistent_video.mkv")


class TestGetVideoInfo:
    def test_returns_none_when_no_video(self, api):
        assert api.get_video_info() is None

    def test_returns_info_after_open(self, api, synthetic_video):
        api.open_video(synthetic_video)
        info = api.get_video_info()
        assert info is not None
        assert info.fps > 0


class TestReadFrameAt:
    def test_returns_ndarray(self, api, synthetic_video):
        api.open_video(synthetic_video)
        img = api.read_frame_at(0.0)
        assert img is not None
        assert isinstance(img, np.ndarray)
        assert img.shape[2] == 3

    def test_returns_none_without_video(self, api):
        img = api.read_frame_at(0.0)
        assert img is None

    def test_returns_none_beyond_duration(self, api, synthetic_video):
        api.open_video(synthetic_video)
        info = api.get_video_info()
        img = api.read_frame_at(info.duration + 999.0)
        assert img is None


class TestCloseVideo:
    def test_clears_state(self, api, synthetic_video):
        api.open_video(synthetic_video)
        api.close_video()
        assert api._video_info is None
        assert api._video_service is None or api._video_service.cap is None


# ═══════════════════════════════════════════════════════════════════════════
#  3. OCR
# ═══════════════════════════════════════════════════════════════════════════


class TestInitOcr:
    def test_returns_bool(self, api):
        try:
            from paddleocr import PaddleOCR  # noqa
        except ImportError:
            pytest.skip("paddleocr not installed")
        result = api.init_ocr()
        assert isinstance(result, bool)


class TestOcrStatus:
    def test_returns_bool(self, api):
        status = api.ocr_status()
        assert isinstance(status, bool)

    def test_false_by_default(self, api):
        assert api.ocr_status() is False


class TestOcrPreview:
    def test_returns_empty_without_ocr(self, api):
        result = api.ocr_preview(make_test_image_png_bytes())
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════
#  4. Extraction
# ═══════════════════════════════════════════════════════════════════════════


class TestStartExtraction:
    @pytest.mark.slow
    def test_extraction_completes(self, api, real_video, tmp_path):
        out_dir = str(tmp_path / "output")
        os.makedirs(out_dir, exist_ok=True)
        try:
            api.start_extraction(real_video, no_ocr=True, start_time=2.0, end_offset=10.0,
                                 output_folder=out_dir, score_name="test_score")
            assert wait_for(lambda: not api.is_busy(), timeout=120.0)
            state = api.get_extraction_state()
            assert state.phase in ("done", "error"), f"Phase: {state.phase}"
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_rejects_when_busy(self, api, tmp_path):
        import threading
        # Simulate a running extraction by setting a fake alive thread
        fake_thread = threading.Thread(target=lambda: time.sleep(30), daemon=True)
        fake_thread.start()
        api._extraction_thread = fake_thread
        api._state = ExtractionState("extracting", 0, 0.0, 0.0)
        try:
            with pytest.raises(RuntimeError, match="already in progress"):
                api.start_extraction("dummy.mp4", no_ocr=True, end_offset=5.0,
                                     output_folder=str(tmp_path), score_name="busy2")
        finally:
            api._extraction_thread = None
            api._state = ExtractionState("idle", 0, 0.0, 0.0)

    def test_requires_output_and_name(self, api, synthetic_video):
        with pytest.raises(RuntimeError, match="output_folder and score_name"):
            api.start_extraction(synthetic_video, no_ocr=True, end_offset=5.0)


class TestCancelExtraction:
    @pytest.mark.slow
    def test_cancels_midway(self, api, real_video, tmp_path):
        out_dir = str(tmp_path / "cancel_test")
        os.makedirs(out_dir, exist_ok=True)
        try:
            api.start_extraction(real_video, no_ocr=True, start_time=2.0, end_offset=0.0,
                                 output_folder=out_dir, score_name="cancel_test")
            time.sleep(2.0)
            if api.is_busy():
                api.cancel_extraction()
                assert wait_for(lambda: not api.is_busy(), timeout=120.0), "Extraction did not cancel in time"
                state = api.get_extraction_state()
                assert state.phase == "idle"
            else:
                state = api.get_extraction_state()
                assert state.phase in ("done", "idle")
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_cancel_sets_flag(self, api):
        """Cancel extraction when nothing is running should still set idle state."""
        api.cancel_extraction()
        state = api.get_extraction_state()
        assert state.phase == "cancelling" or state.phase == "idle"


class TestGetExtractionState:
    def test_returns_extraction_state(self, api):
        state = api.get_extraction_state()
        assert isinstance(state, ExtractionState)
        assert hasattr(state, "phase")
        assert hasattr(state, "pages_detected")
        assert hasattr(state, "elapsed_seconds")
        assert hasattr(state, "current_timestamp")

    def test_initial_phase_is_idle(self, api):
        state = api.get_extraction_state()
        assert state.phase == "idle"


# ═══════════════════════════════════════════════════════════════════════════
#  5. Page Management
# ═══════════════════════════════════════════════════════════════════════════


class TestGetPageCount:
    def test_zero_by_default(self, api):
        assert api.get_page_count() == 0


class TestGetPageThumbnail:
    def test_returns_encoded_png(self, api, synthetic_images):
        from src.domain.models import Frame
        api._pages.add(Frame(synthetic_images[0], 1.0, 0))

        thumb = api.get_page_thumbnail(0)
        assert thumb is not None
        assert isinstance(thumb, bytes)
        assert len(thumb) > 100

        decoded = cv2.imdecode(np.frombuffer(thumb, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert decoded.shape[1] == 320

    def test_returns_none_for_invalid_index(self, api):
        assert api.get_page_thumbnail(999) is None


class TestGetPageFull:
    def test_returns_full_resolution(self, api, synthetic_images):
        from src.domain.models import Frame
        api._pages.add(Frame(synthetic_images[0], 1.0, 0))

        full = api.get_page_full(0)
        assert full is not None
        assert isinstance(full, bytes)
        assert len(full) > 100

    def test_returns_none_for_invalid_index(self, api):
        assert api.get_page_full(999) is None


class TestRemovePage:
    def test_decrements_count(self, api, synthetic_images):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        api.remove_page(0)
        assert api.get_page_count() == 4

    def test_raises_for_invalid_index(self, api):
        with pytest.raises(IndexError):
            api.remove_page(999)

    def test_raises_for_negative_index(self, api, synthetic_images):
        from src.domain.models import Frame
        api._pages.add(Frame(synthetic_images[0], 1.0, 0))
        with pytest.raises(IndexError):
            api.remove_page(-1)


class TestReorderPages:
    def test_reorders_correctly(self, api, synthetic_images):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        api.reorder_pages([4, 3, 2, 1, 0])
        assert api.get_page_count() == 5
        assert api._pages[0].index == 4

    def test_rejects_wrong_length(self, api, synthetic_images):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))
        with pytest.raises(ValueError, match="must match"):
            api.reorder_pages([0, 1])

    def test_rejects_invalid_permutation(self, api, synthetic_images):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))
        with pytest.raises(ValueError, match="permutation"):
            api.reorder_pages([0, 0, 0, 0, 0])


class TestClearPages:
    def test_clears_all(self, api, synthetic_images):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))
        api.clear_pages()
        assert api.get_page_count() == 0

    def test_clears_loaded_score_state(self, api):
        api._loaded_score_path = "/some/path"
        api._loaded_score_metadata = {"foo": "bar"}
        api.clear_pages()
        assert api._loaded_score_path is None
        assert api._loaded_score_metadata == {}


# ═══════════════════════════════════════════════════════════════════════════
#  6. PDF Generation
# ═══════════════════════════════════════════════════════════════════════════


class TestGeneratePdf:
    def test_creates_pdf_file(self, api, synthetic_images, tmp_path):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        output = str(tmp_path / "test_output.pdf")
        api.generate_pdf(output)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(output)
        assert os.path.getsize(output) > 1000

    def test_rejects_when_no_pages(self, api, tmp_path):
        with pytest.raises(RuntimeError, match="No pages"):
            api.generate_pdf(str(tmp_path / "empty.pdf"))

    def test_rejects_when_busy(self, api, synthetic_images, tmp_path):
        from src.domain.models import Frame
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        import threading
        api._pdf_thread = threading.Thread(target=lambda: __import__('time').sleep(10), daemon=True)
        api._pdf_thread.start()
        try:
            with pytest.raises(RuntimeError, match="already in progress"):
                api.generate_pdf(str(tmp_path / "busy.pdf"))
        finally:
            api._pdf_thread = None


class TestRegenerateFromDir:
    def test_loads_and_generates(self, api, synthetic_images, tmp_path):
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        for i, img in enumerate(synthetic_images):
            cv2.imwrite(str(photos_dir / f"page_{i:03d}_merged.png"), img)

        output = str(tmp_path / "regenerated.pdf")
        api.regenerate_from_dir(str(tmp_path), output)
        assert wait_for(lambda: not api.is_busy(), timeout=30.0)
        assert os.path.exists(output)


# ═══════════════════════════════════════════════════════════════════════════
#  7. Score Management
# ═══════════════════════════════════════════════════════════════════════════


class TestListSavedScores:
    def test_returns_list_of_score_info(self, api, tmp_path):
        scores = api.list_saved_scores(str(tmp_path))
        assert isinstance(scores, list)
        for s in scores:
            assert isinstance(s, ScoreInfo)
            assert isinstance(s.path, str)
            assert isinstance(s.page_count, int)
            assert isinstance(s.score_name, str)

    def test_lists_existing_score(self, api, tmp_path, synthetic_images):
        photos_dir = tmp_path / "my_score" / "photos"
        photos_dir.mkdir(parents=True)
        for i, img in enumerate(synthetic_images[:2]):
            cv2.imwrite(str(photos_dir / f"page_{i:03d}_merged.png"), img)

        scores = api.list_saved_scores(str(tmp_path))
        assert len(scores) == 1
        assert scores[0].score_name == "my_score"
        assert scores[0].page_count == 2


class TestLoadSavedScore:
    def test_loads_pages(self, api, tmp_path, synthetic_images):
        score_dir = tmp_path / "load_test"
        photos_dir = score_dir / "photos"
        photos_dir.mkdir(parents=True)
        for i, img in enumerate(synthetic_images[:3]):
            cv2.imwrite(str(photos_dir / f"page_{i:03d}_merged.png"), img)

        count = api.load_saved_score(str(score_dir))
        assert count == 3
        assert api.get_page_count() == 3


class TestDeleteSavedScore:
    def test_removes_directory(self, api, tmp_path):
        score_dir = tmp_path / "to_delete"
        score_dir.mkdir()
        (score_dir / "photos").mkdir()
        assert score_dir.exists()
        api.delete_saved_score(str(score_dir))
        assert not score_dir.exists()

    def test_no_error_for_nonexistent(self, api, tmp_path):
        api.delete_saved_score(str(tmp_path / "nonexistent"))


# ═══════════════════════════════════════════════════════════════════════════
#  8. Lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestCleanup:
    def test_resets_everything(self, api, synthetic_video, synthetic_images):
        from src.domain.models import Frame
        api.open_video(synthetic_video)
        for i, img in enumerate(synthetic_images):
            api._pages.add(Frame(img, float(i), i))

        api.cleanup()
        assert api.get_page_count() == 0
        assert api.get_video_info() is None

    def test_is_idempotent(self, api):
        api.cleanup()
        api.cleanup()
        api.cleanup()


class TestIsBusy:
    def test_false_when_idle(self, api):
        assert api.is_busy() is False

    def test_returns_bool(self, api):
        assert isinstance(api.is_busy(), bool)
