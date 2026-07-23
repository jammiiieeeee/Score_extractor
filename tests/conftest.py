"""Shared fixtures for the Score_extractor test suite.

Provides synthetic images, stub services conforming to domain interfaces,
and temporary directories — everything needed to write isolated unit tests
without real video files or PaddleOCR.
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.domain.value_objects.config import ScoreConfig
from src.domain.models import Frame
from src.domain.interfaces import (
    IVideoService, IOcrService, IFileService, IPdfService,
    _NoopOcrService,
)
from src.domain.deduplication import Deduplicator
from src.domain.page_store import PageStore


# ── Synthetic image helpers ────────────────────────────────────────────


def make_solid_image(
    width: int = 800,
    height: int = 600,
    color: Tuple[int, int, int] = (128, 128, 128),
) -> np.ndarray:
    """Create a solid-color BGR image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = color
    return img


def make_image_with_text(
    text: str,
    width: int = 800,
    height: int = 600,
    font_scale: float = 2.0,
    bg_color: Tuple[int, int, int] = (240, 240, 240),
    text_color: Tuple[int, int, int] = (30, 30, 30),
) -> np.ndarray:
    """Create an image with text rendered on it (simulates page numbers)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = bg_color
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 3)[0]
    x = max(10, (width - text_size[0]) // 2)
    y = (height + text_size[1]) // 2
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, 3)
    return img


def make_bar_image(
    width: int = 800,
    height: int = 600,
    bar_left: int = 100,
    bar_right: int = 400,
    bar_color: Tuple[int, int, int] = (255, 50, 50),
    bar_top_ratio: float = 0.15,
    bg_color: Tuple[int, int, int] = (200, 200, 200),
) -> np.ndarray:
    """Create an image with a horizontal bar (simulates playback bar)."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = bg_color
    bar_top = int(height * bar_top_ratio)
    bar_bottom = bar_top + max(5, int(height * 0.03))
    img[bar_top:bar_bottom, bar_left:bar_right] = bar_color
    return img


def make_synthetic_frames(n: int = 5, width: int = 800, height: int = 600) -> List[Frame]:
    """Create N distinct frames with different content (different shades)."""
    frames = []
    for i in range(n):
        shade = int(50 + (i * 40) % 200)
        img = make_solid_image(width, height, (shade, shade, shade))
        frames.append(Frame(img, timestamp=float(i) * 3.0, index=i * 30))
    return frames


def make_page_number_frames(n: int = 5, width: int = 800, height: int = 600) -> List[Frame]:
    """Create N frames each with a distinct page number drawn on them."""
    frames = []
    for i in range(1, n + 1):
        img = make_image_with_text(str(i), width, height)
        frames.append(Frame(img, timestamp=float(i) * 3.0, index=i * 30))
    return frames


# ── Fixtures: temporary directories ────────────────────────────────────


@pytest.fixture
def work_dir():
    """Yield a temporary directory, clean up after."""
    d = tempfile.mkdtemp(prefix="score_extractor_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def output_dir(work_dir):
    """A pre-created output subdirectory."""
    d = work_dir / "output"
    d.mkdir()
    return d


@pytest.fixture
def score_dir(output_dir):
    """A pre-created score directory with photos/, debug/, video/ subdirs."""
    d = output_dir / "test_score"
    (d / "photos").mkdir(parents=True)
    (d / "debug").mkdir(parents=True)
    (d / "video").mkdir(parents=True)
    return d


# ── Fixtures: synthetic images and frames ──────────────────────────────


@pytest.fixture
def synthetic_image():
    """A single 800x600 grayscale-ish test image."""
    return make_solid_image(800, 600, (128, 128, 128))


@pytest.fixture
def synthetic_images():
    """5 distinct 800x600 test images."""
    return [make_solid_image(800, 600, (s, s, s)) for s in [50, 100, 150, 200, 250]]


@pytest.fixture
def page_frames():
    """5 frames with page numbers 1-5 drawn on them."""
    return make_page_number_frames(5)


@pytest.fixture
def synthetic_frames():
    """5 distinct frames with different content."""
    return make_synthetic_frames(5)


# ── Fixtures: config ───────────────────────────────────────────────────


@pytest.fixture
def config():
    """Default ScoreConfig."""
    return ScoreConfig()


@pytest.fixture
def config_overrides():
    """Factory fixture: returns a function that creates ScoreConfig with overrides."""

    def _make(**kwargs) -> ScoreConfig:
        return ScoreConfig(**kwargs)

    return _make


# ── Fixtures: stub services (implement domain interfaces) ──────────────


class StubVideoService(IVideoService):
    """In-memory video service backed by a list of frames."""

    def __init__(self, frames: Optional[List[np.ndarray]] = None, fps: float = 30.0):
        self._frames = frames or []
        self._fps = fps
        self._idx = 0
        self._orig_w = self._frames[0].shape[1] if self._frames else 800
        self._orig_h = self._frames[0].shape[0] if self._frames else 600

    def open_video(self, video_path: str) -> None:
        self._idx = 0

    def get_fps(self) -> float:
        return self._fps

    def get_original_size(self):
        return self._orig_w, self._orig_h

    def get_total_frames(self) -> int:
        return len(self._frames)

    def read_frames(self):
        for i, f in enumerate(self._frames):
            yield f, i / self._fps, i

    def read_frame_at(self, frame_idx: int):
        if 0 <= frame_idx < len(self._frames):
            return self._frames[frame_idx], frame_idx / self._fps
        return None, None

    def read_next_frame(self):
        if self._idx < len(self._frames):
            frame = self._frames[self._idx]
            ts = self._idx / self._fps
            idx = self._idx
            self._idx += 1
            return frame, ts, idx
        return None, None, None

    def skip_frames(self, count: int):
        self._idx = min(self._idx + count, len(self._frames))

    def read_full_frame_at(self, frame_idx: int):
        return self.read_frame_at(frame_idx)

    def merge_frames(self, frame_a, frame_b, overlay_width_ratio=0.5, crop_ratio=0.35,
                     min_diff_threshold=500.0, bar_padding_px=-15, debug_save_path=None):
        # Simplified: just return frame_a copy with merge_x info
        merge_x = frame_a.shape[1] // 2
        result = frame_a.copy()
        result[:, 0:merge_x] = frame_b[:, 0:merge_x]
        return result, merge_x, merge_x // 2

    def close(self) -> None:
        pass


class StubOcrService(IOcrService):
    """Stub OCR that returns controlled results."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._leftmost_numbers = {}  # image_id -> number
        self._keywords_found = False
        self._texts = []

    def set_leftmost_number(self, img_id: int, number: Optional[int]):
        self._leftmost_numbers[img_id] = number

    def set_keywords_found(self, found: bool):
        self._keywords_found = found

    def set_texts(self, texts: List[str]):
        self._texts = texts

    def initialize(self) -> bool:
        return self._enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def get_leftmost_number(self, image, vertical_range, horizontal_ratio=1.0, confidence_threshold=0):
        key = id(image)
        if key in self._leftmost_numbers:
            return self._leftmost_numbers[key]
        return None

    def detect_keywords(self, image, keywords):
        return self._keywords_found

    def get_texts(self, image):
        return self._texts


class StubFileService(IFileService):
    """In-memory file service backed by a temp directory."""

    def __init__(self, base_dir: Path):
        self._base = base_dir

    def prepare_output_dir(self, output_folder: str, score_name: str) -> Path:
        score_dir = Path(output_folder) / score_name
        (score_dir / "photos").mkdir(parents=True, exist_ok=True)
        (score_dir / "video").mkdir(parents=True, exist_ok=True)
        (score_dir / "debug").mkdir(parents=True, exist_ok=True)
        return score_dir

    def save_page_image(self, score_dir: Path, page_num: int, image: np.ndarray) -> Path:
        path = score_dir / "photos" / f"page_{page_num:03d}_merged.png"
        success, buf = cv2.imencode(".png", image)
        if success:
            buf.tofile(str(path))
        return path

    def load_page_images(self, score_dir: Path) -> List[np.ndarray]:
        files = sorted(
            (score_dir / "photos").glob("page_*_merged.png"),
            key=lambda f: int(f.stem.split("_")[1]),
        )
        images = []
        for f in files:
            file_bytes = np.fromfile(str(f), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                images.append(img)
        return images

    def list_saved_scores(self, output_folder: str) -> List[dict]:
        results = []
        base = Path(output_folder)
        if not base.exists():
            return results
        for d in base.iterdir():
            if d.is_dir() and (d / "photos").is_dir():
                page_files = sorted(d.glob("photos/page_*_merged.png"))
                results.append({
                    "path": str(d),
                    "page_count": len(page_files),
                    "score_name": d.name,
                })
        results.sort(key=lambda x: x["score_name"])
        return results


class StubPdfService(IPdfService):
    """Stub PDF service that records calls."""

    def __init__(self):
        self.calls = []

    def create_pdf(self, images, output_path, config, title_hint=""):
        self.calls.append({
            "images": images,
            "output_path": output_path,
            "config": config,
            "title_hint": title_hint,
        })


# ── Fixtures: stub service instances ───────────────────────────────────


@pytest.fixture
def stub_video_service(synthetic_frames):
    """A StubVideoService pre-loaded with 5 synthetic frames."""
    frames = [f.image for f in synthetic_frames]
    return StubVideoService(frames, fps=30.0)


@pytest.fixture
def stub_ocr_service():
    """A default-enabled StubOcrService."""
    return StubOcrService(enabled=True)


@pytest.fixture
def stub_ocr_disabled():
    """A disabled StubOcrService."""
    return StubOcrService(enabled=False)


@pytest.fixture
def stub_file_service(work_dir):
    """A StubFileService rooted in the test work directory."""
    return StubFileService(work_dir)


@pytest.fixture
def stub_pdf_service():
    """A StubPdfService that records calls."""
    return StubPdfService()


@pytest.fixture
def noop_ocr():
    """The built-in _NoopOcrService."""
    return _NoopOcrService()


@pytest.fixture
def deduplicator(config, stub_ocr_service):
    """A Deduplicator with default config and stub OCR."""
    return Deduplicator(config, stub_ocr_service)


@pytest.fixture
def deduplicator_no_ocr(config, noop_ocr):
    """A Deduplicator with OCR disabled."""
    return Deduplicator(config, noop_ocr)
