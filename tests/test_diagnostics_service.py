"""Unit tests for DiagnosticsService (src/infrastructure/diagnostics_service.py).

Covers generate_html_report with various manifest/log combinations.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.infrastructure.diagnostics_service import generate_html_report


def _make_entry(page, is_duplicate=False, bar_x=100, bar_width=200,
                timestamp=10.0, attempt_duration_ms=500, ssim_score=0.8,
                guard_rail_passed=True):
    return {
        "page": page,
        "timestamp": timestamp,
        "bar_x": bar_x,
        "bar_width": bar_width,
        "is_duplicate": is_duplicate,
        "guard_rail_passed": guard_rail_passed,
        "attempt_duration_ms": attempt_duration_ms,
        "ssim_score": ssim_score,
    }


@pytest.mark.unit
class TestDiagnosticsServiceReturnsNone:

    def test_returns_none_when_no_manifest(self, work_dir):
        result = generate_html_report(work_dir)
        assert result is None

    def test_returns_none_when_manifest_empty(self, work_dir):
        (work_dir / "page_manifest.json").write_text("[]", encoding="utf-8")
        result = generate_html_report(work_dir)
        assert result is None


@pytest.mark.unit
class TestDiagnosticsServiceGeneratesHTML:

    def test_generates_html_file(self, work_dir):
        manifest = [_make_entry(1), _make_entry(2)]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        assert result is not None
        assert result.exists()
        assert result.name == "extraction_debug_charts.html"

    def test_html_contains_page_stats(self, work_dir):
        manifest = [_make_entry(1), _make_entry(2), _make_entry(3)]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        html = result.read_text(encoding="utf-8")
        assert "Pages Extracted" in html
        assert "Hit Rate" in html
        assert "Total Attempts" in html

    def test_no_log_file_still_generates(self, work_dir):
        manifest = [_make_entry(1)]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        assert result is not None

    def test_attempts_json_embedded_in_html(self, work_dir):
        manifest = [_make_entry(1, bar_x=150), _make_entry(2, bar_x=250)]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        html = result.read_text(encoding="utf-8")
        assert "150" in html
        assert "250" in html


@pytest.mark.unit
class TestDiagnosticsServiceRejectionReasons:

    def test_rejection_reasons_bar_profile_from_log(self, work_dir):
        manifest = [_make_entry(1, is_duplicate=True)]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (work_dir / "extraction.log").write_text(
            "Page 1: No clean bar profile, treated as duplicate\n", encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        html = result.read_text(encoding="utf-8")
        assert "bar_profile" in html or "BAR PROFILE" in html

    def test_rejection_reasons_left_spike_from_log(self, work_dir):
        manifest = [_make_entry(1, is_duplicate=True)]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (work_dir / "extraction.log").write_text(
            "Page 1: Left spike outside margin, treated as duplicate\n", encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        html = result.read_text(encoding="utf-8")
        assert "left_spike" in html or "LEFT SPIKE" in html

    def test_duplicates_without_log_reason_default_pixel_sim(self, work_dir):
        manifest = [_make_entry(1, is_duplicate=True)]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        # No log file → duplicate without log reason → pixel_sim
        result = generate_html_report(work_dir)
        html = result.read_text(encoding="utf-8")
        assert "pixel_sim" in html or "PIXEL SIM" in html

    def test_hit_rate_calculation(self, work_dir):
        # 3 accepted + 2 rejected = 5 total, hit rate = 60%
        manifest = [
            _make_entry(1, is_duplicate=False, timestamp=1.0),
            _make_entry(2, is_duplicate=True, timestamp=2.0),
            _make_entry(3, is_duplicate=False, timestamp=3.0),
            _make_entry(4, is_duplicate=True, timestamp=4.0),
            _make_entry(5, is_duplicate=False, timestamp=5.0),
        ]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        html = result.read_text(encoding="utf-8")
        assert "60%" in html

    def test_total_time_string_format(self, work_dir):
        manifest = [
            _make_entry(1, timestamp=5.0, attempt_duration_ms=1000),
            _make_entry(2, timestamp=70.0, attempt_duration_ms=500),
        ]
        (work_dir / "page_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        result = generate_html_report(work_dir)
        html = result.read_text(encoding="utf-8")
        assert "m " in html  # "Xm XXs" format
