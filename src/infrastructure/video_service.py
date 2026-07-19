import cv2
import numpy as np
from typing import Tuple, Optional
from src.domain.interfaces import IVideoService

class VideoService(IVideoService):

    def __init__(self):
        self.cap = None
        self.fps = 0.0
        self.orig_w = 0
        self.orig_h = 0
        self._seq_idx = -1

    def open_video(self, video_path: str) -> None:
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        ret, first = self.cap.read()
        if ret:
            self.orig_h, self.orig_w = first.shape[:2]
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._seq_idx = -1

    def get_fps(self) -> float:
        return self.fps

    def get_original_size(self):
        return self.orig_w, self.orig_h

    def get_total_frames(self) -> int:
        return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def read_frames(self):
        if not self.cap:
            return
        
        frame_idx = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            timestamp = frame_idx / self.fps
            yield frame, timestamp, frame_idx
            frame_idx += 1

    def read_frame_at(self, frame_idx: int):
        if not self.cap:
            return None, None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()
        if not ret:
            return None, None
        timestamp = frame_idx / self.fps
        self._seq_idx = frame_idx
        return frame, timestamp

    def read_next_frame(self):
        if not self.cap:
            return None, None, None
        ret, frame = self.cap.read()
        if not ret:
            return None, None, None
        self._seq_idx += 1
        timestamp = self._seq_idx / self.fps
        return frame, timestamp, self._seq_idx

    def skip_frames(self, count: int):
        """Read and discard count frames without decoding into images."""
        if not self.cap:
            return
        for _ in range(count):
            ret = self.cap.grab()
            if not ret:
                break
            self._seq_idx += 1

    def read_full_frame_at(self, frame_idx: int):
        if not self.cap:
            return None, None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = self.cap.read()
        if not ret:
            return None, None
        timestamp = frame_idx / self.fps
        return frame, timestamp

    def merge_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, overlay_width_ratio: float = 0.5, crop_ratio: float = 0.35, min_diff_threshold: float = 500.0, bar_padding_px: int = -15, debug_save_path: Optional[str] = None) -> Tuple[np.ndarray, int, int]:
        h, w = frame_a.shape[:2]

        # Downscale to 640px for bar detection
        small_w = 640
        small_h = int(h * (small_w / w))
        a_small = cv2.resize(frame_a, (small_w, small_h))
        b_small = cv2.resize(frame_b, (small_w, small_h))

        diff = cv2.absdiff(a_small, b_small)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        # Restrict scan to top portion (overlap region)
        crop_h = int(small_h * crop_ratio) if 0 < crop_ratio < 1 else small_h
        gray_diff = gray_diff[:crop_h, :]

        vertical_sum = np.sum(gray_diff, axis=0)

        search_range = int(small_w * overlay_width_ratio)
        relevant_sum = vertical_sum[:search_range]

        bar_width = 0
        if len(relevant_sum) > 0:
            max_diff = float(np.max(relevant_sum))
            if max_diff < min_diff_threshold:
                bar_x = 0
                merge_x = 0
            else:
                # Detect right edge of bar (right-to-left, column > 50% of max)
                right_threshold = max_diff * 0.5
                bar_right_small = -1
                for col in range(len(relevant_sum) - 1, -1, -1):
                    if relevant_sum[col] > right_threshold:
                        bar_right_small = col
                        break
                if bar_right_small < 0:
                    bar_right_small = int(np.argmax(relevant_sum))

                # Detect left edge of bar (left-to-right, column > 20% of max)
                left_threshold = max_diff * 0.2
                bar_left_small = -1
                for col in range(bar_right_small - 1, -1, -1):
                    if relevant_sum[col] < left_threshold:
                        bar_left_small = col + 1
                        break
                if bar_left_small < 0:
                    bar_left_small = 0

                bar_x = int(bar_right_small * (w / small_w))
                bar_left = int(bar_left_small * (w / small_w))
                bar_width = bar_x - bar_left
                # Set merge point to the bar's left edge, fully excluding the bar body
                merge_x = max(0, min(bar_left + bar_padding_px, w))
        else:
            bar_x = 0
            merge_x = 0

        if debug_save_path:
            np.savetxt(debug_save_path, relevant_sum, fmt='%d')

        result = frame_a.copy()
        result[:, 0:merge_x] = frame_b[:, 0:merge_x]

        bar_width = max(0, bar_width)
        return result, bar_x, bar_width

    def close(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None
