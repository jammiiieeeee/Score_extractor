import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional
from src.domain.interfaces import IFileService

class FileService(IFileService):
    def __init__(self, base_dir: str = "debug"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def prepare_output_dir(self, output_folder: str, score_name: str) -> Path:
        score_dir = Path(output_folder) / score_name
        (score_dir / "photos").mkdir(parents=True, exist_ok=True)
        (score_dir / "video").mkdir(parents=True, exist_ok=True)
        (score_dir / "debug").mkdir(parents=True, exist_ok=True)
        return score_dir

    def save_page_image(self, score_dir: Path, page_num: int, image: np.ndarray) -> Path:
        path = score_dir / "photos" / f"page_{page_num:03d}_merged.png"
        ext = path.suffix
        success, buf = cv2.imencode(ext, image)
        if success:
            buf.tofile(str(path))
        return path

    def load_page_images(self, score_dir: Path) -> List[np.ndarray]:
        files = sorted(
            (score_dir / "photos").glob("page_*_merged.png"),
            key=lambda f: int(f.stem.split("_")[1])
        )
        images = []
        for f in files:
            file_bytes = np.fromfile(str(f), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                images.append(img)
        return images

    def list_saved_scores(self, output_folder: str) -> List[dict]:
        results = []
        base = Path(output_folder)
        if not base.exists():
            return results
        for d in base.iterdir():
            if d.is_dir() and (d / "photos").is_dir():
                page_files = sorted(d.glob("photos/page_*_merged.png"))
                results.append({
                    "path": str(d),
                    "page_count": len(page_files),
                    "score_name": d.name,
                })
        results.sort(key=lambda x: x["score_name"])
        return results
