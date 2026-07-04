# GUI Design Specification

## Overview

This document defines the PyQt6 graphical interface for non-technical users. It consumes the `GuiApi` (`src/api/gui_api.py`, spec at `@reference gui_api.md`) which handles all background threading, video processing, OCR, and PDF generation.

## Architectural Rule

**The GUI layer (`app_gui.py`, `gui_bridge.py`) is a thin wrapper around the CLI layer (`src/application/use_cases.py`).** It must never duplicate or directly implement business logic, extraction loops, or processing pipelines. All behavior lives in `use_cases.py` or domain/infrastructure classes. If the CLI is missing functionality, implement it in `use_cases.py` and expose it through `GuiApi`. The GUI only handles layout, Qt signal wiring, and callback plumbing.

## Project Layout

```
repo root/
├── app_gui.py          # Main window, tabs, and layout
├── gui_bridge.py       # ExtractionSignals QObject (callback → Qt signal relay)
├── build_exe.ps1       # PyInstaller packaging script
├── main.py             # Existing CLI entrypoint (unchanged)
└── src/                # Existing library code (unchanged)
```

## Framework

- **PyQt6** (`pip install PyQt6`)
- Single `.exe` distribution via PyInstaller (`--onefile --upx-dir=...`)
- Estimated build size: ~150MB

## Tab Layout

| Tab | Purpose |
|-----|---------|
| **Config** | Tune extraction parameters |
| **Extract** | Video selection, previews, progress, and one-click output |
| **Gallery** | Review, reorder, delete pages before/after generation |
| **Export** | Sandbox management and PDF regeneration |

---

## Tab Details

### 1. Config Tab

**Default view** (5 fields most users need):

| Field | Widget | Config key | Default |
|-------|--------|------------|---------|
| Crop ratio | QDoubleSpinBox (0.0–1.0, step 0.01) | `default_crop_ratio` | 0.35 |
| Strips per page | QSpinBox (1–20) | `default_strips_per_page` | 7 |
| Page change sensitivity | QDoubleSpinBox (0.0–1.0, step 0.01) | `change_detection_threshold` | 0.96 |
| Min seconds between captures | QDoubleSpinBox (0.0–60.0, step 0.5) | `min_screenshot_interval` | 3.0 |
| OCR confidence | QSpinBox (0–100) | `ocr_confidence_threshold` | 40 |

**Advanced expander** (collapsed by default, QGroupBox with checkable title):

- **Change Detection** — `frame_check_interval`, `top_analysis_ratio`
- **A/B Capture** — `a_capture_delay`, `b_capture_delay`, `b_overlay_width_ratio`
- **Deduplication** — `duplicate_top_ratio`, `pixel_similarity_threshold`, `row_similarity_threshold`, `row_coverage_threshold`
- **OCR** — `ocr_horizontal_ratio`
- **PDF Output** — `crop_top_offset`
- **Blank Detection** — `blank_content_std_threshold`

All updates call `api.update_config(...)` with validation (errors shown in a QMessageBox).

---

### 2. Extract Tab

Layout top-to-bottom:

```
┌──────────────────────────────────────────────────────────┐
│ [ Video file: ____________________ ] [Browse…] [Preview] │
├──────────────────────────────────────────────────────────┤
│ ┌─Crop──┬─Start Time──┬─End Duration──┐                  │
│ │       │              │               │                  │
│ └───────┴──────────────┴───────────────┘                  │
├──────────────────────────────────────────────────────────┤
│ [════════════ Progress ════════════] 48%                  │
│ log: Processing video...                                  │
│      Change detected at 12.3s...                          │
│      Page 5 detected...                                   │
├──────────────────────────────────────────────────────────┤
│ [ Save PDF to: __________________ ] [Browse…]             │
│ Pages: 12   [ Start Extraction ]                          │
└──────────────────────────────────────────────────────────┘
```

#### Video File Picker

- QLineEdit + QPushButton("Browse…") using `QFileDialog.getOpenFileName` (filter: `*.mp4 *.avi *.mkv *.mov`)
- QPushButton("Preview") — opens the first sub-tab (Crop) and shows frame 0
- Gray out "Start Extraction" until a valid video is loaded

#### Preview Sub-Tabs (QTabWidget)

All three share a common pattern:
- Show the video frame at a selected timestamp
- Provide a way to set a value that maps to a CLI parameter

**Crop tab** (`default_crop_ratio`):
- Shows the first video frame (or a representative frame)
- A highlighted horizontal band starting at the top edge of the frame
- The bottom edge of the band is a draggable horizontal line
- Dragging the line changes `default_crop_ratio` (shown as "Crop: 35%")
- No start-time toggle — this is always active
- `crop_top_offset` stays at 0.0

**Start Time tab** (`start_time`):
- QCheckBox "Enable start-time capture" — **checked by default**
- When unchecked, `start_time = -1.0` (start from beginning)
- When checked, a QSlider (0 → video duration) seeks through the video
- Frame updates live as the slider is dragged
- Timestamp shown: "Start: 0:32.5"
- Value passed to `GuiApi.start_extraction(start_time=<value>)`

**End Duration tab** (`duration`):
- QCheckBox "Stop extraction after…" — **unchecked by default**
- When unchecked, `duration = 0.0` (let blank-page detection end naturally)
- When checked, a QSlider (0 → video duration) seeks through the video
- Frame updates live as the slider is dragged
- Timestamp shown: "End: 1:45.0"
- Value passed to `GuiApi.start_extraction(duration=<value>)`

All three sliders call `GuiApi.read_frame_at(timestamp)` to get PNG bytes, decoded into QPixmap for display. The frame display is a QLabel inside a QScrollArea.

#### Progress & Log

- QProgressBar (0–100%) updated via `on_progress` callback
- QTextEdit (read-only) for log output via `on_log` callback
- "Pages: N" label updated via `on_page_detected` callback

#### Bottom Action Bar

- QLineEdit for output path (defaults to input filename with `.pdf`)
- QPushButton("Browse…") for QFileDialog to choose save location
- QPushButton("Start Extraction") — triggers the full pipeline:
  1. Calls `GuiApi.start_extraction(...)` with all user-set parameters
  2. On `on_completed`, **automatically calls** `GuiApi.generate_pdf(output_path)`
  3. On success, shows QMessageBox: "PDF saved to path"
  4. On error, shows QMessageBox with the error
- The button text changes to "Extracting…" while busy; disabled when `api.is_busy()`
- QPushButton("Cancel") — calls `api.cancel_extraction()`

---

### 3. Gallery Tab

```
┌──────────────────────────────────────────────────────────┐
│ Pages: 12                                                │
│                                                          │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐                     │
│ │  pg 1   │ │  pg 2   │ │  pg 3   │                     │
│ │(thumb)  │ │(thumb)  │ │(thumb)  │                     │
│ └─────────┘ └─────────┘ └─────────┘  ...                │
│ (QListWidget in IconMode, vertical scroll)               │
│                                                          │
│ [▲ Move Up] [▼ Move Down] [Delete] [Clear All]           │
└──────────────────────────────────────────────────────────┘
```

- Thumbnails populated via `GuiApi.get_page_thumbnail(index)` → QPixmap
- Selected item is highlighted; Move Up/Down calls `GuiApi.reorder_pages()`
- Delete calls `GuiApi.remove_page(index)`; Clear All calls `GuiApi.clear_pages()`
- After each operation, the thumbnail list refreshes
- **Double-click** a thumbnail → opens a QDialog with full-resolution image from `GuiApi.get_page_full(index)` (QScrollArea if image is large)
- Tab is disabled when no pages exist (`get_page_count() == 0`)

---

### 4. Export Tab

```
┌──────────────────────────────────────────────────────────┐
│ Output PDF                                               │
│ [_________________________] [Browse…]                    │
│                                                          │
│ [Regenerate PDF]                                         │
│                                                          │
│ ── Previous Sessions ────────────────────────────────    │
│                                                          │
│ [▼ tmp_a1b2c3 (12 pages, 2026-06-14, 点描の唄)]  [Load]  │
│ [▼ tmp_d4e5f6 ( 8 pages, 2026-06-13, スパークル)] [Del]  │
│                                                          │
│ Status: last action result...                            │
└──────────────────────────────────────────────────────────┘
```

- **Output path**: QLineEdit + Browse (QFileDialog). Pre-filled from Extract tab's path
- **Regenerate PDF**: Calls `GuiApi.generate_pdf(output_path)` on loaded pages. Shows progress via callbacks
- **Sandbox list**: Populated from `GuiApi.list_sandboxes()`. Each row shows `SandboxInfo` fields
- **[Load]**: Calls `GuiApi.load_sandbox(path)`, then switches to Gallery tab for review
- **[Del]**: Calls `GuiApi.delete_sandbox(path)`, refreshes the list
- **Status**: QLabel updated by `on_log` / `on_completed` / `on_error` callbacks

---

## Thread Bridge (`gui_bridge.py`)

The `GuiApi` runs extraction and PDF generation on daemon threads. It emits plain Python callbacks which run on the background thread — unsafe for direct GUI updates.

```python
from PyQt6.QtCore import QObject, pyqtSignal

class ExtractionSignals(QObject):
    progress      = pyqtSignal(str, float, str)  # phase, percent, detail
    page_detected = pyqtSignal(int, bytes)       # index, png_bytes
    log           = pyqtSignal(str)
    error         = pyqtSignal(str)
    completed     = pyqtSignal(int)              # page_count
    cancelled     = pyqtSignal()

    def wire(self, api: "GuiApi"):
        api.set_on_progress(lambda p, pc, d: self.progress.emit(p, pc, d))
        api.set_on_page_detected(lambda i, b: self.page_detected.emit(i, b))
        api.set_on_log(lambda m: self.log.emit(m))
        api.set_on_error(lambda m: self.error.emit(m))
        api.set_on_completed(lambda c: self.completed.emit(c))
        api.set_on_cancelled(lambda: self.cancelled.emit())
```

`app_gui.py` creates one `ExtractionSignals` instance, calls `.wire(api)`, and connects each signal to the appropriate slot:

```python
self.signals = ExtractionSignals()
self.signals.wire(self.api)
self.signals.progress.connect(self._on_progress)
self.signals.page_detected.connect(self._on_page_detected)
# ...
```

This is the only thread-safe bridge needed. PyQt6's signal-slot mechanism automatically delivers emitted signals on the GUI thread.

---

## Packaging

### Build Command

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name ScoreExtractor --upx-dir="C:\upx" app_gui.py
```

### Notes

- `--onefile` produces a single `.exe` (easiest for non-technical users)
- `--windowed` suppresses the console window
- UPX compression reduces size by 30–50% with no quality impact
- Expected output size: ~150MB
- The `.exe` is portable — copy it anywhere, no Python or dependencies needed
- For distribution, consider adding `--exclude-module` for unused PyQt6 modules (`QtBluetooth`, `QtNetwork`, `QtQml`, `QtSql`, etc.) to reduce size further in a future version

### File list for PyInstaller hook (auto-detected, no manual spec needed):
- `app_gui.py`, `gui_bridge.py`
- `src/api/gui_api.py`
- `src/application/use_cases.py`
- `src/domain/` (models, deduplication, interfaces, value_objects)
- `src/infrastructure/` (video_service, ocr_service, pdf_service, file_service)
- `paddleocr`, `paddlepaddle`, `cv2`, `reportlab`, `skimage`, `numpy`, `rich`

---

## CLI ↔ GUI Method Mapping

| CLI flag | GUI location | GuiApi method |
|----------|-------------|---------------|
| `input` | Extract tab → Browse | `open_video(path)` |
| `-o/--output` | Extract tab → Save PDF to… | `generate_pdf(output)` |
| `-c/--config` | Config tab → all fields | `update_config({...})` |
| `-d/--debug` | (not exposed — always on in GUI) | `start_extraction(debug=True)` |
| `--no-ocr` | Config tab → OCR confidence = 0 disables | `start_extraction(no_ocr=True)` |
| `--start-time` | Extract → Start Time sub-tab | `start_extraction(start_time=...)` |
| `--duration` | Extract → End Duration sub-tab | `start_extraction(duration=...)` |
| `--crop-ratio` | Config tab → Crop ratio field | `update_config({"default_crop_ratio": ...})` |
| `--from-dir` | Export tab → Previous Sessions → Load | `load_sandbox(path)` → `generate_pdf(path)` |
