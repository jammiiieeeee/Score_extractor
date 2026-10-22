import numpy as np
import pytest
from src.domain.models import Frame, Page
from src.domain.page_store import PageStore
from tests.conftest import make_solid_image


def _page(shade=128, w=800, h=600, boundary_row=None):
    return Page(make_solid_image(w, h, (shade, shade, shade)), boundary_row=boundary_row)


def _frame(shade=128, w=800, h=600, ts=0.0, idx=0):
    return Frame(make_solid_image(w, h, (shade, shade, shade)), ts, idx)


@pytest.mark.unit
class TestPageStoreEmpty:
    def test_len_zero(self):
        store = PageStore()
        assert len(store) == 0

    def test_bool_false(self):
        store = PageStore()
        assert bool(store) is False


@pytest.mark.unit
class TestPageStoreAdd:
    def test_add_increments_len(self):
        store = PageStore()
        store.add(_page(100))
        assert len(store) == 1
        store.add(_page(200))
        assert len(store) == 2

    def test_add_returns_index(self):
        store = PageStore()
        i0 = store.add(_page(10))
        i1 = store.add(_page(20))
        assert i0 == 0
        assert i1 == 1

    def test_get_returns_correct_page(self):
        store = PageStore()
        p = _page(55, boundary_row=42)
        store.add(p)
        retrieved = store.get(0)
        assert retrieved.boundary_row == 42
        assert retrieved is p

    def test_getitem(self):
        store = PageStore()
        store.add(_page(10))
        store.add(_page(20))
        assert store[0].boundary_row is None
        assert store[1].boundary_row is None

    def test_add_accepts_a_bare_frame(self):
        store = PageStore()
        store.add(_frame(77))
        assert isinstance(store.get(0), Page)

    def test_get_image(self):
        store = PageStore()
        p = _page(77)
        store.add(p)
        img = store.get_image(0)
        assert img.shape == (600, 800, 3)

    def test_add_with_explicit_png(self):
        store = PageStore()
        page = _page(100)
        fake_png = b"\x89PNG_FAKE_DATA"
        store.add(page, png=fake_png)
        assert store._png_cache[page] == fake_png

    def test_add_encodes_on_demand(self):
        store = PageStore()
        page = _page(100)
        store.add(page)
        assert store.get_full_png(0) is not None
        assert isinstance(store._png_cache[page], bytes)


@pytest.mark.unit
class TestPageStoreSetPages:
    def test_set_pages_replaces_all(self):
        store = PageStore()
        store.add(_page(10))
        store.add(_page(20))
        assert len(store) == 2

        new_pages = [_page(50), _page(60), _page(70)]
        store.set_pages(new_pages)
        assert len(store) == 3

    def test_set_pages_encodes_png(self):
        store = PageStore()
        page = _page(10)
        store.set_pages([page])
        assert store.get_full_png(0) is not None
        assert page in store._png_cache


@pytest.mark.unit
class TestPageStoreRemove:
    def test_remove_valid(self):
        store = PageStore()
        store.add(_page(10))
        store.add(_page(20))
        store.add(_page(30))
        store.remove(1)
        assert len(store) == 2

    def test_remove_invalid_raises(self):
        store = PageStore()
        store.add(_page(10))
        with pytest.raises(IndexError):
            store.remove(5)

    def test_remove_negative_raises(self):
        store = PageStore()
        store.add(_page(10))
        with pytest.raises(IndexError):
            store.remove(-1)


@pytest.mark.unit
class TestPageStoreIndex:
    """An index outside the store is an error, negative included."""

    def test_get_negative_raises(self):
        store = PageStore()
        store.add(_page(10))
        with pytest.raises(IndexError):
            store.get(-1)

    def test_getitem_negative_raises(self):
        store = PageStore()
        store.add(_page(10))
        with pytest.raises(IndexError):
            store[-1]

    def test_get_out_of_range_raises(self):
        store = PageStore()
        store.add(_page(10))
        with pytest.raises(IndexError):
            store.get(5)


@pytest.mark.unit
class TestPageStorePngCache:
    """The PNG cache belongs to the page, so it cannot fall out of step."""

    def test_the_cache_travels_with_a_reorder(self):
        store = PageStore()
        first = _page(10)
        second = _page(20)
        store.add(first)
        store.add(second)
        first_png = store.get_full_png(0)
        second_png = store.get_full_png(1)

        store.reorder([1, 0])

        assert store.get_full_png(0) == second_png
        assert store.get_full_png(1) == first_png

    def test_a_removed_page_takes_its_cache_with_it(self):
        store = PageStore()
        page = _page(10)
        store.add(page)
        store.get_full_png(0)

        store.remove(0)

        assert page not in store._png_cache


@pytest.mark.unit
class TestPageStoreReorder:
    def test_valid_permutation(self):
        store = PageStore()
        a = _page(10, boundary_row=0)
        b = _page(20, boundary_row=1)
        c = _page(30, boundary_row=2)
        store.add(a)
        store.add(b)
        store.add(c)
        store.reorder([2, 0, 1])
        assert store[0] is c
        assert store[1] is a
        assert store[2] is b

    def test_wrong_length_raises(self):
        store = PageStore()
        store.add(_page(10))
        store.add(_page(20))
        with pytest.raises(ValueError):
            store.reorder([0])

    def test_non_permutation_raises(self):
        store = PageStore()
        store.add(_page(10))
        store.add(_page(20))
        with pytest.raises(ValueError):
            store.reorder([0, 0])


@pytest.mark.unit
class TestPageStoreClear:
    def test_clear_empties_everything(self):
        store = PageStore()
        store.add(_page(10))
        store.clear()
        assert len(store) == 0
        assert store._png_cache == {}


@pytest.mark.unit
class TestPageStoreEncodeDecode:
    def test_round_trip(self):
        img = make_solid_image(200, 100, (100, 150, 200))
        data = PageStore.encode_png(img)
        assert data is not None
        restored = PageStore.decode_png(data)
        assert restored is not None
        assert restored.shape == img.shape
        np.testing.assert_array_equal(restored, img)


@pytest.mark.unit
class TestPageStoreThumbnail:
    def test_returns_bytes(self):
        store = PageStore()
        store.add(_page(100))
        thumb = store.get_thumbnail(0)
        assert isinstance(thumb, bytes)

    def test_correct_dimensions(self):
        store = PageStore()
        store.add(_page(100, w=800, h=600))
        thumb = store.get_thumbnail(0, thumb_width=320)
        restored = PageStore.decode_png(thumb)
        assert restored.shape[1] == 320
        assert restored.shape[0] == 240

    def test_out_of_range_returns_none(self):
        store = PageStore()
        store.add(_page(100))
        assert store.get_thumbnail(5) is None
        assert store.get_thumbnail(-1) is None


@pytest.mark.unit
class TestPageStoreFullPng:
    def test_returns_bytes(self):
        store = PageStore()
        store.add(_page(100))
        data = store.get_full_png(0)
        assert isinstance(data, bytes)

    def test_caches_result(self):
        store = PageStore()
        store.add(_page(100))
        data1 = store.get_full_png(0)
        data2 = store.get_full_png(0)
        assert data1 is data2

    def test_out_of_range_returns_none(self):
        store = PageStore()
        assert store.get_full_png(0) is None


@pytest.mark.unit
class TestPageStoreAllPagesImages:
    def test_all_pages(self):
        store = PageStore()
        a = _page(10, boundary_row=0)
        b = _page(20, boundary_row=1)
        store.add(a)
        store.add(b)
        pages = store.all_pages()
        assert len(pages) == 2
        assert pages[0] is a
        assert pages[1] is b

    def test_all_images(self):
        store = PageStore()
        store.add(_page(10))
        imgs = store.all_images()
        assert len(imgs) == 1
        assert isinstance(imgs[0], np.ndarray)


@pytest.mark.unit
class TestPageStoreSingleCopy:
    """The store keeps exactly one copy of each page image."""

    def test_set_pages_reuses_the_given_pages(self):
        store = PageStore()
        page = _page(10)
        store.set_pages([page])
        assert store[0] is page
        assert store.get_image(0) is page.image

    def test_no_second_copy_is_kept(self):
        store = PageStore()
        store.add(_page(10))
        assert not hasattr(store, "_original_pages")
        assert not hasattr(store, "_original_png_cache")
