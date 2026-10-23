"""Unit tests for src/infrastructure/pdf_service.py — PdfService class."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest

from src.infrastructure.pdf_service import PdfService
from src.domain.models import Page, PageStatus
from src.domain.value_objects.config import ScoreConfig
from tests.conftest import make_solid_image, make_image_with_text


pytestmark = pytest.mark.unit


@pytest.fixture
def pdf_svc():
    return PdfService()


@pytest.fixture
def config():
    return ScoreConfig()


def _page(img, boundary_row=None, status=PageStatus.KEEP):
    """A page holding the image, with the boundary row measured for it."""
    return Page(image=img, boundary_row=boundary_row, status=status)


class TestCreatePdf:

    def test_produces_valid_pdf_file(self, pdf_svc, config, tmp_path):
        pages = [_page(make_solid_image(800, 600))]
        out = tmp_path / "test_score.pdf"
        pdf_svc.create_pdf(pages, out, config, title_hint="Test Score")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_pdf_starts_with_pdf_magic_bytes(self, pdf_svc, config, tmp_path):
        pages = [_page(make_solid_image(800, 600))]
        out = tmp_path / "test.pdf"
        pdf_svc.create_pdf(pages, out, config, title_hint="T")
        header = out.read_bytes()[:5]
        assert header == b"%PDF-"

    def test_multi_page_pdf(self, pdf_svc, config, tmp_path):
        # Create many tall images to force multiple pages
        pages = [_page(make_solid_image(800, 2000)) for _ in range(20)]
        out = tmp_path / "multipage.pdf"
        pdf_svc.create_pdf(pages, out, config, title_hint="Multi")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_crops_images_using_config(self, pdf_svc, tmp_path):
        custom_config = ScoreConfig(default_crop_ratio=0.5)
        pages = [_page(make_solid_image(800, 1000))]
        out = tmp_path / "cropped.pdf"
        pdf_svc.create_pdf(pages, out, custom_config, title_hint="Cropped")
        assert out.exists()

    def test_empty_pages_list_produces_pdf(self, pdf_svc, config, tmp_path):
        out = tmp_path / "empty.pdf"
        pdf_svc.create_pdf([], out, config, title_hint="Empty")
        assert out.exists()
        assert out.stat().st_size > 0

    def test_title_from_stem_when_no_hint(self, pdf_svc, config, tmp_path):
        pages = [_page(make_solid_image(800, 600))]
        out = tmp_path / "my_score_name.pdf"
        pdf_svc.create_pdf(pages, out, config)
        assert out.exists()

    def test_font_fallback_no_crash(self, pdf_svc, config, tmp_path):
        pages = [_page(make_solid_image(800, 600))]
        out = tmp_path / "font_test.pdf"
        with patch("src.infrastructure.pdf_service.pdfmetrics") as mock_metrics:
            mock_metrics.registerFont.side_effect = Exception("Font not found")
            pdf_svc.create_pdf(pages, out, config, title_hint="Fallback")
            assert out.exists()


def _capture_drawn_heights(pdf_svc, pages, out, config):
    """Run create_pdf and return the (width, height) list passed to drawImage."""
    drawn = []

    def fake_draw_image(self, image, x, y, width=None, height=None, **kwargs):
        drawn.append((width, height))

    with patch("reportlab.pdfgen.canvas.Canvas.drawImage", fake_draw_image):
        pdf_svc.create_pdf(pages, out, config, title_hint="T")
    return drawn


class TestPdfPageStatus:
    """Only KEEP pages are printed."""

    def test_prints_only_keep_pages(self, pdf_svc, config, tmp_path):
        pages = [
            _page(make_solid_image(800, 600)),
            _page(make_solid_image(800, 600), status=PageStatus.DUPLICATE),
            _page(make_solid_image(800, 600), status=PageStatus.EXCLUDED),
            _page(make_solid_image(800, 600)),
        ]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "status.pdf", config)
        assert len(heights) == 2

    def test_default_status_is_treated_as_keep(self, pdf_svc, config, tmp_path):
        pages = [Page(image=make_solid_image(800, 600))]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "no_status.pdf", config)
        assert len(heights) == 1


class TestPdfCropByMode:
    """Single-crop model: the crop rule owns the only crop, driven by boundary_mode."""

    def test_manual_mode_crops_to_ratio(self, pdf_svc, tmp_path):
        cfg = ScoreConfig(default_crop_ratio=0.5, boundary_mode="manual")
        pages = [_page(make_solid_image(800, 1000))]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "m.pdf", cfg)
        assert len(heights) == 1
        w_pt, h_pt = heights[0]
        # drawn width == usable A4 width (595 - 2*36 = 523); height = ratio of it
        expected_h = w_pt * (500 / 800)
        assert abs(h_pt - expected_h) < 1.0

    def test_off_mode_no_crop_full_frame(self, pdf_svc, tmp_path):
        cfg = ScoreConfig(default_crop_ratio=0.5, boundary_mode="off")
        pages = [_page(make_solid_image(800, 1000))]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "o.pdf", cfg)
        w_pt, h_pt = heights[0]
        expected_h = w_pt * (1000 / 800)   # full height
        assert abs(h_pt - expected_h) < 1.0

    def test_auto_mode_uses_boundary_row(self, pdf_svc, tmp_path):
        cfg = ScoreConfig(default_crop_ratio=0.5, boundary_mode="auto")
        pages = [_page(make_solid_image(800, 1000), boundary_row=400)]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "a.pdf", cfg)
        w_pt, h_pt = heights[0]
        expected_h = w_pt * (400 / 800)   # boundary row 400 of 1000
        assert abs(h_pt - expected_h) < 1.0

    def test_auto_mode_applies_offset(self, pdf_svc, tmp_path):
        cfg = ScoreConfig(default_crop_ratio=0.5, boundary_mode="auto",
                          boundary_offset_px=50)
        pages = [_page(make_solid_image(800, 1000), boundary_row=400)]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "ao.pdf", cfg)
        w_pt, h_pt = heights[0]
        expected_h = w_pt * ((400 - 50) / 800)
        assert abs(h_pt - expected_h) < 1.0

    def test_auto_mode_falls_back_to_ratio_without_row(self, pdf_svc, tmp_path):
        cfg = ScoreConfig(default_crop_ratio=0.5, boundary_mode="auto")
        pages = [_page(make_solid_image(800, 1000))]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "af.pdf", cfg)
        w_pt, h_pt = heights[0]
        expected_h = w_pt * (500 / 800)   # default_crop_ratio
        assert abs(h_pt - expected_h) < 1.0

    def test_auto_offset_scales_across_pages(self, pdf_svc, tmp_path):
        """Each page is cropped at its own row, offset applied per page."""
        cfg = ScoreConfig(boundary_mode="auto", boundary_offset_px=0)
        pages = [
            _page(make_solid_image(800, 1000), boundary_row=300),
            _page(make_solid_image(800, 1000), boundary_row=600),
        ]
        heights = _capture_drawn_heights(pdf_svc, pages, tmp_path / "multi.pdf", cfg)
        w_pt = heights[0][0]
        assert abs(heights[0][1] - w_pt * (300 / 800)) < 1.0
        # second page may go to page 2 of the PDF but drawImage is still called
        assert any(abs(h - w_pt * (600 / 800)) < 1.0 for _w, h in heights)
