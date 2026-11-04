import numpy as np
import pytest

from src.application.use_cases import GenerateOmrUseCase
from src.domain.models import Page
from src.domain.value_objects.config import ScoreConfig


class FakeOmrService:
    def __init__(self):
        self.available = True
        self.recognized = []
        self.merged = None
        self.midi = None

    def is_available(self):
        return self.available

    def recognize_page(self, image_path, output_dir, without_deskew=True):
        self.recognized.append(image_path)
        return str(output_dir) + f"/page_{len(self.recognized)}.musicxml"

    def merge_musicxml(self, xml_paths, output_path):
        self.merged = (list(xml_paths), output_path)
        return output_path

    def musicxml_to_midi(self, xml_path, midi_path):
        self.midi = (xml_path, midi_path)
        return midi_path


def make_pages(n=2):
    pages = []
    for i in range(n):
        img = np.full((60, 80, 3), 200, dtype=np.uint8)
        pages.append(Page(image=img, status=__import__("src.domain.models", fromlist=["PageStatus"]).PageStatus.KEEP))
    return pages


def test_generate_omr_runs_per_page_and_merges(tmp_path):
    svc = FakeOmrService()
    uc = GenerateOmrUseCase(svc, ScoreConfig())
    pages = make_pages(2)
    result = uc.execute(pages, tmp_path, "MyScore", without_deskew=True)
    assert len(svc.recognized) == 2
    assert svc.merged is not None
    assert svc.merged[1].endswith("MyScore.musicxml")
    assert svc.midi[1].endswith("MyScore.mid")
    assert result.musicxml_path.endswith("MyScore.musicxml")
    assert result.midi_path.endswith("MyScore.mid")


def test_generate_omr_rejects_no_included_pages(tmp_path):
    svc = FakeOmrService()
    uc = GenerateOmrUseCase(svc, ScoreConfig())
    # excluded page
    from src.domain.models import PageStatus
    pages = [Page(image=np.zeros((10, 10, 3), dtype=np.uint8), status=PageStatus.EXCLUDED)]
    with pytest.raises(RuntimeError):
        uc.execute(pages, tmp_path, "X")