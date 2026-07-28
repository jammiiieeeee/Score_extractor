"""End-to-end test: download, extract, generate PDF, open diagnostics."""
import sys
import os
import time
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from src.api.gui_api import GuiApi

URL = "https://youtu.be/2UuwmX-voUM?si=N_EhK2-y-1oEkdEg"
OUTPUT_FOLDER = os.path.join(os.getcwd(), "output")
SCORE_NAME = "theta_happy_birthday"

api = GuiApi()

# Enable debug mode so A/B frames + diagnostics are saved
api.set_debug_mode(True)

# Wire up callbacks so we can see progress in the terminal
def on_progress(phase, pct, detail):
    print(f"\r  [{phase}] {pct:5.1f}%  {detail}", end="", flush=True)

def on_log(msg):
    print(f"\n  [log] {msg}")

def on_error(msg):
    print(f"\n  [ERROR] {msg}")

def on_completed(count):
    print(f"\n  [completed] {count} pages")

def on_download_completed(path):
    print(f"\n  [download done] {path}")

api._on_progress = on_progress
api._on_log = on_log
api._on_error = on_error
api._on_completed = on_completed
api._on_download_completed = on_download_completed

# ── Step 1: YouTube download (dual video) ──────────────────────────
print("=" * 60)
print("STEP 1: YouTube download (dual video)")
print("=" * 60)
api.download_youtube(URL)

# Wait for download to finish
while api.is_busy():
    time.sleep(0.5)

state = api.get_extraction_state()
if state.phase == "error":
    print("Download failed.")
    sys.exit(1)

print(f"\n  Video info: {api._video_info.path if api._video_info else 'N/A'}")
print(f"  Original video path: {api._original_video_path}")

# ── Step 2: Extraction ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2: Extraction")
print("=" * 60)
api.start_extraction(
    no_ocr=True,
    start_time=2.0,
    end_offset=0.0,
    output_folder=OUTPUT_FOLDER,
    score_name=SCORE_NAME,
)

while api.is_busy():
    time.sleep(0.5)

state = api.get_extraction_state()
print(f"\n  Final state: {state.phase}, pages: {state.pages_detected}")
if state.phase == "error":
    print("Extraction failed.")
    sys.exit(1)

# ── Step 3: Generate PDF ────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3: Generate PDF")
print("=" * 60)
score_dir = os.path.join(OUTPUT_FOLDER, SCORE_NAME)
pdf_path = os.path.join(score_dir, f"{SCORE_NAME}.pdf")
api.generate_pdf(pdf_path, title=SCORE_NAME)

while api.is_busy():
    time.sleep(0.5)

state = api.get_extraction_state()
print(f"\n  Final state: {state.phase}")
if state.phase == "error":
    print("PDF generation failed.")
    sys.exit(1)

# ── Step 4: Open diagnostics folder ────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4: Open diagnostics folder")
print("=" * 60)
api.open_debug_folder(score_dir)

# ── Summary ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
print(f"  Score dir:   {score_dir}")
print(f"  PDF:         {pdf_path}")
print(f"  Pages:       {api.get_page_count()}")

# List diagnostics contents
diag_dir = os.path.join(score_dir, "diagnostics")
if os.path.isdir(diag_dir):
    print(f"  Diagnostics: {diag_dir}")
    for f in sorted(os.listdir(diag_dir)):
        size = os.path.getsize(os.path.join(diag_dir, f))
        print(f"    {f}  ({size:,} bytes)")
else:
    print("  No diagnostics directory found")

# List photos
photos_dir = os.path.join(score_dir, "photos")
if os.path.isdir(photos_dir):
    print(f"  Photos:")
    for f in sorted(os.listdir(photos_dir)):
        size = os.path.getsize(os.path.join(photos_dir, f))
        print(f"    {f}  ({size:,} bytes)")
