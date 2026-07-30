import cv2
import numpy as np
from typing import Optional
from src.domain.interfaces import IVideoService
from src.domain.models import MergeResult
from src.domain.bar_profile_service import BarProfileService

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

    def merge_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, overlay_width_ratio: float = 0.5, crop_ratio: float = 0.35, min_diff_threshold: float = 500.0, bar_padding_px: int = -15, debug_save_path: Optional[str] = None) -> MergeResult:
        h, w = frame_a.shape[:2]

        col_sums = BarProfileService.compute_column_sums(frame_a, frame_b, crop_ratio)
        search_range = int(640 * overlay_width_ratio)

        # Detect spikes on the FULL profile — same data the deduplicator sees.
        spikes = BarProfileService.detect_spikes(col_sums)

        merge_x = 0
        if len(spikes) == 2:
            sorted_spikes = sorted(spikes, key=lambda p: p[0])
            midpoint_640 = (sorted_spikes[0][0] + sorted_spikes[1][0]) // 2
            merge_x = int(midpoint_640 * (w / 640))

        result = frame_a.copy()
        if merge_x > 0:
            result[:, 0:merge_x] = frame_b[:, 0:merge_x]

        if debug_save_path and len(col_sums) > 0:
            relevant = col_sums[:search_range]
            with open(debug_save_path, 'w') as f:
                f.write(f"# n_spikes={len(spikes)} search_range={search_range}\n")
                for i, v in enumerate(spikes):
                    f.write(f"# spike col={v[0]} val={v[1]:.0f}\n")
                if len(spikes) == 2:
                    sorted_s = sorted(spikes, key=lambda p: p[0])
                    f.write(f"# a_spike={sorted_s[0][0]} b_spike={sorted_s[1][0]} midpoint_640={midpoint_640} merge_x={merge_x}\n")
                np.savetxt(f, relevant.reshape(1, -1), fmt='%d', header='relevant (column sums at 640 scale)', comments='')

        return MergeResult(
            merged=result,
            merge_x=merge_x,
            col_sums=col_sums,
            spikes=spikes,
        )

    def close(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None
