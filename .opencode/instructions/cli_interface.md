# CLI Interface Specification

## Command

```
python main.py [input_video] [options]
```

No subcommands — single flat argument list.

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `input` | positional, optional | `None` | Path to input video file |
| `-o, --output` | str | input name + `.pdf` | Output PDF path |
| `--output-dir` | str | — | Output folder for organized score (`<score_name>/photos/` etc.) |
| `--score-name` | str | video filename stem | Score name |
| `-c, --config` | str | `config.json` | Path to config.json |
| `-d, --debug` | flag | `False` | Enable debug mode (keep debug artifacts) |
| `--no-ocr` | flag | `False` | Skip OCR, force visual-only dedup |
| `--start-time` | float | `2.0` | Jump to this time (seconds), capture first page immediately |
| `--duration` | float | `0.0` | Stop after N seconds (0 = off) |
| `--crop-ratio` | float | — | Override crop ratio for PDF output |
| `--from-dir` | str | — | Regenerate PDF from existing score directory (skips video extraction) |

## Two Modes

### Extraction Mode (default)
```
python main.py input_video.mp4 --output-dir ./output --score-name "Sonata"
```
1. Opens video, initializes OCR (unless `--no-ocr`)
2. Runs `ExtractScoreUseCase.execute()`
3. Explicitly crops each page using `config.crop_top_offset` and `config.default_crop_ratio`
4. Calls `PdfService.create_pdf()` with pre-cropped images
5. Debug artifacts saved to `<output_dir>/debug/` if `--debug`

### Regeneration Mode (`--from-dir`)
```
python main.py --from-dir ./output/Sonata/photos/ -o sonata.pdf
```
1. Loads page images from `<dir>/` via `FileService.load_page_images()`
2. Calls `PdfService.create_pdf()` directly (no cropping — images already cropped)
3. Default output: `<dir>/<dir_name>.pdf`

## Console Output

- Plain `print()` — no Rich, no logging module
- Progress: `\r  [{pct:5.1f}%] {msg}` via `on_progress` callback
- Extraction complete: prints page count
- PDF generated: prints output path
- Errors: prints traceback + error message, exits with code 1

## Exit Codes

- `0`: Success (implicit — no explicit `sys.exit(0)`)
- `1`: Critical error (file not found, directory not found, extraction failed)