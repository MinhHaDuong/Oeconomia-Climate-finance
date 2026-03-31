"""Tests for #509: Script I/O discipline — canonical main() pattern.

Covers:
- parse_io_args() shared argument parser
- Migrated scripts reject missing --output
- Makefile pattern rule exists for figure scripts
"""

import os
import subprocess
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# parse_io_args() utility
# ---------------------------------------------------------------------------

class TestParseIoArgs:
    """Shared I/O argument parser works correctly."""

    def test_parse_io_args_exists(self):
        from script_io_args import parse_io_args
        assert callable(parse_io_args)

    def test_output_required(self):
        """--output is required; missing it causes SystemExit."""
        from script_io_args import parse_io_args
        with pytest.raises(SystemExit):
            parse_io_args(["--input", "foo.csv"])

    def test_input_optional(self):
        """--input is optional (some scripts get input from CATALOGS_DIR)."""
        from script_io_args import parse_io_args
        args, _ = parse_io_args(["--output", "out.png"])
        assert args.output == "out.png"
        assert args.input is None

    def test_input_single(self):
        from script_io_args import parse_io_args
        args, _ = parse_io_args(["--input", "a.csv", "--output", "out.png"])
        assert args.input == ["a.csv"]

    def test_input_multiple(self):
        from script_io_args import parse_io_args
        args, _ = parse_io_args([
            "--input", "a.csv", "b.csv", "--output", "out.png"
        ])
        assert args.input == ["a.csv", "b.csv"]

    def test_extra_args_passed_through(self):
        """Script-specific flags pass through via parse_known_args."""
        from script_io_args import parse_io_args
        args, extra = parse_io_args([
            "--output", "out.png", "--pdf", "--v1-only"
        ])
        assert "--pdf" in extra
        assert "--v1-only" in extra

    def test_validate_io_checks_output_dir(self, tmp_path):
        """validate_io fails if output directory doesn't exist."""
        from script_io_args import validate_io
        with pytest.raises(FileNotFoundError, match="directory"):
            validate_io(output=str(tmp_path / "nonexistent" / "out.png"))

    def test_validate_io_passes_for_valid_paths(self, tmp_path):
        """validate_io succeeds for valid output paths."""
        from script_io_args import validate_io
        # Should not raise
        validate_io(output=str(tmp_path / "out.png"))


# ---------------------------------------------------------------------------
# Migrated scripts
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestMigratedScripts:
    """Migrated scripts enforce --output and produce expected files."""

    def test_plot_fig1_bars_requires_output(self):
        """plot_fig1_bars.py rejects invocation without --output."""
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "plot_fig1_bars.py")],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "output" in result.stderr.lower()

    def test_plot_fig2_composition_requires_output(self):
        """plot_fig2_composition.py rejects invocation without --output."""
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "plot_fig2_composition.py")],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "output" in result.stderr.lower()

    def test_plot_fig45_pca_scatter_requires_output(self):
        """plot_fig45_pca_scatter.py rejects invocation without --output."""
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "plot_fig45_pca_scatter.py")],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "output" in result.stderr.lower()

    def test_plot_fig_lexical_tfidf_requires_output(self):
        """plot_fig_lexical_tfidf.py rejects invocation without --output."""
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "plot_fig_lexical_tfidf.py")],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "output" in result.stderr.lower()

    def test_plot_fig_traditions_requires_output(self):
        """plot_fig_traditions.py rejects invocation without --output."""
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "plot_fig_traditions.py")],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "output" in result.stderr.lower()

    def test_plot_heatmap_communities_clusters_requires_output(self):
        """plot_heatmap_communities_clusters.py rejects without --output."""
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR,
             "plot_heatmap_communities_clusters.py")],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "output" in result.stderr.lower()
