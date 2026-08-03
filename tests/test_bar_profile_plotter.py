"""Unit tests for BarProfilePlotter (src/application/extraction_components.py:668-751).

Covers plot() with various spike counts, left spike states, merge cutoff,
and matplotlib lazy import behavior.

Note: matplotlib may be unavailable in CI due to DLL restrictions.
File-output tests are skipped when matplotlib fails to import.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Check if matplotlib is importable
try:
    import matplotlib
    matplotlib.use("Agg")
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

from src.application.extraction_components import BarProfilePlotter

skip_no_matplotlib = pytest.mark.skipif(
    not MATPLOTLIB_AVAILABLE, reason="matplotlib DLL load failed"
)


@pytest.fixture
def col_sums():
    """A 640-element column sum array with two synthetic spikes."""
    arr = np.zeros(640, dtype=float)
    arr[150] = 5000.0
    arr[450] = 3500.0
    arr[100:200] = 500.0  # base noise around first spike
    arr[400:500] = 300.0  # base noise around second spike
    return arr


@pytest.mark.unit
class TestBarProfilePlotterLazyImport:

    def test_matplotlib_not_imported_until_called(self):
        plotter = BarProfilePlotter()
        assert plotter._plt is None


@pytest.mark.unit
class TestBarProfilePlotterOutput:

    @skip_no_matplotlib
    def test_creates_file_when_output_path_given(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "test_plot.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[(150, 5000.0), (450, 3500.0)],
            merge_x_640=320,
            margin_col=50,
            output_path=out,
            page_num=1,
        )
        assert out.exists()
        assert out.stat().st_size > 0

    def test_no_error_without_output_path(self, col_sums):
        plotter = BarProfilePlotter()
        plotter.plot(
            col_sums=col_sums,
            spikes=[(150, 5000.0), (450, 3500.0)],
            merge_x_640=320,
            margin_col=50,
            output_path=None,
            page_num=1,
        )

    def test_matplotlib_imported_after_first_call(self, col_sums):
        plotter = BarProfilePlotter()
        assert plotter._plt is None
        plotter.plot(
            col_sums=col_sums,
            spikes=[],
            merge_x_640=320,
            margin_col=50,
            output_path=None,
            page_num=1,
        )
        assert plotter._plt is not None


@pytest.mark.unit
class TestBarProfilePlotterSpikeAnnotations:

    @skip_no_matplotlib
    def test_zero_spikes_rejected_annotation(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "zero_spikes.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[],
            merge_x_640=320,
            margin_col=50,
            has_clean=False,
            output_path=out,
            page_num=1,
        )
        assert out.exists()

    @skip_no_matplotlib
    def test_two_spikes_clean_annotation(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "two_clean.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[(150, 5000.0), (450, 3500.0)],
            merge_x_640=320,
            margin_col=50,
            has_clean=True,
            output_path=out,
            page_num=1,
        )
        assert out.exists()

    @skip_no_matplotlib
    def test_two_spikes_rejected_annotation(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "two_rejected.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[(150, 5000.0), (450, 3500.0)],
            merge_x_640=320,
            margin_col=50,
            has_clean=False,
            output_path=out,
            page_num=1,
        )
        assert out.exists()

    @skip_no_matplotlib
    def test_one_spike_only_first_drawn(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "one_spike.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[(150, 5000.0)],
            merge_x_640=320,
            margin_col=50,
            output_path=out,
            page_num=1,
        )
        assert out.exists()


@pytest.mark.unit
class TestBarProfilePlotterLeftSpike:

    @skip_no_matplotlib
    def test_left_spike_ok_annotation(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "left_spike_ok.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[(150, 5000.0), (450, 3500.0)],
            merge_x_640=320,
            margin_col=50,
            left_spike_col=100,
            has_left_spike=True,
            output_path=out,
            page_num=1,
        )
        assert out.exists()

    @skip_no_matplotlib
    def test_left_spike_rejected_annotation(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "left_spike_rej.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[(150, 5000.0), (450, 3500.0)],
            merge_x_640=320,
            margin_col=50,
            left_spike_col=100,
            has_left_spike=False,
            output_path=out,
            page_num=1,
        )
        assert out.exists()


@pytest.mark.unit
class TestBarProfilePlotterMergeCutoff:

    @skip_no_matplotlib
    def test_merge_cutoff_line_drawn(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "merge_line.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[],
            merge_x_640=320,
            margin_col=50,
            output_path=out,
            page_num=1,
        )
        assert out.exists()

    @skip_no_matplotlib
    def test_merge_cutoff_zero_skipped(self, col_sums, work_dir):
        plotter = BarProfilePlotter()
        out = work_dir / "merge_zero.png"
        plotter.plot(
            col_sums=col_sums,
            spikes=[],
            merge_x_640=0,
            margin_col=50,
            output_path=out,
            page_num=1,
        )
        assert out.exists()
