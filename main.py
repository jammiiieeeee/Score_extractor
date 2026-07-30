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
from src.infrastructure.download_service import DownloadService
from src.application.use_cases import ExtractScoreUseCase, GeneratePdfUseCase
from src.domain.models import Frame


def load_config(config_path: str) -> ScoreConfig:
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return ScoreConfig(**data)
        except Exception as e:
            print(f"[WARN] Config load failed: {e}")
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
    parser.add_argument("input", nargs="?", default=None, help="Path to the input video file or YouTube URL")
    parser.add_argument("-o", "--output", help="Output PDF path (default: input name with .pdf)")
    parser.add_argument("--output-dir", help="Output folder for organized score (creates <score_name>/photos/ etc.)")
    parser.add_argument("--score-name", help="Score name (default: video filename stem)")
    parser.add_argument("-c", "--config", default="config.json", help="Path to config.json")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR for deduplication (off by default)")
    parser.add_argument("--start-time", type=float, default=2.0, help="Jump to this time in seconds and capture the first page immediately (default: 2.0)")
    parser.add_argument("--end-offset", type=float, default=0.0, help="Stop processing N seconds before video end (0 = off)")
    parser.add_argument("--crop-ratio", type=float, help="Override crop ratio for PDF output")
    parser.add_argument("--from-dir", help="Regenerate PDF from an existing score directory (skips video extraction)")
    parser.add_argument("--yt-url", help="YouTube URL to download before extraction")
    parser.add_argument("--quality", choices=["1080p", "720p", "480p", "360p"], default="1080p", help="Video quality for YouTube download (default: 1080p)")

    args = parser.parse_args()

    config = load_config(args.config)

    if args.crop_ratio is not None:
        config.default_crop_ratio = args.crop_ratio

    if args.from_dir:
        score_dir = Path(args.from_dir)
        if not score_dir.is_dir():
            print(f"[ERROR] Dir not found: {args.from_dir}")
            sys.exit(1)

        images = FileService().load_page_images(score_dir)
        if not images:
            print(f"[ERROR] No images in {score_dir}/photos/")
            sys.exit(1)

        print(f"Loaded {len(images)} images from {args.from_dir}")

        output_path = args.output or str(score_dir / f"{score_dir.name}.pdf")
        pdf_service = PdfService()
        pdf_service.create_pdf(images, Path(output_path), config, title_hint=Path(output_path).stem)
        print(f"\nPDF saved: {output_path}")

    else:
        # Determine video path - handle YouTube URLs
        video_path = args.input
        is_youtube = False

        if args.yt_url:
            # Explicit YouTube URL flag
            video_path = args.yt_url
            is_youtube = True
        elif video_path and (video_path.startswith("http") or video_path.startswith("www.") or 
                            "youtube.com" in video_path or "youtu.be" in video_path):
            # Auto-detect YouTube URL from positional arg
            is_youtube = True

        # Download YouTube video if needed
        if is_youtube:
            print(f"Downloading: {video_path}")
            download_service = DownloadService(Path.cwd())
            
            # Map quality to format selector
            quality_map = {
                "1080p": "bestvideo[height<=1080][fps<=30]",
                "720p": "bestvideo[height<=720][fps<=30]",
                "480p": "bestvideo[height<=480][fps<=30]",
                "360p": "best[height<=360][fps<=30]",
            }
            fmt = quality_map.get(args.quality, "bestvideo[height<=1080]")
            
            result = download_service.download(
                video_path,
                fmt=fmt,
                on_progress=lambda pct, msg: print(f"\r  [{pct:5.1f}%] {msg}", end="", flush=True),
                on_log=lambda msg: print(msg),
            )
            video_path = result.video_path
            print(f"\nDownloaded: {result.video_title}")
            print(f"Saved to: {video_path}")
            
            # Use video title as score name if not specified
            if not args.score_name:
                args.score_name = result.video_title
        elif not video_path or not os.path.exists(video_path):
            print(f"[ERROR] Not found: {video_path}")
            sys.exit(1)

        video_service = VideoService()
        ocr_service = None
        if args.ocr:
            from src.infrastructure.ocr_service import OcrService
            ocr_service = OcrService()
        pdf_service = PdfService()
        file_service = FileService()

        video_name = Path(video_path).stem
        score_name = args.score_name or video_name

        if args.output_dir:
            output_dir = file_service.prepare_output_dir(args.output_dir, score_name)
            output_pdf = args.output or str(output_dir / f"{score_name}.pdf")
        else:
            output_dir = Path(args.output or str(Path(video_path).with_suffix('.pdf'))).parent
            score_dir_name = args.score_name or video_name
            output_dir = file_service.prepare_output_dir(str(output_dir), score_dir_name)
            output_pdf = str(output_dir / f"{score_dir_name}.pdf")

        extract_use_case = ExtractScoreUseCase(video_service, ocr_service, file_service, config)

        try:
            pages, manifest = extract_use_case.execute(
                video_path,
                output_dir=output_dir,
                no_ocr=not args.ocr,
                start_time=args.start_time,
                debug=args.debug,
                end_offset=args.end_offset,
                on_progress=lambda pct, msg: print(f"\r  [{pct:5.1f}%] {msg}", end="", flush=True),
            )
            print(f"\nExtracted: {len(pages)} pages")

            if pages:
                print(f"PDF: {output_pdf}")
                cropped_images = []
                for page in pages:
                    img = page.image
                    img_h = img.shape[0]
                    y_start = 0
                    y_end = int(img_h * config.default_crop_ratio)
                    cropped_images.append(img[y_start:y_end, :])
                pdf_service.create_pdf(
                    cropped_images,
                    Path(output_pdf),
                    config,
                    title_hint=score_name,
                )
                print(f"PDF saved: {output_pdf}")

            if args.debug:
                print(f"Debug: {output_dir / 'debug'}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\n[ERROR] {e}")
            sys.exit(1)
        finally:
            video_service.close()


if __name__ == "__main__":
    main()
