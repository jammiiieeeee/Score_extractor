# Master Map: Piano Score Video-to-PDF Extractor

This document outlines the high-level CLI architecture and maps functional requirements to detailed specification files.

## CLI Architecture Overview
The system follows Clean Architecture principles to ensure robustness and testability.

### Layered Structure
- **API**: `src/api/cli.py` (Argparse-based interface)
- **Application**: `src/application/use_cases.py` (Orchestration of services)
- **Domain**: `src/domain/` (Business logic, deduplication rules, interfaces)
- **Infrastructure**: `src/infrastructure/` (OpenCV, PaddleOCR, ReportLab implementations)

## Module Mapping & Loading Guide
Load the following specification files via `@reference` depending on the module being developed:

| Module | Specification File | Description |
| :--- | :--- | :--- |
| **CLI & Interface** | `@reference cli_interface.md` | Argument parsing, console output, and flags. |
| **Business Rules** | `@reference domain_logic.md` | Deduplication algorithm and configuration models. |
| **Orchestration** | `@reference application_orchestration.md` | Data flow between services and DTO definitions. |
| **Video Processing** | `@reference infrastructure_video.md` | SSIM detection, Dynamic Bar Erase, and frame extraction. |
| **OCR & PDF** | `@reference infrastructure_ocr_pdf.md` | PaddleOCR initialization, regex filtering, and ReportLab layout. |
| **GUI API** | `@reference gui_api.md` | 28-method Python API surface for GUI integration, callback registry, threading model. |
| **System & Safety** | `@reference system_lifecycle.md` | UUID sandbox protocol, Windows Unicode safety, and error handling. |

## Core Lifecycle
1. **Initialize**: Load config, setup UUID sandbox, perform OCR health check.
2. **Extract**: Stream video, detect changes (SSIM), capture A/B frames.
3. **Deduplicate**: 3-step verification (Global -> Row -> OCR Veto).
4. **Compile**: Layout merged strips and generate PDF in sandbox.
5. **Finalize**: Release handles and move/rename sandbox to final Unicode destination.
