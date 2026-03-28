"""Smoke pipeline: run Phase 2 analysis on a tiny corpus fixture.

Validates that the analysis pipeline (tables, figures) runs end-to-end on
a 100-row fixture without network access or DVC remote.

The fixture lives in tests/fixtures/smoke/ and is checked into git (<1 MB).
Scripts locate it via the CLIMATE_FINANCE_DATA environment variable, which
overrides the default data/catalogs/ path in pipeline_loaders.py.

Smoke tests exercise the critical Phase 2 chain:
  compute_breakpoints → compute_clusters → plot_fig1_bars

Scripts that require larger data (analyze_bimodality, analyze_cocitation)
are excluded — they need statistical mass that 100 rows can't provide.
"""

import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")

SMOKE_N_ROWS = 100


# ---------------------------------------------------------------------------
# Fixture data existence and schema
# ---------------------------------------------------------------------------

class TestSmokeFixtureExists:
    """Fixture files exist with expected shapes — no DVC pull needed."""

    def test_refined_works_exists_and_has_expected_rows(self):
        path = os.path.join(FIXTURE_DIR, "refined_works.csv")
        assert os.path.exists(path), f"Missing fixture: {path}"
        df = pd.read_csv(path)
        assert len(df) == SMOKE_N_ROWS, f"Expected {SMOKE_N_ROWS} rows, got {len(df)}"

    def test_refined_works_has_required_columns(self):
        df = pd.read_csv(os.path.join(FIXTURE_DIR, "refined_works.csv"))
        required = {"doi", "title", "year", "cited_by_count", "source_id", "abstract"}
        missing = required - set(df.columns)
        assert not missing, f"Missing columns in fixture: {missing}"

    def test_refined_embeddings_exists_and_aligned(self):
        emb_path = os.path.join(FIXTURE_DIR, "refined_embeddings.npz")
        assert os.path.exists(emb_path), f"Missing fixture: {emb_path}"
        vectors = np.load(emb_path)["vectors"]
        df = pd.read_csv(os.path.join(FIXTURE_DIR, "refined_works.csv"))
        assert vectors.shape[0] == len(df), (
            f"Embedding rows ({vectors.shape[0]}) != works rows ({len(df)})"
        )

    def test_refined_citations_exists(self):
        path = os.path.join(FIXTURE_DIR, "refined_citations.csv")
        assert os.path.exists(path), f"Missing fixture: {path}"
        df = pd.read_csv(path)
        assert len(df) > 0, "Citations fixture is empty"
        assert "source_doi" in df.columns

    def test_fixture_total_size_under_1mb(self):
        total = 0
        for fname in os.listdir(FIXTURE_DIR):
            if not fname.startswith("."):
                total += os.path.getsize(os.path.join(FIXTURE_DIR, fname))
        assert total < 1_000_000, f"Fixture total size {total} bytes exceeds 1 MB"


# ---------------------------------------------------------------------------
# Smoke environment helper
# ---------------------------------------------------------------------------

def _smoke_env():
    """Environment dict that redirects pipeline_loaders to fixture data."""
    return {
        **os.environ,
        "CLIMATE_FINANCE_DATA": FIXTURE_DIR,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
    }


def _run_script(script_name, *args, timeout=60):
    """Run a Phase 2 script against smoke fixture data."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, script_name), *args],
        capture_output=True, text=True,
        env=_smoke_env(),
        timeout=timeout,
    )
    return result


# ---------------------------------------------------------------------------
# Phase 2 script smoke tests — critical path
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestSmokeCriticalPath:
    """Core Phase 2 scripts run without error on fixture data.

    These scripts form the critical pipeline chain:
    refined_works.csv → breakpoints → clusters → figures.
    """

    def test_compute_breakpoints(self):
        result = _run_script("compute_breakpoints.py", "--no-pdf")
        assert result.returncode == 0, (
            f"compute_breakpoints.py failed:\n{result.stderr}"
        )

    def test_compute_clusters(self):
        result = _run_script("compute_clusters.py", "--no-pdf")
        assert result.returncode == 0, (
            f"compute_clusters.py failed:\n{result.stderr}"
        )

    def test_plot_fig1_bars(self):
        result = _run_script("plot_fig1_bars.py", "--no-pdf")
        assert result.returncode == 0, (
            f"plot_fig1_bars.py failed:\n{result.stderr}"
        )

    def test_plot_fig1_bars_v1(self):
        result = _run_script("plot_fig1_bars.py", "--no-pdf", "--v1-only")
        assert result.returncode == 0, (
            f"plot_fig1_bars.py --v1-only failed:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Makefile smoke target
# ---------------------------------------------------------------------------

class TestSmokeMakeTarget:
    """make smoke target is declared in the Makefile."""

    def test_makefile_has_smoke_target(self):
        import re
        makefile = os.path.join(os.path.dirname(__file__), "..", "Makefile")
        with open(makefile) as f:
            content = f.read()
        assert re.search(r"^smoke\s*:", content, re.MULTILINE), (
            "Makefile missing 'smoke' target"
        )

    def test_smoke_in_phony(self):
        makefile = os.path.join(os.path.dirname(__file__), "..", "Makefile")
        with open(makefile) as f:
            content = f.read()
        assert "smoke" in content.split(".PHONY:")[1].split("\n")[0] if ".PHONY:" in content else False, (
            "smoke not in .PHONY declaration"
        )
