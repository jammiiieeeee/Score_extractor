"""Dynamic score/visualizer boundary detection.

Piano performance videos stack a bright sheet-music panel above a dark MIDI
falling-notes visualizer.  We locate the horizontal line separating the two so
the visualizer can be cropped out of the final page image.

Measurement (per row ``y``): the contrast between the median brightness of a
band *above* ``y`` and a band *below* it.  The true boundary is a sustained
level shift (bright above, dark below); staff lines are thin edges with equal
brightness on both sides, so they score almost zero.  Using region medians
(not raw gradients) is what makes this robust to staff-line noise.

Two modes:

* ``redetect(frame)``  — global search, accept unconditionally.  Used for the
  first page and on every committed page transition (the layout can jump
  between pages).
* ``track(frame)``     — narrow search around the current estimate with a
  median-of-N + hysteresis hold.  Used for in-page frames; falling notes
  crossing the line produce noise that the median rejects.

The median window is reset by ``redetect`` so a genuine jump is never dragged
back toward the previous page's boundary.
"""

from collections import deque
from typing import Optional

import cv2
import numpy as np


class BoundaryDetector:
    def __init__(
        self,
        band_ratio: float = 0.05,
        min_contrast: float = 12.0,
        search_margin: float = 0.05,
        track_window: float = 0.03,
        hysteresis_px: int = 6,
        median_window: int = 5,
        min_dark_mean: float = 120.0,
    ):
        self._band_ratio = float(band_ratio)
        self._min_contrast = float(min_contrast)
        self._search_margin = float(search_margin)
        self._track_window = float(track_window)
        self._hysteresis_px = int(hysteresis_px)
        self._median_window = int(median_window)
        self._min_dark_mean = float(min_dark_mean)

        self._row: Optional[int] = None
        self._recent: deque = deque(maxlen=max(1, self._median_window))
        self._last_confidence = 0.0

    # ── public API ────────────────────────────────────────────────────────

    @property
    def boundary_row(self) -> Optional[int]:
        """Measured boundary row (pixels, in the detector's frame scale), or None."""
        return self._row

    @property
    def is_locked(self) -> bool:
        return self._row is not None

    @property
    def last_confidence(self) -> float:
        """Contrast score of the most recent accepted boundary."""
        return self._last_confidence

    def reset(self) -> None:
        self._row = None
        self._recent.clear()
        self._last_confidence = 0.0

    def redetect(self, frame: np.ndarray) -> Optional[int]:
        """Global search.  Accepts the strongest candidate unconditionally and
        resets the tracking window.  Returns the boundary row or None if no row
        clears ``min_contrast``."""
        profile = self._contrast_profile(frame)
        h = profile.shape[0]

        lo = int(h * self._search_margin)
        hi = int(h * (1.0 - self._search_margin))
        if hi <= lo:
            lo, hi = 0, h

        idx = int(np.argmax(profile[lo:hi])) + lo
        contrast = float(profile[idx])
        if contrast < self._min_contrast:
            self._last_confidence = contrast
            return self._row
        if not self._is_plausible(frame, idx):
            self._last_confidence = contrast
            return self._row

        self._row = idx
        self._last_confidence = contrast
        self._recent.clear()
        self._recent.append(idx)
        return self._row

    def track(self, frame: np.ndarray) -> Optional[int]:
        """Narrow search around the current estimate with hysteresis.  Returns
        the (possibly unchanged) boundary row.  Falls back to a full redetect
        if not yet locked."""
        if self._row is None:
            return self.redetect(frame)

        profile = self._contrast_profile(frame)
        h = profile.shape[0]

        half = max(1, int(h * self._track_window))
        lo = max(0, self._row - half)
        hi = min(h, self._row + half + 1)
        idx = int(np.argmax(profile[lo:hi])) + lo
        contrast = float(profile[idx])

        if contrast < self._min_contrast:
            self._last_confidence = contrast
            return self._row

        self._recent.append(idx)
        median = int(round(float(np.median(self._recent))))

        # Only move once the median has clearly departed from the held row.
        if abs(median - self._row) > self._hysteresis_px:
            self._row = median
        self._last_confidence = contrast
        return self._row

    # ── measurement ───────────────────────────────────────────────────────

    def _contrast_profile(self, frame: np.ndarray) -> np.ndarray:
        """Per-row contrast: median(band above) - median(band below)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        h = gray.shape[0]
        band = max(2, int(h * self._band_ratio))

        row_med = np.median(gray, axis=1)

        # Prefix sums give O(1) band means for every row.
        csum = np.concatenate(([0.0], np.cumsum(row_med, dtype=np.float64)))
        idx = np.arange(h)

        above_lo = np.clip(idx - band, 0, h)
        above_hi = np.clip(idx, 0, h)
        above_cnt = np.clip(above_hi - above_lo, 1, None)
        above = (csum[above_hi] - csum[above_lo]) / above_cnt

        below_lo = np.clip(idx, 0, h)
        below_hi = np.clip(idx + band, 0, h)
        below_cnt = np.clip(below_hi - below_lo, 1, None)
        below = (csum[below_hi] - csum[below_lo]) / below_cnt

        return (above - below).astype(np.float64)

    def _is_plausible(self, frame: np.ndarray, idx: int) -> bool:
        """Sanity guard: reject implausible boundaries.

        The region below the split must actually look like a dark visualizer
        (mean below ``min_dark_mean``).  A video that is bright top-to-bottom
        (e.g. a score that fills the frame) has no such region, so no crop is
        applied rather than cutting away real content."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        below = gray[idx:]
        if below.size == 0:
            return False
        if float(np.mean(below)) > self._min_dark_mean:
            return False
        return True
