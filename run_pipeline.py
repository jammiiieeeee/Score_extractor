"""Full pipeline: download → extract → PDF → diagnostics HTML → open report."""
import time, subprocess, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.api.gui_api import GuiApi

URL = "https://youtu.be/KORz8v7fk10"
SCORE_NAME = "theta_korz"
OUTPUT_DIR = "output"

def log(msg): print(f"  {msg}")

def on_progress(phase, pct, detail):
    bar = '#' * int(pct / 2) + '.' * (50 - int(pct / 2))
    print(f"\r  [{bar}] {pct:5.1f}% {phase}: {detail}", end="", flush=True)

def on_log(msg):
    print()
    log(msg)

def on_error(msg):
    print()
    log(f"[ERROR] {msg}")

def on_completed(count):
    print()
    log(f"Extraction complete: {count} pages")

def on_download(path):
    log(f"Download complete: {path}")

# ─── SETUP ───────────────────────────────────────────────
print("=" * 60)
print("FULL PIPELINE: theta piano extraction")
print("=" * 60)

api = GuiApi()
api.set_debug_mode(True)
api._on_progress = on_progress
api._on_log = on_log
api._on_error = on_error
api._on_completed = on_completed
api._on_download_completed = on_download

# ─── STEP 1: DOWNLOAD ────────────────────────────────────
print("\n[1/4] Downloading from YouTube...")
print(f"  URL: {URL}")
api.download_youtube(URL)
while api.is_busy():
    time.sleep(0.5)

state = api.get_extraction_state()
if state.phase == "error":
    log("Download failed!")
    sys.exit(1)
log("Download OK")

# ─── STEP 2: EXTRACT ─────────────────────────────────────
print("\n[2/4] Extracting pages...")
api.start_extraction(
    no_ocr=True,
    start_time=2.0,
    end_offset=0.0,
    output_folder=OUTPUT_DIR,
    score_name=SCORE_NAME,
)
while api.is_busy():
    time.sleep(0.5)

state = api.get_extraction_state()
if state.phase == "error":
    log("Extraction failed!")
    sys.exit(1)
log(f"Extraction OK: {state.pages_detected} pages")

# ─── STEP 3: PDF ─────────────────────────────────────────
print("\n[3/4] Generating PDF...")
pdf_path = f"{OUTPUT_DIR}/{SCORE_NAME}/{SCORE_NAME}.pdf"
api.generate_pdf(pdf_path, title=SCORE_NAME)
while api.is_busy():
    time.sleep(0.5)
log(f"PDF: {pdf_path}")

# ─── STEP 4: DIAGNOSTICS HTML ────────────────────────────
print("\n[4/4] Generating diagnostics HTML...")
diag_dir = Path(OUTPUT_DIR) / SCORE_NAME / "diagnostics"
score_dir = Path(OUTPUT_DIR) / SCORE_NAME

# Copy generate_charts.py if not already present
src_charts = Path(__file__).parent / "output" / "theta_happy_birthday" / "diagnostics" / "generate_charts.py"
dst_charts = diag_dir / "generate_charts.py"
if not dst_charts.exists() and src_charts.exists():
    import shutil
    shutil.copy2(src_charts, dst_charts)
    log(f"Copied generate_charts.py to {dst_charts}")

# Copy page_manifest.json to diagnostics
src_manifest = score_dir / "page_manifest.json"
dst_manifest = diag_dir / "page_manifest.json"
if src_manifest.exists():
    import shutil
    shutil.copy2(src_manifest, dst_manifest)
    log(f"Copied page_manifest.json to diagnostics")

charts_py = diag_dir / "generate_charts.py"
if charts_py.exists():
    subprocess.run([sys.executable, str(charts_py)], check=True)
    html_path = diag_dir / "extraction_debug_charts.html"
    log(f"Report: {html_path}")
    os.startfile(str(html_path))
else:
    log(f"generate_charts.py not found at {charts_py}")

# ─── DONE ────────────────────────────────────────────────
print("\n" + "=" * 60)
print("DONE")
print("=" * 60)

# List output
score_dir = Path(OUTPUT_DIR) / SCORE_NAME
for sub in ["photos", "diagnostics"]:
    d = score_dir / sub
    if d.exists():
        files = list(d.iterdir())
        print(f"\n  {sub}/ ({len(files)} files)")
        for f in sorted(files)[:5]:
            print(f"    {f.name} ({f.stat().st_size:,} bytes)")
        if len(files) > 5:
            print(f"    ... and {len(files)-5} more")

api.cleanup()
