"""Visual regression tests for the GUI.

Captures screenshots at each workflow state and validates widget geometry
to catch layout issues like text overflow, overlapping elements, and
misaligned widgets.

Run with: python -m pytest tests/test_gui_visual.py -v
Screenshots are saved to tests/visual_output/ for AI analysis.
"""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QWidget
from PyQt6.QtCore import Qt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app_gui
from app_gui import MainWindow, ExtractTab, ConfigTab
from src.domain.models import Frame


@pytest.fixture(scope="session")
def qt_app():
    """Session-scoped QApplication for all visual tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setStyle("Fusion")
    app.setApplicationName("Score Extractor Test")

    app_gui.CHECK_INDICATOR_PATH = app_gui._generate_check_pixmap()
    app_gui.CHEVRON_PATH = app_gui._generate_chevron_pixmap()
    app_gui.SPIN_UP_PATH = app_gui._generate_spin_arrow_pixmap(up=True)
    app_gui.SPIN_DOWN_PATH = app_gui._generate_spin_arrow_pixmap(up=False)

    from PyQt6.QtGui import QFont
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    return app


@pytest.fixture
def window(qt_app, tmp_path):
    """Fresh MainWindow for each test."""
    w = MainWindow()
    w.show()
    qt_app.processEvents()
    yield w
    w.close()


def capture_widget(widget, output_dir: Path, name: str) -> Path:
    """Capture rendered widget as PNG for AI analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.png"
    pixmap = widget.grab()
    pixmap.save(str(path))
    return path


def process_events():
    """Process Qt events using the application instance."""
    app = QApplication.instance()
    if app:
        app.processEvents()


def visible_layout_widgets(tab):
    """Direct children of the tab and its scroll content, in one coord space each."""
    widgets = []
    for parent in (tab, tab._content):
        for child in parent.children():
            if not isinstance(child, QWidget) or child is tab:
                continue
            if (child.isVisible() and child.width() > 0
                    and child.height() > 0):
                widgets.append(child)
    return widgets


def make_dummy_frames(n: int):
    """Create N dummy Frame objects for testing."""
    frames = []
    for i in range(n):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:] = (i * 20) % 256
        frames.append(Frame(img, timestamp=float(i), index=i))
    return frames


class TestExtractTabLayout:
    """Validate ExtractTab widget geometry and layout."""

    def test_no_widget_overlaps(self, window, tmp_path):
        """Check that no visible layout siblings overlap each other."""
        tab = window.extract_tab
        visible_widgets = [(w, w.geometry()) for w in visible_layout_widgets(tab)]

        overlaps = []
        for i, (w1, r1) in enumerate(visible_widgets):
            for w2, r2 in visible_widgets[i+1:]:
                if w1.parentWidget() is not w2.parentWidget():
                    continue
                if r1.intersects(r2):
                    name1 = w1.objectName() or w1.__class__.__name__
                    name2 = w2.objectName() or w2.__class__.__name__
                    if name1 != name2:
                        overlaps.append(f"{name1} intersects {name2}")

        if overlaps:
            screenshot = capture_widget(window, tmp_path, "overlap_detection")
            pytest.fail(
                f"Found {len(overlaps)} widget overlaps:\n" +
                "\n".join(overlaps[:10]) +
                f"\nScreenshot saved to: {screenshot}"
            )

    def test_initial_state_layout(self, window, tmp_path):
        """Verify the current initial state shows correctly without overflow."""
        tab = window.extract_tab
        tab._has_existing_score = False
        tab._video_path = None
        tab._update_state()
        process_events()

        screenshot = capture_widget(window, tmp_path, "state_initial")

        assert tab.status_label.isVisible(), "Status label should be visible"
        assert tab.crop_widget.isVisible(), "Crop widget should be visible"
        assert tab.seek_bar.isVisible(), "Seek bar should be visible"
        assert tab._scroll.isVisible(), "Scroll area should be visible"

    def test_video_loaded_state(self, window, tmp_path):
        """Verify state after video is loaded."""
        tab = window.extract_tab
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.write_bytes(b"dummy")
        tab._video_path = str(dummy_video)
        tab.project_edit.setText("TestScore")
        tab._update_state()
        process_events()

        screenshot = capture_widget(window, tmp_path, "state_video_loaded")

        assert tab.extract_btn.isVisible(), "Extract button should be visible"
        if not tab.extract_btn.isEnabled():
            screenshot = capture_widget(window, tmp_path, "state_video_loaded_disabled")
            pytest.fail(
                f"Extract button should be enabled when video and project are set. "
                f"Screenshot: {screenshot}"
            )

    def test_busy_state(self, window, tmp_path):
        """Verify state during extraction."""
        tab = window.extract_tab
        tab._busy = True
        tab._update_state()
        process_events()

        screenshot = capture_widget(window, tmp_path, "state_busy")

        assert tab.cancel_btn.isVisible(), "Cancel button should be visible"
        assert tab.cancel_btn.isEnabled(), "Cancel button should be enabled"
        assert not tab.extract_btn.isVisible(), "Extract button should be hidden"

    def test_completion_state(self, window, tmp_path):
        """Verify state after extraction completes."""
        tab = window.extract_tab
        tab._busy = False
        tab._has_existing_score = True
        tab._api.set_pages(make_dummy_frames(5))
        tab._update_state()
        process_events()

        screenshot = capture_widget(window, tmp_path, "state_completion")

        assert tab.generate_btn.isVisible(), "Generate button should be visible"
        assert tab.review_btn.isVisible(), "Review button should be visible"
        assert tab.reextract_btn.isVisible(), "Re-extract button should be visible"

    def test_pdf_ready_state(self, window, tmp_path):
        """Verify state after PDF is generated."""
        tab = window.extract_tab
        tab._busy = False
        tab._peak_style = True
        tab._completed_pdf_path = "dummy.pdf"
        tab._api.set_pages(make_dummy_frames(10))
        tab.on_pdf_completed(10)
        process_events()

        screenshot = capture_widget(window, tmp_path, "state_pdf_ready")

        assert tab.open_pdf_btn.isVisible(), "Open PDF button should be visible"
        assert tab.review_btn.isVisible(), "Review button should be visible"


class TestLabelOverflow:
    """Check that label text fits within widget bounds."""

    def test_status_label_fits(self, window, tmp_path):
        """Status label should not overflow with long text."""
        tab = window.extract_tab

        long_text = "This is a very long status message that should wrap properly"
        tab._set_status(long_text)
        process_events()

        screenshot = capture_widget(tab.status_label, tmp_path, "status_label_long")

        metrics = tab.status_label.fontMetrics()
        text_width = metrics.horizontalAdvance(long_text)
        label_width = tab.status_label.width()

        if tab.status_label.wordWrap():
            return

        if text_width > label_width:
            pytest.fail(
                f"Status label text ({text_width}px) wider than widget ({label_width}px). "
                f"Screenshot: {screenshot}"
            )

    def test_page_badge_fits(self, window, tmp_path):
        """Page badge should accommodate page count text."""
        tab = window.extract_tab

        tab.page_badge.setText("Pages: 999")
        process_events()

        screenshot = capture_widget(tab.page_badge, tmp_path, "page_badge")

        metrics = tab.page_badge.fontMetrics()
        text_width = metrics.horizontalAdvance("Pages: 999")
        badge_width = tab.page_badge.width()

        if text_width > badge_width:
            pytest.fail(
                f"Page badge text ({text_width}px) wider than widget ({badge_width}px). "
                f"Screenshot: {screenshot}"
            )

    def test_elapsed_label_fits(self, window, tmp_path):
        """Elapsed time label should fit time text."""
        tab = window.extract_tab

        tab._elapsed_label.setText("02:34:56")
        tab._elapsed_label.setVisible(True)
        process_events()

        screenshot = capture_widget(tab._elapsed_label, tmp_path, "elapsed_label")

        metrics = tab._elapsed_label.fontMetrics()
        text_width = metrics.horizontalAdvance("02:34:56")
        label_width = tab._elapsed_label.width()

        if text_width > label_width:
            pytest.fail(
                f"Elapsed label text ({text_width}px) wider than widget ({label_width}px). "
                f"Screenshot: {screenshot}"
            )

    def test_button_labels_fit(self, window, tmp_path):
        """All action buttons should fit their labels."""
        tab = window.extract_tab

        buttons = [
            (tab.extract_btn, "Start Extraction"),
            (tab.generate_btn, "Generate PDF"),
            (tab.review_btn, "Review Pages"),
            (tab.open_pdf_btn, "Open PDF"),
            (tab.cancel_btn, "Cancel"),
            (tab.reextract_btn, "Re-extract"),
        ]

        for btn, label in buttons:
            btn.setText(label)
            process_events()

            metrics = btn.fontMetrics()
            text_width = metrics.horizontalAdvance(label)

            btn_width = btn.width()
            contents_margins = btn.contentsMargins()
            available_width = btn_width - contents_margins.left() - contents_margins.right()

            if text_width > available_width:
                screenshot = capture_widget(btn, tmp_path, f"button_{btn.objectName()}")
                pytest.fail(
                    f"Button '{label}' text ({text_width}px) wider than available space "
                    f"({available_width}px). Screenshot: {screenshot}"
                )


class TestConfigTabLayout:
    """Validate ConfigTab widget geometry."""

    def test_basic_mode_layout(self, window, tmp_path):
        """Verify basic settings mode renders correctly."""
        tab = window.config_tab
        tab._set_mode("basic")
        window.tabs.setCurrentIndex(1)
        process_events()

        screenshot = capture_widget(window, tmp_path, "config_basic_mode")

        assert tab.basic_widget.isVisible(), "Basic widget should be visible"
        assert not tab.advanced_widget.isVisible(), "Advanced widget should be hidden"

    def test_advanced_mode_layout(self, window, tmp_path):
        """Verify advanced settings mode renders correctly."""
        tab = window.config_tab
        tab._set_mode("advanced")
        window.tabs.setCurrentIndex(1)
        process_events()

        screenshot = capture_widget(window, tmp_path, "config_advanced_mode")

        assert not tab.basic_widget.isVisible(), "Basic widget should be hidden"
        assert tab.advanced_widget.isVisible(), "Advanced widget should be visible"

    def test_basic_mode_has_only_common_settings(self, window):
        """Basic holds sensitivity, blank threshold and OCR; no format profiles."""
        tab = window.config_tab
        tab._set_mode("basic")
        process_events()

        assert tab.basic_widget.isAncestorOf(tab.sensitivity)
        assert tab.basic_widget.isAncestorOf(tab.blank_std)
        assert tab.basic_widget.isAncestorOf(tab.ocr_enabled)

        labels = {label.text() for label in tab.basic_widget.findChildren(QLabel)}
        assert "Page change sensitivity:" in labels
        assert "Blank page threshold:" in labels

        assert tab.basic_widget.findChildren(QComboBox) == []
        assert tab.advanced_widget.findChildren(QComboBox) == []


class TestExtractLayout:
    """Validate the refined Extract tab order and PDF mirror rules."""

    def test_pdf_name_sits_between_project_and_preview(self, window):
        tab = window.extract_tab
        window.show()
        process_events()

        assert tab.project_edit.geometry().y() < tab.pdf_name_edit.geometry().y()
        assert tab.pdf_name_edit.geometry().y() < tab.crop_widget.geometry().y()
        assert not hasattr(tab, "config_btn")

    def test_status_sits_below_seek_bar_and_above_progress(self, window):
        tab = window.extract_tab
        window.show()
        process_events()

        assert tab.seek_bar.geometry().y() < tab.status_label.geometry().y()
        assert tab.status_label.geometry().y() < tab.progress_bar.geometry().y()

    def test_every_combo_fits_its_longest_item(self, window):
        combos = window.findChildren(QComboBox)
        assert combos

        for combo in combos:
            metrics = combo.fontMetrics()
            widest = max(
                metrics.horizontalAdvance(combo.itemText(i))
                for i in range(combo.count())
            )
            assert combo.minimumWidth() >= widest + 40, (
                f"Combo {combo.currentText()!r} is too narrow for its options")

    def test_pdf_name_follows_project_until_edited(self, window):
        tab = window.extract_tab
        tab.project_edit.setText("Sonata")
        assert tab.pdf_name_edit.text() == "Sonata"

        tab.pdf_name_edit.setText("Printed")
        tab.project_edit.setText("Etude")
        assert tab.pdf_name_edit.text() == "Printed"

        tab.pdf_name_edit.setText("")
        assert tab.pdf_name_edit.text() == "Etude"


class TestFullWorkflow:
    """Drive through complete extraction workflow and capture each state."""

    def test_complete_workflow_visual(self, window, tmp_path):
        """Simulate full workflow and capture screenshots at each step."""
        tab = window.extract_tab
        output_dir = tmp_path / "workflow"

        screenshots = []

        tab._update_state()
        process_events()
        screenshots.append(capture_widget(window, output_dir, "01_initial"))

        dummy_video = tmp_path / "test_video.mp4"
        dummy_video.write_bytes(b"dummy")
        tab._video_path = str(dummy_video)
        tab.project_edit.setText("TestScore")
        tab._update_state()
        process_events()
        screenshots.append(capture_widget(window, output_dir, "02_ready"))

        tab._busy = True
        tab.progress_bar.setValue(25)
        tab._set_status("Extracting...")
        tab._update_state()
        process_events()
        screenshots.append(capture_widget(window, output_dir, "03_extracting_25"))

        tab.progress_bar.setValue(50)
        tab.page_badge.setText("Pages: 3")
        process_events()
        screenshots.append(capture_widget(window, output_dir, "04_extracting_50"))

        tab.progress_bar.setValue(100)
        process_events()
        screenshots.append(capture_widget(window, output_dir, "05_extracting_100"))

        tab._busy = False
        tab._has_existing_score = True
        tab._api.set_pages(make_dummy_frames(10))
        tab._update_state()
        process_events()
        screenshots.append(capture_widget(window, output_dir, "06_completed"))

        tab._peak_style = True
        tab._completed_pdf_path = "output/TestScore/TestScore.pdf"
        tab.on_pdf_completed(10)
        process_events()
        screenshots.append(capture_widget(window, output_dir, "07_pdf_ready"))

        summary = "\n".join(f"  - {s.name}" for s in screenshots)
        print(f"\nWorkflow screenshots saved to {output_dir}:\n{summary}")

        for screenshot in screenshots:
            assert screenshot.exists(), f"Screenshot not created: {screenshot}"


class TestMinimumWindowSize:
    """Verify layout works at minimum window size."""

    def test_minimum_size_no_clipping(self, window, tmp_path):
        """Window at minimum size should not clip critical widgets."""
        window.resize(window.minimumWidth(), window.minimumHeight())
        process_events()

        screenshot = capture_widget(window, tmp_path, "minimum_size")

        tab = window.extract_tab
        critical_widgets = [
            tab.extract_btn,
            tab.project_edit,
            tab.status_label,
        ]

        for widget in critical_widgets:
            geo = widget.geometry()
            if geo.width() <= 0 or geo.height() <= 0:
                pytest.fail(
                    f"Widget {widget.__class__.__name__} has zero size at minimum window. "
                    f"Screenshot: {screenshot}"
                )

    def test_minimum_size_uses_scroll(self, window, tmp_path):
        """The tab scrolls instead of overlapping when content does not fit."""
        window.resize(window.minimumWidth(), window.minimumHeight())
        tab = window.extract_tab
        tab._busy = False
        tab._has_existing_score = True
        tab._api.set_pages(make_dummy_frames(2))
        tab._update_state()
        process_events()

        screenshot = capture_widget(window, tmp_path, "minimum_size_scroll")

        assert tab._scroll.verticalScrollBar().maximum() > 0, (
            "Content should scroll at the minimum window height")
        assert tab.crop_widget.geometry().bottom() < tab.crop_mode_combo.geometry().top(), (
            "Crop preview must not overlap the crop controls")
        assert tab.generate_btn.isVisible(), "Action bar should stay visible"
        assert tab.generate_btn.isEnabled(), "Generate PDF should be enabled"
        assert tab.generate_btn.geometry().bottom() <= tab.height(), (
            f"Action bar is clipped below the tab. Screenshot: {screenshot}")


class TestCustomWidgets:
    """Validate custom widget rendering."""

    def test_crop_preview_widget(self, window, tmp_path):
        """CropPreviewWidget should render without errors."""
        tab = window.extract_tab
        tab._update_state()
        process_events()

        screenshot = capture_widget(tab.crop_widget, tmp_path, "crop_preview")

        assert tab.crop_widget.isVisible(), "Crop widget should be visible"
        assert tab.crop_widget.width() > 0, "Crop widget should have width"
        assert tab.crop_widget.height() > 0, "Crop widget should have height"

    def test_seek_bar_widget(self, window, tmp_path):
        """DualHandleSeekBar should render without errors."""
        tab = window.extract_tab
        tab._update_state()
        process_events()

        screenshot = capture_widget(tab.seek_bar, tmp_path, "seek_bar")

        assert tab.seek_bar.isVisible(), "Seek bar should be visible"
        assert tab.seek_bar.width() > 0, "Seek bar should have width"
        assert tab.seek_bar.height() > 0, "Seek bar should have height"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
