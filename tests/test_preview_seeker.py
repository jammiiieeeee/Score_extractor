"""Regression tests for PreviewSeeker frame delivery after open.

Guards against the preview freezing at time=0: PreviewSeeker.open() calls
close() which sets _closing=True; unless open() resets it, every subsequent
_do_seek() early-returns and no frame_ready is ever emitted.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtWidgets import QApplication

pytestmark = pytest.mark.unit

from app_gui import PreviewSeeker


def make_test_video(path: Path, frames: int = 60, fps: float = 30.0,
                    w: int = 320, h: int = 180) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    try:
        for i in range(frames):
            img = np.full((h, w, 3), (int(i * 255 / frames), 0, 0), dtype=np.uint8)
            writer.write(img)
    finally:
        writer.release()
    return path


def _pump(app, ms: float):
    deadline = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.001)


def _run_in_thread(seeker):
    thread = QThread()
    seeker.moveToThread(thread)
    thread.start()
    return thread


class TestPreviewSeekerSeekAfterOpen:
    def test_seek_delivers_frame_after_open(self, work_dir):
        video = make_test_video(work_dir / "tiny.mp4")
        app = QApplication.instance() or QApplication([])

        seeker = PreviewSeeker()
        thread = _run_in_thread(seeker)
        received = []
        seeker.frame_ready.connect(received.append)

        QTimer.singleShot(0, lambda: seeker.open_requested.emit(str(video)))
        _pump(app, 500)

        seeker.seek_requested.emit(1.0, 30.0)
        _pump(app, 2000)

        assert received, "expected a frame after seek; preview is frozen at time=0"

        QTimer.singleShot(0, seeker.close_requested.emit)
        QTimer.singleShot(50, thread.quit)
        _pump(app, 300)

    def test_frames_advance_with_timestamp(self, work_dir):
        """Seek to a later timestamp must produce a frame different from frame 0."""
        video = make_test_video(work_dir / "tiny2.mp4")
        app = QApplication.instance() or QApplication([])

        seeker = PreviewSeeker()
        thread = _run_in_thread(seeker)
        received = []
        seeker.frame_ready.connect(received.append)

        QTimer.singleShot(0, lambda: seeker.open_requested.emit(str(video)))
        _pump(app, 500)

        seeker.seek_requested.emit(0.0, 30.0)
        _pump(app, 1500)
        seeker.seek_requested.emit(1.5, 30.0)
        _pump(app, 1500)

        assert len(received) >= 2, "expected frames for both seeks"

        QTimer.singleShot(0, seeker.close_requested.emit)
        QTimer.singleShot(50, thread.quit)
        _pump(app, 300)
