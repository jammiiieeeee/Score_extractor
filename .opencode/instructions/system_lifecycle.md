# System & Lifecycle Specification

## File System Layout

Output structure for each score:
```
output/<score_name>/
├── photos/
│   ├── page_001_merged.png
│   ├── page_002_merged.png
│   └── ...
├── debug/                    # only when debug=True
│   ├── extraction.log
│   ├── page_001_A.png
│   ├── page_001_B.png
│   ├── bar_profile_page_001.txt
│   └── bar_profile_page_001.png
├── <score_name>.pdf
└── metadata.json
```

## Temporary Files

- **No UUID sandbox** — files go directly into the score directory
- Debug artifacts are written to `<output_dir>/debug/`
- On cancellation, the entire score directory is removed via `shutil.rmtree(score_dir, ignore_errors=True)`

## Windows Unicode Safety

- All paths handled via Python `pathlib.Path` (Unicode-aware)
- `cv2.imencode` + `.tofile()` for writing images with non-ASCII paths
- `os.startfile()` for opening PDFs (Windows-only)

## Resource Cleanup

- `VideoService.close()` — releases `cv2.VideoCapture`
- `OcrService` — no explicit cleanup needed (PaddleOCR handles internally)
- `PdfService` — ReportLab closes file handles after `create_pdf()`
- `GuiApi.cleanup()` — calls `close_video()` + `clear_pages()`

## Error Handling

- Extraction thread: caught in `_run_extraction()`, emitted via `on_error`
- PDF thread: caught in `_run_generate_pdf()`, emitted via `on_error`
- Download thread: caught in `_run_youtube_download()`, emitted via `on_error`
- CLI: caught in `main()`, prints traceback, exits with code 1

## Exit Codes (CLI)

- `0`: Success
- `1`: Critical error (file not found, extraction failed, PDF generation failed)

## Thread Safety

- Three independent background threads: extraction, PDF, download
- `is_busy()` checks all three for `.is_alive()`
- `start_extraction()` / `generate_pdf()` / `download_youtube()` raise `RuntimeError` if already busy
- Cancellation: `_cancel_flag` boolean, checked at each iteration by `FrameStepper.step()`