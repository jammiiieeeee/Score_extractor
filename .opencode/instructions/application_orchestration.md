# Application Orchestration Specification

This document defines the orchestration layer: data flow, component responsibilities, and the extraction pipeline.

## Entry Points

| File | Role |
|------|------|
| `main.py` | CLI — argparse, synchronous extraction, direct PDF generation |
| `app_gui.py` | PyQt6 GUI — two tabs, callback-driven, threaded operations |
| `src/api/gui_api.py` | 44-method Python API — thin orchestrator delegating to sub-modules |

Both `main.py` and `app_gui.py` share `ExtractScoreUseCase` — neither wraps the other.

## Component Map

### `ExtractScoreUseCase` (`src/application/use_cases.py`)

Orchestrates the full extraction pipeline. Constructor takes:
- `video_service: IVideoService`
- `ocr_service: IOcrService`
- `file_service: IFileService`
- `config: ScoreConfig`

`execute()` parameters:
- `video_path: str`
- `output_dir: Path`
- `no_ocr: bool = False`
- `start_time: float = -1.0`
- `debug: bool = False`
- `duration: float = 0.0`
- `on_log`, `on_progress`, `on_page_detected`, `is_cancelled` — callbacks
- `original_video_path: Optional[str]` — for YouTube dual-download workflow

Returns `List[Frame]`.

### `FrameStepper` (`src/application/extraction_components.py`)

Extraction loop state machine. Responsibilities:
- Read frames sequentially with configurable skip (`frame_check_interval`)
- Compute SSIM on top ROI (`top_analysis_ratio`) to detect page changes
- Apply A/B capture delays (`a_capture_delay`, `b_capture_delay`)
- Detect blank content (end of score) via `blank_content_std_threshold`
- Duration limit enforcement
- Tail scan for "Thank you" end-credits in final 20 seconds

Key methods:
- `initialize(start_time)` → optional start pair
- `step()` → `(Frame, ssim_score)` or `None`
- `should_trigger(ssim_score)` → `bool`
- `capture_a_b(trigger_frame)` → `(Frame, Frame)`
- `tail_scan(ocr, unique_pages, ...)` → mutates `unique_pages` in place

### `PageCommitter` (`src/application/extraction_components.py`)

Handles the commit pipeline for each detected page pair:
1. Dynamic Bar Erase (merge A+B frames via `video_service.merge_frames()`)
2. Upscale merged to original resolution
3. Bar profile validation (peak count + left spike margin)
4. OCR number extraction from merged full-res frames
5. Deduplication (OCR → Global → Row)
6. Save to disk via `file_service.save_page_image()`
7. Debug artifact writing (A/B frames, bar profile text)

### `BarProfilePlotter` (`src/application/extraction_components.py`)

Optional matplotlib diagnostic plots. Lazy-imports matplotlib. Only instantiated when `debug=True`.

### `Deduplicator` (`src/domain/deduplication.py`)

Three-stage dedup pipeline:
1. OCR force-duplicate (short-circuit on matching numbers)
2. Global pixel similarity (256×256 grayscale, `TM_CCOEFF_NORMED`)
3. Row-wise similarity (Pearson correlation, coverage check)

Also provides bar profile validation: `check_bar_profile()` → `(has_clean, has_left_spike, peaks)`.

### `PageStore` (`src/domain/page_store.py`)

In-memory page storage. Handles:
- Working pages + original pages (for re-cropping)
- `reapply_crop(ratio)` — crops from originals on each call
- `set_originals()` / `has_originals()` — for loaded-score mode
- Thumbnail generation (320px wide PNG)
- Full-resolution PNG encoding

## Data Flow: Extraction

```
main.py / gui_api.py
  └─ ExtractScoreUseCase.execute()
       ├─ FrameStepper.initialize(start_time)  →  optional first pair
       ├─ Loop: FrameStepper.step()
       │    ├─ SSIM detection on top ROI
       │    └─ FrameStepper.capture_a_b()  →  (A, B)
       ├─ PageCommitter.commit()
       │    ├─ video_service.merge_frames(A, B)  →  merged + bar info
       │    ├─ Bar profile validation (2-4 peaks, left spike)
       │    ├─ OCR number extraction
       │    ├─ Deduplicator.is_duplicate(existing, merged)
       │    └─ file_service.save_page_image()
       ├─ FrameStepper.tail_scan()  →  trim end-credits
       └─ return unique_pages: List[Frame]
```

## Data Flow: GUI Re-extraction

```
app_gui.py (user adjusts crop slider)
  └─ GuiApi.reapply_crop(ratio)
       └─ PageStore.reapply_crop(ratio)
            └─ crops from _original_pages, updates _pages

app_gui.py (user clicks "Regenerate PDF")
  └─ GuiApi.generate_pdf(output_path)
       └─ PdfService.create_pdf(pages.all_images(), ...)
```

## Data Flow: YouTube Download

```
app_gui.py
  └─ GuiApi.download_youtube(url, fmt, scan_fmt)
       └─ DownloadService.download()  →  dual-download:
            ├─ High-res video for PDF (original_path)
            └─ Low-res scan for extraction (scan_path)
       ├─ open_video(scan_path)  →  extraction uses low-res
       └─ _original_video_path = high-res path  →  PageCommitter reads full-res frames
```

## Error Handling

- OCR failure: auto-fallback to `_NoopOcrService` (no user prompt)
- Video seek failure: skip frame, continue loop
- Extraction thread exceptions: caught, emitted via `on_error` callback
- PDF generation exceptions: caught, emitted via `on_error` callback