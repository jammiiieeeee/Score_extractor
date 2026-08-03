import numpy as np
import pytest
from src.domain.bar_profile_guard import BarProfileGuard, BarProfileVerdict
from tests.conftest import make_solid_image, make_bar_image, make_image_with_text


def _make_spike(col, height):
    return (col, float(height))


@pytest.mark.unit
class TestBarProfileGuard:

    def test_two_spikes_clean_with_left(self):
        spikes = [_make_spike(60, 5000.0), _make_spike(400, 4000.0)]
        v = BarProfileGuard.from_spikes(spikes, left_margin_ratio=0.35)
        assert v.is_clean is True
        assert v.has_left_spike is True

    def test_two_spikes_clean_no_left(self):
        spikes = [_make_spike(300, 5000.0), _make_spike(500, 4000.0)]
        v = BarProfileGuard.from_spikes(spikes, left_margin_ratio=0.35)
        assert v.is_clean is True
        assert v.has_left_spike is False

    def test_zero_spikes_clean(self):
        v = BarProfileGuard.from_spikes([], left_margin_ratio=0.35)
        assert v.is_clean is True
        assert v.has_left_spike is True

    def test_one_spike_not_clean(self):
        spikes = [_make_spike(100, 5000.0)]
        v = BarProfileGuard.from_spikes(spikes, left_margin_ratio=0.35)
        assert v.is_clean is False

    def test_three_spikes_not_clean(self):
        spikes = [_make_spike(50, 5000.0), _make_spike(170, 4000.0), _make_spike(290, 3000.0)]
        v = BarProfileGuard.from_spikes(spikes, left_margin_ratio=0.35)
        assert v.is_clean is False

    def test_five_spikes_not_clean(self):
        spikes = [_make_spike(i, 5000.0 - i * 200) for i in (50, 170, 290, 410, 530)]
        v = BarProfileGuard.from_spikes(spikes, left_margin_ratio=0.35)
        assert v.is_clean is False
        assert len(v.spikes) == 5

    def test_two_spikes_custom_margin(self):
        spikes = [_make_spike(200, 5000.0), _make_spike(500, 4000.0)]
        v = BarProfileGuard.from_spikes(spikes, left_margin_ratio=0.35)
        assert v.has_left_spike is True   # col 200 < 640*0.35=224

        v2 = BarProfileGuard.from_spikes(spikes, left_margin_ratio=0.30)
        assert v2.has_left_spike is False  # col 200 > 640*0.30=192

    def test_verdict_is_dataclass(self):
        spikes = [_make_spike(60, 5000.0), _make_spike(400, 4000.0)]
        v = BarProfileGuard.from_spikes(spikes)
        assert isinstance(v, BarProfileVerdict)

    def test_is_gold_sample_true(self):
        spikes = [_make_spike(60, 5000.0), _make_spike(400, 4000.0)]
        assert BarProfileGuard.is_gold_sample(spikes, is_duplicate=False, has_left_spike=True) is True

    def test_is_gold_sample_wrong_spike_count(self):
        spikes = [_make_spike(60, 5000.0)]
        assert BarProfileGuard.is_gold_sample(spikes, is_duplicate=False, has_left_spike=True) is False

    def test_is_gold_sample_duplicate(self):
        spikes = [_make_spike(60, 5000.0), _make_spike(400, 4000.0)]
        assert BarProfileGuard.is_gold_sample(spikes, is_duplicate=True, has_left_spike=True) is False

    def test_is_gold_sample_no_left_spike(self):
        spikes = [_make_spike(60, 5000.0), _make_spike(400, 4000.0)]
        assert BarProfileGuard.is_gold_sample(spikes, is_duplicate=False, has_left_spike=False) is False


@pytest.mark.unit
class TestGetNumber:
    def test_ocr_disabled_returns_none(self, deduplicator_no_ocr):
        img = make_solid_image(800, 600, (100, 100, 100))
        result = deduplicator_no_ocr._get_number(img)
        assert result is None

    def test_ocr_enabled_returns_stub_value(self, deduplicator):
        img = make_solid_image(800, 600, (100, 100, 100))
        deduplicator.ocr_service.set_leftmost_number(img.tobytes(), 42)
        result = deduplicator._get_number(img)
        assert result == 42


@pytest.mark.unit
class TestOcrDedup:
    def test_same_number_duplicate(self, deduplicator):
        img_a = make_solid_image(800, 600, (200, 200, 200))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(img_a.tobytes(), 5)
        deduplicator.ocr_service.set_leftmost_number(img_b.tobytes(), 5)
        assert deduplicator.is_duplicate(img_a, img_b) is True

    def test_different_number_not_duplicate(self, deduplicator):
        img_a = make_solid_image(800, 600, (100, 100, 100))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(img_a.tobytes(), 5)
        deduplicator.ocr_service.set_leftmost_number(img_b.tobytes(), 7)
        assert deduplicator.is_duplicate(img_a, img_b) is False

    def test_no_ocr_result_falls_through_to_pixel(self, deduplicator):
        img = make_solid_image(800, 600, (128, 128, 128))
        assert deduplicator.is_duplicate(img, img) is True

    def test_b_number_argument_used(self, deduplicator):
        img_a = make_solid_image(800, 600, (200, 200, 200))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(img_a.tobytes(), 5)
        assert deduplicator.is_duplicate(img_a, img_b, b_number=5) is True
        assert deduplicator.is_duplicate(img_a, img_b, b_number=9) is False

    def test_one_number_none_falls_through(self, deduplicator):
        img_a = make_solid_image(800, 600, (100, 100, 100))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(img_a.tobytes(), 5)
        assert deduplicator.is_duplicate(img_a, img_b) is True


@pytest.mark.unit
class TestGlobalSimilarity:
    def test_identical_images_high_score(self, deduplicator_no_ocr):
        img = make_solid_image(800, 600, (128, 150, 200))
        score = deduplicator_no_ocr._get_global_similarity(img, img)
        assert score > 0.995

    def test_different_images_low_score(self, deduplicator_no_ocr):
        rng = np.random.RandomState(42)
        img1 = rng.randint(0, 128, (600, 800, 3), dtype=np.uint8)
        img2 = rng.randint(128, 256, (600, 800, 3), dtype=np.uint8)
        score = deduplicator_no_ocr._get_global_similarity(img1, img2)
        assert score < 0.5

    def test_similar_images_moderate_score(self, deduplicator_no_ocr):
        rng = np.random.RandomState(7)
        base = rng.randint(50, 200, (600, 800, 3), dtype=np.uint8)
        noise = rng.randint(-5, 6, (600, 800, 3), dtype=np.int16)
        shifted = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        score = deduplicator_no_ocr._get_global_similarity(base, shifted)
        assert score > 0.8


@pytest.mark.unit
class TestCheckRowSimilarity:
    def test_identical_returns_true(self, deduplicator_no_ocr):
        img = make_solid_image(800, 600, (100, 100, 100))
        assert deduplicator_no_ocr._check_row_similarity(img, img) is True

    def test_different_returns_false(self, deduplicator_no_ocr):
        rng = np.random.RandomState(42)
        img1 = rng.randint(0, 128, (600, 800, 3), dtype=np.uint8)
        img2 = rng.randint(128, 256, (600, 800, 3), dtype=np.uint8)
        assert deduplicator_no_ocr._check_row_similarity(img1, img2) is False


@pytest.mark.unit
class TestIsDuplicatePixelPath:
    def test_identical_images_duplicate(self, deduplicator_no_ocr):
        img = make_solid_image(800, 600, (128, 128, 128))
        assert deduplicator_no_ocr.is_duplicate(img, img) is True

    def test_different_images_not_duplicate(self, deduplicator_no_ocr):
        rng = np.random.RandomState(42)
        img1 = rng.randint(0, 50, (600, 800, 3), dtype=np.uint8)
        img2 = rng.randint(200, 255, (600, 800, 3), dtype=np.uint8)
        assert deduplicator_no_ocr.is_duplicate(img1, img2) is False

    def test_similar_images_may_be_duplicate(self, deduplicator_no_ocr):
        rng = np.random.RandomState(7)
        base = rng.randint(50, 200, (600, 800, 3), dtype=np.uint8)
        copy = base.copy()
        assert deduplicator_no_ocr.is_duplicate(base, copy) is True

    def test_b_number_ignored_when_ocr_disabled(self, deduplicator_no_ocr):
        img = make_solid_image(800, 600, (128, 128, 128))
        assert deduplicator_no_ocr.is_duplicate(img, img, b_number=5) is True
