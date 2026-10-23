import io
from pathlib import Path
from typing import List
import cv2
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from src.domain.interfaces import IPdfService
from src.domain.models import Page
from src.domain.page_crop import crop_page
from src.domain.value_objects.config import ScoreConfig

class PdfService(IPdfService):
    def create_pdf(self, pages: List[Page], output_path: Path, config: ScoreConfig,
                   title_hint: str = "") -> None:
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

        for page in pages:
            if not page.is_printed():
                continue
            # The page images are always full merged frames (single-crop
            # model): extraction never crops, it only records the boundary row
            # measured for the page.  The crop itself is decided by the shared
            # rule in src/domain/page_crop.py, from the page and the config:
            #   off    -> no crop (full frame)
            #   manual -> fixed default_crop_ratio for every page
            #   auto   -> crop at (boundary_row - offset) for pages that have a
            #             row, else default_crop_ratio
            # The row was measured on the same merged frame that is saved as
            # the page image, so it is already in this image's pixel space.
            cropped_img = crop_page(page, config)

            success, buf = cv2.imencode('.png', cropped_img)
            if not success:
                continue
            img_reader = ImageReader(io.BytesIO(buf.tobytes()))

            strip_aspect = cropped_img.shape[1] / cropped_img.shape[0]
            draw_width = usable_width
            draw_height = draw_width / strip_aspect

            if y_offset - draw_height < margin:
                c.showPage()
                y_offset = height - margin

            c.drawImage(img_reader, margin, y_offset - draw_height, width=draw_width, height=draw_height)
            y_offset -= draw_height

        c.save()
