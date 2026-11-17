"""The crop rule for a page - one rule, one place.

A page is cropped from both ends.  The sheet music is kept; a header or lyric
banner above it and the MIDI visualizer below it are dropped.  The rows come
from the config and from what was measured for that page:

    off     - keep the whole frame
    manual  - keep the top ``default_crop_ratio`` of the frame
    auto    - start where the score panel starts (``top_row``, lifted by
              ``boundary_top_offset_px``) and stop at the boundary row
              measured for the page (lifted by ``boundary_offset_px`` plus
              ``boundary_offset_ratio`` of the frame height, a safety margin
              over the visualizer); fall back to ``default_crop_ratio`` for
              the bottom when the page has no measured row

The rule reads the page itself, so an image and its crop can never drift
apart.  Every consumer asks here - the PDF today, a page preview later.
"""

import numpy as np

from src.domain.models import Page
from src.domain.value_objects.config import ScoreConfig


def crop_start_row(page: Page, config: ScoreConfig) -> int:
    """The row where the page's crop starts (inclusive).

    Zero unless auto mode measured a score top for this page, then nudged by
    ``boundary_top_offset_px``.  Always before ``crop_end_row``.
    """
    img_h = page.image.shape[0]
    mode = getattr(config, "boundary_mode", "manual")
    if mode != "auto":
        return 0

    top = getattr(page, "top_row", None)
    if top is None:
        base = 0
    else:
        base = int(top) + int(getattr(config, "boundary_top_offset_px", 0))
    return max(0, min(base, img_h - 1))


def crop_end_row(page: Page, config: ScoreConfig) -> int:
    """The row where the page's crop ends (exclusive).

    The number is always inside the page: at least row 1, at most the last
    row of the image.
    """
    img_h = page.image.shape[0]
    mode = getattr(config, "boundary_mode", "manual")
    offset = int(getattr(config, "boundary_offset_px", 0))
    ratio = float(getattr(config, "boundary_offset_ratio", 0.0))

    if mode == "off":
        return img_h
    if mode == "auto":
        row = page.boundary_row
        if row is None:
            return int(img_h * config.default_crop_ratio)
        lift = offset + int(round(img_h * ratio))
        return max(1, min(int(row) - lift, img_h))
    return int(img_h * config.default_crop_ratio)


def crop_page(page: Page, config: ScoreConfig) -> np.ndarray:
    """The part of the page that belongs in the output.

    A view of the page image (no copy) - treat it as read-only.
    """
    start = crop_start_row(page, config)
    end = crop_end_row(page, config)
    if start >= end:
        start = max(0, end - 1)
    return page.image[start:end, :]
