# Infrastructure: OCR & PDF Specification

## OcrService (`src/infrastructure/ocr_service.py`)

### Initialization

- PaddleOCR with `use_angle_cls=True`, `lang='en'`
- 3-attempt fallback: tries GPU, then CPU, then disabled
- `initialize()` → `True` if any attempt succeeded
- `is_enabled()` → `True` if OCR is operational
- **No user prompt on failure** — auto-fallback to `_NoopOcrService`

### Text Extraction

- `get_texts(image)` → `list[str]` — all recognized strings from full frame
- `get_leftmost_number(image, top_ratio, horizontal_ratio, confidence)` → `Optional[int]`
  - Crop top `top_ratio` (27%) and left `horizontal_ratio` (30%)
  - Find text box with leftmost center point
  - Extract first integer from text, filter by confidence ≥ threshold
  - Returns `None` if no valid number found

### Keyword Detection

- `detect_keywords(image, keywords)` → `bool`
- Used for tail scan: `detect_keywords(tail_img, ["thank"])`
- Case-insensitive substring match on OCR results

### Regex Filtering

- Number extraction uses `r'-?\d+'` pattern
- Confidence threshold: `ocr_confidence_threshold` (40)

## PdfService (`src/infrastructure/pdf_service.py`)

### PDF Generation

`create_pdf(images, output_path, config, title_hint)`:
- Receives **pre-cropped** images (caller is responsible for cropping)
- Layout: dynamic strips per page based on image width vs A4 width
- Default strips_per_page: `max(1, int(img_w / 595))` where 595 = A4 width in points
- Page size: custom `Rect(0, 0, a4_width, strip_height_in_points)`
- **No cropping logic** — was removed in double-crop bug fix (commit `048c68b`)

### ReportLab Layout

- Uses `reportlab.lib.pagesizes` for A4 dimensions
- `SimpleDocTemplate` with `Frame` for each strip
- Each strip: full-width image scaled to fit
- Title page with `title_hint` as document title
- No dynamic bar erase in PDF — bar is already removed during extraction

## Spatial Anchoring

- **X-axis only** — bars are vertical, horizontal position is the key discriminator
- `ocr_horizontal_ratio = 0.30` — search left 30% of frame
- `duplicate_top_ratio = 0.27` — search top 27% of frame
- Y-axis anchor is implicit (top of frame)