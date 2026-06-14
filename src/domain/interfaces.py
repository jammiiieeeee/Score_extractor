import cv2
import numpy as np
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Tuple

class IVideoService(ABC):
    @abstractmethod
    def open_video(self, video_path: str) -> None:
        """Opens the video file."""
        pass

    @abstractmethod
    def get_fps(self) -> float:
        """Returns video FPS."""
        pass

    @abstractmethod
    def read_frames(self):
        """Generator that yields frames with timestamps."""
        pass

    @abstractmethod
    def read_frame_at(self, frame_idx: int):
        """Seeks to and reads a specific frame by index."""
        pass

    @abstractmethod
    def merge_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, overlay_width_ratio: float = 0.2) -> Tuple[np.ndarray, int]:
        """Applies Dynamic Bar Erase and merges Frame B onto Frame A. Returns (merged_image, bar_x)."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Releases video resources."""
        pass

    @abstractmethod
    def get_total_frames(self) -> int:
        """Returns total frame count of the video."""
        pass

class IFileService(ABC):
    @abstractmethod
    def create_sandbox(self) -> Path:
        """Creates a UUID-based sandbox directory."""
        pass

    @abstractmethod
    def get_sandbox_path(self) -> Path:
        """Returns the current sandbox path."""
        pass

    @abstractmethod
    def move_to_final(self, source_name: str, destination_path: Path) -> None:
        """Moves a file from the sandbox to the final destination, handling locks."""
        pass

    @abstractmethod
    def cleanup(self, force: bool = False) -> None:
        """Removes the sandbox directory."""
        pass

class IOcrService(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        """Initializes the OCR engine with fallback. Returns False if all fail."""
        pass

    @abstractmethod
    def get_leftmost_number(self, image: np.ndarray, vertical_range: float, horizontal_ratio: float = 1.0, confidence_threshold: int = 0) -> Optional[int]:
        """Extracts the leftmost number from the top vertical_range of the image, constrained to left horizontal_ratio."""
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Returns True if the OCR service is operational."""
        pass

    @abstractmethod
    def detect_keywords(self, image: np.ndarray, keywords: List[str]) -> bool:
        """Returns True if any keyword text is found in the image."""
        pass

    @abstractmethod
    def get_texts(self, image: np.ndarray) -> List[str]:
        """Returns list of recognized text strings in the image."""
        pass

class IPdfService(ABC):
    @abstractmethod
    def create_pdf(self, images: List[np.ndarray], output_path: Path, config, title_hint: str = "") -> None:
        """Creates a PDF from a list of images. title_hint overrides the file-stem title."""
        pass
