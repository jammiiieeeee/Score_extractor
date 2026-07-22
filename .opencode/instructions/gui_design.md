# GUI Design Specification

## Overview

PyQt6 graphical interface for non-technical users. Consumes `GuiApi` (`src/api/gui_api.py`) for all background operations.

## Project Layout

```
repo root/
├── app_gui.py          # Main window, tabs, layout
├── main.py             # CLI entrypoint
└── src/                # Library code
```

## Tab Layout

| Tab | Purpose |
|-----|---------|
| **Extract** | Unified entry point — fresh extraction or re-extraction |
| **Config** | Tune extraction parameters |

---

## Tab 1: Extract

Single unified interface driven by the **Project** field at the top.

### Project Field
- `QLineEdit` with `QCompleter` fed by `GuiApi.list_saved_scores(parent_dir)`
- Type new name + Enter → creates new project
- Select completion → loads existing score
- Parent directory persisted in `QSettings("ScoreExtractor", "App")`

### Video Controls
- Source toggle: Local file / YouTube URL
- Local: QLineEdit + Browse (filter: `*.mp4 *.avi *.mkv *.mov`)
- YouTube: QLineEdit + quality QComboBox + Download button
- **Disabled** when an existing score is loaded

### Preview Widget
- `CropPreviewWidget` — shows video frame (new) or first loaded page (existing)
- Draggable crop line updates the crop ratio spinbox
- Always interactive regardless of mode

### Seek Bar
- `DualHandleSeekBar` — start time + end duration
- Enabled for new projects, disabled when existing score loaded

### Crop Ratio Row
- QDoubleSpinBox (0.0–1.0, step 0.01, default **0.32**)
- Shows "(was X%)" label when existing score loaded
- "Set as Default" button saves to config
- In existing mode, changing spinbox calls `GuiApi.reapply_crop(ratio)` for live preview

### Output PDF
- QLineEdit for PDF filename (defaults to project name)

### Progress & Log
- QProgressBar (0–100%)
- QTextEdit (read-only, max 140px)

### Action Button (state-driven)

| State | Button text | Behavior |
|-------|-------------|----------|
| New project + video ready | **Start Extraction** | Full pipeline |
| Existing score loaded | **Regenerate PDF** | Re-crop + generate PDF |
| Busy | **Extracting… (45%)** | Disabled |
| PDF complete | **✓ Open PDF** | `os.startfile(output_path)` |

### Cancel Button
- Enabled only during extraction
- Calls `GuiApi.cancel_extraction()`

---

## Tab 2: Config

**Basic Settings** (inline):
- Crop ratio (0.0–1.0, step 0.01, default 0.32)
- Page change sensitivity (0.0–1.0, step 0.01, default 0.96)
- Min seconds between captures (0.0–60.0, step 0.5, default 3.0)
- OCR confidence (0–100, default 40)

**Advanced Settings** (QGroupBox):
- Frame check interval, Top analysis ratio, A/B capture delays, B overlay width
- Deduplication: Duplicate top ratio, Pixel/row similarity, Row coverage
- OCR horizontal ratio, Crop top offset, Blank content std threshold
- Bar min diff threshold, Bar overlay offset

**Debug mode checkbox**

All changes auto-apply via `GuiApi.update_config()`.

---

## Thread Bridge

```python
class ExtractionSignals(QObject):
    progress      = pyqtSignal(str, float, str)
    page_detected = pyqtSignal(int, bytes)
    log           = pyqtSignal(str)
    error         = pyqtSignal(str)
    completed     = pyqtSignal(int)
    cancelled     = pyqtSignal()
    download_done = pyqtSignal(str)     # YouTube download finished
```

---

## Packaging

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name ScoreExtractor --upx-dir="C:\upx" app_gui.py
```

- `--onefile` produces single `.exe`
- `--windowed` suppresses console
- UPX reduces size 30–50%
- Expected size: ~150MB