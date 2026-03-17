"""Tests for collection configuration (tickets #175, #176).

Covers:
- config/corpus_collect.yaml loads correctly with year_min < year_max
- config/corpus_collect.yaml has query strings for ISTEX, Scopus, World Bank (#176)
- load_collect_config() helper in utils.py (including validation)
- catalog_openalex.py build_filter() includes year bounds
- catalog_istex.py build_istex_query() reads query from config, includes year bounds
- catalog_scopus.py query includes year bounds (indirectly via config)
- catalog_grey.py reads World Bank query from config
- dvc.yaml declares config/corpus_collect.yaml as dependency for catalog stages
- No hardcoded query strings remain in catalog scripts (#176)
"""

import os
import sys

import pytest
import yaml

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# Config file exists and is well-formed
# ---------------------------------------------------------------------------

class TestCorpusCollectConfig:
    def test_config_file_exists(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        assert os.path.exists(path), "config/corpus_collect.yaml must exist"

    def test_config_has_year_bounds(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        assert "year_min" in cfg
        assert "year_max" in cfg

    def test_year_min_less_than_year_max(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["year_min"] < cfg["year_max"]

    def test_expected_values(self):
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["year_min"] == 1990
        assert cfg["year_max"] == 2024

    def test_config_has_queries_section(self):
        """#176: query strings externalized into config."""
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        assert "queries" in cfg, "corpus_collect.yaml must have a 'queries' section"

    def test_queries_has_expected_keys(self):
        """#176: ISTEX, Scopus, and World Bank queries present and non-empty."""
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        queries = cfg["queries"]
        for key in ("istex", "scopus", "worldbank"):
            assert key in queries, f"queries.{key} missing"
            val = queries[key]
            assert isinstance(val, (str, list)), (
                f"queries.{key} must be a string or list")
            if isinstance(val, str):
                assert len(val.strip()) > 0, f"queries.{key} must be non-empty"
            else:
                assert len(val) > 0, f"queries.{key} must be non-empty"
                assert all(isinstance(q, str) for q in val), (
                    f"queries.{key} list items must be strings")

    def test_queries_contain_climate_finance(self):
        """#176: all queries search for climate finance."""
        path = os.path.join(ROOT_DIR, "config", "corpus_collect.yaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        for key in ("istex", "scopus", "worldbank"):
            val = cfg["queries"][key]
            # For lists, at least the first query must mention climate finance
            text = val[0].lower() if isinstance(val, list) else val.lower()
            assert "climate finance" in text, (
                f"queries.{key} should mention climate finance"
            )


# ---------------------------------------------------------------------------
# load_collect_config() helper
# ---------------------------------------------------------------------------

class TestLoadCollectConfig:
    def test_load_collect_config_returns_dict(self):
        from utils import load_collect_config
        cfg = load_collect_config()
        assert isinstance(cfg, dict)
        assert cfg["year_min"] == 1990
        assert cfg["year_max"] == 2024


# ---------------------------------------------------------------------------
# OpenAlex build_filter includes year bounds
# ---------------------------------------------------------------------------

class TestOpenAlexYearFilter:
    def test_build_filter_includes_year(self):
        from catalog_openalex import build_filter
        f = build_filter("climate finance", year_min=1990, year_max=2024)
        assert "publication_year" in f
        assert "1989" in f or "1990" in f  # >1989 or >=1990
        assert "2025" in f or "2024" in f  # <2025 or <=2024

    def test_build_filter_no_year_when_none(self):
        """Backwards compat: no year filter when not provided."""
        from catalog_openalex import build_filter
        f = build_filter("climate finance")
        assert "publication_year" not in f


# ---------------------------------------------------------------------------
# ISTEX build_istex_query includes year bounds
# ---------------------------------------------------------------------------

class TestIstexYearFilter:
    _BASE = '"climate finance" OR "finance climat"'

    def test_build_istex_query_includes_year(self):
        from catalog_istex import build_istex_query
        q = build_istex_query(self._BASE, year_min=1990, year_max=2024)
        assert "publicationDate:[1990 TO 2024]" in q

    def test_build_istex_query_no_year_when_none(self):
        from catalog_istex import build_istex_query
        q = build_istex_query(self._BASE)
        assert "publicationDate" not in q

    def test_build_istex_query_uses_config_query(self):
        """#176: build_istex_query includes the base query string."""
        from catalog_istex import build_istex_query
        from utils import load_collect_config
        cfg = load_collect_config()
        base = cfg["queries"]["istex"]
        q = build_istex_query(base)
        assert base in q


# ---------------------------------------------------------------------------
# No hardcoded query strings in catalog scripts (#176)
# ---------------------------------------------------------------------------

class TestNoHardcodedQueries:
    """#176: catalog scripts must not contain hardcoded query strings."""

    def _read_script(self, name):
        path = os.path.join(SCRIPTS_DIR, name)
        with open(path) as f:
            return f.read()

    def _strip_docstrings_and_comments(self, src):
        """Remove triple-quoted docstrings and # comments from source."""
        import re
        # Remove triple-quoted strings (docstrings)
        src = re.sub(r'"""[\s\S]*?"""', '', src)
        src = re.sub(r"'''[\s\S]*?'''", '', src)
        # Remove line comments
        lines = [l for l in src.splitlines() if not l.strip().startswith('#')]
        return "\n".join(lines)

    def test_istex_no_hardcoded_query(self):
        src = self._read_script("catalog_istex.py")
        # Should not have the old _BASE_QUERY constant with a string literal
        assert '_BASE_QUERY = ' not in src, (
            "catalog_istex.py should read query from config, not hardcode _BASE_QUERY"
        )

    def test_scopus_no_hardcoded_query(self):
        src = self._read_script("catalog_scopus.py")
        code = self._strip_docstrings_and_comments(src)
        assert 'TITLE-ABS-KEY' not in code, (
            "catalog_scopus.py should read Scopus query template from config"
        )

    def test_grey_no_hardcoded_worldbank_query(self):
        src = self._read_script("catalog_grey.py")
        code = self._strip_docstrings_and_comments(src)
        assert '"climate finance"' not in code and "'climate finance'" not in code, (
            "catalog_grey.py should read World Bank query from config"
        )


# ---------------------------------------------------------------------------
# DVC declares config/corpus_collect.yaml as dependency
# ---------------------------------------------------------------------------

class TestDvcDependency:
    def test_dvc_catalog_openalex_depends_on_config(self):
        path = os.path.join(ROOT_DIR, "dvc.yaml")
        with open(path) as f:
            dvc = yaml.safe_load(f)
        deps = dvc["stages"]["catalog_openalex"]["deps"]
        assert "config/corpus_collect.yaml" in deps

    def test_dvc_catalog_istex_depends_on_config(self):
        path = os.path.join(ROOT_DIR, "dvc.yaml")
        with open(path) as f:
            dvc = yaml.safe_load(f)
        deps = dvc["stages"]["catalog_istex"]["deps"]
        assert "config/corpus_collect.yaml" in deps

    def test_dvc_catalog_grey_depends_on_config(self):
        path = os.path.join(ROOT_DIR, "dvc.yaml")
        with open(path) as f:
            dvc = yaml.safe_load(f)
        deps = dvc["stages"]["catalog_grey"]["deps"]
        assert "config/corpus_collect.yaml" in deps


# ---------------------------------------------------------------------------
# query_worldbank() list handling and UUID deduplication (#184)
# ---------------------------------------------------------------------------

class TestQueryWorldbankDedup:
    """Test that query_worldbank deduplicates by UUID across multiple queries."""

    def test_list_dedup_removes_overlapping_uuids(self):
        """Records with the same UUID from different queries are deduplicated."""
        from unittest.mock import patch

        sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
        from catalog_grey import query_worldbank

        fake_results = {
            "q1": [
                {"source_id": "aaa", "title": "Paper A"},
                {"source_id": "bbb", "title": "Paper B"},
            ],
            "q2": [
                {"source_id": "bbb", "title": "Paper B duplicate"},
                {"source_id": "ccc", "title": "Paper C"},
            ],
        }
        call_order = iter(["q1", "q2"])

        def mock_single(wb_query, year_min=None, year_max=None):
            key = next(call_order)
            return fake_results[key]

        with patch("catalog_grey._query_worldbank_single", side_effect=mock_single):
            results = query_worldbank(["q1", "q2"])

        ids = [r["source_id"] for r in results]
        assert ids == ["aaa", "bbb", "ccc"], "Should dedup bbb across queries"

    def test_empty_source_id_not_collapsed(self):
        """Records with empty source_id are never deduplicated against each other."""
        from unittest.mock import patch

        sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
        from catalog_grey import query_worldbank

        fake_results = {
            "q1": [
                {"source_id": "", "title": "No-UUID paper 1"},
                {"source_id": "aaa", "title": "Paper A"},
            ],
            "q2": [
                {"source_id": "", "title": "No-UUID paper 2"},
            ],
        }
        call_order = iter(["q1", "q2"])

        def mock_single(wb_query, year_min=None, year_max=None):
            key = next(call_order)
            return fake_results[key]

        with patch("catalog_grey._query_worldbank_single", side_effect=mock_single):
            results = query_worldbank(["q1", "q2"])

        assert len(results) == 3, "Empty source_id records should not be collapsed"

    def test_string_input_backward_compatible(self):
        """A single string query still works (backward compatibility)."""
        from unittest.mock import patch

        sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))
        from catalog_grey import query_worldbank

        def mock_single(wb_query, year_min=None, year_max=None):
            return [{"source_id": "aaa", "title": "Paper A"}]

        with patch("catalog_grey._query_worldbank_single", side_effect=mock_single):
            results = query_worldbank("single query")

        assert len(results) == 1
