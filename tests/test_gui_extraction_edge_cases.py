"""Tests for ExtractTab GUI workflow edge cases.

Covers: path length guard, existing score overwrite, watchdog timeout,
cancelled_with_pages dialog, ExtractTab on_completed, on_error, and
MainWindow signal dispatch.
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_gui import MainWindow, ExtractTab, ReviewPagesDialog
from src.api.gui_api import GuiApi


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def main_window(qapp):
    mw = MainWindow()
    yield mw
    mw.close()


@pytest.fixture
def tab(main_window):
    return main_window.extract_tab


# ── Existing Score Overwrite ──────────────────────────────────────────────


@pytest.mark.unit
class TestExistingScoreOverwrite:

    def test_overwrite_dialog_shown_when_photos_exist(self, tab, tmp_path, monkeypatch):
        # Set up an existing score with photos
        tab._parent_dir = str(tmp_path)
        tab.project_edit.setText("ExistingScore")
        photos = tmp_path / "ExistingScore" / "photos"
        photos.mkdir(parents=True)
        (photos / "page_001_merged.png").write_bytes(b"x")
        # Mock the api to prevent actual extraction
        tab._api.start_extraction = MagicMock()
        # Mock QMessageBox.question to return No
        from PyQt6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
        # Set video path to a fake one so validation passes
        tab._video_path = "fake.mp4"
        monkeypatch.setattr("os.path.exists", lambda p: True)
        # Try to start extraction
        tab._start_extraction()
        # Should have NOT started extraction (still idle)
        assert tab._busy is False

    def test_overwrite_dialog_yes_proceeds(self, tab, tmp_path, monkeypatch):
        tab._parent_dir = str(tmp_path)
        tab.project_edit.setText("ExistingScore")
        photos = tmp_path / "ExistingScore" / "photos"
        photos.mkdir(parents=True)
        (photos / "page_001_merged.png").write_bytes(b"x")
        from PyQt6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        # Mock the api to avoid actual extraction
        tab._api.start_extraction = MagicMock()
        # Set video path to a fake one
        tab._video_path = "fake.mp4"
        monkeypatch.setattr("os.path.exists", lambda p: True)
        tab._start_extraction()
        # Old photos should be cleared
        assert not (photos / "page_001_merged.png").exists()


# ── Path Length Guard ────────────────────────────────────────────────────


@pytest.mark.unit
class TestPathLengthGuard:

    def test_path_too_long_shows_warning(self, tab, tmp_path, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))
        # Mock the api to prevent actual extraction
        tab._api.start_extraction = MagicMock()
        # Set up a very long path
        tab._parent_dir = str(tmp_path)
        tab.project_edit.setText("a" * 300)
        # Patch get_project_dir to return a long path
        monkeypatch.setattr(tab, "get_project_dir", lambda: "C:\\" + "a" * 300)
        tab._video_path = "fake.mp4"
        monkeypatch.setattr("os.path.exists", lambda p: True)
        tab._start_extraction()
        assert len(warnings) > 0
        assert "Path Too Long" in str(warnings[0][1])


# ── Watchdog Timeout ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestWatchdogTimeout:

    def test_watchdog_timeout_cancels_and_resets(self, tab):
        tab._busy = True
        tab._api.cancel_extraction = MagicMock()
        tab._on_watchdog_timeout()
        tab._api.cancel_extraction.assert_called_once()
        assert tab._busy is False

    def test_watchdog_timeout_logs_message(self, tab):
        tab._busy = True
        tab._api.cancel_extraction = MagicMock()
        tab._on_watchdog_timeout()
        assert any("Timeout" in line for line in tab.log_edit.toPlainText().splitlines())


# ── on_completed Zero Pages ──────────────────────────────────────────────


@pytest.mark.unit
class TestOnCompletedZeroPages:

    def test_on_completed_zero_pages_returns_false(self, tab):
        tab._busy = True
        result = tab.on_completed(0)
        assert result is False
        assert tab._busy is False
        assert any("No pages captured" in line for line in tab.log_edit.toPlainText().splitlines())


# ── on_error ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestOnError:

    def test_on_error_logs_message(self, tab):
        tab._busy = True
        tab.on_error("Test error message")
        log_text = tab.log_edit.toPlainText()
        assert "[Error] Test error message" in log_text

    def test_on_error_resets_ui(self, tab):
        tab._busy = True
        tab.on_error("Test error")
        assert tab._busy is False


# ── on_cancelled ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestOnCancelled:

    def test_on_cancelled_logs_message(self, tab):
        tab._busy = True
        tab.on_cancelled()
        log_text = tab.log_edit.toPlainText()
        assert "Cancelled" in log_text
        assert tab._busy is False


# ── on_page_detected ─────────────────────────────────────────────────────


@pytest.mark.unit
class TestOnPageDetected:

    def test_on_page_detected_updates_badge(self, tab):
        tab.on_page_detected(0, b"")
        assert tab.page_badge.text() == "Pages: 1"
        tab.on_page_detected(2, b"")
        assert tab.page_badge.text() == "Pages: 3"


# ── on_cancelled_with_pages ──────────────────────────────────────────────


@pytest.mark.unit
class TestOnCancelledWithPages:

    def test_keep_dialog_yes_calls_generate_pdf(self, tab, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
        tab._api.get_page_count = MagicMock(return_value=3)
        tab._api.generate_pdf = MagicMock()
        tab._busy = True
        tab._review_before_save = MagicMock()
        tab.on_cancelled_with_pages(3)
        tab._api.generate_pdf.assert_called_once()
        assert tab._busy is False

    def test_keep_dialog_no_clears_pages(self, tab, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
        tab._api.clear_pages = MagicMock()
        tab._busy = True
        tab.on_cancelled_with_pages(3)
        tab._api.clear_pages.assert_called_once()
        assert tab._busy is False


# ── _reset_ui ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestResetUI:

    def test_reset_ui_clears_busy(self, tab):
        tab._busy = True
        tab._reset_ui()
        assert tab._busy is False

    def test_reset_ui_clears_reextract_mode(self, tab):
        tab._reextract_mode = True
        tab._reset_ui()
        assert tab._reextract_mode is False

    def test_reset_ui_clears_page_badge(self, tab):
        tab.page_badge.setText("Pages: 5")
        tab._reset_ui()
        assert tab.page_badge.text() == ""


# ── MainWindow Signal Dispatch ───────────────────────────────────────────


@pytest.mark.unit
class TestMainWindowSignalDispatch:

    def test_on_completed_first_call_starts_pdf(self, main_window):
        from app_gui import MainWindow
        # First on_completed should start PDF generation
        main_window._generating_pdf = False
        main_window.extract_tab.on_completed = lambda _pc: True
        main_window._on_completed(5)
        assert main_window._generating_pdf is True

    def test_on_completed_second_call_is_pdf_done(self, main_window):
        from app_gui import MainWindow
        # First call arms the flag
        main_window._generating_pdf = True
        # Second call: extract_tab.on_completed should NOT be called again
        called = []
        main_window.extract_tab.on_completed = lambda _pc: called.append(_pc)
        main_window._on_completed(5)
        assert called == []  # on_completed NOT called on second time

    def test_on_error_calls_extract_tab(self, main_window):
        from app_gui import MainWindow
        called = []
        main_window.extract_tab.on_error = lambda msg: called.append(msg)
        main_window._on_error("test error")
        assert "test error" in called

    def test_on_log_calls_extract_tab(self, main_window):
        from app_gui import MainWindow
        called = []
        main_window.extract_tab._log = lambda msg: called.append(msg)
        main_window._on_log("test log")
        assert "test log" in called

    def test_on_cancelled_calls_extract_tab(self, main_window):
        from app_gui import MainWindow
        called = []
        main_window.extract_tab.on_cancelled = lambda: called.append(True)
        main_window._on_cancelled()
        assert called == [True]

    def test_on_cancelled_with_pages_calls_extract_tab(self, main_window):
        from app_gui import MainWindow
        called = []
        main_window.extract_tab.on_cancelled_with_pages = lambda pc: called.append(pc)
        main_window._on_cancelled_with_pages(7)
        assert called == [7]
