"""Tests for #55: Deterministic enrichment prioritization.

Tests verify:
- compute_priority_scores() returns deterministic results (same input => same output)
- Row order in input doesn't affect priority ranking
- Priority scores use logged components (cited_by_count, source_count, year)
- Sorting DOIs by priority gives deterministic order
- Budget-capped (--limit) runs process highest-priority DOIs first
"""

import os
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Import the priority utility
# ---------------------------------------------------------------------------

class TestImportPriorityUtil:
    def test_compute_priority_scores_importable(self):
        """compute_priority_scores must be importable from utils or enrich_priority."""
        try:
            from utils import compute_priority_scores
        except ImportError:
            try:
                from enrich_priority import compute_priority_scores
            except ImportError:
                pytest.fail(
                    "compute_priority_scores not found in utils.py or enrich_priority.py"
                )

    def test_sort_dois_by_priority_importable(self):
        """sort_dois_by_priority (or equivalent) must be importable."""
        try:
            from utils import sort_dois_by_priority
        except ImportError:
            try:
                from enrich_priority import sort_dois_by_priority
            except ImportError:
                pytest.fail(
                    "sort_dois_by_priority not found in utils.py or enrich_priority.py"
                )


def get_priority_functions():
    """Return (compute_priority_scores, sort_dois_by_priority) from wherever they live."""
    try:
        from utils import compute_priority_scores, sort_dois_by_priority
        return compute_priority_scores, sort_dois_by_priority
    except ImportError:
        from enrich_priority import compute_priority_scores, sort_dois_by_priority
        return compute_priority_scores, sort_dois_by_priority


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------

class TestDeterminism:
    @pytest.fixture
    def sample_works(self):
        return pd.DataFrame({
            "doi": ["10.1/A", "10.1/B", "10.1/C", "10.1/D", "10.1/E"],
            "source_id": ["s1", "s2", "s3", "s4", "s5"],
            "year": [2010, 2015, 2000, 2020, 2005],
            "cited_by_count": [100, 5, 80, 200, 0],
            "source_count": [3, 1, 2, 4, 1],
            "from_openalex": [1, 1, 1, 1, 1],
            "from_semanticscholar": [1, 0, 1, 1, 0],
            "from_istex": [1, 0, 0, 1, 0],
            "from_bibcnrs": [0, 0, 0, 1, 0],
            "from_scispace": [0, 0, 0, 0, 0],
            "from_grey": [0, 0, 0, 0, 0],
            "from_teaching": [0, 0, 0, 0, 0],
        })

    def test_same_input_same_output(self, sample_works):
        """Same DataFrame input must produce identical priority scores each call."""
        compute_priority_scores, _ = get_priority_functions()
        result1 = compute_priority_scores(sample_works.copy())
        result2 = compute_priority_scores(sample_works.copy())
        pd.testing.assert_frame_equal(
            result1[["doi", "_priority"]].reset_index(drop=True),
            result2[["doi", "_priority"]].reset_index(drop=True),
            check_names=True,
        )

    def test_row_order_independent(self, sample_works):
        """Shuffling input rows must not change priority ranking."""
        compute_priority_scores, _ = get_priority_functions()
        result_orig = compute_priority_scores(sample_works.copy())
        shuffled = sample_works.sample(frac=1, random_state=42).reset_index(drop=True)
        result_shuffled = compute_priority_scores(shuffled)
        # Sorted by priority both ways should give same DOI order
        orig_order = result_orig.sort_values("_priority", ascending=False)["doi"].tolist()
        shuffled_order = result_shuffled.sort_values("_priority", ascending=False)["doi"].tolist()
        assert orig_order == shuffled_order, (
            f"Priority order changed after shuffling input.\n"
            f"Original: {orig_order}\nShuffled: {shuffled_order}"
        )

    def test_high_cited_gets_high_priority(self, sample_works):
        """Paper with highest citation count should rank at or near the top."""
        compute_priority_scores, _ = get_priority_functions()
        result = compute_priority_scores(sample_works)
        ranked = result.sort_values("_priority", ascending=False)
        top_doi = ranked.iloc[0]["doi"]
        # DOI D has cited_by_count=200 — should be first
        assert top_doi == "10.1/D", (
            f"Highest-cited paper (10.1/D, cited=200) not ranked first. Got: {top_doi}"
        )

    def test_priority_has_score_components(self, sample_works):
        """Output DataFrame must include score component columns."""
        compute_priority_scores, _ = get_priority_functions()
        result = compute_priority_scores(sample_works)
        assert "_priority" in result.columns, "Missing _priority column"
        # At least one visible score component column
        component_cols = [c for c in result.columns if c.startswith("_score_")]
        assert len(component_cols) >= 1, (
            f"No _score_* component columns found. Columns: {list(result.columns)}"
        )


# ---------------------------------------------------------------------------
# Sort-by-priority helper
# ---------------------------------------------------------------------------

class TestSortDoisByPriority:
    @pytest.fixture
    def sample_works(self):
        return pd.DataFrame({
            "doi": ["10.1/A", "10.1/B", "10.1/C"],
            "source_id": ["s1", "s2", "s3"],
            "year": [2010, 2015, 2005],
            "cited_by_count": [10, 200, 5],
            "source_count": [1, 3, 1],
            "from_openalex": [1, 1, 1],
            "from_semanticscholar": [0, 1, 0],
            "from_istex": [0, 1, 0],
            "from_bibcnrs": [0, 0, 0],
            "from_scispace": [0, 0, 0],
            "from_grey": [0, 0, 0],
            "from_teaching": [0, 0, 0],
        })

    def test_sort_returns_list(self, sample_works):
        _, sort_dois_by_priority = get_priority_functions()
        dois = ["10.1/A", "10.1/B", "10.1/C"]
        result = sort_dois_by_priority(dois, sample_works)
        assert isinstance(result, list), "sort_dois_by_priority must return a list"
        assert len(result) == len(dois), "Output list must have same length as input"

    def test_sort_deterministic(self, sample_works):
        _, sort_dois_by_priority = get_priority_functions()
        dois = ["10.1/C", "10.1/A", "10.1/B"]
        result1 = sort_dois_by_priority(dois, sample_works)
        result2 = sort_dois_by_priority(dois, sample_works)
        assert result1 == result2, "sort_dois_by_priority must be deterministic"

    def test_sort_puts_high_priority_first(self, sample_works):
        _, sort_dois_by_priority = get_priority_functions()
        dois = ["10.1/A", "10.1/B", "10.1/C"]
        result = sort_dois_by_priority(dois, sample_works)
        # B has cited_by_count=200, should come first
        assert result[0] == "10.1/B", (
            f"Highest-cited DOI (10.1/B) should be first. Got: {result}"
        )

    def test_sort_excludes_unknown_dois(self, sample_works):
        """DOIs not in works_df should be sortable (placed at end or skipped)."""
        _, sort_dois_by_priority = get_priority_functions()
        dois = ["10.1/A", "10.1/UNKNOWN", "10.1/B"]
        result = sort_dois_by_priority(dois, sample_works)
        # Unknown DOI should appear in result (not dropped)
        assert "10.1/UNKNOWN" in result, "Unknown DOI should be included in result"
        # But ranked lower than known high-priority ones
        assert result.index("10.1/B") < result.index("10.1/UNKNOWN"), \
            "Unknown DOI should be ranked below known high-priority DOI"


# ---------------------------------------------------------------------------
# Enrich scripts use priority ordering
# ---------------------------------------------------------------------------

class TestScriptUsedPriority:
    def test_enrich_citations_batch_mentions_priority(self):
        """enrich_citations_batch.py source should reference priority ordering."""
        path = os.path.join(SCRIPTS_DIR, "enrich_citations_batch.py")
        with open(path) as f:
            source = f.read()
        assert "priority" in source.lower(), \
            "enrich_citations_batch.py should reference priority ordering"
