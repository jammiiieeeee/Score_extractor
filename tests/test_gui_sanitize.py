"""GUI-side hardening tests for ExtractTab._sanitize alignment."""

import pytest

pytestmark = pytest.mark.unit

from app_gui import ExtractTab
from src.infrastructure.file_service import FileService


class TestExtractTabSanitize:
    def test_matches_file_service_for_regular_names(self):
        names = ["My Score", "Rachmaninoff Op.3", "  padded  ", "a" * 300]
        for name in names:
            assert ExtractTab._sanitize(name) == FileService._sanitize_path_name(name)

    def test_matches_file_service_for_invalid_chars(self):
        for name in ['<>:"/\\|?*', "CON", "con", "AUX.txt", "COM7"]:
            assert ExtractTab._sanitize(name) == FileService._sanitize_path_name(name)

    def test_empty_becomes_untitled(self):
        assert ExtractTab._sanitize("") == "untitled"
        assert ExtractTab._sanitize("   ") == "untitled"
