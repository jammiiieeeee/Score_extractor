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
| **Extract** | Unified entry point — fresh extraction or re-extraction from existing score |
| **Config** | Tune extraction parameters |

---

## Tab Details

### 1. Extract Tab

Single unified interface driven by the **Project** field at the top. The entire UI state (new vs existing project) determines what the action button does.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Extract                                                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  Project: [Mozart Piano Sonata________________________________] [Browse…]    │
│  ● New project — pick a video to start                                       │
│  ✓ Loaded "Mozart Piano Sonata" — 12 pages (originally 35% crop)            │
│                                                                               │
│  ───────────────────────────────────────────────────────────────────────────  │
│  Source: (●) Local file  (○) YouTube URL                                     │
│  Video:  [_______________________________________________] [Browse…]          │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │                         Preview                                    │    │
│  │    (shows video frame OR first loaded page — crop line always live) │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│  [═══════════════════════════════════════════] Seek bar (disabled if loaded) │
│                                                                               │
│  Crop ratio:  [0.35       ]   (was 35%)                 [Set as Default]      │
│  Output PDF:  [Mozart_Piano_Sonata_________________________________.pdf]     │
│                                                                               │
│  ───────────────────────────────────────────────────────────────────────────  │
│  [████████████████████████░░░░░░░░░░░░░░░░░░░░] 65%                          │
│  Processing video...                                                           │
│                                                                               │
│  [    Start Extraction / Regenerate PDF / Open PDF    ]  [Cancel]             │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Project Field

- **QLineEdit** with **QCompleter** — fed by `GuiApi.list_saved_scores(parent_dir)`
- Type a new name + Enter → creates new project at `{parent_dir}/{name}`
- Select a completion → loads that score, enters re-extraction mode
- **Browse…** button: opens `QFileDialog.getExistingDirectory`:
  - If folder contains `photos/` → loads as existing score
  - Otherwise sets parent directory for new projects
- Parent directory persisted in `QSettings("ScoreExtractor", "App")`

#### Status Label

Updates dynamically based on state:

| State | Status text |
|-------|-------------|
| No project | "New project — enter a score name or select an existing one" |
| Project set, no video | "Pick a video to start" |
| Video loaded | "Ready — video loaded" |
| Existing score loaded | "Loaded N pages from ScoreName (originally X% crop)" |
| Extracting | "Extracting pages from video…" |
| Generating PDF | "Generating PDF from loaded pages…" |
| Done | "✓ PDF saved — path" |

#### Video Controls (always visible)

- Source toggle: Local file / YouTube URL
- Local: QLineEdit + Browse (filter: `*.mp4 *.avi *.mkv *.mov`)
- YouTube: QLineEdit + quality QComboBox + Download button
- **Disabled** when an existing score is loaded

#### Preview Widget

- `CropPreviewWidget` — shows video frame (new) or first loaded page (existing)
- Draggable crop line updates the crop ratio spinbox
- Always interactive regardless of mode

#### Seek Bar

- `DualHandleSeekBar` — start time + end duration
- Enabled for new projects, disabled when existing score loaded

#### Crop Ratio Row

- QDoubleSpinBox (0.0–1.0, step 0.01)
- Shows "(was X%)" label when existing score loaded
- "Set as Default" button saves to config
- In existing mode, changing the spinbox re-crops loaded pages on the fly via `GuiApi.reapply_crop(ratio)`

#### Output PDF

- QLineEdit for PDF filename (defaults to project name)
- Extension auto-appended if missing

#### Progress & Log

- QProgressBar (0–100%)
- QTextEdit (read-only, max 140px)
- Action button shows percentage during operations: "Extracting… 45%"

#### Action Button (state-driven)

| State | Button text | Behavior |
|-------|-------------|----------|
| New project + video ready | **Start Extraction** | Full video→pages→PDF pipeline |
| Existing score loaded | **Regenerate PDF** | Re-crop loaded pages + generate PDF |
| Busy | **Extracting… (45%)** | Disabled, shows progress |
| PDF complete | **✓ Open PDF** | Calls `os.startfile(output_path)` |

#### Cancel Button

- Enabled only during extraction (not during PDF generation)
- Calls `GuiApi.cancel_extraction()`

---

### 2. Config Tab

**Unchanged from previous design.** Full settings panel with:

**Basic Settings** (inline, no group box):
- Crop ratio (0.0–1.0, step 0.01, default 0.35)
- Page change sensitivity (0.0–1.0, step 0.01, default 0.96)
- Min seconds between captures (0.0–60.0, step 0.5, default 3.0)
- OCR confidence (0–100, default 40)

**Advanced Settings** (QGroupBox "Advanced Settings"):
- Frame check interval, Top analysis ratio, A/B capture delays, B overlay width
- Deduplication: Duplicate top ratio, Pixel/row similarity, Row coverage
- OCR horizontal ratio, Crop top offset, Blank content std threshold
- Bar min diff threshold, Bar overlay offset

**Debug mode checkbox:** "Debug mode (open temp folder on completion)"

All changes auto-apply via `GuiApi.update_config()`.

---

## Re-extraction Data Flow

1. **User selects existing project** via completer or Browse → `GuiApi.load_saved_score(path)`
2. API loads page images from `{path}/photos/page_*_merged.png` into `_pages` and `_original_pages`
3. API reads `{path}/metadata.json` → restores original crop ratio
4. **User adjusts crop ratio** → `GuiApi.reapply_crop(ratio)` crops from `_original_pages` each time
5. **User clicks "Regenerate PDF"** → `GuiApi.generate_pdf(output_path)` with cached pages
6. Metadata saved to `{output_parent}/metadata.json` after PDF generation

---

## Thread Bridge (`gui_bridge.py`)

```python
from PyQt6.QtCore import QObject, pyqtSignal

class ExtractionSignals(QObject):
    progress      = pyqtSignal(str, float, str)
    page_detected = pyqtSignal(int, bytes)
    log           = pyqtSignal(str)
    error         = pyqtSignal(str)
    completed     = pyqtSignal(int)
    cancelled     = pyqtSignal()

    def wire(self, api: "GuiApi"):
        api.set_on_progress(lambda p, pc, d: self.progress.emit(p, pc, d))
        api.set_on_page_detected(lambda i, b: self.page_detected.emit(i, b))
        api.set_on_log(lambda m: self.log.emit(m))
        api.set_on_error(lambda m: self.error.emit(m))
        api.set_on_completed(lambda c: self.completed.emit(c))
        api.set_on_cancelled(lambda: self.cancelled.emit())
```

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
- The `.exe` is portable — copy it anywhere

### Auto-detected files for PyInstaller hook:
- `app_gui.py`, `gui_bridge.py`
- `src/api/gui_api.py`
- `src/application/use_cases.py`
- `src/domain/` (models, interfaces, value_objects)
- `src/infrastructure/` (video_service, ocr_service, pdf_service, file_service)
- `paddleocr`, `paddlepaddle`, `cv2`, `reportlab`, `skimage`, `numpy`, `rich`

---

## API Method Mapping

| Function | GUI element | GuiApi method |
|----------|-------------|---------------|
| Project selection | Project field + QCompleter | `list_saved_scores(parent_dir)` |
| Load existing score | Completion or Browse | `load_saved_score(path)` |
| New project | Type new name | `start_extraction(output_folder, score_name)` |
| Video selection | Browse button | `open_video(path)` |
| YouTube download | Download button | `download_youtube(url, fmt)` |
| Start extraction | Action button (new mode) | `start_extraction(...)` |
| Regenerate PDF | Action button (existing mode) | `generate_pdf(output_path)` |
| Re-crop pages | Crop ratio spinbox | `reapply_crop(ratio)` |
| Cancel | Cancel button | `cancel_extraction()` |
| Config | Config tab all fields | `update_config({...})` |
| Open PDF | Action button (done state) | `os.startfile(path)` |
