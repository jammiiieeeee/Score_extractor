"""Extraction sub-components split from ExtractScoreUseCase.

FrameStepper  – loop state machine (SSIM detection, A/B capture, blank/end detection)
PageCommitter – merge, deduplicate, persist, debug save
BarProfilePlotter – matplotlib diagnostic plots (optional, disabled by default)
"""

import cv2
import numpy as np
import time
from pathlib import Path
from typing import Callable, List, Optional, TextIO

from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame, PageManifestEntry
from src.domain.interfaces import IVideoService, IOcrService, IFileService
from src.domain.deduplication import Deduplicator


# ═══════════════════════════════════════════════════════════════════════════
#  FrameStepper – extraction loop state machine
# ═══════════════════════════════════════════════════════════════════════════

class FrameStepper:
    """Manages the frame-by-frame extraction loop.

    Responsibilities:
    - Read frames sequentially with configurable skip
    - Compute SSIM on top ROI to detect page changes
    - Apply A/B capture delays
    - Detect blank content (end of score)
    - Duration limit enforcement
    """

    def __init__(
        self,
        video_service: IVideoService,
        config: ScoreConfig,
        on_log: Callable[[str], None] = print,
        on_progress: Optional[Callable[[float, str], None]] = None,
        is_cancelled: Callable[[], bool] = lambda: False,
    ):
        self.video = video_service
        self.config = config
        self.on_log = on_log
        self.on_progress = on_progress
        self.is_cancelled = is_cancelled

        fps = self.video.get_fps()
        self.cooldown_frames = int(config.min_screenshot_interval * fps)
        self.stability_frames = int(config.b_capture_delay * fps)
        self.seek_step = max(1, int(config.frame_check_interval * fps))
        self.fps = fps

        self.last_trigger_idx = -self.cooldown_frames
        self.last_stable_frame: Optional[Frame] = None
        self.current_idx = 0
        self._n_frames = 0
        self._t_loop = time.time()
        self._unique_pages_ref: list = []

    def _get_roi(self, img: np.ndarray):
        h, w = img.shape[:2]
        y_end = int(h * self.config.top_analysis_ratio)
        roi = img[0:y_end, :]
        small = cv2.resize(roi, (320, int(320 * (y_end / h))))
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    def initialize(self, start_time: float = -1.0) -> Optional[Frame]:
        """Set up initial state. Handles start-time capture or reads first frame.
        Returns the initial last_stable_frame, or None on failure."""
        if start_time >= 0:
            start_idx = int(start_time * self.fps)
            a_img, a_ts = self.video.read_frame_at(start_idx)
            if a_img is not None:
                self.current_idx = start_idx
                b_idx = start_idx + self.stability_frames
                b_img, b_ts = self.video.read_frame_at(b_idx)
                if b_img is None:
                    b_img, b_ts = a_img.copy(), a_ts
                    b_idx = start_idx

                self.last_stable_frame = Frame(b_img.copy(), b_ts, b_idx)
                self.last_trigger_idx = start_idx
                return Frame(a_img.copy(), a_ts, start_idx), Frame(b_img.copy(), b_ts, b_idx)
            else:
                self.on_log("  [WARN] Could not seek to start time, starting from beginning.")

        img, ts = self.video.read_frame_at(0)
        if img is None:
            raise RuntimeError("Could not read video.")
        self.current_idx = 0
        self.last_stable_frame = Frame(img.copy(), ts, 0)
        return None

    def step(self) -> Optional[tuple]:
        """Advance one frame. Returns (current_frame, ssim_score) or None if done."""
        if self.is_cancelled():
            self.on_log("Extraction cancelled.")
            return None

        t0 = time.time()
        if self.seek_step > 1:
            self.video.skip_frames(self.seek_step - 1)
        frame_img, timestamp, current_idx = self.video.read_next_frame()
        if frame_img is None:
            return None

        t_read = time.time() - t0
        current_frame = Frame(frame_img, timestamp, current_idx)
        self.current_idx = current_idx
        self._n_frames += 1

        total_frames = self.video.get_total_frames()
        if total_frames > 0:
            percent = min(95.0, (current_idx / total_frames) * 100.0)
        else:
            percent = 0.0
        if self.on_progress:
            elapsed = time.time() - self._t_loop
            avg = elapsed / self._n_frames
            self.on_progress(percent, f"Frame {current_idx}/{total_frames} at {timestamp:.1f}s  ({t_read*1000:.0f}ms/frame  {elapsed:.0f}s elapsed)")

        # Blank-content detection
        if len(self._unique_pages_ref) > 0:
            roi_std = np.std(self._get_roi(current_frame.image))
            if roi_std < self.config.blank_content_std_threshold:
                self.on_log("  End of score detected (blank content).")
                return None

        # Page change detection
        ssim_score = None
        if (
            (current_idx - self.last_trigger_idx) > self.cooldown_frames
            and self.last_stable_frame is not None
        ):
            from skimage.metrics import structural_similarity as ssim
            ssim_score = ssim(self._get_roi(self.last_stable_frame.image), self._get_roi(current_frame.image))

        self.last_stable_frame = current_frame
        return current_frame, ssim_score

    def should_trigger(self, ssim_score: float) -> bool:
        return ssim_score is not None and ssim_score < self.config.change_detection_threshold

    def capture_a_b(self, trigger_frame: Frame) -> tuple:
        """Apply A-capture delay and B-frame stability delay. Returns (a_frame, b_frame)."""
        a_frame = trigger_frame

        delay_frames = int(self.config.a_capture_delay * self.fps)
        if delay_frames > 0:
            cap_idx = a_frame.index + delay_frames
            cap_img, cap_ts = self.video.read_frame_at(cap_idx)
            if cap_img is not None:
                a_frame = Frame(cap_img.copy(), cap_ts, cap_idx)

        b_idx = a_frame.index + self.stability_frames
        b_img, b_ts = self.video.read_frame_at(b_idx)
        if b_img is None:
            b_img = a_frame.image.copy()
            b_ts = a_frame.timestamp

        b_frame = Frame(b_img.copy(), b_ts, b_idx)
        self.last_trigger_idx = a_frame.index
        return a_frame, b_frame

    def check_end_offset(self, timestamp: float, end_offset: float, video_duration: float) -> bool:
        if end_offset > 0 and video_duration > 0:
            end_time = video_duration - end_offset
            if timestamp >= end_time:
                self.on_log(f"  Trim end: stopping at {end_time:.1f}s (last {end_offset:.1f}s skipped).")
                return True
        return False

    def set_unique_pages_ref(self, pages: list):
        """Set a reference to the unique_pages list for blank detection."""
        self._unique_pages_ref = pages

    def tail_scan(self, ocr_service: IOcrService, unique_pages: list, current_idx: int,
                  end_offset: float, debug: bool = False, log_file: Optional[TextIO] = None) -> None:
        """Check last 20 seconds for 'Thank you' end-credits."""
        if end_offset > 0 or self.is_cancelled():
            return
        try:
            total_frames = self.video.get_total_frames()
            last_20s_frame = total_frames - int(20 * self.fps)
            tail_start = max(last_20s_frame, current_idx)
            tail_step = int(2.0 * self.fps)

            if tail_start < total_frames and ocr_service.is_enabled():
                self.on_log("  Scanning final 20 seconds for end-credits...")
                tail_idx = tail_start
                while tail_idx < total_frames:
                    if self.is_cancelled():
                        break
                    tail_img, tail_ts = self.video.read_full_frame_at(tail_idx)
                    if tail_img is None:
                        break
                    if ocr_service.detect_keywords(tail_img, ["thank"]):
                        trim_time = tail_ts - 2.0
                        self.on_log(f"  'Thank you' detected at {tail_ts:.1f}s, trimming after {trim_time:.1f}s.")
                        unique_pages[:] = [p for p in unique_pages if p.timestamp <= trim_time]
                        break
                    if debug:
                        texts = ocr_service.get_texts(tail_img)
                        if texts:
                            self.on_log(f"  [Debug] Tail frame at {tail_ts:.1f}s OCR: {texts}")
                    tail_idx += tail_step
                else:
                    self.on_log("  No 'Thank you' detected in final 20 seconds.")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
#  PageCommitter – merge, deduplicate, persist
# ═══════════════════════════════════════════════════════════════════════════

class PageCommitter:
    """Handles the commit pipeline for a detected page pair.

    Responsibilities:
    - Dynamic Bar Erase (merge A+B frames)
    - Bar profile validation
    - Deduplication (OCR + pixel + row similarity)
    - Save to disk
    - Debug artifact writing (A/B frames, bar profile text)
    """

    def __init__(
        self,
        video_service: IVideoService,
        file_service: IFileService,
        ocr_service: IOcrService,
        config: ScoreConfig,
        deduplicator: Deduplicator,
        orig_w: int,
        orig_h: int,
        original_video_path: Optional[str] = None,
    ):
        self.video = video_service
        self.file_service = file_service
        self.ocr_service = ocr_service
        self.config = config
        self.deduplicator = deduplicator
        self.orig_w = orig_w
        self.orig_h = orig_h
        self._original_video_path = original_video_path
        self._original_cap = None
        self._original_fps = None

        # If original (full-res) video is available, query its real dimensions
        # so the merge upscale targets the original resolution, not the scan video's
        if original_video_path:
            import cv2
            probe = cv2.VideoCapture(original_video_path)
            if probe.isOpened():
                self.orig_w = int(probe.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.orig_h = int(probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self._original_fps = probe.get(cv2.CAP_PROP_FPS)
                self._original_cap = probe
            else:
                probe.release()

    def _read_full_frame_from_original(self, frame_idx: int, timestamp: float):
        """Read a frame from the original (full-res) video using timestamp for accurate seek."""
        import cv2
        if not self._original_video_path:
            return None
        if self._original_cap is None:
            self._original_cap = cv2.VideoCapture(self._original_video_path)
            self._original_fps = self._original_cap.get(cv2.CAP_PROP_FPS)
        # Use timestamp for frame index to handle different fps between scan and original
        orig_idx = int(round(timestamp * self._original_fps))
        self._original_cap.set(cv2.CAP_PROP_POS_FRAMES, orig_idx)
        ret, frame = self._original_cap.read()
        if ret:
            return frame
        return None

    def release(self):
        """Release the original video capture if opened."""
        if self._original_cap:
            self._original_cap.release()
            self._original_cap = None

    def commit(
        self,
        frame_a: Frame,
        frame_b: Frame,
        unique_pages: List[Frame],
        output_dir: Path,
        attempt_num: int,
        debug: bool,
        log: Callable[[str], None],
        on_page_detected: Optional[Callable[[int, np.ndarray], None]] = None,
        is_first: bool = False,
        plotter: Optional['BarProfilePlotter'] = None,
        ssim_score: Optional[float] = None,
    ) -> Optional[PageManifestEntry]:
        page_num = attempt_num
        t_commit_start = time.time()

        # Read full-res A/B frames from original video when available,
        # so the merge operates on full-resolution data instead of scan-res
        full_a = full_b = None
        if self._original_video_path:
            full_a = self._read_full_frame_from_original(frame_a.index, frame_a.timestamp)
            full_b = self._read_full_frame_from_original(frame_b.index, frame_b.timestamp)
        elif self.ocr_service.is_enabled() or debug:
            full_a, _ = self.video.read_full_frame_at(frame_a.index)
            full_b, _ = self.video.read_full_frame_at(frame_b.index)

        if debug:
            if full_a is not None:
                success, buf = cv2.imencode('.png', full_a)
                if success:
                    buf.tofile(str(output_dir / "diagnostics" / f"page_{page_num:03d}_A.png"))
            if full_b is not None:
                success, buf = cv2.imencode('.png', full_b)
                if success:
                    buf.tofile(str(output_dir / "diagnostics" / f"page_{page_num:03d}_B.png"))

        # Merge frames — use full-res when available, scan-res as fallback
        merge_a = full_a if full_a is not None else frame_a.image
        merge_b = full_b if full_b is not None else frame_b.image
        debug_profile_path = str(output_dir / "diagnostics" / f"bar_profile_page_{page_num:03d}.txt") if debug else None
        mr = self.video.merge_frames(
            merge_a, merge_b, self.config.b_overlay_width_ratio,
            self.config.default_crop_ratio, self.config.bar_min_diff_threshold,
            self.config.bar_padding_px, debug_profile_path
        )
        full_img = mr.merged
        merge_x = mr.merge_x
        log(f"  Merge result: {len(mr.spikes)} spike(s), merge_x={merge_x} for page {page_num}")

        # Deduplication check
        is_dup = False
        merged_number = None
        if self.ocr_service.is_enabled() and full_a is not None and full_b is not None:
            ocr_mr = self.video.merge_frames(
                full_a, full_b, self.config.b_overlay_width_ratio,
                self.config.default_crop_ratio, self.config.bar_min_diff_threshold,
                self.config.bar_padding_px, None
            )
            merged_number = self.ocr_service.get_leftmost_number(
                ocr_mr.merged, self.config.duplicate_top_ratio,
                self.config.ocr_horizontal_ratio, self.config.ocr_confidence_threshold
            )

        # Guard rail: compute bar profile peaks once (skip for first page)
        has_clean_profile, has_left_spike, bar_peaks = self.deduplicator.check_bar_profile(
            frame_a.image, frame_b.image, self.config.default_crop_ratio
        )
        if bar_peaks:
            sorted_peaks = sorted(bar_peaks, key=lambda p: p[0])
            peak_str = ", ".join(f"col{p[0]}:{p[1]:.0f}" for p in sorted_peaks)
            log(f"  Dedup peaks: [{peak_str}] (n={len(bar_peaks)}, clean={has_clean_profile})")
        guard_rail_passed = True
        if not is_first:
            if not is_dup and not has_clean_profile:
                is_dup = True
                guard_rail_passed = False
                log(f"  [SKIP] Page {page_num}: No clean bar profile, treated as duplicate")
            if not is_dup and not has_left_spike:
                is_dup = True
                guard_rail_passed = False
                log(f"  [SKIP] Page {page_num}: Left spike outside margin, treated as duplicate")

        for existing in unique_pages:
            if self.deduplicator.is_duplicate(existing.image, full_img, b_number=merged_number):
                is_dup = True
                break

        if not is_dup:
            frame = Frame(full_img.copy(), frame_a.timestamp, frame_a.index)
            unique_pages.append(frame)
            self.file_service.save_page_image(output_dir, page_num, full_img)
            log(f"  New page detected at {frame_a.timestamp:.2f}s (Index: {frame_a.index})")
            if on_page_detected:
                on_page_detected(len(unique_pages) - 1, full_img)
        else:
            log(f"  Duplicate page skipped at {frame_a.timestamp:.2f}s")

        if plotter is not None:
            plot_path = output_dir / "diagnostics" / f"bar_profile_page_{page_num:03d}.png"
            w_full = frame_a.image.shape[1]
            merge_x_640 = int(mr.merge_x * (640 / w_full)) if w_full > 0 else 0
            left_spike_col = -1
            if len(bar_peaks) >= 2:
                sorted_ps = sorted(bar_peaks, key=lambda p: p[0])
                left_spike_col = sorted_ps[0][0]
            plotter.plot(
                col_sums=mr.col_sums,
                spikes=mr.spikes,
                merge_x_640=merge_x_640,
                margin_col=int(640 * self.config.bar_left_margin),
                left_spike_col=left_spike_col,
                has_left_spike=has_left_spike,
                has_clean=has_clean_profile,
                output_path=plot_path,
                page_num=page_num,
            )

        attempt_duration_ms = (time.time() - t_commit_start) * 1000

        return PageManifestEntry(
            page=attempt_num,
            timestamp=frame_a.timestamp,
            frame_index=frame_a.index,
            bar_x=merge_x,
            bar_width=0,
            merge_x=merge_x,
            is_duplicate=is_dup,
            ocr_number=str(merged_number) if merged_number is not None else None,
            ssim_score=ssim_score,
            guard_rail_passed=guard_rail_passed,
            attempt_duration_ms=round(attempt_duration_ms, 1),
        )


# ═══════════════════════════════════════════════════════════════════════════
#  BarProfilePlotter – matplotlib diagnostic plots (optional)
#  PURE DISPLAY — no computation, all data provided by caller.
# ═══════════════════════════════════════════════════════════════════════════

class BarProfilePlotter:
    """Generates matplotlib bar profile diagnostic plots.

    Pure display — all data (col_sums, spikes, merge point) must be
    pre-computed and passed in.  Lazy-imports matplotlib on first use.
    Can be disabled by not passing to PageCommitter (pass None instead).
    """

    def __init__(self):
        self._plt = None

    def plot(
        self,
        col_sums: np.ndarray,
        spikes: list,
        merge_x_640: int,
        margin_col: int,
        left_spike_col: int = -1,
        has_left_spike: bool = False,
        has_clean: bool = False,
        output_path: Path = None,
        page_num: int = 0,
    ):
        if self._plt is None:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            self._plt = plt
        plt = self._plt

        fig, ax = plt.subplots(figsize=(10, 4))
        x = np.arange(len(col_sums))
        ax.fill_between(x, 0, col_sums, alpha=0.4, color='steelblue')
        ax.plot(x, col_sums, color='steelblue', linewidth=1)

        max_val = max(np.max(col_sums), 1)

        ax.axvline(x=margin_col, color='red', linewidth=2, alpha=0.7)
        ax.annotate(f'Left margin cutoff (col {margin_col})',
                    xy=(margin_col, max_val * 0.9), fontsize=8, color='red',
                    fontweight='bold', rotation=90, va='bottom')

        # Spike lines — annotate up to 2 spikes across full profile
        n_spikes = len(spikes)
        if n_spikes >= 1:
            sorted_spikes = sorted(spikes[:2], key=lambda p: p[0])
            colors = ['orange', 'purple']
            labels = ['Bar in A (old)', 'Bar in B (new)']
            for pi, (col, val) in enumerate(sorted_spikes):
                ax.axvline(x=col, color=colors[pi], linestyle='--', alpha=0.7)
                ax.annotate(f'{labels[pi]} (col {col})', xy=(col, val),
                            xytext=(5, 5), textcoords='offset points', fontsize=8,
                            color=colors[pi])

            if n_spikes >= 2 and left_spike_col >= 0:
                ax.annotate('LEFT SPIKE OK' if has_left_spike else 'LEFT SPIKE REJECTED',
                            xy=(left_spike_col, 0), fontsize=8,
                            color='green' if has_left_spike else 'red',
                            fontweight='bold')

        annot_x = min(len(col_sums) - 80, 600)
        if has_clean:
            ax.annotate(f'{n_spikes} SPIKES OK', xy=(annot_x, max_val * 0.15), fontsize=9,
                        color='green', fontweight='bold')
        else:
            ax.annotate(f'{n_spikes} SPIKES — REJECTED (need 0 or 2)', xy=(annot_x, max_val * 0.15), fontsize=9,
                        color='red', fontweight='bold')

        # Merge cutoff line
        if 0 < merge_x_640 < len(col_sums):
            ax.axvline(x=merge_x_640, color='crimson', linestyle='-', alpha=0.9, linewidth=2)
            ax.annotate(f'Overlay cutoff (col {merge_x_640})', xy=(merge_x_640, max_val * 0.65),
                        fontsize=8, color='crimson', fontweight='bold',
                        rotation=90, va='bottom')

        ax.set_xlabel('Column (640px scale)')
        ax.set_ylabel('Summed absdiff')
        ax.set_title(f'Page {page_num} — Bar Profile')
        ax.set_xlim(0, len(col_sums))

        plt.tight_layout()
        if output_path:
            plt.savefig(str(output_path), dpi=150)
        plt.close(fig)
