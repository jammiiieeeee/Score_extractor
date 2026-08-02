import re
import shutil
import glob as _glob
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple


class DownloadResult:
    """Result of a YouTube download operation."""
    def __init__(self, video_path: str, video_title: str, original_path: Optional[str] = None,
                 scan_path: Optional[str] = None):
        self.video_path = video_path
        self.video_title = video_title
        self.original_path = original_path or video_path
        self.scan_path = scan_path or video_path


class DownloadService:
    """Encapsulates yt-dlp YouTube download logic.

    Separated from GuiApi to keep streaming/download concerns
    in one place and make them independently testable.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    @staticmethod
    def find_ffmpeg() -> str:
        path = shutil.which("ffmpeg")
        if path:
            return path
        for pattern in (
            r"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\**\ffmpeg.exe",
            r"C:\ProgramData\WinGet\Packages\**\ffmpeg.exe",
        ):
            for match in _glob.glob(pattern, recursive=True):
                if os.path.exists(match):
                    return match
        manual = r"C:\ProgramData\ffmpeg\ffmpeg.exe"
        if os.path.exists(manual):
            return manual
        return ""

    @staticmethod
    def _ffmpeg_works(path: str) -> bool:
        """Check if ffmpeg binary actually runs (not blocked by AppControl)."""
        if not path:
            return False
        try:
            result = subprocess.run([path, "-version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats."""
        patterns = [
            r'(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$',
        ]
        for pat in patterns:
            m = re.search(pat, url)
            if m:
                return m.group(1)
        return None

    def _check_cache(self, video_id: str, scan_fmt: str,
                     on_log: Optional[Callable[[str], None]] = None) -> Optional[DownloadResult]:
        """Check if video files already exist in yt_dl/ for this video ID."""
        dl_dir = self.base_dir / "yt_dl"
        if not dl_dir.exists():
            return None

        title_path = self._title_path(self.base_dir, video_id)
        main_files = sorted(
            (f for f in dl_dir.glob(f"{video_id}.*")
             if f != title_path and f.suffix != ".title"),
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        if not main_files:
            return None

        main_path = str(main_files[0])
        scan_path = main_path

        if scan_fmt:
            scan_files = sorted(
                (f for f in dl_dir.glob(f"{video_id}_scan.*")
                 if f.suffix != ".title"),
                key=lambda f: f.stat().st_mtime, reverse=True,
            )
            if scan_files:
                scan_path = str(scan_files[0])

        return DownloadResult(video_path=main_path, video_title=self._read_title(video_id), scan_path=scan_path)

    @staticmethod
    def _title_path(base_dir: Path, video_id: str) -> Path:
        return base_dir / "yt_dl" / f"{video_id}.title"

    def _save_title(self, video_id: str, title: str) -> None:
        """Persist the video title to a UTF-8 sidecar file for cache retrieval."""
        if not video_id or not title:
            return
        path = self._title_path(self.base_dir, video_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(title, encoding="utf-8")
        except OSError:
            pass

    def _read_title(self, video_id: str) -> str:
        """Read the cached video title. Falls back to video_id if missing or unreadable."""
        path = self._title_path(self.base_dir, video_id)
        try:
            if path.exists():
                title = path.read_text(encoding="utf-8").lstrip("\ufeff").strip()
                if title:
                    return title
        except (OSError, UnicodeDecodeError):
            pass
        return video_id

    def download(
        self,
        url: str,
        fmt: str = "bestvideo[height<=1080]",
        scan_fmt: str = "",
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> DownloadResult:
        """Download a YouTube video. Returns DownloadResult with path and title.

        Only video streams are requested (no audio) — formats should use
        ``bestvideo[...]`` selectors. If scan_fmt is provided, downloads a
        lower-resolution video-only version for scanning.
        Raises on cancellation or failure.
        """
        import yt_dlp
        import cv2

        dl_dir = self.base_dir / "yt_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)

        # Check cache before downloading
        video_id = self._extract_video_id(url)
        if video_id:
            cached = self._check_cache(video_id, scan_fmt, on_log=on_log)
            if cached:
                if on_log:
                    on_log(f"Cached: {cached.video_path}")
                return cached

        output_template = str(dl_dir / "%(id)s.%(ext)s")

        finished_logged = False

        def progress_hook(d):
            nonlocal finished_logged
            if is_cancelled and is_cancelled():
                raise Exception("Download cancelled by user")
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                pct = d.get('downloaded_bytes', 0) / total * 100
                if on_progress:
                    on_progress(pct, f"Downloading... {pct:.0f}%")
            elif d['status'] == 'finished' and not finished_logged:
                finished_logged = True
                if on_log:
                    on_log("  Processing...")

        ffmpeg_path = self.find_ffmpeg()
        has_ffmpeg = self._ffmpeg_works(ffmpeg_path)
        if on_log and ffmpeg_path and not has_ffmpeg:
            on_log("  ffmpeg blocked, skipping merge")

        # Video-only formats (bestvideo) need no ffmpeg merge; only combined
        # formats such as bestvideo+bestaudio would require it.

        ydl_opts = {
            'format': fmt,
            'outtmpl': output_template,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'playlistend': 1,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/131.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            },
        }
        if has_ffmpeg:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            ydl_opts['merge_output_format'] = 'mp4'

        if on_log:
            on_log(f"Downloading: {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')

            # Log format details
            if info.get('requested_formats') and on_log:
                for f in info['requested_formats']:
                    codec = f.get('vcodec') or f.get('acodec', '?')
                    ext = f.get('ext', '?')
                    res = f"{f.get('width', '?')}x{f.get('height', '?')}" if f.get('vcodec') else 'audio'
                    on_log(f"  Format: {ext} | {res} | codec={codec}")
            elif on_log:
                vcodec = info.get('vcodec', '?')
                acodec = info.get('acodec', '?')
                on_log(f"  Codec: video={vcodec}  audio={acodec}")

            video_id = info.get('id', 'video')
            candidates = list(dl_dir.glob(f"{video_id}.*"))
            if not candidates:
                candidates = sorted(dl_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
            if not candidates:
                raise RuntimeError("Could not find downloaded video file")
            video_path = str(candidates[0])

        # Download low-res scan version if requested
        scan_path = video_path
        if scan_fmt:
            if on_log:
                on_log(f"Downloading scan (low-res)...")
            scan_template = str(dl_dir / f"%(id)s_scan.%(ext)s")
            ydl_opts_scan = {
                'format': scan_fmt,
                'outtmpl': scan_template,
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'playlistend': 1,
            }
            if has_ffmpeg:
                ydl_opts_scan['ffmpeg_location'] = ffmpeg_path
                ydl_opts_scan['merge_output_format'] = 'mp4'
            with yt_dlp.YoutubeDL(ydl_opts_scan) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info.get('id', 'video')
                candidates = list(dl_dir.glob(f"{video_id}_scan.*"))
                if candidates:
                    scan_path = str(candidates[0])
                    if on_log:
                        cap = cv2.VideoCapture(scan_path)
                        sw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        sh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        cap.release()
                        on_log(f"  Scan version: {sw}x{sh}")
                        on_log(f"  Download path: {scan_path}")

        if on_log:
            on_log(f"  Title: {video_title}")
            on_log(f"  Saved to: {video_path}")

        # Persist the title so a future cache hit can recover it
        self._save_title(video_id, video_title)

        if is_cancelled and is_cancelled():
            raise Exception("Download cancelled by user")

        return DownloadResult(video_path=video_path, video_title=video_title,
                              scan_path=scan_path)
