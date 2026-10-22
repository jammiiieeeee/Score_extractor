import numpy as np
import pytest
from src.domain.models import Frame, Page, PageStatus


@pytest.mark.unit
class TestFrame:
    def test_create_with_all_fields(self):
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        frame = Frame(image=img, timestamp=1.5, index=10, path="/tmp/test.png")
        assert frame.timestamp == 1.5
        assert frame.index == 10
        assert frame.path == "/tmp/test.png"
        assert frame.image.shape == (100, 200, 3)

    def test_create_with_default_path_none(self):
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        frame = Frame(image=img, timestamp=0.0, index=0)
        assert frame.path is None

    def test_equality_same_data(self):
        img = np.array([[[10, 20, 30]]], dtype=np.uint8)
        a = Frame(image=img, timestamp=2.0, index=5)
        b = Frame(image=img.copy(), timestamp=2.0, index=5)
        assert np.array_equal(a.image, b.image)
        assert a.timestamp == b.timestamp
        assert a.index == b.index
        assert a.path == b.path

    def test_inequality_different_data(self):
        img_a = np.zeros((10, 10, 3), dtype=np.uint8)
        img_b = np.ones((10, 10, 3), dtype=np.uint8) * 255
        a = Frame(image=img_a, timestamp=1.0, index=0)
        b = Frame(image=img_b, timestamp=1.0, index=0)
        assert not np.array_equal(a.image, b.image)

    def test_inequality_different_timestamp(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        a = Frame(image=img, timestamp=1.0, index=0)
        b = Frame(image=img, timestamp=2.0, index=0)
        assert a.timestamp != b.timestamp

    def test_inequality_different_index(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        a = Frame(image=img, timestamp=1.0, index=0)
        b = Frame(image=img, timestamp=2.0, index=1)
        assert a.index != b.index


@pytest.mark.unit
class TestPageStatus:
    def test_vocabulary(self):
        assert PageStatus.KEEP.value == "keep"
        assert PageStatus.EXCLUDED.value == "excluded"
        assert PageStatus.DUPLICATE.value == "duplicate"

    def test_built_from_value(self):
        assert PageStatus("keep") is PageStatus.KEEP
        assert PageStatus("excluded") is PageStatus.EXCLUDED
        assert PageStatus("duplicate") is PageStatus.DUPLICATE

    def test_compares_as_string(self):
        assert PageStatus.KEEP == "keep"


@pytest.mark.unit
class TestPage:
    def test_carries_everything_known_about_a_page(self):
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        page = Page(
            image=img,
            boundary_row=250,
            attempt_number=3,
            file="/tmp/page_003_merged.png",
            status=PageStatus.KEEP,
        )
        assert page.image.shape == (100, 200, 3)
        assert page.boundary_row == 250
        assert page.attempt_number == 3
        assert page.file == "/tmp/page_003_merged.png"
        assert page.status is PageStatus.KEEP

    def test_defaults(self):
        page = Page(image=np.zeros((10, 10, 3), dtype=np.uint8))
        assert page.boundary_row is None
        assert page.attempt_number == 0
        assert page.file is None
        assert page.status is PageStatus.KEEP

    def test_missing_boundary_row_stays_none(self):
        """A page without a detected row records the absence, not a guess."""
        page = Page(image=np.zeros((10, 10, 3), dtype=np.uint8), boundary_row=None)
        assert page.boundary_row is None

    def test_status_can_be_changed(self):
        page = Page(image=np.zeros((10, 10, 3), dtype=np.uint8))
        page.status = PageStatus.EXCLUDED
        assert page.status is PageStatus.EXCLUDED

