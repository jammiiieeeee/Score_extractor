"""
Tests for main.py CLI argument parsing.

Uses argparse directly (mirroring main.py's parser) to verify argument
handling without running extraction.

Run: pytest tests/test_cli.py -v
"""

import sys
import argparse
from io import StringIO
import pytest


def _make_parser():
    """Build the same parser used by main.py."""
    parser = argparse.ArgumentParser(description="Piano Score Video-to-PDF Extractor")
    parser.add_argument("input", nargs="?", default=None,
                        help="Path to the input video file or YouTube URL")
    parser.add_argument("-o", "--output",
                        help="Output PDF path (default: input name with .pdf)")
    parser.add_argument("--output-dir",
                        help="Output folder for organized score")
    parser.add_argument("--score-name",
                        help="Score name (default: video filename stem)")
    parser.add_argument("-c", "--config", default="config.json",
                        help="Path to config.json")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug mode")
    parser.add_argument("--ocr", action="store_true",
                        help="Enable OCR for deduplication")
    parser.add_argument("--start-time", type=float, default=2.0,
                        help="Jump to this time in seconds")
    parser.add_argument("--end-offset", type=float, default=0.0,
                        help="Stop processing N seconds before video end")
    parser.add_argument("--crop-ratio", type=float,
                        help="Override crop ratio for PDF output")
    parser.add_argument("--from-dir",
                        help="Regenerate PDF from existing score directory")
    parser.add_argument("--yt-url",
                        help="YouTube URL to download before extraction")
    parser.add_argument("--quality",
                        choices=["1080p", "720p", "480p", "360p"],
                        default="1080p",
                        help="Video quality for YouTube download")
    return parser


def _parse_args(argv):
    """Parse args the same way main.py does (argv should NOT include prog name)."""
    return _make_parser().parse_args(argv)


# ═══════════════════════════════════════════════════════════════════════════
#  Default Arguments
# ═══════════════════════════════════════════════════════════════════════════


class TestDefaultArguments:
    def test_input_defaults_to_none(self):
        args = _parse_args([])
        assert args.input is None

    def test_config_defaults_to_config_json(self):
        args = _parse_args([])
        assert args.config == "config.json"

    def test_start_time_defaults_to_2(self):
        args = _parse_args([])
        assert args.start_time == 2.0

    def test_end_offset_defaults_to_0(self):
        args = _parse_args([])
        assert args.end_offset == 0.0

    def test_debug_defaults_to_false(self):
        args = _parse_args([])
        assert args.debug is False

    def test_ocr_defaults_to_false(self):
        args = _parse_args([])
        assert args.ocr is False

    def test_quality_defaults_to_1080p(self):
        args = _parse_args([])
        assert args.quality == "1080p"

    def test_crop_ratio_defaults_to_none(self):
        args = _parse_args([])
        assert args.crop_ratio is None

    def test_from_dir_defaults_to_none(self):
        args = _parse_args([])
        assert args.from_dir is None

    def test_yt_url_defaults_to_none(self):
        args = _parse_args([])
        assert args.yt_url is None

    def test_output_defaults_to_none(self):
        args = _parse_args([])
        assert args.output is None

    def test_output_dir_defaults_to_none(self):
        args = _parse_args([])
        assert args.output_dir is None

    def test_score_name_defaults_to_none(self):
        args = _parse_args([])
        assert args.score_name is None


# ═══════════════════════════════════════════════════════════════════════════
#  Custom Arguments
# ═══════════════════════════════════════════════════════════════════════════


class TestCustomArguments:
    def test_all_flags_specified(self):
        args = _parse_args([
            "my_video.mp4",
            "-o", "output.pdf",
            "--output-dir", "./scores",
            "--score-name", "My Score",
            "-c", "custom_config.json",
            "-d",
            "--ocr",
            "--start-time", "5.0",
            "--end-offset", "3.5",
            "--crop-ratio", "0.30",
            "--from-dir", "./existing",
            "--yt-url", "https://youtube.com/watch?v=abc",
            "--quality", "720p",
        ])
        assert args.input == "my_video.mp4"
        assert args.output == "output.pdf"
        assert args.output_dir == "./scores"
        assert args.score_name == "My Score"
        assert args.config == "custom_config.json"
        assert args.debug is True
        assert args.ocr is True
        assert args.start_time == 5.0
        assert args.end_offset == 3.5
        assert args.crop_ratio == 0.30
        assert args.from_dir == "./existing"
        assert args.yt_url == "https://youtube.com/watch?v=abc"
        assert args.quality == "720p"


# ═══════════════════════════════════════════════════════════════════════════
#  Individual Flag Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestOcrFlag:
    def test_ocr_flag_enables_ocr(self):
        args = _parse_args(["video.mp4", "--ocr"])
        assert args.ocr is True

    def test_no_ocr_flag_disables(self):
        args = _parse_args(["video.mp4"])
        assert args.ocr is False


class TestDebugFlag:
    def test_debug_flag_enables(self):
        args = _parse_args(["video.mp4", "-d"])
        assert args.debug is True

    def test_debug_long_flag_enables(self):
        args = _parse_args(["video.mp4", "--debug"])
        assert args.debug is True

    def test_no_debug_flag_disables(self):
        args = _parse_args(["video.mp4"])
        assert args.debug is False


class TestStartTime:
    def test_parses_float(self):
        args = _parse_args(["video.mp4", "--start-time", "10.5"])
        assert args.start_time == 10.5

    def test_parses_zero(self):
        args = _parse_args(["video.mp4", "--start-time", "0.0"])
        assert args.start_time == 0.0

    def test_default_value(self):
        args = _parse_args(["video.mp4"])
        assert args.start_time == 2.0


class TestEndOffset:
    def test_parses_float(self):
        args = _parse_args(["video.mp4", "--end-offset", "7.5"])
        assert args.end_offset == 7.5

    def test_parses_zero(self):
        args = _parse_args(["video.mp4", "--end-offset", "0.0"])
        assert args.end_offset == 0.0

    def test_default_value(self):
        args = _parse_args(["video.mp4"])
        assert args.end_offset == 0.0


class TestCropRatio:
    def test_parses_float(self):
        args = _parse_args(["video.mp4", "--crop-ratio", "0.28"])
        assert args.crop_ratio == 0.28

    def test_default_is_none(self):
        args = _parse_args(["video.mp4"])
        assert args.crop_ratio is None


class TestFromDir:
    def test_sets_from_dir(self):
        args = _parse_args(["--from-dir", "/path/to/scores"])
        assert args.from_dir == "/path/to/scores"

    def test_default_is_none(self):
        args = _parse_args([])
        assert args.from_dir is None


class TestYtUrl:
    def test_sets_yt_url(self):
        args = _parse_args(["--yt-url", "https://youtube.com/watch?v=abc"])
        assert args.yt_url == "https://youtube.com/watch?v=abc"

    def test_default_is_none(self):
        args = _parse_args([])
        assert args.yt_url is None


class TestQuality:
    def test_1080p(self):
        args = _parse_args(["video.mp4", "--quality", "1080p"])
        assert args.quality == "1080p"

    def test_720p(self):
        args = _parse_args(["video.mp4", "--quality", "720p"])
        assert args.quality == "720p"

    def test_480p(self):
        args = _parse_args(["video.mp4", "--quality", "480p"])
        assert args.quality == "480p"

    def test_360p(self):
        args = _parse_args(["video.mp4", "--quality", "360p"])
        assert args.quality == "360p"

    def test_invalid_quality_rejected(self):
        with pytest.raises(SystemExit):
            _parse_args(["video.mp4", "--quality", "4k"])


# ═══════════════════════════════════════════════════════════════════════════
#  Missing / Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestMissingVideoPath:
    def test_input_is_none_when_not_given(self):
        args = _parse_args([])
        assert args.input is None

    def test_from_dir_does_not_require_input(self):
        args = _parse_args(["--from-dir", "/some/dir"])
        assert args.from_dir == "/some/dir"
        assert args.input is None


class TestHelp:
    def test_help_does_not_raise(self):
        with pytest.raises(SystemExit) as exc_info:
            _parse_args(["--help"])
        assert exc_info.value.code == 0


class TestOutputPath:
    def test_sets_output_path(self):
        args = _parse_args(["video.mp4", "-o", "custom.pdf"])
        assert args.output == "custom.pdf"

    def test_default_output_path(self):
        args = _parse_args(["video.mp4"])
        assert args.output is None
