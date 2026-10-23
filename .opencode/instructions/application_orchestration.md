# Application Orchestration Specification

This document defines the orchestration layer: data flow, component responsibilities, and the extraction pipeline.

## Entry Points

| File | Role |
|------|------|
| `main.py` | CLI — argparse, synchronous extraction, direct PDF generation |
| `app_gui.py` | PyQt6 GUI — two tabs, callback-driven, threaded operations |
| `src/api/gui_api.py` | 43-method Python API — thin orchestrator delegating to sub-modules |

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
- `end_offset: float = 0.0` — stop processing N seconds before video end (0 = off)
- `on_log`, `on_progress`, `on_page_detected`, `is_cancelled` — callbacks
- `original_video_path: Optional[str]` — for YouTube dual-download workflow

Returns `ExtractResult`:
- `pages: List[Frame]` — the keep-only pool used for deduplication (old list,
  still in place)
- `manifest: List[PageManifestEntry]` — one entry per attempt
- `page_records: List[Page]` — one page object per analyzed page transition,
  including duplicates, blank captures, guard-rail failures and end-credit
  pages.  Each carries its image, boundary row, attempt number, file and status.
  Only KEEP pages print.
- `candidates: List[PageCandidate]` — the same transitions as lightweight
  records (attempt number, boundary row, file, status), derived from the pages

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
- `tail_scan(ocr, unique_pages, ...)` → the end-credit cutoff, or `None`.
  Does not remove pages; the committer flags trailing pages as duplicate.

### `PageCommitter` (`src/application/extraction_components.py`)

Handles the commit pipeline for each detected page pair:
1. Read full-res A/B frames from original video (scan-res fallback when unavailable)
2. Dynamic Bar Erase (merge full-res A+B via `video_service.merge_frames()`)
3. Bar profile validation (peak count + left spike margin)
4. OCR number extraction from merged full-res frames
5. Deduplication (OCR → Global → Row)
6. Save to disk via `file_service.save_page_image()`
7. Debug artifact writing (A/B frames, bar profile text)
8. Build the page object (`Page`) for the committed page

`committer.pages` returns every analyzed page transition in commit order — one
Page per candidate.  Kept pages share their image with the dedup-pool frame;
duplicate candidates keep their own image and point at the file written under
`candidates/`.  Deduplication still compares only against the `unique_pages`
keep-only pool.

### `BarProfilePlotter` (`src/application/extraction_components.py`)

Optional matplotlib diagnostic plots. Lazy-imports matplotlib. Only instantiated when `debug=True`.

### `read_saved_score()` (`src/application/saved_score.py`)

The one place that reads a score directory. It returns the pages of a saved
score and puts the config on the crop the score was saved with:
- `read_saved_score(score_dir, file_service, config)` → `SavedScore(pages, metadata)`
- `read_metadata(score_dir)` → the metadata of a score (empty when there is none)
- `pages_from_records(saved, metadata)` → the pages, from the page records.
  Photos are matched to records by the page number in the file name, because
  the records include duplicate candidates that have no photo.
- `apply_saved_crop(config, metadata)` → the crop the score was saved with

Both the GUI (`GuiApi.load_saved_score`, `GuiApi.regenerate_from_dir`) and the
command line (`main.py --from-dir`) read a score through here, so both see the
same pages, cropped the same way.

### `Deduplicator` (`src/domain/deduplication.py`)

Three-stage dedup pipeline:
1. OCR force-duplicate (short-circuit on matching numbers)
2. Global pixel similarity (256×256 grayscale, `TM_CCOEFF_NORMED`)
3. Row-wise similarity (Pearson correlation, coverage check)

Also provides bar profile validation: `check_bar_profile()` → `(has_clean, has_left_spike, peaks)`.

### `PageStore` (`src/domain/page_store.py`)

In-memory page storage. Holds **one copy** of each page:
- `_pages` — the page objects (the only copy of the pixel data); each page
  carries its own image, boundary row, file and status
- `_png_cache` — the encoded PNG of a page, keyed by that page (full-size
  rendering), so it cannot fall out of step with the page list
- Thumbnail generation (320px wide PNG)
- Full-resolution PNG encoding

## Data Flow: Extraction

```
main.py / gui_api.py
  └─ ExtractScoreUseCase.execute()
       ├─ FrameStepper.initialize(start_time)  →  optional first pair
       ├─ Loop: FrameStepper.step()
       │    ├─ SSIM detection on top ROI (scan video)
       │    └─ FrameStepper.capture_a_b()  →  (A, B) from scan video
       ├─ PageCommitter.commit()
       │    ├─ Read full-res A/B from original video (if available)
       │    ├─ video_service.merge_frames(full_res_A, full_res_B)  →  merged + bar info
       │    ├─ Bar profile validation (on scan-res A/B)
       │    ├─ OCR number extraction
       │    ├─ Deduplicator.is_duplicate(existing, merged)
       │    └─ file_service.save_page_image()
       ├─ FrameStepper.tail_scan()  →  end-credit cutoff (no trimming)
       ├─ PageCommitter.mark_end_credits(cutoff)  →  trailing pages DUPLICATE
       └─ return ExtractResult(pages, manifest, page_records, candidates)
```

## Data Flow: Reading a Saved Score

```
app_gui.py (user opens a score)      main.py --from-dir ./output/Sonata/
  └─ GuiApi.load_saved_score(dir)      └─ read_saved_score(dir, file_service, config)
       └─ read_saved_score(dir, ...)        ├─ read_metadata(dir)
            ├─ read_metadata(dir)            ├─ file_service.load_page_images_with_paths(dir)
            ├─ file_service.load_page_      ├─ pages_from_records(...)  →  pages with their rows
            │   images_with_paths(dir)      └─ apply_saved_crop(config, metadata)
            ├─ pages_from_records(...)
            └─ apply_saved_crop(config, metadata)
                 └─ PdfService.create_pdf(pages, ...) → the shared crop rule
```

## Data Flow: GUI Re-extraction

```
app_gui.py (user adjusts crop slider)
  └─ GuiApi.update_config({"default_crop_ratio": ratio})
       └─ stored in config; applied once by the crop rule at PDF generation

app_gui.py (user clicks "Regenerate PDF")
  └─ GuiApi.generate_pdf(output_path)
       └─ PdfService.create_pdf(pages.all_pages(), ...)
            └─ each page cropped by the shared rule (src/domain/page_crop.py)
```

## Data Flow: YouTube Download

```
app_gui.py
  └─ GuiApi.download_youtube(url, fmt, scan_fmt)
       └─ DownloadService.download()  →  dual-download:
            ├─ High-res video for PDF (original_path)
            └─ Low-res scan for extraction (scan_path)
       ├─ open_video(scan_path)  →  SSIM + bar detection use low-res
       └─ _original_video_path = high-res path
            →  PageCommitter reads full-res frames for merge (not just OCR/debug)
```

## Error Handling

- OCR failure: auto-fallback to `_NoopOcrService` (no user prompt)
- Video seek failure: skip frame, continue loop
- Extraction thread exceptions: caught, emitted via `on_error` callback
- PDF generation exceptions: caught, emitted via `on_error` callback