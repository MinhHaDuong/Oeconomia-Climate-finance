"""cluster_labels.json is a Phase 2 artifact, not Phase 1.

It must be read from content/tables/, not data/catalogs/.
Ticket: #199
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import utils


def test_cluster_labels_path_is_phase2():
    """_CLUSTER_LABELS_PATH must point to content/tables/, not data/catalogs/."""
    path = utils._CLUSTER_LABELS_PATH
    assert "content" in path and "tables" in path, (
        f"cluster_labels.json path points to {path}, "
        "expected content/tables/ (Phase 2 output)"
    )
    assert "catalogs" not in path, (
        f"cluster_labels.json path points to {path}, "
        "must not be in data/catalogs/ (Phase 1)"
    )
