# System & Lifecycle Specification

## File System Layout

Output structure for each score:
```
output/<score_name>/
├── photos/
│   ├── page_001_merged.png
│   ├── page_002_merged.png
│   └── ...
├── candidates/               # duplicate candidates, when detected
│   ├── page_001_merged.png
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

### metadata.json

```json
{
  "score_name": "My Score",
  "crop_ratio": 0.32,
  "boundary_mode": "auto",
  "boundary_offset_px": 0,
  "page_count": 3,
  "extraction_date": "2026-01-01T12:00:00",
  "pages": [
    {"attempt": 1, "boundary_row": 197, "status": "keep"},
    {"attempt": 2, "boundary_row": 211, "status": "keep"},
    {"attempt": 4, "boundary_row": null, "status": "keep"}
  ]
}
```

`pages` holds one record per page - the attempt that produced it, the
boundary row measured on it, and its status - and is always written, even
when no page had a row.  Changing a page's status rewrites this file
straight away; no photo or candidate file is removed by a status change.  A
score saved before this format carries `page_boundary_rows` (a bare list of
rows) instead; it is still read, as a fallback, with every page kept.

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