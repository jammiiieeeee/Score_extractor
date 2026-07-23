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
