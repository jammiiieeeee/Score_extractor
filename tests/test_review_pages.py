"""Tests for the page review window and completion peak in the GUI.

Covers the brass live page-count badge, the PDF-like ReviewPagesDialog
(title, capture labels, zoom), and the store/file removal mapping (disk
files are numbered by extraction attempt, so gaps exist when duplicates
were skipped).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

pytestmark = pytest.mark.unit

from src.api.gui_api import GuiApi
from app_gui import MainWindow, ReviewPagesDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp):
    mw = MainWindow()
    yield mw.extract_tab
    mw.close()


def _page_png(width: int = 160, height: int = 60) -> bytes:
    ok, buf = cv2.imencode(".png", np.full((height, width, 3), 200, dtype=np.uint8))
    assert ok
    return buf.tobytes()


class FakePageApi:
    def __init__(self, count: int, png: bytes | None = None):
        self.count = count
        self._png = png or _page_png()

    def get_page_count(self):
        return self.count

    def get_page_cropped(self, index: int):
        return self._png

    def get_page(self, index: int):
        class _Page:
            attempt_number = index + 1
        return _Page()


class TestReviewPagesDialog:
    def test_stacks_pages_onto_a4_sheets_like_the_pdf(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(10), "Sonata")
        dlg.show()
        qapp.processEvents()
        assert dlg._count == 10
        assert len(dlg._view._sheets) < dlg._count
        packed = sum(len(s._items) for s in dlg._view._sheets)
        assert packed == 10
        assert "10 captured" in dlg.windowTitle()
        dlg.close()

    def test_first_sheet_carries_the_title(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(10), "Sonata")
        assert dlg._view._sheets[0]._title == "Sonata"
        assert all(s._title == "" for s in dlg._view._sheets[1:])
        dlg.close()

    def test_capture_labels_sit_outside_the_sheets(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(10), "Sonata")
        dlg.show()
        qapp.processEvents()
        assert [label.text() for label in dlg._view._labels] == [
            str(i) for i in range(1, 11)]
        sheet_left = min(s.geometry().left() for s in dlg._view._sheets)
        for label in dlg._view._labels:
            assert label.geometry().right() < sheet_left
        dlg.close()

    def test_fit_width_is_the_default(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(2), "Sonata")
        dlg.show()
        qapp.processEvents()
        assert dlg.is_fit_width() is True
        assert dlg._zoom_label.text() == "Fit width"
        dlg.close()

    def test_100_percent_control(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(2), "Sonata")
        dlg.set_zoom_percent(100)
        assert dlg.is_fit_width() is False
        assert dlg.zoom_percent() == 100
        assert dlg._zoom_label.text() == "100%"
        dlg.close()

    def test_wheel_zoom_leaves_fit_width(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(2), "Sonata")
        dlg.set_zoom_percent(100)
        dlg._zoom_by(1.15)
        assert dlg.is_fit_width() is False
        assert dlg.zoom_percent() == 115
        dlg.close()

    def test_opens_at_the_top(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(2), "Sonata")
        dlg.show()
        qapp.processEvents()
        assert dlg._scroll.verticalScrollBar().value() == 0
        dlg.close()


class TestReviewTitle:
    def test_pdf_name_wins(self, tab):
        tab.project_edit.setText("Project")
        tab.pdf_name_edit.setText("Printed")
        assert tab._review_title() == "Printed"

    def test_project_name_is_the_fallback(self, tab):
        tab.project_edit.setText("Project")
        tab.pdf_name_edit.setText("")
        assert tab._review_title() == "Project"

    def test_review_pages_opens_the_window(self, tab, monkeypatch):
        calls = []

        class FakeDialog:
            def __init__(self, api, title, parent):
                calls.append(title)

            def exec(self):
                return 0

        monkeypatch.setattr("app_gui.ReviewPagesDialog", FakeDialog)
        tab._api.get_page_count = lambda: 2
        tab.project_edit.setText("Project")
        tab.pdf_name_edit.setText("Printed")

        tab._on_review_pages()

        assert calls == ["Printed"]


class TestPageBadge:
    def test_updates_live_and_clears_on_reset(self, tab):
        tab.on_page_detected(0, b"")
        assert tab.page_badge.text() == "Pages: 1"
        tab.on_page_detected(4, b"")
        assert tab.page_badge.text() == "Pages: 5"
        tab._reset_ui()
        assert tab.page_badge.text() == ""


class TestCompletionPeak:
    def test_peak_status_and_review_button(self, tab):
        tab.on_pdf_completed(7)
        assert tab.status_label.text() == "Score ready — 7 pages in the PDF"
        assert tab._peak_style is True
        assert tab.status_label.property("class") == "count"
        assert not tab.review_btn.isHidden()
        assert tab.page_badge.text() == "Pages: 7"

    def test_peak_clears_when_status_reset(self, tab):
        tab.on_pdf_completed(3)
        tab._set_status("back to work")
        assert tab._peak_style is False
        assert tab.status_label.property("class") == "muted"


class TestGeneratingPdfFlag:
    """MainWindow must only arm _generating_pdf when on_completed started the PDF."""

    def test_flag_stays_clear_when_no_pdf_started(self, tab):
        mw = tab.window()
        mw._generating_pdf = False
        # Review dropped every page -> on_completed returns False
        mw.extract_tab.on_completed = lambda _page_count: False
        mw._on_completed(5)
        assert mw._generating_pdf is False

    def test_flag_arms_when_pdf_started(self, tab):
        mw = tab.window()
        mw._generating_pdf = False
        mw.extract_tab.on_completed = lambda _page_count: True
        mw._on_completed(5)
        assert mw._generating_pdf is True


class TestPageRemovals:
    """Removing a page deletes that page's file and no other."""

    def _saved_score(self, tmp_path, names):
        """A score on disk with the given page files, loaded into the API."""
        photos = tmp_path / "photos"
        photos.mkdir(parents=True, exist_ok=True)
        paths = []
        for name in names:
            path = photos / name
            cv2.imwrite(str(path), np.full((40, 40, 3), 90, dtype=np.uint8))
            paths.append(path)
        api = GuiApi()
        api.load_saved_score(str(tmp_path))
        return api, paths

    def test_removes_correct_files_despite_gaps(self, tab, tmp_path):
        api, paths = self._saved_score(
            tmp_path, ["page_001_merged.png", "page_003_merged.png", "page_005_merged.png"]
        )
        tab._api = api

        tab._apply_page_removals([1])

        # The page knows its own file, so the file that goes is page_003 -
        # the page_002 that never existed (duplicate attempts were skipped)
        # is not touched, and neither is any other page's file.
        remaining = sorted(p.name for p in (tmp_path / "photos").iterdir())
        assert remaining == ["page_001_merged.png", "page_005_merged.png"], remaining
        assert api.get_page_count() == 2
        api.cleanup()

    def test_removes_multiple_highest_first(self, tab, tmp_path):
        api, paths = self._saved_score(tmp_path, [
            "page_001_merged.png", "page_002_merged.png", "page_003_merged.png",
            "page_004_merged.png", "page_005_merged.png",
        ])
        tab._api = api

        tab._apply_page_removals([1, 3])

        remaining = sorted(p.name for p in (tmp_path / "photos").iterdir())
        assert remaining == ["page_001_merged.png", "page_003_merged.png", "page_005_merged.png"]
        assert api.get_page_count() == 3
        api.cleanup()

    def test_removing_all_leaves_empty_photos(self, tab, tmp_path):
        api, paths = self._saved_score(
            tmp_path, ["page_001_merged.png", "page_003_merged.png"]
        )
        tab._api = api

        tab._apply_page_removals([0, 1])

        remaining = sorted(p.name for p in (tmp_path / "photos").iterdir())
        assert remaining == []
        assert api.get_page_count() == 0
        api.cleanup()

    def test_the_removed_page_takes_its_own_file(self, tab, tmp_path):
        api, paths = self._saved_score(
            tmp_path, ["page_001_merged.png", "page_003_merged.png", "page_005_merged.png"]
        )
        tab._api = api

        tab._apply_page_removals([1])

        assert not paths[1].exists()
        assert paths[0].exists()
        assert paths[2].exists()
        api.cleanup()
