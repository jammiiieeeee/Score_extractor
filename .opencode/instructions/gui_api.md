# GUI API Specification

This document defines the 47-method Python API surface for GUI integration.

## Design Principles

- **Single import**: `from src.api.gui_api import GuiApi`
- **Thread-safe**: Extraction/PDF/download run on background threads; callbacks dispatch to GUI thread.
- **Callback-driven**: Async progress, page detection, errors, and completion flow through registered callbacks.
- **No GUI framework dependency**: Pure Python — no PyQt, Tkinter, or UI library imports.
- **Delegates to sub-modules**: `VideoService`, `OcrService`, `PdfService`, `FileService`, `DownloadService`, `PageStore`.

## Dataclasses

```python
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
    phase: str              # "idle"|"extracting"|"cancelling"|"downloading"|"generating_pdf"|"done"|"error"
    pages_detected: int
    elapsed_seconds: float
    current_timestamp: float

@dataclass
class ScoreInfo:
    path: str
    page_count: int
    score_name: str
```

## API Methods

### Config Management (5)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 1 | `get_config()` | `→ dict` | Flat dict of all `ScoreConfig` fields |
| 2 | `update_config(updates)` | `dict → dict` | Patch fields with validation. Raises `ValueError` on invalid keys/values |
| 3 | `reset_config()` | `→ dict` | Restore `ScoreConfig()` defaults |
| 4 | `load_config_file(path)` | `str → dict` | Load config from JSON file |
| 5 | `save_config_file(path)` | `str → None` | Serialize current config to JSON |

### Video Management (4)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 6 | `open_video(path)` | `str → VideoInfo` | Open video, extract metadata |
| 7 | `get_video_info()` | `→ VideoInfo\|None` | Cached metadata from last `open_video()` |
| 8 | `read_frame_at(timestamp)` | `float → np.ndarray\|None` | Read frame at timestamp (seconds) |
| 9 | `close_video()` | `→ None` | Release video handle |

### OCR Management (3)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 10 | `init_ocr()` | `→ bool` | Initialize PaddleOCR with 3-attempt fallback |
| 11 | `ocr_status()` | `→ bool` | Is OCR operational? |
| 12 | `ocr_preview(image_bytes)` | `bytes → list[str]` | Run OCR on PNG image, return text lines |

### Extraction Process (3)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 13 | `start_extraction(video_path, no_ocr, start_time, duration, output_folder, score_name)` | → None | Start extraction on background thread |
| 14 | `cancel_extraction()` | `→ None` | Set cancellation flag |
| 15 | `get_extraction_state()` | `→ ExtractionState` | Current phase + metadata |

### Callback Registry (7)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 16 | `set_on_progress(fn)` | `fn(phase, percent, detail) → None` | Progress updates |
| 17 | `set_on_page_detected(fn)` | `fn(index, image_bytes) → None` | New unique page confirmed |
| 18 | `set_on_log(fn)` | `fn(message) → None` | Status/debug messages |
| 19 | `set_on_error(fn)` | `fn(message) → None` | Non-fatal errors |
| 20 | `set_on_completed(fn)` | `fn(page_count) → None` | Operation finished |
| 21 | `set_on_cancelled(fn)` | `fn() → None` | Cancellation acknowledged |
| 22 | `set_on_download_completed(fn)` | `fn(path) → None` | YouTube download finished |

### Page Management (10)

Pages are read and changed through this interface only.  Callers (the GUI and
the tests) never touch the store's internal lists, so how pages are held can
change without rewriting them.  `get_page` returns a `PageState` view carrying
the page's index, image, boundary row, file and status; `set_page_status`
changes one page's status and writes it into the score's metadata, so the
flag survives a reload.

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 23 | `get_page_count()` | `→ int` | Number of stored pages |
| 24 | `add_page(image, boundary_row, file, status)` | `np.ndarray, int?, str?, PageStatus? → int` | Append a page, return its index |
| 25 | `set_pages(pages)` | `list[Page\|Frame\|np.ndarray] → None` | Replace all pages at once |
| 26 | `get_page(index)` | `int → PageState` | Read a page's index, image, boundary row, file, status |
| 27 | `set_page_status(index, status)` | `int, PageStatus → None` | Change one page's status and save it |
| 28 | `get_page_thumbnail(index)` | `int → bytes\|None` | PNG bytes, 320px wide |
| 29 | `get_page_full(index)` | `int → bytes\|None` | PNG bytes, full resolution |
| 30 | `remove_page(index)` | `int → None` | Remove a page and the file it was written to |
| 31 | `clear_pages()` | `→ None` | Remove all pages |

### PDF Generation (2)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 32 | `generate_pdf(output_path, title)` | `str, str? → None` | Generate PDF on background thread |
| 33 | `regenerate_from_dir(score_dir, output_path)` | `str, str? → None` | Load pages from dir with their saved crop, generate PDF |

### YouTube Download (1)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 34 | `download_youtube(url, fmt, scan_fmt)` | `str, str, str → None` | Download on background thread |

### Score Management (4)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 35 | `list_saved_scores(output_folder)` | `str → list[ScoreInfo]` | List existing scores in directory |
| 36 | `load_saved_score(path)` | `str → int` | Load pages from existing score |
| 37 | `delete_saved_score(path)` | `str → None` | Delete score directory |
| 38 | `save_metadata(score_dir, data)` | `str, dict → None` | Write metadata.json |

### Re-extraction Helpers (6)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 39 | `has_loaded_score()` | `→ bool` | Is an existing score loaded? |
| 40 | `get_loaded_score_path()` | `→ str\|None` | Path of loaded score |
| 41 | `get_loaded_score_metadata()` | `→ dict` | metadata.json contents |
| 42 | `is_loading_from_scratch()` | `→ bool` | True if no loaded score |
| 43 | `get_first_page_image()` | `→ np.ndarray\|None` | First page for preview |

### Lifecycle (3)

| # | Method | Signature | Description |
|---|--------|-----------|-------------|
| 44 | `cleanup()` | `→ None` | Close video, clear pages |
| 45 | `is_busy()` | `→ bool` | Any background thread alive? |
| 46 | `set_debug_mode(enabled)` | `bool → None` | Enable/disable debug mode |

## Threading Model

Three independent background threads:
- `_extraction_thread` — extraction pipeline
- `_pdf_thread` — PDF generation
- `_download_thread` — YouTube download

`is_busy()` checks all three. `start_extraction()`, `generate_pdf()`, `download_youtube()` raise `RuntimeError` if already busy.

## Error Handling

- Background-thread errors caught and delivered via `on_error` callback
- `get_extraction_state()` returns phase `"error"` after background failure
- Config validation: `ValueError` for unknown keys or out-of-range values