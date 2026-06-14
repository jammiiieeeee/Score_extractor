import cv2
import numpy as np
from typing import Tuple
from src.domain.interfaces import IVideoService

class VideoService(IVideoService):
    def __init__(self):
        self.cap = None
        self.fps = 0.0

    def open_video(self, video_path: str) -> None:
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)

    def get_fps(self) -> float:
        return self.fps

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
        return frame, timestamp

    def merge_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, overlay_width_ratio: float = 0.2) -> Tuple[np.ndarray, int]:
        h, w = frame_a.shape[:2]

        # Downscale to 640px for bar detection
        small_w = 640
        small_h = int(h * (small_w / w))
        a_small = cv2.resize(frame_a, (small_w, small_h))
        b_small = cv2.resize(frame_b, (small_w, small_h))

        diff = cv2.absdiff(a_small, b_small)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        vertical_sum = np.sum(gray_diff, axis=0)

        search_range = int(small_w * overlay_width_ratio)
        relevant_sum = vertical_sum[:search_range]

        if len(relevant_sum) > 0:
            bar_x_small = np.argmax(relevant_sum)
            bar_x = int(bar_x_small * (w / small_w))
            merge_x = min(bar_x + 10, w)
        else:
            bar_x = 0
            merge_x = 0

        result = frame_a.copy()
        result[:, 0:merge_x] = frame_b[:, 0:merge_x]

        return result, bar_x

    def close(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None
