"""Tests for GuiApi callback error resilience.

Covers the 8 _emit_* methods that swallow callback exceptions to prevent
GUI crashes from broken callback implementations.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.gui_api import GuiApi


@pytest.fixture
def api(tmp_path):
    a = GuiApi(config_path=str(tmp_path / "config.json"))
    yield a
    a.cleanup()


@pytest.mark.unit
class TestCallbackResilience:

    def test_on_progress_exception_swallowed(self, api):
        def bad_callback(phase, percent, detail):
            raise RuntimeError("GUI crashed")
        api.set_on_progress(bad_callback)
        api._emit_progress("extracting", 50.0, "test")
        # No exception propagates

    def test_on_page_detected_exception_swallowed(self, api):
        def bad_callback(idx, png_bytes):
            raise RuntimeError("GUI crashed")
        api.set_on_page_detected(bad_callback)
        api._emit_page_detected(0, b"fake_png")
        # No exception propagates

    def test_on_log_exception_swallowed(self, api):
        def bad_callback(msg):
            raise RuntimeError("GUI crashed")
        api.set_on_log(bad_callback)
        api._emit_log("test message")
        # No exception propagates

    def test_on_error_exception_swallowed(self, api):
        def bad_callback(msg):
            raise RuntimeError("GUI crashed")
        api.set_on_error(bad_callback)
        api._emit_error("test error")
        # No exception propagates

    def test_on_completed_exception_swallowed(self, api):
        def bad_callback(page_count):
            raise RuntimeError("GUI crashed")
        api.set_on_completed(bad_callback)
        api._emit_completed(5)
        # No exception propagates

    def test_on_cancelled_exception_swallowed(self, api):
        def bad_callback():
            raise RuntimeError("GUI crashed")
        api.set_on_cancelled(bad_callback)
        api._emit_cancelled()
        # No exception propagates

    def test_on_cancelled_with_pages_exception_swallowed(self, api):
        def bad_callback(page_count):
            raise RuntimeError("GUI crashed")
        api.set_on_cancelled_with_pages(bad_callback)
        api._emit_cancelled_with_pages(3)
        # No exception propagates

    def test_on_download_completed_exception_swallowed(self, api):
        def bad_callback(path):
            raise RuntimeError("GUI crashed")
        api.set_on_download_completed(bad_callback)
        api._emit_download_completed("/tmp/video.mp4")
        # No exception propagates


@pytest.mark.unit
class TestCallbackNoneHandling:

    def test_emit_progress_with_no_callback(self, api):
        api._on_progress = None
        api._emit_progress("extracting", 50.0, "test")
        # No exception when callback is None

    def test_emit_log_with_no_callback(self, api):
        api._on_log = None
        api._emit_log("test")
        # No exception when callback is None

    def test_emit_error_with_no_callback(self, api):
        api._on_error = None
        api._emit_error("test")
        # No exception when callback is None
