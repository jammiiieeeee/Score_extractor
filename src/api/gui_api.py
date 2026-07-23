import threading
import time
import json
import os
import sys
import contextlib
import io
import cv2
import numpy as np
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Callable, List

from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from src.domain.page_store import PageStore
from src.infrastructure.video_service import VideoService
from src.infrastructure.ocr_service import OcrService
from src.infrastructure.pdf_service import PdfService
from src.infrastructure.file_service import FileService
from src.infrastructure.download_service import DownloadService
from src.application.use_cases import ExtractScoreUseCase


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
class ScoreInfo:
    path: str
    page_count: int
    score_name: str


class GuiApi:
    """Thin orchestrator that delegates to focused sub-modules.

    Responsibilities:
    - Config management (load/save/validate)
    - Video lifecycle (open/close/preview)
    - OCR lifecycle (init/status/preview)
    - Extraction orchestration (threaded)
    - PDF generation (threaded)
    - YouTube download (threaded)
    - Callback registry
    - Score management (load/save/delete)
    """

    def __init__(self, config_path: str = "config.json"):
        self._config_path = config_path
        self._config = self._load_config(config_path)

        self._file_service = FileService()
        self._video_service: Optional[VideoService] = None
        self._ocr_service: Optional[OcrService] = None
        self._pdf_service = PdfService()
        self._pages = PageStore()
        self._download_service = DownloadService(self._file_service.base_dir)

        self._video_info: Optional[VideoInfo] = None
        self._original_video_path: Optional[str] = None
        self._loaded_score_path: Optional[str] = None
        self._loaded_score_metadata: dict = {}

        self._extraction_thread: Optional[threading.Thread] = None
        self._pdf_thread: Optional[threading.Thread] = None
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_flag = False
        self._debug_mode = False
        self._last_download_title: Optional[str] = None
        self._prev_download_title: Optional[str] = None
        self._state = ExtractionState("idle", 0, 0.0, 0.0)
        self._extraction_start_time = 0.0

        self._on_progress: Optional[Callable] = None
        self._on_page_detected: Optional[Callable] = None
        self._on_log: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._on_completed: Optional[Callable] = None
        self._on_cancelled: Optional[Callable] = None
        self._on_download_completed: Optional[Callable] = None
        self._ocr_init_lock = threading.Lock()

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
        return PageStore.encode_png(img)

    @staticmethod
    def _decode_png(data: bytes) -> Optional[np.ndarray]:
        return PageStore.decode_png(data)

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
            "bar_left_margin",
        }
        valid_float_any = {
            "frame_check_interval", "min_screenshot_interval",
            "a_capture_delay", "b_capture_delay",
            "blank_content_std_threshold", "bar_min_diff_threshold",
        }
        valid_int_0_100 = {"ocr_confidence_threshold"}
        valid_int_any = {"bar_padding_px", "yt_quality_index"}

        valid_keys = valid_float_0_1 | valid_float_any | valid_int_0_100 | valid_int_any

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
            elif key in valid_int_0_100:
                val = int(value)
                if not (0 <= val <= 100):
                    raise ValueError(f"{key} must be between 0 and 100")
                setattr(self._config, key, val)
            elif key in valid_int_any:
                setattr(self._config, key, int(value))

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

    def read_frame_at(self, timestamp: float) -> Optional[np.ndarray]:
        if self._video_service is None or self._video_info is None:
            return None
        frame_idx = int(timestamp * self._video_info.fps)
        img, _ = self._video_service.read_frame_at(frame_idx)
        return img

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

        with self._ocr_init_lock:
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                result = self._ocr_service.initialize()

            for line in capture.getvalue().splitlines():
                line = line.strip()
                if line:
                    self._emit_log(line)

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
                         start_time: float = 2.0, end_offset: float = 0.0,
                         output_folder: str = "", score_name: str = "") -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        if video_path is not None:
            self.open_video(video_path)

        if self._video_service is None or self._video_info is None:
            raise RuntimeError("No video opened. Call open_video() or provide video_path.")

        if not output_folder or not score_name:
            raise RuntimeError("output_folder and score_name are required")

        self._cancel_flag = False
        self._pages.clear()
        self._state = ExtractionState("extracting", 0, 0.0, 0.0)
        self._extraction_start_time = time.time()

        self._extraction_thread = threading.Thread(
            target=self._run_extraction,
            args=(no_ocr, start_time, end_offset, self._debug_mode, output_folder, score_name, self._original_video_path),
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

    def _run_extraction(self, no_ocr: bool, start_time: float, end_offset: float,
                        debug: bool, output_folder: str, score_name: str,
                        original_video_path: Optional[str] = None):
        try:
            score_dir = self._file_service.prepare_output_dir(output_folder, score_name)

            effective_ocr: OcrService
            if no_ocr:
                effective_ocr = OcrService()
            else:
                if self._ocr_service is None:
                    self.init_ocr()
                effective_ocr = self._ocr_service if (self._ocr_service and self._ocr_service.is_enabled()) else OcrService()

            # Always use the low-res scan video for extraction (SSIM, bar detection, A/B merge)
            # The original_video_path is only used by PageCommitter for OCR/debug full-res reads
            extraction_video_path = self._video_info.path

            use_case = ExtractScoreUseCase(self._video_service, effective_ocr,
                                           self._file_service, self._config)

            pages = use_case.execute(
                extraction_video_path,
                output_dir=score_dir,
                no_ocr=no_ocr,
                start_time=start_time,
                debug=debug,
                end_offset=end_offset,
                on_log=self._emit_log,
                on_progress=lambda pct, d: self._emit_progress("extracting", pct, d),
                is_cancelled=lambda: self._cancel_flag,
                original_video_path=original_video_path,
            )

            self._pages.set_pages(pages)

            if not self._cancel_flag:
                self._state.phase = "done"
                self._state.pages_detected = len(self._pages)
                self._emit_progress("extracting", 100.0, "Extraction complete")
                self._emit_completed(len(self._pages))
                self._emit_log(f"Extraction complete: {len(self._pages)} pages found")
            else:
                self._pages.clear()
                self._state.phase = "idle"
                import shutil
                shutil.rmtree(score_dir, ignore_errors=True)
                self._emit_cancelled()

        except Exception as e:
            self._state.phase = "error"
            self._emit_error(f"Extraction failed: {e}")
            self._emit_log(f"  [Error] {e}")

        finally:
            self._extraction_thread = None

    # ═════════════════════════════════════════════════════════════════════
    #  YouTube Download
    # ═════════════════════════════════════════════════════════════════════

    def download_youtube(self, url: str, fmt: str = "bestvideo[height<=1080][fps<=30]",
                         scan_fmt: str = "best[height<=640]") -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        self._cancel_flag = False
        self._state = ExtractionState("downloading", 0, 0.0, 0.0)
        self._extraction_start_time = time.time()

        self._download_thread = threading.Thread(
            target=self._run_youtube_download,
            args=(url, fmt, scan_fmt),
            daemon=True,
        )
        self._download_thread.start()

    def _run_youtube_download(self, url: str, fmt: str = "bestvideo[height<=1080][fps<=30]",
                              scan_fmt: str = "best[height<=640]"):
        try:
            def on_progress(pct, detail):
                self._state.current_timestamp = pct
                self._emit_progress("downloading", pct, detail)

            result = self._download_service.download(
                url, fmt, scan_fmt=scan_fmt,
                on_progress=on_progress,
                on_log=self._emit_log,
                is_cancelled=lambda: self._cancel_flag,
            )

            self._prev_download_title = self._last_download_title
            self._last_download_title = result.video_title

            if self._cancel_flag:
                raise Exception("Download cancelled by user")

            original_path = result.video_path

            if scan_fmt and result.scan_path != result.video_path:
                self._original_video_path = original_path
                self.open_video(result.scan_path)
            else:
                self._original_video_path = None
                self.open_video(result.video_path)

            self._emit_download_completed(result.video_path)
            self._emit_log(f"Video ready: {result.video_path}")

        except Exception as e:
            self._state.phase = "error"
            self._emit_error(f"YouTube download failed: {e}")
            self._emit_log(f"  [Error] {e}")

        finally:
            self._download_thread = None
            self._state.phase = "idle"

    # ═════════════════════════════════════════════════════════════════════
    #  Page Management (16-21) — delegates to PageStore
    # ═════════════════════════════════════════════════════════════════════

    def get_page_count(self) -> int:
        return len(self._pages)

    def get_page_thumbnail(self, index: int) -> Optional[bytes]:
        return self._pages.get_thumbnail(index)

    def get_page_full(self, index: int) -> Optional[bytes]:
        return self._pages.get_full_png(index)

    def remove_page(self, index: int) -> None:
        self._pages.remove(index)

    def reorder_pages(self, new_order: list[int]) -> None:
        self._pages.reorder(new_order)

    def clear_pages(self) -> None:
        self._pages.clear()
        self._loaded_score_path = None
        self._loaded_score_metadata = {}

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
            images = self._pages.all_images()
            final_title = title if title else Path(output_path).stem
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            self._emit_log(f"Generating PDF with {len(images)} pages...")
            self._emit_progress("generating_pdf", 0.0, "Starting PDF generation...")

            self._pdf_service.create_pdf(images, output, self._config, title_hint=final_title)

            self._emit_progress("generating_pdf", 100.0, "PDF generated successfully")
            self._emit_completed(len(self._pages))
            self._emit_log(f"PDF generated: {output_path}")

            score_dir = output.parent
            self.save_metadata(str(score_dir), {
                "score_name": final_title,
                "crop_ratio": self._config.default_crop_ratio,
                "page_count": len(self._pages),
                "extraction_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })

        except Exception as e:
            self._emit_error(f"PDF generation failed: {e}")
            self._emit_log(f"  [Error] {e}")

        finally:
            self._state.phase = "idle"
            self._pdf_thread = None

    def regenerate_from_dir(self, score_dir: str, output_path: Optional[str] = None) -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        sb_path = Path(score_dir)
        images = self._file_service.load_page_images(sb_path)
        if not images:
            raise RuntimeError(f"No page images found in {score_dir}/photos/")

        from src.domain.models import Frame
        self._pages.clear()
        for i, img in enumerate(images):
            self._pages.add(Frame(img, 0.0, i))

        if output_path is None:
            output_path = str(sb_path / f"{sb_path.name}.pdf")

        self._emit_log(f"Loaded {len(images)} pages from {score_dir}")
        self.generate_pdf(output_path)

    # ═════════════════════════════════════════════════════════════════════
    #  Score Management
    # ═════════════════════════════════════════════════════════════════════

    def list_saved_scores(self, output_folder: str) -> list[ScoreInfo]:
        results = self._file_service.list_saved_scores(output_folder)
        return [ScoreInfo(**r) for r in results]

    def load_saved_score(self, path: str) -> int:
        score_dir = Path(path)
        images = self._file_service.load_page_images(score_dir)

        from src.domain.models import Frame
        self._pages.clear()
        working = []
        originals = []
        for i, img in enumerate(images):
            frame = Frame(img, 0.0, i)
            working.append(frame)
            originals.append(Frame(img.copy(), 0.0, i))
        self._pages.set_pages(working)
        self._pages.set_originals(originals)

        self._loaded_score_path = path
        self._loaded_score_metadata = self._read_metadata(score_dir)
        meta_crop = self._loaded_score_metadata.get("crop_ratio", 0.35)
        self._config.default_crop_ratio = meta_crop
        self._emit_log(f"Loaded {len(self._pages)} pages from {path}")
        return len(self._pages)

    def delete_saved_score(self, path: str) -> None:
        import shutil
        score_path = Path(path)
        if not score_path.exists():
            return
        shutil.rmtree(score_path)
        self._emit_log(f"Deleted score: {path}")

    # ═════════════════════════════════════════════════════════════════════
    #  Re-extraction helpers
    # ═════════════════════════════════════════════════════════════════════

    def reapply_crop(self, ratio: float) -> None:
        self._pages.reapply_crop(ratio)

    def has_loaded_score(self) -> bool:
        return self._pages.has_originals() and self._loaded_score_path is not None

    def get_loaded_score_path(self) -> Optional[str]:
        return self._loaded_score_path

    def get_loaded_score_metadata(self) -> dict:
        return dict(self._loaded_score_metadata)

    def is_loading_from_scratch(self) -> bool:
        return not self.has_loaded_score()

    def get_first_page_image(self) -> Optional[np.ndarray]:
        if self._pages:
            return self._pages[0].image
        return None

    def _read_metadata(self, score_dir) -> dict:
        score_dir = Path(score_dir)
        meta_path = score_dir / "metadata.json"
        if meta_path.exists():
            try:
                with open(str(meta_path), 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @staticmethod
    def save_metadata(score_dir: str, data: dict) -> None:
        meta_path = Path(score_dir) / "metadata.json"
        try:
            with open(str(meta_path), 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def has_video(self) -> bool:
        return self._video_service is not None and self._video_info is not None

    # ═════════════════════════════════════════════════════════════════════
    #  Lifecycle
    # ═════════════════════════════════════════════════════════════════════

    def set_debug_mode(self, enabled: bool) -> None:
        self._debug_mode = enabled

    def is_debug_mode(self) -> bool:
        return self._debug_mode

    def open_debug_folder(self, score_dir: str) -> None:
        if not self._debug_mode:
            return
        debug_path = Path(score_dir) / "debug"
        if debug_path.exists():
            os.startfile(str(debug_path.resolve()))

    def cleanup(self) -> None:
        self.close_video()
        self._pages.clear()

    def is_busy(self) -> bool:
        if self._download_thread is not None and self._download_thread.is_alive():
            return True
        if self._extraction_thread is not None and self._extraction_thread.is_alive():
            return True
        if self._pdf_thread is not None and self._pdf_thread.is_alive():
            return True
        return False
