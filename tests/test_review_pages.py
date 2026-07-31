"""Tests for the page review loop and completion peak in the GUI.

Covers the brass live page-count badge, the ReviewPagesDialog keep-mask,
and the store/file removal mapping (disk files are numbered by extraction
attempt, so gaps exist when duplicates were skipped).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


class FakePageApi:
    def __init__(self, count: int):
        self.count = count

    def get_page_count(self):
        return self.count

    def get_page_thumbnail(self, index: int):
        return b"thumb" + str(index).encode()

    def get_page_full(self, index: int):
        return b"full" + str(index).encode()


class TestReviewPagesDialog:
    def test_all_kept_by_default(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(4))
        assert dlg._count == 4
        assert dlg.kept_mask() == [True, True, True, True]
        assert dlg._summary.text() == "All pages will be in the PDF."
        dlg.close()

    def test_unchecking_updates_mask_and_summary(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(3))
        dlg._checks[1].setChecked(False)
        assert dlg.kept_mask() == [True, False, True]
        assert "2 of 3" in dlg._summary.text()
        dlg._checks[0].setChecked(False)
        assert dlg.kept_mask() == [False, False, True]
        assert "1 of 3" in dlg._summary.text()
        dlg.close()

    def test_checked_state_survives_mask_query(self, qapp):
        dlg = ReviewPagesDialog(FakePageApi(2))
        dlg._checks[0].setChecked(False)
        dlg._checks[1].setChecked(False)
        assert dlg.kept_mask() == [False, False]
        dlg._checks[0].setChecked(True)
        assert dlg.kept_mask() == [True, False]
        dlg.close()


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
        assert "#d4a843" in tab.status_label.styleSheet()
        assert not tab.review_btn.isHidden()
        assert tab.page_badge.text() == "Pages: 7"

    def test_peak_clears_when_status_reset(self, tab):
        tab.on_pdf_completed(3)
        tab._set_status("back to work")
        assert tab._peak_style is False
        assert tab.status_label.styleSheet() == ""


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
    class FakeStore:
        def __init__(self, count: int):
            self.pages = list(range(count))
            self.removed = []

        def remove_page(self, index: int):
            self.pages.pop(index)

        def get_page_count(self):
            return len(self.pages)

    def _make_project(self, tab, tmp_path, files):
        tab.project_edit.setText("ReviewTest")
        tab._parent_dir = str(tmp_path)
        photos = tmp_path / "ReviewTest" / "photos"
        photos.mkdir(parents=True, exist_ok=True)
        for name in files:
            (photos / name).write_bytes(b"x")

    def test_removes_correct_files_despite_gaps(self, tab, tmp_path):
        files = ["page_001_merged.png", "page_003_merged.png", "page_005_merged.png"]
        self._make_project(tab, tmp_path, files)
        store = self.FakeStore(3)
        tab._api = store

        tab._apply_page_removals([1])

        # Store index 1 maps to the 2nd file in sorted order (page_003),
        # not to page_002 which never existed (duplicate attempts were skipped).
        remaining = sorted(p.name for p in (tmp_path / "ReviewTest" / "photos").iterdir())
        assert remaining == ["page_001_merged.png", "page_005_merged.png"], remaining
        assert store.pages == [0, 2]

    def test_removes_multiple_highest_first(self, tab, tmp_path):
        files = [
            "page_001_merged.png", "page_002_merged.png", "page_003_merged.png",
            "page_004_merged.png", "page_005_merged.png",
        ]
        self._make_project(tab, tmp_path, files)
        store = self.FakeStore(5)
        tab._api = store

        tab._apply_page_removals([1, 3])

        remaining = sorted(p.name for p in (tmp_path / "ReviewTest" / "photos").iterdir())
        assert remaining == ["page_001_merged.png", "page_003_merged.png", "page_005_merged.png"]
        assert store.pages == [0, 2, 4]

    def test_removing_all_leaves_empty_photos(self, tab, tmp_path):
        self._make_project(tab, tmp_path, ["page_001_merged.png", "page_003_merged.png"])
        store = self.FakeStore(2)
        tab._api = store

        tab._apply_page_removals([0, 1])

        remaining = sorted(p.name for p in (tmp_path / "ReviewTest" / "photos").iterdir())
        assert remaining == []
        assert store.pages == []
