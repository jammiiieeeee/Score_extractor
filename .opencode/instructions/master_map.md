# Master Map: Piano Score Video-to-PDF Extractor

This document outlines the high-level architecture and maps functional requirements to detailed specification files.

## Architecture Overview
The system follows Clean Architecture principles to ensure robustness and testability.

### Layered Structure
- **Entry Points**: `main.py` (CLI), `app_gui.py` (PyQt6 GUI)
- **API**: `src/api/gui_api.py` (GUI orchestrator, 44-method Python API)
- **Application**: `src/application/use_cases.py` + `extraction_components.py` (Orchestration)
- **Domain**: `src/domain/` (Business logic, deduplication, interfaces, page store)
- **Infrastructure**: `src/infrastructure/` (OpenCV, PaddleOCR, ReportLab, yt-dlp implementations)

## Module Mapping & Loading Guide
Load the following specification files via `@reference` depending on the module being developed:

| Module | Specification File | Description |
| :--- | :--- | :--- |
| **CLI & Interface** | `@reference cli_interface.md` | Argument parsing, console output, and flags. |
| **Business Rules** | `@reference domain_logic.md` | Deduplication algorithm and configuration models. |
| **Orchestration** | `@reference application_orchestration.md` | Data flow between services and component definitions. |
| **Video Processing** | `@reference infrastructure_video.md` | SSIM detection, Dynamic Bar Erase, and frame extraction. |
| **OCR & PDF** | `@reference infrastructure_ocr_pdf.md` | PaddleOCR initialization, regex filtering, and ReportLab layout. |
| **GUI API** | `@reference gui_api.md` | 44-method Python API surface for GUI integration, callback registry, threading model. |
| **GUI Design** | `@reference gui_design.md` | Two-tab layout, state machine, and widget specifications. |
| **System & Safety** | `@reference system_lifecycle.md` | Windows Unicode safety, error handling, and resource cleanup. |

## Core Lifecycle
1. **Initialize**: Load config, open video, perform OCR health check with fallback.
2. **Extract**: Stream video, detect changes (SSIM), capture A/B frames.
3. **Guard Rails**: Bar profile validation (peak count + left spike margin).
4. **Deduplicate**: OCR-first verification (OCR → Global → Row).
5. **Compile**: Layout merged strips and generate PDF in output directory.
6. **Finalize**: Release handles, save metadata.