import time
import numpy as np
from pathlib import Path
from typing import Callable, List, Optional, TextIO

from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame, PageManifestEntry
from src.domain.interfaces import IVideoService, IOcrService, IPdfService, IFileService
from src.domain.deduplication import Deduplicator
from src.application.extraction_components import FrameStepper, PageCommitter, BarProfilePlotter


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

    def execute(
        self,
        video_path: str,
        output_dir: Path,
        no_ocr: bool = False,
        start_time: float = -1.0,
        debug: bool = False,
        end_offset: float = 0.0,
        on_log: Callable[[str], None] = print,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_page_detected: Optional[Callable[[int, np.ndarray], None]] = None,
        is_cancelled: Callable[[], bool] = lambda: False,
        original_video_path: Optional[str] = None,
    ) -> tuple[List[Frame], List[PageManifestEntry]]:
        self.video_service.open_video(video_path)
        orig_w, orig_h = self.video_service.get_original_size()

        # Resolve effective OCR
        effective_ocr: IOcrService
        if no_ocr:
            from src.domain.interfaces import _NoopOcrService
            effective_ocr = _NoopOcrService()
        else:
            if not self.ocr_service.initialize():
                on_log("[WARN] OCR initialization failed, continuing without OCR.")
                from src.domain.interfaces import _NoopOcrService
                effective_ocr = _NoopOcrService()
            else:
                effective_ocr = self.ocr_service

        deduplicator = Deduplicator(self.config, effective_ocr)
        ocr_available = effective_ocr.is_enabled()

        # Write extraction log to diagnostics/ subfolder (always on)
        log_file: Optional[TextIO] = None
        try:
            log_path = output_dir / "diagnostics" / "extraction.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(log_path, "w", encoding="utf-8")
        except Exception:
            pass

        def log(msg: str):
            on_log(msg)
            if log_file:
                log_file.write(msg + "\n")
                log_file.flush()

        # Build sub-components
        plotter = BarProfilePlotter()
        committer = PageCommitter(
            self.video_service, self.file_service, effective_ocr,
            self.config, deduplicator, orig_w, orig_h,
            original_video_path=original_video_path,
        )
        stepper = FrameStepper(
            self.video_service, self.config,
            on_log=log, on_progress=on_progress, is_cancelled=is_cancelled,
        )

        unique_pages: List[Frame] = []
        manifest_entries: List[PageManifestEntry] = []
        stepper.set_unique_pages_ref(unique_pages)

        log(f"Processing video: {video_path}")

        # Get video duration for end_offset calculation
        video_duration = self.video_service.get_total_frames() / self.video_service.get_fps() if self.video_service.get_fps() > 0 else 0.0

        # Initialize: handle start-time capture
        attempt_num = 0
        start_pair = stepper.initialize(start_time)
        if start_pair is not None:
            a_frame, b_frame = start_pair
            attempt_num += 1
            log(f"Start-time capture at {a_frame.timestamp:.1f}s...")
            entry = committer.commit(
                a_frame, b_frame, unique_pages, output_dir, attempt_num,
                debug, log, on_page_detected, is_first=True, plotter=plotter,
            )
            if entry is not None:
                manifest_entries.append(entry)

        log(f"Starting extraction from ~{stepper.current_idx / stepper.fps:.1f}s...")

        # Main loop
        while True:
            result = stepper.step()
            if result is None:
                break
            current_frame, ssim_score = result

            if stepper.check_end_offset(current_frame.timestamp, end_offset, video_duration):
                break

            if stepper.should_trigger(ssim_score):
                log(f"  Change detected at ~{current_frame.timestamp:.1f}s, scanning for precise trigger...")
                a_frame, b_frame = stepper.capture_a_b(current_frame)
                attempt_num += 1
                entry = committer.commit(
                    a_frame, b_frame, unique_pages, output_dir, attempt_num,
                    debug, log, on_page_detected, is_first=False, plotter=plotter,
                    ssim_score=ssim_score,
                )
                if entry is not None:
                    manifest_entries.append(entry)

        # Tail scan for end-credits
        stepper.tail_scan(effective_ocr, unique_pages, stepper.current_idx, end_offset, debug, log_file)

        # Release original video capture if opened
        committer.release()

        if log_file:
            log_file.close()

        return unique_pages, manifest_entries


class GeneratePdfUseCase:
    def __init__(self, pdf_service: IPdfService, config: ScoreConfig,
                 on_log: Callable[[str], None] = print):
        self.pdf_service = pdf_service
        self.config = config
        self._log = on_log

    def execute(self, frames: List[Frame], output_path: str):
        if not frames:
            self._log("[WARN] No pages detected. PDF not generated.")
            return

        images = [f.image for f in frames]
        final_title = Path(output_path).stem
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        self._log(f"Generating PDF with {len(frames)} pages...")
        self.pdf_service.create_pdf(images, output, self.config, title_hint=final_title)
        self._log(f"PDF generated: {output_path}")
