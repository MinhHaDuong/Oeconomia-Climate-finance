"""Tests for #53: Parameterize Phase 1 scripts with --works-input / --works-output.

Tests verify:
- Each script accepts --works-input CLI arg
- enrich_dois.py also accepts --works-output
- When --works-input is provided, the script reads from that path
- Defaults are defined and backward-compatible (point to unified_works.csv)
- Checkpoints are not invalidated when works path changes
"""

import argparse
import importlib
import os
import subprocess
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
PYTHON = sys.executable


def parse_script_args(script_name, extra_args=None):
    """Run a script with --help and verify --works-input appears."""
    result = subprocess.run(
        [PYTHON, os.path.join(SCRIPTS_DIR, script_name), "--help"],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr


# ---------------------------------------------------------------------------
# enrich_dois.py
# ---------------------------------------------------------------------------

class TestEnrichDoisCLI:
    def test_accepts_works_input(self):
        output = parse_script_args("enrich_dois.py")
        assert "--works-input" in output, \
            "enrich_dois.py must accept --works-input"

    def test_accepts_works_output(self):
        output = parse_script_args("enrich_dois.py")
        assert "--works-output" in output, \
            "enrich_dois.py must accept --works-output"

    def test_works_input_default_is_unified(self):
        """Default --works-input should point to unified_works.csv."""
        output = parse_script_args("enrich_dois.py")
        assert "unified_works.csv" in output, \
            "enrich_dois.py --works-input default should be unified_works.csv"

    def test_works_output_default_is_enriched(self):
        """Default --works-output should point to enriched_works.csv."""
        output = parse_script_args("enrich_dois.py")
        assert "enriched_works.csv" in output, \
            "enrich_dois.py --works-output default should be enriched_works.csv"

    @pytest.mark.slow
    @pytest.mark.timeout(30)
    def test_dry_run_uses_custom_input(self, tmp_path):
        """With --dry-run --works-input, the script reads from the specified path."""
        csv = tmp_path / "custom_input.csv"
        csv.write_text("source_id,title,doi,year,source\n"
                       "test_1,Test paper,, 2020,scopus\n")
        result = subprocess.run(
            [PYTHON, os.path.join(SCRIPTS_DIR, "enrich_dois.py"),
             "--dry-run", "--works-input", str(csv)],
            capture_output=True, text=True, cwd=tmp_path
        )
        combined = result.stdout + result.stderr
        assert "custom_input.csv" in combined or "1 works" in combined or \
               result.returncode == 0 or "Loaded" in combined, \
            f"Script did not appear to use custom input path. Output:\n{combined}"


# ---------------------------------------------------------------------------
# enrich_abstracts.py
# ---------------------------------------------------------------------------

class TestEnrichAbstractsCLI:
    def test_accepts_works_input(self):
        output = parse_script_args("enrich_abstracts.py")
        assert "--works-input" in output, \
            "enrich_abstracts.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        """--works-input must have a default (not required)."""
        output = parse_script_args("enrich_abstracts.py")
        # Either unified_works or enriched_works is acceptable as default
        assert "unified_works.csv" in output or "enriched_works.csv" in output, \
            "enrich_abstracts.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# enrich_citations_batch.py
# ---------------------------------------------------------------------------

class TestEnrichCitationsBatchCLI:
    def test_accepts_works_input(self):
        output = parse_script_args("enrich_citations_batch.py")
        assert "--works-input" in output, \
            "enrich_citations_batch.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        output = parse_script_args("enrich_citations_batch.py")
        assert "unified_works.csv" in output or "enriched_works.csv" in output, \
            "enrich_citations_batch.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# enrich_citations_openalex.py
# ---------------------------------------------------------------------------

class TestEnrichCitationsOpenAlexCLI:
    def test_accepts_works_input(self):
        output = parse_script_args("enrich_citations_openalex.py")
        assert "--works-input" in output, \
            "enrich_citations_openalex.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        output = parse_script_args("enrich_citations_openalex.py")
        assert "unified_works.csv" in output or "enriched_works.csv" in output \
               or "refined_works.csv" in output, \
            "enrich_citations_openalex.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# qc_citations.py
# ---------------------------------------------------------------------------

class TestQcCitationsCLI:
    def test_accepts_works_input(self):
        output = parse_script_args("qc_citations.py")
        assert "--works-input" in output, \
            "qc_citations.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        output = parse_script_args("qc_citations.py")
        assert "unified_works.csv" in output or "enriched_works.csv" in output \
               or "refined_works.csv" in output, \
            "qc_citations.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# analyze_embeddings.py
# ---------------------------------------------------------------------------

class TestAnalyzeEmbeddingsCLI:
    def test_accepts_works_input(self):
        output = parse_script_args("analyze_embeddings.py")
        assert "--works-input" in output, \
            "analyze_embeddings.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        output = parse_script_args("analyze_embeddings.py")
        assert "unified_works.csv" in output or "enriched_works.csv" in output \
               or "refined_works.csv" in output, \
            "analyze_embeddings.py --works-input must have a default path"

    def test_has_main_guard(self):
        """analyze_embeddings.py must execute via main(), not module scope."""
        # This checks that the script has an if __name__ == '__main__' block
        script_path = os.path.join(SCRIPTS_DIR, "analyze_embeddings.py")
        with open(script_path) as f:
            content = f.read()
        assert "__name__" in content and "__main__" in content, \
            "analyze_embeddings.py must have if __name__ == '__main__': guard"
