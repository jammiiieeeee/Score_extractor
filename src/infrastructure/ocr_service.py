import os
import re
import cv2
import numpy as np
import traceback
from typing import Optional, List, Tuple

# ===== CRITICAL FIX: SET ENV FLAGS BEFORE IMPORTING PADDLE =====
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_enable_mkldnn'] = '0'
os.environ['FLAGS_use_ngraph'] = 'False'
os.environ['PADDLE_DISABLE_STATIC'] = 'True'
os.environ['FLAGS_enable_pir_in_executor'] = '0'
os.environ['FLAGS_enable_pir_api'] = '0'

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False

from src.domain.interfaces import IOcrService

class OcrService(IOcrService):
    def __init__(self):
        self.ocr = None
        self.enabled = False

    def initialize(self) -> bool:
        if not PADDLE_AVAILABLE:
            print("Error: 'paddleocr' library not found. Please install requirements.")
            return False

        print("Initializing OCR engine...")

        # Test image with a number to verify detection + recognition
        test_img = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.putText(test_img, "123", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)

        # 3-attempt initialization logic
        initialization_attempts = [
            lambda: PaddleOCR(lang='en', enable_mkldnn=False),
            lambda: PaddleOCR(enable_mkldnn=False),
            lambda: PaddleOCR()
        ]

        for i, init_func in enumerate(initialization_attempts):
            try:
                print(f"  Attempt {i+1}...")
                self.ocr = init_func()
                res = self.ocr.ocr(test_img)
                if res:
                    print(f"  SUCCESS (Attempt {i+1})")
                    self.enabled = True
                    return True
            except Exception as e:
                print(f"  Attempt {i+1} FAILED - {e}")

        print("All PaddleOCR initialization attempts failed!")
        self.enabled = False
        return False

    def is_enabled(self) -> bool:
        return self.enabled

    def detect_keywords(self, image: np.ndarray, keywords: List[str]) -> bool:
        if not self.enabled or self.ocr is None:
            return False

        try:
            results = self.ocr.ocr(image)
            if not results or not results[0]:
                return False

            data_source = results[0]
            texts = []

            if isinstance(data_source, dict):
                texts = data_source.get('rec_texts', [])
            elif isinstance(data_source, list):
                texts = [line[1][0] for line in data_source if line and len(line) >= 2]

            text_lower = " ".join(texts).lower()
            return any(kw.lower() in text_lower for kw in keywords)

        except Exception:
            return False

    def get_texts(self, image: np.ndarray) -> List[str]:
        if not self.enabled or self.ocr is None:
            return []

        try:
            results = self.ocr.ocr(image)
            if not results or not results[0]:
                return []

            data_source = results[0]
            if isinstance(data_source, dict):
                return data_source.get('rec_texts', [])
            elif isinstance(data_source, list):
                return [line[1][0] for line in data_source if line and len(line) >= 2]
            return []
        except Exception:
            return []

    def get_leftmost_number(self, image: np.ndarray, vertical_range: float, horizontal_ratio: float = 1.0, confidence_threshold: int = 0) -> Optional[int]:
        if not self.enabled or self.ocr is None:
            return None

        height, width = image.shape[:2]
        max_y = int(height * vertical_range)
        max_x = int(width * horizontal_ratio)
        roi = image[:max_y, :max_x]

        try:
            results = self.ocr.ocr(roi)
            if not results or not results[0]:
                return None

            candidates = []

            data_source = results[0]

            if isinstance(data_source, dict):
                # Format 1: Dictionary (PaddleOCR v2.7+)
                texts = data_source.get('rec_texts', [])
                scores = data_source.get('rec_scores', [])
                polys = data_source.get('rec_polys', [])
                for i, text in enumerate(texts):
                    text = text.strip()
                    if re.fullmatch(r'\d+', text):
                        if i < len(scores) and int(scores[i] * 100) < confidence_threshold:
                            continue
                        bbox = polys[i] if i < len(polys) else None
                        if bbox is not None:
                            min_x = min(point[0] for point in bbox)
                            candidates.append((min_x, int(text)))

            elif isinstance(data_source, list):
                # Format 2: Legacy List Format
                for line in data_source:
                    if line and len(line) >= 2:
                        bbox = line[0]
                        text = line[1][0].strip()
                        score = line[1][1]
                        if re.fullmatch(r'\d+', text):
                            if int(score * 100) < confidence_threshold:
                                continue
                            min_x = min(point[0] for point in bbox)
                            candidates.append((min_x, int(text)))

            if not candidates:
                return None

            candidates.sort(key=lambda x: x[0])
            return candidates[0][1]

        except Exception as e:
            print(f"OCR internal error: {e}")
            return None
