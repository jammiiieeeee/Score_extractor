import cv2
import re
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple
from src.domain.interfaces import IFileService

class FileService(IFileService):
    def __init__(self, base_dir: str = "debug"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    _WINDOWS_RESERVED = (
        {"CON", "PRN", "AUX", "NUL"}
        | {f"COM{i}" for i in range(1, 10)}
        | {f"LPT{i}" for i in range(1, 10)}
    )

    @staticmethod
    def _sanitize_path_name(name: str) -> str:
        """Remove characters invalid for Windows folder names."""
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        name = name.strip('. ')
        name = re.sub(r'\s+', ' ', name)
        name = name[:100] if name else "untitled"
        stem, sep, suffix = name.rpartition('.')
        if sep:
            stem = stem or name
        else:
            stem, suffix = name, ""
        if stem.upper() in FileService._WINDOWS_RESERVED:
            name = stem + "_" + (("." + suffix) if suffix else "")
        return name

    def prepare_output_dir(self, output_folder: str, score_name: str) -> Path:
        score_name = self._sanitize_path_name(score_name)
        score_dir = Path(output_folder) / score_name
        (score_dir / "photos").mkdir(parents=True, exist_ok=True)
        (score_dir / "video").mkdir(parents=True, exist_ok=True)
        (score_dir / "diagnostics").mkdir(parents=True, exist_ok=True)
        return score_dir

    def save_page_image(self, score_dir: Path, page_num: int, image: np.ndarray) -> Path:
        path = score_dir / "photos" / f"page_{page_num:03d}_merged.png"
        ext = path.suffix
        success, buf = cv2.imencode(ext, image)
        if success:
            buf.tofile(str(path))
        return path

    def load_page_images(self, score_dir: Path) -> List[np.ndarray]:
        return [image for _, image in self.load_page_images_with_paths(score_dir)]

    def load_page_images_with_paths(self, score_dir: Path) -> List[Tuple[Path, np.ndarray]]:
        """The saved pages, each with the file it came from.

        The file travels with its image, so a page can be deleted again later
        without guessing which file belongs to it.
        """
        files = sorted(
            (score_dir / "photos").glob("page_*_merged.png"),
            key=lambda f: int(f.stem.split("_")[1])
        )
        pages = []
        for f in files:
            file_bytes = np.fromfile(str(f), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is not None:
                pages.append((f, img))
        return pages

    def delete_page_image(self, path: str) -> bool:
        """Delete one saved page image. Returns True when a file was removed."""
        if not path:
            return False
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            return False
        return True

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
