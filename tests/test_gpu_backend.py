"""Tests for GPU backend dispatch and torch/numpy equivalence.

Tests:
1. Backend dispatch logic (auto, cpu, cuda)
2. Torch implementations match numpy within tolerance (S1-S4)
3. Config toggle works end-to-end
"""

import os
import sys

import numpy as np
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

# Skip entire module if torch+CUDA unavailable
torch = pytest.importorskip("torch")
pytestmark = pytest.mark.skipif(
    not torch.cuda.is_available(),
    reason="CUDA not available",
)


@pytest.fixture()
def random_arrays():
    """Two random 200x64 arrays (small but enough for all methods)."""
    rng = np.random.RandomState(123)
    X = rng.randn(200, 64).astype(np.float32)
    Y = rng.randn(200, 64).astype(np.float32) + 0.3  # shift for nonzero distance
    return X, Y


@pytest.fixture()
def cfg_gpu():
    """Config with backend: cuda."""
    from pipeline_loaders import load_analysis_config

    cfg = load_analysis_config()
    cfg["divergence"]["backend"] = "cuda"
    return cfg


@pytest.fixture()
def cfg_cpu():
    """Config with backend: cpu."""
    from pipeline_loaders import load_analysis_config

    cfg = load_analysis_config()
    cfg["divergence"]["backend"] = "cpu"
    return cfg


# ---------------------------------------------------------------------------
# Backend dispatch
# ---------------------------------------------------------------------------


class TestBackendDispatch:
    """get_backend returns correct value for each config setting."""

    def test_cpu_setting(self, cfg_cpu):
        from _divergence_backend import get_backend

        assert get_backend(cfg_cpu) == "numpy"

    def test_cuda_setting(self, cfg_gpu):
        from _divergence_backend import get_backend

        assert get_backend(cfg_gpu) == "torch"

    def test_auto_selects_torch_when_cuda(self):
        from _divergence_backend import get_backend

        cfg = {"divergence": {"backend": "auto"}}
        assert get_backend(cfg) == "torch"

    def test_invalid_cuda_raises(self, monkeypatch):
        # Temporarily pretend CUDA is unavailable
        import _divergence_backend
        from _divergence_backend import get_backend

        monkeypatch.setattr(_divergence_backend, "_TORCH_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="cuda"):
            get_backend({"divergence": {"backend": "cuda"}})
        # Reset cached state
        monkeypatch.setattr(_divergence_backend, "_TORCH_AVAILABLE", None)


# ---------------------------------------------------------------------------
# Torch/numpy equivalence for S1-S4
# ---------------------------------------------------------------------------

RTOL = 1e-3  # float32 accumulation tolerance for O(n²) sums


class TestMMDEquivalence:
    """S1: _mmd_rbf_torch matches compute_mmd_rbf."""

    def test_values_match(self, random_arrays):
        from _divergence_semantic import _mmd_rbf_torch, compute_mmd_rbf

        X, Y = random_arrays
        bandwidth = float(np.median(np.sum((X[:100] - Y[:100]) ** 2, axis=1)))

        val_np = compute_mmd_rbf(X, Y, bandwidth)
        val_torch = _mmd_rbf_torch(X, Y, bandwidth)

        assert val_np > 0, "numpy MMD should be positive for shifted distributions"
        assert val_torch > 0, "torch MMD should be positive for shifted distributions"
        np.testing.assert_allclose(val_torch, val_np, rtol=RTOL)


class TestEnergyEquivalence:
    """S2: _energy_distance_torch matches dcor.energy_distance."""

    def test_values_match(self, random_arrays):
        import dcor
        from _divergence_semantic import _energy_distance_torch

        X, Y = random_arrays

        val_np = float(dcor.energy_distance(X, Y))
        val_torch = _energy_distance_torch(X, Y)

        assert val_np > 0
        assert val_torch > 0
        np.testing.assert_allclose(val_torch, val_np, rtol=RTOL)


class TestFrechetEquivalence:
    """S4: _frechet_torch matches compute_frechet_distance."""

    def test_values_match(self, random_arrays):
        from _divergence_semantic import _frechet_torch, compute_frechet_distance

        X, Y = random_arrays

        val_np = compute_frechet_distance(X, Y)
        val_torch = _frechet_torch(X, Y)

        assert val_np > 0
        assert val_torch > 0
        np.testing.assert_allclose(val_torch, val_np, rtol=RTOL)


class TestWassersteinGPU:
    """S3: POT with torch tensors produces same result as numpy.

    POT generates random projections independently per backend, so
    exact match is not expected — we check both are positive and
    within 1% of each other.
    """

    def test_values_match(self, random_arrays):
        import ot
        from _divergence_backend import to_tensor

        X, Y = random_arrays
        n_proj = 500

        val_np = float(
            ot.sliced_wasserstein_distance(X, Y, n_projections=n_proj, seed=42)
        )
        val_torch = float(
            ot.sliced_wasserstein_distance(
                to_tensor(X), to_tensor(Y), n_projections=n_proj, seed=42
            )
        )

        assert val_np > 0
        assert val_torch > 0
        np.testing.assert_allclose(val_torch, val_np, rtol=5e-3)
