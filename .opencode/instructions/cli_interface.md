# CLI Interface Specification

## Primary Command
`python main.py extract <input_video_path> [options]`

## Arguments & Flags
- `input_video_path`: Required. Path to the source video (may contain non-ASCII characters).
- `-o, --output`: Optional. Final PDF path. Defaults to input filename with `.pdf` extension.
- `-c, --config`: Optional. Path to a custom `config.json`.
- `-d, --debug`: Optional flag. If set:
    - Retains the UUID temporary folder.
    - Saves `ocr_result/` containing debug images with bounding boxes.
- `--no-ocr`: Optional flag. Skips OCR step entirely, forcing fallback to visual-only deduplication.

## Console Feedback
- **Rich Integration**: Use `rich.progress` for the main video processing loop.
- **Logging**:
    - `INFO`: Standard status updates.
    - `WARNING`: OCR failures or potential duplicate misidentifications.
    - `ERROR`: Critical failures (File not found, OpenCV crash).

## Exit Codes
- `0`: Success.
- `1`: Critical Error (Source not found).
- `2`: Resource Error (OCR Engine failure and user chose not to continue).
