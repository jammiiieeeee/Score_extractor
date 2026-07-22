# Infrastructure: Video Processing Specification

## VideoService (`src/infrastructure/video_service.py`)

### Frame Reading

- `open_video(path)` — opens via `cv2.VideoCapture`
- `read_frame_at(frame_idx)` → `(image, timestamp)` — seek to absolute frame index
- `read_next_frame()` → `(image, timestamp, frame_idx)` — sequential read
- `skip_frames(n)` — advance `n` frames without returning
- `read_full_frame_at(frame_idx)` — read at native resolution (for OCR/debug)

### Frame Skipping

- Configured by `frame_check_interval` (default 0.8s)
- `seek_step = max(1, int(frame_check_interval * fps))`
- Implemented via `skip_frames(seek_step - 1)` before `read_next_frame()`
- No dual-speed skipping, no circular buffer — single linear scan

### SSIM Detection

- ROI: **top 34%** of frame (`top_analysis_ratio = 0.34`), not center 60%
- Resize to 320px width for comparison
- Convert to grayscale, compute `skimage.metrics.structural_similarity`
- Trigger when SSIM < `change_detection_threshold` (0.96)

### Cooldown

- `min_screenshot_interval = 3.0` seconds (not 1.5s)
- Cooldown in frames: `int(min_screenshot_interval * fps)`
- After trigger, skip detection for cooldown period

### Dynamic Bar Erase (`merge_frames`)

- Detects playback bar via column-wise absdiff between A and B
- Bar right edge = argmax of vertical sum in left 50% of frame
- Bar left edge estimated from `bar_width` (column distance)
- B-frame overlay from start of A to `bar_right_edge + bar_padding_px`
- `bar_padding_px = -15` means overlay stops 15px before bar right edge
- Outputs: merged image, bar_x (right edge), bar_width

### Bar Overlay Behavior

- `b_overlay_width_ratio = 0.5` — left 50% of B overlaid onto A
- Overlay cutoff: `bar_right_edge + bar_padding_px` (in original resolution)
- At 640px scale: `merge_x = bar_left_640 + bar_padding_px * (640/w)`

### Bar Profile Validation

Peaks computed by `Deduplicator._get_bar_profile_peaks()`:
1. Resize A/B to 640px width
2. Crop top `crop_ratio` region
3. Column-wise absdiff → `col_sums`
4. Find local maxima: `col_sums[i] > col_sums[i-1]` and `>= col_sums[i+1]`
5. Threshold: `> max_val * 0.3`
6. Minimum distance: `max(3, int(640 * 0.06))` between peaks
7. **Clean profile**: 2–4 peaks
8. **Left spike**: leftmost of top 2 peaks < `640 * bar_left_margin` (20%)

## Frame Model

`src/domain/models.py`:
```python
@dataclass
class Frame:
    image: np.ndarray          # BGR image
    timestamp: float           # seconds
    frame_index: int
    ssim_score: float = 0.0
```