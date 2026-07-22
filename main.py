import argparse
import sys
import os
import json
import cv2
import numpy as np
from pathlib import Path

from src.domain.value_objects.config import ScoreConfig
from src.infrastructure.video_service import VideoService
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
    return FileService().load_page_images(Path(dir_path))


def main():
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
    parser.add_argument("-o", "--output", help="Output PDF path (default: input name with .pdf)")
    parser.add_argument("--output-dir", help="Output folder for organized score (creates <score_name>/photos/ etc.)")
    parser.add_argument("--score-name", help="Score name (default: video filename stem)")
    parser.add_argument("-c", "--config", default="config.json", help="Path to config.json")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR step")
    parser.add_argument("--start-time", type=float, default=2.0, help="Jump to this time in seconds and capture the first page immediately (default: 2.0)")
    parser.add_argument("--duration", type=float, default=0.0, help="Stop processing after N seconds (0 = off)")
    parser.add_argument("--crop-ratio", type=float, help="Override crop ratio for PDF output")
    parser.add_argument("--from-dir", help="Regenerate PDF from an existing score directory (skips video extraction)")

    args = parser.parse_args()

    config = load_config(args.config)

    if args.crop_ratio is not None:
        config.default_crop_ratio = args.crop_ratio

    if args.from_dir:
        score_dir = Path(args.from_dir)
        if not score_dir.is_dir():
            print(f"Error: Directory not found: {args.from_dir}")
            sys.exit(1)

        images = FileService().load_page_images(score_dir)
        if not images:
            print(f"Error: No page images found in {score_dir}/photos/")
            sys.exit(1)

        print(f"Loaded {len(images)} page images from {args.from_dir}")

        output_path = args.output or str(score_dir / f"{score_dir.name}.pdf")
        pdf_service = PdfService()
        pdf_service.create_pdf(images, Path(output_path), config, title_hint=Path(output_path).stem)
        print(f"\nSuccess! PDF generated: {output_path}")

    else:
        if not args.input or not os.path.exists(args.input):
            print(f"Error: File not found: {args.input}")
            sys.exit(1)

        video_service = VideoService()
        ocr_service = None
        if not args.no_ocr:
            from src.infrastructure.ocr_service import OcrService
            ocr_service = OcrService()
        pdf_service = PdfService()
        file_service = FileService()

        video_name = Path(args.input).stem
        score_name = args.score_name or video_name

        if args.output_dir:
            output_dir = file_service.prepare_output_dir(args.output_dir, score_name)
            output_pdf = args.output or str(output_dir / f"{score_name}.pdf")
        else:
            output_dir = Path(args.output or str(Path(args.input).with_suffix('.pdf'))).parent
            score_dir_name = args.score_name or video_name
            output_dir = file_service.prepare_output_dir(str(output_dir), score_dir_name)
            output_pdf = str(output_dir / f"{score_dir_name}.pdf")

        extract_use_case = ExtractScoreUseCase(video_service, ocr_service, file_service, config)

        try:
            pages = extract_use_case.execute(
                args.input,
                output_dir=output_dir,
                no_ocr=args.no_ocr,
                start_time=args.start_time,
                debug=args.debug,
                duration=args.duration,
                on_progress=lambda pct, msg: print(f"\r  [{pct:5.1f}%] {msg}", end="", flush=True) if pct > 0 else None,
            )
            print(f"\nExtraction complete: {len(pages)} pages found")

            if pages:
                print(f"Generating PDF: {output_pdf}")
                cropped_images = []
                for page in pages:
                    img = page.image
                    img_h = img.shape[0]
                    y_start = int(img_h * config.crop_top_offset)
                    y_end = int(img_h * (config.crop_top_offset + config.default_crop_ratio))
                    cropped_images.append(img[y_start:y_end, :])
                pdf_service.create_pdf(
                    cropped_images,
                    Path(output_pdf),
                    config,
                    title_hint=score_name,
                )
                print(f"PDF generated: {output_pdf}")

            if args.debug:
                print(f"Debug files kept in: {output_dir / 'debug'}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\n[Error] {e}")
            sys.exit(1)
        finally:
            video_service.close()


if __name__ == "__main__":
    main()
