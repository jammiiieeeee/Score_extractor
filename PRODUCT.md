# Product

<!-- impeccable:product-schema 1 -->

## Platform

windows

## Users

Primary users are music teachers and students. A teacher records a video of a piano score as pages are turned (either a physical score filmed on a music stand or a digital score in a scrolling/PDF viewer), and the tool extracts each page turn into individual page images compiled into a printable PDF. Secondary users are pianists and sheet music archivists with the same workflow.

The situation is a single-user desktop session: load a video, preview and adjust crop, detect page turns, review extracted pages, and export a PDF.

## Product Purpose

Score Extractor converts a video of page-turning sheet music into a clean, printable PDF of individual pages. It eliminates the manual work of taking screenshots, cropping, and assembling pages from a video recording.

## Positioning

Unlike generic video-to-frame extraction or manual screenshotting, this tool has a purpose-built pipeline: SSIM-based change detection finds page-turn moments precisely, an A/B capture system with bar-overlay removal produces clean merged pages, and a three-pass deduplication pipeline (global pixel, row-by-row, OCR-verified) eliminates near-duplicates from slow page turns. The output is a print-ready PDF with correctly ordered, cropped, and deduplicated pages — no manual cleanup required.

## Operating Context

- Windows desktop application (PyQt6 GUI + CLI fallback)
- Video sources: local files (.mp4, .avi, .mkv, .mov) or YouTube downloads (via yt-dlp)
- ffmpeg required for frame seeking (detected via WinGet fallback on Windows)
- Output: `output/<score_name>/photos/` (page images), `output/<score_name>/<score_name>.pdf` (compiled PDF)
- Debug artifacts in `debug/` subdirectory when debug mode is enabled
- OCR is optional (PaddleOCR) and disabled by default

## Capabilities and Constraints

**Capabilities:**
- Frame-accurate page turn detection via SSIM change detection
- Adjustable crop region (top portion of frame retained)
- A/B frame capture with configurable delays and bar-overlay merging
- Three-pass deduplication: global pixel similarity, row-by-row similarity, OCR text comparison
- Dual-handle seek bar for trimming start/end of video
- YouTube download with quality presets (360p–1080p)
- PDF generation with crop reapplied (regenerate with different crop without re-extracting)
- Debug mode with diagnostic HTML report
- Preview seeker using ffmpeg with OpenCV fallback

**Constraints:**
- Windows-only (WinGet-based ffmpeg detection, backslash paths)
- PDF is the only output format
- OCR requires PaddleOCR (adds startup time; off by default)
- Single-video processing per session (no batch mode)
- GUI requires Python + Qt runtime

## Brand Commitments

- Name: "Score Extractor"
- No color, typography, or visual identity commitments beyond those implemented in code (ebony-and-brass dark theme)
- Open-source (no proprietary assets or licensing claims)

## Evidence on Hand

- Complete implementation in `app_gui.py` (PyQt6) and `main.py` (CLI)
- 374+ passing pytest tests covering domain logic, API, and integration
- Synthetic video test fixtures for extraction verification
- Reference learning materials in `reference/` and `learning-records/`
- AGENTS.md documents conventions and commands

## Product Principles

1. **Precision over convenience.** Every extraction parameter is tunable (delays, thresholds, ratios) because score quality depends on the specific video. Sensible defaults exist, but power users can dial in exact behavior.
2. **Output quality first.** The deduplication pipeline and bar-overlay removal exist solely to produce a PDF that looks like it was scanned, not extracted from video. Near-duplicates and seam artifacts are the primary quality failures this tool exists to prevent.
3. **Single-player workflow.** One video, one score, one PDF per session. The UI is optimized for a focused extraction pass, not batch or background processing.
4. **Windows-native expectations.** The app follows desktop conventions (Qt widgets, file dialogs, status bars, tabbed settings) rather than web or cross-platform patterns. Users expect standard Windows desktop behavior.
5. **Progressive disclosure.** Basic extraction needs only a video file and project name. Advanced tuning is available in the Config tab. The crop preview with draggable overlay makes the most critical adjustment visual and interactive.

## Accessibility & Inclusion

- The interface is a standard Qt desktop app (not web-based)
- No specific accessibility audit has been performed
- The dark theme (ebony-and-brass) provides moderate contrast; no WCAG compliance target has been established
