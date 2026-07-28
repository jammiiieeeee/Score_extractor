"""Unit tests for src/infrastructure/ocr_service.py — OcrService class."""

import sys
from unittest.mock import MagicMock, patch, PropertyMock

import cv2
import numpy as np
import pytest

from src.infrastructure.ocr_service import OcrService
from tests.conftest import make_solid_image


pytestmark = pytest.mark.unit


@pytest.fixture
def dummy_image():
    return make_solid_image(200, 200, (255, 255, 255))


class TestInitialize:

    def test_returns_false_when_paddleocr_not_importable(self):
        with patch.dict("sys.modules", {"paddleocr": None}):
            svc = OcrService()
            svc.ocr = None
            svc.enabled = False
            result = svc.initialize()
            assert result is False

    def test_returns_true_on_successful_init(self):
        mock_paddle = MagicMock()
        mock_ocr_instance = MagicMock()
        mock_ocr_instance.ocr.return_value = [[[]]]
        mock_paddle.PaddleOCR.return_value = mock_ocr_instance

        with patch.dict("sys.modules", {"paddleocr": mock_paddle}):
            svc = OcrService()
            svc.ocr = None
            svc.enabled = False
            result = svc.initialize()
            assert result is True
            assert svc.enabled is True

    def test_returns_false_when_all_attempts_fail(self):
        mock_paddle = MagicMock()
        mock_paddle.PaddleOCR.side_effect = Exception("init failed")

        with patch.dict("sys.modules", {"paddleocr": mock_paddle}):
            svc = OcrService()
            svc.ocr = None
            svc.enabled = False
            result = svc.initialize()
            assert result is False
            assert svc.enabled is False


class TestIsEnabled:

    def test_returns_true_when_initialized(self):
        svc = OcrService()
        svc.enabled = True
        assert svc.is_enabled() is True

    def test_returns_false_by_default(self):
        svc = OcrService()
        assert svc.is_enabled() is False


class TestGetLeftmostNumber:

    def _make_svc(self, enabled=True):
        svc = OcrService()
        svc.enabled = enabled
        svc.ocr = MagicMock()
        return svc

    def test_dict_format_returns_leftmost_number(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            {
                "rec_texts": ["42", "10"],
                "rec_scores": [0.95, 0.88],
                "rec_polys": [
                    [[50, 10], [100, 10], [100, 30], [50, 30]],
                    [[10, 10], [40, 10], [40, 30], [10, 30]],
                ],
            }
        ]
        result = svc.get_leftmost_number(dummy_image, vertical_range=0.3)
        assert result == 10

    def test_list_format_returns_leftmost_number(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            [
                [[[50, 10], [100, 10], [100, 30], [50, 30]], ["42", 0.95]],
                [[[10, 10], [40, 10], [40, 30], [10, 30]], ["10", 0.88]],
            ]
        ]
        result = svc.get_leftmost_number(dummy_image, vertical_range=0.3)
        assert result == 10

    def test_returns_none_when_no_digits(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            {
                "rec_texts": ["hello", "world"],
                "rec_scores": [0.9, 0.8],
                "rec_polys": [
                    [[10, 10], [50, 10], [50, 30], [10, 30]],
                    [[60, 10], [100, 10], [100, 30], [60, 30]],
                ],
            }
        ]
        result = svc.get_leftmost_number(dummy_image, vertical_range=0.3)
        assert result is None

    def test_returns_none_when_disabled(self, dummy_image):
        svc = self._make_svc(enabled=False)
        result = svc.get_leftmost_number(dummy_image, vertical_range=0.3)
        assert result is None

    def test_returns_none_on_empty_ocr_result(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [None]
        result = svc.get_leftmost_number(dummy_image, vertical_range=0.3)
        assert result is None

    def test_confidence_threshold_filters_low_scores(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            {
                "rec_texts": ["99"],
                "rec_scores": [0.20],
                "rec_polys": [
                    [[10, 10], [40, 10], [40, 30], [10, 30]],
                ],
            }
        ]
        result = svc.get_leftmost_number(dummy_image, vertical_range=0.3, confidence_threshold=50)
        assert result is None


class TestDetectKeywords:

    def _make_svc(self, enabled=True):
        svc = OcrService()
        svc.enabled = enabled
        svc.ocr = MagicMock()
        return svc

    def test_dict_format_keyword_found(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            {"rec_texts": ["Czerny Etude Op. 299"]}
        ]
        assert svc.detect_keywords(dummy_image, ["Czerny"]) is True

    def test_list_format_keyword_found(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            [[[[0, 0], [100, 0], [100, 20], [0, 20]], ["Czerny Etude", 0.9]]]
        ]
        assert svc.detect_keywords(dummy_image, ["Czerny"]) is True

    def test_no_match_returns_false(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            {"rec_texts": ["Bach Prelude"]}
        ]
        assert svc.detect_keywords(dummy_image, ["Czerny"]) is False

    def test_case_insensitive_match(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            {"rec_texts": ["CZERNY ETUDE"]}
        ]
        assert svc.detect_keywords(dummy_image, ["czerny"]) is True

    def test_returns_false_when_disabled(self, dummy_image):
        svc = self._make_svc(enabled=False)
        assert svc.detect_keywords(dummy_image, ["anything"]) is False

    def test_returns_false_on_empty_result(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [None]
        assert svc.detect_keywords(dummy_image, ["test"]) is False


class TestGetTexts:

    def _make_svc(self, enabled=True):
        svc = OcrService()
        svc.enabled = enabled
        svc.ocr = MagicMock()
        return svc

    def test_dict_format_returns_texts(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            {"rec_texts": ["hello", "world"]}
        ]
        assert svc.get_texts(dummy_image) == ["hello", "world"]

    def test_list_format_returns_texts(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [
            [
                [[[0, 0], [50, 0], [50, 20], [0, 20]], ["hello", 0.9]],
                [[[60, 0], [110, 0], [110, 20], [60, 20]], ["world", 0.85]],
            ]
        ]
        assert svc.get_texts(dummy_image) == ["hello", "world"]

    def test_returns_empty_list_when_disabled(self, dummy_image):
        svc = self._make_svc(enabled=False)
        assert svc.get_texts(dummy_image) == []

    def test_returns_empty_list_on_none_result(self, dummy_image):
        svc = self._make_svc()
        svc.ocr.ocr.return_value = [None]
        assert svc.get_texts(dummy_image) == []
