import numpy as np
import pytest
from tests.conftest import make_solid_image, make_bar_image, make_image_with_text


def _vertical_stripe_image(
    width=800,
    height=600,
    stripes=None,
    stripe_color=(255, 50, 50),
    bg_color=(200, 200, 200),
    top_ratio=0.3,
):
    """Create an image with vertical stripes in the top portion.

    stripes: list of (x_start, x_end) column ranges.
    """
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = bg_color
    top_h = int(height * top_ratio)
    if stripes:
        for x_start, x_end in stripes:
            img[:top_h, x_start:x_end] = stripe_color
    return img


@pytest.mark.unit
class TestGetBarProfilePeaks:
    def test_two_stripes_produce_two_peaks(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(80, 100), (400, 420)])
        b = _vertical_stripe_image(stripes=[])
        peaks = deduplicator._get_bar_profile_peaks(a, b, crop_ratio=0.3)
        assert len(peaks) == 2

    def test_no_difference_no_peaks(self, deduplicator):
        img = _vertical_stripe_image(stripes=[(80, 100)])
        peaks = deduplicator._get_bar_profile_peaks(img, img, crop_ratio=0.3)
        assert len(peaks) == 0

    def test_identical_solid_images_no_peaks(self, deduplicator):
        img = make_solid_image(800, 600, (128, 128, 128))
        peaks = deduplicator._get_bar_profile_peaks(img, img, crop_ratio=0.3)
        assert len(peaks) == 0

    def test_five_stripes_produce_five_peaks(self, deduplicator):
        stripes = [(50, 70), (170, 190), (290, 310), (410, 430), (530, 550)]
        a = _vertical_stripe_image(stripes=stripes)
        b = _vertical_stripe_image(stripes=[])
        peaks = deduplicator._get_bar_profile_peaks(a, b, crop_ratio=0.3)
        assert len(peaks) == 5

    def test_peaks_sorted_by_value_desc(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(80, 100), (400, 420)])
        b = _vertical_stripe_image(stripes=[])
        peaks = deduplicator._get_bar_profile_peaks(a, b, crop_ratio=0.3)
        values = [v for _, v in peaks]
        assert values == sorted(values, reverse=True)

    def test_peak_entries_are_tuples(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(80, 100)])
        b = _vertical_stripe_image(stripes=[])
        peaks = deduplicator._get_bar_profile_peaks(a, b, crop_ratio=0.3)
        assert len(peaks) >= 1
        col, val = peaks[0]
        assert isinstance(col, (int, np.integer))
        assert isinstance(val, (float, np.floating, int, np.integer))


@pytest.mark.unit
class TestHasCleanBarProfile:
    def test_two_peaks_returns_true(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(80, 100), (400, 420)])
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_clean_bar_profile(a, b, crop_ratio=0.3) is True

    def test_four_peaks_returns_false(self, deduplicator):
        stripes = [(50, 70), (170, 190), (290, 310), (410, 430)]
        a = _vertical_stripe_image(stripes=stripes)
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_clean_bar_profile(a, b, crop_ratio=0.3) is False

    def test_one_peak_returns_false(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(80, 100)])
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_clean_bar_profile(a, b, crop_ratio=0.3) is False

    def test_five_peaks_returns_false(self, deduplicator):
        stripes = [(50, 70), (170, 190), (290, 310), (410, 430), (530, 550)]
        a = _vertical_stripe_image(stripes=stripes)
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_clean_bar_profile(a, b, crop_ratio=0.3) is False

    def test_zero_peaks_returns_true(self, deduplicator):
        img = make_solid_image(800, 600, (128, 128, 128))
        assert deduplicator.has_clean_bar_profile(img, img, crop_ratio=0.3) is True

    def test_three_peaks_returns_false(self, deduplicator):
        stripes = [(50, 70), (170, 190), (290, 310)]
        a = _vertical_stripe_image(stripes=stripes)
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_clean_bar_profile(a, b, crop_ratio=0.3) is False


@pytest.mark.unit
class TestHasLeftSpikeInMargin:
    def test_left_peak_within_margin(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(60, 80), (400, 420)])
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_left_spike_in_margin(a, b, crop_ratio=0.3) is True

    def test_left_peak_outside_margin(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(300, 320), (400, 420)])
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_left_spike_in_margin(a, b, crop_ratio=0.3) is False

    def test_fewer_than_two_peaks_returns_false(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(60, 80)])
        b = _vertical_stripe_image(stripes=[])
        assert deduplicator.has_left_spike_in_margin(a, b, crop_ratio=0.3) is False

    def test_no_peaks_returns_false(self, deduplicator):
        img = make_solid_image(800, 600, (128, 128, 128))
        assert deduplicator.has_left_spike_in_margin(img, img, crop_ratio=0.3) is False


@pytest.mark.unit
class TestCheckBarProfile:
    def test_two_peaks_left_spike(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(60, 80), (400, 420)])
        b = _vertical_stripe_image(stripes=[])
        has_clean, has_left_spike, peaks = deduplicator.check_bar_profile(a, b, crop_ratio=0.3)
        assert has_clean is True
        assert has_left_spike is True
        assert len(peaks) == 2

    def test_two_peaks_no_left_spike(self, deduplicator):
        a = _vertical_stripe_image(stripes=[(300, 320), (500, 520)])
        b = _vertical_stripe_image(stripes=[])
        has_clean, has_left_spike, peaks = deduplicator.check_bar_profile(a, b, crop_ratio=0.3)
        assert has_clean is True
        assert has_left_spike is False

    def test_zero_peaks(self, deduplicator):
        img = make_solid_image(800, 600, (128, 128, 128))
        has_clean, has_left_spike, peaks = deduplicator.check_bar_profile(img, img, crop_ratio=0.3)
        assert has_clean is True
        assert has_left_spike is True
        assert peaks == []

    def test_five_peaks_not_clean(self, deduplicator):
        stripes = [(50, 70), (170, 190), (290, 310), (410, 430), (530, 550)]
        a = _vertical_stripe_image(stripes=stripes)
        b = _vertical_stripe_image(stripes=[])
        has_clean, has_left_spike, peaks = deduplicator.check_bar_profile(a, b, crop_ratio=0.3)
        assert has_clean is False
        assert len(peaks) == 5


@pytest.mark.unit
class TestGetCachedNumber:
    def test_same_image_returns_cached(self, deduplicator):
        img = make_solid_image(800, 600, (100, 100, 100))
        r1 = deduplicator._get_cached_number(img)
        r2 = deduplicator._get_cached_number(img)
        assert r1 == r2
        assert id(img) in deduplicator._number_cache

    def test_ocr_disabled_returns_none(self, deduplicator_no_ocr):
        img = make_solid_image(800, 600, (100, 100, 100))
        result = deduplicator_no_ocr._get_cached_number(img)
        assert result is None

    def test_ocr_enabled_returns_stub_value(self, deduplicator):
        img = make_solid_image(800, 600, (100, 100, 100))
        deduplicator.ocr_service.set_leftmost_number(id(img), 42)
        result = deduplicator._get_cached_number(img)
        assert result == 42


@pytest.mark.unit
class TestOcrDedup:
    def test_same_number_duplicate(self, deduplicator):
        img_a = make_solid_image(800, 600, (200, 200, 200))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(id(img_a), 5)
        deduplicator.ocr_service.set_leftmost_number(id(img_b), 5)
        assert deduplicator.is_duplicate(img_a, img_b) is True

    def test_different_number_not_duplicate(self, deduplicator):
        img_a = make_solid_image(800, 600, (200, 200, 200))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(id(img_a), 5)
        deduplicator.ocr_service.set_leftmost_number(id(img_b), 7)
        assert deduplicator.is_duplicate(img_a, img_b) is False

    def test_no_ocr_result_falls_through_to_pixel(self, deduplicator):
        img = make_solid_image(800, 600, (128, 128, 128))
        assert deduplicator.is_duplicate(img, img) is True

    def test_b_number_argument_used(self, deduplicator):
        img_a = make_solid_image(800, 600, (200, 200, 200))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(id(img_a), 5)
        assert deduplicator.is_duplicate(img_a, img_b, b_number=5) is True
        assert deduplicator.is_duplicate(img_a, img_b, b_number=9) is False

    def test_one_number_none_falls_through(self, deduplicator):
        img_a = make_solid_image(800, 600, (200, 200, 200))
        img_b = make_solid_image(800, 600, (200, 200, 200))
        deduplicator.ocr_service.set_leftmost_number(id(img_a), 5)
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
