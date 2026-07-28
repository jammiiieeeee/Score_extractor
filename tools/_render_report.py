"""Generate the HTML report from already-collected benchmark data."""
import json
from pathlib import Path
from datetime import datetime

BURST_N = 20

# Data collected from the benchmark run
DATA = [
    {"label": "H.264  640x360  30fps", "codec": "h264", "w": 640, "h": 360, "fps": 30, "container": ".mp4", "mb": 12.7, "frames": 7914, "cold_ms": 60.4, "single_ms": 72.9, "burst_p50": 57.3, "burst_p95": 57.3, "burst_p99": 57.3, "burst_max": 57.3, "stale": 19},
    {"label": "H.264  854x480  30fps", "codec": "h264", "w": 854, "h": 480, "fps": 30, "container": ".mp4", "mb": 15.9, "frames": 7914, "cold_ms": 53.4, "single_ms": 71.9, "burst_p50": 80.2, "burst_p95": 80.2, "burst_p99": 80.2, "burst_max": 80.2, "stale": 19},
    {"label": "H.264 1280x720  60fps", "codec": "h264", "w": 1280, "h": 720, "fps": 60, "container": ".mp4", "mb": 47.7, "frames": 15828, "cold_ms": 87.2, "single_ms": 236.4, "burst_p50": 362.8, "burst_p95": 362.8, "burst_p99": 362.8, "burst_max": 362.8, "stale": 19},
    {"label": "VP9    640x360  30fps", "codec": "VP90", "w": 640, "h": 360, "fps": 30, "container": ".webm", "mb": 6.2, "frames": 7914, "cold_ms": 33.7, "single_ms": 43.8, "burst_p50": 18.7, "burst_p95": 18.7, "burst_p99": 18.7, "burst_max": 18.7, "stale": 19},
    {"label": "VP9   1280x720  60fps", "codec": "VP90", "w": 1280, "h": 720, "fps": 60, "container": ".webm", "mb": 32.0, "frames": 15828, "cold_ms": 114.8, "single_ms": 480.5, "burst_p50": 167.0, "burst_p95": 167.0, "burst_p99": 167.0, "burst_max": 167.0, "stale": 19},
    {"label": "VP9   1920x1080 60fps", "codec": "VP90", "w": 1920, "h": 1080, "fps": 60, "container": ".webm", "mb": 49.4, "frames": 15828, "cold_ms": 343.1, "single_ms": 574.6, "burst_p50": 1791.7, "burst_p95": 1791.7, "burst_p99": 1791.7, "burst_max": 1791.7, "stale": 19},
    {"label": "AV1    640x360  30fps", "codec": "AV01", "w": 640, "h": 360, "fps": 30, "container": ".mp4", "mb": 5.2, "frames": 7914, "cold_ms": 147.6, "single_ms": 417.8, "burst_p50": 411.1, "burst_p95": 411.1, "burst_p99": 411.1, "burst_max": 411.1, "stale": 19},
    {"label": "AV1   1280x720  60fps", "codec": "AV01", "w": 1280, "h": 720, "fps": 60, "container": ".mp4", "mb": 17.3, "frames": 15828, "cold_ms": 522.0, "single_ms": 2799.5, "burst_p50": 3850.7, "burst_p95": 3850.7, "burst_p99": 3850.7, "burst_max": 3850.7, "stale": 19},
    {"label": "AV1   1920x1080 60fps", "codec": "AV01", "w": 1920, "h": 1080, "fps": 60, "container": ".mp4", "mb": 40.5, "frames": 19070, "cold_ms": 1135.9, "single_ms": 4326.2, "burst_p50": 5306.6, "burst_p95": 5306.6, "burst_p99": 5306.6, "burst_max": 5306.6, "stale": 19},
]

rows = ""
over100 = []
for r in DATA:
    over = r["burst_p50"] > 100
    if over:
        over100.append(r)
    tr_cls = ' class="warn"' if over else ""
    hot = " hot" if over else ""

    rows += (
        f'<tr{tr_cls}>'
        f'<td class="label">{r["label"]}</td>'
        f'<td>{r["codec"]}</td>'
        f'<td>{r["w"]}x{r["h"]}</td>'
        f'<td class="num">{r["fps"]}</td>'
        f'<td>{r["container"]}</td>'
        f'<td class="num">{r["mb"]}</td>'
        f'<td class="num">{r["frames"]}</td>'
        f'<td class="num">{r["cold_ms"]:.1f}</td>'
        f'<td class="num">{r["single_ms"]:.1f}</td>'
        f'<td class="num {hot}">{r["burst_p50"]:.1f}</td>'
        f'<td class="num {hot}">{r["burst_p95"]:.1f}</td>'
        f'<td class="num">{r["burst_p99"]:.1f}</td>'
        f'<td class="num">{r["burst_max"]:.1f}</td>'
        f'<td class="num">{r["stale"]}/{BURST_N}</td>'
        f'<td>{"<span class=err>OVER 100ms</span>" if over else ""}</td>'
        "</tr>\n"
    )

# Next steps
ns_items = []
seen = set()
for r in over100:
    key = (r["codec"], r["w"], r["h"], r["fps"])
    if key in seen:
        continue
    seen.add(key)
    codec = r["codec"]
    res = f'{r["w"]}x{r["h"]}'
    fps_v = r["fps"]
    item = f'<li><strong>{r["label"]}</strong> ({codec} {res} @{fps_v}fps) &mdash; burst p50 = <strong>{r["burst_p50"]:.0f} ms</strong><br>\n'
    if codec == "AV01":
        item += (
            "<em>Root cause:</em> AV1 intra-frame decode is extremely CPU-heavy. "
            "OpenCV's FFmpeg backend must fully decode each frame; there is no hardware AV1 decode on this system.<br>"
            "<em>Current mitigation:</em> The latest-wins coalescing pattern prevents queue buildup "
            "but does not reduce per-frame decode cost.<br>"
            "<em>Recommended next steps:</em><br>"
            "(a) <strong>Low-res preview decode</strong> &mdash; decode a 640px-wide copy for the "
            "seek slider thumbnail. This cuts pixel count by 75-98%.<br>"
            "(b) <strong>FFmpeg keyframe-only seek</strong> &mdash; use <code>ffmpeg -ss T -i file -frames:v 1</code> "
            "which skips to the nearest keyframe without decoding all intermediate frames.<br>"
            "(c) <strong>Pre-transcode sidecar</strong> &mdash; on first open, generate a low-res H.264 "
            "sidecar file for fast seeking; use the original only for extraction.</li>\n"
        )
    elif codec == "VP90":
        item += (
            "<em>Root cause:</em> VP9 decode via libvpx is multi-threaded but still slower than H.264 "
            "at equivalent resolution. Higher resolutions amplify the cost.<br>"
            "<em>Current mitigation:</em> Latest-wins coalescing only.<br>"
            "<em>Recommended next steps:</em><br>"
            "(a) Same low-res preview decode pass as above.<br>"
            "(b) <strong>FFmpeg keyframe seek</strong> &mdash; VP9 has long keyframe intervals by default; "
            "FFmpeg can skip directly to keyframes.<br>"
            "(c) Consider forcing <code>-g 60</code> during VP9 encode to guarantee a keyframe every 2 seconds.</li>\n"
        )
    elif r["w"] >= 1280 and r["fps"] >= 60:
        item += (
            "<em>Root cause:</em> 1280x720 @60fps requires decoding ~55K pixels per frame at 60fps. "
            "cv2.resize + display overhead stacks up.<br>"
            "<em>Recommended next steps:</em><br>"
            "(a) <strong>Limit preview decode resolution</strong> &mdash; cap at 640px width for the seek slider.<br>"
            "(b) <strong>Cap decode FPS</strong> &mdash; seek slider only needs one frame per seek, not 60fps decode.</li>\n"
        )
    else:
        item += (
            "<em>Root cause:</em> Borderline latency.<br>"
            "<em>Recommended:</em> Monitor; no code changes needed unless user-facing lag is reported.</li>\n"
        )
    ns_items.append(item)

if ns_items:
    ns_html = "<h2>Combinations Over 100 ms &mdash; Recommended Next Steps</h2>\n<ul>\n" + "\n".join(ns_items) + "</ul>\n"
else:
    ns_html = '<h2>Combinations Over 100 ms</h2>\n<p class="all-good">All within budget.</p>\n'

html = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    '<meta charset="utf-8">\n'
    "<title>Preview Burst-Seek Benchmark Report</title>\n"
    "<style>\n"
    "body{font-family:system-ui,-apple-system,sans-serif;margin:2rem;color:#222;background:#fafafa}\n"
    "h1{border-bottom:2px solid #333;padding-bottom:.3rem}\n"
    "h2{margin-top:2rem;color:#555}\n"
    "table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.88rem;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1)}\n"
    "th,td{border:1px solid #ddd;padding:6px 10px;text-align:left}\n"
    "th{background:#f0f0f0;position:sticky;top:0}\n"
    "tr:hover{background:#f5f5f5}\n"
    "tr.warn{background:#fff3cd}\n"
    "tr.warn:hover{background:#ffeeba}\n"
    "td.num{text-align:right;font-variant-numeric:tabular-nums;font-family:'SF Mono','Cascadia Code',monospace;font-size:.85rem}\n"
    "td.hot{color:#c0392b;font-weight:700}\n"
    "td.label{font-weight:600;white-space:nowrap}\n"
    ".all-good{color:#27ae60;font-weight:600;font-size:1.1rem}\n"
    ".err{color:#e74c3c;font-weight:600}\n"
    ".meta{color:#888;font-size:.85rem;margin-bottom:1.5rem}\n"
    "code{background:#eee;padding:1px 4px;border-radius:3px;font-size:.85em}\n"
    "ul{line-height:1.8}\n"
    "li{margin-bottom:.6rem}\n"
    "em{font-style:normal;color:#666}\n"
    "code{background:#eee;padding:1px 4px;border-radius:3px}\n"
    "</style>\n</head>\n<body>\n"
    "<h1>Preview Burst-Seek Benchmark Report</h1>\n"
    f'<p class="meta">Generated: {datetime.now():%Y-%m-%d %H:%M:%S} &mdash; '
    f'{len(DATA)} videos &mdash; target &lt; 100 ms burst p50</p>\n\n'
    "<h2>Benchmark Results</h2>\n"
    "<table>\n<thead><tr>"
    "<th>Label</th><th>Codec</th><th>Resolution</th><th>FPS</th>"
    "<th>Container</th><th>Size</th><th>Frames</th>"
    "<th>Cold (ms)</th><th>Single mean (ms)</th>"
    "<th>Burst p50</th><th>Burst p95</th><th>Burst p99</th><th>Burst max</th>"
    "<th>Stale</th><th>Note</th>"
    "</tr></thead>\n<tbody>\n"
    + rows
    + "</tbody>\n</table>\n\n"
    + ns_html
    + "</body>\n</html>"
)

out = Path("tools/_bench_videos/bench_report.html")
out.write_text(html, encoding="utf-8")
print(f"Report: {out.resolve()}")

# Also save JSON
Path("tools/_bench_videos/matrix_results.json").write_text(json.dumps(DATA, indent=2), encoding="utf-8")
print(f"JSON:   {Path('tools/_bench_videos/matrix_results.json').resolve()}")
