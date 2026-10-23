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

    Extraction produces KEEP pages and DUPLICATE candidates; EXCLUDED is
    reserved for page selection.
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
    timestamp: float = 0.0

    def to_record(self) -> dict:
        """How this page is written into a saved score.

        One record per page, so a saved score describes the same pages the
        extraction produced.
        """
        return {
            "attempt": self.attempt_number,
            "boundary_row": self.boundary_row,
            "status": self.status.value,
        }

    def is_printed(self) -> bool:
        """Whether this page belongs in the generated PDF.

        Only KEEP pages print.  A page with no explicit status defaults to KEEP.
        """
        return self.status is PageStatus.KEEP

    @classmethod
    def from_record(cls, record: dict, image: np.ndarray,
                    file: Optional[str] = None) -> "Page":
        """Rebuild a page from a saved record.

        A record that is short or unreadable still gives a usable page: the
        facts that are missing fall back to their defaults.
        """
        row = record.get("boundary_row")
        try:
            status = PageStatus(record.get("status", PageStatus.KEEP.value))
        except ValueError:
            status = PageStatus.KEEP
        try:
            attempt = int(record.get("attempt", 0))
        except (TypeError, ValueError):
            attempt = 0
        return cls(
            image=image,
            boundary_row=int(row) if row is not None else None,
            attempt_number=attempt,
            file=file,
            status=status,
        )


@dataclass(eq=False)
class PageCandidate:
    """One page transition seen by extraction.

    Carries the facts needed to review a candidate without keeping its image
    in memory.  The image, when written, is on disk at ``file``.
    """

    attempt_number: int
    boundary_row: Optional[int] = None
    file: Optional[str] = None
    status: PageStatus = PageStatus.KEEP


@dataclass(frozen=True)
class PageState:
    """A read-only view of one page, as seen by a caller.

    Carries the page's position in the score together with the facts the page
    knows about itself (image, boundary row, file, status).  Callers read page
    state through this view so they never depend on how pages are stored; the
    storage is free to change without touching them.
    """

    index: int
    image: np.ndarray
    boundary_row: Optional[int] = None
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
