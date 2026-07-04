import cv2
import numpy as np
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Tuple

class IVideoService(ABC):
    @abstractmethod
    def open_video(self, video_path: str) -> None:
        pass

    @abstractmethod
    def get_fps(self) -> float:
        pass

    @abstractmethod
    def read_frames(self):
        pass

    @abstractmethod
    def read_frame_at(self, frame_idx: int):
        pass

    @abstractmethod
    def merge_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, overlay_width_ratio: float = 0.5, crop_ratio: float = 0.35, min_diff_threshold: float = 500.0, bar_padding_px: int = 10, debug_save_path: Optional[str] = None) -> Tuple[np.ndarray, int]:
        """Applies Dynamic Bar Erase and merges Frame B onto Frame A. Returns (merged_image, bar_x)."""
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
    def load_page_images(self, score_dir: Path) -> List[np.ndarray]:
        """Loads all page_*_merged.png from photos/, ordered by page number."""
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

class IPdfService(ABC):
    @abstractmethod
    def create_pdf(self, images: List[np.ndarray], output_path: Path, config, title_hint: str = "") -> None:
        pass
