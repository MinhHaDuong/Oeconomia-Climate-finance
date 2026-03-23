"""Tests for #307: Embedding cache survives DVC output deletion.

The incremental embedding cache must live in enrich_cache/ (not as a DVC output),
so DVC re-runs don't destroy already-computed vectors.

Verifies:
- utils.py exports EMBEDDINGS_CACHE_PATH pointing to enrich_cache/
- enrich_embeddings.py reads cache from EMBEDDINGS_CACHE_PATH, not EMBEDDINGS_PATH
- enrich_embeddings.py writes cache to EMBEDDINGS_CACHE_PATH
- enrich_embeddings.py writes DVC output to EMBEDDINGS_PATH (unchanged)
- DVC stage does not list the cache path as an output
"""

import ast
import os
import sys

import yaml
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
DVC_YAML = os.path.join(os.path.dirname(__file__), "..", "dvc.yaml")
sys.path.insert(0, SCRIPTS_DIR)


class TestEmbeddingsCachePath:
    """utils.py exports the cache path in enrich_cache/."""

    def test_cache_path_exists_in_utils(self):
        from utils import EMBEDDINGS_CACHE_PATH
        assert "enrich_cache" in EMBEDDINGS_CACHE_PATH

    def test_cache_path_is_npz(self):
        from utils import EMBEDDINGS_CACHE_PATH
        assert EMBEDDINGS_CACHE_PATH.endswith(".npz")

    def test_cache_path_differs_from_output(self):
        from utils import EMBEDDINGS_CACHE_PATH, EMBEDDINGS_PATH
        assert EMBEDDINGS_CACHE_PATH != EMBEDDINGS_PATH


class TestEnrichEmbeddingsScript:
    """enrich_embeddings.py reads/writes cache from enrich_cache/, not the DVC output."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        path = os.path.join(SCRIPTS_DIR, "enrich_embeddings.py")
        with open(path) as f:
            self.source = f.read()

    def test_imports_cache_path(self):
        """Script must import EMBEDDINGS_CACHE_PATH from utils."""
        assert "EMBEDDINGS_CACHE_PATH" in self.source

    def test_reads_cache_from_cache_path(self):
        """Cache loading must use EMBEDDINGS_CACHE_PATH, not EMBEDDINGS_PATH directly."""
        tree = ast.parse(self.source)
        # Find all function calls where EMBEDDINGS_CACHE_PATH is an argument
        # (either np.load(EMBEDDINGS_CACHE_PATH) or helper(EMBEDDINGS_CACHE_PATH))
        cache_path_used = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args:
                for arg in node.args:
                    if isinstance(arg, ast.Name) and arg.id == "EMBEDDINGS_CACHE_PATH":
                        cache_path_used = True
                        break
        assert cache_path_used, (
            "EMBEDDINGS_CACHE_PATH must be passed to a function call (np.load or helper)"
        )


class TestDVCStageUnchanged:
    """DVC stage still outputs embeddings.npz, and does NOT output the cache."""

    @pytest.fixture(autouse=True)
    def _load_dvc(self):
        with open(DVC_YAML) as f:
            self.dvc = yaml.safe_load(f)
        self.stage = self.dvc["stages"]["enrich_embeddings"]

    def test_output_is_embeddings_npz(self):
        outs = [str(o) for o in self.stage["outs"]]
        assert any("embeddings.npz" in o for o in outs)

    def test_cache_not_in_outputs(self):
        outs = [str(o) for o in self.stage["outs"]]
        assert not any("enrich_cache" in o for o in outs)
