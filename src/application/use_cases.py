import cv2
import os
import numpy as np
from pathlib import Path
from typing import List
from skimage.metrics import structural_similarity as ssim
from rich.progress import Progress

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
        self.debug = False
        self.log_file = None

    def _log(self, msg: str):
        print(msg)
        if self.log_file:
            self.log_file.write(msg + "\n")
            self.log_file.flush()

    def execute(self, video_path: str, no_ocr: bool = False, start_time: float = 0.0, debug: bool = False, duration: float = 0.0) -> List[Frame]:
        self.debug = debug
        self.video_service.open_video(video_path)

        if not no_ocr:
            if not self.ocr_service.initialize():
                print("\n[Warning] OCR initialization failed.")
                choice = input("Do you want to continue without OCR? (y/n): ")
                if choice.lower() != 'y':
                    raise RuntimeError("OCR required but failed to initialize.")

        sandbox_path = self.file_service.create_sandbox()
        self.log_file = open(sandbox_path / "extraction.log", "w", encoding="utf-8")
        if self.debug:
            try:
                os.startfile(str(sandbox_path.resolve()))
            except Exception as e:
                self._log(f"  [Debug] Could not open temp folder: {e}")

        fps = self.video_service.get_fps()
        cooldown_frames = int(self.config.min_screenshot_interval * fps)
        stability_frames = int(self.config.b_capture_delay * fps)
        seek_step = max(1, int(self.config.frame_check_interval * fps))
        scan_step = max(1, int(0.1 * fps))

        unique_pages = []
        last_trigger_idx = -cooldown_frames
        last_stable_frame = None

        def get_roi(img):
            h, w = img.shape[:2]
            y_end = int(h * self.config.top_analysis_ratio)
            roi = img[0:y_end, :]
            small = cv2.resize(roi, (320, int(320 * (y_end / h))))
            return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        self._log(f"Processing video: {video_path}")

        # Handle start-time capture
        if start_time >= 0:
            start_idx = int(start_time * fps)
            a_img, a_ts = self.video_service.read_frame_at(start_idx)
            if a_img is not None:
                self._log(f"Start-time capture at {a_ts:.1f}s...")
                b_idx = start_idx + stability_frames
                b_img, b_ts = self.video_service.read_frame_at(b_idx)
                if b_img is None:
                    b_img, b_ts = a_img.copy(), a_ts
                    b_idx = start_idx
                a_frame = Frame(a_img.copy(), a_ts, start_idx)
                b_frame = Frame(b_img.copy(), b_ts, b_idx)
                self._process_new_page(a_frame, b_frame, unique_pages, skip_merge=True)
                last_trigger_idx = start_idx
                last_stable_frame = b_frame
                current_idx = b_idx
            else:
                self._log(f"Warning: Could not seek to {start_time}s, starting from beginning.")
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

        self._log(f"Starting extraction from ~{current_idx / fps:.1f}s...")

        while True:
            current_idx += seek_step
            frame_img, timestamp = self.video_service.read_frame_at(current_idx)
            if frame_img is None:
                break

            current_frame = Frame(frame_img.copy(), timestamp, current_idx)

            # Status indicator
            print(f"Checking second {timestamp:.1f}...", end='\r', flush=True)

            # Blank-content detection
            if len(unique_pages) > 0:
                roi_std = np.std(get_roi(current_frame.image))
                if roi_std < self.config.blank_content_std_threshold:
                    self._log(f"  End of score detected (blank content).")
                    break

            # Duration limit
            if duration > 0 and timestamp >= duration:
                self._log(f"  Duration limit reached ({duration:.1f}s).")
                break

            # Page change detection
            if (
                (current_idx - last_trigger_idx) > cooldown_frames
                and last_stable_frame is not None
            ):
                score = ssim(get_roi(last_stable_frame.image), get_roi(current_frame.image))

                if score < self.config.change_detection_threshold:
                    self._log(f"  Change detected at ~{timestamp:.1f}s, scanning for precise trigger...")

                    # Scan Mode: backtrack and check every 0.1s
                    scan_start = last_stable_frame.index + scan_step
                    a_frame = None

                    for scan_idx in range(scan_start, current_idx + 1, scan_step):
                        scan_img, scan_ts = self.video_service.read_frame_at(scan_idx)
                        if scan_img is None:
                            break
                        scan_score = ssim(get_roi(last_stable_frame.image), get_roi(scan_img))
                        if scan_score < self.config.change_detection_threshold:
                            a_frame = Frame(scan_img.copy(), scan_ts, scan_idx)
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
                    self._process_new_page(a_frame, b_frame, unique_pages)
                    last_trigger_idx = a_frame.index

            last_stable_frame = current_frame

        print()

        # Tail scan: check last 20 seconds for "Thank you" end-credits
        try:
            total_frames = self.video_service.get_total_frames()
            last_20s_frame = total_frames - int(20 * fps)
            tail_start = max(last_20s_frame, current_idx)
            tail_step = int(2.0 * fps)

            if tail_start < total_frames and self.ocr_service.is_enabled():
                self._log("  Scanning final 20 seconds for end-credits...")
                tail_idx = tail_start
                while tail_idx < total_frames:
                    tail_img, tail_ts = self.video_service.read_frame_at(tail_idx)
                    if tail_img is None:
                        break
                    if self.ocr_service.detect_keywords(tail_img, ["thank"]):
                        trim_time = tail_ts - 2.0
                        self._log(f"  'Thank you' detected at {tail_ts:.1f}s, trimming after {trim_time:.1f}s.")
                        unique_pages[:] = [p for p in unique_pages if p.timestamp <= trim_time]
                        break
                    if self.debug:
                        texts = self.ocr_service.get_texts(tail_img)
                        if texts:
                            self._log(f"  [Debug] Tail frame at {tail_ts:.1f}s OCR: {texts}")
                    tail_idx += tail_step
                else:
                    self._log("  No 'Thank you' detected in final 20 seconds.")
        except Exception:
            pass  # tail scan is best-effort

        if self.log_file:
            self.log_file.close()

        return unique_pages

    def _process_new_page(self, frame_a: Frame, frame_b: Frame, unique_pages: List[Frame], skip_merge: bool = False):
        page_num = len(unique_pages) + 1

        if skip_merge:
            merged_img, bar_x = frame_a.image, 0
            self._log("  Start-time capture, merge skipped")
        else:
            merged_img, bar_x = self.video_service.merge_frames(
                frame_a.image, frame_b.image, self.config.b_overlay_width_ratio, self.config.default_crop_ratio
            )
            self._log(f"  Bar edge at x={bar_x} for page {page_num}")

        if self.debug:
            sandbox = self.file_service.get_sandbox_path()
            a_path = str(sandbox / f"page_{page_num:03d}_A.png")
            b_path = str(sandbox / f"page_{page_num:03d}_B.png")
            cv2.imwrite(a_path, frame_a.image)
            cv2.imwrite(b_path, frame_b.image)

        is_dup = False

        merged_number = None
        if self.ocr_service.is_enabled():
            merged_number = self.ocr_service.get_leftmost_number(
                merged_img, self.config.duplicate_top_ratio,
                self.config.ocr_horizontal_ratio, self.config.ocr_confidence_threshold
            )

        for existing in unique_pages:
            if self.deduplicator.is_duplicate(existing.image, merged_img, b_number=merged_number):
                is_dup = True
                break

        if not is_dup:
            frame_a.image = merged_img
            unique_pages.append(frame_a)
            self._log(f"  New page detected at {frame_a.timestamp:.2f}s (Index: {frame_a.index})")
            sandbox = self.file_service.get_sandbox_path()
            m_path = str(sandbox / f"page_{page_num:03d}_merged.png")
            cv2.imwrite(m_path, merged_img)
        else:
            self._log(f"  Duplicate page skipped at {frame_a.timestamp:.2f}s")

class GeneratePdfUseCase:
    def __init__(self, pdf_service: IPdfService, file_service: IFileService, config: ScoreConfig):
        self.pdf_service = pdf_service
        self.file_service = file_service
        self.config = config

    def execute(self, frames: List[Frame], output_path: str):
        if not frames:
            print("No pages detected. PDF not generated.")
            return

        sandbox_path = self.file_service.get_sandbox_path()
        draft_pdf_name = "draft_output.pdf"
        draft_pdf_path = sandbox_path / draft_pdf_name

        print(f"Generating PDF with {len(frames)} pages...")
        images = [f.image for f in frames]

        final_title = Path(output_path).stem

        old_cwd = os.getcwd()
        os.chdir(sandbox_path)
        try:
            self.pdf_service.create_pdf(images, Path(draft_pdf_name), self.config, title_hint=final_title)
        finally:
            os.chdir(old_cwd)

        print(f"Finalizing PDF: {output_path}")
        self.file_service.move_to_final(draft_pdf_name, Path(output_path))
