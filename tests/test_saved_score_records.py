"""A saved score records its pages.

The saved score holds one record per page - attempt number, boundary row,
status - so a score that is opened again describes the same pages the
extraction produced.  Scores saved before that still open: the bare list of
boundary rows is read as a fallback.
"""

import json
import time

import cv2
import numpy as np
import pytest

from src.api.gui_api import GuiApi
from src.domain.models import Page, PageStatus
from src.domain.page_crop import crop_page
from src.domain.value_objects.config import ScoreConfig


pytestmark = pytest.mark.unit


@pytest.fixture
def api():
    a = GuiApi()
    yield a
    a.cleanup()


def _wait_for_pdf(api, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not api.is_busy():
            return True
        time.sleep(0.1)
    raise AssertionError("the PDF was not generated in time")


def _write_pages(score_dir, count=3, height=480):
    """Save `count` page images and return their paths, in order."""
    photos = score_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(count):
        path = photos / f"page_{i + 1:03d}_merged.png"
        image = np.full((height, 200, 3), 40 + i * 10, dtype=np.uint8)
        cv2.imwrite(str(path), image)
        paths.append(path)
    return paths


def _read_metadata(score_dir):
    return json.loads((score_dir / "metadata.json").read_text(encoding="utf-8"))


def _drawn_strips(pages, config):
    """The images the PDF draws for these pages (crop_page is the crop rule)."""
    return [crop_page(page, config) for page in pages]


def _config(api):
    return ScoreConfig(**api.get_config())


def _image(shade=10, height=480):
    return np.full((height, 200, 3), shade, dtype=np.uint8)


class TestTheSavedRecord:
    """The saved score records one entry per page."""

    def _generate(self, api, tmp_path, pages):
        api.set_pages(pages)
        api.generate_pdf(str(tmp_path / "score.pdf"))
        _wait_for_pdf(api)
        return _read_metadata(tmp_path)

    def test_every_page_has_an_entry(self, api, tmp_path):
        meta = self._generate(api, tmp_path, [
            Page(_image(10), boundary_row=100, attempt_number=3),
            Page(_image(20), boundary_row=200, attempt_number=4),
        ])

        assert len(meta["pages"]) == 2

    def test_the_entry_carries_attempt_row_and_status(self, api, tmp_path):
        meta = self._generate(api, tmp_path, [
            Page(_image(10), boundary_row=100, attempt_number=3),
        ])

        assert meta["pages"][0] == {"attempt": 3, "boundary_row": 100, "status": "keep"}

    def test_the_entries_are_written_without_a_row(self, api, tmp_path):
        meta = self._generate(api, tmp_path, [Page(_image(10))])

        assert meta["pages"] == [{"attempt": 0, "boundary_row": None, "status": "keep"}]

    def test_the_status_is_written(self, api, tmp_path):
        page = Page(_image(10), boundary_row=100)
        page.status = PageStatus.EXCLUDED
        kept = Page(_image(20), boundary_row=200)

        meta = self._generate(api, tmp_path, [kept, page])

        assert meta["pages"][1]["status"] == "excluded"


class TestReopeningASavedScore:
    """A saved score opens with the pages it was saved with."""

    def test_the_records_are_read_back(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"pages": [
            {"attempt": 1, "boundary_row": 111, "status": "keep"},
            {"attempt": 2, "boundary_row": 222, "status": "duplicate"},
            {"attempt": 3, "boundary_row": None, "status": "keep"},
        ]})

        api.load_saved_score(str(tmp_path))

        assert api.get_page(0).boundary_row == 111
        assert api.get_page(1).status is PageStatus.DUPLICATE
        assert api.get_page(2).boundary_row is None

    def test_a_duplicate_record_does_not_shift_later_pages(self, api, tmp_path):
        photos = tmp_path / "photos"
        photos.mkdir(parents=True, exist_ok=True)
        for number, shade in ((1, 10), (3, 30)):
            cv2.imwrite(str(photos / f"page_{number:03d}_merged.png"), _image(shade))
        api.save_metadata(str(tmp_path), {"pages": [
            {"attempt": 1, "boundary_row": 111, "status": "keep"},
            {"attempt": 2, "boundary_row": 222, "status": "duplicate"},
            {"attempt": 3, "boundary_row": 333, "status": "keep"},
        ]})

        api.load_saved_score(str(tmp_path))

        assert api.get_page_count() == 2
        assert api.get_page(0).boundary_row == 111
        assert api.get_page(1).boundary_row == 333

    def test_an_old_score_still_opens(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"crop_ratio": 0.4, "page_boundary_rows": [11, 22, 33]})

        api.load_saved_score(str(tmp_path))

        assert [api.get_page(i).boundary_row for i in range(3)] == [11, 22, 33]

    def test_an_old_score_still_regenerates_the_same_pdf(self, api, tmp_path):
        paths = _write_pages(tmp_path)
        images = [cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
                  for p in paths]
        api.save_metadata(str(tmp_path), {"crop_ratio": 0.4, "page_boundary_rows": [11, 22, 33]})

        api.regenerate_from_dir(str(tmp_path), str(tmp_path / "regen.pdf"))
        _wait_for_pdf(api)

        reopened = api._pages.all_pages()
        original = [Page(image=img, boundary_row=row)
                    for img, row in zip(images, [11, 22, 33])]
        config = _config(api)
        for before, after in zip(_drawn_strips(original, config), _drawn_strips(reopened, config)):
            assert np.array_equal(before, after)


class TestTheSamePdfAfterReopening:
    """Reopening and regenerating gives back the PDF that was saved."""

    def test_the_same_strips_are_drawn(self, api, tmp_path):
        photos = tmp_path / "photos"
        photos.mkdir(parents=True, exist_ok=True)
        images = [_image(10), _image(20)]
        for i, image in enumerate(images):
            cv2.imwrite(str(photos / f"page_{i + 1:03d}_merged.png"), image)

        api.set_pages([
            Page(image=images[0], boundary_row=150),
            Page(image=images[1], boundary_row=250),
        ])
        api.update_config({"boundary_mode": "auto", "boundary_offset_px": 5,
                           "boundary_offset_ratio": 0.03})
        api.generate_pdf(str(tmp_path / "score.pdf"))
        _wait_for_pdf(api)
        saved = _drawn_strips(api._pages.all_pages(), _config(api))

        api.clear_pages()
        api.load_saved_score(str(tmp_path))
        reopened = _drawn_strips(api._pages.all_pages(), _config(api))

        assert len(reopened) == len(saved)
        for before, after in zip(saved, reopened):
            assert np.array_equal(before, after)

    def test_the_saved_crop_is_used(self, api, tmp_path):
        _write_pages(tmp_path, count=1)
        api.save_metadata(str(tmp_path), {
            "crop_ratio": 0.4,
            "boundary_mode": "manual",
            "boundary_offset_px": 7,
            "boundary_offset_ratio": 0.05,
        })

        api.load_saved_score(str(tmp_path))
        config = _config(api)

        assert config.default_crop_ratio == 0.4
        assert config.boundary_mode == "manual"
        assert config.boundary_offset_px == 7
        assert config.boundary_offset_ratio == 0.05


class TestStatusChangesAreSaved:
    """Changing a page's status writes it into the saved score at once."""

    def _load(self, api, tmp_path):
        paths = _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"pages": [
            {"attempt": 1, "boundary_row": 11, "status": "keep"},
            {"attempt": 2, "boundary_row": 22, "status": "keep"},
            {"attempt": 3, "boundary_row": 33, "status": "keep"},
        ]})
        api.load_saved_score(str(tmp_path))
        return paths

    def test_the_duplicate_flag_is_written_immediately(self, api, tmp_path):
        self._load(api, tmp_path)

        api.set_page_status(1, PageStatus.DUPLICATE)

        assert _read_metadata(tmp_path)["pages"][1]["status"] == "duplicate"

    def test_the_excluded_flag_is_written_immediately(self, api, tmp_path):
        self._load(api, tmp_path)

        api.set_page_status(1, PageStatus.EXCLUDED)

        assert _read_metadata(tmp_path)["pages"][1]["status"] == "excluded"

    def test_both_flags_survive_reopening(self, api, tmp_path):
        self._load(api, tmp_path)
        api.set_page_status(0, PageStatus.DUPLICATE)
        api.set_page_status(1, PageStatus.EXCLUDED)

        api.clear_pages()
        api.load_saved_score(str(tmp_path))

        assert [api.get_page(i).status for i in range(3)] == [
            PageStatus.DUPLICATE, PageStatus.EXCLUDED, PageStatus.KEEP,
        ]

    def test_a_status_change_keeps_every_file(self, api, tmp_path):
        paths = self._load(api, tmp_path)

        api.set_page_status(0, PageStatus.DUPLICATE)
        api.set_page_status(1, PageStatus.EXCLUDED)

        assert all(path.exists() for path in paths)

    def test_an_old_score_loads_as_keep(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"page_boundary_rows": [11, 22, 33]})

        api.load_saved_score(str(tmp_path))

        assert all(api.get_page(i).status is PageStatus.KEEP for i in range(3))

    def test_an_old_score_can_save_a_status(self, api, tmp_path):
        _write_pages(tmp_path)
        api.save_metadata(str(tmp_path), {"page_boundary_rows": [11, 22, 33]})
        api.load_saved_score(str(tmp_path))

        api.set_page_status(1, PageStatus.DUPLICATE)

        api.clear_pages()
        api.load_saved_score(str(tmp_path))
        assert api.get_page(1).status is PageStatus.DUPLICATE

    def test_a_status_change_after_generating_is_written(self, api, tmp_path):
        api.set_pages([
            Page(_image(10), attempt_number=1),
            Page(_image(20), attempt_number=2),
        ])
        api.generate_pdf(str(tmp_path / "score.pdf"))
        _wait_for_pdf(api)

        api.set_page_status(1, PageStatus.EXCLUDED)

        assert _read_metadata(tmp_path)["pages"][1]["status"] == "excluded"

    def test_a_candidate_reopens_with_its_status_and_file(self, api, tmp_path):
        (tmp_path / "photos").mkdir(parents=True)
        (tmp_path / "candidates").mkdir(parents=True)
        for number, shade in ((1, 10), (3, 30)):
            cv2.imwrite(str(tmp_path / "photos" / f"page_{number:03d}_merged.png"),
                        _image(shade))
        candidate = tmp_path / "candidates" / "page_002_merged.png"
        cv2.imwrite(str(candidate), _image(20))
        api.save_metadata(str(tmp_path), {"pages": [
            {"attempt": 1, "boundary_row": 11, "status": "keep"},
            {"attempt": 2, "boundary_row": 22, "status": "duplicate"},
            {"attempt": 3, "boundary_row": 33, "status": "keep"},
        ]})

        api.load_saved_score(str(tmp_path))

        assert api.get_page_count() == 3
        assert api.get_page(1).status is PageStatus.DUPLICATE
        assert api.get_page(1).file == str(candidate)
