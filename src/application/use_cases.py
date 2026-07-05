import cv2
import os
import time
import numpy as np
from pathlib import Path
from typing import Callable, List, Optional, TextIO
from skimage.metrics import structural_similarity as ssim

from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from src.domain.interfaces import IVideoService, IOcrService, IPdfService, IFileService
from src.domain.deduplication import Deduplicator


class ExtractScoreUseCase:
    def __init__(
        self,
        video_service: IVideoService,
        ocr_service: IOcrService,
        file_service: IFileService,
        config: ScoreConfig
    ):
        self.video_service = video_service
        self.ocr_service = ocr_service
        self.file_service = file_service
        self.config = config
        self.deduplicator = Deduplicator(config, ocr_service)
        self._attempt_num = 0

    def execute(
        self,
        video_path: str,
        output_dir: Path,
        no_ocr: bool = False,
        start_time: float = -1.0,
        debug: bool = False,
        duration: float = 0.0,
        on_log: Callable[[str], None] = print,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_page_detected: Optional[Callable[[int, np.ndarray], None]] = None,
        is_cancelled: Callable[[], bool] = lambda: False,
    ) -> List[Frame]:
        self.video_service.open_video(video_path)
        self._orig_w, self._orig_h = self.video_service.get_original_size()

        effective_ocr: IOcrService
        if no_ocr:
            from src.domain.interfaces import _NoopOcrService
            effective_ocr = _NoopOcrService()
        else:
            if not self.ocr_service.initialize():
                on_log("[Warning] OCR initialization failed, continuing without OCR.")
                from src.domain.interfaces import _NoopOcrService
                effective_ocr = _NoopOcrService()
            else:
                effective_ocr = self.ocr_service

        deduplicator = Deduplicator(self.config, effective_ocr)
        ocr_available = effective_ocr.is_enabled()

        # Write extraction log to debug/ subfolder
        log_file: Optional[TextIO] = None
        if debug:
            try:
                log_path = output_dir / "debug" / "extraction.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_file = open(log_path, "w", encoding="utf-8")
            except Exception:
                pass

        def log(msg: str):
            on_log(msg)
            if log_file:
                log_file.write(msg + "\n")
                log_file.flush()

        fps = self.video_service.get_fps()
        cooldown_frames = int(self.config.min_screenshot_interval * fps)
        stability_frames = int(self.config.b_capture_delay * fps)
        seek_step = max(1, int(self.config.frame_check_interval * fps))
        scan_step = max(1, int(0.1 * fps))


        unique_pages: List[Frame] = []
        last_trigger_idx = -cooldown_frames
        last_stable_frame: Optional[Frame] = None

        def get_roi(img):
            h, w = img.shape[:2]
            y_end = int(h * self.config.top_analysis_ratio)
            roi = img[0:y_end, :]
            small = cv2.resize(roi, (320, int(320 * (y_end / h))))
            return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        log(f"Processing video: {video_path}")

        # Handle start-time capture
        if start_time >= 0:
            start_idx = int(start_time * fps)
            a_img, a_ts = self.video_service.read_frame_at(start_idx)
            if a_img is not None:
                log(f"Start-time capture at {a_ts:.1f}s...")
                b_idx = start_idx + stability_frames
                b_img, b_ts = self.video_service.read_frame_at(b_idx)
                if b_img is None:
                    b_img, b_ts = a_img.copy(), a_ts
                    b_idx = start_idx

                a_frame = Frame(a_img.copy(), a_ts, start_idx)
                b_frame = Frame(b_img.copy(), b_ts, b_idx)
                self._attempt_num += 1
                self._store_page(a_frame, b_frame, unique_pages, output_dir, debug, log,
                                 effective_ocr, deduplicator, on_page_detected)
                last_trigger_idx = start_idx
                last_stable_frame = b_frame
                current_idx = b_idx
            else:
                log("Warning: Could not seek to start time, starting from beginning.")
                dummy_img, dummy_ts = self.video_service.read_frame_at(0)
                if dummy_img is None:
                    raise RuntimeError("Could not read video.")
                current_idx = 0
                last_stable_frame = Frame(dummy_img.copy(), dummy_ts, 0)
        else:
            dummy_img, dummy_ts = self.video_service.read_frame_at(0)
            if dummy_img is None:
                raise RuntimeError("Could not read video.")
            current_idx = 0
            last_stable_frame = Frame(dummy_img.copy(), dummy_ts, 0)

        log(f"Starting extraction from ~{current_idx / fps:.1f}s...")

        t_loop = time.time()
        n_frames = 0
        while True:
            if is_cancelled():
                log("Extraction cancelled.")
                break

            t0 = time.time()
            if seek_step > 1:
                self.video_service.skip_frames(seek_step - 1)
            frame_img, timestamp, current_idx = self.video_service.read_next_frame()
            if frame_img is None:
                break

            t_read = time.time() - t0
            current_frame = Frame(frame_img, timestamp, current_idx)
            n_frames += 1

            total_frames = self.video_service.get_total_frames()
            if total_frames > 0:
                percent = min(95.0, (current_idx / total_frames) * 100.0)
            else:
                percent = 0.0
            if on_progress:
                elapsed = time.time() - t_loop
                avg = elapsed / n_frames
                on_progress(percent, f"Frame {current_idx}/{total_frames} at {timestamp:.1f}s  ({t_read*1000:.0f}ms/frame  {elapsed:.0f}s elapsed)")

            # Blank-content detection
            if len(unique_pages) > 0:
                roi_std = np.std(get_roi(current_frame.image))
                if roi_std < self.config.blank_content_std_threshold:
                    log("  End of score detected (blank content).")
                    break

            # Duration limit
            if duration > 0 and timestamp >= duration:
                log(f"  Duration limit reached ({duration:.1f}s).")
                break

            # Page change detection
            if (
                (current_idx - last_trigger_idx) > cooldown_frames
                and last_stable_frame is not None
            ):
                score = ssim(get_roi(last_stable_frame.image), get_roi(current_frame.image))

                if score < self.config.change_detection_threshold:
                    log(f"  Change detected at ~{timestamp:.1f}s, scanning for precise trigger...")

                    # Scan Mode: current frame is trigger point
                    a_frame = current_frame

                    # Apply a_capture_delay to skip page-flip animation
                    delay_frames = int(self.config.a_capture_delay * fps)
                    if delay_frames > 0:
                        cap_idx = a_frame.index + delay_frames
                        cap_img, cap_ts = self.video_service.read_frame_at(cap_idx)
                        if cap_img is not None:
                            a_frame = Frame(cap_img.copy(), cap_ts, cap_idx)

                    # Capture B-frame
                    b_idx = a_frame.index + stability_frames
                    b_img, b_ts = self.video_service.read_frame_at(b_idx)
                    if b_img is None:
                        b_img = a_frame.image.copy()
                        b_ts = a_frame.timestamp

                    b_frame = Frame(b_img.copy(), b_ts, b_idx)
                    self._attempt_num += 1
                    self._store_page(a_frame, b_frame, unique_pages, output_dir, debug, log,
                                     effective_ocr, deduplicator, on_page_detected)
                    last_trigger_idx = a_frame.index

            last_stable_frame = current_frame

        # Tail scan: check last 20 seconds for "Thank you" end-credits (skip if explicit end duration)
        if duration <= 0 and not is_cancelled():
            try:
                total_frames = self.video_service.get_total_frames()
                last_20s_frame = total_frames - int(20 * fps)
                tail_start = max(last_20s_frame, current_idx)
                tail_step = int(2.0 * fps)

                if tail_start < total_frames and ocr_available:
                    log("  Scanning final 20 seconds for end-credits...")
                    tail_idx = tail_start
                    while tail_idx < total_frames:
                        if is_cancelled():
                            break
                        tail_img, tail_ts = self.video_service.read_full_frame_at(tail_idx)
                        if tail_img is None:
                            break
                        if effective_ocr.detect_keywords(tail_img, ["thank"]):
                            trim_time = tail_ts - 2.0
                            log(f"  'Thank you' detected at {tail_ts:.1f}s, trimming after {trim_time:.1f}s.")
                            unique_pages[:] = [p for p in unique_pages if p.timestamp <= trim_time]
                            break
                        if debug:
                            texts = effective_ocr.get_texts(tail_img)
                            if texts:
                                log(f"  [Debug] Tail frame at {tail_ts:.1f}s OCR: {texts}")
                        tail_idx += tail_step
                    else:
                        log("  No 'Thank you' detected in final 20 seconds.")
            except Exception:
                pass  # tail scan is best-effort

        if log_file:
            log_file.close()

        return unique_pages

    def _save_bar_profile_plot(
        self, frame_a: np.ndarray, frame_b: np.ndarray,
        crop_ratio: float, bar_x: int, bar_width: int, bar_padding_px: int,
        margin_col: int, output_path: Path, page_num: int,
        deduplicator, peaks=None, has_clean=None, has_left_spike=None
    ):
        if not hasattr(self, '_plt'):
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            self._plt = plt
        plt = self._plt

        h, w = frame_a.shape[:2]
        scale = 640 / w
        target_h = int(h * scale)
        a_small = cv2.resize(frame_a, (640, target_h))
        b_small = cv2.resize(frame_b, (640, target_h))

        crop_h = int(target_h * crop_ratio)
        a_top = cv2.cvtColor(a_small[:crop_h, :], cv2.COLOR_BGR2GRAY).astype(float)
        b_top = cv2.cvtColor(b_small[:crop_h, :], cv2.COLOR_BGR2GRAY).astype(float)

        diff = np.abs(a_top - b_top)
        col_sums = np.sum(diff, axis=0)

        fig, ax = plt.subplots(figsize=(10, 4))
        x = np.arange(len(col_sums))
        ax.fill_between(x, 0, col_sums, alpha=0.4, color='steelblue')
        ax.plot(x, col_sums, color='steelblue', linewidth=1)

        max_val = max(np.max(col_sums), 1)

        ax.axvline(x=margin_col, color='red', linewidth=2, alpha=0.7)
        ax.annotate(f'Left {self.config.bar_left_margin:.0%} cutoff (col {margin_col})',
                    xy=(margin_col, max_val * 0.9), fontsize=8, color='red',
                    fontweight='bold', rotation=90, va='bottom')

        if peaks is None:
            peaks = deduplicator._get_bar_profile_peaks(frame_a, frame_b, crop_ratio)

        n_peaks = len(peaks)
        two_spike_ok = 2 <= n_peaks <= 4
        if has_left_spike is None and two_spike_ok:
            has_left_spike = deduplicator.has_left_spike_in_margin(frame_a, frame_b, crop_ratio)
        elif has_left_spike is None:
            has_left_spike = False

        if n_peaks >= 1:
            sorted_peaks = sorted(peaks[:2], key=lambda p: p[0])
            colors = ['orange', 'purple']
            labels = ['Bar in A (old)', 'Bar in B (new)']
            for pi, (col, val) in enumerate(peaks[:2]):
                ax.axvline(x=col, color=colors[pi], linestyle='--', alpha=0.7)
                ax.annotate(f'{labels[pi]} (col {col})', xy=(col, val),
                            xytext=(5, 5), textcoords='offset points', fontsize=8,
                            color=colors[pi])

            if n_peaks >= 2:
                left_col = sorted_peaks[0][0]
                ax.annotate('LEFT SPIKE OK' if has_left_spike else 'LEFT SPIKE REJECTED',
                            xy=(left_col, 0), fontsize=8,
                            color='green' if has_left_spike else 'red',
                            fontweight='bold')

        if two_spike_ok:
            ax.annotate(f'{n_peaks} PEAKS OK', xy=(600, max_val * 0.15), fontsize=9,
                        color='green', fontweight='bold')
        else:
            ax.annotate(f'{n_peaks} PEAKS — REJECTED (need 2-4)', xy=(400, max_val * 0.15), fontsize=9,
                        color='red', fontweight='bold')

        bar_x_640 = int(round(bar_x * (640 / w)))
        bar_left_640 = max(0, bar_x_640 - int(round(bar_width * (640 / w))))
        merge_x_640 = max(0, min(640, bar_left_640 + int(round(bar_padding_px * (640 / w)))))
        if bar_x_640 > 0:
            ax.axvline(x=bar_x_640, color='green', linestyle=':', alpha=0.5)
            ax.annotate(f'right={bar_x_640}', xy=(bar_x_640, max_val * 0.4),
                        fontsize=7, color='green')
            if bar_left_640 > 0:
                ax.axvline(x=bar_left_640, color='green', linestyle=':', alpha=0.3)
                ax.annotate(f'left={bar_left_640}', xy=(bar_left_640, max_val * 0.35),
                            fontsize=7, color='green')
            if 0 < merge_x_640 < 640:
                ax.axvline(x=merge_x_640, color='darkgreen', linestyle='-', alpha=0.8)
                ax.annotate(f'merge_x={merge_x_640}', xy=(merge_x_640, max_val * 0.3),
                            fontsize=7, color='darkgreen')

        ax.set_xlabel('Column (640px scale)')
        ax.set_ylabel('Summed absdiff')
        ax.set_title(f'Page {page_num} — Bar Profile')
        ax.set_xlim(0, len(col_sums))

        plt.tight_layout()
        plt.savefig(str(output_path), dpi=150)
        plt.close(fig)

    def _store_page(
        self,
        frame_a: Frame,
        frame_b: Frame,
        unique_pages: List[Frame],
        output_dir: Path,
        debug: bool,
        log: Callable[[str], None],
        ocr_service: IOcrService,
        deduplicator,
        on_page_detected: Optional[Callable[[int, np.ndarray], None]] = None,
    ):
        page_num = self._attempt_num

        # Merge frames (always applied, including start-time)
        debug_path = str(output_dir / "debug" / f"bar_profile_page_{page_num:03d}.txt") if debug else None
        merged_img, bar_x, bar_width = self.video_service.merge_frames(
            frame_a.image, frame_b.image, self.config.b_overlay_width_ratio,
            self.config.default_crop_ratio, self.config.bar_min_diff_threshold,
            self.config.bar_padding_px, debug_path
        )
        log(f"  Bar right edge at x={bar_x}, width={bar_width}px for page {page_num}")

        # Upscale merged to original resolution (used for saving, storing, and dedup comparison)
        full_img = cv2.resize(merged_img, (self._orig_w, self._orig_h),
                              interpolation=cv2.INTER_LINEAR)

        # Read full-res A/B once, use for both debug and OCR
        full_a = full_b = None
        if ocr_service.is_enabled() or debug:
            full_a, _ = self.video_service.read_full_frame_at(frame_a.index)
            full_b, _ = self.video_service.read_full_frame_at(frame_b.index)
        if debug:
            if full_a is not None:
                cv2.imwrite(str(output_dir / "debug" / f"page_{page_num:03d}_A.png"), full_a)
            if full_b is not None:
                cv2.imwrite(str(output_dir / "debug" / f"page_{page_num:03d}_B.png"), full_b)

        # Deduplication check
        is_dup = False
        merged_number = None
        if ocr_service.is_enabled() and full_a is not None and full_b is not None:
            ocr_merged, _ = self.video_service.merge_frames(
                full_a, full_b, self.config.b_overlay_width_ratio,
                self.config.default_crop_ratio, self.config.bar_min_diff_threshold,
                self.config.bar_padding_px, None
            )
            merged_number = ocr_service.get_leftmost_number(
                ocr_merged, self.config.duplicate_top_ratio,
                self.config.ocr_horizontal_ratio, self.config.ocr_confidence_threshold
            )

        # Guard rail: compute bar profile peaks once
        has_clean_profile, has_left_spike, bar_peaks = deduplicator.check_bar_profile(
            frame_a.image, frame_b.image, self.config.default_crop_ratio
        )
        if not is_dup and not has_clean_profile:
            is_dup = True
            log(f"  Page {page_num}: No clean bar profile, treated as duplicate")
        if not is_dup and not has_left_spike:
            is_dup = True
            log(f"  Page {page_num}: Left spike outside margin, treated as duplicate")

        for existing in unique_pages:
            if deduplicator.is_duplicate(existing.image, full_img, b_number=merged_number):
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

        if debug:
            plot_path = output_dir / "debug" / f"bar_profile_page_{page_num:03d}.png"
            self._save_bar_profile_plot(
                frame_a.image, frame_b.image, self.config.default_crop_ratio,
                bar_x, bar_width, self.config.bar_padding_px,
                int(640 * self.config.bar_left_margin), plot_path, page_num,
                deduplicator, peaks=bar_peaks, has_clean=has_clean_profile,
                has_left_spike=has_left_spike
            )


class GeneratePdfUseCase:
    def __init__(self, pdf_service: IPdfService, config: ScoreConfig):
        self.pdf_service = pdf_service
        self.config = config

    def execute(self, frames: List[Frame], output_path: str):
        if not frames:
            print("No pages detected. PDF not generated.")
            return

        images = [f.image for f in frames]
        final_title = Path(output_path).stem
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        print(f"Generating PDF with {len(frames)} pages...")
        self.pdf_service.create_pdf(images, output, self.config, title_hint=final_title)
        print(f"PDF generated: {output_path}")
