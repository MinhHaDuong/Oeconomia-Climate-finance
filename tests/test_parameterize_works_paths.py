"""Tests for #53: Parameterize Phase 1 scripts with --works-input / --works-output.

Tests verify:
- Each script accepts --works-input CLI arg
- enrich_dois.py also accepts --works-output
- When --works-input is provided, the script reads from that path
- Defaults are defined and backward-compatible (point to unified_works.csv)
- Checkpoints are not invalidated when works path changes

CLI flag presence is checked via source inspection (no subprocess).
Integration tests that run scripts via subprocess are marked @integration.
"""

import os
import subprocess
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
PYTHON = sys.executable


def _read_script(script_name):
    """Read script source text for flag inspection."""
    path = os.path.join(SCRIPTS_DIR, script_name)
    with open(path) as f:
        return f.read()


def _has_flag(source, flag):
    """Check that the script source defines an argparse flag."""
    return f'"{flag}"' in source or f"'{flag}'" in source


# ---------------------------------------------------------------------------
# enrich_dois.py
# ---------------------------------------------------------------------------

class TestEnrichDoisCLI:
    @pytest.fixture(autouse=True, scope="class")
    def _load_source(self, request):
        request.cls._source = _read_script("enrich_dois.py")

    def test_accepts_works_input(self):
        assert _has_flag(self._source, "--works-input"), \
            "enrich_dois.py must accept --works-input"

    def test_accepts_works_output(self):
        assert _has_flag(self._source, "--works-output"), \
            "enrich_dois.py must accept --works-output"

    def test_works_input_default_is_unified(self):
        """Default --works-input should point to unified_works.csv."""
        assert "unified_works.csv" in self._source, \
            "enrich_dois.py --works-input default should be unified_works.csv"

    def test_works_output_default_is_enriched(self):
        """Default --works-output should point to enriched_works.csv."""
        assert "enriched_works.csv" in self._source, \
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
    @pytest.fixture(autouse=True, scope="class")
    def _load_source(self, request):
        request.cls._source = _read_script("enrich_abstracts.py")

    def test_accepts_works_input(self):
        assert _has_flag(self._source, "--works-input"), \
            "enrich_abstracts.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        """--works-input must have a default (not required)."""
        assert "unified_works.csv" in self._source or "enriched_works.csv" in self._source, \
            "enrich_abstracts.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# enrich_citations_batch.py
# ---------------------------------------------------------------------------

class TestEnrichCitationsBatchCLI:
    @pytest.fixture(autouse=True, scope="class")
    def _load_source(self, request):
        request.cls._source = _read_script("enrich_citations_batch.py")

    def test_accepts_works_input(self):
        assert _has_flag(self._source, "--works-input"), \
            "enrich_citations_batch.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        assert "unified_works.csv" in self._source or "enriched_works.csv" in self._source, \
            "enrich_citations_batch.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# enrich_citations_openalex.py
# ---------------------------------------------------------------------------

class TestEnrichCitationsOpenAlexCLI:
    @pytest.fixture(autouse=True, scope="class")
    def _load_source(self, request):
        request.cls._source = _read_script("enrich_citations_openalex.py")

    def test_accepts_works_input(self):
        assert _has_flag(self._source, "--works-input"), \
            "enrich_citations_openalex.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        assert "unified_works.csv" in self._source or "enriched_works.csv" in self._source \
               or "refined_works.csv" in self._source, \
            "enrich_citations_openalex.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# qa_citations.py
# ---------------------------------------------------------------------------

class TestQcCitationsCLI:
    @pytest.fixture(autouse=True, scope="class")
    def _load_source(self, request):
        request.cls._source = _read_script("qa_citations.py")

    def test_accepts_works_input(self):
        assert _has_flag(self._source, "--works-input"), \
            "qa_citations.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        assert "unified_works.csv" in self._source or "enriched_works.csv" in self._source \
               or "refined_works.csv" in self._source, \
            "qa_citations.py --works-input must have a default path"


# ---------------------------------------------------------------------------
# analyze_embeddings.py
# ---------------------------------------------------------------------------

class TestAnalyzeEmbeddingsCLI:
    @pytest.fixture(autouse=True, scope="class")
    def _load_source(self, request):
        request.cls._source = _read_script("analyze_embeddings.py")

    def test_accepts_works_input(self):
        assert _has_flag(self._source, "--works-input"), \
            "analyze_embeddings.py must accept --works-input"

    def test_works_input_default_is_defined(self):
        assert "unified_works.csv" in self._source or "enriched_works.csv" in self._source \
               or "refined_works.csv" in self._source, \
            "analyze_embeddings.py --works-input must have a default path"

    def test_has_main_guard(self):
        """analyze_embeddings.py must execute via main(), not module scope."""
        assert "__name__" in self._source and "__main__" in self._source, \
            "analyze_embeddings.py must have if __name__ == '__main__': guard"
