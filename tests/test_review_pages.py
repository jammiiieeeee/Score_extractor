"""Tests for the page review window and completion peak in the GUI.

Covers the brass live page-count badge, the PDF-like ReviewPagesDialog
(title, capture labels, zoom), and the store/file removal mapping (disk
files are numbered by extraction attempt, so gaps exist when duplicates
were skipped).
"""

import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

pytestmark = pytest.mark.unit

from src.api.gui_api import GuiApi
from src.domain.models import Page, PageStatus
from app_gui import MainWindow, ReviewPagesDialog, TrashDialog


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
        for _ in range(7):
            tab._api.add_page(np.full((60, 160, 3), 200, dtype=np.uint8))
        tab.on_pdf_completed(7)
        assert tab.status_label.text() == "Score ready — 7 pages in the PDF"
        assert tab._peak_style is True
        assert tab.status_label.property("class") == "count"
        assert not tab.review_btn.isHidden()
        assert not tab.generate_btn.isHidden()
        assert tab.page_badge.text() == "Pages: 7"
        tab._api.clear_pages()

    def test_peak_clears_when_status_reset(self, tab):
        for _ in range(3):
            tab._api.add_page(np.full((60, 160, 3), 200, dtype=np.uint8))
        tab.on_pdf_completed(3)
        tab._set_status("back to work")
        assert tab._peak_style is False
        assert tab.status_label.property("class") == "muted"
        tab._api.clear_pages()


class TestExtractionReviewFlow:
    """Extraction ends in Review Pages; the PDF waits for the user."""

    @staticmethod
    def _count_reviews(monkeypatch, tab):
        calls = []

        class FakeDialog:
            def __init__(self, api, title, parent):
                calls.append(title)

            def exec(self):
                return 0

        monkeypatch.setattr("app_gui.ReviewPagesDialog", FakeDialog)
        tab._api.generate_pdf = MagicMock()
        return calls

    def test_completion_opens_review_and_stays_on_the_main_screen(
            self, tab, monkeypatch):
        calls = self._count_reviews(monkeypatch, tab)
        tab._busy = True
        tab._reextract_mode = False
        tab.project_edit.setText("Project")
        tab.pdf_name_edit.setText("Printed")

        started_pdf = tab.on_completed(4)

        assert calls == ["Printed"]
        assert started_pdf is False
        tab._api.generate_pdf.assert_not_called()
        assert tab._busy is False

    def test_cancel_with_pages_opens_review_and_does_not_generate(
            self, tab, monkeypatch):
        calls = self._count_reviews(monkeypatch, tab)
        tab._busy = True
        tab._video_path = None
        tab._yt_video_paths = []
        tab.project_edit.setText("Project")

        tab.on_cancelled_with_pages(3)

        assert calls == ["Project"]
        tab._api.generate_pdf.assert_not_called()
        assert tab._busy is False

    def test_closing_review_returns_with_flags_saved(self, tab, monkeypatch):
        calls = self._count_reviews(monkeypatch, tab)
        tab._api.add_page(np.full((60, 160, 3), 200, dtype=np.uint8))
        tab._busy = True

        tab.on_completed(1)

        assert calls
        assert tab._busy is False
        assert tab._has_existing_score is True
        tab._api.clear_pages()


class TestPdfGating:
    """Generate PDF is enabled only while a page is included."""

    @staticmethod
    def _api_with_statuses(tab, statuses):
        tab._api.clear_pages()
        for status in statuses:
            tab._api.add_page(
                np.full((60, 160, 3), 200, dtype=np.uint8), status=status)

    def test_generate_is_enabled_when_a_page_is_kept(self, tab):
        self._api_with_statuses(
            tab, [PageStatus.KEEP, PageStatus.DUPLICATE])
        tab._busy = False

        tab._update_state()

        assert tab.generate_btn.isEnabled()
        assert tab.generate_btn.text() == "Generate PDF"

    def test_generate_is_disabled_when_nothing_is_included(self, tab):
        self._api_with_statuses(
            tab, [PageStatus.DUPLICATE, PageStatus.EXCLUDED])
        tab._busy = False

        tab._update_state()

        assert not tab.generate_btn.isEnabled()
        assert "No pages included" in tab.status_label.text()

    def test_generate_refuses_when_nothing_is_included(self, tab, monkeypatch):
        self._api_with_statuses(tab, [PageStatus.EXCLUDED])
        tab.project_edit.setText("Score")
        warnings = []
        monkeypatch.setattr(
            "app_gui.QMessageBox.warning",
            lambda *args, **kwargs: warnings.append(args))
        tab._api.generate_pdf = MagicMock()

        tab._generate_pdf()

        assert warnings and "No Pages Included" in warnings[0][1]
        tab._api.generate_pdf.assert_not_called()

    def test_loaded_score_review_updates_gating_without_regenerating(
            self, tab, monkeypatch):
        self._api_with_statuses(tab, [PageStatus.KEEP])
        tab._has_existing_score = True
        tab._busy = False
        tab._api.generate_pdf = MagicMock()
        calls = []

        class FakeDialog:
            def __init__(self, api, title, parent):
                calls.append(title)
                for index in range(api.get_page_count()):
                    api.set_page_status(index, PageStatus.EXCLUDED)

            def exec(self):
                return 0

        monkeypatch.setattr("app_gui.ReviewPagesDialog", FakeDialog)

        tab._on_review_pages()

        assert calls
        tab._api.generate_pdf.assert_not_called()
        assert not tab.generate_btn.isEnabled()
        assert "No pages included" in tab.status_label.text()


class TestIncludedPageCount:
    def test_counts_only_kept_pages(self):
        api = GuiApi()
        api.add_page(np.full((20, 20, 3), 10, dtype=np.uint8))
        api.add_page(np.full((20, 20, 3), 20, dtype=np.uint8),
                     status=PageStatus.DUPLICATE)
        api.add_page(np.full((20, 20, 3), 30, dtype=np.uint8),
                     status=PageStatus.EXCLUDED)

        assert api.get_page_count() == 3
        assert api.get_included_page_count() == 1
        api.cleanup()


class TestDuplicateMarking:
    """Clicking pages marks duplicates without deleting them."""

    @staticmethod
    def _api(count: int) -> GuiApi:
        api = GuiApi()
        for _ in range(count):
            api.add_page(np.full((60, 160, 3), 200, dtype=np.uint8))
        return api

    def test_click_toggles_duplicate_and_updates_the_count(self, qapp):
        api = self._api(4)
        dlg = ReviewPagesDialog(api, "Sonata")

        dlg._on_page_clicked(1, False)
        assert api.get_page(1).status is PageStatus.DUPLICATE
        assert dlg._dup_label.text() == "1 duplicate"

        dlg._on_page_clicked(1, False)
        assert api.get_page(1).status is PageStatus.KEEP
        assert dlg._dup_label.text() == "0 duplicates"
        assert api.get_page_count() == 4
        dlg.close()
        api.cleanup()

    def test_shift_click_marks_the_range(self, qapp):
        api = self._api(5)
        dlg = ReviewPagesDialog(api, "Sonata")

        dlg._on_page_clicked(1, False)
        dlg._on_page_clicked(3, True)

        assert {i for i in range(5) if api.get_page(i).status is PageStatus.DUPLICATE} == {
            1, 2, 3}
        assert dlg._dup_label.text() == "3 duplicates"
        dlg.close()
        api.cleanup()

    def test_d_toggles_the_page_under_the_mouse(self, qapp):
        api = self._api(3)
        dlg = ReviewPagesDialog(api, "Sonata")
        dlg._view._hover_index = 2

        QTest.keyClick(dlg, Qt.Key.Key_D)

        assert api.get_page(2).status is PageStatus.DUPLICATE
        dlg.close()
        api.cleanup()

    def test_page_at_maps_a_point_to_its_page(self, qapp):
        api = self._api(3)
        dlg = ReviewPagesDialog(api, "Sonata")
        sheet = dlg._view._sheets[0]
        _index, _pixmap, x, y, _w, _h = sheet._items[0]
        point = sheet.pos() + QPoint(
            round((x + 1) * sheet._scale), round((y + 1) * sheet._scale))

        assert dlg._view.page_at(point) == 0
        dlg.close()
        api.cleanup()

    def test_the_flag_persists_in_the_saved_score(self, qapp, tmp_path):
        photos = tmp_path / "photos"
        photos.mkdir(parents=True)
        for name in ["page_001_merged.png", "page_002_merged.png"]:
            cv2.imwrite(str(photos / name), np.full((40, 40, 3), 90, dtype=np.uint8))
        api = GuiApi()
        api.load_saved_score(str(tmp_path))
        dlg = ReviewPagesDialog(api, "Sonata")

        dlg._on_page_clicked(1, False)
        dlg.close()
        api.cleanup()

        reloaded = GuiApi()
        reloaded.load_saved_score(str(tmp_path))
        assert reloaded.get_page(1).status is PageStatus.DUPLICATE
        assert reloaded.get_page(0).status is PageStatus.KEEP
        reloaded.cleanup()


class TestExclusion:
    """Excluding a page hides it, trashes it, and can be undone."""

    @staticmethod
    def _api(count: int) -> GuiApi:
        api = GuiApi()
        api.set_pages([
            Page(image=np.full((60, 160, 3), 200, dtype=np.uint8),
                 attempt_number=i + 1)
            for i in range(count)
        ])
        return api

    @staticmethod
    def _visible(dlg) -> set[int]:
        return {index for sheet in dlg._view._sheets for index, *_ in sheet._items}

    def test_exclude_replaces_the_duplicate_flag_and_leaves_the_scroll(self, qapp):
        api = self._api(4)
        dlg = ReviewPagesDialog(api, "Sonata")
        dlg._on_page_clicked(1, False)

        dlg._on_exclude(1)

        assert api.get_page(1).status is PageStatus.EXCLUDED
        assert dlg._dup_label.text() == "0 duplicates"
        assert dlg._trash_label.text() == "1 in trash"
        assert self._visible(dlg) == {0, 2, 3}
        dlg.close()
        api.cleanup()

    def test_e_excludes_the_page_under_the_mouse(self, qapp):
        api = self._api(3)
        dlg = ReviewPagesDialog(api, "Sonata")
        dlg._view._hover_index = 2

        QTest.keyClick(dlg, Qt.Key.Key_E)

        assert api.get_page(2).status is PageStatus.EXCLUDED
        assert self._visible(dlg) == {0, 1}
        dlg.close()
        api.cleanup()

    def test_right_click_excludes_the_page(self, qapp):
        api = self._api(3)
        dlg = ReviewPagesDialog(api, "Sonata")
        dlg.show()
        qapp.processEvents()
        sheet = dlg._view._sheets[0]
        index, _pixmap, x, y, _w, _h = sheet._items[0]
        point = sheet.pos() + QPoint(
            round((x + 1) * sheet._scale), round((y + 1) * sheet._scale))

        QTest.mouseClick(dlg._view, Qt.MouseButton.RightButton, pos=point)

        assert api.get_page(index).status is PageStatus.EXCLUDED
        dlg.close()
        api.cleanup()

    def test_trash_lists_excluded_pages_and_restores_them(self, qapp):
        api = self._api(4)
        dlg = ReviewPagesDialog(api, "Sonata")
        dlg._on_exclude(1)
        dlg._on_exclude(3)
        trash = TrashDialog(api, dlg._excluded, dlg._restore_page)

        assert trash._list.count() == 2
        assert [trash._list.item(i).text() for i in range(2)] == [
            str(api.get_page(1).attempt_number),
            str(api.get_page(3).attempt_number),
        ]

        trash._list.setCurrentRow(0)
        trash._restore()

        assert api.get_page(1).status is PageStatus.KEEP
        assert self._visible(dlg) == {0, 1, 2}
        assert trash._list.count() == 1
        assert dlg._trash_label.text() == "1 in trash"
        trash.close()
        dlg.close()
        api.cleanup()

    def test_exclusion_persists_and_keeps_the_page_file(self, qapp, tmp_path):
        photos = tmp_path / "photos"
        photos.mkdir(parents=True)
        paths = []
        for name in ["page_001_merged.png", "page_002_merged.png"]:
            path = photos / name
            cv2.imwrite(str(path), np.full((40, 40, 3), 90, dtype=np.uint8))
            paths.append(path)
        api = GuiApi()
        api.load_saved_score(str(tmp_path))
        dlg = ReviewPagesDialog(api, "Sonata")

        dlg._on_exclude(1)
        dlg.close()
        api.cleanup()

        assert paths[1].exists()
        reloaded = GuiApi()
        reloaded.load_saved_score(str(tmp_path))
        assert reloaded.get_page(1).status is PageStatus.EXCLUDED
        assert reloaded.get_page(0).status is PageStatus.KEEP
        reloaded.cleanup()

    def test_d_after_exclude_does_not_revive_the_hidden_page(self, qapp):
        api = self._api(3)
        dlg = ReviewPagesDialog(api, "Sonata")
        dlg._view._hover_index = 1

        dlg._on_exclude(1)
        QTest.keyClick(dlg, Qt.Key.Key_D)

        assert api.get_page(1).status is PageStatus.EXCLUDED
        assert dlg._trash_label.text() == "1 in trash"
        dlg.close()
        api.cleanup()

    def test_a_duplicate_range_skips_excluded_pages(self, qapp):
        api = self._api(4)
        dlg = ReviewPagesDialog(api, "Sonata")
        dlg._on_exclude(2)

        dlg._on_page_clicked(1, False)
        dlg._on_page_clicked(3, True)

        assert {i for i in range(4) if api.get_page(i).status is PageStatus.DUPLICATE} == {
            1, 3}
        assert api.get_page(2).status is PageStatus.EXCLUDED
        dlg.close()
        api.cleanup()


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
