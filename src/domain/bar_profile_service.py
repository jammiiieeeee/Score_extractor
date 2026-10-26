import cv2
import numpy as np


class BarProfileService:
    """Shared bar-profile (spike) detection used by both Deduplicator and VideoService."""

    @staticmethod
    def compute_column_sums(frame_a: np.ndarray, frame_b: np.ndarray, analysis_ratio: float) -> np.ndarray:
        h, w = frame_a.shape[:2]
        target_w = 640
        scale = target_w / w
        target_h = int(h * scale)
        a_small = cv2.resize(frame_a, (target_w, target_h))
        b_small = cv2.resize(frame_b, (target_w, target_h))
        analysis_h = int(target_h * analysis_ratio)
        a_top = cv2.cvtColor(a_small[:analysis_h, :], cv2.COLOR_BGR2GRAY).astype(float)
        b_top = cv2.cvtColor(b_small[:analysis_h, :], cv2.COLOR_BGR2GRAY).astype(float)
        diff = np.abs(a_top - b_top)
        return np.sum(diff, axis=0)

    @staticmethod
    def detect_spikes(col_sums: np.ndarray, min_diff_threshold: float = 100.0) -> list:
        max_val = float(np.max(col_sums))
        if max_val < min_diff_threshold:
            return []
        threshold = max_val * 0.3
        min_dist = max(3, int(640 * 0.06))
        candidates = []
        for i in range(2, len(col_sums) - 2):
            if col_sums[i] > col_sums[i-1] and col_sums[i] >= col_sums[i+1] and col_sums[i] > threshold:
                candidates.append((i, float(col_sums[i])))
        if not candidates:
            return []

        # Keep the widest set of peaks first and the tallest set second, so a
        # tall peak cannot swallow two neighbours that are far enough apart.
        best = [None] * len(candidates)
        best_end = 0
        best_score = (0, 0.0)
        for i, (col, value) in enumerate(candidates):
            count, height, prev = 1, value, None
            for j in range(i - 1, -1, -1):
                if candidates[j][0] > col - min_dist:
                    continue
                prev_count, prev_height, _ = best[j]
                if (prev_count + 1, prev_height + value) > (count, height):
                    count, height, prev = prev_count + 1, prev_height + value, j
            best[i] = (count, height, prev)
            if (count, height) > best_score:
                best_score, best_end = (count, height), i

        peaks = []
        while best_end is not None:
            peaks.append(candidates[best_end])
            best_end = best[best_end][2]
        peaks.sort(key=lambda p: p[1], reverse=True)
        return peaks
