"""The command line reads a saved score the way the GUI does.

The command line used to open a score directory as a pile of images and crop
every page with the flat ratio.  The boundary measured during extraction was
thrown away, so every page of the PDF lost its bottom: on a 480-row frame the
flat ratio kept 153 rows, where the boundary sat at 200.

These tests drive the real command line and compare it with the GUI.
"""

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

import main
from src.api.gui_api import GuiApi
from src.domain.models import Page
from src.domain.page_crop import crop_page
from src.domain.value_objects.config import ScoreConfig
from src.infrastructure.pdf_service import PdfService


FRAME_HEIGHT = 480
FRAME_WIDTH = 120
BOUNDARY_ROW = 200


def _write_score(score_dir: Path, rows, records: bool = True):
    """A score directory: page images, and the records of those pages."""
    photos = score_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)

    for i, row in enumerate(rows):
        img = np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), 250, dtype=np.uint8)
        img[:row or 0, :] = 10
        cv2.imwrite(str(photos / f"page_{i:03d}_merged.png"), img)

    metadata = {
        "crop_ratio": 0.32,
        "boundary_mode": "auto",
        "boundary_offset_px": 0,
    }
    if records:
        metadata["pages"] = [
            {"attempt": i + 1, "boundary_row": row, "status": "keep"}
            for i, row in enumerate(rows)
        ]
    else:
        metadata["page_boundary_rows"] = list(rows)
    (score_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return metadata


def _run_cli(*args):
    """Run the command line with the given arguments.

    The command line sets the console to UTF-8 when it starts.  Under the
    test runner that call also reaches the runner's own capture, which then
    refuses to read anything that is not UTF-8 - so the streams are put back.
    """
    saved = [(s, s.encoding, s.errors)
             for s in (sys.stdout, sys.stderr, sys.stdin)
             if hasattr(s, "reconfigure")]
    try:
        with patch.object(sys, "argv", ["main.py", *args]):
            main.main()
    finally:
        for stream, encoding, errors in saved:
            try:
                stream.reconfigure(encoding=encoding, errors=errors)
            except Exception:
                pass


@pytest.fixture
def pdf_calls(monkeypatch):
    """The pages the command line hands to the PDF service."""
    calls = {}

    def fake_create_pdf(self, pages, output_path, config, title_hint=""):
        calls["pages"] = pages
        calls["config"] = config
        calls["output_path"] = output_path

    monkeypatch.setattr(PdfService, "create_pdf", fake_create_pdf)
    return calls


def _cli(*args, config_path="no_config.json"):
    """Run the command line without a config file (so the defaults are used)."""
    _run_cli(*args, "-c", config_path)


class TestCommandLineReadsTheSavedScore:
    """The command line uses the pages the score was saved with."""

    def test_the_pages_carry_the_measured_boundary(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [BOUNDARY_ROW])

        _cli("--from-dir", str(score_dir))

        assert len(pdf_calls["pages"]) == 1
        assert pdf_calls["pages"][0].boundary_row == BOUNDARY_ROW

    def test_the_pdf_keeps_the_bottom_of_the_score(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [BOUNDARY_ROW])

        _cli("--from-dir", str(score_dir))

        page = pdf_calls["pages"][0]
        strip = crop_page(page, pdf_calls["config"])
        assert strip.shape[0] == BOUNDARY_ROW
        # the flat ratio would have cut the page off here
        assert strip.shape[0] > int(FRAME_HEIGHT * 0.32)

    def test_a_score_saved_before_the_records_still_works(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [BOUNDARY_ROW], records=False)

        _cli("--from-dir", str(score_dir))

        page = pdf_calls["pages"][0]
        assert page.boundary_row == BOUNDARY_ROW
        assert crop_page(page, pdf_calls["config"]).shape[0] == BOUNDARY_ROW

    def test_a_score_without_a_boundary_falls_back_to_the_ratio(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [None])

        _cli("--from-dir", str(score_dir))

        page = pdf_calls["pages"][0]
        assert page.boundary_row is None
        assert crop_page(page, pdf_calls["config"]).shape[0] == int(FRAME_HEIGHT * 0.32)

    def test_a_ratio_on_the_command_line_wins(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [None])

        _cli("--from-dir", str(score_dir), "--crop-ratio", "0.25")

        config = pdf_calls["config"]
        assert config.default_crop_ratio == 0.25
        page = pdf_calls["pages"][0]
        assert crop_page(page, config).shape[0] == int(FRAME_HEIGHT * 0.25)

    def test_the_saved_crop_is_used(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [None])
        metadata = json.loads((score_dir / "metadata.json").read_text(encoding="utf-8"))
        metadata["crop_ratio"] = 0.5
        (score_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

        _cli("--from-dir", str(score_dir))

        config = pdf_calls["config"]
        assert config.default_crop_ratio == 0.5
        assert config.boundary_mode == "auto"


class TestTheCommandLinePdf:
    """The PDF the command line writes holds the whole page."""

    def test_the_pdf_holds_the_whole_page(self, tmp_path):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [BOUNDARY_ROW])

        _cli("--from-dir", str(score_dir))

        data = (score_dir / "score.pdf").read_bytes()
        heights = re.findall(rb"/Height\s+(\d+)", data)
        assert heights, "the PDF holds no image"
        # the flat ratio would have put 153 rows in here
        assert int(heights[0]) == BOUNDARY_ROW


class TestCommandLineAndGuiAgree:
    """The command line and the GUI read a score the same way."""

    def test_both_read_the_same_pages(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [BOUNDARY_ROW, 240])

        _cli("--from-dir", str(score_dir))
        cli_pages = pdf_calls["pages"]
        cli_config = pdf_calls["config"]

        api = GuiApi()
        api.load_saved_score(str(score_dir))
        gui_config = ScoreConfig(**api.get_config())
        gui_pages = [api.get_page(i) for i in range(api.get_page_count())]

        assert len(gui_pages) == len(cli_pages)
        for cli_page, gui_page in zip(cli_pages, gui_pages):
            assert cli_page.boundary_row == gui_page.boundary_row
            cli_strip = crop_page(cli_page, cli_config)
            gui_strip = crop_page(
                Page(image=gui_page.image, boundary_row=gui_page.boundary_row),
                gui_config,
            )
            assert np.array_equal(cli_strip, gui_strip)

    def test_both_use_the_same_crop(self, tmp_path, pdf_calls):
        score_dir = tmp_path / "score"
        _write_score(score_dir, [BOUNDARY_ROW])

        _cli("--from-dir", str(score_dir))

        api = GuiApi()
        api.load_saved_score(str(score_dir))

        assert api.get_config()["default_crop_ratio"] == pdf_calls["config"].default_crop_ratio
        assert api.get_config()["boundary_mode"] == pdf_calls["config"].boundary_mode
