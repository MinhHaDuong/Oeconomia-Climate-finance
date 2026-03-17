"""Tests for #189: Split analyze_embeddings into encoding (Phase 1) and analysis (Phase 2).

Verifies:
- enrich_embeddings.py exists and produces only embeddings.npz (no UMAP/clustering)
- analyze_embeddings.py exists and consumes embeddings.npz (produces semantic_clusters.csv)
- dvc.yaml enrich_embeddings stage runs enrich_embeddings.py (not analyze_embeddings.py)
- dvc.yaml enrich_embeddings stage outputs only embeddings.npz
- A Phase 2 analyze_embeddings stage exists in dvc.yaml with semantic_clusters.csv output
"""

import os
import sys

import yaml
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
DVC_YAML = os.path.join(os.path.dirname(__file__), "..", "dvc.yaml")
sys.path.insert(0, SCRIPTS_DIR)


class TestDVCStages:
    """DVC pipeline declares the correct stages after the split."""

    @pytest.fixture(autouse=True)
    def _load_dvc(self):
        with open(DVC_YAML) as f:
            self.dvc = yaml.safe_load(f)
        self.stages = self.dvc.get("stages", {})

    def test_enrich_embeddings_runs_enrich_script(self):
        """enrich_embeddings stage must run enrich_embeddings.py, not analyze_embeddings.py."""
        stage = self.stages["enrich_embeddings"]
        assert "enrich_embeddings.py" in stage["cmd"]
        assert "analyze_embeddings.py" not in stage["cmd"]

    def test_enrich_embeddings_deps_on_enrich_script(self):
        """enrich_embeddings stage must depend on enrich_embeddings.py."""
        deps = self.stages["enrich_embeddings"]["deps"]
        dep_strs = [str(d) for d in deps]
        assert any("enrich_embeddings.py" in d for d in dep_strs)
        assert not any("analyze_embeddings.py" in d for d in dep_strs)

    def test_enrich_embeddings_outputs_only_npz(self):
        """enrich_embeddings stage must output embeddings.npz and nothing else."""
        outs = self.stages["enrich_embeddings"]["outs"]
        out_strs = [str(o) for o in outs]
        assert any("embeddings.npz" in o for o in out_strs)
        assert not any("semantic_clusters" in o for o in out_strs)

    def test_analyze_embeddings_stage_exists(self):
        """A Phase 2 analyze_embeddings stage must exist."""
        assert "analyze_embeddings" in self.stages

    def test_analyze_embeddings_depends_on_embeddings_npz(self):
        """analyze_embeddings stage must depend on embeddings.npz."""
        deps = self.stages["analyze_embeddings"]["deps"]
        dep_strs = [str(d) for d in deps]
        assert any("embeddings.npz" in d for d in dep_strs)

    def test_analyze_embeddings_outputs_clusters(self):
        """analyze_embeddings stage must output semantic_clusters.csv."""
        outs = self.stages["analyze_embeddings"]["outs"]
        out_strs = [str(o) for o in outs]
        assert any("semantic_clusters" in o for o in out_strs)


class TestScriptFiles:
    """The correct script files exist after the split."""

    def test_enrich_embeddings_script_exists(self):
        assert os.path.isfile(os.path.join(SCRIPTS_DIR, "enrich_embeddings.py"))

    def test_analyze_embeddings_script_exists(self):
        assert os.path.isfile(os.path.join(SCRIPTS_DIR, "analyze_embeddings.py"))

    def test_enrich_script_does_not_import_umap(self):
        """Encoding-only script must not import umap or sklearn."""
        with open(os.path.join(SCRIPTS_DIR, "enrich_embeddings.py")) as f:
            source = f.read()
        assert "import umap" not in source
        assert "from sklearn" not in source
        assert "import matplotlib" not in source

    def test_analyze_script_does_not_import_sentence_transformers(self):
        """Analysis script must not import sentence_transformers or torch."""
        with open(os.path.join(SCRIPTS_DIR, "analyze_embeddings.py")) as f:
            source = f.read()
        assert "SentenceTransformer" not in source
        assert "import torch" not in source
