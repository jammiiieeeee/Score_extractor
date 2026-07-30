import cv2
import numpy as np


class BarProfileService:
    """Shared bar-profile (spike) detection used by both Deduplicator and VideoService."""

    @staticmethod
    def compute_column_sums(frame_a: np.ndarray, frame_b: np.ndarray, crop_ratio: float) -> np.ndarray:
        h, w = frame_a.shape[:2]
        target_w = 640
        scale = target_w / w
        target_h = int(h * scale)
        a_small = cv2.resize(frame_a, (target_w, target_h))
        b_small = cv2.resize(frame_b, (target_w, target_h))
        crop_h = int(target_h * crop_ratio)
        a_top = cv2.cvtColor(a_small[:crop_h, :], cv2.COLOR_BGR2GRAY).astype(float)
        b_top = cv2.cvtColor(b_small[:crop_h, :], cv2.COLOR_BGR2GRAY).astype(float)
        diff = np.abs(a_top - b_top)
        return np.sum(diff, axis=0)

    @staticmethod
    def detect_spikes(col_sums: np.ndarray) -> list:
        max_val = float(np.max(col_sums))
        if max_val < 100:
            return []
        threshold = max_val * 0.3
        min_dist = max(3, int(640 * 0.06))
        peaks = []
        for i in range(2, len(col_sums) - 2):
            if col_sums[i] > col_sums[i-1] and col_sums[i] >= col_sums[i+1] and col_sums[i] > threshold:
                is_clean = True
                for prev_col, _ in peaks:
                    if abs(i - prev_col) < min_dist:
                        is_clean = False
                        break
                if is_clean:
                    peaks.append((i, float(col_sums[i])))
        peaks.sort(key=lambda p: p[1], reverse=True)
        return peaks
