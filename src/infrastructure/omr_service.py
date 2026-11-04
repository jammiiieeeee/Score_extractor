"""OMR adapter: homr for recognition, music21 for merging and MIDI export."""

import os
import subprocess
from pathlib import Path
from typing import List

from src.domain.interfaces import IOmrService


class OmrService(IOmrService):
    def is_available(self) -> bool:
        try:
            import music21  # noqa: F401
        except Exception:
            return False
        # homr must be on PATH
        try:
            subprocess.run(["homr", "--version"], capture_output=True, timeout=10)
            return True
        except Exception:
            # homr may not support --version; try invoking help
            try:
                r = subprocess.run(["homr"], capture_output=True, timeout=10)
                # homr with no args exits non-zero but is present
                return True
            except FileNotFoundError:
                return False
            except Exception:
                return True

    def _require(self):
        if not self.is_available():
            raise RuntimeError(
                "OMR dependencies are not installed. "
                "Install them with: pip install -r requirements-omr.txt"
            )
    def recognize_page(self, image_path: str, output_dir: str,
                       without_deskew: bool = True,
                       use_tf: bool = False) -> str:
        self._require()
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        # homr writes <stem>.musicxml next to the input image.
        # Place a copy of the image in output_dir so output lands there.
        src = Path(image_path)
        dst = Path(output_dir) / src.name
        if str(src.resolve()) != str(dst.resolve()):
            import shutil
            shutil.copy2(str(src), str(dst))
        # Run homr on the copied image.
        subprocess.run(
            ["homr", str(dst)],
            cwd=str(output_dir),
            check=True,
            capture_output=True,
            timeout=600,
        )
        out_xml = Path(output_dir) / (dst.stem + ".musicxml")
        if not out_xml.exists():
            # homr may name it differently; find any new musicxml
            candidates = sorted(Path(output_dir).glob("*.musicxml"))
            if candidates:
                out_xml = candidates[-1]
        if not out_xml.exists():
            raise RuntimeError("homr did not produce a MusicXML file")
        return str(out_xml)

    def merge_musicxml(self, xml_paths: List[str], output_path: str) -> str:
        self._require()
        from copy import deepcopy

        from music21 import converter, stream

        if not xml_paths:
            raise RuntimeError("No MusicXML pages to merge")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        first = converter.parse(xml_paths[0])
        part_count = len(first.parts) if hasattr(first, "parts") and first.parts else 1

        new_score = stream.Score()
        for pi in range(part_count):
            new_part = stream.Part()
            measure_number = 1
            for xml_path in xml_paths:
                score = converter.parse(xml_path)
                parts = list(score.parts) if hasattr(score, "parts") and score.parts else [score]
                if pi >= len(parts):
                    continue
                part = parts[pi]
                for measure in part.getElementsByClass(stream.Measure):
                    m = deepcopy(measure)
                    try:
                        m.number = measure_number
                    except Exception:
                        pass
                    measure_number += 1
                    new_part.append(m)
            new_score.insert(0, new_part)

        try:
            new_score.metadata = first.metadata
        except Exception:
            pass

        new_score.write("musicxml", fp=output_path)
        return output_path

    def musicxml_to_midi(self, xml_path: str, midi_path: str) -> str:
        self._require()
        from music21 import converter

        Path(midi_path).parent.mkdir(parents=True, exist_ok=True)
        score = converter.parse(xml_path)
        score.write("midi", fp=midi_path)
        return midi_path

