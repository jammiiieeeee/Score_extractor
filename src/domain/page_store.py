import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from src.domain.models import Frame, Page


@dataclass
class PageStore:
    """Encapsulates the page state.

    Holds one copy of each page: _pages (the page objects, each carrying its
    own image, boundary row, file and status).  The encoded PNG of a page is
    cached against that page itself, so there is no second list to keep in
    step - a cache entry belongs to the page it was made from.
    """

    _pages: List[Page] = field(default_factory=list)
    _png_cache: Dict[Page, bytes] = field(default_factory=dict)

    # Queries -------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._pages)

    def __bool__(self) -> bool:
        return len(self._pages) > 0

    def __getitem__(self, index: int) -> Page:
        return self.get(index)

    def get(self, index: int) -> Page:
        """The page at that position.

        Raises IndexError for any index outside the store, negative included:
        a negative index must not silently address the last page.
        """
        if index < 0 or index >= len(self._pages):
            raise IndexError(f"Page index {index} out of range (0-{len(self._pages) - 1})")
        return self._pages[index]

    def get_image(self, index: int) -> np.ndarray:
        return self.get(index).image

    def all_pages(self) -> List[Page]:
        return list(self._pages)

    def all_images(self) -> List[np.ndarray]:
        return [p.image for p in self._pages]

    @staticmethod
    def as_page(page: Union[Page, Frame]) -> Page:
        """Accept either a Page or a bare Frame and return a Page."""
        if isinstance(page, Page):
            return page
        return Page(image=page.image)

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
        page = self._pages[index]
        cached = self._png_cache.get(page)
        if cached is not None:
            return cached
        png = self.encode_png(page.image)
        if png is None:
            return None
        self._png_cache[page] = png
        return png

    # Mutations -----------------------------------------------------------

    def add(self, page: Union[Page, Frame], png: Optional[bytes] = None) -> int:
        """Append a page. Returns the new index."""
        page = self.as_page(page)
        self._pages.append(page)
        if png is not None:
            self._png_cache[page] = png
        return len(self._pages) - 1

    def set_pages(self, pages: List[Union[Page, Frame]]) -> None:
        """Replace working pages entirely (e.g. after extraction completes)."""
        self._pages = [self.as_page(p) for p in pages]
        self._png_cache = {}

    def remove(self, index: int) -> None:
        page = self.get(index)
        self._pages.pop(index)
        self._png_cache.pop(page, None)

    def clear(self) -> None:
        """Clear all pages (full reset)."""
        self._pages.clear()
        self._png_cache.clear()
