import argparse
import sys
import os
import json
import cv2
import numpy as np
from pathlib import Path

from src.domain.value_objects.config import ScoreConfig
from src.infrastructure.video_service import VideoService
from src.infrastructure.ocr_service import OcrService
from src.infrastructure.pdf_service import PdfService
from src.infrastructure.file_service import FileService
from src.application.use_cases import ExtractScoreUseCase, GeneratePdfUseCase
from src.domain.models import Frame

def load_config(config_path: str) -> ScoreConfig:
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return ScoreConfig(**data)
        except Exception as e:
            print(f"Warning: Failed to load config, using defaults. {e}")
    return ScoreConfig()

def load_images_from_dir(dir_path: str):
    p = Path(dir_path)
    files = sorted(p.glob("page_*_merged.png"), key=lambda f: int(f.stem.split("_")[1]))
    images = []
    for f in files:
        file_bytes = np.fromfile(str(f), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is not None:
            images.append(img)
    return images

def main():
    # Windows Unicode safety: reconfigure stdout/stderr/stdin to UTF-8
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    try:
        sys.stdin.reconfigure(encoding='utf-8')
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Piano Score Video-to-PDF Extractor")
    parser.add_argument("input", nargs="?", default=None, help="Path to the input video file")
    parser.add_argument("-o", "--output", help="Path to the output PDF file")
    parser.add_argument("-c", "--config", default="config.json", help="Path to config.json")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (retains temporary files)")
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR step")
    parser.add_argument("--start-time", type=float, default=-1.0, help="Jump to this time in seconds and capture the first page immediately")
    parser.add_argument("--duration", type=float, default=0.0, help="Stop processing after N seconds (0 = off)")
    parser.add_argument("--crop-ratio", type=float, help="Override crop ratio for PDF output")
    parser.add_argument("--from-dir", help="Regenerate PDF from an existing sandbox directory (skips video extraction)")

    args = parser.parse_args()

    # Validate arguments
    if args.from_dir:
        if not os.path.isdir(args.from_dir):
            print(f"Error: Directory not found: {args.from_dir}")
            sys.exit(1)
    else:
        if not args.input or not os.path.exists(args.input):
            print(f"Error: File not found: {args.input}")
            sys.exit(1)

    # Output path
    output_path = args.output
    if not output_path:
        if args.from_dir:
            output_path = Path(args.from_dir).stem + ".pdf"
        else:
            output_path = str(Path(args.input).with_suffix('.pdf'))

    config = load_config(args.config)

    # Override crop ratio if provided
    if args.crop_ratio is not None:
        config.default_crop_ratio = args.crop_ratio

    if args.from_dir:
        # Regeneration path -- skip extraction
        print(f"Regenerating PDF from: {args.from_dir}")
        images = load_images_from_dir(args.from_dir)
        if not images:
            print("Error: No page images found in directory.")
            sys.exit(1)
        print(f"Loaded {len(images)} page images")

        pdf_service = PdfService()
        file_service = FileService()
        file_service.create_sandbox()
        generate_pdf_use_case = GeneratePdfUseCase(pdf_service, file_service, config)
        frames = [Frame(img, 0.0, i) for i, img in enumerate(images)]
        generate_pdf_use_case.execute(frames, output_path)
        file_service.cleanup()
        print("\nSuccess! PDF regenerated.")

    else:
        # Normal extraction path
        video_service = VideoService()
        ocr_service = OcrService()
        pdf_service = PdfService()
        file_service = FileService()

        extract_use_case = ExtractScoreUseCase(video_service, ocr_service, file_service, config)
        generate_pdf_use_case = GeneratePdfUseCase(pdf_service, file_service, config)

        try:
            pages = extract_use_case.execute(args.input, no_ocr=args.no_ocr, start_time=args.start_time, debug=args.debug, duration=args.duration)
            generate_pdf_use_case.execute(pages, output_path)
            print("\nSuccess! Extraction complete.")
        except Exception as e:
            print(f"\n[Error] {e}")
            if not args.debug:
                file_service.cleanup(force=True)
            sys.exit(1)
        finally:
            video_service.close()
            if not args.debug:
                file_service.cleanup()
            else:
                try:
                    sandbox = file_service.get_sandbox_path()
                    video_stem = Path(args.input).stem
                    new_name = sandbox.with_name(video_stem)
                    if sandbox.exists() and not new_name.exists():
                        sandbox.rename(new_name)
                    print(f"Debug: Temporary files kept in {new_name if new_name.exists() else sandbox}")
                except:
                    pass

if __name__ == "__main__":
    main()
