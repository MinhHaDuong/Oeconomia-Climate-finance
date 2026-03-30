"""Smoke pipeline: run Phase 2 analysis on a tiny corpus fixture.

Validates that the analysis pipeline (tables, figures) runs end-to-end on
a 100-row fixture without network access or DVC remote.

The fixture lives in tests/fixtures/smoke/catalogs/ and is checked into git (<1 MB).
Scripts locate it via the CLIMATE_FINANCE_DATA environment variable, which
overrides DATA_DIR in pipeline_loaders.py (CATALOGS_DIR = DATA_DIR/catalogs/).

Smoke tests exercise the critical Phase 2 chain:
  compute_breakpoints → compute_clusters → plot_fig1_bars

Scripts that require larger data (analyze_bimodality, analyze_cocitation)
are excluded — they need statistical mass that 100 rows can't provide.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

SMOKE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
FIXTURE_DIR = os.path.join(SMOKE_DIR, "catalogs")
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")

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

def _smoke_env(output_dir=None):
    """Environment dict that redirects pipeline_loaders to fixture data.

    If output_dir is given, also sets CLIMATE_FINANCE_OUTPUT to redirect
    table/figure outputs away from the repo's content/ directory.
    """
    env = {
        **os.environ,
        "CLIMATE_FINANCE_DATA": SMOKE_DIR,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
    }
    if output_dir:
        env["CLIMATE_FINANCE_OUTPUT"] = output_dir
    return env


def _run_script(script_name, *args, output_dir=None, timeout=60):
    """Run a Phase 2 script against smoke fixture data.

    When output_dir is given, script outputs go there instead of content/.
    """
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, script_name), *args],
        capture_output=True, text=True,
        env=_smoke_env(output_dir),
        timeout=timeout,
    )
    return result


# ---------------------------------------------------------------------------
# Phase 2 script smoke tests — critical path
# ---------------------------------------------------------------------------

@pytest.fixture
def smoke_output_dir(tmp_path):
    """Create a temp output tree mirroring content/{figures,tables}.

    Scripts resolve output paths from BASE_DIR/content/. We can't easily
    redirect that without touching every script (that's #509). Instead,
    we back up affected files before the test and restore them after.
    """
    tables = os.path.join(ROOT_DIR, "content", "tables")
    figures = os.path.join(ROOT_DIR, "content", "figures")

    # Track files that existed before the test
    affected_tables = [
        "tab_breakpoints.csv", "tab_breakpoint_robustness.csv",
        "tab_alluvial.csv", "cluster_labels.json", "tab_core_shares.csv",
    ]
    affected_figures = ["fig_bars.png", "fig_bars_v1.png"]
    backup = {}

    for fname in affected_tables:
        path = os.path.join(tables, fname)
        if os.path.exists(path):
            backup[path] = tmp_path / f"backup_{fname}"
            shutil.copy2(path, backup[path])

    for fname in affected_figures:
        path = os.path.join(figures, fname)
        if os.path.exists(path):
            backup[path] = tmp_path / f"backup_{fname}"
            shutil.copy2(path, backup[path])

    yield tmp_path

    # Restore backed-up files, remove smoke artifacts
    for orig_path, backup_path in backup.items():
        shutil.copy2(backup_path, orig_path)


@pytest.mark.slow
class TestSmokeCriticalPath:
    """Core Phase 2 scripts run without error on fixture data.

    These scripts form the critical pipeline chain:
    refined_works.csv → breakpoints → clusters → figures.

    The smoke_output_dir fixture backs up and restores any content/
    files that scripts overwrite, so production outputs are preserved.
    """

    def test_compute_breakpoints(self, smoke_output_dir):
        result = _run_script("compute_breakpoints.py", "--no-pdf")
        assert result.returncode == 0, (
            f"compute_breakpoints.py failed:\n{result.stderr}"
        )

    def test_compute_clusters(self, smoke_output_dir):
        result = _run_script("compute_clusters.py", "--no-pdf")
        assert result.returncode == 0, (
            f"compute_clusters.py failed:\n{result.stderr}"
        )

    def test_plot_fig1_bars(self, smoke_output_dir):
        result = _run_script("plot_fig1_bars.py", "--no-pdf")
        assert result.returncode == 0, (
            f"plot_fig1_bars.py failed:\n{result.stderr}"
        )

    def test_plot_fig1_bars_v1(self, smoke_output_dir):
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
        import re
        makefile = os.path.join(os.path.dirname(__file__), "..", "Makefile")
        with open(makefile) as f:
            content = f.read()
        assert re.search(r"\.PHONY:.*\bsmoke\b", content), (
            "smoke not in .PHONY declaration"
        )
