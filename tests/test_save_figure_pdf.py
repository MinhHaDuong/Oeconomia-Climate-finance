"""Tests for #544: save_figure defaults to PNG-only, opt-in PDF."""

import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def test_save_figure_no_pdf_by_default(tmp_path):
    """save_figure() produces PNG only unless pdf=True."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pipeline_io import save_figure

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    save_figure(fig, str(tmp_path / "test"), pdf=False)
    assert (tmp_path / "test.png").exists()
    assert not (tmp_path / "test.pdf").exists()
    plt.close(fig)


def test_save_figure_with_pdf(tmp_path):
    """save_figure(pdf=True) produces both PNG and PDF."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pipeline_io import save_figure

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    save_figure(fig, str(tmp_path / "test"), pdf=True)
    assert (tmp_path / "test.png").exists()
    assert (tmp_path / "test.pdf").exists()
    plt.close(fig)


def test_save_figure_default_is_png_only(tmp_path):
    """save_figure() with no pdf kwarg produces PNG only (default pdf=False)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pipeline_io import save_figure

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    save_figure(fig, str(tmp_path / "test"))
    assert (tmp_path / "test.png").exists()
    assert not (tmp_path / "test.pdf").exists()
    plt.close(fig)
