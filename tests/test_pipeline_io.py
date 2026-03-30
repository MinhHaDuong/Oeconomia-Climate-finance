"""Tests for pipeline_io.save_figure (#544)."""

import os
import sys

import matplotlib.pyplot as plt
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from pipeline_io import save_figure  # noqa: E402


class TestSaveFigureDefault:
    """save_figure() should produce PNG only by default (#544)."""

    @pytest.fixture()
    def fig(self):
        fig, _ax = plt.subplots()
        yield fig
        plt.close(fig)

    def test_no_pdf_by_default(self, fig, tmp_path):
        """Default call produces PNG, not PDF."""
        save_figure(fig, str(tmp_path / "test"))
        assert (tmp_path / "test.png").exists()
        assert not (tmp_path / "test.pdf").exists()

    def test_pdf_opt_in(self, fig, tmp_path):
        """pdf=True produces both PNG and PDF."""
        save_figure(fig, str(tmp_path / "test"), pdf=True)
        assert (tmp_path / "test.png").exists()
        assert (tmp_path / "test.pdf").exists()
