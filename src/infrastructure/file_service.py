import uuid
import shutil
import os
import time
from pathlib import Path
from src.domain.interfaces import IFileService

class FileService(IFileService):
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.sandbox_path: Optional[Path] = None

    def create_sandbox(self) -> Path:
        sandbox_id = uuid.uuid4()
        self.sandbox_path = self.base_dir / f"tmp_{sandbox_id}"
        self.sandbox_path.mkdir(parents=True, exist_ok=True)
        return self.sandbox_path

    def get_sandbox_path(self) -> Path:
        if not self.sandbox_path:
            raise RuntimeError("Sandbox not created.")
        return self.sandbox_path

    def move_to_final(self, source_name: str, destination_path: Path) -> None:
        if not self.sandbox_path:
            raise RuntimeError("Sandbox not created.")
        
        source_path = self.sandbox_path / source_name
        
        # Ensure destination directory exists
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                # shutil.move handles cross-device moves and unicode paths on Windows
                shutil.move(str(source_path), str(destination_path))
                break
            except PermissionError:
                print(f"\n[Error] Target file is locked: {destination_path}")
                input("Please close the PDF and press ENTER to retry...")
            except Exception as e:
                print(f"\n[Error] Failed to move file: {e}")
                raise

    def cleanup(self, force: bool = False) -> None:
        if self.sandbox_path and self.sandbox_path.exists():
            if force:
                shutil.rmtree(self.sandbox_path)
            else:
                # In a real app, we might check debug flag here
                shutil.rmtree(self.sandbox_path)
        self.sandbox_path = None
