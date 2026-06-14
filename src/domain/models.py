import numpy as np
from dataclasses import dataclass
from typing import Optional

from src.domain.value_objects.config import ScoreConfig

@dataclass
class Frame:
    image: np.ndarray
    timestamp: float
    index: int
    path: Optional[str] = None
