# Repo Map

> **This file is auto-loaded into every agent session** (via `opencode.json`).
> Read it before doing anything else. Do **not** run Glob / Grep / `ls` / `tree`
> to orient yourself — the answer is below.
>
> If something here is wrong or missing, **fix it in the same session** and add
> a line to [Recently changed](#recently-changed). See [Maintenance](#maintenance).

Last verified: 2026-10-23 at `a12123c`.

## What this is

Piano-score video → PDF extractor. Clean Architecture:

```
src/api  →  src/application  →  src/domain  ←  src/infrastructure
```

`domain` owns the rules and interfaces. `infrastructure` implements those
interfaces (OpenCV, PaddleOCR, ReportLab, yt-dlp). Nothing points inward.

## Layout

| Path | Purpose |
| :--- | :--- |
| `src/api/` | GUI-facing Python API (`GuiApi`) |
| `src/application/` | Use cases + extraction pipeline wiring |
| `src/domain/` | Models, interfaces, dedupe/crop/bar-profile rules |
| `src/domain/value_objects/` | `ScoreConfig` and other value objects |
| `src/infrastructure/` | OpenCV, PaddleOCR, ReportLab, yt-dlp adapters |
| `tests/` | Pytest suite (default run skips `-m slow`) |
| `tools/` | One-off dev scripts, benchmarks, test media |
| `scripts/` | Windows packaging (PyInstaller, shortcut) |
| `.opencode/instructions/` | Module specs — one per module; the Spec column below names it |
| `.opencode/plugins/` | `map-guard.js` — nudges the agent when a new file is missing from this map |
| `.agents/skills/`, `docs/agents/` | Installed agent skills / agent config: this map, issue tracker, triage, domain docs |
| `learning-records/`, `lessons/`, `reference/`, `archive/`, `.impeccable/` | Notes, generated lessons, arch refs, old test videos, UI critique state (not app code) |
| `.github/workflows/` | CI: `test.yml` runs pytest |
| root | `AGENTS.md`, `opencode.json`, `requirements.txt`, `pytest.ini`, `PRODUCT.md`, `DESIGN.md`, `CHANGELOG.md`, `RESOURCES.md` |

## Module table

| File | Owns | Spec |
| :--- | :--- | :--- |
| `src/api/gui_api.py` | `GuiApi` public surface + `VideoInfo` / `ExtractionState` / `ScoreInfo`; thin, delegates to application layer | `gui_api.md` |
| `src/application/use_cases.py` | `ExtractScoreUseCase`, `GeneratePdfUseCase`, `ExtractRequest`, `ExtractResult` — the pipeline | `application_orchestration.md` |
| `src/application/extraction_components.py` | `FrameStepper`, `PageCommitter`, `BarProfilePlotter`, `_PendingCommit`, `_Analysis` | `application_orchestration.md` |
| `src/application/saved_score.py` | `SavedScore`, `read_metadata`, `write_metadata`, `save_page_status`, `apply_saved_crop`, `pages_from_records`, `read_saved_score` — reopening a past run | `application_orchestration.md` |
| `src/domain/models.py` | `Page`, `PageCandidate`, `PageState`, `PageStatus`, `Frame`, `MergeResult`, `PageManifestEntry` | `domain_logic.md` |
| `src/domain/interfaces.py` | `IVideoService`, `IFileService`, `IOcrService`, `IPdfService`, `_NoopOcrService` | `domain_logic.md` |
| `src/domain/value_objects/config.py` | `ScoreConfig` — every tunable | `domain_logic.md` |
| `src/domain/deduplication.py` | `Deduplicator` — OCR-first duplicate-page rejection | `domain_logic.md` |
| `src/domain/page_store.py` | `PageStore` — in-memory page collection + PNG/thumbnail cache (add, remove) | `domain_logic.md` |
| `src/domain/page_crop.py` | `crop_end_row`, `crop_page` — the one crop rule | `domain_logic.md` |
| `src/domain/boundary_detector.py` | `BoundaryDetector` — score/visualizer boundary | `infrastructure_video.md` |
| `src/domain/bar_profile_calibrator.py` | `BarProfileCalibrator` — adaptive min-diff threshold | `infrastructure_video.md` |
| `src/domain/bar_profile_service.py` | `BarProfileService` — shared bar-profile spike detection (dedupe + video) | `infrastructure_video.md` |
| `src/domain/bar_profile_guard.py` | `BarProfileGuard`, `BarProfileVerdict` — peak count + left-spike margin | `infrastructure_video.md` |
| `src/infrastructure/video_service.py` | `VideoService` — frame reads, SSIM change detection, A/B capture | `infrastructure_video.md` |
| `src/infrastructure/ocr_service.py` | `OcrService` — PaddleOCR init + regex filtering | `infrastructure_ocr_pdf.md` |
| `src/infrastructure/pdf_service.py` | `PdfService` — ReportLab page layout | `infrastructure_ocr_pdf.md` |
| `src/infrastructure/download_service.py` | `DownloadService`, `DownloadResult` — yt-dlp wrapper | — |
| `src/infrastructure/file_service.py` | `FileService` — output dirs, page image save/load/delete, saved-score listing | `system_lifecycle.md` |
| `src/infrastructure/diagnostics_service.py` | `generate_html_report` — debug charts from `page_manifest.json` + `extraction.log` | `system_lifecycle.md` |

## Entry points

| File | Role |
| :--- | :--- |
| `app_gui.py` | PyQt6 GUI. Imports `gui_bridge.ExtractionSignals` + `GuiApi` + `FileService`. |
| `gui_bridge.py` | `ExtractionSignals` — Qt signals between worker thread and widgets. |
| `main.py` | CLI. Wires `ScoreConfig` + infrastructure + use cases **directly** (no GUI). |
| `run_pipeline.py` | Scripted end-to-end run (download → extract → PDF → report) driving `GuiApi`. |

```
app_gui.py ──► gui_bridge ──► GuiApi ──► use_cases / extraction_components
                                           ├──► domain/*
                                           └──► infrastructure/* (through domain interfaces)
main.py ──────────────► use_cases (no GUI)
run_pipeline.py ──────► GuiApi (scripted)
```

## Where to start

| Task | Open |
| :--- | :--- |
| Change a pipeline step | `src/application/use_cases.py`, `extraction_components.py` |
| Change dedupe / crop / merge rules | `src/domain/` |
| Change frame or bar-profile detection | `src/infrastructure/video_service.py` + `src/domain/bar_profile_*` |
| Change OCR text rules | `src/infrastructure/ocr_service.py` |
| Change PDF layout | `src/infrastructure/pdf_service.py` |
| Change GUI behaviour | `src/api/gui_api.py` first, then `app_gui.py` widgets |
| Change a CLI flag | `main.py` |
| Add a tunable | `src/domain/value_objects/config.py` |
| Understand a design decision | The module's spec in `.opencode/instructions/` (ADRs when present) |

## Tests

| Area | Files |
| :--- | :--- |
| Fixtures | `tests/conftest.py`, `tests/fixtures/` (sample video, real page-36 bar profile) |
| Domain | `test_bar_profile_*`, `test_boundary_detector`, `test_deduplication`, `test_models`, `test_page_crop`, `test_page_store`, `test_page_lifecycle`, `test_config`, `test_double_crop_bug` |
| Application | `test_use_cases`, `test_saved_score_records`, `test_cli*`, `test_integration_e2e`, `test_page_committer`, `test_frame_stepper`, `test_bar_profile_plotter` |
| Infrastructure | `test_video_service`, `test_ocr_service`, `test_pdf_service`, `test_file_service`, `test_download_service`, `test_diagnostics_service` |
| API / GUI | `test_gui_api*`, `test_gui_workflow`, `test_gui_sanitize`, `test_gui_extraction_edge_cases`, `test_gui_callbacks_resilience`, `test_review_pages`, `test_preview_seeker`, `test_gui_visual`, `test_library_tab`, `test_projects_folder` |

## Tools and scripts

| File | Purpose |
| :--- | :--- |
| `tools/verify_1080p.py` | End-to-end 1080p extraction check |
| `tools/yt_dl_1080.py` | Download a 1080p video-only sample |
| `tools/plot_bar_profile.py`, `tools/plot_aggregate.py` | Bar-profile debug plots |
| `tools/bench_video_bottleneck.py`, `tools/bench_codec_matrix.py` | Benchmarks |
| `tools/_render_report.py`, `tools/_list_codecs.py` | Private scratch helpers |
| `tools/_test_*.mp4`, `tools/_bench_videos/` | Test media and benchmark output (not source) |
| `scripts/build_exe.ps1` | PyInstaller build |
| `scripts/create_desktop_shortcut.ps1` | Desktop shortcut |

## Recently changed

Max 10 lines, newest first. Older lines get dropped (git has the history).

- 2026-11-17 — opening a project with no video (or a missing one) clears the previous video and shows the project's first saved page, so switching projects in the Library actually updates the preview — `app_gui.py`, `tests/test_library_tab.py`
- 2026-11-17 — the projects folder moved from the Extract tab's Browse… button to Settings → Projects; the button and File → Open Project are gone, and changing the folder resets a loaded project so pages never land in the new root — `app_gui.py`, `tests/test_projects_folder.py`
- 2026-11-17 — new **Library** tab: a browsable card catalog of saved projects (page preview, page count, date, PDF badge) with filter, sort, open, open-PDF, show-folder and delete; `ScoreInfo` gained `thumbnail`/`modified`/`pdf_path` — `app_gui.py`, `src/api/gui_api.py`, `src/infrastructure/file_service.py`, `tests/test_library_tab.py`
- 2026-11-17 — page-change detection now looks at the detected score band (not the lyric banner) with a stable band and a post-cooldown check, so systems hidden behind an unchanged banner and turns inside the capture cooldown are no longer lost (『Frozen Heart』: 14 -> 17 correct systems, bars 1..51); the scanned band is now exactly the preview's crop band (top offset..crop end, scaled) — `src/application/extraction_components.py`, `src/application/use_cases.py`, `tests/test_frame_stepper.py`
- 2026-11-16 — extraction now writes `metadata.json` as soon as pages commit (not only when a PDF is generated) and a status change refreshes `page_count`, so a locked/stale PDF cannot leave the last page out of the saved record — `src/api/gui_api.py`, `src/application/saved_score.py`, `tests/test_saved_score_records.py`
- 2026-11-16 — auto crop is now a band: the detector measures the score top below a header/lyric banner and the crop runs top..boundary, so the 『Frozen Heart』 pages lose their banner (top 337 of 1080 on every page) — `src/domain/boundary_detector.py`, `src/domain/page_crop.py`, `src/domain/models.py`, `src/application/extraction_components.py`, `app_gui.py`, tests
- 2026-11-16 — the preview's **Top offset** line now moves the band start (`boundary_top_offset_px`), not the bottom boundary; Settings gained “Crop top offset” — `app_gui.py`, `tests/test_gui_visual.py`
- 2026-11-16 — boundary sanity guard now accepts a bottom mean up to 140 (was 120): lit piano keys/hands lift real scans to ~123, which used to reject the detected split and fall back to the fixed crop (the 『花に亡霊』 scan had no page boundary rows at all) — `src/domain/boundary_detector.py`, `src/domain/value_objects/config.py`, `tests/test_boundary_detector.py`
- 2026-11-16 — crop preview gained a **Top offset** checkbox that shows a draggable auto-crop line (preview-frame boundary detection; the line writes `boundary_offset_px` and hides outside Auto) — `app_gui.py`, `tests/test_gui_visual.py`
- 2026-11-03 — crop preview is read-only outside Fixed ratio: no band, line, grips or drag in Auto/Full frame, so it can no longer write `default_crop_ratio` by accident — `app_gui.py`, `tests/test_gui_visual.py`

## Maintenance

Update this file in the **same session** as the change, whenever you:

- create, delete, rename or move a file under `src/`, `tests/`, `tools/` or `scripts/`
- change what a module owns (not just internals)
- add or remove a directory listed in [Layout](#layout)

Do this every time:

1. Edit the relevant table (add, remove or reword the row).
2. Add one line at the top of [Recently changed](#recently-changed):
   `- YYYY-MM-DD — what changed — affected paths`
3. If the change makes a spec doc wrong, fix that doc too.
4. Keep this file under ~150 lines. If it grows, demote detail into the spec doc
   and leave a pointer here.

A plugin (`.opencode/plugins/map-guard.js`) appends a `[MAP GUARD]` note to the
tool result when you write a new file under `src/`, `tests/`, `tools/` or
`scripts/` that this map does not mention. That note is the reminder to do the
steps above — do not ignore it.
