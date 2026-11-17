"""The projects folder lives in Settings, not next to the project name."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QFileDialog

pytestmark = pytest.mark.unit

from app_gui import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    window = MainWindow()
    # Point both tabs at throwaway settings so the real app is untouched.
    window.extract_tab._settings = QSettings(
        str(tmp_path / "extract.ini"), QSettings.Format.IniFormat)
    window.config_tab._settings = QSettings(
        str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    yield window
    window.close()


def _make_project(root, name, pages=1):
    photos = Path(root) / name / "photos"
    photos.mkdir(parents=True)
    image = np.full((60, 40, 3), 200, dtype=np.uint8)
    for i in range(1, pages + 1):
        cv2.imwrite(str(photos / f"page_{i:03d}_merged.png"), image)
    return str(Path(root) / name)


class TestSettingsRow:

    def test_shows_the_current_projects_folder(self, window):
        assert (window.config_tab.projects_folder_edit.text()
                == window.extract_tab.get_parent_dir())

    def test_the_path_cannot_be_typed(self, window):
        assert window.config_tab.projects_folder_edit.isReadOnly()

    def test_stays_visible_in_advanced_mode(self, window):
        window.config_tab._set_mode("advanced")
        assert window.config_tab.projects_folder_edit.isVisibleTo(
            window.config_tab)

    def test_the_extract_tab_has_no_browse_button(self, window):
        assert not hasattr(window.extract_tab, "project_browse_btn")
        assert not hasattr(window.extract_tab, "_browse_project")


class TestChangingFolder:

    def test_moves_the_projects_root(self, window, tmp_path, monkeypatch):
        target = tmp_path / "scores"
        target.mkdir()
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *a, **k: str(target))

        window.config_tab._choose_projects_folder()

        assert window.extract_tab.get_parent_dir() == str(target)
        assert window.config_tab.projects_folder_edit.text() == str(target)

    def test_the_library_follows_the_new_folder(
            self, window, tmp_path, monkeypatch):
        target = tmp_path / "scores"
        _make_project(target, "new_song")
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *a, **k: str(target))

        window.config_tab._choose_projects_folder()
        window.library_tab.refresh()

        assert [c.info.score_name for c in window.library_tab._cards] == [
            "new_song"]

    def test_resets_a_project_loaded_from_the_old_folder(
            self, window, tmp_path, monkeypatch):
        old_root = tmp_path / "old"
        _make_project(old_root, "Song", pages=2)
        window.extract_tab._parent_dir = str(old_root)
        window.extract_tab.project_edit.setText("Song")
        window.extract_tab._on_project_entered()
        assert window.api.get_page_count() == 2

        target = tmp_path / "new"
        target.mkdir()
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *a, **k: str(target))
        window.config_tab._choose_projects_folder()

        assert window.api.get_page_count() == 0
        assert not window.api.has_loaded_score()
        assert window.extract_tab.project_edit.text() == "Song"

    def test_cancelling_the_picker_changes_nothing(
            self, window, tmp_path, monkeypatch):
        before = window.extract_tab.get_parent_dir()
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *a, **k: "")

        window.config_tab._choose_projects_folder()

        assert window.extract_tab.get_parent_dir() == before
