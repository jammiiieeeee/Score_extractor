"""Verify the extraction end to end on a 1080p scan.

Run it on a video that is at least 1080p tall:

    python tools/verify_1080p.py path\\to\\video.mp4

It checks, on a real extraction:

  1. the extraction finishes and finds pages
  2. every strip in the PDF is cut at the row that was measured for its page
  3. the saved score holds one record per page
  4. reopening the score and regenerating gives the same PDF
  5. the review dialog opens, lists every page, and its verdict reaches the PDF
  6. the command line reads the saved score the same way the GUI does

The output is left in the folder given by --out (default: a temporary folder).
The script exits with 1 when a check fails.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication

from src.api.gui_api import GuiApi
from app_gui import ReviewPagesDialog


class Report:
    """The checks, and what they found."""

    def __init__(self):
        self.checks = []

    def add(self, name: str, ok: bool, detail: str = ""):
        self.checks.append((name, ok, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" - {detail}" if detail else ""))
        return ok

    @property
    def failed(self):
        return [c for c in self.checks if not c[1]]


def wait_for_thread(api, timeout=1800.0):
    """Wait for the work the API started in the background to finish."""
    thread = api._extraction_thread or api._pdf_thread
    if thread is not None:
        thread.join(timeout=timeout)
        if thread.is_alive():
            raise RuntimeError("the background work did not finish")
    deadline = time.time() + 30.0
    while time.time() < deadline and api.is_busy():
        time.sleep(0.2)


def pdf_images(pdf_path: Path):
    """The images inside a PDF: (width, height, hash of the pixels)."""
    if not pdf_path.exists():
        return []
    data = pdf_path.read_bytes()
    images = []
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        head = data[max(0, start - 400):start]
        width = re.search(rb"/Width\s+(\d+)", head)
        height = re.search(rb"/Height\s+(\d+)", head)
        if not width or not height:
            continue
        end = data.find(b"endstream", start)
        raw = data[start:end]
        try:
            pixels = zlib.decompress(raw)
        except zlib.error:
            pixels = raw
        images.append((
            int(width.group(1)),
            int(height.group(1)),
            hashlib.sha256(pixels).hexdigest()[:12],
        ))
    return images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="A video that is at least 1080p tall")
    parser.add_argument("--out", default="", help="Where to keep the output")
    parser.add_argument("--score-name", default="v1080")
    parser.add_argument("--start-time", type=float, default=2.0)
    parser.add_argument("--end-offset", type=float, default=0.0,
                        help="Stop this many seconds before the video ends")
    args = parser.parse_args()

    video = Path(args.video)
    if not video.exists():
        print(f"[ERROR] No such video: {video}")
        return 1

    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="verify_1080p_"))
    out.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    capture.release()
    print(f"Video: {video.name} ({width}x{height})")
    print(f"Output: {out}")

    report = Report()

    # 1. The extraction runs and finds pages.
    api = GuiApi()
    api.start_extraction(
        str(video), no_ocr=True, start_time=args.start_time,
        end_offset=args.end_offset, output_folder=str(out),
        score_name=args.score_name,
    )
    wait_for_thread(api)
    phase = api.get_extraction_state().phase
    count = api.get_page_count()
    report.add("the extraction finishes", phase == "done", f"phase {phase}")
    report.add("the extraction finds pages", count > 0, f"{count} pages")
    report.add("the scan is 1080p or better", height >= 1080, f"{width}x{height}")
    if count == 0:
        return 1

    score_dir = out / args.score_name
    pdf = score_dir / f"{args.score_name}.pdf"
    api.generate_pdf(str(pdf))
    wait_for_thread(api)
    images = pdf_images(pdf)
    report.add("the PDF holds every page", len(images) == count,
               f"{len(images)} strips for {count} pages")

    # 2. Every strip is cut at the row that was measured for its page.
    meta = json.loads((score_dir / "metadata.json").read_text(encoding="utf-8-sig"))
    records = meta.get("pages")
    if records is None:
        rows = meta.get("page_boundary_rows") or []
    else:
        rows = [r.get("boundary_row") for r in records]
    report.add("the saved score holds one record per page",
               len(rows) == count, f"{len(rows)} records for {count} pages")
    offset = int(meta.get("boundary_offset_px", 0))
    expected = [int(r) - offset for r in rows if r is not None]
    measured = [h for _, h, _ in images]
    report.add("every strip is cut at its measured row",
               measured == expected, f"strips {measured[:3]} rows {expected[:3]}")

    # 3. Reopening the score and regenerating gives the same PDF.
    reopened = GuiApi()
    api2 = reopened
    api2.load_saved_score(str(score_dir))
    report.add("the score reopens with every page",
               api2.get_page_count() == count, f"{api2.get_page_count()} pages")
    regen = score_dir / "regenerated.pdf"
    api2.regenerate_from_dir(str(score_dir), str(regen))
    wait_for_thread(api2)
    report.add("regenerating gives the same PDF",
               pdf_images(regen) == images)

    # 4. The command line reads the saved score the same way the GUI does.
    cli_pdf = out / "from_dir.pdf"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "main.py"), "--from-dir", str(score_dir),
         "-o", str(cli_pdf)],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    report.add("the command line reads the saved score",
               result.returncode == 0 and cli_pdf.exists(),
               (result.stdout or "").strip().splitlines()[-1] if result.stdout else "")
    if cli_pdf.exists():
        report.add("the command line gives the same PDF",
                   pdf_images(cli_pdf) == images,
                   f"{len(pdf_images(cli_pdf))} strips")

    # 5. The review dialog opens, lists every page, and its verdict reaches the PDF.
    app = QApplication.instance() or QApplication([])
    dialog = ReviewPagesDialog(api2)
    drawn = sum(1 for t in dialog._thumbs
                if t.pixmap() is not None and not t.pixmap().isNull())
    report.add("the review dialog opens and lists every page",
               dialog._count == count and drawn == count,
               f"{dialog._count} pages, {drawn} thumbnails")
    if count > 1:
        dialog._checks[1].setChecked(False)
        removed = [i for i, keep in enumerate(dialog.kept_mask()) if not keep]
        for idx in sorted(removed, reverse=True):
            api2.remove_page(idx)
        reviewed = score_dir / "reviewed.pdf"
        api2.generate_pdf(str(reviewed))
        wait_for_thread(api2)
        kept_images = [img for i, img in enumerate(images) if i not in removed]
        report.add("a page dropped in the review stays out of the PDF",
                   pdf_images(reviewed) == kept_images,
                   f"{len(pdf_images(reviewed))} strips for {count - 1} kept pages")

    print()
    if report.failed:
        print(f"{len(report.failed)} of {len(report.checks)} checks failed:")
        for name, _, detail in report.failed:
            print(f"  - {name} {detail}")
        return 1
    print(f"All {len(report.checks)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
