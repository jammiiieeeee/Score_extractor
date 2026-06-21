# PRD: PyQt6 Graphical User Interface for Piano Score Video-to-PDF Extractor

## Problem Statement

The piano score video-to-PDF extractor is currently accessible only through a CLI (`python main.py`), which requires the user to memorise flags, edit JSON config files by hand, and manually manage extraction sandboxes. Non-technical users — pianists, teachers, and students who want to convert their performance videos into printable sheet music — cannot use the tool without command-line familiarity. The CLI also provides no visual feedback: no video preview, no crop preview, no gallery to review extracted pages before PDF generation, and no way to see progress during extraction.

## Solution

A PyQt6 desktop GUI that exposes all CLI capabilities through an intuitive four-tab window:

1. **Extract tab** — paste a YouTube URL or browse for a local video file; preview the video with a draggable crop line and a dual-handle seek bar for start/end time; one-click "Extract & Generate PDF"
2. **Gallery tab** — review extracted pages as thumbnails, reorder, delete unwanted pages, double-click for full preview
3. **Export tab** — browse sandboxes from previous extractions, regenerate PDFs with different settings, or rename sandboxes to the original video title
4. **Config tab** — full settings panel (basic + advanced) in a scrollable layout, debug mode checkbox

The GUI runs as a single-file Windows executable (~150 MB) built with PyInstaller `--onefile`.

## User Stories

1. As a piano student, I want to paste a YouTube URL and download the video automatically, so that I can extract sheet music from any online performance without downloading files manually.

2. As a piano teacher, I want to select a local video file with a native file browser, so that I can process my own recordings.

3. As a user, I want clear visual feedback when a playlist URL is pasted ("Only the first video will be downloaded. Do you want to proceed?"), so that I am not surprised when only one video is processed.

4. As a user, I want to see the video frame immediately after selecting a file, so that I can confirm I have the right video before configuring settings.

5. As a user, I want to drag a horizontal crop line on the preview to set the crop ratio, so that I can visually exclude non-score regions (hands, piano body, background).

6. As a user, I want the crop line to show a grip indicator (three horizontal ridges ≡) so that I know it is draggable.

7. As a user, I want to set the crop ratio as a default so that subsequent videos automatically use my preferred crop.

8. As a user, I want to drag two handles on a single seek bar to set the start time and end duration, so that I can trim the video to the score portion without switching tabs.

9. As a user, I want the start-time capture enabled by default and the end-duration disabled by default, since most videos only need trimming from the beginning.

10. As a user, I want to see the time readout update live as I drag the seek handles, so that I know the exact timestamp.

11. As a user, I want the progress bar and log panel to show extraction progress, so that I know the tool is working and how far along it is.

12. As a user, I want a "Cancel" button that stops extraction cleanly, so that I can abort a misconfigured run.

13. As a user, I want to see extracted pages as thumbnails in a gallery, so that I can review and select which pages to include in the PDF.

14. As a user, I want to reorder gallery pages by moving them up or down, so that the final PDF page order matches my preference.

15. As a user, I want to delete unwanted pages from the gallery, so that low-quality or duplicate pages are excluded from the PDF.

16. As a user, I want to double-click a thumbnail to see a full-resolution preview in a dialog, so that I can inspect page quality closely.

17. As a user, I want extraction to automatically generate the PDF when complete, so that I get a finished PDF with one click.

18. As a user, I want the output PDF path to default to the same name/location as the video, so that I don't have to type a filename.

19. As a user, I want to customise the PDF title separately from the filename, auto-populated from the video title, so that the PDF metadata is meaningful.

20. As a user, I want to regenerate a PDF from a sandbox with different settings, so that I can tweak output without re-extracting.

21. As a user, I want to manage sandboxes (list, load, delete) from the Export tab, so that I can revisit past extractions.

22. As a user, I want to configure all 20 extraction parameters in one place, so that I can fine-tune SSIM thresholds, OCR confidence, and other settings.

23. As a user, I want the config tab wrapped in a scroll area so that all fields are accessible on any screen size.

24. As a user, I want a debug mode that opens the temp sandbox folder on completion, so that I can inspect intermediate files when troubleshooting.

25. As a user, I want the window to have a warm, paper-toned colour scheme (ink on cream paper), so that it feels inviting for a music-related tool.

26. As a beginner, I want the Extract tab to open by default, since that is where I start every session.

27. As a user, I want the "Save PDF to" path to be read-only in the Export tab (just a display), so that I don't accidentally change it while reviewing.

28. As a user, I want a success dialog with an "Open PDF" button after generation, so that I can open the result immediately.

29. As an advanced user, I want keyboard-accessible controls and standard system font sizes so that the GUI is accessible.

30. As a user, I want YouTube downloads to show a monotonic progress indicator (not cycling 0→100% per fragment) so that I can estimate remaining time.

## Implementation Decisions

### Architecture

- **Clean Architecture layering preserved**: `app_gui.py` (presentation) → `gui_bridge.py` (signal relay) → `src/api/gui_api.py` (application API) → domain/infrastructure layers unchanged.
- **Thread bridge pattern**: `ExtractionSignals(QObject)` with 7 `pyqtSignal`s (`progress`, `page_detected`, `log`, `error`, `completed`, `cancelled`, `download_done`) relays background-thread callbacks to the Qt main thread via `pyqtSignal`. The `.wire(api)` method maps GuiApi callbacks to signals in a single call.
- **Three thread types**: `_download_thread`, `_extraction_thread`, `_pdf_thread` managed by GuiApi. `is_busy()` checks all three. Thread cancellation via `_cancel_flag`.

### GUI Layout

- **Four-tab QTabWidget**: Extract (index 0, opens by default), Gallery (1), Export (2), Config (3).
- **Extract tab layout** (top to bottom):
  1. Source toggle: QRadioButton (Local file / YouTube URL)
  2. Grid row: Video file picker or YouTube URL + browse/download
  3. Grid row: PDF title (auto-populated from video filename)
  4. Grid row: Save PDF to path + browse button
  5. CropPreviewWidget (single video preview, stretch=1)
  6. DualHandleSeekBar (combined start/end seek bar with two draggable handle circles)
  7. Crop default label + "Set as Default" button row
  8. QProgressBar
  9. QTextEdit log (max 140px)
  10. Action bar: Start Extraction + Cancel buttons
- **Config tab**: QScrollArea wrapping a QWidget with 5 basic fields + Advanced QGroupBox with 12 fields + debug checkbox. Uses QGridLayout with fixed vertical policy to prevent label squeezing.

### DualHandleSeekBar Design

- Custom `QWidget` with `paintEvent` drawing: a horizontal groove line, highlighted range band between handles (when both enabled), and two filled circle handles outlined in white.
- **Semantics**: `_start` and `_end` as fractions (0.0–1.0) of total duration. Clamping ensures `0 ≤ start ≤ end ≤ 1.0`.
- **Controls row below groove**: checkbox for start capture + time label, stretch spacer, checkbox for end duration + time label + total duration label.
- **Signals**: `seek_changed(float)` emits the timestamp of whichever handle was dragged (used to update the crop-preview frame for visual feedback).
- **Public API**: `set_duration(secs)`, `set_start(ts)`, `set_end(ts)`, `get_start()` → `-1.0` if disabled else timestamp, `get_end()` → `0.0` if disabled else timestamp.

### YouTube Download

- Toggle between Local file (QFileDialog) and YouTube URL (direct input + Download button).
- Download uses `yt-dlp` with `format='best[height<=1080]'`, `noplaylist=True`, `playlistend=1`.
- Progress hook uses a `finished_logged` flag to emit "Download finished, processing..." only once.
- Downloaded file saved to `<workspace>/debug/yt_dl/`, then the sandbox is renamed to the YouTube video title.
- Playlist detection via `urllib.parse.parse_qs` — shows QMessageBox.question warning before proceeding.
- On download completion: auto-populates PDF title from the video filename stem, enables start button.

### CropPreviewWidget

- Custom `QWidget` with `paintEvent`: scales video frame to fit widget, draws semi-transparent red overlay from top to crop line, draws red crop line, draws three horizontal grip ridges (≡) at the line center.
- Mouse interaction: `mousePressEvent` detects proximity to crop line (<12px), `mouseMoveEvent` drags line up/down, `mouseReleaseEvent` stops drag.
- Emits `crop_ratio_changed(float)` on drag (0.05–0.95 clamping).
- "Set as Default" button writes ratio to `GuiApi.update_config({"default_crop_ratio": ratio})`.

### Styling

- **Palette**: warm cream background (`#f5f0e8`), white cards (`#ffffff`), deep navy text (`#1a1a2e`), muted slate (`#6b6b8d`), vintage red accent (`#c0392b`).
- **Checkboxes**: custom 18×18 PNG checkmark generated at startup via `QPainter` and stored in temp directory. Path converted to forward slashes for Qt stylesheet `url()` compatibility. Inline CSS: `QCheckBox::indicator:checked { background: ACCENT; border-color: ACCENT; image: url(path); }`.
- **Button padding**: secondary buttons use `padding: 8px 14px` to prevent truncation of "Browse…".

### PDF Generation

- Auto-triggered after extraction completes.
- Title passed via `GuiApi.generate_pdf(output_path, title=title_or_none)`.
- Success dialog has "Open PDF" button that calls `os.startfile(output_path)`.
- Sandbox always renamed to video filename after extraction (not just in debug mode).

### Debug Mode

- Controlled by checkbox in Config → Advanced settings.
- Stored as `_debug_mode` on GuiApi.
- On completion, `GuiApi.open_sandbox_folder()` opens Windows Explorer to the sandbox directory (executed on main thread in the completion callback).

### Packaging

- **Build script**: `build_exe.ps1` — PyInstaller with `--onefile --windowed --name ScoreExtractor --upx-dir`.
- Target: single ~150 MB .exe.

## Testing Decisions

### Seams

The existing test suite (`tests/test_api.py`) tests the **GuiApi** layer — the highest feasible seam for automated testing. All 28 public API methods are covered via a custom `test()` decorator runner (not pytest), using synthetic images and mock callbacks.

| Seam | Layer | Testing approach | Existing coverage |
|------|-------|------------------|-------------------|
| GuiApi callbacks | Application API | Unit tests with synthetic frames, callback assertions | 33 tests covering all 28 methods |
| ExtractionSignals | Bridge | Wire to mocks, verify signal emission (manual / future) | Not covered |
| GUI widgets | Presentation | Manual / QTest (future) | Not covered |

### What makes a good test

- Test **external behaviour**, not internal implementation details.
- Prefer testing via `GuiApi` callbacks (`set_on_log`, `set_on_progress`, `set_on_completed`, etc.) rather than inspecting widget state.
- New GUI features should add tests at the `GuiApi` seam when possible (e.g., test that `download_youtube` with a playlist URL calls `set_on_log` with expected warnings, test that `set_on_download_completed` fires with the correct path).

### Prior art

- `tests/test_api.py` provides the pattern: a `test(name)` decorator wraps each function, `SkipTest` handles conditional skips, and `_find_test_video()` provides a real video file when available.
- The `make_test_image()` and `make_test_image_ndarray()` helpers create synthetic frames for page/dedup tests.

### Future GUI testing

- `CropPreviewWidget` and `DualHandleSeekBar` could be tested by installing them in a `QMainWindow`, simulating mouse events via `QTest.mousePress/Move/Release`, and reading the emitted signals or internal state.
- The thread bridge (`ExtractionSignals`) can be tested by calling `.wire()` with a mock GuiApi and verifying signal emission.
- Manual testing is currently required for the full extraction flow (real video file or YouTube URL).

## Out of Scope

- **Command-line interface improvements**: the existing CLI (`main.py`) is unchanged.
- **Multi-track extraction**: only single-video → PDF extraction; no batch/multi-video workflows.
- **Cloud storage / sharing**: no upload, no cloud sync, no email/share features.
- **Mobile / web version**: Windows desktop only.
- **Video editing beyond crop and trim**: no frame-by-frame editing, no audio processing, no effects.
- **Auto page detection quality improvement**: the SSIM-based deduplication algorithm is unchanged; this PRD covers only the GUI surface.
- **Translation / i18n**: GUI text is English-only.
- **Dark mode / theme switching**: single palette (ink-on-cream-paper).
- **OCR training / custom model loading**: PaddleOCR is used as-is; no model management UI.
- **Automatic updates / version checking**: no update mechanism.

## Further Notes

- **Environment variable**: `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=1` must be set or PaddleOCR hangs on startup checking model hosts.
- **CI tests**: `QT_QPA_PLATFORM=offscreen` env var is needed for headless test runs.
- **GitHub**: the repo has 4 commits on `main` and is published at `https://github.com/jammiiieeeee/Score_extractor`.
- **PyQt6 imports**: `QSize` lives in `PyQt6.QtCore` (separate from `Qt` namespace). All widgets are imported explicitly from `PyQt6.QtWidgets`.
- **`tests/test_api.py`**: this file is a standalone script (not a pytest suite). It uses a custom `test()` decorator. Adding `__test__ = False` prevents pytest collection errors.
