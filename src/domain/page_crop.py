"""The crop rule for a page - one rule, one place.

A page is cropped from the top: the sheet music is kept, the MIDI
visualizer below it is dropped.  How far the page is kept depends on the
config and on what was measured for that page:

    off     - keep the whole frame
    manual  - keep ``default_crop_ratio`` of the frame
    auto    - keep up to the boundary row measured for this page (lifted by
              ``boundary_offset_px``); fall back to ``default_crop_ratio``
              when the page has no measured row

The rule reads the page itself, so an image and its crop can never drift
apart.  Every consumer asks here - the PDF today, a page preview later.
"""

import numpy as np

from src.domain.models import Page
from src.domain.value_objects.config import ScoreConfig


def crop_end_row(page: Page, config: ScoreConfig) -> int:
    """The row where the page's crop ends (exclusive).

    The number is always inside the page: at least row 1, at most the last
    row of the image.
    """
    img_h = page.image.shape[0]
    mode = getattr(config, "boundary_mode", "manual")
    offset = int(getattr(config, "boundary_offset_px", 0))

    if mode == "off":
        return img_h
    if mode == "auto":
        row = page.boundary_row
        if row is None:
            return int(img_h * config.default_crop_ratio)
        return max(1, min(int(row) - offset, img_h))
    return int(img_h * config.default_crop_ratio)


def crop_page(page: Page, config: ScoreConfig) -> np.ndarray:
    """The part of the page that belongs in the output.

    A view of the page image (no copy) - treat it as read-only.
    """
    return page.image[0:crop_end_row(page, config), :]
