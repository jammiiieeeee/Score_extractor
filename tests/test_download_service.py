"""Unit tests for src/infrastructure/download_service.py — DownloadService class."""

import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.infrastructure.download_service import DownloadService, DownloadResult


pytestmark = pytest.mark.unit


@pytest.fixture
def dl_svc(tmp_path):
    return DownloadService(base_dir=tmp_path)


class TestFindFfmpeg:

    def test_returns_string(self):
        result = DownloadService.find_ffmpeg()
        assert isinstance(result, str)

    def test_returns_empty_when_not_found(self):
        with patch("shutil.which", return_value=None), \
             patch("glob.glob", return_value=[]), \
             patch("os.path.exists", return_value=False):
            result = DownloadService.find_ffmpeg()
            assert result == ""


class TestFfmpegWorks:

    def test_empty_string_returns_false(self):
        assert DownloadService._ffmpeg_works("") is False

    def test_nonexistent_path_returns_false(self):
        assert DownloadService._ffmpeg_works("/nonexistent/path/ffmpeg") is False

    def test_successful_run_returns_true(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert DownloadService._ffmpeg_works("ffmpeg") is True

    def test_failed_run_returns_false(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert DownloadService._ffmpeg_works("ffmpeg") is False

    def test_exception_returns_false(self):
        with patch("subprocess.run", side_effect=OSError("no such file")):
            assert DownloadService._ffmpeg_works("bad_path") is False


class TestDownloadResult:

    def test_stores_path_and_title(self):
        r = DownloadResult(video_path="/a/b.mp4", video_title="My Video")
        assert r.video_path == "/a/b.mp4"
        assert r.video_title == "My Video"

    def test_defaults_scan_path_to_video_path(self):
        r = DownloadResult(video_path="/a/b.mp4", video_title="T")
        assert r.scan_path == "/a/b.mp4"

    def test_defaults_original_path_to_video_path(self):
        r = DownloadResult(video_path="/a/b.mp4", video_title="T")
        assert r.original_path == "/a/b.mp4"

    def test_explicit_scan_path(self):
        r = DownloadResult(video_path="/a/b.mp4", video_title="T", scan_path="/a/b_scan.mp4")
        assert r.scan_path == "/a/b_scan.mp4"

    def test_explicit_original_path(self):
        r = DownloadResult(video_path="/a/b.mp4", video_title="T", original_path="/orig.mp4")
        assert r.original_path == "/orig.mp4"


class TestTitleCache:

    def test_save_and_read_roundtrip(self, dl_svc, tmp_path):
        dl_svc._save_title("abc12345678", "My Piano Piece")
        assert dl_svc._read_title("abc12345678") == "My Piano Piece"

    def test_read_falls_back_to_id_when_missing(self, dl_svc):
        assert dl_svc._read_title("nonexistent999") == "nonexistent999"

    def test_read_falls_back_to_id_when_empty(self, dl_svc):
        dl_svc._save_title("emptyID00001", "")
        assert dl_svc._read_title("emptyID00001") == "emptyID00001"

    def test_read_falls_back_to_id_when_whitespace_only(self, dl_svc):
        path = dl_svc.base_dir / "yt_dl" / "wsID0000001.title"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("   \n\t  ", encoding="utf-8")
        assert dl_svc._read_title("wsID0000001") == "wsID0000001"

    def test_save_handles_japanese(self, dl_svc):
        title = "月光 第三楽章 — ベートーヴェン"
        dl_svc._save_title("jpID00000001", title)
        assert dl_svc._read_title("jpID00000001") == title

    def test_save_handles_illegal_chars_in_content(self, dl_svc):
        title = 'Bad/Title:With<Illegal>Chars?'
        dl_svc._save_title("badID0000001", title)
        # The sidecar file stores the raw title; sanitization is the
        # caller's job when building paths.
        assert dl_svc._read_title("badID0000001") == title

    def test_save_strips_bom_on_read(self, dl_svc):
        path = dl_svc.base_dir / "yt_dl" / "bomID0000001.title"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes("\ufeffBOM Title".encode("utf-8"))
        assert dl_svc._read_title("bomID0000001") == "BOM Title"

    def test_save_overwrites_existing(self, dl_svc):
        dl_svc._save_title("overID0000001", "Old Title")
        dl_svc._save_title("overID0000001", "New Title")
        assert dl_svc._read_title("overID0000001") == "New Title"

    def test_save_silent_on_oserror(self, dl_svc, monkeypatch):
        def _raise(*a, **kw):
            raise OSError("disk full")
        monkeypatch.setattr(Path, "write_text", _raise)
        # Should not raise
        dl_svc._save_title("errID0000001", "Whatever")


class TestCheckCache:

    def _make_cached_video(self, tmp_path, video_id, title="Real Title"):
        dl_dir = tmp_path / "yt_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        main = dl_dir / f"{video_id}.mp4"
        main.write_bytes(b"fake video")
        if title:
            (dl_dir / f"{video_id}.title").write_text(title, encoding="utf-8")
        return main

    def test_returns_none_when_no_cache(self, dl_svc):
        assert dl_svc._check_cache("nopeID000001", "") is None

    def test_uses_saved_title(self, dl_svc, tmp_path):
        self._make_cached_video(tmp_path, "abc12345678", title="My Real Title")
        result = dl_svc._check_cache("abc12345678", "")
        assert result is not None
        assert result.video_title == "My Real Title"
        assert result.video_path.endswith("abc12345678.mp4")

    def test_falls_back_to_id_when_no_sidecar(self, dl_svc, tmp_path):
        self._make_cached_video(tmp_path, "oldID0000001", title=None)
        result = dl_svc._check_cache("oldID0000001", "")
        assert result is not None
        assert result.video_title == "oldID0000001"

    def test_ignores_title_file_as_video(self, dl_svc, tmp_path):
        # Only the sidecar exists, no actual video file
        dl_dir = tmp_path / "yt_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        (dl_dir / "onlyID000001.title").write_text("just a title", encoding="utf-8")
        assert dl_svc._check_cache("onlyID000001", "") is None

    def test_uses_scan_path_when_available(self, dl_svc, tmp_path):
        dl_dir = tmp_path / "yt_dl"
        dl_dir.mkdir(parents=True, exist_ok=True)
        (dl_dir / "scanID0000001.mp4").write_bytes(b"main")
        (dl_dir / "scanID0000001_scan.mp4").write_bytes(b"scan")
        (dl_dir / "scanID0000001.title").write_text("Scanned Title", encoding="utf-8")
        result = dl_svc._check_cache("scanID0000001", "best[height<=360]")
        assert result is not None
        assert result.video_path.endswith("scanID0000001.mp4")
        assert result.scan_path.endswith("scanID0000001_scan.mp4")
        assert result.video_title == "Scanned Title"

    def test_preserves_japanese_title_through_cache(self, dl_svc, tmp_path):
        title = "ショパン：ノクターン Op.9 No.2"
        self._make_cached_video(tmp_path, "jpID00000099", title=title)
        result = dl_svc._check_cache("jpID00000099", "")
        assert result.video_title == title
