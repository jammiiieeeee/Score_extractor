"""
Benchmark burst-seek latency across a codec x resolution x fps matrix.
Produces an HTML report with color-coded results and next-step recommendations.

Usage:
    python tools/bench_codec_matrix.py
"""
import sys, os, time, json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

import cv2
import numpy as np

TEST_VIDEOS = [
    ("H.264  640x360  30fps",  "yt_dl/d8TZhL7dvao.mp4"),
    ("H.264  854x480  30fps",  "yt_dl/bench_h264_480p30.mp4"),
    ("H.264 1280x720  60fps",  "yt_dl/bench_h264_720p60.mp4"),
    ("VP9    640x360  30fps",  "yt_dl/bench_vp9_360p30.webm"),
    ("VP9   1280x720  60fps",  "yt_dl/bench_vp9_720p60.webm"),
    ("VP9   1920x1080 60fps",  "yt_dl/bench_vp9_1080p60.webm"),
    ("AV1    640x360  30fps",  "yt_dl/bench_av1_360p30.mp4"),
    ("AV1   1280x720  60fps",  "yt_dl/bench_av1_720p60.mp4"),
    ("AV1   1920x1080 60fps",  "yt_dl/backnumber_1080p.f399.mp4"),
]

BURST_N = 20
SINGLE_SEEKS = 20


def _poll(app, ms):
    deadline = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.001)


def _wait_frame(app, recv_list, t0, timeout=5.0):
    deadline = t0 + timeout
    while not recv_list and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.001)


def probe(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {}
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    codec = "".join(chr((fourcc >> 8 * i) & 0xFF) for i in range(4))
    info = dict(
        codec=codec,
        w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        fps=round(cap.get(cv2.CAP_PROP_FPS), 2),
        frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        container=Path(path).suffix,
        mb=round(os.path.getsize(path) / (1024 * 1024), 1),
    )
    cap.release()
    return info


@dataclass
class BenchResult:
    label: str = ""
    path: str = ""
    meta: dict = field(default_factory=dict)
    single_ms: float = 0.0
    cold_ms: float = 0.0
    burst_p50: float = 0.0
    burst_p95: float = 0.0
    burst_p99: float = 0.0
    burst_max: float = 0.0
    stale: int = 0
    error: str = ""


def run_bench(label, path):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QThread, QTimer
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import importlib, app_gui

    app = QApplication.instance() or QApplication(sys.argv)
    importlib.reload(app_gui)
    PreviewSeeker = app_gui.PreviewSeeker

    meta = probe(path)
    total_frames = meta.get("frames", 0)
    fps = meta.get("fps", 30.0)
    if total_frames < 2:
        return BenchResult(label=label, path=path, meta=meta, error="too few frames")

    result = BenchResult(label=label, path=path, meta=meta)

    seeker = PreviewSeeker()
    thread = QThread()
    seeker.moveToThread(thread)
    thread.start()
    QTimer.singleShot(0, lambda: seeker.open(path))
    _poll(app, 1000)

    timestamps = np.linspace(0.5, max(0.5, total_frames / fps - 0.5), SINGLE_SEEKS).tolist()
    single_times = []
    for ts in timestamps:
        recv = []
        seeker.frame_ready.connect(lambda img: recv.append(time.perf_counter()))
        t0 = time.perf_counter()
        seeker.seek_requested.emit(ts, fps)
        _wait_frame(app, recv, t0, 5.0)
        if recv:
            single_times.append((recv[0] - t0) * 1000)
        seeker.frame_ready.disconnect()

    if single_times:
        result.single_ms = float(np.mean(single_times))
        result.cold_ms = single_times[0]

    recv_burst = []
    seeker.frame_ready.connect(lambda img: recv_burst.append(time.perf_counter()))
    burst_ts = np.linspace(0.5, max(0.5, total_frames / fps - 0.5), BURST_N).tolist()
    t0 = time.perf_counter()
    for ts in burst_ts:
        seeker.seek_requested.emit(ts, fps)
    _poll(app, 8000)
    seeker.frame_ready.disconnect()

    burst_times = sorted((t - t0) * 1000 for t in recv_burst)
    result.stale = BURST_N - len(burst_times)
    if burst_times:
        arr = np.array(burst_times)
        result.burst_p50 = float(np.percentile(arr, 50))
        result.burst_p95 = float(np.percentile(arr, 95))
        result.burst_p99 = float(np.percentile(arr, 99))
        result.burst_max = float(np.max(arr))

    QTimer.singleShot(0, seeker.close)
    QTimer.singleShot(50, thread.quit)
    _poll(app, 300)

    return result


def write_html(results, out_path):
    rows = ""
    over100_rows = []
    for r in results:
        m = r.meta
        over = r.burst_p50 > 100
        if over:
            over100_rows.append(r)
        tr_cls = ' class="warn"' if over else ""
        err_badge = f'<span class="err">ERROR: {r.error}</span>' if r.error else ""
        hot = " hot" if over else ""

        def fmt(v):
            return f"{v:.1f}" if not r.error else "-"

        rows += (
            f'<tr{tr_cls}>'
            f'<td class="label">{r.label}</td>'
            f"<td>{m.get('codec','?')}</td>"
            f"<td>{m.get('w','?')}x{m.get('h','?')}</td>"
            f'<td class="num">{m.get("fps","?")}</td>'
            f"<td>{m.get('container','?')}</td>"
            f'<td class="num">{m.get("mb","?")}</td>'
            f'<td class="num">{m.get("frames","?")}</td>'
            f'<td class="num">{fmt(r.cold_ms)}</td>'
            f'<td class="num">{fmt(r.single_ms)}</td>'
            f'<td class="num {hot}">{fmt(r.burst_p50)}</td>'
            f'<td class="num {hot}">{fmt(r.burst_p95)}</td>'
            f'<td class="num">{fmt(r.burst_p99)}</td>'
            f'<td class="num">{fmt(r.burst_max)}</td>'
            f'<td class="num">{r.stale}/{BURST_N if not r.error else "?"}</td>'
            f"<td>{err_badge}</td>"
            "</tr>\n"
        )

    if over100_rows:
        ns = "<h2>Combinations Over 100 ms &mdash; Recommended Next Steps</h2>\n<ul>\n"
        seen = set()
        for r in over100_rows:
            key = (r.meta.get("codec"), r.meta.get("w"), r.meta.get("h"), r.meta.get("fps"))
            if key in seen:
                continue
            seen.add(key)
            codec = r.meta.get("codec", "?")
            res = f"{r.meta.get('w')}x{r.meta.get('h')}"
            fps_v = r.meta.get("fps", "?")
            ns += f'<li><strong>{r.label}</strong> ({codec} {res} @{fps_v}fps) &mdash; p50 = {r.burst_p50:.0f} ms<br>\n'
            if codec in ("AV01",):
                ns += (
                    "<em>Root cause:</em> AV1 intra-frame decode is CPU-heavy at high resolution. "
                    "The current pipeline <strong>has no codec-aware mitigation</strong>.<br>"
                    "<em>Action:</em> (a) Add a low-res preview decode pass (FFmpeg <code>-vf scale=640:-2</code>). "
                    "(b) Consider pre-transcoding to H.264 for thumbnail/seek use. "
                    "(c) Use FFmpeg keyframe-only seek (<code>-ss</code> before <code>-i</code>) for AV1 content.</li>\n"
                )
            elif codec == "VP90":
                ns += (
                    "<em>Root cause:</em> VP9 is a royalty-free codec with slower decode than H.264. "
                    "The current pipeline <strong>has no codec-aware mitigation</strong>.<br>"
                    "<em>Action:</em> (a) Same low-res preview decode pass as above. "
                    "(b) VP9 keyframe intervals are longer by default &mdash; verify keyframe-rich source. "
                    "(c) Consider FFmpeg <code>-c:v copy -ss</code> for fast keyframe seek.</li>\n"
                )
            elif r.meta.get("w", 0) >= 1920 or r.meta.get("h", 0) >= 1080:
                ns += (
                    "<em>Root cause:</em> Full-resolution decode at 1080p+ is inherently slow. "
                    "The current pipeline <strong>has no resolution-aware preview tier</strong>.<br>"
                    "<em>Action:</em> (a) Add a low-res decode pass (640px width) for preview. "
                    "(b) Use FFmpeg <code>-vf scale=640:-2</code> in the extraction worker.</li>\n"
                )
            else:
                ns += (
                    "<em>Root cause:</em> Latency is borderline. The pipeline's latest-wins "
                    "coalescing <strong>already mitigates</strong> most burst overhead.<br>"
                    "<em>Action:</em> Monitor in production; no code changes needed unless "
                    "user-facing lag is reported.</li>\n"
                )
        ns += "</ul>\n"
    else:
        ns = (
            "<h2>Combinations Over 100 ms</h2>\n"
            '<p class="all-good">All tested combinations are within the 100 ms burst-p50 budget. '
            "No additional mitigations needed.</p>\n"
        )

    html = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        "<title>Preview Burst-Seek Benchmark Report</title>\n"
        "<style>\n"
        "  body { font-family: system-ui, -apple-system, sans-serif; margin: 2rem; color: #222; background: #fafafa; }\n"
        "  h1 { border-bottom: 2px solid #333; padding-bottom: .3rem; }\n"
        "  h2 { margin-top: 2rem; color: #555; }\n"
        "  table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .88rem; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.1); }\n"
        "  th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }\n"
        "  th { background: #f0f0f0; position: sticky; top: 0; }\n"
        "  tr:hover { background: #f5f5f5; }\n"
        "  tr.warn { background: #fff3cd; }\n"
        "  tr.warn:hover { background: #ffeeba; }\n"
        "  td.num { text-align: right; font-variant-numeric: tabular-nums; font-family: 'SF Mono', 'Cascadia Code', monospace; font-size: .85rem; }\n"
        "  td.hot { color: #c0392b; font-weight: 700; }\n"
        "  td.label { font-weight: 600; white-space: nowrap; }\n"
        "  .all-good { color: #27ae60; font-weight: 600; font-size: 1.1rem; }\n"
        "  .err { color: #e74c3c; font-weight: 600; }\n"
        "  .meta { color: #888; font-size: .85rem; margin-bottom: 1.5rem; }\n"
        "  code { background: #eee; padding: 1px 4px; border-radius: 3px; font-size: .85em; }\n"
        "  ul { line-height: 1.8; }\n"
        "  li { margin-bottom: .6rem; }\n"
        "  em { font-style: normal; color: #666; }\n"
        "</style>\n</head>\n<body>\n"
        "<h1>Preview Burst-Seek Benchmark Report</h1>\n"
        f'<p class="meta">Generated: {datetime.now():%Y-%m-%d %H:%M:%S} &mdash; '
        f"{len(results)} videos tested &mdash; target &lt; 100 ms burst p50</p>\n\n"
        "<table>\n<thead><tr>"
        "<th>Label</th><th>Codec</th><th>Resolution</th><th>FPS</th>"
        "<th>Container</th><th>Size</th><th>Frames</th>"
        "<th>Cold (ms)</th><th>Single mean (ms)</th>"
        "<th>Burst p50</th><th>Burst p95</th><th>Burst p99</th><th>Burst max</th>"
        "<th>Stale</th><th>Note</th>"
        "</tr></thead>\n<tbody>\n"
        + rows
        + "</tbody>\n</table>\n\n"
        + ns
        + "</body>\n</html>"
    )

    Path(out_path).write_text(html, encoding="utf-8")
    print(f"HTML report: {Path(out_path).resolve()}")


def main():
    results = []
    print(f"=== Benchmarking {len(TEST_VIDEOS)} videos (burst={BURST_N}, single={SINGLE_SEEKS}) ===\n", flush=True)

    for idx, (label, path) in enumerate(TEST_VIDEOS, 1):
        print(f"[{idx}/{len(TEST_VIDEOS)}] {label} ...", end=" ", flush=True)
        if not os.path.isfile(path):
            print("MISSING")
            results.append(BenchResult(label=label, path=path, error="file not found"))
            continue
        r = run_bench(label, path)
        results.append(r)
        if r.error:
            print(f"ERROR: {r.error}")
        else:
            flag = " *** OVER 100ms ***" if r.burst_p50 > 100 else ""
            print(f"cold={r.cold_ms:.1f} single={r.single_ms:.1f} burst_p50={r.burst_p50:.1f} p95={r.burst_p95:.1f} stale={r.stale}/{BURST_N}{flag}", flush=True)

    json_out = "tools/_bench_videos/matrix_results.json"
    Path(json_out).write_text(json.dumps([vars(r) for r in results], indent=2), encoding="utf-8")
    print(f"\nJSON: {Path(json_out).resolve()}")

    write_html(results, "tools/_bench_videos/bench_report.html")


if __name__ == "__main__":
    main()
