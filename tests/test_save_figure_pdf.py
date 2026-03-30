"""Test that save_figure defaults to PNG-only (no PDF).

The project convention is that PDF output is opt-in via --pdf, not opt-out
via --no-pdf. This test verifies the interface contract of save_figure().
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pipeline_io import save_figure


class TestSaveFigurePdfDefault:
    def test_no_pdf_by_default(self, tmp_path):
        """Default call produces PNG only — no PDF."""
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        save_figure(fig, str(tmp_path / "test"))
        assert (tmp_path / "test.png").exists()
        assert not (tmp_path / "test.pdf").exists()
        plt.close(fig)

    def test_pdf_when_requested(self, tmp_path):
        """Explicit pdf=True produces both PNG and PDF."""
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        save_figure(fig, str(tmp_path / "test"), pdf=True)
        assert (tmp_path / "test.png").exists()
        assert (tmp_path / "test.pdf").exists()
        plt.close(fig)
