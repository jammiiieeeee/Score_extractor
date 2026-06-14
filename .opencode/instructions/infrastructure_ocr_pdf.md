# Infrastructure: OCR & PDF Specification

## OCR Implementation (PaddleOCR)
### Initialization Loop
1. Set critical `os.environ` flags before importing PaddleOCR.
2. Try `PaddleOCR(lang='en', enable_mkldnn=False)`.
3. On failure: `PaddleOCR(enable_mkldnn=False)`.
4. On second failure: `PaddleOCR()` (default).
5. If all attempts fail: Prompt user to continue without OCR.

### Number Extraction
- **Scope**: Top 27% vertical slice.
- **Filtering**: `re.fullmatch(r'\d+', text)`. Only pure numeric strings are considered (ignores chord names like `C(add9)` and tempo markings).
- **Spatial Anchoring**: Store $(x, y)$ of detected numbers. Only compare numbers if their bounding boxes overlap horizontally by $> 80\%$.

## PDF Implementation (ReportLab)
- **Page Size**: A4 (595.27 x 841.89 points).
- **Margins**: 36pt (0.5 inch).
- **Scaling**: 
    - Strip Width = `A4_Width - 2 * Margins`.
    - Maintain aspect ratio of the 35% cropped strip.
- **Layout**: 7 strips per page. If a page is not full, leave the bottom white.
