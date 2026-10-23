import cv2
import numpy as np
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Tuple

from src.domain.models import MergeResult, Page

class IVideoService(ABC):
    @abstractmethod
    def open_video(self, video_path: str) -> None:
        pass

    @abstractmethod
    def get_fps(self) -> float:
        pass

    @abstractmethod
    def get_original_size(self):
        """Returns (width, height) of the original video frames."""
        pass

    @abstractmethod
    def read_frames(self):
        pass

    @abstractmethod
    def read_frame_at(self, frame_idx: int):
        """Returns (frame, timestamp) at the video's native resolution."""
        pass

    @abstractmethod
    def read_next_frame(self):
        """Reads the next frame sequentially (no seek). Returns (frame, timestamp, frame_idx) or (None, None, None)."""
        pass

    @abstractmethod
    def skip_frames(self, count: int):
        """Read and discard count frames without decoding (faster)."""
        pass

    @abstractmethod
    def read_full_frame_at(self, frame_idx: int):
        """Returns (frame_full_res, timestamp) without resizing."""
        pass

    @abstractmethod
    def merge_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, overlay_width_ratio: float = 0.5, bar_analysis_ratio: float = 0.32, min_diff_threshold: float = 500.0, bar_padding_px: int = -15, debug_save_path: Optional[str] = None) -> MergeResult:
        """Detect bar edge via spike detection and merge Frame B onto Frame A.
        
        If exactly 2 spikes are found, sets the overlay cutoff to the midpoint between them.
        Otherwise returns frame A unchanged.
        
        Returns MergeResult containing the merged image, merge point, and debug data.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def get_total_frames(self) -> int:
        pass

class IFileService(ABC):
    @abstractmethod
    def prepare_output_dir(self, output_folder: str, score_name: str) -> Path:
        """Creates output_folder/score_name/ with photos/, video/, debug/ subdirs. Returns the score dir."""
        pass

    @abstractmethod
    def save_page_image(self, score_dir: Path, page_num: int, image: np.ndarray) -> Path:
        """Saves page_NNN_merged.png to photos/. Returns the file path."""
        pass

    @abstractmethod
    def save_candidate_image(self, score_dir: Path, page_num: int, image: np.ndarray) -> Path:
        """Saves page_NNN_merged.png to candidates/. Returns the file path."""
        pass

    @abstractmethod
    def load_page_images(self, score_dir: Path) -> List[np.ndarray]:
        """Loads all page_*_merged.png from photos/, ordered by page number."""
        pass

    @abstractmethod
    def load_page_images_with_paths(self, score_dir: Path) -> List[Tuple[Path, np.ndarray]]:
        """Loads the saved pages, each with the file it came from."""
        pass

    @abstractmethod
    def delete_page_image(self, path: str) -> bool:
        """Deletes one saved page image. Returns True when a file was removed."""
        pass

    @abstractmethod
    def list_saved_scores(self, output_folder: str) -> List[dict]:
        """Lists score dirs under output_folder that contain photos/.
        Returns list of {path, page_count, created, score_name}."""
        pass

class IOcrService(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def get_leftmost_number(self, image: np.ndarray, vertical_range: float, horizontal_ratio: float = 1.0, confidence_threshold: int = 0) -> Optional[int]:
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        pass

    @abstractmethod
    def detect_keywords(self, image: np.ndarray, keywords: List[str]) -> bool:
        pass

    @abstractmethod
    def get_texts(self, image: np.ndarray) -> List[str]:
        pass

class _NoopOcrService(IOcrService):
    def initialize(self) -> bool:
        return False
    def get_leftmost_number(self, image: np.ndarray, vertical_range: float, horizontal_ratio: float = 1.0, confidence_threshold: int = 0) -> Optional[int]:
        return None
    def is_enabled(self) -> bool:
        return False
    def detect_keywords(self, image: np.ndarray, keywords: List[str]) -> bool:
        return False
    def get_texts(self, image: np.ndarray) -> List[str]:
        return []

class IPdfService(ABC):
    @abstractmethod
    def create_pdf(self, pages: List[Page], output_path: Path, config, title_hint: str = "") -> None:
        """Build a PDF from pages.

        Each page is cropped by the shared crop rule (src/domain/page_crop.py),
        so an image and its crop can never drift apart.
        """
        pass
