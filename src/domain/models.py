import numpy as np
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional

from src.domain.value_objects.config import ScoreConfig

@dataclass
class MergeResult:
    merged: np.ndarray
    merge_x: int
    col_sums: np.ndarray
    spikes: list


class PageStatus(str, Enum):
    """The role of a page inside a score.

    KEEP      - the page belongs to the score.
    EXCLUDED  - the page was taken out by hand (page selection).
    DUPLICATE - the page repeats an earlier page.

    Only KEEP is produced by extraction today; the other two exist so page
    selection can be added later without another migration.
    """

    KEEP = "keep"
    EXCLUDED = "excluded"
    DUPLICATE = "duplicate"


@dataclass(eq=False)
class Page:
    """One page of a score, with everything known about it.

    A page carries its own image and the facts measured for that image: the
    boundary row that was detected on it, the attempt that produced it, the
    file it was written to, and its status.  Nothing about a page lives in a
    list somewhere else, so an image and its measurements cannot drift apart.

    Equality is identity: two pages are the same page only when they are the
    same object, because the image is a numpy array.
    """

    image: np.ndarray
    boundary_row: Optional[int] = None
    attempt_number: int = 0
    file: Optional[str] = None
    status: PageStatus = PageStatus.KEEP


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
    ssim_score: Optional[float] = None
    guard_rail_passed: bool = True
    attempt_duration_ms: float = 0.0
    boundary_row: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)
