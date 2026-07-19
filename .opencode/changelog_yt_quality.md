# YouTube Download Quality Fixes

## Changes (2026-07-19)

### Format Strings (High Priority)

**Problem:** 720p/480p/360p options used single-stream format (`best[height<=X]`), delivering lower quality than the 1080p option which used split video+audio.

**Problem:** "Best (≤1080p)" over-constrained with `ext=mp4`/`ext=m4a`, eliminating valid higher-bitrate candidates.

**Fix:** All quality tiers now use split format for separate video+audio streams:
- `bestvideo[height<=1080]+bestaudio/best[height<=1080]` (was: `bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]`)
- `bestvideo[height<=720]+bestaudio/best[height<=720]` (was: `best[ext=mp4][height<=720]`)
- `bestvideo[height<=480]+bestaudio/best[height<=480]` (was: `best[ext=mp4][height<=480]`)
- `bestvideo[height<=360]+bestaudio/best[height<=360]` (was: `best[ext=mp4][height<=360]`)

**Files:** `app_gui.py:1010-1015`

### Hardcoded ffmpeg Path (Medium Priority)

**Problem:** ffmpeg path was hardcoded to a specific WinGet package version (`ffmpeg-8.1.2`), breaking on updates.

**Fix:** Added `_find_ffmpeg()` static method that uses `shutil.which()` with a WinGet glob fallback.

**Files:** `gui_api.py:414-424`

### Quality Persistence (Medium Priority)

**Problem:** Quality selection reset to "Best (≤1080p)" on every app launch.

**Fix:** Added `yt_quality_index: int = 0` to `ScoreConfig`. Combo box restores saved index on startup and saves on change via `update_config()`.

**Files:** `config.py:40-41`, `app_gui.py:1016-1017,1118,1277-1278`

### API Default Sync (Low Priority)

**Problem:** API default format string diverged from GUI default (used `vcodec*=avc1` instead of plain height filter).

**Fix:** Both `download_youtube()` and `_run_youtube_download()` now default to `bestvideo[height<=1080]+bestaudio/best[height<=1080]`.

**Files:** `gui_api.py:430,445`

### Redundant format_sort (Low Priority)

**Problem:** `format_sort: ['codec:h264', 'codec:vp9', 'codec:av01']` was redundant with the (now-removed) `ext=mp4` constraint.

**Fix:** Removed `format_sort` from `ydl_opts`. yt-dlp's format selection now handles codec preference implicitly.

**Files:** `gui_api.py:469-478`
