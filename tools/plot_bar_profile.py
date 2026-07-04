"""
Plot a bar profile file (bar_profile_page_NNN.txt) generated during debug mode.

Usage:
    python tools/plot_bar_profile.py path/to/bar_profile_page_001.txt [options]

Options:
    --ab-dir PATH   Path to debug/ folder containing page_NNN_A.png and page_NNN_B.png
    --output PATH   Custom output path for the plot PNG
    --show          Display plot interactively (default: just save)
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def detect_bar_x(relevant_sum: np.ndarray) -> int:
    """Replicate the bar detection algorithm from video_service.py."""
    max_diff = float(np.max(relevant_sum))
    threshold = max_diff * 0.5

    bar_x_small = -1
    for col in range(len(relevant_sum) - 1, -1, -1):
        if relevant_sum[col] > threshold:
            bar_x_small = col
            break

    if bar_x_small < 0:
        bar_x_small = int(np.argmax(relevant_sum))

    return bar_x_small, threshold, max_diff


def find_two_peaks(values: np.ndarray, min_distance: int = 15, prominence_ratio: float = 0.15):
    """Find the two most prominent peaks in a 1D signal.
    
    Returns list of (column_index, value) sorted by column index ascending,
    or fewer if not enough peaks found.
    """
    if len(values) < 3:
        return []

    max_val = float(np.max(values))
    if max_val == 0:
        return []

    min_prominence = max_val * prominence_ratio

    # Find all local maxima
    peaks = []
    for i in range(1, len(values) - 1):
        if values[i] > values[i - 1] and values[i] >= values[i + 1]:
            if values[i] >= min_prominence:
                peaks.append((i, int(values[i])))

    if not peaks:
        # Fallback: just take the global max
        argmax = int(np.argmax(values))
        return [(argmax, int(values[argmax]))]

    # Sort by value descending, take top 2
    peaks.sort(key=lambda p: p[1], reverse=True)
    top = [peaks[0]]
    for p in peaks[1:]:
        if abs(p[0] - top[0][0]) >= min_distance:
            top.append(p)
            break

    # Sort by column index ascending
    top.sort(key=lambda p: p[0])
    return top


def load_ab_frames(ab_dir: Path, page_num: int):
    a_path = ab_dir / f"page_{page_num:03d}_A.png"
    b_path = ab_dir / f"page_{page_num:03d}_B.png"

    a_img = plt.imread(str(a_path)) if a_path.exists() else None
    b_img = plt.imread(str(b_path)) if b_path.exists() else None
    return a_img, b_img


def main():
    parser = argparse.ArgumentParser(description="Plot bar profile for debugging bar edge detection")
    parser.add_argument("profile", type=str, help="Path to bar_profile_page_NNN.txt")
    parser.add_argument("--ab-dir", type=str, default=None, help="Path to debug/ folder with A/B frames")
    parser.add_argument("--output", type=str, default=None, help="Output path for plot PNG")
    parser.add_argument("--show", action="store_true", help="Display plot interactively")
    args = parser.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"Error: file not found: {profile_path}", file=sys.stderr)
        sys.exit(1)

    relevant_sum = np.loadtxt(str(profile_path), dtype=int)
    if relevant_sum.ndim != 1 or len(relevant_sum) == 0:
        print(f"Error: expected 1D array, got shape {relevant_sum.shape}", file=sys.stderr)
        sys.exit(1)

    bar_x, threshold, max_diff = detect_bar_x(relevant_sum)
    peaks = find_two_peaks(relevant_sum)

    page_match = re.search(r"page_(\d+)", profile_path.stem)
    page_num = int(page_match.group(1)) if page_match else None

    fig, axes = plt.subplots(1, 1, figsize=(14, 5))
    ax = axes

    cols = np.arange(len(relevant_sum))
    ax.plot(cols, relevant_sum, color="#1a3a5c", linewidth=1.2, label="Per-column summed difference")
    ax.axhline(y=threshold, color="#c0392b", linestyle="--", linewidth=1,
               label=f"Threshold (50% of max = {threshold:.0f})")
    ax.axvline(x=bar_x, color="#27ae60", linestyle="-", linewidth=2,
               label=f"Merge boundary (col {bar_x})")

    # Shade B-coverage region
    ax.axvspan(0, bar_x, alpha=0.06, color="#27ae60", label="B overlay region (0 → merge boundary)")

    # Annotate both spikes
    for idx, (col, val) in enumerate(peaks):
        if len(peaks) == 2:
            label = "Bar in A (old position)" if idx == 0 else "Bar in B (new position)"
            color = "#e67e22" if idx == 0 else "#8e44ad"
            marker = "o"
        else:
            label = f"Peak at col {col}"
            color = "#e67e22"
            marker = "o"

        ax.scatter([col], [val], color=color, s=60, zorder=5, marker=marker)
        ax.axvline(x=col, color=color, linestyle=":", linewidth=1.2, alpha=0.7)
        offset = -20 if idx == 0 else 12
        ax.annotate(
            label,
            xy=(col, val),
            xytext=(col, val + max_diff * 0.08 * (1 if idx == 0 else 1.15)),
            fontsize=8.5,
            color=color,
            ha="center",
            arrowprops=dict(arrowstyle="->", color=color, lw=1),
        )

    ax.set_xlabel("Column index (at 640px scale, left 50% region)", fontsize=10)
    ax.set_ylabel("Summed grayscale difference", fontsize=10)
    title = f"Bar Profile"
    if page_num is not None:
        title += f" — Page {page_num}"
    n_peaks = len(peaks)
    title += f"\nBar edge at column {bar_x} | {n_peaks} peak{'s' if n_peaks != 1 else ''} detected | max diff = {max_diff:.0f}"
    ax.set_title(title, fontsize=11)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)

    if args.ab_dir:
        ab_dir_path = Path(args.ab_dir)
        a_img, b_img = load_ab_frames(ab_dir_path, page_num or 0)
        if a_img is not None and b_img is not None:
            fig_a, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(14, 6))
            ax_a.imshow(a_img)
            # Draw vertical line at A bar position
            if len(peaks) >= 1:
                p_col = peaks[0][0] * (a_img.shape[1] / 320)
                ax_a.axvline(x=p_col, color="#e67e22", linestyle=":", linewidth=2)
                ax_a.set_title(f"Frame A — bar at col {peaks[0][0]} (orange)", fontsize=10)
            else:
                ax_a.set_title("Frame A", fontsize=10)
            ax_a.axis("off")
            ax_b.imshow(b_img)
            if len(peaks) >= 2:
                p_col = peaks[1][0] * (b_img.shape[1] / 320)
                ax_b.axvline(x=p_col, color="#8e44ad", linestyle=":", linewidth=2)
                ax_b.set_title(f"Frame B — bar at col {peaks[1][0]} (purple)", fontsize=10)
            elif len(peaks) == 1:
                p_col = peaks[0][0] * (b_img.shape[1] / 320)
                ax_b.axvline(x=p_col, color="#e67e22", linestyle=":", linewidth=2)
                ax_b.set_title("Frame B", fontsize=10)
            else:
                ax_b.set_title("Frame B", fontsize=10)
            ax_b.axis("off")
            fig_a.tight_layout()

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = profile_path.with_name(f"{profile_path.stem}_plot.png")

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150)
    print(f"Plot saved: {output_path}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
