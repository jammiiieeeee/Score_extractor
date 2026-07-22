"""
Tests verifying PdfService crops images correctly.

After the fix:
- PdfService.create_pdf() crops images using config settings
- Callers pass uncropped images
- User can regenerate PDF with different crop ratio

Run: pytest tests/test_double_crop_bug.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.domain.models import Frame
from src.domain.page_store import PageStore
from src.domain.value_objects.config import ScoreConfig
from src.infrastructure.pdf_service import PdfService


# ── Helpers ──────────────────────────────────────────────────────────────


def make_tall_image(width=800, height=1000):
    """Create a tall synthetic image with a visible top strip for crop verification.

    Top 100px: RED (to track if crop includes/excludes it)
    Bottom 900px: WHITE
    """
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    img[0:100, :, :] = [0, 0, 255]  # Red top strip (BGR)
    return img


def read_strip(idx=0):
    """Read the temp strip file and clean up."""
    temp_strip = Path(f"temp_strip_{idx}.png")
    if temp_strip.exists():
        strip_img = cv2.imread(str(temp_strip))
        temp_strip.unlink()
        return strip_img
    return None


# ── Tests ────────────────────────────────────────────────────────────────


class TestPdfServiceCrops:
    """Verify PdfService crops images correctly."""

    def test_pdf_service_crops_to_ratio(self):
        """PdfService.create_pdf should crop images using config ratio."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.1, crop_top_offset=0.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf([img], output, config)

            strip_img = read_strip()
            assert strip_img is not None, "Temp strip not found"
            # 1000 * 0.1 = 100px
            assert strip_img.shape[0] == 100, (
                f"PdfService should crop to 100px. Got {strip_img.shape[0]}px"
            )

    def test_pdf_service_crops_with_offset(self):
        """PdfService.create_pdf should apply crop_top_offset."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.1, crop_top_offset=0.2)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf([img], output, config)

            strip_img = read_strip()
            assert strip_img is not None, "Temp strip not found"
            # offset 0.2, ratio 0.1 → y_start=200, y_end=300 → 100px
            assert strip_img.shape[0] == 100, (
                f"PdfService should crop to 100px. Got {strip_img.shape[0]}px"
            )
            # Red was at rows 0-100, we start at row 200, so no red
            # Check that top-left is NOT red (BGR: 0,0,255)
            pixel = strip_img[0, 0]
            assert not (pixel[0] == 0 and pixel[1] == 0 and pixel[2] == 255), "Red strip should be cropped out"

    def test_pdf_service_preserves_content(self):
        """PdfService should preserve the correct region."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.5, crop_top_offset=0.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf([img], output, config)

            strip_img = read_strip()
            assert strip_img is not None, "Temp strip not found"
            # 1000 * 0.5 = 500px
            assert strip_img.shape[0] == 500
            # Red was at rows 0-100, we include it, so top-left should be red
            assert strip_img[0, 0, 2] == 255, "Red strip preserved"

    def test_various_ratios(self):
        """All ratios produce correct crop."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(crop_top_offset=0.0)

        for ratio in [0.05, 0.1, 0.2, 0.32, 0.5]:
            config.default_crop_ratio = ratio

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test.pdf"
                pdf_service = PdfService()
                pdf_service.create_pdf([img], output, config)

                strip_img = read_strip()
                assert strip_img is not None, "Temp strip not found"
                expected = int(1000 * ratio)
                assert strip_img.shape[0] == expected, (
                    f"ratio={ratio}: expected {expected}px, got {strip_img.shape[0]}px"
                )


class TestRegenerateWithDifferentCrop:
    """Verify user can regenerate PDF with different crop ratio."""

    def test_regenerate_with_different_crop(self):
        """Extract once, regenerate PDF with different crop ratio."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.3, crop_top_offset=0.0)

        # Store uncropped image (simulating extraction)
        store = PageStore()
        store.set_originals([Frame(img, 0.0, 0)])
        # Also add to working pages for all_images()
        store._pages.append(Frame(img.copy(), 0.0, 0))

        # First PDF with 30% crop
        with tempfile.TemporaryDirectory() as tmpdir:
            output1 = Path(tmpdir) / "test1.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf(store.all_images(), output1, config)

            strip1 = read_strip()
            assert strip1 is not None, "Temp strip not found"
            assert strip1.shape[0] == 300, "First PDF: 300px"

        # Second PDF with 50% crop (user changed ratio)
        config.default_crop_ratio = 0.5
        with tempfile.TemporaryDirectory() as tmpdir:
            output2 = Path(tmpdir) / "test2.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf(store.all_images(), output2, config)

            strip2 = read_strip()
            assert strip2 is not None, "Temp strip not found"
            assert strip2.shape[0] == 500, "Second PDF: 500px"

        # Original image unchanged
        assert store._original_pages[0].image.shape[0] == 1000, "Original unchanged"


class TestReapplyCropStillWorks:
    """Verify reapply_crop still works for GUI slider."""

    def test_reapply_crop_then_pdf(self):
        """reapply_crop crops originals, then PdfService crops again."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.1, crop_top_offset=0.0)

        store = PageStore()
        store.set_originals([Frame(img, 0.0, 0)])

        # reapply_crop crops to 900px (removes top 10%)
        store.reapply_crop(0.1)
        assert store[0].image.shape[0] == 900, "reapply_crop: 900px"

        # PdfService crops again to 90px (900 * 0.1)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf(store.all_images(), output, config)

            strip_img = read_strip()
            assert strip_img is not None, "Temp strip not found"
            # 900 * 0.1 = 90px
            assert strip_img.shape[0] == 90, (
                f"Expected 90px. Got {strip_img.shape[0]}px"
            )
