# GUI API Specification

This document defines the Python API surface that any GUI framework (PyQt, Tkinter, web-based via eel/brython, etc.) can consume to build a graphical interface for the Piano Score Video-to-PDF Extractor.

## Design Principles

- **Single import**: `from src.api.gui_api import GuiApi`
- **Thread-safe**: Extraction runs on a background thread; callbacks dispatch to the GUI thread.
- **Callback-driven**: Async progress, page detection, errors, and completion flow through registered callbacks.
- **No GUI framework dependency**: The API itself is pure Python — it does not import PyQt, Tkinter, or any UI library.
- **Lazy resource initialization**: Video capture and OCR engines are created on first use, not on construction.

## API Reference

### 1. Construction

| Method | Signature | Description |
|--------|-----------|-------------|
| Constructor | `GuiApi(config_path: str = "config.json")` | Loads config from JSON (or creates default). Initialises FileService. Does NOT open video or OCR. |

```python
from src.api.gui_api import GuiApi
api = GuiApi("config.json")
```

---

### 2. Config Management

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 1 | `get_config() -> dict` | Flat dict of all `ScoreConfig` fields | Read current configuration |
| 2 | `update_config(updates: dict) -> dict` | Updated config dict | Patch specific fields with validation (type checks, range checks). Returns full updated config. |
| 3 | `reset_config() -> dict` | Default config dict | Restore factory defaults from `ScoreConfig()` |
| 4 | `load_config_file(path: str) -> dict` | Loaded config dict | Load `ScoreConfig` from a JSON file |
| 5 | `save_config_file(path: str) -> None` | — | Serialize current config to JSON |

**Validation rules** (`update_config`):
- All float fields: must be 0.0–1.0 (except `blank_content_std_threshold` and `ocr_confidence_threshold`)
- `ocr_confidence_threshold`: int 0–100
- `default_strips_per_page`: int 1–20
- Reject unknown keys

---

### 3. Video Management

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 6 | `open_video(path: str) -> VideoInfo` | `VideoInfo` dataclass | Open video file; validate it is readable; extract metadata. Raises `ValueError` on failure. |
| 7 | `get_video_info() -> VideoInfo\|None` | Cached metadata or `None` | Returns info from last `open_video()` call |
| 8 | `read_frame_at(timestamp: float) -> bytes\|None` | PNG bytes of the frame | Seek to a timestamp, decode frame, encode as PNG bytes (for GUI thumbnail display). `None` on seek failure. |
| 9 | `close_video() -> None` | — | Release `cv2.VideoCapture` handle |

**`VideoInfo` dataclass**:
```python
@dataclass
class VideoInfo:
    path: str
    duration: float        # seconds
    fps: float
    width: int
    height: int
    frame_count: int
```

---

### 4. OCR Management

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 10 | `init_ocr() -> bool` | Success flag | Initialize PaddleOCR with 3-attempt fallback. Emits `on_log` for each attempt. Returns `True` if any attempt succeeded. |
| 11 | `ocr_status() -> bool` | OCR is operational? | Returns `self._ocr.is_enabled()` |
| 12 | `ocr_preview(image_bytes: bytes) -> list[str]` | Extracted text lines | Run OCR on a PNG-encoded image and return all recognized strings. Used for "test OCR on current frame" button. |

---

### 5. Extraction Process

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 13 | `start_extraction(video_path: str \| None = None, no_ocr: bool = False, start_time: float = -1.0, duration: float = 0.0, debug: bool = False) -> None` | — | Start extraction on a background thread. If `video_path` is provided, calls `open_video()` first. Progress emitted via callbacks (see §6). Raises `RuntimeError` if already running. |
| 14 | `cancel_extraction() -> None` | — | Set cancellation flag; the extraction loop checks this at each iteration and stops gracefully |
| 15 | `get_extraction_state() -> ExtractionState` | Current state | Returns phase enum + metadata |

**`ExtractionState` dataclass**:
```python
@dataclass
class ExtractionState:
    phase: str                        # "idle" | "extracting" | "cancelling" | "done" | "error"
    pages_detected: int
    elapsed_seconds: float
    current_timestamp: float          # video timestamp being processed
```

**Cancellation points in extraction loop**:
- After each seek step in the main `while True`
- Before `_process_new_page`
- After each page processed during tail scan

---

### 6. Callback Registry

All callbacks are stored as simple function references. The GUI framework is responsible for dispatching to its event loop (e.g., PyQt `pyqtSignal`, Tkinter `after_idle`).

| Callback | Signature | When Emitted |
|----------|-----------|-------------|
| `set_on_progress(fn)` | `fn(phase: str, percent: float, detail: str)` | Every iteration of extraction loop (percent is estimated from elapsed / duration or frame progress) |
| `set_on_page_detected(fn)` | `fn(index: int, image_bytes: bytes)` | Each time a new unique page is confirmed; `image_bytes` is PNG-encoded merged strip for live gallery |
| `set_on_log(fn)` | `fn(message: str)` | Replaces all `print()` calls; includes status messages, OCR attempt notes, detected bar x, etc. |
| `set_on_error(fn)` | `fn(message: str)` | Non-fatal errors (e.g., OCR partial failure, failed seek during tail scan) |
| `set_on_completed(fn)` | `fn(page_count: int)` | Extraction finished successfully |
| `set_on_cancelled(fn)` | `fn()` | User-requested cancellation acknowledged |

---

### 7. Page Management (Post-Extraction)

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 16 | `get_page_count() -> int` | Number of stored pages | — |
| 17 | `get_page_thumbnail(index: int) -> bytes\|None` | PNG bytes, resized to 320px wide | For gallery thumbnails in the GUI |
| 18 | `get_page_full(index: int) -> bytes\|None` | PNG bytes, full resolution | For preview / zoom |
| 19 | `remove_page(index: int) -> None` | — | Remove a page before PDF generation. Raises `IndexError` on invalid index. |
| 20 | `reorder_pages(new_order: list[int]) -> None` | — | Reorder pages by providing the desired index order (0-based). Length must match page count. |
| 21 | `clear_pages() -> None` | — | Remove all pages (reset state for new extraction) |

---

### 8. PDF Generation

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 22 | `generate_pdf(output_path: str) -> None` | — | Generate PDF from current page list. Runs on background thread. Emits `on_progress`, `on_completed`, `on_error`. Sandbox is cleaned up on success unless `debug=True`. |
| 23 | `regenerate_from_dir(sandbox_dir: str, output_path: str \| None = None) -> None` | — | Skip extraction, load page images from an existing sandbox directory, generate PDF. Useful for "try a different config" workflow. |

---

### 9. Sandbox Management

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 24 | `list_sandboxes() -> list[SandboxInfo]` | List of sandbox dirs | Scan `debug/` for `tmp_*` directories that contain `page_*_merged.png` files |
| 25 | `load_sandbox(path: str) -> int` | Page count loaded | Load pages from an existing sandbox into memory for preview/PDF gen |
| 26 | `delete_sandbox(path: str) -> None` | — | Remove a sandbox directory |

**`SandboxInfo` dataclass**:
```python
@dataclass
class SandboxInfo:
    path: str
    page_count: int
    created: datetime
    video_name: str                 # from extraction.log or directory naming heuristic
```

---

### 10. Lifecycle

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 27 | `cleanup() -> None` | — | Close video, release OCR memory, remove sandbox (if not debug) |
| 28 | `is_busy() -> bool` | Is extraction or PDF gen running? | Check if background thread is alive |

---

## Threading Model

```
GUI Thread                             Background Thread
=============                          =================
api.start_extraction() ──────────────> thread starts
  └─ set_on_page_detected(fn)            │
  └─ set_on_progress(fn)                 │ process frames
  └─ ...                                 │
                                         │ fn(page_detected) ──> queued to GUI
api.cancel_extraction() ──────────────>  │ check cancel flag
                                         │ if flag set: break, fn(cancelled)
                                         │
                                         │ fn(completed) ──> queued to GUI
```

**Important**: The API does not import any GUI toolkit. The callbacks are plain Python callables. The GUI must wrap them in thread-safe dispatchers:
- PyQt: `QMetaObject.invokeMethod` or `pyqtSignal`
- Tkinter: `root.after(0, callback)`
- wxPython: `wx.CallAfter`

---

## Integration Example (PyQt)

```python
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from src.api.gui_api import GuiApi

class GuiBridge(QObject):
    page_detected = pyqtSignal(int, bytes)

    def __init__(self):
        super().__init__()
        self.api = GuiApi()

        def on_page(idx, img_bytes):
            self.page_detected.emit(idx, img_bytes)

        self.api.set_on_page_detected(on_page)
```

---

## Error Handling

- All API methods raise typed exceptions: `ValueError`, `RuntimeError`, `FileNotFoundError`
- Background-thread errors are caught and delivered via `on_error` callback, not thrown
- `get_extraction_state()` returns phase `"error"` + message after a background failure

---

## Summary of All API Methods

| # | Method | Category |
|---|--------|----------|
| 1 | `get_config()` | Config |
| 2 | `update_config(updates)` | Config |
| 3 | `reset_config()` | Config |
| 4 | `load_config_file(path)` | Config |
| 5 | `save_config_file(path)` | Config |
| 6 | `open_video(path)` | Video |
| 7 | `get_video_info()` | Video |
| 8 | `read_frame_at(timestamp)` | Video |
| 9 | `close_video()` | Video |
| 10 | `init_ocr()` | OCR |
| 11 | `ocr_status()` | OCR |
| 12 | `ocr_preview(image_bytes)` | OCR |
| 13 | `start_extraction(...)` | Extraction |
| 14 | `cancel_extraction()` | Extraction |
| 15 | `get_extraction_state()` | Extraction |
| 16 | `get_page_count()` | Pages |
| 17 | `get_page_thumbnail(index)` | Pages |
| 18 | `get_page_full(index)` | Pages |
| 19 | `remove_page(index)` | Pages |
| 20 | `reorder_pages(new_order)` | Pages |
| 21 | `clear_pages()` | Pages |
| 22 | `generate_pdf(output_path)` | PDF |
| 23 | `regenerate_from_dir(sandbox_dir)` | PDF |
| 24 | `list_sandboxes()` | Sandbox |
| 25 | `load_sandbox(path)` | Sandbox |
| 26 | `delete_sandbox(path)` | Sandbox |
| 27 | `cleanup()` | Lifecycle |
| 28 | `is_busy()` | Lifecycle |
