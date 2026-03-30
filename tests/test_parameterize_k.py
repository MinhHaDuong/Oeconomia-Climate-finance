"""Tests for #511: analyze_embeddings.py reads K from config/analysis.yaml.

Verifies that n_clusters is not hardcoded — it should be a variable
read from the config file, not a literal integer.
"""

import ast
import os

import yaml

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


class TestKFromConfig:
    """K parameter comes from config, not hardcoded."""

    def test_config_declares_k(self):
        with open(os.path.join(CONFIG_DIR, "analysis.yaml")) as f:
            cfg = yaml.safe_load(f)
        assert "clustering" in cfg
        assert "k" in cfg["clustering"]
        assert isinstance(cfg["clustering"]["k"], int)

    def test_no_hardcoded_n_clusters(self):
        """KMeans(n_clusters=...) must not use a literal integer."""
        source = open(os.path.join(SCRIPTS_DIR, "analyze_embeddings.py")).read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "n_clusters":
                assert not isinstance(node.value, ast.Constant), (
                    f"n_clusters is hardcoded to {node.value.value} — "
                    "should read from config/analysis.yaml"
                )

    def test_analyze_embeddings_not_in_dvc(self):
        """analyze_embeddings is Phase 2 — must NOT be a DVC stage (#527)."""
        dvc_path = os.path.join(os.path.dirname(__file__), "..", "dvc.yaml")
        with open(dvc_path) as f:
            dvc = yaml.safe_load(f)
        assert "analyze_embeddings" not in dvc.get("stages", {}), (
            "analyze_embeddings is Phase 2 — should be a Makefile target, not DVC"
        )
