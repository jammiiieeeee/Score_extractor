# CLI Interface Specification

## Command

```
python main.py [input_video_or_url] [options]
```

No subcommands — single flat argument list.

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `input` | positional, optional | `None` | Path to input video file or YouTube URL |
| `-o, --output` | str | input name + `.pdf` | Output PDF path |
| `--output-dir` | str | — | Output folder for organized score (`<score_name>/photos/` etc.) |
| `--score-name` | str | video filename stem or YouTube title | Score name |
| `-c, --config` | str | `config.json` | Path to config.json |
| `-d, --debug` | flag | `False` | Enable debug mode (keep debug artifacts) |
| `--no-ocr` | flag | `False` | Skip OCR, force visual-only dedup |
| `--start-time` | float | `2.0` | Jump to this time (seconds), capture first page immediately |
| `--end-offset` | float | `0.0` | Stop processing N seconds before video end (0 = off) |
| `--crop-ratio` | float | — | Override crop ratio for PDF output |
| `--from-dir` | str | — | Regenerate PDF from existing score directory (skips video extraction) |
| `--yt-url` | str | — | YouTube URL to download before extraction |
| `--quality` | choice | `1080p` | Video quality for YouTube download: 1080p, 720p, 480p, 360p |

## Two Modes

### Extraction Mode (default)
```
python main.py input_video.mp4 --output-dir ./output --score-name "Sonata"
```
1. Opens video, initializes OCR (unless `--no-ocr`)
2. Runs `ExtractScoreUseCase.execute()`
3. Hands the extracted pages (image + measured boundary row) to the PDF builder
4. Calls `PdfService.create_pdf()` — the shared crop rule crops each page
5. Debug artifacts saved to `<output_dir>/debug/` if `--debug`

### Regeneration Mode (`--from-dir`)
```
python main.py --from-dir ./output/Sonata/ -o sonata.pdf
```
1. Reads the score with `read_saved_score()` - the page images, the page
   records written with them, and the crop the score was saved with
2. The config is put on the saved crop, so the score is read the way it was
   cropped (`--crop-ratio` still wins over the saved ratio)
3. Calls `PdfService.create_pdf()` with those pages - the same crop rule the
   GUI uses, so the PDF keeps the bottom of every page
4. Default output: `<dir>/<dir_name>.pdf`

The GUI reads a score through the same `read_saved_score()`, so the command
line and the GUI produce the same pages, cropped the same way.

## YouTube Download

YouTube URLs are auto-detected from the `input` positional argument or can be specified explicitly with `--yt-url`.

### Auto-detection
```
python main.py "https://youtube.com/watch?v=d8TZhL7dvao" --start-time 2 --end-offset 10
```

### Explicit flag
```
python main.py --yt-url "https://youtube.com/watch?v=d8TZhL7dvao" --start-time 2 --end-offset 10
```

### Quality options
- `--quality 1080p` (default) — downloads video-only stream, no ffmpeg needed
- `--quality 720p` — lower resolution, faster download
- `--quality 480p` — even lower resolution
- `--quality 360p` — includes audio (combined format)

## Console Output

- Plain `print()` — no Rich, no logging module
- Progress: `\r  [{pct:5.1f}%] {msg}` via `on_progress` callback
- Extraction complete: prints page count
- PDF generated: prints output path
- Errors: prints traceback + error message, exits with code 1

## Exit Codes

- `0`: Success (implicit — no explicit `sys.exit(0)`)
- `1`: Critical error (file not found, directory not found, extraction failed)