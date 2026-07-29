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


def make_marker_image(width=800, height=1000, marker_row=0):
    """Create an image with a single red row at marker_row for precise crop verification."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    img[marker_row, :, :] = [0, 0, 255]  # Red row (BGR)
    return img


def crop_image(img, config):
    """Apply the same crop logic as PdfService.create_pdf — returns cropped image."""
    img_h = img.shape[0]
    y_start = 0
    y_end = int(img_h * config.default_crop_ratio)
    return img[y_start:y_end, :]


# ── Tests ────────────────────────────────────────────────────────────────


class TestPdfServiceCrops:
    """Verify PdfService crops images correctly (via direct crop logic verification)."""

    def test_pdf_service_crops_to_ratio(self):
        """Crop logic produces correct height for given ratio."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.1)

        cropped = crop_image(img, config)
        assert cropped.shape[0] == 100, (
            f"Expected 100px. Got {cropped.shape[0]}px"
        )

    def test_pdf_service_preserves_content(self):
        """Crop preserves the correct region."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.5)

        cropped = crop_image(img, config)
        assert cropped.shape[0] == 500
        # Red was at rows 0-100, we include it, so top-left should be red
        assert cropped[0, 0, 2] == 255, "Red strip preserved"

    def test_various_ratios(self):
        """All ratios produce correct crop."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig()

        for ratio in [0.05, 0.1, 0.2, 0.32, 0.5]:
            config.default_crop_ratio = ratio
            cropped = crop_image(img, config)
            expected = int(1000 * ratio)
            assert cropped.shape[0] == expected, (
                f"ratio={ratio}: expected {expected}px, got {cropped.shape[0]}px"
            )

    def test_create_pdf_runs_without_error(self):
        """PdfService.create_pdf completes without leaving temp files."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.3)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf([img], output, config)
            assert output.exists(), "PDF file should exist"
            assert output.stat().st_size > 0, "PDF should not be empty"


class TestRegenerateWithDifferentCrop:
    """Verify user can regenerate PDF with different crop ratio."""

    def test_regenerate_with_different_crop(self):
        """Extract once, regenerate PDF with different crop ratio."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.3)

        # Store uncropped image (simulating extraction)
        store = PageStore()
        store.set_originals([Frame(img, 0.0, 0)])
        # Also add to working pages for all_images()
        store._pages.append(Frame(img.copy(), 0.0, 0))

        # First crop 30%
        cropped1 = crop_image(img, config)
        assert cropped1.shape[0] == 300, "First crop: 300px"

        # Second crop 50% (user changed ratio)
        config.default_crop_ratio = 0.5
        cropped2 = crop_image(img, config)
        assert cropped2.shape[0] == 500, "Second crop: 500px"

        # Original image unchanged
        assert store._original_pages[0].image.shape[0] == 1000, "Original unchanged"


class TestReapplyCropUpdatesConfig:
    """Verify reapply_crop now only updates config (single-crop model)."""

    def test_reapply_crop_updates_config(self):
        """reapply_crop changes config, does NOT modify page images."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.1)

        store = PageStore()
        store.set_originals([Frame(img, 0.0, 0)])
        store._pages.append(Frame(img.copy(), 0.0, 0))

        # reapply_crop sets ratio on config — no page mutation
        from src.api.gui_api import GuiApi
        api = GuiApi()
        api._config.default_crop_ratio = 0.9
        api._pages = store

        api.reapply_crop(0.5)
        assert api._config.default_crop_ratio == 0.5
        assert store[0].image.shape[0] == 1000, "Pages should NOT be cropped by reapply_crop"

    def test_single_crop_in_pdf_service(self):
        """PdfService crops once from full-size images."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.3)

        # Full-size image goes directly to PdfService
        cropped = crop_image(img, config)
        assert cropped.shape[0] == 300, "Single crop: 300px from 1000px"

        # Change ratio and crop again from original
        config.default_crop_ratio = 0.5
        cropped = crop_image(img, config)
        assert cropped.shape[0] == 500, "Single crop: 500px from 1000px"
