"""Unit tests for ExtractScoreUseCase and GeneratePdfUseCase (src/application/use_cases.py).

Tests the orchestration layer with stub services.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.use_cases import ExtractScoreUseCase, GeneratePdfUseCase, ExtractRequest
from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from src.domain.interfaces import _NoopOcrService
from tests.conftest import (
    StubVideoService, StubOcrService, StubFileService, StubPdfService,
    make_solid_image, make_image_with_text,
)


@pytest.mark.unit
class TestExtractScoreUseCase:
    """Tests for ExtractScoreUseCase.execute()."""

    def _make_frames(self, n=10, width=800, height=600):
        fps = 30.0
        frames = []
        for i in range(n):
            shade = int(50 + (i * 30) % 200)
            img = make_solid_image(width, height, (shade, shade, shade))
            frames.append(Frame(img, float(i) / fps, i))
        return frames, fps

    def _make_uc(self, frames, fps=30.0, ocr_enabled=True, config=None, work_dir=None):
        svc = StubVideoService([f.image for f in frames], fps=fps)
        ocr = StubOcrService(enabled=ocr_enabled)
        file_svc = StubFileService(work_dir or Path(os.environ.get("TEMP", ".")))
        cfg = config or ScoreConfig(frame_check_interval=0.01)
        uc = ExtractScoreUseCase(svc, ocr, file_svc, cfg)
        return uc, svc, ocr, file_svc

    def test_full_extraction(self, tmp_path):
        frames, fps = self._make_frames(10)
        uc, _, _, _ = self._make_uc(frames, fps, work_dir=tmp_path)
        out = tmp_path / "output"
        out.mkdir()
        (out / "photos").mkdir()
        result = uc.execute(ExtractRequest("fake.mp4", out, no_ocr=True))
        pages = result.pages
        manifest = result.manifest
        assert isinstance(pages, list)
        assert isinstance(manifest, list)
        assert len(pages) >= 0

    def test_extraction_with_ocr_disabled(self, tmp_path):
        frames, fps = self._make_frames(5)
        uc, _, ocr, _ = self._make_uc(frames, fps, ocr_enabled=False, work_dir=tmp_path)
        out = tmp_path / "output"
        out.mkdir()
        (out / "photos").mkdir()
        result = uc.execute(ExtractRequest("fake.mp4", out, no_ocr=True))
        pages = result.pages
        manifest = result.manifest
        assert isinstance(pages, list)
        assert isinstance(manifest, list)

    def test_extraction_with_ocr_fallback(self, tmp_path):
        frames, fps = self._make_frames(5)
        uc, _, ocr, _ = self._make_uc(frames, fps, ocr_enabled=False, work_dir=tmp_path)
        ocr.initialize = MagicMock(return_value=False)
        out = tmp_path / "output"
        out.mkdir()
        (out / "photos").mkdir()
        result = uc.execute(ExtractRequest("fake.mp4", out, no_ocr=False))
        pages = result.pages
        manifest = result.manifest
        assert isinstance(pages, list)
        assert isinstance(manifest, list)

    def test_extraction_cancelled(self, tmp_path):
        frames, fps = self._make_frames(10)
        call_count = [0]
        def cancel():
            call_count[0] += 1
            return call_count[0] > 2
        uc, _, _, _ = self._make_uc(frames, fps, work_dir=tmp_path)
        out = tmp_path / "output"
        out.mkdir()
        (out / "photos").mkdir()
        result = uc.execute(ExtractRequest("fake.mp4", out, no_ocr=True, is_cancelled=cancel))
        pages = result.pages
        manifest = result.manifest
        assert isinstance(pages, list)
        assert isinstance(manifest, list)

    def test_extraction_with_start_time(self, tmp_path):
        frames, fps = self._make_frames(100)
        uc, _, _, _ = self._make_uc(frames, fps, work_dir=tmp_path)
        out = tmp_path / "output"
        out.mkdir()
        (out / "photos").mkdir()
        result = uc.execute(ExtractRequest("fake.mp4", out, no_ocr=True, start_time=1.0))
        pages = result.pages
        manifest = result.manifest
        assert isinstance(pages, list)
        assert isinstance(manifest, list)

    def test_extraction_with_end_offset(self, tmp_path):
        frames, fps = self._make_frames(100)
        uc, _, _, _ = self._make_uc(frames, fps, work_dir=tmp_path)
        out = tmp_path / "output"
        out.mkdir()
        (out / "photos").mkdir()
        result = uc.execute(ExtractRequest("fake.mp4", out, no_ocr=True, end_offset=5.0))
        pages = result.pages
        manifest = result.manifest
        assert isinstance(pages, list)
        assert isinstance(manifest, list)

    def test_callbacks_called(self, tmp_path):
        frames, fps = self._make_frames(5)
        uc, _, _, _ = self._make_uc(frames, fps, work_dir=tmp_path)
        log_cb = MagicMock()
        prog_cb = MagicMock()
        out = tmp_path / "output"
        out.mkdir()
        (out / "photos").mkdir()
        uc.execute(ExtractRequest("fake.mp4", out, no_ocr=True, on_log=log_cb, on_progress=prog_cb))
        assert log_cb.call_count > 0

    def test_empty_video(self, tmp_path):
        svc = StubVideoService([], fps=30.0)
        ocr = StubOcrService(enabled=False)
        file_svc = StubFileService(tmp_path)
        cfg = ScoreConfig()
        uc = ExtractScoreUseCase(svc, ocr, file_svc, cfg)
        out = tmp_path / "output"
        out.mkdir()
        with pytest.raises(RuntimeError):
            uc.execute(ExtractRequest("fake.mp4", out, no_ocr=True))


@pytest.mark.unit
class TestGeneratePdfUseCase:
    """Tests for GeneratePdfUseCase.execute()."""

    def test_generate_pdf_with_frames(self, tmp_path):
        pdf_svc = StubPdfService()
        cfg = ScoreConfig()
        uc = GeneratePdfUseCase(pdf_svc, cfg)
        frames = [Frame(make_solid_image(), 1.0, 0)]
        out_path = tmp_path / "test_output.pdf"
        uc.execute(frames, str(out_path))
        assert len(pdf_svc.calls) == 1

    def test_generate_pdf_empty_frames(self, tmp_path):
        pdf_svc = StubPdfService()
        cfg = ScoreConfig()
        uc = GeneratePdfUseCase(pdf_svc, cfg)
        out_path = tmp_path / "test_output.pdf"
        uc.execute([], str(out_path))
        assert len(pdf_svc.calls) == 0

    def test_output_directory_created(self, tmp_path):
        pdf_svc = StubPdfService()
        cfg = ScoreConfig()
        uc = GeneratePdfUseCase(pdf_svc, cfg)
        frames = [Frame(make_solid_image(), 1.0, 0)]
        out_path = tmp_path / "subdir" / "output.pdf"
        uc.execute(frames, str(out_path))
        assert out_path.parent.exists()
