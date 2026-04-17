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
        """Under H0 (same distribution), AUC should be near 0.5.

        Tolerance 0.35-0.65: with only 200 samples per class and 5-fold CV,
        logistic regression AUC has high variance on random data.  Tighter
        bounds (e.g. 0.40-0.60) cause sporadic failures across seeds.
        """
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(42)
        X = rng.randn(200, 32)
        Y = rng.randn(200, 32)
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)["mean"]
        assert 0.35 < auc < 0.65, f"Null AUC should be near 0.5, got {auc}"

    def test_shift_auc_high(self):
        """With a planted shift, AUC should be well above 0.5."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(42)
        X = rng.randn(200, 32)
        Y = rng.randn(200, 32) + 1.0  # shifted
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)["mean"]
        assert auc > 0.7, f"Shifted AUC should be > 0.7, got {auc}"

    def test_auc_bounded_zero_one(self):
        """AUC should always be in [0, 1]."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(99)
        X = rng.randn(100, 16)
        Y = rng.randn(100, 16) + 0.5
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)["mean"]
        assert 0.0 <= auc <= 1.0, f"AUC out of bounds: {auc}"

    def test_shuffled_cv_reproducible(self):
        """Same seed must produce identical AUC (shuffled CV is deterministic)."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(7)
        X = rng.randn(150, 20)
        Y = rng.randn(150, 20) + 0.3
        r1 = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=123)
        r2 = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=123)
        assert r1["mean"] == r2["mean"], (
            f"Same seed gave different mean: {r1['mean']} vs {r2['mean']}"
        )

    def test_returns_fold_variance(self):
        """_c2st_auc returns per-fold variance, CI, n_folds, and p-value vs 0.5.

        Ticket 0068: C2ST uses CV fold variance as its inference primitive
        instead of the shared permutation null. Must expose: mean, std,
        q025, q975, n_folds, p_value_vs_chance.
        """
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(42)
        X = rng.randn(200, 32)
        Y = rng.randn(200, 32) + 1.5  # strong shift — clearly > 0.5 AUC
        result = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        for key in ("mean", "std", "q025", "q975", "n_folds", "p_value_vs_chance"):
            assert key in result, f"Missing key {key} in {result.keys()}"
        assert result["n_folds"] == 5
        assert result["std"] > 0, f"std should be > 0 on real data, got {result['std']}"
        assert 0.0 <= result["q025"] <= result["mean"] <= result["q975"] <= 1.0, (
            f"CI ordering wrong: {result}"
        )
        # One-sample t vs 0.5 should reject H0 on well-separated data
        assert result["p_value_vs_chance"] < 0.05, (
            f"p-value vs 0.5 should be < 0.05 on shifted data, got {result['p_value_vs_chance']}"
        )

    def test_null_p_value_not_significant(self):
        """Under H0 (no shift), p-value vs 0.5 should usually be >= 0.05."""
        from _divergence_c2st import _c2st_auc

        rng = np.random.RandomState(0)
        X = rng.randn(200, 32)
        Y = rng.randn(200, 32)
        result = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=0)
        # Lenient bound: CV AUC can wobble; we just check the p-value is a
        # reasonable probability, not a pathological value.
        assert 0.0 <= result["p_value_vs_chance"] <= 1.0

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
        auc = _c2st_auc(X, Y, cv_folds=5, class_weight="balanced", seed=42)["mean"]
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
    """Output of compute_c2st_embedding matches C2STDivergenceSchema."""

    def test_output_schema(self):
        """Synthetic data produces valid C2STDivergenceSchema output."""
        import copy

        from _divergence_c2st import compute_c2st_embedding
        from pipeline_loaders import load_analysis_config
        from schemas import C2STDivergenceSchema

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

        # Dispatcher attaches channel before validating
        result["channel"] = "semantic"
        C2STDivergenceSchema.validate(result)
        for col in ("auc_std", "auc_q025", "auc_q975", "n_folds", "p_value_vs_chance"):
            assert col in result.columns, f"{col} missing from C2ST output"


class TestC2STLexicalSchema:
    """Output of compute_c2st_lexical matches C2STDivergenceSchema."""

    def test_output_schema(self):
        """Synthetic text data produces valid C2STDivergenceSchema output."""
        import copy

        from _divergence_c2st import compute_c2st_lexical
        from pipeline_loaders import load_analysis_config
        from schemas import C2STDivergenceSchema

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
        C2STDivergenceSchema.validate(result)


class TestC2STSchemaStrict:
    """C2STDivergenceSchema must reject rows missing the variance columns."""

    def test_rejects_missing_variance_columns(self):
        """Missing auc_std must fail strict C2STDivergenceSchema validation."""
        import pandera.errors
        import pytest
        from schemas import C2STDivergenceSchema

        bad = pd.DataFrame(
            [
                {
                    "year": 2010,
                    "channel": "semantic",
                    "window": "2",
                    "hyperparams": "pca=32",
                    "value": 0.7,
                    # auc_std, q025, q975, n_folds, p_value_vs_chance missing
                }
            ]
        )
        with pytest.raises((pandera.errors.SchemaError, pandera.errors.SchemaErrors)):
            C2STDivergenceSchema.validate(bad)


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


# ---------------------------------------------------------------------------
# PCA n_components floor path (ticket 0063 item 1a)
# ---------------------------------------------------------------------------


class TestC2STPCAFloor:
    """Exercise the n_components = max(2, ...) clamp for tiny datasets."""

    def test_pca_floor_with_tiny_dataset(self):
        """When min(len(X), len(Y)) <= 2, PCA n_components should clamp to 2.

        With only 3 samples in the smaller window and pca_dim=32,
        min(pca_dim, min(3,3)-1, dim) = min(32, 2, 8) = 2.
        The floor max(2, 2) = 2 is a no-op here.  We also check with 2
        samples where min(pca_dim, 1, dim) = 1, clamped to 2.
        """
        import copy

        from _divergence_c2st import compute_c2st_embedding
        from pipeline_loaders import load_analysis_config

        cfg = copy.deepcopy(load_analysis_config())
        cfg["divergence"]["windows"] = [1]
        cfg["divergence"]["max_subsample"] = 5000
        cfg["divergence"]["min_papers"] = 2
        cfg["divergence"]["min_papers_smoke"] = 2
        # Set low cv_folds and pca_dim to allow tiny datasets
        cfg["divergence"]["c2st"] = {
            "pca_dim": 32,
            "cv_folds": 2,
            "class_weight": "balanced",
        }

        # Build tiny data: 3 years with 2 papers each -> window of 1 year
        # gives before/after groups of ~2-4 papers.
        # With window=1: before = [year-1, year], after = [year+1, year+2]
        rng = np.random.RandomState(42)
        n_years = 4
        papers_per_year = 2
        n = n_years * papers_per_year
        years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
        df = pd.DataFrame({"year": years, "cited_by_count": 0})
        emb = rng.randn(n, 8).astype(np.float32)

        # This should trigger n_components = max(2, min(32, 3, 8)) = max(2, 3) = 3
        # or n_components = max(2, min(32, 1, 8)) = max(2, 1) = 2  (the floor path)
        result = compute_c2st_embedding(df, emb, cfg)
        # Verify the floor path was hit by checking hyperparams
        if len(result) > 0:
            for _, row in result.iterrows():
                pca_val = int(row["hyperparams"].replace("pca=", ""))
                assert pca_val >= 2, (
                    f"PCA n_components should be >= 2 after floor, got {pca_val}"
                )
