"""Unit tests for src/infrastructure/file_service.py — FileService class."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from src.infrastructure.file_service import FileService
from tests.conftest import make_solid_image


pytestmark = pytest.mark.unit


@pytest.fixture
def fs(tmp_path):
    return FileService(base_dir=str(tmp_path / "debug_base"))


class TestPrepareOutputDir:

    def test_creates_photos_video_debug_subdirs(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "my_score")
        assert (score_dir / "photos").is_dir()
        assert (score_dir / "video").is_dir()
        assert (score_dir / "diagnostics").is_dir()

    def test_idempotent(self, fs, tmp_path):
        out = str(tmp_path / "output")
        d1 = fs.prepare_output_dir(out, "score1")
        d2 = fs.prepare_output_dir(out, "score1")
        assert d1 == d2
        assert (d1 / "photos").is_dir()

    def test_returns_score_dir_path(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "test_name")
        assert score_dir.name == "test_name"

    def test_sanitizes_invalid_chars(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, 'Test<>:"/\\|?*Name')
        assert score_dir.name == "TestName"

    def test_sanitizes_trailing_spaces(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "  My Score  ")
        assert score_dir.name == "My Score"

    def test_truncates_long_names(self, fs, tmp_path):
        out = str(tmp_path / "output")
        long_name = "A" * 300
        score_dir = fs.prepare_output_dir(out, long_name)
        assert len(score_dir.name) == 100


class TestSavePageImage:

    def test_creates_file_at_correct_path(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "sc")
        img = make_solid_image(800, 600)
        path = fs.save_page_image(score_dir, 1, img)
        assert path.exists()
        assert path.name == "page_001_merged.png"

    def test_file_is_loadable_by_cv2(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "sc")
        img = make_solid_image(800, 600, (100, 200, 50))
        path = fs.save_page_image(score_dir, 3, img)
        loaded = cv2.imread(str(path))
        assert loaded is not None
        assert loaded.shape == img.shape

    def test_multiple_pages(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "sc")
        for i in range(1, 4):
            img = make_solid_image(800, 600, (i * 50, i * 50, i * 50))
            fs.save_page_image(score_dir, i, img)
        photos = list((score_dir / "photos").glob("page_*_merged.png"))
        assert len(photos) == 3


class TestLoadPageImages:

    def test_returns_images_sorted_by_page(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "sc")
        imgs_in = []
        for i in [3, 1, 2]:
            img = make_solid_image(800, 600, (i * 50, i * 50, i * 50))
            fs.save_page_image(score_dir, i, img)
            imgs_in.append(img)
        loaded = fs.load_page_images(score_dir)
        assert len(loaded) == 3
        for orig, lded in zip(sorted(imgs_in, key=lambda x: x[0, 0, 0]), loaded):
            np.testing.assert_array_equal(orig, lded)

    def test_empty_photos_returns_empty_list(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "sc")
        loaded = fs.load_page_images(score_dir)
        assert loaded == []


class TestListSavedScores:

    def test_finds_directories_with_photos(self, fs, tmp_path):
        out = str(tmp_path / "output")
        s1 = fs.prepare_output_dir(out, "alpha")
        s2 = fs.prepare_output_dir(out, "beta")
        img = make_solid_image(800, 600)
        fs.save_page_image(s1, 1, img)
        fs.save_page_image(s2, 1, img)
        fs.save_page_image(s2, 2, img)
        results = fs.list_saved_scores(out)
        assert len(results) == 2
        names = [r["score_name"] for r in results]
        assert names == ["alpha", "beta"]

    def test_ignores_dirs_without_photos(self, fs, tmp_path):
        out = str(tmp_path / "output")
        fs.prepare_output_dir(out, "has_photos")
        empty_dir = Path(out) / "no_photos"
        empty_dir.mkdir(parents=True)
        img = make_solid_image(800, 600)
        fs.save_page_image(Path(out) / "has_photos", 1, img)
        results = fs.list_saved_scores(out)
        assert len(results) == 1
        assert results[0]["score_name"] == "has_photos"

    def test_returns_correct_metadata(self, fs, tmp_path):
        out = str(tmp_path / "output")
        score_dir = fs.prepare_output_dir(out, "myscore")
        img = make_solid_image(800, 600)
        for i in range(1, 4):
            fs.save_page_image(score_dir, i, img)
        results = fs.list_saved_scores(out)
        assert len(results) == 1
        r = results[0]
        assert r["score_name"] == "myscore"
        assert r["page_count"] == 3
        assert str(score_dir) == r["path"]

    def test_nonexistent_output_returns_empty(self, fs, tmp_path):
        results = fs.list_saved_scores(str(tmp_path / "nonexistent"))
        assert results == []
