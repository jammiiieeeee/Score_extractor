import numpy as np
import pytest
from src.domain.models import Frame
from src.domain.page_store import PageStore
from tests.conftest import make_solid_image


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
        store.add(_frame(100))
        assert len(store) == 1
        store.add(_frame(200))
        assert len(store) == 2

    def test_add_returns_index(self):
        store = PageStore()
        i0 = store.add(_frame(10))
        i1 = store.add(_frame(20))
        assert i0 == 0
        assert i1 == 1

    def test_get_returns_correct_frame(self):
        store = PageStore()
        f = _frame(55, ts=3.0, idx=9)
        store.add(f)
        retrieved = store.get(0)
        assert retrieved.timestamp == 3.0
        assert retrieved.index == 9

    def test_getitem(self):
        store = PageStore()
        store.add(_frame(10))
        store.add(_frame(20))
        assert store[0].timestamp == 0.0
        assert store[1].timestamp == 0.0

    def test_get_image(self):
        store = PageStore()
        f = _frame(77)
        store.add(f)
        img = store.get_image(0)
        assert img.shape == (600, 800, 3)

    def test_add_with_explicit_png(self):
        store = PageStore()
        fake_png = b"\x89PNG_FAKE_DATA"
        idx = store.add(_frame(100), png=fake_png)
        assert store._png_cache[idx] == fake_png

    def test_add_without_png_encodes(self):
        store = PageStore()
        idx = store.add(_frame(100))
        assert store._png_cache[idx] is not None
        assert isinstance(store._png_cache[idx], bytes)


@pytest.mark.unit
class TestPageStoreSetPages:
    def test_set_pages_replaces_all(self):
        store = PageStore()
        store.add(_frame(10))
        store.add(_frame(20))
        assert len(store) == 2

        new_frames = [_frame(50), _frame(60), _frame(70)]
        store.set_pages(new_frames)
        assert len(store) == 3

    def test_set_pages_encodes_png(self):
        store = PageStore()
        store.set_pages([_frame(10)])
        assert store._png_cache[0] is not None


@pytest.mark.unit
class TestPageStoreRemove:
    def test_remove_valid(self):
        store = PageStore()
        store.add(_frame(10))
        store.add(_frame(20))
        store.add(_frame(30))
        store.remove(1)
        assert len(store) == 2

    def test_remove_invalid_raises(self):
        store = PageStore()
        store.add(_frame(10))
        with pytest.raises(IndexError):
            store.remove(5)

    def test_remove_negative_raises(self):
        store = PageStore()
        store.add(_frame(10))
        with pytest.raises(IndexError):
            store.remove(-1)


@pytest.mark.unit
class TestPageStoreReorder:
    def test_valid_permutation(self):
        store = PageStore()
        store.add(_frame(10, idx=0))
        store.add(_frame(20, idx=1))
        store.add(_frame(30, idx=2))
        store.reorder([2, 0, 1])
        assert store[0].index == 2
        assert store[1].index == 0
        assert store[2].index == 1

    def test_wrong_length_raises(self):
        store = PageStore()
        store.add(_frame(10))
        store.add(_frame(20))
        with pytest.raises(ValueError):
            store.reorder([0])

    def test_non_permutation_raises(self):
        store = PageStore()
        store.add(_frame(10))
        store.add(_frame(20))
        with pytest.raises(ValueError):
            store.reorder([0, 0])


@pytest.mark.unit
class TestPageStoreClear:
    def test_clear_empties_everything(self):
        store = PageStore()
        store.add(_frame(10))
        store.set_originals([_frame(50)])
        store.clear()
        assert len(store) == 0
        assert store.has_originals() is False

    def test_clear_working_keeps_originals(self):
        store = PageStore()
        store.add(_frame(10))
        store.set_originals([_frame(50)])
        store.clear_working()
        assert len(store) == 0
        assert store.has_originals() is True


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
        store.add(_frame(100))
        thumb = store.get_thumbnail(0)
        assert isinstance(thumb, bytes)

    def test_correct_dimensions(self):
        store = PageStore()
        store.add(_frame(100, w=800, h=600))
        thumb = store.get_thumbnail(0, thumb_width=320)
        restored = PageStore.decode_png(thumb)
        assert restored.shape[1] == 320
        assert restored.shape[0] == 240

    def test_out_of_range_returns_none(self):
        store = PageStore()
        store.add(_frame(100))
        assert store.get_thumbnail(5) is None
        assert store.get_thumbnail(-1) is None


@pytest.mark.unit
class TestPageStoreFullPng:
    def test_returns_bytes(self):
        store = PageStore()
        store.add(_frame(100))
        data = store.get_full_png(0)
        assert isinstance(data, bytes)

    def test_caches_result(self):
        store = PageStore()
        store.add(_frame(100))
        data1 = store.get_full_png(0)
        data2 = store.get_full_png(0)
        assert data1 is data2

    def test_out_of_range_returns_none(self):
        store = PageStore()
        assert store.get_full_png(0) is None


@pytest.mark.unit
class TestPageStoreAllFramesImages:
    def test_all_frames(self):
        store = PageStore()
        store.add(_frame(10, idx=0))
        store.add(_frame(20, idx=1))
        frames = store.all_frames()
        assert len(frames) == 2
        assert frames[0].index == 0
        assert frames[1].index == 1

    def test_all_images(self):
        store = PageStore()
        store.add(_frame(10))
        imgs = store.all_images()
        assert len(imgs) == 1
        assert isinstance(imgs[0], np.ndarray)


@pytest.mark.unit
class TestPageStoreOriginals:
    def test_has_originals_false_initially(self):
        store = PageStore()
        assert store.has_originals() is False

    def test_has_originals_true_after_set(self):
        store = PageStore()
        store.set_originals([_frame(10)])
        assert store.has_originals() is True


@pytest.mark.unit
class TestPageStoreReapplyCrop:
    def test_reapply_crop_replaces_working(self):
        store = PageStore()
        originals = [_frame(100, h=600), _frame(200, h=600)]
        store.set_originals(originals)
        store.add(_frame(99))

        store.reapply_crop(0.5)
        assert len(store) == 2
        assert store[0].image.shape[0] == 300

    def test_reapply_crop_with_no_originals_noop(self):
        store = PageStore()
        store.add(_frame(10))
        store.reapply_crop(0.5)
        assert len(store) == 1

    def test_reapply_crop_preserves_metadata(self):
        store = PageStore()
        f = _frame(100, ts=5.5, idx=42, h=400)
        store.set_originals([f])
        store.reapply_crop(0.25)
        assert store[0].timestamp == 5.5
        assert store[0].index == 42
        assert store[0].image.shape[0] == 100
