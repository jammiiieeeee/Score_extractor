import threading
import time
import json
import os
import sys
import cv2
import numpy as np
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Callable, List

from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from src.infrastructure.video_service import VideoService
from src.infrastructure.ocr_service import OcrService
from src.infrastructure.pdf_service import PdfService
from src.infrastructure.file_service import FileService
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
        self._original_pages: List[Frame] = []
        self._original_png_cache: List[Optional[bytes]] = []
        self._loaded_score_path: Optional[str] = None
        self._loaded_score_metadata: dict = {}

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
            "bar_left_margin",
        }
        valid_float_any = {
            "frame_check_interval", "min_screenshot_interval",
            "a_capture_delay", "b_capture_delay",
            "blank_content_std_threshold", "bar_min_diff_threshold",
        }
        valid_int_0_100 = {"ocr_confidence_threshold"}
        valid_int_any = {"bar_padding_px"}

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

        old_stdout = sys.stdout

        gui_self = self

        class CapturePrint:
            def write(self, text):
                text = text.strip()
                if text:
                    gui_self._emit_log(text)
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
                         start_time: float = 2.0, duration: float = 0.0,
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
        self._page_png_cache.clear()
        self._state = ExtractionState("extracting", 0, 0.0, 0.0)
        self._extraction_start_time = time.time()

        self._extraction_thread = threading.Thread(
            target=self._run_extraction,
            args=(no_ocr, start_time, duration, self._debug_mode, output_folder, score_name),
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

    def _run_extraction(self, no_ocr: bool, start_time: float, duration: float,
                        debug: bool, output_folder: str, score_name: str):
        try:
            score_dir = self._file_service.prepare_output_dir(output_folder, score_name)

            effective_ocr: OcrService
            if no_ocr:
                effective_ocr = OcrService()
            else:
                if self._ocr_service is None:
                    self.init_ocr()
                effective_ocr = self._ocr_service if (self._ocr_service and self._ocr_service.is_enabled()) else OcrService()

            use_case = ExtractScoreUseCase(self._video_service, effective_ocr,
                                           self._file_service, self._config)

            pages = use_case.execute(
                self._video_info.path,
                output_dir=score_dir,
                no_ocr=no_ocr,
                start_time=start_time,
                debug=debug,
                duration=duration,
                on_log=self._emit_log,
                on_progress=lambda pct, d: self._emit_progress("extracting", pct, d),
                is_cancelled=lambda: self._cancel_flag,
            )

            self._pages = pages
            self._page_png_cache = [self._encode_png(p.image) for p in pages]

            if not self._cancel_flag:
                self._state.phase = "done"
                self._state.pages_detected = len(self._pages)
                self._emit_progress("extracting", 100.0, "Extraction complete")
                self._emit_completed(len(self._pages))
                self._emit_log(f"Extraction complete: {len(self._pages)} pages found")
            else:
                self._pages.clear()
                self._page_png_cache.clear()
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

    def download_youtube(self, url: str, fmt: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]") -> None:
        if self.is_busy():
            raise RuntimeError("Extraction or PDF generation already in progress")

        self._cancel_flag = False
        self._state = ExtractionState("downloading", 0, 0.0, 0.0)
        self._extraction_start_time = time.time()

        self._download_thread = threading.Thread(
            target=self._run_youtube_download,
            args=(url, fmt),
            daemon=True,
        )
        self._download_thread.start()

    def _run_youtube_download(self, url: str, fmt: str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"):
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

            ffmpeg_path = r"C:\Users\hosze\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
            ydl_opts = {
                'format': fmt,
                'outtmpl': output_template,
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'playlistend': 1,
                'ffmpeg_location': ffmpeg_path,
                'merge_output_format': 'mp4',
            }

            self._emit_log(f"Downloading: {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get('title', 'video')
                candidates = list(dl_dir.glob(f"{video_title}.*"))
                candidates.extend(dl_dir.glob("*.mp4"))
                if not candidates:
                    candidates = sorted(dl_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
                if not candidates:
                    raise RuntimeError("Could not find downloaded video file")
                video_path = str(candidates[0])

            self._emit_log(f"Downloaded to: {video_path}")

            if self._cancel_flag:
                raise Exception("Download cancelled by user")

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
        self._original_pages.clear()
        self._original_png_cache.clear()
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
            images = [f.image for f in self._pages]
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

        self._pages.clear()
        self._page_png_cache.clear()
        for i, img in enumerate(images):
            frame = Frame(img, 0.0, i)
            self._pages.append(frame)
            self._page_png_cache.append(self._encode_png(img))

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
        self._pages.clear()
        self._page_png_cache.clear()
        self._original_pages.clear()
        self._original_png_cache.clear()
        for i, img in enumerate(images):
            frame = Frame(img, 0.0, i)
            self._pages.append(frame)
            self._page_png_cache.append(self._encode_png(img))
            self._original_pages.append(Frame(img.copy(), 0.0, i))
            self._original_png_cache.append(self._encode_png(img))
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
        if not self._original_pages:
            return
        self._pages.clear()
        self._page_png_cache.clear()
        for i, frame in enumerate(self._original_pages):
            h = frame.image.shape[0]
            crop_px = int(h * ratio)
            cropped = frame.image[crop_px:, :].copy()
            self._pages.append(Frame(cropped, frame.timestamp, frame.index))
            self._page_png_cache.append(self._encode_png(cropped))

    def has_loaded_score(self) -> bool:
        return len(self._original_pages) > 0 and self._loaded_score_path is not None

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
        self._page_png_cache.clear()

    def is_busy(self) -> bool:
        if self._download_thread is not None and self._download_thread.is_alive():
            return True
        if self._extraction_thread is not None and self._extraction_thread.is_alive():
            return True
        if self._pdf_thread is not None and self._pdf_thread.is_alive():
            return True
        return False
