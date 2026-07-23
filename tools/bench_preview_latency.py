"""
Benchmark video preview latency across different codecs/files.

Tests the exact code path used by PreviewSeeker:
  - FFmpeg subprocess seek (the actual preview path)
  - OpenCV CAP_PROP_POS_FRAMES seek (initial load path)
  - Reports codec info per file

Run from project root:
    python tools/bench_preview_latency.py
    python tools/bench_preview_latency.py --videos path1.mp4 path2.webm
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np


@dataclass
class VideoInfo:
    path: str
    codec: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    total_frames: int = 0
    duration_s: float = 0.0
    file_size_mb: float = 0.0


@dataclass
class LatencyResult:
    video: VideoInfo
    ffmpeg_seek_ms: List[float] = field(default_factory=list)
    opencv_seek_ms: List[float] = field(default_factory=list)
    ffmpeg_open_ms: float = 0.0
    opencv_open_ms: float = 0.0


def find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    pattern = r"C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\*ffmpeg*\bin\ffmpeg.exe"
    matches = glob.glob(pattern)
    return matches[0] if matches else "ffmpeg"


def probe_video(path: str) -> VideoInfo:
    """Get video metadata via OpenCV + ffprobe."""
    info = VideoInfo(path=path)
    info.file_size_mb = os.path.getsize(path) / (1024 * 1024)

    cap = cv2.VideoCapture(path)
    if cap.isOpened():
        info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        info.fps = cap.get(cv2.CAP_PROP_FPS) or 1.0
        info.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        info.duration_s = info.total_frames / info.fps
        cap.release()

    # ffprobe for codec
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,pix_fmt",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=5
        )
        parts = result.stdout.strip().split(",")
        if parts:
            info.codec = parts[0]
    except Exception:
        pass

    return info


def bench_ffmpeg_subprocess(ffmpeg_bin: str, path: str, width: int,
                            timestamps: List[float]) -> List[float]:
    """Benchmark FFmpeg subprocess seek — exact PreviewSeeker path."""
    times = []
    for ts in timestamps:
        cmd = [
            ffmpeg_bin,
            "-hide_banner", "-loglevel", "error",
            "-hwaccel", "auto",
            "-ss", f"{ts:.3f}",
            "-i", path,
            "-frames:v", "1",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "pipe:1",
        ]
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5,
            )
            t1 = time.perf_counter()
            if proc.returncode == 0 and len(proc.stdout) > 9:
                times.append((t1 - t0) * 1000)
            else:
                times.append(-1)  # failure marker
        except (subprocess.TimeoutExpired, OSError) as e:
            t1 = time.perf_counter()
            times.append(-1)
    return times


def bench_opencv_seek(path: str, total_frames: int,
                      timestamps: List[float], fps: float) -> List[float]:
    """Benchmark OpenCV seek — exact initial load path."""
    times = []
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return [-1] * len(timestamps)

    for ts in timestamps:
        frame_idx = int(ts * fps)
        t0 = time.perf_counter()
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, _ = cap.read()
        t1 = time.perf_counter()
        if ret:
            times.append((t1 - t0) * 1000)
        else:
            times.append(-1)

    cap.release()
    return times


def bench_ffmpeg_open(ffmpeg_bin: str, path: str) -> float:
    """Time how long FFmpeg takes to open + decode first frame."""
    cmd = [
        ffmpeg_bin,
        "-hide_banner", "-loglevel", "error",
        "-i", path,
        "-frames:v", "1",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "pipe:1",
    ]
    t0 = time.perf_counter()
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    except Exception:
        pass
    return (time.perf_counter() - t0) * 1000


def run_benchmark(video_paths: List[str], seek_samples: int = 20):
    ffmpeg_bin = find_ffmpeg()
    print(f"FFmpeg binary: {ffmpeg_bin}")
    print(f"Seek samples: {seek_samples}\n")

    results: List[LatencyResult] = []

    for vpath in video_paths:
        if not os.path.isfile(vpath):
            print(f"SKIP (not found): {vpath}")
            continue

        info = probe_video(vpath)
        print(f"{'='*70}")
        print(f"File:     {info.path}")
        print(f"Codec:    {info.codec or 'unknown'}")
        print(f"Size:     {info.width}x{info.height} @ {info.fps:.1f} fps")
        print(f"Duration: {info.duration_s:.1f}s ({info.total_frames} frames)")
        print(f"File:     {info.file_size_mb:.1f} MB")

        # Generate seek timestamps spread across the video
        if info.duration_s > 1:
            timestamps = np.linspace(0.5, info.duration_s - 0.5, seek_samples).tolist()
        else:
            timestamps = [0.0]

        res = LatencyResult(video=info)

        # FFmpeg subprocess latency
        print(f"\n  [FFmpeg subprocess seek]")
        t0 = time.perf_counter()
        res.ffmpeg_open_ms = bench_ffmpeg_open(ffmpeg_bin, vpath)
        print(f"    open+first-frame: {res.ffmpeg_open_ms:.1f} ms")
        res.ffmpeg_seek_ms = bench_ffmpeg_subprocess(ffmpeg_bin, vpath, info.width, timestamps)
        valid = [t for t in res.ffmpeg_seek_ms if t > 0]
        if valid:
            print(f"    seek+decode:      {np.mean(valid):7.1f} ± {np.std(valid):.1f} ms  "
                  f"(min={min(valid):.1f}  max={max(valid):.1f}  n={len(valid)})")
        else:
            print(f"    seek+decode:      ALL FAILED")

        # OpenCV seek latency
        print(f"\n  [OpenCV CAP_PROP_POS_FRAMES seek]")
        t0 = time.perf_counter()
        cap = cv2.VideoCapture(vpath)
        res.opencv_open_ms = (time.perf_counter() - t0) * 1000
        if cap.isOpened():
            cap.release()
        print(f"    open:             {res.opencv_open_ms:.1f} ms")
        res.opencv_seek_ms = bench_opencv_seek(vpath, info.total_frames, timestamps, info.fps)
        valid_cv = [t for t in res.opencv_seek_ms if t > 0]
        if valid_cv:
            print(f"    seek+read:        {np.mean(valid_cv):7.1f} ± {np.std(valid_cv):.1f} ms  "
                  f"(min={min(valid_cv):.1f}  max={max(valid_cv):.1f}  n={len(valid_cv)})")
        else:
            print(f"    seek+read:        ALL FAILED")

        # Comparison
        if valid and valid_cv:
            ratio = np.mean(valid_cv) / np.mean(valid)
            faster = "FFmpeg" if ratio > 1 else "OpenCV"
            print(f"\n  >>> {faster} is {abs(ratio):.1f}x faster for random seek")

        print()
        results.append(res)

    # Summary table
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'File':<35} {'Codec':<8} {'FFmpeg':>10} {'OpenCV':>10} {'Winner':>10}")
    print("-" * 75)
    for r in results:
        ff_valid = [t for t in r.ffmpeg_seek_ms if t > 0]
        cv_valid = [t for t in r.opencv_seek_ms if t > 0]
        ff_str = f"{np.mean(ff_valid):.1f} ms" if ff_valid else "FAIL"
        cv_str = f"{np.mean(cv_valid):.1f} ms" if cv_valid else "FAIL"
        if ff_valid and cv_valid:
            winner = "FFmpeg" if np.mean(ff_valid) < np.mean(cv_valid) else "OpenCV"
        else:
            winner = "-"
        name = Path(r.video.path).name[:34]
        print(f"{name:<35} {r.video.codec:<8} {ff_str:>10} {cv_str:>10} {winner:>10}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark preview latency across codecs")
    parser.add_argument("--videos", nargs="*", help="Video file paths (default: scan yt_dl/ and tests/fixtures/)")
    parser.add_argument("--samples", type=int, default=20, help="Number of seek positions to test")
    args = parser.parse_args()

    if args.videos:
        videos = args.videos
    else:
        # Auto-discover videos
        videos = []
        for pattern in ["yt_dl/*.mp4", "yt_dl/*.webm", "tests/fixtures/*.mp4"]:
            videos.extend(sorted(glob.glob(pattern)))
        if not videos:
            print("No videos found. Use --videos to specify paths.")
            sys.exit(1)
        print(f"Auto-discovered {len(videos)} video(s)\n")

    run_benchmark(videos, seek_samples=args.samples)
