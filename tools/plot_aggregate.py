import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2, numpy as np, os, glob

debug_dir = "output/winter_sonata_full/debug"
output_path = "output/winter_sonata_full/bar_profile.png"

ab_files = sorted(glob.glob(os.path.join(debug_dir, "page_*_A.png")))

n_pages = len(ab_files)
n_cols = min(4, n_pages)
n_rows = (n_pages + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(5*n_cols, 3*n_rows))
if n_rows == 1:
    axes = [axes]
axes_flat = [ax for row in axes for ax in row]

# Colors for peak annotations
colors_cycle = plt.cm.Set1(np.linspace(0, 1, 10))

for idx, a_path in enumerate(ab_files):
    if idx >= len(axes_flat):
        break
    ax = axes_flat[idx]
    
    b_path = a_path.replace("_A.png", "_B.png")
    a = cv2.imread(a_path, cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(b_path, cv2.IMREAD_GRAYSCALE)
    
    if a is None or b is None:
        ax.text(0.5, 0.5, "Missing", ha='center', va='center', transform=ax.transAxes)
        continue
    
    h, w = a.shape
    crop_h = int(h * 0.33)
    top_a = a[:crop_h, :].astype(float)
    top_b = b[:crop_h, :].astype(float)
    diff = cv2.absdiff(top_a, top_b)
    col_sums = np.sum(diff, axis=0)
    
    x = np.arange(w)
    ax.fill_between(x, 0, col_sums, alpha=0.5, color='steelblue')
    ax.plot(x, col_sums, color='steelblue', linewidth=0.8)
    
    max_val = np.max(col_sums[:320]) if len(col_sums) > 320 else np.max(col_sums)
    threshold = max_val * 0.5
    
    # Find peaks (two-spike detection)
    left_range = col_sums[:320] if len(col_sums) > 320 else col_sums
    threshold2 = np.max(left_range) * 0.3
    peaks = []
    for i in range(1, len(left_range)-1):
        if left_range[i] > left_range[i-1] and left_range[i] >= left_range[i+1] and left_range[i] > threshold2:
            peaks.append((i, left_range[i]))
    
    peaks.sort(key=lambda p: p[1], reverse=True)
    
    peaks_to_show = peaks[:2]  # top 2 peaks
    colors = ['orange', 'purple']
    labels = ['Bar in A', 'Bar in B']
    
    for pi, (col, val) in enumerate(peaks_to_show):
        c = colors[pi % len(colors)]
        lb = labels[pi % len(labels)]
        ax.axvline(x=col, color=c, linestyle='--', linewidth=1.5, alpha=0.8)
        ax.annotate(f'{lb}={col}', xy=(col, val), xytext=(5, 5),
                    textcoords='offset points', fontsize=7, color=c,
                    arrowprops=dict(arrowstyle='->', color=c, lw=0.8))
    
    ax.axhline(y=threshold, color='green', linestyle=':', linewidth=0.5, alpha=0.5)
    
    page_num = int(os.path.basename(a_path).split('_')[1])
    ax.set_title(f'Page {page_num}', fontsize=9)
    ax.set_xlabel('Column', fontsize=7)
    ax.set_ylabel('Diff sum', fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_xlim(0, w)

# Hide unused subplots
for idx in range(n_pages, len(axes_flat)):
    axes_flat[idx].set_visible(False)

plt.tight_layout()
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"Saved {output_path}")
print(f"Total pages: {n_pages}")
