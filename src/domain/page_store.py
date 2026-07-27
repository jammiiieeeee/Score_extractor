import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from src.domain.models import Frame


@dataclass
class PageStore:
    """Encapsulates the dual-list page state.

    Manages _pages + _page_png_cache (working copy) and
    _original_pages + _original_png_cache (untouched originals for re-crop).
    Every mutation is atomic — the four lists are always in sync.
    """

    _pages: List[Frame] = field(default_factory=list)
    _png_cache: List[Optional[bytes]] = field(default_factory=list)
    _original_pages: List[Frame] = field(default_factory=list)
    _original_png_cache: List[Optional[bytes]] = field(default_factory=list)

    # ── Queries ───────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._pages)

    def __bool__(self) -> bool:
        return len(self._pages) > 0

    def __getitem__(self, index: int) -> Frame:
        return self._pages[index]

    def get(self, index: int) -> Frame:
        return self._pages[index]

    def get_image(self, index: int) -> np.ndarray:
        return self._pages[index].image

    def all_frames(self) -> List[Frame]:
        return list(self._pages)

    def all_images(self) -> List[np.ndarray]:
        return [f.image for f in self._pages]

    def has_originals(self) -> bool:
        return len(self._original_pages) > 0

    @staticmethod
    def encode_png(img: np.ndarray) -> Optional[bytes]:
        success, buf = cv2.imencode('.png', img)
        if not success:
            return None
        return buf.tobytes()

    @staticmethod
    def decode_png(data: bytes) -> Optional[np.ndarray]:
        buf = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def get_thumbnail(self, index: int, thumb_width: int = 320) -> Optional[bytes]:
        if index < 0 or index >= len(self._pages):
            return None
        img = self._pages[index].image
        h, w = img.shape[:2]
        thumb_h = int(h * (thumb_width / w))
        thumb = cv2.resize(img, (thumb_width, thumb_h))
        return self.encode_png(thumb)

    def get_full_png(self, index: int) -> Optional[bytes]:
        if index < 0 or index >= len(self._pages):
            return None
        if self._png_cache[index] is not None:
            return self._png_cache[index]
        png = self.encode_png(self._pages[index].image)
        self._png_cache[index] = png
        return png

    # ── Mutations ─────────────────────────────────────────────────────

    def add(self, frame: Frame, png: Optional[bytes] = None) -> int:
        """Append a page. Returns the new index."""
        self._pages.append(frame)
        self._png_cache.append(png if png is not None else self.encode_png(frame.image))
        return len(self._pages) - 1

    def set_pages(self, frames: List[Frame]) -> None:
        """Replace working pages entirely (e.g. after extraction completes)."""
        self._pages = list(frames)
        self._png_cache = [self.encode_png(f.image) for f in frames]

    def remove(self, index: int) -> None:
        if index < 0 or index >= len(self._pages):
            raise IndexError(f"Page index {index} out of range (0-{len(self._pages) - 1})")
        self._pages.pop(index)
        self._png_cache.pop(index)

    def reorder(self, new_order: List[int]) -> None:
        if len(new_order) != len(self._pages):
            raise ValueError(f"New order length {len(new_order)} must match page count {len(self._pages)}")
        if set(new_order) != set(range(len(self._pages))):
            raise ValueError("New order must be a permutation of 0..N-1")
        self._pages = [self._pages[i] for i in new_order]
        self._png_cache = [self._png_cache[i] for i in new_order]

    def clear(self) -> None:
        """Clear all pages AND originals (full reset)."""
        self._pages.clear()
        self._png_cache.clear()
        self._original_pages.clear()
        self._original_png_cache.clear()

    def clear_working(self) -> None:
        """Clear only working pages, keep originals for re-crop."""
        self._pages.clear()
        self._png_cache.clear()

    # ── Original management (for loaded scores + re-crop) ─────────────

    def set_originals(self, frames: List[Frame]) -> None:
        self._original_pages = list(frames)
        self._original_png_cache = [self.encode_png(f.image) for f in frames]

    def reapply_crop(self, offset: float, ratio: float) -> None:
        """Re-crop originals with a new offset and ratio, replacing working pages.

        Uses the same model as PdfService: crop from offset to offset+ratio.
        """
        if not self._original_pages:
            return
        self._pages.clear()
        self._png_cache.clear()
        for frame in self._original_pages:
            h = frame.image.shape[0]
            y_start = int(h * offset)
            y_end = int(h * (offset + ratio))
            cropped = frame.image[y_start:y_end, :].copy()
            new_frame = Frame(cropped, frame.timestamp, frame.index)
            self._pages.append(new_frame)
            self._png_cache.append(self.encode_png(cropped))
