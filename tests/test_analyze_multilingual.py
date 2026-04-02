"""Tests for analyze_multilingual.py."""

import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from analyze_multilingual import (
    classify_quadrant,
    compute_citation_directionality,
    compute_contingency,
    compute_core_composition,
    compute_isolation_scores,
    compute_language_stats,
    compute_quadrant_stats,
)


class TestClassifyQuadrant:
    """Unit tests for the four-quadrant classification."""

    def test_english_north(self):
        row = {"language": "en", "affiliations": "MIT, Cambridge, USA"}
        assert classify_quadrant(row) == "EN-N"

    def test_english_south(self):
        row = {"language": "en", "affiliations": "University of Nairobi, Kenya"}
        assert classify_quadrant(row) == "EN-S"

    def test_non_english_north(self):
        row = {"language": "de", "affiliations": "TU Berlin, Germany"}
        assert classify_quadrant(row) == "nonEN-N"

    def test_non_english_south(self):
        row = {"language": "pt", "affiliations": "USP, São Paulo, Brazil"}
        assert classify_quadrant(row) == "nonEN-S"

    def test_missing_language(self):
        row = {"language": "", "affiliations": "MIT, USA"}
        assert classify_quadrant(row) is None

    def test_missing_affiliations(self):
        row = {"language": "en", "affiliations": ""}
        assert classify_quadrant(row) is None

    def test_none_language(self):
        row = {"language": None, "affiliations": "MIT, USA"}
        assert classify_quadrant(row) is None

    def test_eng_variant(self):
        row = {"language": "eng", "affiliations": "Oxford, UK"}
        assert classify_quadrant(row) == "EN-N"


class TestComputeLanguageStats:
    """Unit tests for language distribution computation."""

    def test_basic_counts(self):
        df = pd.DataFrame({"language": ["en", "en", "pt", None]})
        result = compute_language_stats(df)
        assert result["en"]["n"] == 2
        assert result["pt"]["n"] == 1
        assert result["missing"]["n"] == 1

    def test_percentages(self):
        df = pd.DataFrame({"language": ["en"] * 9 + ["fr"]})
        result = compute_language_stats(df)
        assert result["en"]["pct"] == 90.0
        assert result["fr"]["pct"] == 10.0


class TestComputeQuadrantStats:
    """Unit tests for quadrant classification stats."""

    def test_all_quadrants(self):
        df = pd.DataFrame({
            "language": ["en", "en", "de", "pt"],
            "affiliations": ["MIT, USA", "Nairobi, Kenya", "TU Berlin", "USP, Brazil"],
            "cited_by_count": [100, 50, 30, 10],
        })
        result = compute_quadrant_stats(df)
        assert result["EN-N"]["n"] == 1
        assert result["EN-S"]["n"] == 1
        assert result["nonEN-N"]["n"] == 1
        assert result["nonEN-S"]["n"] == 1
        assert result["unclassified"] == 0

    def test_unclassified_counted(self):
        df = pd.DataFrame({
            "language": ["en", ""],
            "affiliations": ["MIT, USA", "somewhere"],
            "cited_by_count": [10, 5],
        })
        result = compute_quadrant_stats(df)
        assert result["unclassified"] == 1


class TestComputeContingency:
    """Unit tests for language x cluster contingency table."""

    def test_basic_contingency(self):
        df = pd.DataFrame({
            "doi": ["d1", "d2", "d3", "d4"],
            "language": ["en", "en", "pt", "de"],
        })
        clusters_df = pd.DataFrame({
            "doi": ["d1", "d2", "d3", "d4"],
            "semantic_cluster": [0, 1, 0, 1],
        })
        result = compute_contingency(df, clusters_df)
        assert "chi2" in result
        assert "p_value" in result
        assert "dof" in result
        assert "contingency_table" in result
        assert isinstance(result["significant_cells"], list)

    def test_missing_language_grouped(self):
        """NaN languages should appear as 'missing', not crash."""
        df = pd.DataFrame({
            "doi": ["d1", "d2", "d3"],
            "language": ["en", None, "en"],
        })
        clusters_df = pd.DataFrame({
            "doi": ["d1", "d2", "d3"],
            "semantic_cluster": [0, 0, 1],
        })
        result = compute_contingency(df, clusters_df)
        # ct.to_dict() keys by column (cluster); lang_group is in the inner dict
        first_cluster = result["contingency_table"][0]
        assert "missing" in first_cluster

    def test_rare_language_grouped_as_other(self):
        """Languages not in the top-7 list should map to 'other'."""
        df = pd.DataFrame({
            "doi": ["d1", "d2", "d3", "d4"],
            "language": ["en", "en", "ko", "tr"],
        })
        clusters_df = pd.DataFrame({
            "doi": ["d1", "d2", "d3", "d4"],
            "semantic_cluster": [0, 1, 0, 1],
        })
        result = compute_contingency(df, clusters_df)
        first_cluster = result["contingency_table"][0]
        assert "other" in first_cluster


class TestComputeIsolationScores:
    """Unit tests for isolation score computation."""

    def test_basic_isolation(self):
        """EN-S works farther from EN-N cluster should have higher isolation."""
        rng = np.random.RandomState(42)
        # EN-N cluster around origin
        en_n_emb = rng.randn(20, 8) * 0.1
        # EN-S cluster offset
        en_s_emb = rng.randn(5, 8) * 0.1 + 2.0

        embeddings = np.vstack([en_n_emb, en_s_emb])
        df = pd.DataFrame({
            "language": ["en"] * 25,
            "affiliations": ["MIT, USA"] * 20 + ["Nairobi, Kenya"] * 5,
            "cited_by_count": [10] * 25,
        })

        result = compute_isolation_scores(df, embeddings, k=5)
        assert "EN-N" in result
        assert "EN-S" in result
        assert result["EN-S"]["mean"] > result["EN-N"]["mean"]

    def test_too_few_en_north(self):
        embeddings = np.random.randn(3, 8)
        df = pd.DataFrame({
            "language": ["en", "pt", "fr"],
            "affiliations": ["MIT, USA", "USP, Brazil", "Paris, France"],
            "cited_by_count": [10, 5, 3],
        })
        result = compute_isolation_scores(df, embeddings, k=10)
        assert result == {}


class TestComputeCitationDirectionality:
    """Unit tests for vectorized citation flow computation."""

    def test_basic_flows(self):
        df = pd.DataFrame({
            "doi": ["d1", "d2", "d3"],
            "language": ["en", "en", "en"],
            "affiliations": ["MIT, USA", "MIT, USA", "Nairobi, Kenya"],
            "cited_by_count": [10, 5, 3],
        })
        citations = pd.DataFrame({
            "source_doi": ["d1", "d3"],
            "ref_doi": ["d3", "d1"],
        })
        result = compute_citation_directionality(df, citations)
        assert result["N\u2192S"] == 1
        assert result["S\u2192N"] == 1
        assert result["asymmetry_ratio"] == 1.0

    def test_unclassified_edges(self):
        df = pd.DataFrame({
            "doi": ["d1"],
            "language": ["en"],
            "affiliations": ["MIT, USA"],
            "cited_by_count": [10],
        })
        citations = pd.DataFrame({
            "source_doi": ["d1", "d1"],
            "ref_doi": ["d_unknown", "d1"],
        })
        result = compute_citation_directionality(df, citations)
        assert result["unclassified"] == 1
        assert result["N\u2192N"] == 1


class TestComputeCoreComposition:
    """Unit tests for core subset composition."""

    def test_core_threshold(self):
        df = pd.DataFrame({
            "language": ["en", "en", "pt"],
            "affiliations": ["MIT, USA", "MIT, USA", "USP, Brazil"],
            "cited_by_count": [100, 30, 60],
        })
        result = compute_core_composition(df)
        assert result["total"] == 2  # only cited >= 50


@pytest.mark.integration
class TestScriptCLI:
    """Integration test: script enforces --output."""

    def test_requires_output(self):
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "analyze_multilingual.py")],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "output" in result.stderr.lower()
