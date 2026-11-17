"""Tests for the Library tab — a browsable catalog of saved projects."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

pytestmark = pytest.mark.unit

from app_gui import LibraryTab, MainWindow
from src.api.gui_api import ScoreInfo


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeApi:
    def __init__(self, scores=None):
        self.scores = list(scores or [])
        self.deleted = []

    def list_saved_scores(self, folder):
        return list(self.scores)

    def delete_saved_score(self, path):
        self.deleted.append(path)
        self.scores = [s for s in self.scores if s.path != path]


def _score(name, pages=3, modified=0.0):
    return ScoreInfo(
        path=str(Path("output") / name),
        page_count=pages,
        score_name=name,
        modified=modified,
    )


@pytest.fixture
def library(qapp):
    api = FakeApi([
        _score("alpha", pages=2, modified=100.0),
        _score("beta", pages=7, modified=300.0),
        _score("gamma", pages=1, modified=200.0),
    ])
    tab = LibraryTab(api, lambda: "output")
    yield tab, api
    tab.deleteLater()


class TestCatalog:

    def test_one_card_per_project(self, library):
        tab, _ = library
        assert len(tab._cards) == 3
        assert {c.info.score_name for c in tab._cards} == {
            "alpha", "beta", "gamma"}

    def test_newest_first_by_default(self, library):
        tab, _ = library
        assert [c.info.score_name for c in tab._cards] == [
            "beta", "gamma", "alpha"]

    def test_sort_by_name(self, library):
        tab, _ = library
        tab._sort_combo.setCurrentIndex(1)
        assert [c.info.score_name for c in tab._cards] == [
            "alpha", "beta", "gamma"]

    def test_sort_by_most_pages(self, library):
        tab, _ = library
        tab._sort_combo.setCurrentIndex(2)
        assert [c.info.score_name for c in tab._cards] == [
            "beta", "alpha", "gamma"]

    def test_filter_hides_non_matching_projects(self, library):
        tab, _ = library
        tab._filter_edit.setText("be")
        assert [c.info.score_name for c in tab._cards] == ["beta"]
        assert tab._count_label.text() == "1 project"

    def test_filter_without_match_shows_empty_state(self, library):
        tab, _ = library
        tab._filter_edit.setText("nothing")
        assert tab._cards == []
        assert tab._stack.currentWidget() is tab._empty_page
        assert "filter" in tab._empty_title.text().lower()

    def test_empty_output_shows_empty_state(self, qapp):
        tab = LibraryTab(FakeApi(), lambda: "output")
        assert tab._cards == []
        assert tab._stack.currentWidget() is tab._empty_page
        assert tab._empty_title.text() == "No saved projects yet"


class TestCardActions:

    def test_click_opens_the_project(self, library):
        tab, _ = library
        opened = []
        tab.open_requested.connect(opened.append)
        card = tab._cards[0]
        QTest.mouseClick(card, Qt.MouseButton.LeftButton)
        assert opened == [card.info.path]

    def test_enter_key_opens_the_project(self, library):
        tab, _ = library
        opened = []
        tab.open_requested.connect(opened.append)
        card = tab._cards[0]
        QTest.keyClick(card, Qt.Key.Key_Return)
        assert opened == [card.info.path]

    def test_delete_removes_the_project_after_confirmation(
            self, library, monkeypatch):
        tab, api = library
        deleted = []
        tab.project_deleted.connect(deleted.append)
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **k: QMessageBox.StandardButton.Yes)

        target = tab._cards[0].info
        tab._confirm_delete(target)

        assert api.deleted == [target.path]
        assert deleted == [target.path]
        assert target.score_name not in [c.info.score_name for c in tab._cards]

    def test_delete_cancelled_keeps_the_project(self, library, monkeypatch):
        tab, api = library
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **k: QMessageBox.StandardButton.No)

        tab._confirm_delete(tab._cards[0].info)

        assert api.deleted == []
        assert len(tab._cards) == 3


class TestWindowIntegration:

    def test_window_has_a_library_tab(self, qapp):
        window = MainWindow()
        try:
            assert window.tabs.tabText(1) == "Library"
            assert window.tabs.widget(1) is window.library_tab
        finally:
            window.close()

    def test_opening_a_card_loads_it_into_extract(self, qapp, tmp_path):
        score_dir = tmp_path / "my_score"
        photos = score_dir / "photos"
        photos.mkdir(parents=True)
        image = np.full((60, 40, 3), 200, dtype=np.uint8)
        cv2.imwrite(str(photos / "page_001_merged.png"), image)

        window = MainWindow()
        try:
            window.extract_tab._parent_dir = str(tmp_path)
            window.library_tab.refresh()
            assert len(window.library_tab._cards) == 1

            window.library_tab._cards[0].open_requested.emit(str(score_dir))

            assert window.tabs.currentWidget() is window.extract_tab
            assert window.extract_tab.project_edit.text() == "my_score"
            assert window.api.get_page_count() == 1
        finally:
            window.close()
