"""
Disposable script: benchmark video pipeline bottlenecks.

Measures latency of each stage (open, seek, read, resize, diff, ssim, ocr init)
across multiple capture backends.  Run from project root:

    python -m tools.bench_video_bottleneck --video path/to/video.mp4

Use --all-backends to test all supported OpenCV backends.
Use --html to write an HTML report.
"""

import argparse
import gc
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

BACKENDS: List[Tuple[str, int]] = [
    ("CAP_ANY", cv2.CAP_ANY),
]

# NOTE: DSHOW / MSMF / VFW are camera-capture backends, not file decoders.
# They can hang when given a file path — omitted deliberately.

# Try FFMPEG
try:
    BACKENDS.append(("CAP_FFMPEG", cv2.CAP_FFMPEG))
except AttributeError:
    pass

# Try GStreamer
try:
    BACKENDS.append(("CAP_GSTREAMER", cv2.CAP_GSTREAMER))
except AttributeError:
    pass


TARGET_WIDTH = 640
REPEAT_READS = 5


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resize(frame, width=TARGET_WIDTH):
    h, w = frame.shape[:2]
    if w <= width:
        return frame
    target_h = int(h * (width / w))
    return cv2.resize(frame, (width, target_h), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# benchmark results
# ---------------------------------------------------------------------------

@dataclass
class BackendResult:
    name: str
    api_pref: int

    open_ms: float = 0.0
    info: str = ""

    seq_read_ms: List[float] = field(default_factory=list)   # per-frame, first 50
    seek_read_ms: List[float] = field(default_factory=list)   # random-seek + read
    grab_ms: List[float] = field(default_factory=list)        # skip_frames via grab
    full_read_ms: List[float] = field(default_factory=list)   # full-res read

    resize_ms: List[float] = field(default_factory=list)
    ssim_ms: List[float] = field(default_factory=list)
    absdiff_ms: List[float] = field(default_factory=list)

    error: Optional[str] = None


# ---------------------------------------------------------------------------
# individual benchmarks
# ---------------------------------------------------------------------------

def bench_open(path: str, api_pref: int) -> Tuple[float, str, int, int, float, int]:
    """Open video with given backend.  Return (open_ms, info, w, h, fps, total_frames)."""
    t0 = time.perf_counter()
    cap = cv2.VideoCapture(path, api_pref)
    t1 = time.perf_counter()
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Failed to open with api_pref={api_pref}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
    else:
        w = h = 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    cap.release()

    info = f"{w}x{h}  {fps:.2f} fps  {total} frames"
    return (t1 - t0) * 1000, info, w, h, fps, total


def bench_sequential_read(path: str, api_pref: int, count: int = 50) -> List[float]:
    """Sequential cap.read() times for first *count* frames."""
    times: List[float] = []
    cap = cv2.VideoCapture(path, api_pref)
    if not cap.isOpened():
        return times
    for _ in range(count):
        t0 = time.perf_counter()
        ret, _ = cap.read()
        t1 = time.perf_counter()
        if not ret:
            break
        times.append((t1 - t0) * 1000)
    cap.release()
    return times


def bench_seek_read(path: str, api_pref: int, total_frames: int, samples: int = 30) -> List[float]:
    """Random-access seek + read time."""
    if total_frames <= 1:
        return []
    times: List[float] = []
    cap = cv2.VideoCapture(path, api_pref)
    if not cap.isOpened():
        return times
    indices = np.linspace(0, total_frames - 1, samples, dtype=int).tolist()
    for idx in indices:
        t0 = time.perf_counter()
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, _ = cap.read()
        t1 = time.perf_counter()
        if ret:
            times.append((t1 - t0) * 1000)
    cap.release()
    return times


def bench_grab(path: str, api_pref: int, count: int = 100) -> List[float]:
    """Time per cap.grab() call (skip without decode)."""
    times: List[float] = []
    cap = cv2.VideoCapture(path, api_pref)
    if not cap.isOpened():
        return times
    for _ in range(count):
        t0 = time.perf_counter()
        ret = cap.grab()
        t1 = time.perf_counter()
        if not ret:
            break
        times.append((t1 - t0) * 1000)
    cap.release()
    return times


def bench_full_read(path: str, api_pref: int, total_frames: int, samples: int = 30) -> List[float]:
    """Full-resolution read (no resize) — mimics read_full_frame_at."""
    if total_frames <= 1:
        return []
    times: List[float] = []
    cap = cv2.VideoCapture(path, api_pref)
    if not cap.isOpened():
        return times
    indices = np.linspace(0, total_frames - 1, samples, dtype=int).tolist()
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        t0 = time.perf_counter()
        ret, frame = cap.read()
        t1 = time.perf_counter()
        if ret:
            times.append((t1 - t0) * 1000)
    cap.release()
    return times


def bench_processing(path: str, api_pref: int) -> dict:
    """Benchmark downstream processing ops (resize, SSIM, absdiff) on real frames."""
    cap = cv2.VideoCapture(path, api_pref)
    if not cap.isOpened():
        return {}

    # Collect 5 sample frame pairs
    frames_a: List[np.ndarray] = []
    frames_b: List[np.ndarray] = []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total > 10:
        gap = total // 10
        for i in range(5):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i * gap)
            ret_a, fa = cap.read()
            cap.set(cv2.CAP_PROP_POS_FRAMES, i * gap + min(gap, 30))
            ret_b, fb = cap.read()
            if ret_a and ret_b:
                frames_a.append(fa)
                frames_b.append(fb)
    cap.release()

    if not frames_a:
        return {}

    from skimage.metrics import structural_similarity as ssim

    results = {"resize_ms": [], "ssim_ms": [], "absdiff_ms": []}

    for fa, fb in zip(frames_a, frames_b):
        # resize
        t0 = time.perf_counter()
        for _ in range(REPEAT_READS):
            rs = _resize(fa)
        t1 = time.perf_counter()
        results["resize_ms"].append((t1 - t0) / REPEAT_READS * 1000)

        # ssim
        try:
            h, w = fa.shape[:2]
            roi_a = cv2.cvtColor(cv2.resize(fa[0:int(h * 0.34), :], (320, 109)), cv2.COLOR_BGR2GRAY)
            roi_b = cv2.cvtColor(cv2.resize(fb[0:int(h * 0.34), :], (320, 109)), cv2.COLOR_BGR2GRAY)
            t0 = time.perf_counter()
            for _ in range(REPEAT_READS):
                _ = ssim(roi_a, roi_b)
            t1 = time.perf_counter()
            results["ssim_ms"].append((t1 - t0) / REPEAT_READS * 1000)
        except Exception:
            results["ssim_ms"].append(0.0)

        # absdiff (merge_frames style)
        h, w = fa.shape[:2]
        scale = 640 / w
        a_small = cv2.resize(fa, (640, int(h * scale)))
        b_small = cv2.resize(fb, (640, int(h * scale)))
        t0 = time.perf_counter()
        for _ in range(REPEAT_READS):
            diff = cv2.absdiff(a_small, b_small)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _ = np.sum(gray[:int(640 * 0.32), :], axis=0)
        t1 = time.perf_counter()
        results["absdiff_ms"].append((t1 - t0) / REPEAT_READS * 1000)

    return results


# ---------------------------------------------------------------------------
# main runner
# ---------------------------------------------------------------------------

def run_all(path: str, all_backends: bool) -> List[BackendResult]:
    if not os.path.isfile(path):
        print(f"ERROR: file not found: {path}")
        sys.exit(1)

    file_size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"File:  {path}")
    print(f"Size:  {file_size_mb:.1f} MB")
    print(f"{'='*60}\n")

    backends = BACKENDS if all_backends else [("CAP_ANY", cv2.CAP_ANY)]

    results: List[BackendResult] = []

    for name, api_pref in backends:
        print(f"--- Backend: {name} ---")
        res = BackendResult(name=name, api_pref=api_pref)

        try:
            # 1. open
            open_ms, info, w, h, fps, total = bench_open(path, api_pref)
            res.open_ms = open_ms
            res.info = info
            print(f"  open:         {open_ms:7.2f} ms  ({info})")

            # 2. sequential read
            seq = bench_sequential_read(path, api_pref, count=min(50, max(10, total // 10)))
            res.seq_read_ms = seq
            if seq:
                print(f"  seq read:     {np.mean(seq):7.2f} ± {np.std(seq):.2f} ms  (n={len(seq)})")
            else:
                print(f"  seq read:     FAILED")

            # 3. seek + read
            seek = bench_seek_read(path, api_pref, total)
            res.seek_read_ms = seek
            if seek:
                print(f"  seek+read:    {np.mean(seek):7.2f} ± {np.std(seek):.2f} ms  (n={len(seek)})")

            # 4. grab (skip_frames)
            grab = bench_grab(path, api_pref, count=min(100, total))
            res.grab_ms = grab
            if grab:
                print(f"  grab (skip):  {np.mean(grab):7.2f} ± {np.std(grab):.2f} ms  (n={len(grab)})")

            # 5. full-res read
            full = bench_full_read(path, api_pref, total)
            res.full_read_ms = full
            if full:
                print(f"  full read:    {np.mean(full):7.2f} ± {np.std(full):.2f} ms  (n={len(full)})")

            # 6. processing ops
            proc = bench_processing(path, api_pref)
            res.resize_ms = proc.get("resize_ms", [])
            res.ssim_ms = proc.get("ssim_ms", [])
            res.absdiff_ms = proc.get("absdiff_ms", [])

            if res.resize_ms:
                print(f"  resize:       {np.mean(res.resize_ms):7.2f} ± {np.std(res.resize_ms):.2f} ms")
            if res.ssim_ms:
                print(f"  ssim:         {np.mean(res.ssim_ms):7.2f} ± {np.std(res.ssim_ms):.2f} ms")
            if res.absdiff_ms:
                print(f"  absdiff+sum:  {np.mean(res.absdiff_ms):7.2f} ± {np.std(res.absdiff_ms):.2f} ms")

        except RuntimeError as e:
            res.error = str(e)
            print(f"  ERROR: {e}")

        print()
        results.append(res)

    return results


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def print_summary(results: List[BackendResult]):
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    header = f"{'Backend':<16} {'Open':>8} {'SeqRead':>8} {'SeekRd':>8} {'Grab':>8} {'FullRd':>8} {'Resize':>8} {'SSIM':>8} {'Diff':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        def _m(v):
            return f"{np.mean(v):.1f}" if v else "-"
        print(f"{r.name:<16} {_m([r.open_ms]):>8} {_m(r.seq_read_ms):>8} {_m(r.seek_read_ms):>8} {_m(r.grab_ms):>8} {_m(r.full_read_ms):>8} {_m(r.resize_ms):>8} {_m(r.ssim_ms):>8} {_m(r.absdiff_ms):>8}")


def write_html(path: str, results: List[BackendResult]):
    import datetime
    rows = ""
    for r in results:
        def _s(v):
            if not v:
                return "<td>-</td>"
            vals = [float(x) for x in v]
            return f"<td>{np.mean(vals):.2f} &plusmn; {np.std(vals):.2f}</td>"
        rows += f"""
        <tr>
            <td>{r.name}</td>
            <td>{r.open_ms:.2f}</td>
            {_s(r.seq_read_ms)}
            {_s(r.seek_read_ms)}
            {_s(r.grab_ms)}
            {_s(r.full_read_ms)}
            {_s(r.resize_ms)}
            {_s(r.ssim_ms)}
            {_s(r.absdiff_ms)}
            <td>{r.info}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Video Bottleneck Report</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: right; }}
th {{ background: #f5f5f5; }}
td:first-child, th:first-child {{ text-align: left; font-weight: bold; }}
tr:nth-child(even) {{ background: #fafafa; }}
</style></head>
<body>
<h1>Video Bottleneck Report</h1>
<p>Generated: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}</p>
<table>
<thead><tr>
<th>Backend</th><th>Open (ms)</th><th>Seq Read (ms)</th><th>Seek+Read (ms)</th><th>Grab (ms)</th><th>Full Read (ms)</th><th>Resize (ms)</th><th>SSIM (ms)</th><th>AbsDiff (ms)</th><th>Info</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
</body></html>"""
    Path(path).write_text(html, encoding="utf-8")
    print(f"\nHTML report written to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark video pipeline bottlenecks")
    parser.add_argument("--video", "-v", required=True, help="Path to video file")
    parser.add_argument("--all-backends", "-a", action="store_true", help="Test all capture backends")
    parser.add_argument("--html", help="Write HTML report to this path (e.g. report.html)")
    args = parser.parse_args()

    results = run_all(args.video, args.all_backends)

    print_summary(results)

    if args.html:
        write_html(args.html, results)
