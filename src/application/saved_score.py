"""The pages of a saved score.

One place reads a score directory: the page images, the page records written
with them, and the crop the score was saved with.  The GUI and the command
line both go through here, so both see the same pages, cropped the same way.

A score saved now carries one record per page.  A score saved before that
carries a bare list of boundary rows, which is read as a fallback.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from src.domain.interfaces import IFileService
from src.domain.models import Page
from src.domain.value_objects.config import ScoreConfig


@dataclass
class SavedScore:
    """A score that was saved: its pages, its metadata and its crop."""

    pages: List[Page] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def read_metadata(score_dir) -> dict:
    """The metadata of a score directory (empty when there is none)."""
    meta_path = Path(score_dir) / "metadata.json"
    if not meta_path.exists():
        return {}
    try:
        with open(str(meta_path), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def apply_saved_crop(config: ScoreConfig, metadata: dict) -> None:
    """Put the config on the crop the score was saved with.

    A score is read the way it was cropped, so opening it again gives back
    the same pages.
    """
    ratio = metadata.get("crop_ratio")
    if ratio is not None:
        config.default_crop_ratio = ratio
    mode = metadata.get("boundary_mode")
    if mode:
        config.boundary_mode = mode
    offset = metadata.get("boundary_offset_px")
    if offset is not None:
        config.boundary_offset_px = int(offset)


def pages_from_records(saved: list, metadata: dict) -> List[Page]:
    """The pages of a saved score, with the crop they were saved with.

    `saved` is the page images, each with the file it came from.
    """
    records = metadata.get("pages")
    if records is not None:
        pages = []
        for i, (file_path, img) in enumerate(saved):
            record = records[i] if i < len(records) else {}
            pages.append(Page.from_record(record, img, file=str(file_path)))
        return pages

    rows = metadata.get("page_boundary_rows") or []
    return [
        Page(image=img, boundary_row=rows[i] if i < len(rows) else None,
             file=str(file_path))
        for i, (file_path, img) in enumerate(saved)
    ]


def read_saved_score(score_dir, file_service: IFileService,
                     config: ScoreConfig) -> SavedScore:
    """Read a score directory into its pages.

    The config is put on the crop the score was saved with, so the caller
    crops the pages the way the score was cropped.
    """
    score_dir = Path(score_dir)
    metadata = read_metadata(score_dir)
    saved = file_service.load_page_images_with_paths(score_dir)
    apply_saved_crop(config, metadata)
    return SavedScore(pages=pages_from_records(saved, metadata), metadata=metadata)
