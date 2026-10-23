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

`create_pdf(pages, output_path, config, title_hint)`:
- Receives **pages** (`Page` objects) — a page carries its own image and the
  boundary row measured for it, so an image and its crop cannot drift apart
- Crops every page with the shared crop rule (`src/domain/page_crop.py`)
- Prints only pages whose status is KEEP; DUPLICATE and EXCLUDED pages are skipped
- Layout: one strip per page, scaled to the usable A4 width (595 − 2×36 = 523 pt)
- A new PDF page starts when the next strip would not fit above the bottom margin
- Title drawn at the top of the first page (CJK font, fallback to Helvetica)

### Crop rule (`src/domain/page_crop.py`)

- `crop_end_row(page, config)` → the row where the page's crop ends (exclusive)
- `crop_page(page, config)` → the cropped image (a view of the page image)
- `boundary_mode = "off"` → keep the whole frame
- `boundary_mode = "manual"` → keep `default_crop_ratio` of the frame
- `boundary_mode = "auto"` → keep up to the page's measured `boundary_row`,
  lifted by `boundary_offset_px`; fall back to `default_crop_ratio` when the
  page has no measured row
- The crop is top-anchored: the sheet music is kept, the visualizer below it
  is dropped
- Any consumer can call the rule directly — the PDF does, a page preview can

### ReportLab Layout

- Uses `reportlab.lib.pagesizes` for A4 dimensions
- `canvas.Canvas` — one PDF page holds as many strips as fit
- Each strip: full-width image scaled to fit
- Title on the first page, from `title_hint` (or the file stem)
- No dynamic bar erase in PDF — bar is already removed during extraction

## Spatial Anchoring

- **X-axis only** — bars are vertical, horizontal position is the key discriminator
- `ocr_horizontal_ratio = 0.30` — search left 30% of frame
- `duplicate_top_ratio = 0.27` — search top 27% of frame
- Y-axis anchor is implicit (top of frame)