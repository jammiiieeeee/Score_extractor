import cv2
import os
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

        effective_ocr: IOcrService
        if no_ocr:
            from src.infrastructure.ocr_service import OcrService
            effective_ocr = OcrService()
        else:
            if not self.ocr_service.initialize():
                on_log("[Warning] OCR initialization failed, continuing without OCR.")
                from src.infrastructure.ocr_service import OcrService
                effective_ocr = OcrService()
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

        while True:
            if is_cancelled():
                log("Extraction cancelled.")
                break

            current_idx += seek_step
            frame_img, timestamp = self.video_service.read_frame_at(current_idx)
            if frame_img is None:
                break

            current_frame = Frame(frame_img.copy(), timestamp, current_idx)

            total_frames = self.video_service.get_total_frames()
            if total_frames > 0:
                percent = min(95.0, (current_idx / total_frames) * 100.0)
            else:
                percent = 0.0
            if on_progress:
                on_progress(percent, f"Checking frame at {timestamp:.1f}s")

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

                    # Scan Mode: backtrack and check every 0.1s
                    scan_start = last_stable_frame.index + scan_step
                    a_frame = None

                    for scan_idx in range(scan_start, current_idx + 1, scan_step):
                        if is_cancelled():
                            break
                        scan_img, scan_ts = self.video_service.read_frame_at(scan_idx)
                        if scan_img is None:
                            break
                        scan_score = ssim(get_roi(last_stable_frame.image), get_roi(scan_img))
                        if scan_score < self.config.change_detection_threshold:
                            a_frame = Frame(scan_img.copy(), scan_ts, scan_idx)
                            break

                    if is_cancelled():
                        break

                    if a_frame is None:
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
                        tail_img, tail_ts = self.video_service.read_frame_at(tail_idx)
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
        page_num = len(unique_pages) + 1

        # Merge frames (always applied, including start-time)
        debug_path = str(output_dir / "debug" / f"bar_profile_page_{page_num:03d}.txt") if debug else None
        merged_img, bar_x = self.video_service.merge_frames(
            frame_a.image, frame_b.image, self.config.b_overlay_width_ratio,
            self.config.default_crop_ratio, self.config.bar_min_diff_threshold,
            self.config.bar_padding_px, debug_path
        )
        log(f"  Bar edge at x={bar_x} for page {page_num}")

        # Write debug A/B frames
        if debug:
            cv2.imwrite(str(output_dir / "debug" / f"page_{page_num:03d}_A.png"), frame_a.image)
            cv2.imwrite(str(output_dir / "debug" / f"page_{page_num:03d}_B.png"), frame_b.image)

        # Deduplication check
        is_dup = False
        merged_number = None
        if ocr_service.is_enabled():
            merged_number = ocr_service.get_leftmost_number(
                merged_img, self.config.duplicate_top_ratio,
                self.config.ocr_horizontal_ratio, self.config.ocr_confidence_threshold
            )

        for existing in unique_pages:
            if deduplicator.is_duplicate(existing.image, merged_img, b_number=merged_number):
                is_dup = True
                break

        if not is_dup:
            frame = Frame(merged_img.copy(), frame_a.timestamp, frame_a.index)
            unique_pages.append(frame)
            self.file_service.save_page_image(output_dir, page_num, merged_img)
            log(f"  New page detected at {frame_a.timestamp:.2f}s (Index: {frame_a.index})")
            if on_page_detected:
                on_page_detected(len(unique_pages) - 1, merged_img)
        else:
            log(f"  Duplicate page skipped at {frame_a.timestamp:.2f}s")


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
