import os
from pathlib import Path
from typing import List
import numpy as np
import cv2
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from src.domain.interfaces import IPdfService
from src.domain.value_objects.config import ScoreConfig

class PdfService(IPdfService):
    def create_pdf(self, images: List[np.ndarray], output_path: Path, config: ScoreConfig, title_hint: str = "") -> None:
        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4

        margin = 36
        usable_width = width - 2 * margin

        y_offset = height - margin

        if title_hint:
            title = title_hint
        else:
            title = output_path.stem.replace('_', ' ').replace('-', ' ')

        # Register CJK font for Japanese/Chinese filenames, fallback to Helvetica
        try:
            pdfmetrics.registerFont(TTFont("CJK", "C:/Windows/Fonts/msgothic.ttc"))
            c.setFont("CJK", 18)
        except Exception:
            c.setFont("Helvetica-Bold", 18)

        c.drawCentredString(width / 2, height - margin, title)
        y_offset -= 40

        strips_on_page = 0

        for idx, img in enumerate(images):
            img_h, img_w = img.shape[:2]
            y_start = int(img_h * config.crop_top_offset)
            y_end = int(img_h * (config.crop_top_offset + config.default_crop_ratio))
            cropped_img = img[y_start:y_end, :]

            temp_img_path = f"temp_strip_{idx}.png"
            cv2.imwrite(temp_img_path, cropped_img)

            strip_aspect = cropped_img.shape[1] / cropped_img.shape[0]
            draw_width = usable_width
            draw_height = draw_width / strip_aspect

            if y_offset - draw_height < margin or strips_on_page >= config.default_strips_per_page:
                c.showPage()
                y_offset = height - margin
                strips_on_page = 0

            c.drawImage(temp_img_path, margin, y_offset - draw_height, width=draw_width, height=draw_height)
            y_offset -= draw_height
            strips_on_page += 1

        c.save()
