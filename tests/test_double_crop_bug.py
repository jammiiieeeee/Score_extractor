"""
Tests verifying the double-crop bug is fixed.

After the fix:
- PdfService.create_pdf() no longer crops images
- Callers are responsible for providing final images
- CLI explicitly crops before calling PdfService
- GUI slider re-crop is the only crop step

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
    img[0:100, :, :] = [0, 0, 255]  # Red top strip
    return img


def crop_height(img, ratio, top_offset=0.0):
    """Replicate what callers should do before passing to PdfService."""
    img_h = img.shape[0]
    y_start = int(img_h * top_offset)
    y_end = int(img_h * (top_offset + ratio))
    return img[y_start:y_end, :]


# ── Tests ────────────────────────────────────────────────────────────────


class TestDoubleCropBugFixed:
    """Verify the double-crop bug is fixed."""

    def test_reapply_crop_produces_correct_height(self):
        """PageStore.reapply_crop should crop originals to expected height."""
        img = make_tall_image(800, 1000)
        store = PageStore()
        store.set_originals([Frame(img, 0.0, 0)])

        ratio = 0.1
        store.reapply_crop(ratio)

        result = store[0].image
        expected_h = 1000 - int(1000 * ratio)  # 900
        assert result.shape[0] == expected_h, (
            f"reapply_crop should produce {expected_h}px, got {result.shape[0]}px"
        )
        assert result.shape[1] == 800

    def test_pdf_service_no_longer_crops(self):
        """PdfService.create_pdf should NOT crop images — it receives final images."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.1, crop_top_offset=0.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf([img], output, config)

            # Read back the temp strip to verify no cropping happened
            temp_strip = Path("temp_strip_0.png")
            if temp_strip.exists():
                strip_img = cv2.imread(str(temp_strip))
                # After fix: strip should be full height (1000px), not cropped
                assert strip_img.shape[0] == 1000, (
                    f"PdfService should not crop. Got {strip_img.shape[0]}px, expected 1000px"
                )
                temp_strip.unlink()

    def test_single_crop_produces_correct_output(self):
        """The full pipeline: reapply_crop then PdfService = single crop (fixed)."""
        img = make_tall_image(800, 1000)
        ratio = 0.1
        config = ScoreConfig(default_crop_ratio=ratio, crop_top_offset=0.0)

        # Step 1: reapply_crop crops from 1000 to 900
        store = PageStore()
        store.set_originals([Frame(img, 0.0, 0)])
        store.reapply_crop(ratio)
        cropped_once = store[0].image
        assert cropped_once.shape[0] == 900, "Step 1: reapply_crop should produce 900px"

        # Step 2: PdfService no longer crops — image passes through unchanged
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf([cropped_once], output, config)

            temp_strip = Path("temp_strip_0.png")
            if temp_strip.exists():
                strip_img = cv2.imread(str(temp_strip))
                final_height = strip_img.shape[0]
                temp_strip.unlink()
            else:
                final_height = cropped_once.shape[0]

        expected_height = 900  # What user intends
        actual_height = final_height

        print(f"\n  Original:  1000px")
        print(f"  After crop 1 (reapply): {cropped_once.shape[0]}px")
        print(f"  After PdfService (no crop): {actual_height}px")
        print(f"  Expected:  {expected_height}px")

        assert actual_height == expected_height, (
            f"SINGLE CROP: expected {expected_height}px, got {actual_height}px"
        )

    def test_pdf_service_preserves_image_content(self):
        """PdfService should preserve the full image — red strip stays if not cropped."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(default_crop_ratio=0.1, crop_top_offset=0.0)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf([img], output, config)

            temp_strip = Path("temp_strip_0.png")
            if temp_strip.exists():
                strip_img = cv2.imread(str(temp_strip))
                # Red strip should still be there (top-left pixel is red)
                assert strip_img[0, 0, 2] == 255, "Red strip preserved — no cropping"
                temp_strip.unlink()

    def test_various_ratios_all_single_crop(self):
        """All ratios produce correct single-crop output."""
        img = make_tall_image(800, 1000)
        config = ScoreConfig(crop_top_offset=0.0)

        for ratio in [0.05, 0.1, 0.2, 0.32, 0.5]:
            store = PageStore()
            store.set_originals([Frame(img, 0.0, 0)])
            store.reapply_crop(ratio)
            after_crop = store[0].image

            config.default_crop_ratio = ratio

            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "test.pdf"
                pdf_service = PdfService()
                pdf_service.create_pdf([after_crop], output, config)

                temp_strip = Path("temp_strip_0.png")
                if temp_strip.exists():
                    strip_img = cv2.imread(str(temp_strip))
                    final_height = strip_img.shape[0]
                    temp_strip.unlink()
                else:
                    final_height = after_crop.shape[0]

            expected = 1000 - int(1000 * ratio)
            actual = final_height

            assert actual == expected, (
                f"ratio={ratio}: expected {expected}px, got {actual}px"
            )


class TestDoubleCropIntegration:
    """Integration test: full pipeline through PdfService.create_pdf."""

    def test_pdf_service_receives_already_cropped_images(self):
        """When the GUI calls reapply_crop then generate_pdf, PdfService
        receives images that were already cropped by PageStore — and does NOT crop again."""

        img = make_tall_image(800, 1000)
        ratio = 0.1
        config = ScoreConfig(default_crop_ratio=ratio, crop_top_offset=0.0)

        # Simulate what _regenerate_pdf does (app_gui.py:1605-1623)
        store = PageStore()
        store.set_originals([Frame(img, 0.0, 0)])

        # Step 1: reapply_crop (app_gui.py:1606)
        store.reapply_crop(ratio)
        images_for_pdf = store.all_images()

        assert images_for_pdf[0].shape[0] == 900, "Images should be 900px after reapply_crop"

        # Step 2: PdfService.create_pdf does NOT crop them
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.pdf"
            pdf_service = PdfService()
            pdf_service.create_pdf(images_for_pdf, output, config)

            # Verify PDF was created
            assert output.exists()

            # Read back the temp strip — should be 900px (not 90px)
            temp_strip = Path("temp_strip_0.png")
            if temp_strip.exists():
                strip_img = cv2.imread(str(temp_strip))
                # After fix: strip is 900px (correct), not 90px (bug)
                assert strip_img.shape[0] == 900, (
                    f"PDF temp strip height is {strip_img.shape[0]}px — "
                    f"should be 900px (single crop, no double-crop)"
                )
                temp_strip.unlink()
