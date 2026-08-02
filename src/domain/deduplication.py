import cv2
import numpy as np
from typing import Optional
from src.domain.value_objects.config import ScoreConfig
from src.domain.interfaces import IOcrService
from src.domain.bar_profile_service import BarProfileService
from src.domain.bar_profile_calibrator import BarProfileCalibrator

class Deduplicator:
    def __init__(self, config: ScoreConfig, ocr_service: IOcrService,
                 calibrator: Optional[BarProfileCalibrator] = None):
        self.config = config
        self.ocr_service = ocr_service
        self.calibrator = calibrator
        self._number_cache: dict[int, Optional[int]] = {}
        # Cache of preprocessed (crop+resize+cvtColor) 256x256 grayscale
        # images keyed by image id. Existing pages are compared many
        # times across detections; preprocessing them once saves a
        # resize+cvtColor per comparison after the first.
        self._gray_cache: dict[int, np.ndarray] = {}

    def _current_floor(self) -> float:
        if self.calibrator is not None:
            return self.calibrator.current_floor
        return float(self.config.bar_min_diff_threshold)

    def _get_bar_profile_peaks(self, frame_a: np.ndarray, frame_b: np.ndarray, crop_ratio: float) -> list:
        col_sums = BarProfileService.compute_column_sums(frame_a, frame_b, crop_ratio)
        return BarProfileService.detect_spikes(col_sums, self._current_floor())

    def has_clean_bar_profile(self, frame_a: np.ndarray, frame_b: np.ndarray, crop_ratio: float) -> bool:
        n = len(self._get_bar_profile_peaks(frame_a, frame_b, crop_ratio))
        return n == 0 or n == 2

    def has_left_spike_in_margin(self, frame_a: np.ndarray, frame_b: np.ndarray, crop_ratio: float) -> bool:
        peaks = self._get_bar_profile_peaks(frame_a, frame_b, crop_ratio)
        if len(peaks) < 2:
            return False
        left_col = sorted(peaks[:2], key=lambda p: p[0])[0][0]
        margin_col = int(640 * self.config.bar_left_margin)
        return left_col < margin_col

    def check_bar_profile(self, frame_a: np.ndarray, frame_b: np.ndarray, crop_ratio: float):
        """Returns (has_clean, has_left_spike, peaks) from a single peak computation."""
        peaks = self._get_bar_profile_peaks(frame_a, frame_b, crop_ratio)
        has_clean = len(peaks) == 0 or len(peaks) == 2
        # Left-spike check only applies when a bar is actually present (2+ spikes).
        # A clean 0-spike profile (no bar detected) is never "misplaced".
        has_left_spike = True
        if len(peaks) >= 2:
            left_col = sorted(peaks[:2], key=lambda p: p[0])[0][0]
            margin_col = int(640 * self.config.bar_left_margin)
            has_left_spike = left_col < margin_col
        return has_clean, has_left_spike, peaks

    def check_bar_profile_from_spikes(self, spikes: list):
        """Same guard-rail verdict as check_bar_profile, but reuses spikes
        already computed by merge_frames rather than recomputing column
        sums. Output is identical when spikes were produced with the same
        floor (the only caller — _analyze — satisfies this)."""
        has_clean = len(spikes) == 0 or len(spikes) == 2
        has_left_spike = True
        if len(spikes) >= 2:
            left_col = sorted(spikes[:2], key=lambda p: p[0])[0][0]
            margin_col = int(640 * self.config.bar_left_margin)
            has_left_spike = left_col < margin_col
        return has_clean, has_left_spike, spikes

    def _get_cached_number(self, image: np.ndarray) -> Optional[int]:
        key = id(image)
        if key not in self._number_cache:
            if self.ocr_service.is_enabled():
                self._number_cache[key] = self.ocr_service.get_leftmost_number(
                    image, self.config.duplicate_top_ratio,
                    self.config.ocr_horizontal_ratio, self.config.ocr_confidence_threshold
                )
            else:
                self._number_cache[key] = None
        return self._number_cache[key]

    def is_duplicate(self, frame_a: np.ndarray, frame_b: np.ndarray, b_number: Optional[int] = None) -> bool:
        # Step 0: OCR Force-Duplicate (with caching)
        if self.ocr_service.is_enabled():
            num_a = self._get_cached_number(frame_a)
            if b_number is not None:
                num_b = b_number
            else:
                num_b = self._get_cached_number(frame_b)

            if num_a is not None and num_b is not None:
                if num_a == num_b:
                    return True
                else:
                    return False

        # Step 1: Global Pixel Similarity (compare merged frames directly)
        sim_score = self._get_global_similarity(frame_a, frame_b)
        
        if sim_score > 0.995:
            return True
        if sim_score < self.config.pixel_similarity_threshold:
            return False
            
        # Step 2: Row-wise Similarity
        is_row_dup = self._check_row_similarity(frame_a, frame_b)
        return is_row_dup

    def _preprocess_gray(self, img: np.ndarray) -> np.ndarray:
        """Crop top region, resize to 256x256, convert to grayscale.
        Cached by image id so existing pages are preprocessed once."""
        key = id(img)
        cached = self._gray_cache.get(key)
        if cached is not None:
            return cached
        h = img.shape[0]
        max_row = int(h * self.config.duplicate_top_ratio)
        g = cv2.cvtColor(cv2.resize(img[:max_row, :], (256, 256)), cv2.COLOR_BGR2GRAY)
        self._gray_cache[key] = g
        return g

    def _get_global_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        # Crop to top region, resize to 256x256 grayscale for fast comparison
        g1 = self._preprocess_gray(img1)
        g2 = self._preprocess_gray(img2)
        # Calculate correlation coefficient
        res = cv2.matchTemplate(g1, g2, cv2.TM_CCOEFF_NORMED)
        return res[0][0]

    def _check_row_similarity(self, img1: np.ndarray, img2: np.ndarray) -> bool:
        height = img1.shape[0]
        max_row = int(height * self.config.duplicate_top_ratio)

        g1 = cv2.cvtColor(img1[:max_row, :], cv2.COLOR_BGR2GRAY).astype(np.float64)
        g2 = cv2.cvtColor(img2[:max_row, :], cv2.COLOR_BGR2GRAY).astype(np.float64)

        # Per-row std to detect blank rows
        std1 = g1.std(axis=1)
        std2 = g2.std(axis=1)
        blank_mask = (std1 < 0.1) & (std2 < 0.1)

        # Pearson correlation, vectorized across all rows at once.
        # Center each row, then r = sum(x*y) / sqrt(sum(x^2) * sum(y^2)).
        g1_centered = g1 - g1.mean(axis=1, keepdims=True)
        g2_centered = g2 - g2.mean(axis=1, keepdims=True)
        numer = np.sum(g1_centered * g2_centered, axis=1)
        denom = np.sqrt(np.sum(g1_centered ** 2, axis=1) * np.sum(g2_centered ** 2, axis=1))
        # np.divide with where= keeps NaN where denom == 0, matching np.corrcoef
        corrs = np.divide(
            numer, denom,
            out=np.full_like(numer, np.nan),
            where=denom != 0,
        )

        # Same decision rule as the original loop:
        #   blank rows => always similar
        #   non-blank  => similar iff corr is finite and > threshold
        similar_mask = blank_mask.copy()
        need_check = ~blank_mask
        if need_check.any():
            sub = corrs[need_check]
            similar_mask[need_check] = (~np.isnan(sub)) & (sub > self.config.row_similarity_threshold)

        coverage = float(similar_mask.sum()) / max_row
        return coverage > self.config.row_coverage_threshold
