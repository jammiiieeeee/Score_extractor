"""Capture GUI screenshots for visual inspection."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
import numpy as np

import app_gui
from app_gui import MainWindow
from src.domain.models import Frame


def make_dummy_frames(n: int):
    frames = []
    for i in range(n):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:] = (i * 20) % 256
        frames.append(Frame(img, timestamp=float(i), index=i))
    return frames


def capture(widget, path: Path):
    pixmap = widget.grab()
    pixmap.save(str(path))
    return path


def main():
    output_dir = Path(__file__).resolve().parent / "visual_output"
    output_dir.mkdir(exist_ok=True)

    app = QApplication([])
    app.setStyle("Fusion")
    app.setApplicationName("Score Extractor Test")

    app_gui.CHECK_INDICATOR_PATH = app_gui._generate_check_pixmap()
    app_gui.CHEVRON_PATH = app_gui._generate_chevron_pixmap()
    app_gui.SPIN_UP_PATH = app_gui._generate_spin_arrow_pixmap(up=True)
    app_gui.SPIN_DOWN_PATH = app_gui._generate_spin_arrow_pixmap(up=False)

    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()
    app.processEvents()

    tab = window.extract_tab

    # 1. Initial state
    tab._has_existing_score = False
    tab._video_path = None
    tab._update_state()
    app.processEvents()
    capture(window, output_dir / "01_initial_state.png")
    print("Captured: 01_initial_state.png")

    # 2. Video loaded, ready to extract
    dummy_video = output_dir / "dummy.mp4"
    dummy_video.write_bytes(b"dummy")
    tab._video_path = str(dummy_video)
    tab.project_edit.setText("TestScore")
    tab._update_state()
    app.processEvents()
    capture(window, output_dir / "02_ready_to_extract.png")
    print("Captured: 02_ready_to_extract.png")

    # 3. Extracting (25%)
    tab._busy = True
    tab.progress_bar.setValue(25)
    tab._set_status("Extracting...")
    tab._update_state()
    app.processEvents()
    capture(window, output_dir / "03_extracting_25pct.png")
    print("Captured: 03_extracting_25pct.png")

    # 4. Extracting (75%) with pages detected
    tab.progress_bar.setValue(75)
    tab.page_badge.setText("Pages: 5")
    tab._set_status("Processing frames...")
    tab._log("Page 1 detected")
    tab._log("Page 2 detected")
    tab._log("Page 3 detected")
    tab._log("Page 4 detected")
    tab._log("Page 5 detected")
    app.processEvents()
    capture(window, output_dir / "04_extracting_75pct.png")
    print("Captured: 04_extracting_75pct.png")

    # 5. Extraction complete
    tab._busy = False
    tab._has_existing_score = True
    tab._api.set_pages(make_dummy_frames(10))
    tab._update_state()
    app.processEvents()
    capture(window, output_dir / "05_extraction_complete.png")
    print("Captured: 05_extraction_complete.png")

    # 6. PDF ready
    tab._peak_style = True
    tab._completed_pdf_path = "output/TestScore/TestScore.pdf"
    tab.on_pdf_completed(10)
    app.processEvents()
    capture(window, output_dir / "06_pdf_ready.png")
    print("Captured: 06_pdf_ready.png")

    # 7. Config tab - Basic mode
    tab._api.clear_pages()
    tab._has_existing_score = False
    tab._video_path = None
    tab._update_state()
    window.config_tab._set_mode("basic")
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    capture(window, output_dir / "07_config_basic.png")
    print("Captured: 07_config_basic.png")

    # 8. Config tab - Advanced mode
    window.config_tab._set_mode("advanced")
    app.processEvents()
    capture(window, output_dir / "08_config_advanced.png")
    print("Captured: 08_config_advanced.png")

    # 9. Minimum window size
    window.tabs.setCurrentIndex(0)
    window.resize(window.minimumWidth(), window.minimumHeight())
    tab._update_state()
    app.processEvents()
    capture(window, output_dir / "09_minimum_size.png")
    print("Captured: 09_minimum_size.png")

    # 10. Minimum size with content
    tab._video_path = str(dummy_video)
    tab.project_edit.setText("TestScore")
    tab._update_state()
    app.processEvents()
    capture(window, output_dir / "10_minimum_size_ready.png")
    print("Captured: 10_minimum_size_ready.png")

    # 11. YouTube mode
    tab.yt_radio.setChecked(True)
    tab._on_source_toggled()
    app.processEvents()
    capture(window, output_dir / "11_youtube_mode.png")
    print("Captured: 11_youtube_mode.png")

    # 12. Re-extract mode
    tab.local_radio.setChecked(True)
    tab._on_source_toggled()
    tab._reextract_mode = True
    tab._api.set_pages(make_dummy_frames(5))
    tab._update_state()
    app.processEvents()
    capture(window, output_dir / "12_reextract_mode.png")
    print("Captured: 12_reextract_mode.png")

    window.close()
    print(f"\nAll screenshots saved to: {output_dir}")
    print(f"Total: 12 screenshots")


if __name__ == "__main__":
    main()
