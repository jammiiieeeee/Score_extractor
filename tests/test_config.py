import pytest
from src.domain.value_objects.config import ScoreConfig


@pytest.mark.unit
class TestScoreConfigDefaults:
    def test_default_construction(self):
        cfg = ScoreConfig()
        assert cfg is not None

    def test_change_detection_threshold(self):
        assert ScoreConfig().change_detection_threshold == 0.96

    def test_frame_check_interval(self):
        assert ScoreConfig().frame_check_interval == 0.8

    def test_top_analysis_ratio(self):
        assert ScoreConfig().top_analysis_ratio == 0.34

    def test_min_screenshot_interval(self):
        assert ScoreConfig().min_screenshot_interval == 3.0

    def test_a_capture_delay(self):
        assert ScoreConfig().a_capture_delay == 0.3

    def test_b_capture_delay(self):
        assert ScoreConfig().b_capture_delay == 3.0

    def test_b_overlay_width_ratio(self):
        assert ScoreConfig().b_overlay_width_ratio == 0.5

    def test_duplicate_top_ratio(self):
        assert ScoreConfig().duplicate_top_ratio == 0.27

    def test_pixel_similarity_threshold(self):
        assert ScoreConfig().pixel_similarity_threshold == 0.95

    def test_row_similarity_threshold(self):
        assert ScoreConfig().row_similarity_threshold == 0.98

    def test_row_coverage_threshold(self):
        assert ScoreConfig().row_coverage_threshold == 0.94

    def test_ocr_confidence_threshold(self):
        assert ScoreConfig().ocr_confidence_threshold == 40

    def test_ocr_horizontal_ratio(self):
        assert ScoreConfig().ocr_horizontal_ratio == 0.30

    def test_default_crop_ratio(self):
        assert ScoreConfig().default_crop_ratio == 0.32

    def test_crop_top_offset(self):
        assert ScoreConfig().crop_top_offset == 0.0

    def test_bar_min_diff_threshold(self):
        assert ScoreConfig().bar_min_diff_threshold == 500.0

    def test_bar_padding_px(self):
        assert ScoreConfig().bar_padding_px == -15

    def test_bar_left_margin(self):
        assert ScoreConfig().bar_left_margin == 0.20

    def test_blank_content_std_threshold(self):
        assert ScoreConfig().blank_content_std_threshold == 3.0

    def test_yt_quality_index(self):
        assert ScoreConfig().yt_quality_index == 0


@pytest.mark.unit
class TestScoreConfigCustomConstruction:
    def test_override_single_field(self):
        cfg = ScoreConfig(change_detection_threshold=0.90)
        assert cfg.change_detection_threshold == 0.90
        assert cfg.a_capture_delay == 0.3

    def test_override_multiple_fields(self):
        cfg = ScoreConfig(
            change_detection_threshold=0.85,
            a_capture_delay=1.0,
            bar_left_margin=0.30,
        )
        assert cfg.change_detection_threshold == 0.85
        assert cfg.a_capture_delay == 1.0
        assert cfg.bar_left_margin == 0.30

    def test_override_preserves_other_defaults(self):
        cfg = ScoreConfig(pixel_similarity_threshold=0.99)
        assert cfg.pixel_similarity_threshold == 0.99
        assert cfg.row_similarity_threshold == 0.98
        assert cfg.b_capture_delay == 3.0


@pytest.mark.unit
class TestScoreConfigFieldTypes:
    def test_float_fields_are_float(self):
        cfg = ScoreConfig()
        assert isinstance(cfg.change_detection_threshold, float)
        assert isinstance(cfg.a_capture_delay, float)
        assert isinstance(cfg.default_crop_ratio, float)
        assert isinstance(cfg.bar_left_margin, float)

    def test_int_fields_are_int(self):
        cfg = ScoreConfig()
        assert isinstance(cfg.ocr_confidence_threshold, int)
        assert isinstance(cfg.bar_padding_px, int)
        assert isinstance(cfg.yt_quality_index, int)


@pytest.mark.unit
class TestScoreConfigEquality:
    def test_same_defaults_are_equal(self):
        a = ScoreConfig()
        b = ScoreConfig()
        assert a == b

    def test_different_values_not_equal(self):
        a = ScoreConfig()
        b = ScoreConfig(a_capture_delay=99.0)
        assert a != b
