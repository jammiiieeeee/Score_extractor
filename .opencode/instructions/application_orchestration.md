# Application Orchestration Specification

## Use Cases

### `ExtractScoreUseCase`
**Input**: `input_path`, `config`
1. Initialize `VideoService` and `OcrService`.
2. Perform OCR health check.
3. Iterate through video frames:
    - Buffer frames for stability.
    - Trigger `PageChange` on SSIM drop.
    - Coordinate `A/B Capture` timing.
    - Call `Deduplicator` service.
4. Return a list of `MergedFrame` DTOs.

### `GeneratePdfUseCase`
**Input**: `list[MergedFrame]`, `output_path`, `config`
1. Initialize `PdfService`.
2. Calculate scaling for A4 page width.
3. Layout 7 strips per page.
4. Save draft PDF in UUID sandbox.

## Data Transfer Objects (DTOs)
- `FrameData`: Contains raw image path (in sandbox), timestamp, and frame index.
- `MergedFrame`: Contains the path to the A/B composite image.
- `ExtractionResult`: Summary of total pages detected vs. deduplicated.
