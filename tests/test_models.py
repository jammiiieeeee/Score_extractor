import numpy as np
import pytest
from src.domain.models import Frame


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
        b = Frame(image=img, timestamp=1.0, index=1)
        assert a.index != b.index
