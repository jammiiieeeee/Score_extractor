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
        pattern = r"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\*ffmpeg*\bin\ffmpeg.exe"
        matches = _glob.glob(pattern)
        if matches:
            return matches[0]
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

        main_files = sorted(dl_dir.glob(f"{video_id}.*"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not main_files:
            return None

        main_path = str(main_files[0])
        scan_path = main_path

        if scan_fmt:
            scan_files = sorted(dl_dir.glob(f"{video_id}_scan.*"), key=lambda f: f.stat().st_mtime, reverse=True)
            if scan_files:
                scan_path = str(scan_files[0])

        return DownloadResult(video_path=main_path, video_title=video_id, scan_path=scan_path)

    def download(
        self,
        url: str,
        fmt: str = "bestvideo[height<=1080][fps<=30]",
        scan_fmt: str = "",
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> DownloadResult:
        """Download a YouTube video. Returns DownloadResult with path and title.

        If scan_fmt is provided, downloads a lower-resolution version for scanning.
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
                    on_log(f"Using cached video: {cached.video_path}")
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
                    on_log("  Download finished, processing...")

        ffmpeg_path = self.find_ffmpeg()
        has_ffmpeg = self._ffmpeg_works(ffmpeg_path)
        if on_log and ffmpeg_path and not has_ffmpeg:
            on_log("  ffmpeg found but blocked by policy, will skip format merging")

        # bestvideo requires ffmpeg for merging — fall back to best (combined) when unavailable
        if not has_ffmpeg and fmt.startswith("bestvideo"):
            fmt = fmt.replace("bestvideo", "best")
            if on_log:
                on_log("  ffmpeg unavailable, using combined format instead of bestvideo")

        ydl_opts = {
            'format': fmt,
            'outtmpl': output_template,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'playlistend': 1,
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
                on_log(f"Downloading scan version (low-res)...")
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

        if is_cancelled and is_cancelled():
            raise Exception("Download cancelled by user")

        return DownloadResult(video_path=video_path, video_title=video_title,
                              scan_path=scan_path)
