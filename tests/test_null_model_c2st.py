"""Tests for C2ST null model permutation drivers (ticket 0107).

Tests:
1. _run_c2st_embedding_permutations — unit test with mocked loaders
2. _run_c2st_lexical_permutations   — unit test with mocked loaders
3. main() dispatch — C2ST methods gate before channel branches
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Shared synthetic data builders
# ---------------------------------------------------------------------------


def _make_semantic_data(n_years=15, papers_per_year=30, emb_dim=20, seed=42):
    """Return (df, emb) suitable for patching load_semantic_data."""
    rng = np.random.RandomState(seed)
    years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
    df = pd.DataFrame({"year": years, "cited_by_count": 10})
    emb = rng.randn(len(df), emb_dim).astype(np.float32)
    return df, emb


def _make_lexical_data(n_years=15, papers_per_year=30, seed=42):
    """Return a DataFrame with 'year' and 'abstract' for patching load_lexical_data."""
    rng = np.random.RandomState(seed)
    vocab = [
        "climate",
        "finance",
        "carbon",
        "energy",
        "policy",
        "market",
        "green",
        "bond",
        "risk",
        "fund",
        "investment",
        "emissions",
        "trading",
        "bank",
        "tax",
    ]
    years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
    abstracts = [
        " ".join(rng.choice(vocab, rng.randint(10, 30), replace=True))
        for _ in range(len(years))
    ]
    return pd.DataFrame({"year": years, "abstract": abstracts})


def _base_cfg(n_perm=20):
    """Minimal config covering all keys read by the C2ST null model drivers."""
    return {
        "divergence": {
            "windows": [3],
            "max_subsample": 50,
            "equal_n": False,
            "random_seed": 42,
            "gap": 1,
            "permutation": {"n_perm": n_perm},
            "min_papers_fraction": 0.001,
            "min_papers_floor": 5,
            "c2st": {
                "pca_dim": 4,
                "cv_folds": 2,
                "class_weight": "balanced",
                "min_papers": 5,
            },
            "lexical": {
                "tfidf_max_features": 50,
                "tfidf_min_df": 1,
            },
        }
    }


# ---------------------------------------------------------------------------
# Unit test: _run_c2st_embedding_permutations
# ---------------------------------------------------------------------------


class TestC2STEmbeddingNullModel:
    """Unit tests for _run_c2st_embedding_permutations."""

    def test_driver_importable(self):
        """_run_c2st_embedding_permutations must be importable from compute_null_model."""
        from compute_null_model import _run_c2st_embedding_permutations

        assert callable(_run_c2st_embedding_permutations)

    def test_output_schema(self):
        """Output must pass NullModelSchema and have expected columns."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_embedding_permutations
        from schemas import NullModelSchema

        df, emb = _make_semantic_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            result = _run_c2st_embedding_permutations(div_df, cfg)

        assert len(result) > 0, "Expected at least one row"
        NullModelSchema.validate(result)

        expected_cols = {
            "year",
            "window",
            "observed",
            "null_mean",
            "null_std",
            "z_score",
            "p_value",
        }
        assert expected_cols == set(result.columns)

    def test_auc_in_valid_range(self):
        """Observed AUC and null_mean should be in [0, 1]."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_embedding_permutations

        df, emb = _make_semantic_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2006], "window": [3, 3]})

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            result = _run_c2st_embedding_permutations(div_df, cfg)

        rows = result.dropna()
        if len(rows) > 0:
            assert rows["observed"].between(0.0, 1.0).all(), "observed AUC out of [0,1]"
            assert rows["null_mean"].between(0.0, 1.0).all(), (
                "null_mean AUC out of [0,1]"
            )

    def test_null_auc_near_chance(self):
        """Under the null (shuffled labels), AUC should be near 0.5."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_embedding_permutations

        df, emb = _make_semantic_data()
        cfg = _base_cfg(n_perm=30)
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            result = _run_c2st_embedding_permutations(div_df, cfg)

        rows = result.dropna()
        if len(rows) > 0:
            null_mean = rows["null_mean"].iloc[0]
            assert 0.2 <= null_mean <= 0.8, (
                f"null_mean={null_mean:.3f} too far from 0.5 under null"
            )

    def test_reproducible(self):
        """Same config must produce identical z-scores on repeated calls."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_embedding_permutations

        df, emb = _make_semantic_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            r1 = _run_c2st_embedding_permutations(div_df, cfg)

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            r2 = _run_c2st_embedding_permutations(div_df, cfg)

        assert r1["z_score"].tolist() == r2["z_score"].tolist(), (
            "Results not reproducible"
        )


# ---------------------------------------------------------------------------
# Unit test: _run_c2st_lexical_permutations
# ---------------------------------------------------------------------------


class TestC2STLexicalNullModel:
    """Unit tests for _run_c2st_lexical_permutations."""

    def test_driver_importable(self):
        """_run_c2st_lexical_permutations must be importable from compute_null_model."""
        from compute_null_model import _run_c2st_lexical_permutations

        assert callable(_run_c2st_lexical_permutations)

    def test_output_schema(self):
        """Output must pass NullModelSchema and have expected columns."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_lexical_permutations
        from schemas import NullModelSchema

        df = _make_lexical_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            result = _run_c2st_lexical_permutations(div_df, cfg)

        assert len(result) > 0, "Expected at least one row"
        NullModelSchema.validate(result)

        expected_cols = {
            "year",
            "window",
            "observed",
            "null_mean",
            "null_std",
            "z_score",
            "p_value",
        }
        assert expected_cols == set(result.columns)

    def test_auc_in_valid_range(self):
        """Observed AUC and null_mean should be in [0, 1]."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_lexical_permutations

        df = _make_lexical_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2006], "window": [3, 3]})

        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            result = _run_c2st_lexical_permutations(div_df, cfg)

        rows = result.dropna()
        if len(rows) > 0:
            assert rows["observed"].between(0.0, 1.0).all(), "observed AUC out of [0,1]"
            assert rows["null_mean"].between(0.0, 1.0).all(), (
                "null_mean AUC out of [0,1]"
            )

    def test_null_auc_near_chance(self):
        """Under the null (shuffled labels), AUC should be near 0.5."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_lexical_permutations

        df = _make_lexical_data()
        cfg = _base_cfg(n_perm=30)
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            result = _run_c2st_lexical_permutations(div_df, cfg)

        rows = result.dropna()
        if len(rows) > 0:
            null_mean = rows["null_mean"].iloc[0]
            assert 0.2 <= null_mean <= 0.8, (
                f"null_mean={null_mean:.3f} too far from 0.5 under null"
            )

    def test_reproducible(self):
        """Same config must produce identical z-scores on repeated calls."""
        from unittest.mock import patch

        from compute_null_model import _run_c2st_lexical_permutations

        df = _make_lexical_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            r1 = _run_c2st_lexical_permutations(div_df, cfg)

        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            r2 = _run_c2st_lexical_permutations(div_df, cfg)

        assert r1["z_score"].tolist() == r2["z_score"].tolist(), (
            "Results not reproducible"
        )


# ---------------------------------------------------------------------------
# Integration smoke test: subprocess invocation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestC2STNullModelSmoke:
    """Smoke tests that invoke compute_null_model.py via subprocess."""

    @pytest.mark.parametrize("method", ["C2ST_embedding", "C2ST_lexical"])
    def test_compute_produces_output(self, method, tmp_path):
        """Script runs end-to-end and produces a valid CSV on smoke fixture."""
        import subprocess

        from conftest import run_compute, smoke_env

        div_out = tmp_path / f"tab_div_{method}.csv"
        result = run_compute(method, div_out)
        assert result.returncode == 0, f"Divergence {method} failed:\n{result.stderr}"

        null_out = tmp_path / f"tab_null_{method}.csv"
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "compute_null_model.py"),
            "--method",
            method,
            "--output",
            str(null_out),
            "--div-csv",
            str(div_out),
        ]
        res = subprocess.run(
            cmd,
            env=smoke_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert res.returncode == 0, (
            f"Null model {method} failed:\nstdout: {res.stdout}\nstderr: {res.stderr}"
        )
        assert null_out.exists(), f"Output CSV not created for {method}"

        df = pd.read_csv(null_out)
        expected_cols = {
            "year",
            "window",
            "observed",
            "null_mean",
            "null_std",
            "z_score",
            "p_value",
        }
        assert expected_cols == set(df.columns)
        assert len(df) > 0
        # AUC-based null mean should be in a reasonable range
        rows = df.dropna()
        if len(rows) > 0:
            assert rows["null_mean"].between(0.0, 1.0).all()
