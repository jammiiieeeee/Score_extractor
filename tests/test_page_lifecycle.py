"""Removing, reordering and reloading a page keeps it whole.

A page carries its own image, crop and file.  These tests pin the three ways
that used to fall apart: removing a page deleted the wrong file, reordering
left a page's crop behind, and reopening a score forgot the per-page crop and
fell back to a flat ratio.
"""

import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.api.gui_api import GuiApi
from src.domain.models import Page, PageStatus
from src.domain.page_store import PageStore


pytestmark = pytest.mark.unit


def _wait_for(condition_fn, timeout=30.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def api():
    a = GuiApi()
    yield a
    a.cleanup()


def _write_pages(score_dir, count=3):
    """Save `count` page images and return their paths, in order."""
    photos = score_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(count):
        path = photos / f"page_{i + 1:03d}_merged.png"
        image = np.full((120, 200, 3), 40 + i * 10, dtype=np.uint8)
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths


class TestRemovingAPage:
    """Removing a page deletes that page's file and no other."""

    def test_only_that_file_is_deleted(self, api, tmp_path):
        paths = _write_pages(tmp_path)
        api.load_saved_score(str(tmp_path))

        api.remove_page(1)

        assert not paths[1].exists()
        assert paths[0].exists()
        assert paths[2].exists()

    def test_the_right_file_goes_after_a_reorder(self, api, tmp_path):
        paths = _write_pages(tmp_path)
        api.load_saved_score(str(tmp_path))
        api.reorder_pages([2, 0, 1])

        api.remove_page(0)

        assert not paths[2].exists()
        assert paths[0].exists()
        assert paths[1].exists()

    def test_the_other_pages_keep_their_crop(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"page_boundary_rows": [11, 22, 33]})
        api.load_saved_score(str(tmp_path))

        api.remove_page(1)

        assert [api.get_page(i).boundary_row for i in range(2)] == [11, 33]

    def test_the_page_is_gone_from_the_score(self, api, tmp_path):
        _write_pages(tmp_path)
        api.load_saved_score(str(tmp_path))

        api.remove_page(0)

        assert api.get_page_count() == 2


class TestReordering:
    """Reordering keeps each page's crop with its page."""

    def test_the_crop_travels_with_the_page(self, api, synthetic_images):
        api.add_page(synthetic_images[0], boundary_row=10)
        api.add_page(synthetic_images[1], boundary_row=20)
        api.add_page(synthetic_images[2], boundary_row=30)

        api.reorder_pages([2, 0, 1])

        assert [api.get_page(i).boundary_row for i in range(3)] == [30, 10, 20]

    def test_the_file_travels_with_the_page(self, api, tmp_path):
        paths = _write_pages(tmp_path)
        api.load_saved_score(str(tmp_path))

        api.reorder_pages([1, 2, 0])

        assert [Path(api.get_page(i).file).name for i in range(3)] == [
            paths[1].name, paths[2].name, paths[0].name,
        ]


class TestReopeningAScore:
    """Reopening a saved score keeps the per-page crop it was saved with."""

    def test_loading_keeps_the_saved_rows(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"crop_ratio": 0.4, "page_boundary_rows": [11, 22, 33]})

        api.load_saved_score(str(tmp_path))

        assert [api.get_page(i).boundary_row for i in range(3)] == [11, 22, 33]

    def test_regenerating_keeps_the_saved_rows(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"crop_ratio": 0.4, "page_boundary_rows": [11, 22, 33]})

        api.regenerate_from_dir(str(tmp_path), str(tmp_path / "out.pdf"))

        assert [api.get_page(i).boundary_row for i in range(3)] == [11, 22, 33]
        assert _wait_for(lambda: not api.is_busy())

    def test_the_saved_crop_ratio_is_kept(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"crop_ratio": 0.4})

        api.load_saved_score(str(tmp_path))

        assert api.get_config()["default_crop_ratio"] == 0.4

    def test_a_score_without_rows_keeps_working(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"crop_ratio": 0.4})

        api.load_saved_score(str(tmp_path))

        assert api.get_page_count() == 3
        assert api.get_page(0).boundary_row is None


class TestNoParallelLists:
    """The old parallel lists are gone, so nothing can fall out of step."""

    def test_the_legacy_crop_row_list_is_gone(self, api):
        assert not hasattr(api, "_page_crop_rows")
        assert not hasattr(api, "_sync_crop_rows")

    def test_the_png_cache_belongs_to_its_page(self):
        store = PageStore()
        page = Page(np.full((40, 40, 3), 10, dtype=np.uint8))
        store.add(page)

        store.get_full_png(0)

        assert list(store._png_cache) == [page]

    def test_the_png_cache_follows_a_reorder(self):
        store = PageStore()
        first = Page(np.full((40, 40, 3), 10, dtype=np.uint8))
        second = Page(np.full((40, 40, 3), 20, dtype=np.uint8))
        store.add(first)
        store.add(second)
        store.get_full_png(0)
        store.get_full_png(1)

        store.reorder([1, 0])

        assert store.get_full_png(0) is store._png_cache[second]
        assert store.get_full_png(1) is store._png_cache[first]


class TestPageAccess:
    """The public page interface refuses an index that is not there."""

    def test_a_negative_index_is_refused(self, api, synthetic_images):
        api.add_page(synthetic_images[0])

        with pytest.raises(IndexError):
            api.get_page(-1)

    def test_a_negative_index_cannot_change_a_page(self, api, synthetic_images):
        api.add_page(synthetic_images[0])

        with pytest.raises(IndexError):
            api.set_page_status(-1, PageStatus.EXCLUDED)

    def test_the_status_is_stored_as_a_status(self, api, synthetic_images):
        api.add_page(synthetic_images[0], status="duplicate")

        assert api.get_page(0).status is PageStatus.DUPLICATE
