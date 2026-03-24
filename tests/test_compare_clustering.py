"""Tests for compare_clustering.py — clustering methods comparison.

Ticket: #299 (tracking), sub-issues #300–#304.
Tests clustering method implementations and comparison framework.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# ---------------------------------------------------------------------------
# Fixtures: synthetic data that mimics real corpus structure
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_embeddings():
    """3 well-separated Gaussian blobs in 10D — any reasonable method should find them."""
    rng = np.random.RandomState(42)
    n_per = 100
    centers = [rng.randn(10) * 5 for _ in range(3)]
    X = np.vstack([c + rng.randn(n_per, 10) * 0.5 for c in centers])
    true_labels = np.repeat([0, 1, 2], n_per)
    return X, true_labels


@pytest.fixture
def noisy_embeddings():
    """Blobs with scattered noise points — tests HDBSCAN noise handling."""
    rng = np.random.RandomState(42)
    n_per = 80
    centers = [rng.randn(10) * 5 for _ in range(3)]
    blobs = np.vstack([c + rng.randn(n_per, 10) * 0.5 for c in centers])
    noise = rng.randn(20, 10) * 10  # scattered noise
    X = np.vstack([blobs, noise])
    return X


# ---------------------------------------------------------------------------
# Test: method dispatch and basic output shape
# ---------------------------------------------------------------------------

class TestClusterMethods:
    """Each clustering method returns valid labels of correct length."""

    def test_kmeans_labels(self, synthetic_embeddings):
        from compare_clustering import cluster_kmeans
        X, _ = synthetic_embeddings
        labels = cluster_kmeans(X, k=3, random_state=42)
        assert len(labels) == len(X)
        assert set(labels) == {0, 1, 2}

    def test_hdbscan_labels(self, synthetic_embeddings):
        from compare_clustering import cluster_hdbscan
        X, _ = synthetic_embeddings
        labels = cluster_hdbscan(X, min_cluster_size=10)
        assert len(labels) == len(X)
        # HDBSCAN may produce -1 for noise
        assert max(labels) >= 0, "Should find at least one cluster"

    def test_hdbscan_finds_noise(self, noisy_embeddings):
        from compare_clustering import cluster_hdbscan
        labels = cluster_hdbscan(noisy_embeddings, min_cluster_size=10)
        n_noise = sum(1 for l in labels if l == -1)
        # With well-separated blobs + random noise, should detect some noise
        assert n_noise > 0, "HDBSCAN should detect noise points"

    def test_spectral_labels(self, synthetic_embeddings):
        from compare_clustering import cluster_spectral
        X, _ = synthetic_embeddings
        labels = cluster_spectral(X, k=3, random_state=42)
        assert len(labels) == len(X)
        assert len(set(labels)) == 3

    def test_all_methods_agree_on_well_separated(self, synthetic_embeddings):
        """On trivially separable data, all methods should mostly agree."""
        from compare_clustering import cluster_kmeans, cluster_hdbscan, cluster_spectral
        from sklearn.metrics import adjusted_rand_score

        X, true = synthetic_embeddings
        km = cluster_kmeans(X, k=3, random_state=42)
        hdb = cluster_hdbscan(X, min_cluster_size=10)
        sp = cluster_spectral(X, k=3, random_state=42)

        # Each method vs ground truth — should be very high on clean blobs
        assert adjusted_rand_score(true, km) > 0.9
        # HDBSCAN: compare only non-noise points (must find most of them)
        non_noise = [i for i in range(len(hdb)) if hdb[i] >= 0]
        assert len(non_noise) > 50, (
            f"HDBSCAN should cluster most well-separated points, "
            f"got {len(non_noise)} non-noise out of {len(hdb)}"
        )
        assert adjusted_rand_score(
            [true[i] for i in non_noise],
            [hdb[i] for i in non_noise]
        ) > 0.9
        assert adjusted_rand_score(true, sp) > 0.9


# ---------------------------------------------------------------------------
# Test: stability metrics
# ---------------------------------------------------------------------------

class TestStabilityMetrics:
    """ARI-based stability measurement works correctly."""

    def test_ari_identical_assignments(self):
        from compare_clustering import compute_stability_ari
        labels = np.array([0, 1, 2, 0, 1, 2])
        ari = compute_stability_ari(labels, labels)
        assert ari == pytest.approx(1.0)

    def test_ari_random_assignments(self):
        from compare_clustering import compute_stability_ari
        rng = np.random.RandomState(42)
        a = rng.randint(0, 3, size=1000)
        b = rng.randint(0, 3, size=1000)
        ari = compute_stability_ari(a, b)
        assert abs(ari) < 0.1, "Random assignments should have near-zero ARI"

    def test_perturbation_stability(self, synthetic_embeddings):
        """Removing 1% of points should not drastically change clustering."""
        from compare_clustering import perturbation_stability
        X, _ = synthetic_embeddings
        mean_ari, std_ari = perturbation_stability(
            X, method="kmeans", k=3, drop_frac=0.01, n_repeats=5,
            random_state=42,
        )
        assert mean_ari > 0.8, f"Well-separated clusters should be stable, got {mean_ari}"
        assert std_ari < 0.2


# ---------------------------------------------------------------------------
# Test: optimal k analysis
# ---------------------------------------------------------------------------

class TestOptimalK:
    """k-selection metrics return valid results."""

    def test_silhouette_scores(self, synthetic_embeddings):
        from compare_clustering import silhouette_sweep
        X, _ = synthetic_embeddings
        results = silhouette_sweep(X, k_range=range(2, 6), random_state=42)
        assert len(results) == 4  # k=2,3,4,5
        # k=3 should have highest silhouette on 3-blob data
        best_k = max(results, key=lambda r: r["silhouette"])["k"]
        assert best_k == 3, f"Expected k=3 to win on 3-blob data, got k={best_k}"

    def test_hdbscan_min_cluster_size_sweep(self, synthetic_embeddings):
        from compare_clustering import hdbscan_sweep
        X, _ = synthetic_embeddings
        results = hdbscan_sweep(X, sizes=[5, 10, 20, 50])
        assert len(results) == 4
        for r in results:
            assert "min_cluster_size" in r
            assert "n_clusters" in r
            assert "noise_fraction" in r
            assert 0 <= r["noise_fraction"] <= 1


# ---------------------------------------------------------------------------
# Test: multi-space representations
# ---------------------------------------------------------------------------

class TestMultiSpace:
    """TF-IDF and citation space builders produce valid outputs."""

    def test_tfidf_space(self):
        from compare_clustering import build_tfidf_space
        df = pd.DataFrame({
            "abstract": [
                "climate change finance green bonds sustainable investment",
                "carbon emissions trading scheme cap and trade policy",
                "renewable energy solar wind power electricity generation",
                "forest conservation biodiversity ecosystem services land use",
            ] * 10  # 40 works
        })
        X, valid_idx = build_tfidf_space(df, max_features=100)
        assert X.shape[0] == 40
        assert X.shape[1] <= 100
        assert len(valid_idx) == 40

    def test_citation_space(self, tmp_path):
        from compare_clustering import build_citation_space
        # 6 works: A,B cite refs 1,2; C,D cite refs 2,3; E,F cite ref 4
        # → A-B coupled, C-D coupled, E-F coupled (3 groups)
        df = pd.DataFrame({
            "doi": ["10.1/a", "10.1/b", "10.1/c", "10.1/d", "10.1/e", "10.1/f"],
            "title": ["A", "B", "C", "D", "E", "F"],
        })
        cit_path = tmp_path / "citations.csv"
        cit_path.write_text(
            "source_doi,ref_doi\n"
            "10.1/a,10.99/r1\n10.1/a,10.99/r2\n"
            "10.1/b,10.99/r1\n10.1/b,10.99/r2\n"
            "10.1/c,10.99/r2\n10.1/c,10.99/r3\n"
            "10.1/d,10.99/r2\n10.1/d,10.99/r3\n"
            "10.1/e,10.99/r4\n"
            "10.1/f,10.99/r4\n"
        )
        X, valid_idx = build_citation_space(df, citations_path=str(cit_path))
        assert X is not None
        assert len(X) == len(valid_idx)
        assert len(valid_idx) <= 6
        # Vectors should be L2-normalized
        norms = np.linalg.norm(X, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-6)

    def test_spectral_subsampling_preserves_sample_labels(self):
        """Spectral subsampling: sample points keep spectral labels."""
        from compare_clustering import cluster_spectral
        rng = np.random.RandomState(42)
        # Create 3 well-separated blobs with enough points to trigger subsampling
        centers = [rng.randn(5) * 10 for _ in range(3)]
        X = np.vstack([c + rng.randn(20, 5) * 0.3 for c in centers])
        labels = cluster_spectral(X, k=3, random_state=42, max_n=30)
        assert len(labels) == 60
        assert len(set(labels)) == 3
        # All 60 points should be assigned (no -1 or uninitialized)
        assert all(0 <= l < 3 for l in labels)
