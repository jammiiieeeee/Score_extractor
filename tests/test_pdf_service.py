"""Unit tests for src/infrastructure/pdf_service.py — PdfService class."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest

from src.infrastructure.pdf_service import PdfService
from src.domain.value_objects.config import ScoreConfig
from tests.conftest import make_solid_image, make_image_with_text


pytestmark = pytest.mark.unit


@pytest.fixture
def pdf_svc():
    return PdfService()


@pytest.fixture
def config():
    return ScoreConfig()


class TestCreatePdf:

    def test_produces_valid_pdf_file(self, pdf_svc, config, tmp_path):
        images = [make_solid_image(800, 600)]
        out = tmp_path / "test_score.pdf"
        pdf_svc.create_pdf(images, out, config, title_hint="Test Score")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_pdf_starts_with_pdf_magic_bytes(self, pdf_svc, config, tmp_path):
        images = [make_solid_image(800, 600)]
        out = tmp_path / "test.pdf"
        pdf_svc.create_pdf(images, out, config, title_hint="T")
        header = out.read_bytes()[:5]
        assert header == b"%PDF-"

    def test_multi_page_pdf(self, pdf_svc, config, tmp_path):
        # Create many tall images to force multiple pages
        images = [make_solid_image(800, 2000) for _ in range(20)]
        out = tmp_path / "multipage.pdf"
        pdf_svc.create_pdf(images, out, config, title_hint="Multi")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_crops_images_using_config(self, pdf_svc, tmp_path):
        custom_config = ScoreConfig(crop_top_offset=0.1, default_crop_ratio=0.5)
        img = make_solid_image(800, 1000)
        out = tmp_path / "cropped.pdf"
        pdf_svc.create_pdf([img], out, custom_config, title_hint="Cropped")
        assert out.exists()

    def test_empty_images_list_produces_pdf(self, pdf_svc, config, tmp_path):
        out = tmp_path / "empty.pdf"
        pdf_svc.create_pdf([], out, config, title_hint="Empty")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_title_from_stem_when_no_hint(self, pdf_svc, config, tmp_path):
        images = [make_solid_image(800, 600)]
        out = tmp_path / "my_score_name.pdf"
        pdf_svc.create_pdf(images, out, config)
        assert out.exists()

    def test_font_fallback_no_crash(self, pdf_svc, config, tmp_path):
        images = [make_solid_image(800, 600)]
        out = tmp_path / "font_test.pdf"
        with patch("src.infrastructure.pdf_service.pdfmetrics") as mock_metrics:
            mock_metrics.registerFont.side_effect = Exception("Font not found")
            pdf_svc.create_pdf(images, out, config, title_hint="Fallback")
            assert out.exists()
