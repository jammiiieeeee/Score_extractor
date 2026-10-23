# Agent Instructions

## Orientation

- **Repo map: `docs/agents/repo-map.md`** — it is already loaded in context.
  Use it to find files; do **not** Glob / Grep / `ls` / `tree` to orient yourself.
- The map lists every module, entry point, test group and tool. Read the one file
  it names, then work.
- If the map is wrong or incomplete, fix it in the same session — see its
  [Maintenance](docs/agents/repo-map.md#maintenance) section. That is what
  keeps the next session from having to rescan.

## Package Manager
- Use **pip**: `pip install -r requirements.txt`

## Commands
| Task | Command |
|------|---------|
| Run GUI | `python app_gui.py` |
| Run CLI | `python main.py <video_path>` |
| Run all tests | `python -m pytest tests/ -v -m "not slow"` |
| Run all tests (incl. slow/OCR) | `python -m pytest tests/ -v` |
| Run single test | `python -m pytest tests/test_api.py -v -k test_name` |
| Verify a 1080p extraction end to end | `python tools/verify_1080p.py <video>` |

## Architecture
- Clean Architecture: `src/api` → `src/application` → `src/domain` ← `src/infrastructure`
- Entry points: `app_gui.py` (PyQt6 GUI), `main.py` (CLI)
- Repo map: `docs/agents/repo-map.md` (loaded automatically, keep it current)
- Module specs: `.opencode/instructions/` — the map's Spec column names the right one

## Testing
- Default test run **skips slow tests** (`-m "not slow"`) — this avoids PaddleOCR import timeouts unless changes touch OCR code
- Run the full suite (including slow/OCR) only when working on OCR-related changes or before committing

## Communication
- The user prefers **simple explanations**. Write in plain language with short sentences, and avoid jargon dumps.
- Lead with *what it does* and *why it matters*; keep file paths, line numbers and code as references, not as the explanation itself.
- Use a diagram (ASCII or Markdown) to show structure, call flow or information flow instead of describing it in prose.
- When a term has to be technical, define it in one line the first time it appears.
- Keep summaries short: what changed, what it affects, what happens next.

## Key Conventions
- Domain models in `src/domain/models.py`, config in `src/domain/value_objects/config.py`
- Services implement interfaces from `src/domain/interfaces.py`
- Extraction logic lives in `src/application/use_cases.py` and `extraction_components.py`
- GUI orchestrator: `src/api/gui_api.py` — thin layer delegating to sub-modules
- UI design tokens and rules: `DESIGN.md`
- Output structure: `output/<score_name>/photos/` for kept page images, `candidates/` for duplicate candidates, `debug/` for artifacts
- Windows-only: paths use backslashes, ffmpeg detected via WinGet fallback

## Commits
- **Never commit without explicit permission.** Wait for the user to say "commit" (or similar). Do not commit after tests pass on your own initiative. If unsure, ask first.
- When permitted, AI commits MUST include:
```
Co-Authored-By: opencode <noreply@opencode.ai>
```

## Extraction Rules
- When the user asks to extract a score from a YouTube video, **always use at least 1080p** (`bestvideo[height<=1080]`) for the scan/download. Lower resolutions (360p/480p/720p) produce blurry bar profiles and unreliable merge cutoffs.
- **Video-only only**: use `bestvideo[...]` selectors (no `+bestaudio`, no combined `best`), so downloads carry no audio stream. The scan format is also video-only (e.g. `bestvideo[height<=640]`).
- Use `--start-time 2.0` to skip the camera settling at the beginning.
- Enable debug mode (`--debug` or `debug=True`) on first runs to verify bar profile alignment.
- The output PDF should contain only clean score pages — blank frames, end credits, and duplicate pages are rejected automatically.

## Agent skills

### Issue tracker
Issues live as GitHub issues on this repo. External PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels
Five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs
Glossary in `CONTEXT.md` and decisions in `docs/adr/` (when present; create lazily). See `docs/agents/domain.md`.
