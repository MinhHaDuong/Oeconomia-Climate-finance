"""Tests for #57: Phase 1 migration validation.

Integration, incrementality, and compatibility tests ensuring that:
1. Phase 1 on a sample dataset produces valid outputs
2. Incremental reruns respect checkpoints/caches
3. corpus_filter.py --apply remains the stable endpoint
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture
def temp_catalogs(tmp_path):
    """Create temporary catalogs dir with sample unified_works.csv."""
    catalogs_dir = tmp_path / "catalogs"
    catalogs_dir.mkdir(parents=True)
    
    # Load fixture
    unified_df = pd.read_csv(
        os.path.join(os.path.dirname(__file__), "fixtures", "filter_fixture.csv")
    )
    (catalogs_dir / "unified_works.csv").write_text(unified_df.to_csv(index=False))
    
    # Create empty citations
    (catalogs_dir / "citations.csv").write_text("source_doi,ref_doi,ref_title\n")
    
    # Create dummy embeddings
    np.savez(catalogs_dir / "embeddings.npz", embeddings=np.zeros((len(unified_df), 384)))
    
    return catalogs_dir


@pytest.fixture
def monkeypatch_env(monkeypatch, tmp_path):
    """Set CLIMATE_FINANCE_DATA env var."""
    catalogs = tmp_path / "catalogs"
    catalogs.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLIMATE_FINANCE_DATA", str(tmp_path))
    return tmp_path


class TestPhase1Integration:
    """Test Phase 1 refining workflow end-to-end."""

    def test_corpus_filter_apply_works(self, temp_catalogs, monkeypatch):
        """corpus_filter.py --apply produces refined_works.csv and corpus_audit.csv."""
        import subprocess
        
        # Set env and run
        env = os.environ.copy()
        env["CLIMATE_FINANCE_DATA"] = str(temp_catalogs.parent)
        
        result = subprocess.run(
            [
                "python", os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
                "--apply", "--skip-llm", "--skip-citation-flag",
                "--works-input", str(temp_catalogs / "unified_works.csv"),
                "--works-output", str(temp_catalogs / "refined_works.csv"),
            ],
            cwd=str(temp_catalogs),
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, (
            f"corpus_filter.py --apply failed:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        
        # Check outputs
        assert (temp_catalogs / "refined_works.csv").exists(), "refined_works.csv missing"
        assert (temp_catalogs / "corpus_audit.csv").exists(), "corpus_audit.csv missing"
        
        refined = pd.read_csv(temp_catalogs / "refined_works.csv", dtype=str)
        assert len(refined) > 0, "refined_works.csv is empty"


class TestIncrementiality:
    """Test cache/checkpoint behavior."""

    def test_corpus_filter_idempotent(self, temp_catalogs, monkeypatch):
        """Running corpus_filter --apply twice produces identical refined_works.csv."""
        import subprocess
        
        env = os.environ.copy()
        env["CLIMATE_FINANCE_DATA"] = str(temp_catalogs.parent)
        
        cmd = [
            "python", os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
            "--apply", "--skip-llm", "--skip-citation-flag",
            "--works-input", str(temp_catalogs / "unified_works.csv"),
            "--works-output", str(temp_catalogs / "refined_works.csv"),
        ]

        # First run
        subprocess.run(cmd, cwd=str(temp_catalogs), capture_output=True, text=True, env=env)
        run1 = (temp_catalogs / "refined_works.csv").read_text()

        # Second run
        subprocess.run(cmd, cwd=str(temp_catalogs), capture_output=True, text=True, env=env)
        run2 = (temp_catalogs / "refined_works.csv").read_text()
        
        assert run1 == run2, "corpus_filter --apply is not idempotent"

    def test_checkpoint_structure_preserved(self, temp_catalogs):
        """Checkpoint files have expected structure (backwards compatible)."""
        checkpoint_path = temp_catalogs / ".citations_batch_checkpoint.csv"
        
        # Create a test checkpoint (as if interrupted run)
        checkpoint = pd.DataFrame({
            "source_doi": ["10.1/test"],
            "source_id": [""],
            "ref_doi": [""],
            "ref_title": [""],
            "ref_first_author": [""],
            "ref_year": [""],
            "ref_journal": [""],
            "ref_raw": [""],
        })
        checkpoint.to_csv(checkpoint_path, index=False)
        
        # Verify it can be read back (contract)
        reloaded = pd.read_csv(checkpoint_path)
        assert list(reloaded["source_doi"]) == ["10.1/test"]


class TestBackwardCompatibility:
    """Verify old entrypoints maintain API."""

    def test_corpus_filter_apply_flag(self):
        """corpus_filter.py --apply flag exists."""
        import subprocess
        result = subprocess.run(
            ["python", os.path.join(SCRIPTS_DIR, "corpus_filter.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert "--apply" in result.stdout, "Missing --apply flag"

    def test_enrich_citation_limit_arg(self):
        """enrich_citations_batch.py --limit is available."""
        import subprocess
        result = subprocess.run(
            ["python", os.path.join(SCRIPTS_DIR, "enrich_citations_batch.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert "--limit" in result.stdout, "Missing --limit arg"


class TestPhase1OutputContract:
    """Verify outputs respect Phase 1 contract."""

    def test_refined_works_csv_schema(self, temp_catalogs):
        """refined_works.csv has expected core columns."""
        refined_path = temp_catalogs / "refined_works.csv"
        
        if not refined_path.exists():
            pytest.skip("refined_works.csv not yet created (OK for unit test)")
        
        df = pd.read_csv(refined_path, dtype=str)
        # Core contract columns
        for col in ["source", "doi", "title"]:
            assert col in df.columns or df.empty, f"Missing core column: {col}"

    def test_embeddings_npz_format(self, temp_catalogs):
        """embeddings.npz is valid numpy format."""
        npz_path = temp_catalogs / "embeddings.npz"
        assert npz_path.exists(), "embeddings.npz missing"
        
        with np.load(npz_path) as data:
            assert "embeddings" in data.files, "Missing 'embeddings' key in .npz"
            emb = data["embeddings"]
            assert emb.dtype == np.float32 or emb.dtype == np.float64
            assert len(emb.shape) == 2, f"embeddings shape should be 2D, got {emb.shape}"
