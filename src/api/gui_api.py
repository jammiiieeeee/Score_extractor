import threading
import time
import json
import os
import sys
import cv2
import numpy as np
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from skimage.metrics import structural_similarity as ssim

from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from src.domain.deduplication import Deduplicator
from src.infrastructure.video_service import VideoService
from src.infrastructure.ocr_service import OcrService
from src.infrastructure.pdf_service import PdfService
from src.infrastructure.file_service import FileService


@dataclass
class VideoInfo:
    path: str
    duration: float
    fps: float
    width: int
    height: int
    frame_count: int


@dataclass
class ExtractionState:
    phase: str
    pages_detected: int
    elapsed_seconds: float
    current_timestamp: float


@dataclass
class SandboxInfo:
    path: str
    page_count: int
    created: datetime
    video_name: str


class GuiApi:
    def __init__(self, config_path: str = "config.json"):
        self._config_path = config_path
        self._config = self._load_config(config_path)
        self._file_service = FileService()
        self._video_service: Optional[VideoService] = None
        self._ocr_service: Optional[OcrService] = None
        self._pdf_service = PdfService()
        self._video_info: Optional[VideoInfo] = None
        self._pages: List[Frame] = []
        self._page_png_cache: List[Optional[bytes]] = []

        self._extraction_thread: Optional[threading.Thread] = None
        self._pdf_thread: Optional[threading.Thread] = None
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_flag = False
        self._debug_mode = False
        self._state = ExtractionState("idle", 0, 0.0, 0.0)
        self._extraction_start_time = 0.0

        self._on_progress: Optional[Callable] = None
        self._on_page_detected: Optional[Callable] = None
        self._on_log: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._on_completed: Optional[Callable] = None
        self._on_cancelled: Optional[Callable] = None
        self._on_download_completed: Optional[Callable] = None

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _load_config(config_path: str) -> ScoreConfig:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                return ScoreConfig(**data)
            except Exception:
                pass
        return ScoreConfig()

    @staticmethod
    def _encode_png(img: np.ndarray) -> Optional[bytes]:
        success, buf = cv2.imencode('.png', img)
        if not success:
            return None
        return buf.tobytes()

    @staticmethod
    def _decode_png(data: bytes) -> Optional[np.ndarray]:
        buf = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def _emit_progress(self, phase: str, percent: float, detail: str):
        if self._on_progress:
            try:
                self._on_progress(phase, percent, detail)
            except Exception:
                pass

    def _emit_page_detected(self, index: int, image_bytes: bytes):
        if self._on_page_detected:
            try:
                self._on_page_detected(index, image_bytes)
            except Exception:
                pass

    def _emit_log(self, message: str):
        if self._on_log:
            try:
                self._on_log(message)
            except Exception:
                pass

    def _emit_error(self, message: str):
        if self._on_error:
            try:
                self._on_error(message)
            except Exception:
                pass

    def _emit_completed(self, page_count: int):
        if self._on_completed:
            try:
                self._on_completed(page_count)
            except Exception:
                pass

    def _emit_cancelled(self):
        if self._on_cancelled:
            try:
                self._on_cancelled()
            except Exception:
                pass

    def _emit_download_completed(self, path: str):
        if self._on_download_completed:
            try:
                self._on_download_completed(path)
            except Exception:
                pass

    # ═════════════════════════════════════════════════════════════════════
    #  Config Management (1-5)
    # ═════════════════════════════════════════════════════════════════════

    def get_config(self) -> dict:
        return asdict(self._config)

    def update_config(self, updates: dict) -> dict:
        valid_float_0_1 = {
            "change_detection_threshold", "top_analysis_ratio",
            "b_overlay_width_ratio", "duplicate_top_ratio",
            "pixel_similarity_threshold", "row_similarity_threshold",
            "row_coverage_threshold", "ocr_horizontal_ratio",
            "default_crop_ratio", "crop_top_offset",
        }
        valid_float_any = {
            "frame_check_interval", "min_screenshot_interval",
            "a_capture_delay", "b_capture_delay",
            "blank_content_std_threshold", "bar_min_diff_threshold",
        }
        valid_int_1_20 = {"default_strips_per_page"}
        valid_int_0_100 = {"ocr_confidence_threshold"}

        valid_keys = valid_float_0_1 | valid_float_any | valid_int_1_20 | valid_int_0_100

        for key, value in updates.items():
            if key not in valid_keys:
                raise ValueError(f"Unknown config key: {key}")

            if key in valid_float_0_1:
                val = float(value)
                if not (0.0 <= val <= 1.0):
                    raise ValueError(f"{key} must be between 0.0 and 1.0")
                setattr(self._config, key, val)
            elif key in valid_float_any:
                setattr(self._config, key, float(value))
            elif key in valid_int_1_20:
                val = int(value)
                if not (1 <= val <= 20):
                    raise ValueError(f"{key} must be between 1 and 20")
                setattr(self._config, key, val)
            elif key in valid_int_0_100:
                val = int(value)
                if not (0 <= val <= 100):
                    raise ValueError(f"{key} must be between 0 and 100")
                setattr(self._config, key, val)

        return asdict(self._config)

    def reset_config(self) -> dict:
        self._config = ScoreConfig()
        return asdict(self._config)

    def load_config_file(self, path: str) -> dict:
        self._config = self._load_config(path)
        return asdict(self._config)

    def save_config_file(self, path: str) -> None:
        with open(path, 'w') as f:
            json.dump(asdict(self._config), f, indent=2)

    # ═════════════════════════════════════════════════════════════════════
    #  Video Management (6-9)
    # ═════════════════════════════════════════════════════════════════════

    def open_video(self, path: str) -> VideoInfo:
        if self._video_service is None:
            self._video_service = VideoService()
        self._video_service.open_video(path)
        fps = self._video_service.get_fps()
        frame_count = self._video_service.get_total_frames()
        cap = self._video_service.cap
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0.0

        self._video_info = VideoInfo(
            path=os.path.abspath(path),
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            frame_count=frame_count,
        )
        return self._video_info

    def get_video_info(self) -> Optional[VideoInfo]:
        return self._video_info

    def read_frame_at(self, timestamp: float) -> Optional[bytes]:
        if self._video_service is None or self._video_info is None:
            return None
        frame_idx = int(timestamp * self._video_info.fps)
        img, _ = self._video_service.read_frame_at(frame_idx)
        if img is None:
            return None
        return self._encode_png(img)

    def close_video(self) -> None:
        if self._video_service:
            self._video_service.close()
        self._video_info = None

    # ═════════════════════════════════════════════════════════════════════
    #  OCR Management (10-12)
    # ═════════════════════════════════════════════════════════════════════

    def init_ocr(self) -> bool:
        if self._ocr_service is None:
            self._ocr_service = OcrService()

        log_captured = []

        def capture_print(text):
            text = text.strip()
            if text:
                log_captured.append(text)
                self._emit_log(text)

        old_stdout = sys.stdout

        class CapturePrint:
            def write(self, text):
                capture_print(text)
            def flush(self):
                pass

        sys.stdout = CapturePrint()
        try:
            result = self._ocr_service.initialize()
        finally:
            sys.stdout = old_stdout

        return result

    def ocr_status(self) -> bool:
        if self._ocr_service is None:
            return False
        return self._ocr_service.is_enabled()

    def ocr_preview(self, image_bytes: bytes) -> list[str]:
        if self._ocr_service is None or not self._ocr_service.is_enabled():
            return []
        img = self._decode_png(image_bytes)
        if img is None:
            return []
        return self._ocr_service.get_texts(img)

    # ═════════════════════════════════════════════════════════════════════
    #  Callback Registry
    # ═════════════════════════════════════════════════════════════════════

    def set_on_progress(self, fn: Optional[Callable]):
        self._on_progress = fn

    def set_on_page_detected(self, fn: Optional[Callable]):
        self._on_page_detected = fn

    def set_on_log(self, fn: Optional[Callable]):
        self._on_log = fn

    def set_on_error(self, fn: Optional[Callable]):
        self._on_error = fn

    def set_on_completed(self, fn: Optional[Callable]):
        self._on_completed = fn

    def set_on_cancelled(self, fn: Optional[Callable]):
        self._on_cancelled = fn

    def set_on_download_completed(self, fn: Optional[Callable]):
        self._on_download_completed = fn

    # ═════════════════════════════════════════════════════════════════════
    #  Extraction Process (13-15)
    # ═════════════════════════════════════════════════════════════════════

    def start_extraction(self, video_path: Optional[str] = None, no_ocr: bool = False,
                         start_time: float = -1.0, duration: float = 0.0,
                         debug: bool = False) -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        if video_path is not None:
            self.open_video(video_path)

        if self._video_service is None or self._video_info is None:
            raise RuntimeError("No video opened. Call open_video() or provide video_path.")

        self._cancel_flag = False
        self._pages.clear()
        self._page_png_cache.clear()
        self._state = ExtractionState("extracting", 0, 0.0, 0.0)
        self._extraction_start_time = time.time()

        self._extraction_thread = threading.Thread(
            target=self._run_extraction,
            args=(no_ocr, start_time, duration, self._debug_mode),
            daemon=True,
        )
        self._extraction_thread.start()

    def cancel_extraction(self) -> None:
        self._cancel_flag = True
        self._state = ExtractionState("cancelling", self._state.pages_detected,
                                       time.time() - self._extraction_start_time,
                                       self._state.current_timestamp)

    def get_extraction_state(self) -> ExtractionState:
        if self._state.phase in ("extracting", "cancelling"):
            elapsed = time.time() - self._extraction_start_time
            self._state.elapsed_seconds = elapsed
        return self._state

    def _check_cancel(self) -> bool:
        if self._cancel_flag:
            self._state.phase = "idle"
            self._emit_cancelled()
            return True
        return False

    def _run_extraction(self, no_ocr: bool, start_time: float, duration: float, debug: bool):
        try:
            fps = self._video_info.fps
            cooldown_frames = int(self._config.min_screenshot_interval * fps)
            stability_frames = int(self._config.b_capture_delay * fps)
            seek_step = max(1, int(self._config.frame_check_interval * fps))
            scan_step = max(1, int(0.1 * fps))

            effective_ocr: OcrService
            if no_ocr:
                effective_ocr = OcrService()
            else:
                if self._ocr_service is None:
                    self.init_ocr()
                effective_ocr = self._ocr_service if (self._ocr_service and self._ocr_service.is_enabled()) else OcrService()

            deduplicator = Deduplicator(self._config, effective_ocr)
            ocr_available = effective_ocr.is_enabled()

            def get_roi(img):
                h, w = img.shape[:2]
                y_end = int(h * self._config.top_analysis_ratio)
                roi = img[0:y_end, :]
                small = cv2.resize(roi, (320, int(320 * (y_end / h))))
                return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            self._emit_log(f"Processing video: {self._video_info.path}")

            sandbox_path = self._file_service.create_sandbox()

            last_trigger_idx = -cooldown_frames
            last_stable_frame = None
            current_idx = 0

            if start_time >= 0:
                start_idx = int(start_time * fps)
                a_img, a_ts = self._video_service.read_frame_at(start_idx)
                if a_img is not None:
                    self._emit_log(f"Start-time capture at {a_ts:.1f}s...")
                    b_idx = start_idx + stability_frames
                    b_img, b_ts = self._video_service.read_frame_at(b_idx)
                    if b_img is None:
                        b_img, b_ts = a_img.copy(), a_ts
                        b_idx = start_idx

                    debug_path = str(sandbox_path / "bar_profile_page_000.txt") if self._debug_mode else None
                    merged_img, bar_x = self._video_service.merge_frames(
                        a_img, b_img, self._config.b_overlay_width_ratio,
                        self._config.default_crop_ratio, self._config.bar_min_diff_threshold, debug_path
                    )
                    self._emit_log(f"  Start-time capture, bar edge at x={bar_x}")
                    self._add_page(merged_img, a_ts, start_idx, sandbox_path)
                    last_trigger_idx = start_idx
                    last_stable_frame = Frame(b_img.copy(), b_ts, b_idx)
                    current_idx = b_idx
                else:
                    self._emit_log("Warning: Could not seek to start time, starting from beginning.")
                    dummy_img, dummy_ts = self._video_service.read_frame_at(0)
                    if dummy_img is None:
                        raise RuntimeError("Could not read video.")
                    current_idx = 0
                    last_stable_frame = Frame(dummy_img.copy(), dummy_ts, 0)
            else:
                dummy_img, dummy_ts = self._video_service.read_frame_at(0)
                if dummy_img is None:
                    raise RuntimeError("Could not read video.")
                current_idx = 0
                last_stable_frame = Frame(dummy_img.copy(), dummy_ts, 0)

            self._emit_log(f"Starting extraction from ~{current_idx / fps:.1f}s...")

            while True:
                if self._check_cancel():
                    return

                current_idx += seek_step
                frame_img, timestamp = self._video_service.read_frame_at(current_idx)
                if frame_img is None:
                    break

                current_frame = Frame(frame_img.copy(), timestamp, current_idx)

                if self._video_info.frame_count > 0:
                    percent = min(95.0, (current_idx / self._video_info.frame_count) * 100.0)
                else:
                    percent = 0.0
                self._state.current_timestamp = timestamp
                self._emit_progress("extracting", percent, f"Checking frame at {timestamp:.1f}s")

                if len(self._pages) > 0:
                    roi_std = np.std(get_roi(current_frame.image))
                    if roi_std < self._config.blank_content_std_threshold:
                        self._emit_log("  End of score detected (blank content).")
                        break

                if duration > 0 and timestamp >= duration:
                    self._emit_log(f"  Duration limit reached ({duration:.1f}s).")
                    break

                if (current_idx - last_trigger_idx) > cooldown_frames and last_stable_frame is not None:
                    score = ssim(get_roi(last_stable_frame.image), get_roi(current_frame.image))

                    if score < self._config.change_detection_threshold:
                        self._emit_log(f"  Change detected at ~{timestamp:.1f}s, scanning...")

                        scan_start = last_stable_frame.index + scan_step
                        a_frame = None

                        for scan_idx in range(scan_start, current_idx + 1, scan_step):
                            if self._check_cancel():
                                return
                            scan_img, scan_ts = self._video_service.read_frame_at(scan_idx)
                            if scan_img is None:
                                break
                            scan_score = ssim(get_roi(last_stable_frame.image), get_roi(scan_img))
                            if scan_score < self._config.change_detection_threshold:
                                a_frame = Frame(scan_img.copy(), scan_ts, scan_idx)
                                break

                        if a_frame is None:
                            a_frame = current_frame

                        delay_frames = int(self._config.a_capture_delay * fps)
                        if delay_frames > 0:
                            cap_idx = a_frame.index + delay_frames
                            cap_img, cap_ts = self._video_service.read_frame_at(cap_idx)
                            if cap_img is not None:
                                a_frame = Frame(cap_img.copy(), cap_ts, cap_idx)

                        b_idx = a_frame.index + stability_frames
                        b_img, b_ts = self._video_service.read_frame_at(b_idx)
                        if b_img is None:
                            b_img = a_frame.image.copy()
                            b_ts = a_frame.timestamp

                        b_frame = Frame(b_img.copy(), b_ts, b_idx)

                        if self._check_cancel():
                            return
                        debug_path = str(sandbox_path / f"bar_profile_page_{len(self._pages) + 1:03d}.txt") if self._debug_mode else None
                        merged_img, bar_x = self._video_service.merge_frames(
                            a_frame.image, b_frame.image, self._config.b_overlay_width_ratio,
                            self._config.default_crop_ratio, self._config.bar_min_diff_threshold, debug_path
                        )
                        self._emit_log(f"  Bar edge at x={bar_x} for page {len(self._pages) + 1}")

                        merged_number = None
                        if ocr_available:
                            merged_number = effective_ocr.get_leftmost_number(
                                merged_img, self._config.duplicate_top_ratio,
                                self._config.ocr_horizontal_ratio, self._config.ocr_confidence_threshold
                            )

                        is_dup = False
                        for existing in self._pages:
                            if deduplicator.is_duplicate(existing.image, merged_img, b_number=merged_number):
                                is_dup = True
                                break

                        if not is_dup:
                            self._add_page(merged_img, a_frame.timestamp, a_frame.index, sandbox_path)
                        else:
                            self._emit_log(f"  Duplicate page skipped at {a_frame.timestamp:.2f}s")

                        last_trigger_idx = a_frame.index

                last_stable_frame = current_frame

            # Tail scan for end-credits
            if not self._cancel_flag:
                try:
                    total_frames = self._video_info.frame_count
                    last_20s_frame = total_frames - int(20 * fps)
                    tail_start = max(last_20s_frame, current_idx)
                    tail_step = int(2.0 * fps)

                    if tail_start < total_frames and ocr_available:
                        self._emit_log("  Scanning final 20 seconds for end-credits...")
                        tail_idx = tail_start
                        while tail_idx < total_frames:
                            if self._check_cancel():
                                return
                            tail_img, tail_ts = self._video_service.read_frame_at(tail_idx)
                            if tail_img is None:
                                break
                            if effective_ocr.detect_keywords(tail_img, ["thank"]):
                                trim_time = tail_ts - 2.0
                                self._emit_log(f"  'Thank you' detected at {tail_ts:.1f}s, trimming.")
                                trimmed = [(p, c) for p, c in zip(self._pages, self._page_png_cache)
                                           if p.timestamp <= trim_time]
                                self._pages = [t[0] for t in trimmed]
                                self._page_png_cache = [t[1] for t in trimmed]
                                break
                            tail_idx += tail_step
                        else:
                            self._emit_log("  No 'Thank you' detected in final 20 seconds.")
                except Exception:
                    pass

            if not self._cancel_flag:
                # Rename sandbox to video filename
                try:
                    video_stem = Path(self._video_info.path).stem
                    self._file_service.rename_sandbox(video_stem)
                except Exception as e:
                    self._emit_log(f"  Could not rename sandbox: {e}")

                self._state.phase = "done"
                self._state.pages_detected = len(self._pages)
                self._emit_progress("extracting", 100.0, "Extraction complete")
                self._emit_completed(len(self._pages))
                self._emit_log(f"Extraction complete: {len(self._pages)} pages found")

        except Exception as e:
            self._state.phase = "error"
            self._emit_error(f"Extraction failed: {e}")
            self._emit_log(f"  [Error] {e}")

        finally:
            self._extraction_thread = None

    def _add_page(self, merged_img: np.ndarray, timestamp: float, index: int, sandbox_path: Path):
        page_num = len(self._pages) + 1
        png_bytes = self._encode_png(merged_img)

        frame = Frame(merged_img.copy(), timestamp, index)
        self._pages.append(frame)
        self._page_png_cache.append(png_bytes)

        m_path = sandbox_path / f"page_{page_num:03d}_merged.png"
        cv2.imwrite(str(m_path), merged_img)

        self._state.pages_detected = len(self._pages)
        self._emit_log(f"  New page detected at {timestamp:.2f}s (Index: {index})")
        if png_bytes is not None:
            self._emit_page_detected(len(self._pages) - 1, png_bytes)

    # ═════════════════════════════════════════════════════════════════════
    #  YouTube Download
    # ═════════════════════════════════════════════════════════════════════

    def download_youtube(self, url: str) -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        self._cancel_flag = False
        self._state = ExtractionState("downloading", 0, 0.0, 0.0)
        self._extraction_start_time = time.time()

        self._download_thread = threading.Thread(
            target=self._run_youtube_download,
            args=(url,),
            daemon=True,
        )
        self._download_thread.start()

    def _run_youtube_download(self, url: str):
        try:
            import yt_dlp

            dl_dir = self._file_service.base_dir / "yt_dl"
            dl_dir.mkdir(parents=True, exist_ok=True)
            output_template = str(dl_dir / "%(title)s.%(ext)s")

            finished_logged = False

            def progress_hook(d):
                nonlocal finished_logged
                if self._cancel_flag:
                    raise Exception("Download cancelled by user")
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                    pct = d.get('downloaded_bytes', 0) / total * 100
                    self._state.current_timestamp = pct
                    self._emit_progress("downloading", pct, f"Downloading... {pct:.0f}%")
                elif d['status'] == 'finished' and not finished_logged:
                    finished_logged = True
                    self._emit_log("  Download finished, processing...")

            ydl_opts = {
                'format': 'best[height<=1080]',
                'outtmpl': output_template,
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'playlistend': 1,
            }

            self._emit_log(f"Downloading: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get('title', 'video')
                # Find actual downloaded file
                candidates = list(dl_dir.glob(f"{video_title}.*"))
                candidates.extend(dl_dir.glob("*.mp4"))
                # yt-dlp sanitizes the title; find any new file in dl_dir
                if not candidates:
                    candidates = sorted(dl_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
                if not candidates:
                    raise RuntimeError("Could not find downloaded video file")
                video_path = str(candidates[0])

            self._emit_log(f"Downloaded to: {video_path}")

            if self._cancel_flag:
                raise Exception("Download cancelled by user")

            # Open the downloaded video for preview
            self.open_video(video_path)
            self._emit_download_completed(video_path)
            self._emit_log(f"Video ready: {video_path}")

        except Exception as e:
            self._state.phase = "error"
            self._emit_error(f"YouTube download failed: {e}")
            self._emit_log(f"  [Error] {e}")

        finally:
            self._download_thread = None
            self._state.phase = "idle"

    # ═════════════════════════════════════════════════════════════════════
    #  Page Management (16-21)
    # ═════════════════════════════════════════════════════════════════════

    def get_page_count(self) -> int:
        return len(self._pages)

    def get_page_thumbnail(self, index: int) -> Optional[bytes]:
        if index < 0 or index >= len(self._pages):
            return None
        img = self._pages[index].image
        h, w = img.shape[:2]
        thumb_w = 320
        thumb_h = int(h * (thumb_w / w))
        thumb = cv2.resize(img, (thumb_w, thumb_h))
        return self._encode_png(thumb)

    def get_page_full(self, index: int) -> Optional[bytes]:
        if index < 0 or index >= len(self._pages):
            return None
        if self._page_png_cache[index] is not None:
            return self._page_png_cache[index]
        png = self._encode_png(self._pages[index].image)
        self._page_png_cache[index] = png
        return png

    def remove_page(self, index: int) -> None:
        if index < 0 or index >= len(self._pages):
            raise IndexError(f"Page index {index} out of range (0-{len(self._pages) - 1})")
        self._pages.pop(index)
        self._page_png_cache.pop(index)

    def reorder_pages(self, new_order: list[int]) -> None:
        if len(new_order) != len(self._pages):
            raise ValueError(f"New order length {len(new_order)} must match page count {len(self._pages)}")
        if set(new_order) != set(range(len(self._pages))):
            raise ValueError("New order must be a permutation of 0..N-1")
        self._pages = [self._pages[i] for i in new_order]
        self._page_png_cache = [self._page_png_cache[i] for i in new_order]

    def clear_pages(self) -> None:
        self._pages.clear()
        self._page_png_cache.clear()

    # ═════════════════════════════════════════════════════════════════════
    #  PDF Generation (22-23)
    # ═════════════════════════════════════════════════════════════════════

    def generate_pdf(self, output_path: str, title: Optional[str] = None) -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        if not self._pages:
            raise RuntimeError("No pages to generate PDF")

        self._state = ExtractionState("generating_pdf", len(self._pages), 0.0, 0.0)
        self._extraction_start_time = time.time()

        self._pdf_thread = threading.Thread(
            target=self._run_generate_pdf,
            args=(output_path, title),
            daemon=True,
        )
        self._pdf_thread.start()

    def _run_generate_pdf(self, output_path: str, title: Optional[str] = None):
        try:
            try:
                sandbox_path = self._file_service.get_sandbox_path()
            except RuntimeError:
                sandbox_path = self._file_service.create_sandbox()

            draft_pdf_name = "draft_output.pdf"
            final_title = title if title else Path(output_path).stem
            images = [f.image for f in self._pages]

            self._emit_log(f"Generating PDF with {len(images)} pages...")
            self._emit_progress("generating_pdf", 0.0, "Starting PDF generation...")

            old_cwd = os.getcwd()
            os.chdir(sandbox_path)
            try:
                self._pdf_service.create_pdf(images, Path(draft_pdf_name), self._config, title_hint=final_title)
            finally:
                os.chdir(old_cwd)

            self._emit_progress("generating_pdf", 90.0, "Finalizing PDF...")
            self._emit_log(f"Finalizing PDF: {output_path}")
            self._file_service.move_to_final(draft_pdf_name, Path(output_path))

            self._emit_progress("generating_pdf", 100.0, "PDF generated successfully")
            self._emit_completed(len(self._pages))
            self._emit_log(f"PDF generated: {output_path}")

        except Exception as e:
            self._emit_error(f"PDF generation failed: {e}")
            self._emit_log(f"  [Error] {e}")

        finally:
            self._state.phase = "idle"
            self._pdf_thread = None

    def regenerate_from_dir(self, sandbox_dir: str, output_path: Optional[str] = None) -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        sb_path = Path(sandbox_dir)
        if not sb_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {sandbox_dir}")

        files = sorted(
            sb_path.glob("page_*_merged.png"),
            key=lambda f: int(f.stem.split("_")[1])
        )
        if not files:
            raise RuntimeError(f"No page images found in {sandbox_dir}")

        images = []
        for f in files:
            file_bytes = np.fromfile(str(f), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                images.append(img)

        if not images:
            raise RuntimeError("Could not decode any page images")

        self._pages.clear()
        self._page_png_cache.clear()
        for i, img in enumerate(images):
            frame = Frame(img, 0.0, i)
            self._pages.append(frame)
            self._page_png_cache.append(self._encode_png(img))

        if output_path is None:
            output_path = sb_path.stem + ".pdf"

        self._emit_log(f"Loaded {len(images)} pages from {sandbox_dir}")
        self._file_service.sandbox_path = sb_path
        self.generate_pdf(output_path)

    # ═════════════════════════════════════════════════════════════════════
    #  Sandbox Management (24-26)
    # ═════════════════════════════════════════════════════════════════════

    def list_sandboxes(self) -> list[SandboxInfo]:
        results = []
        base_dir = self._file_service.base_dir
        if not base_dir.exists():
            return results

        for d in base_dir.iterdir():
            if d.is_dir() and d.name.startswith("tmp_"):
                page_files = sorted(d.glob("page_*_merged.png"))
                page_count = len(page_files)
                created = datetime.fromtimestamp(d.stat().st_ctime)

                video_name = d.name
                log_file = d / "extraction.log"
                if log_file.exists():
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            first_line = f.readline().strip()
                        if first_line.startswith("Processing video:"):
                            video_name = Path(first_line.split("Processing video:")[1].strip()).stem
                    except Exception:
                        pass

                results.append(SandboxInfo(
                    path=str(d),
                    page_count=page_count,
                    created=created,
                    video_name=video_name,
                ))

        results.sort(key=lambda x: x.created, reverse=True)
        return results

    def load_sandbox(self, path: str) -> int:
        sb_path = Path(path)
        if not sb_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {path}")

        files = sorted(
            sb_path.glob("page_*_merged.png"),
            key=lambda f: int(f.stem.split("_")[1])
        )

        self._pages.clear()
        self._page_png_cache.clear()

        for f in files:
            file_bytes = np.fromfile(str(f), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                frame = Frame(img, 0.0, len(self._pages))
                self._pages.append(frame)
                self._page_png_cache.append(self._encode_png(img))

        self._file_service.sandbox_path = sb_path
        self._emit_log(f"Loaded {len(self._pages)} pages from {path}")
        return len(self._pages)

    def delete_sandbox(self, path: str) -> None:
        import shutil
        sb_path = Path(path)
        if not sb_path.exists():
            return
        shutil.rmtree(sb_path)
        self._emit_log(f"Deleted sandbox: {path}")

    # ═════════════════════════════════════════════════════════════════════
    #  Lifecycle (27-28)
    # ═════════════════════════════════════════════════════════════════════

    def set_debug_mode(self, enabled: bool) -> None:
        self._debug_mode = enabled

    def is_debug_mode(self) -> bool:
        return self._debug_mode

    def open_sandbox_folder(self) -> None:
        if not self._debug_mode:
            return
        try:
            path = self._file_service.get_sandbox_path()
            os.startfile(str(path.resolve()))
        except Exception as e:
            msg = f"Could not open sandbox folder: {e}"
            if self._on_log:
                self._on_log(f"  {msg}")

    def cleanup(self) -> None:
        self.close_video()
        self._file_service.cleanup()
        self._pages.clear()
        self._page_png_cache.clear()

    def is_busy(self) -> bool:
        if self._download_thread is not None and self._download_thread.is_alive():
            return True
        if self._extraction_thread is not None and self._extraction_thread.is_alive():
            return True
        if self._pdf_thread is not None and self._pdf_thread.is_alive():
            return True
        return False
