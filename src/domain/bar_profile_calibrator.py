"""Adaptive minimum-diff threshold for bar-profile spike detection.

The hardcoded absolute floor in ``BarProfileService.detect_spikes`` is
replaced by a value learned from genuine two-spike bar profiles.  A profile
qualifies as a calibration sample only when it shows exactly two clean bar
spikes; its two spike heights are the intrinsic "how big a bar looks in this
video" evidence.  The floor becomes a low quantile of the running window of
per-sample minimum spike heights, discounted so a real spike still clears it.

Until enough genuine samples exist the calibrator reports its bootstrap value,
which is the only configurable input (``bar_min_diff_threshold``).  Pages
judged before calibration must not be decided with that guess, so the pipeline
holds them and re-judges them once calibration lands (see PageCommitter).
"""

from collections import deque
from typing import Optional


class BarProfileCalibrator:
    def __init__(
        self,
        bootstrap: float = 500.0,
        min_samples: int = 3,
        window: int = 20,
        quantile: float = 0.10,
        discount: float = 0.8,
        min_floor: float = 1.0,
    ):
        self._bootstrap = float(bootstrap)
        self._min_samples = int(min_samples)
        self._window_size = int(window)
        self._quantile = float(quantile)
        self._discount = float(discount)
        self._min_floor = float(min_floor)
        self._window: deque = deque(maxlen=self._window_size)
        self._sample_count = 0

    @property
    def current_floor(self) -> float:
        """The threshold to use for the next detection."""
        if self._sample_count < self._min_samples:
            return self._bootstrap
        vals = sorted(self._window)
        idx = int(round(self._quantile * (len(vals) - 1)))
        idx = max(0, min(idx, len(vals) - 1))
        return max(self._min_floor, vals[idx] * self._discount)

    @property
    def is_calibrated(self) -> bool:
        return self._sample_count >= self._min_samples

    @property
    def sample_count(self) -> int:
        return self._sample_count

    @property
    def bootstrap(self) -> float:
        return self._bootstrap

    def sample(self, spike_heights) -> None:
        """Record one genuine two-spike profile's heights (already validated)."""
        if not spike_heights:
            return
        heights = [float(h) for h in spike_heights if h is not None]
        if len(heights) < 2:
            return
        self._window.append(min(heights))
        self._sample_count += 1

    def reset(self) -> None:
        self._window.clear()
        self._sample_count = 0
