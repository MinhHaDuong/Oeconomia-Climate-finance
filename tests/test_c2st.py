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
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)
        assert 0.35 < auc < 0.65, f"Null AUC should be near 0.5, got {auc}"

    def test_shift_auc_high(self):
        """With a planted shift, AUC should be well above 0.5."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(42)
        X = rng.randn(200, 32)
        Y = rng.randn(200, 32) + 1.0  # shifted
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)
        assert auc > 0.7, f"Shifted AUC should be > 0.7, got {auc}"

    def test_auc_bounded_zero_one(self):
        """AUC should always be in [0, 1]."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(99)
        X = rng.randn(100, 16)
        Y = rng.randn(100, 16) + 0.5
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)
        assert 0.0 <= auc <= 1.0, f"AUC out of bounds: {auc}"

    def test_shuffled_cv_reproducible(self):
        """Same seed must produce identical AUC (shuffled CV is deterministic)."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(7)
        X = rng.randn(150, 20)
        Y = rng.randn(150, 20) + 0.3
        auc1 = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=123)
        auc2 = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=123)
        assert auc1 == auc2, f"Same seed gave different AUC: {auc1} vs {auc2}"

    def test_contiguous_labels_not_degenerate(self):
        """With contiguous labels (all 0s then all 1s), AUC must not be degenerate.

        This is the bug scenario: unshuffled StratifiedKFold on contiguous labels
        can produce extreme fold compositions. A properly shuffled CV should yield
        AUC in a reasonable range for a mild shift.
        """
        from _divergence_c2st import _c2st_auc

        # Contiguous labels: all X first, then all Y — exactly what _c2st_auc builds
        rng = np.random.RandomState(42)
        X = rng.randn(100, 10)
        Y = rng.randn(100, 10) + 0.5  # mild shift
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)
        # A reasonable classifier should find a mild shift; AUC should be clearly
        # between 0.5 and 1.0 (not degenerate 0.0 or 1.0)
        assert 0.5 < auc < 0.95, (
            f"AUC on contiguous-label mild shift should be moderate, got {auc}"
        )

    def test_uses_shuffled_stratified_kfold(self):
        """Verify that _c2st_auc uses StratifiedKFold with shuffle=True.

        This is the direct regression test for the contiguous-labels bug.
        """
        from unittest.mock import patch

        from _divergence_c2st import _c2st_auc
        from sklearn.model_selection import StratifiedKFold

        rng = np.random.RandomState(42)
        X = rng.randn(100, 10)
        Y = rng.randn(100, 10)

        with patch(
            "_divergence_c2st.StratifiedKFold", wraps=StratifiedKFold
        ) as mock_skf:
            _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)

        mock_skf.assert_called_once()
        assert mock_skf.call_args.kwargs.get("shuffle") is True, (
            f"StratifiedKFold not called with shuffle=True: {mock_skf.call_args.kwargs}"
        )


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

        result = compute_c2st_lexical(df, cfg)
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
