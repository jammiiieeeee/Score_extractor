# Agent Instructions

## Package Manager
- Use **pip**: `pip install -r requirements.txt`

## Commands
| Task | Command |
|------|---------|
| Run GUI | `python app_gui.py` |
| Run CLI | `python main.py <video_path>` |
| Run all tests | `python -m pytest tests/ -v` |
| Run single test | `python -m pytest tests/test_api.py -v -k test_name` |

## Architecture
- Clean Architecture: `src/api` → `src/application` → `src/domain` ← `src/infrastructure`
- Entry points: `app_gui.py` (PyQt6 GUI), `main.py` (CLI)
- Specs: `.opencode/instructions/master_map.md`

## Key Conventions
- Domain models in `src/domain/models.py`, config in `src/domain/value_objects/config.py`
- Services implement interfaces from `src/domain/interfaces.py`
- Extraction logic lives in `src/application/use_cases.py` and `extraction_components.py`
- GUI orchestrator: `src/api/gui_api.py` — thin layer delegating to sub-modules
- Output structure: `output/<score_name>/photos/` for page images, `debug/` for artifacts
- Windows-only: paths use backslashes, ffmpeg detected via WinGet fallback

## Commit Attribution
AI commits MUST include:
```
Co-Authored-By: opencode <noreply@opencode.ai>
```

## Extraction Rules
- When the user asks to extract a score from a YouTube video, **always use at least 1080p** (`bestvideo[height<=1080]`) for the scan/download. Lower resolutions (360p/480p/720p) produce blurry bar profiles and unreliable merge cutoffs.
- **Video-only only**: use `bestvideo[...]` selectors (no `+bestaudio`, no combined `best`), so downloads carry no audio stream. The scan format is also video-only (e.g. `bestvideo[height<=640]`).
- Use `--start-time 2.0` to skip the camera settling at the beginning.
- Enable debug mode (`--debug` or `debug=True`) on first runs to verify bar profile alignment.
- The output PDF should contain only clean score pages — blank frames, end credits, and duplicate pages are rejected automatically.
