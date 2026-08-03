import cv2
import numpy as np
from typing import Optional
from src.domain.value_objects.config import ScoreConfig
from src.domain.interfaces import IOcrService
class Deduplicator:
    def __init__(self, config: ScoreConfig, ocr_service: IOcrService):
        self.config = config
        self.ocr_service = ocr_service

    def _get_number(self, image: np.ndarray) -> Optional[int]:
        if self.ocr_service.is_enabled():
            return self.ocr_service.get_leftmost_number(
                image, self.config.duplicate_top_ratio,
                self.config.ocr_horizontal_ratio, self.config.ocr_confidence_threshold
            )
        return None

    def is_duplicate(self, frame_a: np.ndarray, frame_b: np.ndarray, b_number: Optional[int] = None) -> bool:
        if self.ocr_service.is_enabled():
            num_a = self._get_number(frame_a)
            if b_number is not None:
                num_b = b_number
            else:
                num_b = self._get_number(frame_b)

            if num_a is not None and num_b is not None:
                if num_a == num_b:
                    return True
                else:
                    return False

        sim_score = self._get_global_similarity(frame_a, frame_b)

        if sim_score > self.config.force_duplicate_similarity:
            return True
        if sim_score < self.config.pixel_similarity_threshold:
            return False

        is_row_dup = self._check_row_similarity(frame_a, frame_b)
        return is_row_dup

    def _preprocess_gray(self, img: np.ndarray) -> np.ndarray:
        h = img.shape[0]
        max_row = int(h * self.config.duplicate_top_ratio)
        return cv2.cvtColor(cv2.resize(img[:max_row, :], (256, 256)), cv2.COLOR_BGR2GRAY)

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
