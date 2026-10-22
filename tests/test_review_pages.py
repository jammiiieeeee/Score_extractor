"""Tests for the page review loop and completion peak in the GUI.

Covers the brass live page-count badge, the ReviewPagesDialog keep-mask,
and the store/file removal mapping (disk files are numbered by extraction
attempt, so gaps exist when duplicates were skipped).
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
