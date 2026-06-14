import cv2
import numpy as np
from typing import Optional
from src.domain.value_objects.config import ScoreConfig
from src.domain.interfaces import IOcrService

class Deduplicator:
    def __init__(self, config: ScoreConfig, ocr_service: IOcrService):
        self.config = config
        self.ocr_service = ocr_service
        self._number_cache: dict[int, Optional[int]] = {}

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

        # Pre-process: Identify and mask the playback bar in both frames
        # (We use a simple diff-based masking for similarity checks)
        mask_a = self._apply_bar_mask(frame_a, frame_b)
        mask_b = self._apply_bar_mask(frame_b, frame_a)

        # Step 1: Global Pixel Similarity (on masked images)
        sim_score = self._get_global_similarity(mask_a, mask_b)
        
        if sim_score > 0.995:
            return True
        if sim_score < 0.950:
            return False
            
        # Step 2: Row-wise Similarity
        is_row_dup = self._check_row_similarity(mask_a, mask_b)
        return is_row_dup

    def _apply_bar_mask(self, img: np.ndarray, other_img: np.ndarray) -> np.ndarray:
        # Identify the bar by comparing with the other image
        diff = cv2.absdiff(img, other_img)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        vertical_sum = np.sum(gray_diff, axis=0)
        
        search_range = int(img.shape[1] * 0.4)
        if len(vertical_sum) > search_range:
            bar_x = np.argmax(vertical_sum[:search_range])
            
            # Black out the bar region in a copy
            masked = img.copy()
            x_start = max(0, bar_x - 15)
            x_end = min(img.shape[1], bar_x + 15)
            masked[:, x_start:x_end] = 0
            return masked
        return img

    def _get_global_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        # Resize to 256x256 grayscale for fast comparison
        g1 = cv2.cvtColor(cv2.resize(img1, (256, 256)), cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(cv2.resize(img2, (256, 256)), cv2.COLOR_BGR2GRAY)
        
        # Calculate correlation coefficient
        res = cv2.matchTemplate(g1, g2, cv2.TM_CCOEFF_NORMED)
        return res[0][0]

    def _check_row_similarity(self, img1: np.ndarray, img2: np.ndarray) -> bool:
        height = img1.shape[0]
        max_row = int(height * self.config.duplicate_top_ratio)
        
        g1 = cv2.cvtColor(img1[:max_row, :], cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(img2[:max_row, :], cv2.COLOR_BGR2GRAY)
        
        similar_rows = 0
        total_rows = max_row
        
        for i in range(total_rows):
            row1 = g1[i, :]
            row2 = g2[i, :]
            
            # Use correlation for row-wise check
            # Adding a small constant to avoid division by zero in flat areas
            std1 = np.std(row1)
            std2 = np.std(row2)
            
            if std1 < 0.1 and std2 < 0.1:
                similar_rows += 1
                continue
                
            res = cv2.matchTemplate(row1.reshape(1, -1), row2.reshape(1, -1), cv2.TM_CCOEFF_NORMED)
            if res[0][0] > self.config.row_similarity_threshold:
                similar_rows += 1
                
        coverage = similar_rows / total_rows
        return coverage > self.config.row_coverage_threshold
