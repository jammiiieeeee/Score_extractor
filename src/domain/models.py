import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional

from src.domain.value_objects.config import ScoreConfig

@dataclass
class Frame:
    image: np.ndarray
    timestamp: float
    index: int
    path: Optional[str] = None


@dataclass
class PageManifestEntry:
    page: int
    timestamp: float
    frame_index: int
    bar_x: int = 0
    bar_width: int = 0
    merge_x: int = 0
    is_duplicate: bool = False
    ocr_number: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
