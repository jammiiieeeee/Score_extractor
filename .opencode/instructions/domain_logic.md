# Domain Logic Specification

## Configuration Model (`ScoreConfig`)
Defined in `src/domain/value_objects/config.py`. Loadable via `config.json`:

| Parameter | Default | Purpose |
| :--- | :--- | :--- |
| `change_detection_threshold` | 0.96 | SSIM threshold for page change |
| `frame_check_interval` | 0.2 | Seconds between seek-mode checks |
| `top_analysis_ratio` | 0.35 | Top portion for SSIM ROI |
| `min_screenshot_interval` | 3.0 | Cooldown between captures |
| `b_capture_delay` | 3.0 | A→B delay in seconds |
| `b_overlay_width_ratio` | 0.2 | Left portion of B overlaid onto A |
| `duplicate_top_ratio` | 0.27 | Top portion for OCR/dup analysis |
| `pixel_similarity_threshold` | 0.95 | Step 1: global similarity |
| `row_similarity_threshold` | 0.98 | Step 2: per-row threshold |
| `row_coverage_threshold` | 0.94 | Step 2: row coverage |
| `ocr_confidence_threshold` | 40 | Min OCR confidence (0-100) |
| `ocr_horizontal_ratio` | 0.30 | Left portion for OCR search |
| `default_crop_ratio` | 0.35 | Height of each PDF strip |
| `crop_top_offset` | 0.0 | Starting Y offset for crop |
| `default_strips_per_page` | 7 | Strips per PDF page |

## 3-Step Deduplication Algorithm
The `Deduplicator` service must implement the following logic:

### Step 1: Global Pixel Similarity
- Comparison of resized 256x256 grayscale versions of frames.
- If similarity $> 99.5\% \rightarrow$ **DUPLICATE** (Short-circuit).
- If similarity $< 95.0\% \rightarrow$ **UNIQUE** (Short-circuit).

### Step 2: Row-wise Similarity (if Step 1 is inconclusive)
- Analyze the top `ocr_vertical_range` (27%).
- Compare frames row-by-row.
- A row is "Similar" if pixel correlation $> 98\%$.
- A frame is a **DUPLICATE** if $> 94\%$ of rows are "Similar".

### Step 3: OCR Veto & Force
- If Step 1 or 2 suggests a Duplicate, extract the leftmost numeric string from the top 27%.
- **Force Rule**: If Frame A and Frame B have the **same number**, return **DUPLICATE** immediately.
- **Veto Rule**: If Frame A has number $N_1$ and Frame B has number $N_2$, and $N_1 \neq N_2$, mark as **UNIQUE**.
- If OCR fails or results are identical, maintain the "Duplicate" status from Step 2.

## Masking Strategy
- Before similarity analysis, the system identifies the "playback bar" X-coordinate ($X_{bar}$).
- A vertical mask of $X_{bar} \pm 10px$ is applied (blacked out) to both frames to ignore the bar's position.
