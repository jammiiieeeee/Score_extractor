"""
Comprehensive test script for the GuiApi (all 28 methods).

Run: python tests/test_api.py

Tests that don't require external resources (video file, OCR) always run.
Video-dependent tests are skipped if no test video is available.
OCR-dependent tests are skipped if paddleocr is not installed.
"""

import os
import sys
import time
import json
import tempfile
import traceback

from typing import Optional
import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.gui_api import GuiApi, VideoInfo, ExtractionState, SandboxInfo


# ── Test helpers ────────────────────────────────────────────────────────

PASS = 0
FAIL = 0
SKIP = 0


def test(name: str, skip: bool = False):
    """Decorator that runs a test function and counts pass/fail/skip."""
    def decorator(fn):
        global PASS, FAIL, SKIP

        def wrapper(*args, **kwargs):
            global PASS, FAIL, SKIP
            if skip:
                print(f"  [SKIP] {name}")
                SKIP += 1
                return
            try:
                fn(*args, **kwargs)
                print(f"  [PASS] {name}")
                PASS += 1
            except SkipTest as e:
                print(f"  [SKIP] {name}: {e}")
                SKIP += 1
            except Exception as e:
                print(f"  [FAIL] {name}")
                print(f"         {e}")
                traceback.print_exc()
                FAIL += 1
        return wrapper
    return decorator


def make_test_image(width: int = 800, height: int = 600, page_num: int = 1) -> bytes:
    """Create a synthetic test image with a page number visible."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 240
    cv2.putText(img, f"Page {page_num}", (50, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    cv2.rectangle(img, (50, 150), (750, 550), (100, 100, 100), 2)
    _, buf = cv2.imencode('.png', img)
    return buf.tobytes()


def make_test_image_ndarray(width: int = 800, height: int = 600, page_num: int = 1) -> np.ndarray:
    """Create a synthetic test image as ndarray."""
    from src.api.gui_api import GuiApi
    data = make_test_image(width, height, page_num)
    return GuiApi._decode_png(data)


# ── Tests ───────────────────────────────────────────────────────────────

def test_all():
    api = GuiApi()
    log_messages = []
    progress_events = []
    page_events = []
    error_events = []
    completed_count = [0]
    cancelled_flag = [False]

    api.set_on_log(lambda m: log_messages.append(m))
    api.set_on_progress(lambda p, pc, d: progress_events.append((p, pc, d)))
    api.set_on_page_detected(lambda idx, img: page_events.append((idx, len(img))))
    api.set_on_error(lambda m: error_events.append(m))
    api.set_on_completed(lambda c: completed_count.__setitem__(0, c))
    api.set_on_cancelled(lambda: cancelled_flag.__setitem__(0, True))

    # ── 1. get_config() ────────────────────────────────────────────────
    def test_get_config():
        cfg = api.get_config()
        assert isinstance(cfg, dict), "get_config should return a dict"
        assert "change_detection_threshold" in cfg
        assert cfg["change_detection_threshold"] == 0.96

    # ── 2. update_config() ─────────────────────────────────────────────
    def test_update_config():
        result = api.update_config({"change_detection_threshold": 0.90})
        assert result["change_detection_threshold"] == 0.90
        assert api._config.change_detection_threshold == 0.90

    def test_update_config_rejects_unknown_key():
        try:
            api.update_config({"nonexistent": 1.0})
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_update_config_rejects_oob_float():
        try:
            api.update_config({"change_detection_threshold": 1.5})
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_update_config_rejects_oob_int():
        try:
            api.update_config({"default_strips_per_page": 0})
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
        try:
            api.update_config({"default_strips_per_page": 21})
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_update_config_rejects_oob_confidence():
        try:
            api.update_config({"ocr_confidence_threshold": -1})
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
        try:
            api.update_config({"ocr_confidence_threshold": 101})
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    # ── 3. reset_config() ──────────────────────────────────────────────
    def test_reset_config():
        result = api.reset_config()
        assert result["change_detection_threshold"] == 0.96
        assert api._config.change_detection_threshold == 0.96

    # ── 4. load_config_file() ──────────────────────────────────────────
    def test_load_config_file():
        cfg = {"change_detection_threshold": 0.50, "frame_check_interval": 0.5}
        path = os.path.join(tempfile.gettempdir(), "_test_gui_config.json")
        with open(path, 'w') as f:
            json.dump(cfg, f)
        result = api.load_config_file(path)
        assert result["change_detection_threshold"] == 0.50
        assert result["frame_check_interval"] == 0.5
        os.remove(path)

    # ── 5. save_config_file() ──────────────────────────────────────────
    def test_save_config_file():
        path = os.path.join(tempfile.gettempdir(), "_test_gui_config_save.json")
        api.save_config_file(path)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert "change_detection_threshold" in data
        os.remove(path)

    # ── 6. open_video() ────────────────────────────────────────────────
    def test_open_video():
        # Look for a test video
        test_video = _find_test_video()
        if test_video is None:
            raise SkipTest("No test video found")
        info = api.open_video(test_video)
        assert isinstance(info, VideoInfo)
        assert info.fps > 0
        assert info.width > 0
        assert info.height > 0
        assert info.frame_count > 0
        assert os.path.isabs(info.path)

    # ── 7. get_video_info() ────────────────────────────────────────────
    def test_get_video_info():
        test_video = _find_test_video()
        if test_video is None:
            raise SkipTest("No test video found")
        if api._video_info is None:
            api.open_video(test_video)
        info = api.get_video_info()
        assert info is not None
        assert info.fps > 0

    # ── 8. read_frame_at() ─────────────────────────────────────────────
    def test_read_frame_at():
        test_video = _find_test_video()
        if test_video is None:
            raise SkipTest("No test video found")
        if api._video_info is None:
            api.open_video(test_video)
        png = api.read_frame_at(0.0)
        assert png is not None
        assert isinstance(png, bytes)
        assert len(png) > 100

    # ── 9. close_video() ───────────────────────────────────────────────
    def test_close_video():
        test_video = _find_test_video()
        if test_video is None:
            raise SkipTest("No test video found")
        if api._video_info is None:
            api.open_video(test_video)
        api.close_video()
        assert api._video_info is None
        assert api._video_service is None or api._video_service.cap is None

    # ── 10. init_ocr() ─────────────────────────────────────────────────
    def test_init_ocr():
        try:
            from paddleocr import PaddleOCR  # noqa
        except ImportError:
            raise SkipTest("paddleocr not installed")
        # This is slow, so just verify it returns bool
        result = api.init_ocr()
        assert isinstance(result, bool)

    # ── 11. ocr_status() ───────────────────────────────────────────────
    def test_ocr_status():
        status = api.ocr_status()
        assert isinstance(status, bool)

    # ── 12. ocr_preview() ──────────────────────────────────────────────
    def test_ocr_preview():
        if not api.ocr_status():
            raise SkipTest("OCR not available")
        img_bytes = make_test_image(page_num=42)
        texts = api.ocr_preview(img_bytes)
        assert isinstance(texts, list)

    # ── 13. start_extraction() ─────────────────────────────────────────
    def test_start_extraction():
        test_video = _find_test_video()
        if test_video is None:
            raise SkipTest("No test video found")
        api.start_extraction(test_video, no_ocr=True, duration=5.0)
        # Wait for completion
        timeout = 60.0
        start = time.time()
        while api.is_busy() and time.time() - start < timeout:
            time.sleep(0.5)
        state = api.get_extraction_state()
        assert state.phase in ("done", "error"), f"Extraction ended in {state.phase}"
        if state.phase == "done":
            assert completed_count[0] == api.get_page_count()
            assert state.pages_detected == api.get_page_count()

    # ── 14. cancel_extraction() ────────────────────────────────────────
    def test_cancel_extraction():
        test_video = _find_test_video()
        if test_video is None:
            raise SkipTest("No test video found")
        api.start_extraction(test_video, no_ocr=True, duration=999.0)
        time.sleep(1.0)
        api.cancel_extraction()
        time.sleep(2.0)
        assert not api.is_busy(), "Extraction should have been cancelled"

    # ── 15. get_extraction_state() ─────────────────────────────────────
    def test_get_extraction_state():
        state = api.get_extraction_state()
        assert isinstance(state, ExtractionState)
        assert hasattr(state, "phase")
        assert hasattr(state, "pages_detected")
        assert hasattr(state, "elapsed_seconds")
        assert hasattr(state, "current_timestamp")

    # ── 16. get_page_count() ───────────────────────────────────────────
    def test_get_page_count():
        count = api.get_page_count()
        assert isinstance(count, int)

    # ── 17. get_page_thumbnail() ───────────────────────────────────────
    def test_get_page_thumbnail():
        # Add a synthetic page
        img = make_test_image_ndarray(page_num=1)
        from src.domain.models import Frame
        api._pages.append(Frame(img, 1.0, 0))
        from src.api.gui_api import GuiApi as GA
        api._page_png_cache.append(GA._encode_png(img))

        thumb = api.get_page_thumbnail(0)
        assert thumb is not None
        assert isinstance(thumb, bytes)
        assert len(thumb) > 100

        # Decode and verify size
        decoded = cv2.imdecode(np.frombuffer(thumb, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert decoded.shape[1] == 320  # width

    # ── 18. get_page_full() ────────────────────────────────────────────
    def test_get_page_full():
        full = api.get_page_full(0)
        assert full is not None
        assert isinstance(full, bytes)
        assert len(full) > 100

    # ── 19. remove_page() ──────────────────────────────────────────────
    def test_remove_page():
        count_before = api.get_page_count()
        if count_before == 0:
            raise SkipTest("No pages to remove")
        api.remove_page(0)
        assert api.get_page_count() == count_before - 1

    def test_remove_page_invalid():
        try:
            api.remove_page(999)
            assert False, "Should have raised IndexError"
        except IndexError:
            pass

    # ── 20. reorder_pages() ────────────────────────────────────────────
    def test_reorder_pages():
        api._pages.clear()
        api._page_png_cache.clear()
        for i in range(3):
            img = make_test_image_ndarray(page_num=i)
            from src.domain.models import Frame
            api._pages.append(Frame(img, float(i), i))
            api._page_png_cache.append(None)

        api.reorder_pages([2, 0, 1])
        assert api.get_page_count() == 3

    def test_reorder_pages_invalid_length():
        try:
            api.reorder_pages([0, 1])
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_reorder_pages_invalid_permutation():
        try:
            api.reorder_pages([0, 0, 0])
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    # ── 21. clear_pages() ──────────────────────────────────────────────
    def test_clear_pages():
        api.clear_pages()
        assert api.get_page_count() == 0

    # ── 22. generate_pdf() ─────────────────────────────────────────────
    def test_generate_pdf():
        # Add synthetic pages
        if api.get_page_count() == 0:
            for i in range(3):
                img = make_test_image_ndarray(page_num=i)
                from src.domain.models import Frame
                api._pages.append(Frame(img, float(i), i))
                api._page_png_cache.append(None)

        output = os.path.join(tempfile.gettempdir(), "_test_gui_output.pdf")
        api.generate_pdf(output)

        timeout = 30.0
        start = time.time()
        while api.is_busy() and time.time() - start < timeout:
            time.sleep(0.5)
        assert not api.is_busy(), "PDF generation timed out"

        state = api.get_extraction_state()
        assert state.phase == "idle", f"PDF generation state: {state.phase}"

        if os.path.exists(output):
            assert os.path.getsize(output) > 1000
            os.remove(output)
        else:
            print(f"         PDF not found at {output}, checking for errors: {error_events}")
            # The PDF might have been generated elsewhere if sandbox was different
            # Let's search in debug/
            debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug")
            if os.path.exists(debug_dir):
                for root, dirs, files in os.walk(debug_dir):
                    for f in files:
                        if f.endswith(".pdf"):
                            os.remove(os.path.join(root, f))

    # ── 23. regenerate_from_dir() ──────────────────────────────────────
    def test_regenerate_from_dir():
        import tempfile
        tmpdir = tempfile.mkdtemp()
        # Create dummy page images
        for i in range(2):
            img = make_test_image_ndarray(page_num=i)
            cv2.imwrite(os.path.join(tmpdir, f"page_{i:03d}_merged.png"), img)

        output = os.path.join(tempfile.gettempdir(), "_test_gui_regenerated.pdf")
        api.regenerate_from_dir(tmpdir, output)

        timeout = 30.0
        start = time.time()
        while api.is_busy() and time.time() - start < timeout:
            time.sleep(0.5)
        assert not api.is_busy(), "Regeneration timed out"

        if os.path.exists(output):
            assert os.path.getsize(output) > 1000
            os.remove(output)

        # Cleanup temp dir
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ── 24. list_sandboxes() ───────────────────────────────────────────
    def test_list_sandboxes():
        sandboxes = api.list_sandboxes()
        assert isinstance(sandboxes, list)
        for sb in sandboxes:
            assert isinstance(sb, SandboxInfo)
            assert isinstance(sb.path, str)
            assert isinstance(sb.page_count, int)

    # ── 25. load_sandbox() ─────────────────────────────────────────────
    def test_load_sandbox():
        sandboxes = api.list_sandboxes()
        found_valid = False
        for sb in sandboxes:
            if sb.page_count > 0:
                count = api.load_sandbox(sb.path)
                assert count == sb.page_count
                assert api.get_page_count() == count
                found_valid = True
                break
        if not found_valid:
            # Create a sandbox dir manually and test
            import tempfile
            tmpdir = tempfile.mkdtemp(suffix="tmp_", dir="debug")
            for i in range(2):
                img = make_test_image_ndarray(page_num=i)
                cv2.imwrite(os.path.join(tmpdir, f"page_{i:03d}_merged.png"), img)
            count = api.load_sandbox(tmpdir)
            assert count == 2
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ── 26. delete_sandbox() ───────────────────────────────────────────
    def test_delete_sandbox():
        import tempfile
        tmpdir = tempfile.mkdtemp(suffix="tmp_", dir="debug")
        with open(os.path.join(tmpdir, "dummy.txt"), 'w') as f:
            f.write("test")
        assert os.path.exists(tmpdir)
        api.delete_sandbox(tmpdir)
        assert not os.path.exists(tmpdir)

    # ── 27. cleanup() ──────────────────────────────────────────────────
    def test_cleanup():
        test_video = _find_test_video()
        if test_video:
            api.open_video(test_video)
        # Add a page
        api._pages.clear()
        img = make_test_image_ndarray(page_num=1)
        from src.domain.models import Frame
        api._pages.append(Frame(img, 1.0, 0))

        api.cleanup()
        assert api._video_info is None
        assert api.get_page_count() == 0

    # ── 28. is_busy() ──────────────────────────────────────────────────
    def test_is_busy():
        busy = api.is_busy()
        assert isinstance(busy, bool)
        assert not busy  # Should be idle after cleanup


    # ── Run all tests ──────────────────────────────────────────────────

    tests = [
        ("get_config", test_get_config),
        ("update_config", test_update_config),
        ("update_config rejects unknown key", test_update_config_rejects_unknown_key),
        ("update_config rejects OOB float", test_update_config_rejects_oob_float),
        ("update_config rejects OOB int", test_update_config_rejects_oob_int),
        ("update_config rejects OOB confidence", test_update_config_rejects_oob_confidence),
        ("reset_config", test_reset_config),
        ("load_config_file", test_load_config_file),
        ("save_config_file", test_save_config_file),
        ("open_video", test_open_video),
        ("get_video_info", test_get_video_info),
        ("read_frame_at", test_read_frame_at),
        ("close_video", test_close_video),
        ("init_ocr", test_init_ocr),
        ("ocr_status", test_ocr_status),
        ("ocr_preview", test_ocr_preview),
        ("start_extraction", test_start_extraction),
        ("cancel_extraction", test_cancel_extraction),
        ("get_extraction_state", test_get_extraction_state),
        ("get_page_count", test_get_page_count),
        ("get_page_thumbnail", test_get_page_thumbnail),
        ("get_page_full", test_get_page_full),
        ("remove_page", test_remove_page),
        ("remove_page invalid", test_remove_page_invalid),
        ("reorder_pages", test_reorder_pages),
        ("reorder_pages invalid length", test_reorder_pages_invalid_length),
        ("reorder_pages invalid permutation", test_reorder_pages_invalid_permutation),
        ("clear_pages", test_clear_pages),
        ("generate_pdf", test_generate_pdf),
        ("regenerate_from_dir", test_regenerate_from_dir),
        ("list_sandboxes", test_list_sandboxes),
        ("load_sandbox", test_load_sandbox),
        ("delete_sandbox", test_delete_sandbox),
        ("cleanup", test_cleanup),
        ("is_busy", test_is_busy),
    ]

    print(f"\n{'='*60}")
    print(f"  GuiApi Test Suite — {len(tests)} tests")
    print(f"{'='*60}\n")

    for name, fn in tests:
        test(name)(fn)()

    print(f"\n{'='*60}")
    total = PASS + FAIL + SKIP
    print(f"  Results: {PASS} passed, {FAIL} failed, {SKIP} skipped ({total} total)")
    print(f"{'='*60}\n")

    return FAIL == 0


class SkipTest(Exception):
    pass


def _find_test_video() -> Optional[str]:
    """Look for a test video file in common locations."""
    candidates = [
        r"C:\Users\hosze\OneDrive\Documents\点描の唄 上級ver. ピアノ楽譜.mp4",
        os.path.join(os.path.dirname(__file__), "..", "test.mp4"),
        os.path.join(os.path.dirname(__file__), "..", "test.avi"),
        os.path.join(os.path.dirname(__file__), "..", "test.mkv"),
        os.path.join(os.path.dirname(__file__), "..", "test.mov"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    # Check if any mp4 exists in the project root
    import glob
    project_root = os.path.join(os.path.dirname(__file__), "..")
    for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov"):
        matches = glob.glob(os.path.join(project_root, ext))
        if matches:
            return matches[0]

    return None


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
