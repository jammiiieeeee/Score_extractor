# Domain Logic Specification

This document defines the business rules for deduplication, configuration, and data models.

## Deduplication Algorithm

Three-stage pipeline executed by `src/domain/deduplication.py:Deduplicator`:

### Stage 0: OCR Force-Duplicate
1. Extract leftmost number from B-frame via `IOcrService.get_leftmost_number()`.
2. If OCR enabled AND both A and B numbers are not `None`:
   - **Same number → duplicate immediately** (short-circuit).
   - **Different numbers → not duplicate immediately** (short-circuit).
3. If OCR unavailable or either number is `None`, fall through to visual stages.

### Stage 1: Global Pixel Similarity
1. Detect and mask playback bar in both frames (30px band around max-diff column, left half only).
2. Resize both to 256×256 grayscale.
3. Compute `cv2.matchTemplate(TM_CCOEFF_NORMED)`.
4. Score > 0.995 → duplicate.
5. Score < `pixel_similarity_threshold` (0.95) → not duplicate.

### Stage 2: Row-wise Similarity
1. Crop both frames to top `duplicate_top_ratio` (27%).
2. For each row: compute Pearson correlation.
3. If both rows have std < 0.1 → count as similar (skip correlation).
4. If coverage > `row_coverage_threshold` (94%) → duplicate.

## Bar Profile Validation

Guard rails applied to each A/B capture pair before deduplication:

1. Compute column-wise absolute diff between A and B in top `crop_ratio` region (resized to 640px width).
2. Find peaks: local maxima exceeding 30% of peak value, minimum 6% width apart.
3. **Clean profile**: 2–4 peaks → pass.
4. **Left spike**: leftmost of top 2 peaks must be within `bar_left_margin` (20%) of frame width.
5. Both conditions must be true to accept the capture.

## Configuration Model

`src/domain/value_objects/config.py:ScoreConfig` — 22 fields across 7 groups:

### Change Detection
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `change_detection_threshold` | float | 0.96 | SSIM similarity threshold (1.0 = identical) |
| `frame_check_interval` | float | 0.8 | Seek step in seconds |
| `top_analysis_ratio` | float | 0.34 | Top fraction of frame for SSIM ROI |
| `min_screenshot_interval` | float | 3.0 | Cooldown between captures (seconds) |

### A/B Capture
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `a_capture_delay` | float | 0.3 | Seconds after SSIM trigger before A-frame |
| `b_capture_delay` | float | 3.0 | Seconds between A and B frame |
| `b_overlay_width_ratio` | float | 0.5 | Left portion of B overlaid onto A |

### Deduplication
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `duplicate_top_ratio` | float | 0.27 | Top fraction for duplicate analysis |
| `pixel_similarity_threshold` | float | 0.95 | Stage 1 threshold |
| `row_similarity_threshold` | float | 0.98 | Stage 2 per-row correlation |
| `row_coverage_threshold` | float | 0.94 | Stage 2 row coverage fraction |

### OCR
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ocr_confidence_threshold` | int | 40 | Minimum confidence (0–100) |
| `ocr_horizontal_ratio` | float | 0.30 | Left fraction of frame for OCR search |

### PDF Output
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_crop_ratio` | float | 0.32 | Height of each PDF strip |

### Bar Detection
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bar_min_diff_threshold` | float | 500.0 | Minimum summed column diff to accept bar |
| `bar_padding_px` | int | -15 | B overlay offset from bar edge (+ into bar, - retract) |
| `bar_left_margin` | float | 0.20 | Left spike must be within this fraction of width |

### Blank / End Detection
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `blank_content_std_threshold` | float | 3.0 | Pixel std below this = blank screen |

### YouTube Download
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `yt_quality_index` | int | 0 | Combo box index for quality preset |

## Data Models

`src/domain/models.py`:
```python
@dataclass
class Frame:
    image: np.ndarray          # BGR image
    timestamp: float           # Seconds from video start
    frame_index: int           # Absolute frame number
    ssim_score: float = 0.0    # Similarity to previous frame
```

## Interfaces

`src/domain/interfaces.py` defines:
- `IVideoService`: `open_video()`, `read_frame_at()`, `read_next_frame()`, `skip_frames()`, `read_full_frame_at()`, `merge_frames()`, `get_original_size()`, `get_fps()`, `get_total_frames()`, `close()`
- `IOcrService`: `initialize()`, `is_enabled()`, `get_leftmost_number()`
- `IPdfService`: `create_pdf()`
- `IFileService`: `prepare_output_dir()`, `load_page_images()`
- `_NoopOcrService`: Fallback when OCR is disabled or fails