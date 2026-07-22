# Changelog

## 2026-07-22

### Bug Fixes
- **PDF crop**: `PdfService.create_pdf()` now crops images using `config.default_crop_ratio` and `config.crop_top_offset`. Users can regenerate PDF with different crop ratios without re-extracting.
- **OCR toggle**: Added "Enable OCR" checkbox to Settings tab. Unchecking disables OCR during extraction.
- **End offset**: Fixed `DualHandleSeekBar.get_end()` — when end handle is disabled, extraction now goes to the video end instead of stopping at timestamp 0.

### Changes
- **Preview**: Reverted FFmpeg downscaling in `PreviewSeeker`. Preview uses the low-res scan video directly when available from YouTube download.
