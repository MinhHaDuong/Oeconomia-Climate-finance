"""cluster_labels.json is a Phase 2 artifact, not Phase 1.

It must be read from content/tables/, not data/catalogs/.
Tickets: #199, #204
"""

import os
import sys
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import utils


def test_cluster_labels_path_is_phase2():
    """_CLUSTER_LABELS_PATH must point to content/tables/, not data/catalogs/."""
    path = utils._CLUSTER_LABELS_PATH
    assert path.endswith(os.path.join("content", "tables", "cluster_labels.json")), (
        f"cluster_labels.json path should end with content/tables/cluster_labels.json, "
        f"got {path}"
    )
    assert "catalogs" not in path, (
        f"cluster_labels.json path points to {path}, "
        "must not be in data/catalogs/ (Phase 1)"
    )


def test_fallback_warning_references_compute_clusters():
    """When cluster_labels.json is missing, the warning must tell users to run compute_clusters.py."""
    # Temporarily override path to a non-existent location to trigger fallback
    original = utils._CLUSTER_LABELS_PATH
    try:
        utils._CLUSTER_LABELS_PATH = "/nonexistent/cluster_labels.json"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            labels = utils.load_cluster_labels(n_clusters=4)
        assert len(w) == 1, f"Expected 1 warning, got {len(w)}"
        msg = str(w[0].message)
        assert "compute_clusters.py" in msg, (
            f"Warning should reference compute_clusters.py, got: {msg}"
        )
        # Verify fallback returns generic labels
        assert labels == {i: f"Cluster {i}" for i in range(4)}
    finally:
        utils._CLUSTER_LABELS_PATH = original
