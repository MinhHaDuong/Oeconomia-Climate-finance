"""Tests for C2ST (Classifier Two-Sample Test) divergence methods.

Tests:
1. Null hypothesis: AUC near 0.5 when distributions are identical
2. Alternative hypothesis: AUC high when distributions are shifted
3. Output matches DivergenceSchema
4. Dispatcher integration (methods registered in METHODS dict)
"""

import os
import sys

import numpy as np
import pandas as pd

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Unit tests for the core C2ST AUC computation
# ---------------------------------------------------------------------------


class TestC2STCore:
    """Test the internal _c2st_auc function."""

    def test_null_auc_near_half(self):
        """Under H0 (same distribution), AUC should be near 0.5."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(42)
        X = rng.randn(200, 32)
        Y = rng.randn(200, 32)
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced")
        assert 0.35 < auc < 0.65, f"Null AUC should be near 0.5, got {auc}"

    def test_shift_auc_high(self):
        """With a planted shift, AUC should be well above 0.5."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(42)
        X = rng.randn(200, 32)
        Y = rng.randn(200, 32) + 1.0  # shifted
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced")
        assert auc > 0.7, f"Shifted AUC should be > 0.7, got {auc}"

    def test_auc_bounded_zero_one(self):
        """AUC should always be in [0, 1]."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(99)
        X = rng.randn(100, 16)
        Y = rng.randn(100, 16) + 0.5
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced")
        assert 0.0 <= auc <= 1.0, f"AUC out of bounds: {auc}"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestC2STEmbeddingSchema:
    """Output of compute_c2st_embedding matches DivergenceSchema."""

    def test_output_schema(self):
        """Synthetic data produces valid DivergenceSchema output."""
        import copy

        from _divergence_c2st import compute_c2st_embedding
        from pipeline_loaders import load_analysis_config
        from schemas import DivergenceSchema

        cfg = copy.deepcopy(load_analysis_config())
        cfg["divergence"]["windows"] = [2]
        cfg["divergence"]["max_subsample"] = 500

        # Build synthetic data: 20 years, 30 papers per year
        rng = np.random.RandomState(42)
        n_years = 20
        papers_per_year = 30
        n = n_years * papers_per_year
        years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
        df = pd.DataFrame({"year": years, "cited_by_count": 0})
        emb = rng.randn(n, 64).astype(np.float32)

        result = compute_c2st_embedding(df, emb, cfg)
        assert len(result) > 0, "compute_c2st_embedding produced no rows"

        # Add channel (dispatcher does this normally)
        result["channel"] = "semantic"
        DivergenceSchema.validate(result)


class TestC2STLexicalSchema:
    """Output of compute_c2st_lexical matches DivergenceSchema."""

    def test_output_schema(self):
        """Synthetic text data produces valid DivergenceSchema output."""
        import copy

        from _divergence_c2st import compute_c2st_lexical
        from pipeline_loaders import load_analysis_config
        from schemas import DivergenceSchema

        cfg = copy.deepcopy(load_analysis_config())
        cfg["divergence"]["windows"] = [2]
        cfg["divergence"]["max_subsample"] = 500

        # Build synthetic text data: 20 years, 30 papers per year
        rng = np.random.RandomState(42)
        n_years = 20
        papers_per_year = 30
        words = [
            "climate",
            "finance",
            "carbon",
            "green",
            "bond",
            "risk",
            "policy",
            "energy",
            "market",
            "investment",
        ]
        rows = []
        for y in range(2000, 2000 + n_years):
            for _ in range(papers_per_year):
                text = " ".join(rng.choice(words, size=15))
                rows.append({"year": y, "abstract": text})
        df = pd.DataFrame(rows)

        result = compute_c2st_lexical(df, None, cfg)
        assert len(result) > 0, "compute_c2st_lexical produced no rows"

        result["channel"] = "lexical"
        DivergenceSchema.validate(result)


# ---------------------------------------------------------------------------
# Dispatcher integration
# ---------------------------------------------------------------------------


class TestC2STDispatcherIntegration:
    """compute_divergence.py registers both C2ST methods."""

    def test_methods_registered(self):
        from compute_divergence import METHODS

        assert "C2ST_embedding" in METHODS, "C2ST_embedding not in METHODS"
        assert "C2ST_lexical" in METHODS, "C2ST_lexical not in METHODS"

    def test_c2st_embedding_entry(self):
        from compute_divergence import METHODS

        entry = METHODS["C2ST_embedding"]
        assert entry[0] == "_divergence_c2st"
        assert entry[2] == "semantic"
        assert entry[3] is True  # needs_embeddings
        assert entry[4] is False  # needs_citations

    def test_c2st_lexical_entry(self):
        from compute_divergence import METHODS

        entry = METHODS["C2ST_lexical"]
        assert entry[0] == "_divergence_c2st"
        assert entry[2] == "lexical"
        assert entry[3] is False  # needs_embeddings
        assert entry[4] is False  # needs_citations
