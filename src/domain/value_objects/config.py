from dataclasses import dataclass


@dataclass
class ScoreConfig:
    # Change Detection
    change_detection_threshold: float = 0.96     # SSIM similarity score (1.0 = identical)
    frame_check_interval: float = 0.2            # Seek every N seconds
    top_analysis_ratio: float = 0.34             # Top portion of frame for SSIM ROI
    min_screenshot_interval: float = 3.0         # Cooldown between captures (seconds)

    # A/B Capture
    a_capture_delay: float = 0.3                 # Seconds after SSIM trigger before A-frame capture
    b_capture_delay: float = 3.0                 # Seconds between A-frame and B-frame
    b_overlay_width_ratio: float = 0.5           # Left portion of B overlaid onto A

    # Deduplication
    duplicate_top_ratio: float = 0.27            # Top portion for duplicate / OCR analysis
    pixel_similarity_threshold: float = 0.95     # Step 1: global pixel similarity
    row_similarity_threshold: float = 0.98       # Step 2: per-row similarity
    row_coverage_threshold: float = 0.94         # Step 2: % of rows must be similar

    # OCR
    ocr_confidence_threshold: int = 40           # Minimum confidence (0-100)
    ocr_horizontal_ratio: float = 0.30           # Left portion of frame for OCR search

    # PDF Output
    default_crop_ratio: float = 0.35             # Height of each PDF strip
    crop_top_offset: float = 0.0                 # Starting Y offset for crop
    default_strips_per_page: int = 7             # Strips per PDF page

    # Blank / End Detection
    blank_content_std_threshold: float = 3.0     # Pixel std below this = blank screen
