import cv2
import numpy as np
from typing import Optional
from src.domain.value_objects.config import ScoreConfig
from src.domain.interfaces import IOcrService
from src.domain.bar_profile_service import BarProfileService

class Deduplicator:
    def __init__(self, config: ScoreConfig, ocr_service: IOcrService):
        self.config = config
        self.ocr_service = ocr_service
        self._number_cache: dict[int, Optional[int]] = {}

    def _get_bar_profile_peaks(self, frame_a: np.ndarray, frame_b: np.ndarray, crop_ratio: float) -> list:
        col_sums = BarProfileService.compute_column_sums(frame_a, frame_b, crop_ratio)
        return BarProfileService.detect_spikes(col_sums)

    def has_clean_bar_profile(self, frame_a: np.ndarray, frame_b: np.ndarray, crop_ratio: float) -> bool:
        n = len(self._get_bar_profile_peaks(frame_a, frame_b, crop_ratio))
        return 2 <= n <= 4

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
        has_clean = 2 <= len(peaks) <= 4
        has_left_spike = False
        if len(peaks) >= 2:
            left_col = sorted(peaks[:2], key=lambda p: p[0])[0][0]
            margin_col = int(640 * self.config.bar_left_margin)
            has_left_spike = left_col < margin_col
        return has_clean, has_left_spike, peaks

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

    def _get_global_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        h = img1.shape[0]
        max_row = int(h * self.config.duplicate_top_ratio)
        # Crop to top region, resize to 256x256 grayscale for fast comparison
        g1 = cv2.cvtColor(cv2.resize(img1[:max_row, :], (256, 256)), cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(cv2.resize(img2[:max_row, :], (256, 256)), cv2.COLOR_BGR2GRAY)
        
        # Calculate correlation coefficient
        res = cv2.matchTemplate(g1, g2, cv2.TM_CCOEFF_NORMED)
        return res[0][0]

    def _check_row_similarity(self, img1: np.ndarray, img2: np.ndarray) -> bool:
        height = img1.shape[0]
        max_row = int(height * self.config.duplicate_top_ratio)
        
        g1 = cv2.cvtColor(img1[:max_row, :], cv2.COLOR_BGR2GRAY).astype(np.float64)
        g2 = cv2.cvtColor(img2[:max_row, :], cv2.COLOR_BGR2GRAY).astype(np.float64)
        
        similar_rows = 0
        
        for i in range(max_row):
            row1 = g1[i, :]
            row2 = g2[i, :]
            
            std1 = np.std(row1)
            std2 = np.std(row2)
            
            if std1 < 0.1 and std2 < 0.1:
                similar_rows += 1
                continue
                
            corr = np.corrcoef(row1, row2)[0, 1]
            if not np.isnan(corr) and corr > self.config.row_similarity_threshold:
                similar_rows += 1
                
        coverage = similar_rows / max_row
        return coverage > self.config.row_coverage_threshold
