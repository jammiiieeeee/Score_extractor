"""Unit tests for the shared crop rule (src/domain/page_crop.py).

The rule is the single place that decides how far a page is kept.  It is
called by the PDF, and any other consumer (a page preview, a thumbnail) can
call it without going through the PDF.
"""

from unittest.mock import patch

import cv2
import numpy as np
import pytest

from src.domain.models import Page
from src.domain.page_crop import crop_end_row, crop_page
from src.domain.value_objects.config import ScoreConfig
from src.infrastructure.pdf_service import PdfService


pytestmark = pytest.mark.unit


def _img(height=1000, width=800):
    """A page image with a distinct band at the top, so a crop is visible."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    img[0:100, :, :] = [0, 0, 255]
    return img


class TestCropEndRow:

    def test_off_mode_keeps_the_whole_page(self):
        cfg = ScoreConfig(boundary_mode="off")
        page = Page(image=_img(1000), boundary_row=400)
        assert crop_end_row(page, cfg) == 1000

    def test_manual_mode_uses_the_default_ratio(self):
        cfg = ScoreConfig(boundary_mode="manual", default_crop_ratio=0.5)
        page = Page(image=_img(1000), boundary_row=400)
        assert crop_end_row(page, cfg) == 500

    def test_auto_mode_uses_the_boundary_row_of_the_page(self):
        cfg = ScoreConfig(boundary_mode="auto", default_crop_ratio=0.5,
                          boundary_offset_ratio=0.0)
        page = Page(image=_img(1000), boundary_row=400)
        assert crop_end_row(page, cfg) == 400

    def test_auto_mode_lifts_the_row_by_the_default_margin(self):
        cfg = ScoreConfig(boundary_mode="auto", boundary_offset_ratio=0.02)
        page = Page(image=_img(1000), boundary_row=400)
        assert crop_end_row(page, cfg) == 380

    def test_auto_mode_adds_the_offset_to_the_margin(self):
        cfg = ScoreConfig(boundary_mode="auto", boundary_offset_ratio=0.02,
                          boundary_offset_px=10)
        page = Page(image=_img(1000), boundary_row=400)
        assert crop_end_row(page, cfg) == 370

    def test_auto_mode_falls_back_to_the_ratio_without_a_row(self):
        cfg = ScoreConfig(boundary_mode="auto", default_crop_ratio=0.5)
        page = Page(image=_img(1000))
        assert crop_end_row(page, cfg) == 500

    def test_auto_mode_lifts_the_row_by_the_offset(self):
        cfg = ScoreConfig(boundary_mode="auto", boundary_offset_px=50,
                          boundary_offset_ratio=0.0)
        page = Page(image=_img(1000), boundary_row=400)
        assert crop_end_row(page, cfg) == 350

    def test_crop_end_stays_inside_the_page(self):
        cfg = ScoreConfig(boundary_mode="auto", boundary_offset_px=500)
        page = Page(image=_img(1000), boundary_row=400)
        assert crop_end_row(page, cfg) == 1

    def test_crop_end_never_passes_the_last_row(self):
        cfg = ScoreConfig(boundary_mode="auto")
        page = Page(image=_img(1000), boundary_row=5000)
        assert crop_end_row(page, cfg) == 1000


class TestCropPage:

    def test_returns_the_top_of_the_page(self):
        cfg = ScoreConfig(boundary_mode="manual", default_crop_ratio=0.5)
        img = _img(1000)
        cropped = crop_page(Page(image=img), cfg)
        assert cropped.shape[0] == 500
        assert np.array_equal(cropped, img[0:500, :])

    def test_crops_each_page_at_its_own_row(self):
        cfg = ScoreConfig(boundary_mode="auto", boundary_offset_ratio=0.0)
        img_a, img_b = _img(1000), _img(1000)
        cropped_a = crop_page(Page(image=img_a, boundary_row=300), cfg)
        cropped_b = crop_page(Page(image=img_b, boundary_row=700), cfg)
        assert cropped_a.shape[0] == 300
        assert cropped_b.shape[0] == 700


class TestPdfUsesTheSameRule:
    """The PDF must draw exactly what the crop rule hands out."""

    @staticmethod
    def _draw(pages, out, config):
        drawn = []

        def fake_draw_image(self, image, x, y, width=None, height=None, **kwargs):
            image.fp.seek(0)
            buf = np.frombuffer(image.fp.read(), dtype=np.uint8)
            drawn.append(cv2.imdecode(buf, cv2.IMREAD_COLOR))

        with patch("reportlab.pdfgen.canvas.Canvas.drawImage", fake_draw_image):
            PdfService().create_pdf(pages, out, config, title_hint="T")
        return drawn

    def test_drawn_page_is_the_cropped_page(self, tmp_path):
        cfg = ScoreConfig(boundary_mode="auto", boundary_offset_px=25)
        img = _img(1000)
        page = Page(image=img, boundary_row=420)

        drawn = self._draw([page], tmp_path / "a.pdf", cfg)

        assert len(drawn) == 1
        assert np.array_equal(drawn[0], crop_page(page, cfg))

    def test_every_page_is_drawn_with_its_own_crop(self, tmp_path):
        cfg = ScoreConfig(boundary_mode="auto")
        pages = [
            Page(image=_img(1000), boundary_row=300),
            Page(image=_img(1000), boundary_row=700),
        ]

        drawn = self._draw(pages, tmp_path / "b.pdf", cfg)

        assert len(drawn) == 2
        for drawn_img, page in zip(drawn, pages):
            assert np.array_equal(drawn_img, crop_page(page, cfg))
