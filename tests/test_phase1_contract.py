"""Tests for #64: Phase 1 contract — row-aligned refined_embeddings.npz
and refined_citations.csv produced by corpus_align.py.

Covers:
- shape invariant: refined_embeddings.npz rows == len(refined_works.csv)
- DOI-domain invariant: all refined_citations source_doi ∈ refined DOIs
- load_refined_embeddings() and load_refined_citations() raise on missing file
- corpus_align.py CLI: --dry-run works without writing files
- corpus_align.py: alignment is correct given synthetic fixture data
- Makefile declares corpus-align target; dvc.yaml align stage lists refined_works.csv in deps
"""

import os
import sys
import subprocess
import tempfile

import yaml

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")
DVC_YAML = os.path.join(os.path.dirname(__file__), "..", "dvc.yaml")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_refined_works(tmp_path, n=5):
    """Synthetic refined_works.csv with n rows."""
    df = pd.DataFrame({
        "doi": [f"10.1/work{i}" for i in range(n)],
        "title": [f"Work {i}" for i in range(n)],
        "source": ["openalex"] * n,
        "source_id": [f"W{i:04d}" for i in range(n)],
        "year": [2010 + i for i in range(n)],
        "cited_by_count": [i * 10 for i in range(n)],
    })
    path = tmp_path / "refined_works.csv"
    df.to_csv(path, index=False)
    return path, df


def _make_embeddings_npz(tmp_path, dois, dim=8):
    """Synthetic embeddings.npz with keys aligned to a DOI list."""
    n = len(dois)
    vectors = np.random.rand(n, dim).astype(np.float32)
    keys = np.array(dois, dtype=object)
    path = tmp_path / "embeddings.npz"
    np.savez_compressed(str(path), vectors=vectors, keys=keys)
    return path, vectors


def _make_citations_csv(tmp_path, refined_dois, extra_dois=None):
    """Synthetic citations.csv with some in-refined and some out-of-refined source DOIs."""
    rows = []
    for doi in refined_dois:
        rows.append({
            "source_doi": doi, "source_id": "", "ref_doi": "10.1/ref1",
            "ref_title": "Ref", "ref_first_author": "", "ref_year": "2005",
            "ref_journal": "Nature", "ref_raw": "",
        })
    if extra_dois:
        for doi in extra_dois:
            rows.append({
                "source_doi": doi, "source_id": "", "ref_doi": "10.1/ref2",
                "ref_title": "Ref2", "ref_first_author": "", "ref_year": "2006",
                "ref_journal": "Science", "ref_raw": "",
            })
    df = pd.DataFrame(rows)
    path = tmp_path / "citations.csv"
    df.to_csv(path, index=False)
    return path


def _env_with_data(tmp_path):
    return {**os.environ, "CLIMATE_FINANCE_DATA": str(tmp_path)}


# ---------------------------------------------------------------------------
# Unit: utils loaders raise FileNotFoundError on missing files
# ---------------------------------------------------------------------------

class TestLoaderErrors:
    def test_load_refined_embeddings_raises_when_missing(self, tmp_path):
        import utils
        orig = utils.CATALOGS_DIR
        utils.CATALOGS_DIR = str(tmp_path)
        utils.REFINED_EMBEDDINGS_PATH = os.path.join(str(tmp_path), "refined_embeddings.npz")
        try:
            with pytest.raises(FileNotFoundError, match="refined_embeddings.npz"):
                utils.load_refined_embeddings()
        finally:
            utils.CATALOGS_DIR = orig

    def test_load_refined_citations_raises_when_missing(self, tmp_path):
        import utils
        orig = utils.CATALOGS_DIR
        utils.CATALOGS_DIR = str(tmp_path)
        utils.REFINED_CITATIONS_PATH = os.path.join(str(tmp_path), "refined_citations.csv")
        try:
            with pytest.raises(FileNotFoundError, match="refined_citations.csv"):
                utils.load_refined_citations()
        finally:
            utils.CATALOGS_DIR = orig

    def test_load_refined_embeddings_returns_array(self, tmp_path):
        import utils
        # Create a valid refined_embeddings.npz
        vectors = np.eye(4, dtype=np.float32)
        npz_path = tmp_path / "refined_embeddings.npz"
        np.savez_compressed(str(npz_path), vectors=vectors)
        orig = utils.REFINED_EMBEDDINGS_PATH
        utils.REFINED_EMBEDDINGS_PATH = str(npz_path)
        try:
            arr = utils.load_refined_embeddings()
            assert arr.shape == (4, 4)
        finally:
            utils.REFINED_EMBEDDINGS_PATH = orig

    def test_load_refined_citations_returns_dataframe(self, tmp_path):
        import utils
        df = pd.DataFrame({"source_doi": ["10.1/a"], "ref_doi": ["10.1/b"]})
        csv_path = tmp_path / "refined_citations.csv"
        df.to_csv(csv_path, index=False)
        orig = utils.REFINED_CITATIONS_PATH
        utils.REFINED_CITATIONS_PATH = str(csv_path)
        try:
            result = utils.load_refined_citations()
            assert "source_doi" in result.columns
            assert len(result) == 1
        finally:
            utils.REFINED_CITATIONS_PATH = orig


# ---------------------------------------------------------------------------
# Unit: corpus_align alignment logic
# ---------------------------------------------------------------------------

class TestAlignEmbeddings:
    def test_shape_invariant(self, tmp_path):
        """aligned vectors shape[0] must equal len(refined_works.csv)."""
        from corpus_align import align_embeddings

        refined_path, refined_df = _make_refined_works(tmp_path, n=5)
        dois = [f"10.1/work{i}" for i in range(5)]
        _make_embeddings_npz(tmp_path, dois, dim=8)

        import corpus_align
        orig_emb = corpus_align.EMBEDDINGS_PATH
        corpus_align.EMBEDDINGS_PATH = str(tmp_path / "embeddings.npz")
        try:
            aligned, n_matched, n_zero = align_embeddings(refined_df)
            assert aligned.shape[0] == len(refined_df), \
                f"shape[0]={aligned.shape[0]} != {len(refined_df)}"
            assert aligned.shape[1] == 8
        finally:
            corpus_align.EMBEDDINGS_PATH = orig_emb

    def test_matched_equals_n_when_all_dois_present(self, tmp_path):
        """When all DOIs are in the embedding cache, n_matched == N."""
        from corpus_align import align_embeddings

        _, refined_df = _make_refined_works(tmp_path, n=4)
        dois = [f"10.1/work{i}" for i in range(4)]
        _make_embeddings_npz(tmp_path, dois, dim=4)

        import corpus_align
        orig = corpus_align.EMBEDDINGS_PATH
        corpus_align.EMBEDDINGS_PATH = str(tmp_path / "embeddings.npz")
        try:
            _, n_matched, n_zero = align_embeddings(refined_df)
            assert n_matched == 4
            assert n_zero == 0
        finally:
            corpus_align.EMBEDDINGS_PATH = orig

    def test_zero_fallback_when_doi_absent(self, tmp_path):
        """Works whose DOI is absent in cache → zero vector."""
        from corpus_align import align_embeddings

        _, refined_df = _make_refined_works(tmp_path, n=3)
        # Only provide embeddings for work0 and work1, not work2
        _make_embeddings_npz(tmp_path, ["10.1/work0", "10.1/work1"], dim=4)

        import corpus_align
        orig = corpus_align.EMBEDDINGS_PATH
        corpus_align.EMBEDDINGS_PATH = str(tmp_path / "embeddings.npz")
        try:
            aligned, n_matched, n_zero = align_embeddings(refined_df)
            assert n_matched == 2
            assert n_zero == 1
            # Row 2 (work2) should be all zeros
            assert np.allclose(aligned[2], 0)
        finally:
            corpus_align.EMBEDDINGS_PATH = orig

    def test_row_order_is_canonical(self, tmp_path):
        """Row i of aligned must correspond to row i of refined_works.csv."""
        from corpus_align import align_embeddings

        _, refined_df = _make_refined_works(tmp_path, n=3)
        # Put embeddings in reverse order: work2, work1, work0
        dois_rev = ["10.1/work2", "10.1/work1", "10.1/work0"]
        emb_path, vectors = _make_embeddings_npz(tmp_path, dois_rev, dim=4)
        # vectors[0] = work2, vectors[1] = work1, vectors[2] = work0

        import corpus_align
        orig = corpus_align.EMBEDDINGS_PATH
        corpus_align.EMBEDDINGS_PATH = str(emb_path)
        try:
            aligned, _, _ = align_embeddings(refined_df)
            # aligned[0] should be work0 → which is vectors[2]
            assert np.allclose(aligned[0], vectors[2])
            # aligned[1] should be work1 → which is vectors[1]
            assert np.allclose(aligned[1], vectors[1])
            # aligned[2] should be work2 → which is vectors[0]
            assert np.allclose(aligned[2], vectors[0])
        finally:
            corpus_align.EMBEDDINGS_PATH = orig


class TestAlignCitations:
    def test_domain_invariant(self, tmp_path):
        """All source_doi in refined_citations must be in refined DOI set."""
        from corpus_align import align_citations
        from utils import normalize_doi

        refined_dois = {"10.1/work0", "10.1/work1", "10.1/work2"}
        extra_dois = ["10.1/other_work"]
        cit_path = _make_citations_csv(tmp_path, list(refined_dois), extra_dois)

        filtered, total_in, n_kept = align_citations(
            refined_dois, cit_path=str(cit_path)
        )
        assert total_in == 4  # 3 in-refined + 1 extra
        assert n_kept == 3
        # All source_doi in filtered must be in refined_dois
        for doi in filtered["source_doi"]:
            assert normalize_doi(doi) in refined_dois, \
                f"{doi!r} not in refined DOI set"

    def test_extra_dois_dropped(self, tmp_path):
        """source_doi values outside the refined set must be dropped."""
        from corpus_align import align_citations

        refined_dois = {"10.1/work0"}
        extra = ["10.1/not_refined"]
        cit_path = _make_citations_csv(tmp_path, ["10.1/work0"], extra)

        filtered, total_in, n_kept = align_citations(
            refined_dois, cit_path=str(cit_path)
        )
        assert n_kept == 1
        assert total_in == 2


# ---------------------------------------------------------------------------
# Integration: corpus_align.py CLI
# ---------------------------------------------------------------------------

class TestCorpusAlignCLI:
    def test_dry_run_no_files_written(self, tmp_path):
        """--dry-run must not write any output files."""
        refined_path, _ = _make_refined_works(tmp_path, n=3)
        dois = [f"10.1/work{i}" for i in range(3)]
        _make_embeddings_npz(tmp_path, dois, dim=4)
        _make_citations_csv(tmp_path, [f"10.1/work{i}" for i in range(3)])

        env = _env_with_data(tmp_path)
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_align.py"),
             "--dry-run",
             "--refined-works", str(refined_path),
             "--embeddings", str(tmp_path / "embeddings.npz"),
             "--citations", str(tmp_path / "citations.csv"),
             "--out-embeddings", str(tmp_path / "refined_embeddings.npz"),
             "--out-citations", str(tmp_path / "refined_citations.csv"),
             ],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, result.stderr
        assert not (tmp_path / "refined_embeddings.npz").exists()
        assert not (tmp_path / "refined_citations.csv").exists()
        assert "Dry run" in result.stdout

    def test_produces_aligned_outputs(self, tmp_path):
        """Full run produces refined_embeddings.npz and refined_citations.csv."""
        n = 4
        refined_path, _ = _make_refined_works(tmp_path, n=n)
        dois = [f"10.1/work{i}" for i in range(n)]
        _make_embeddings_npz(tmp_path, dois, dim=8)
        _make_citations_csv(tmp_path, dois, extra_dois=["10.1/extra"])

        out_emb = tmp_path / "refined_embeddings.npz"
        out_cit = tmp_path / "refined_citations.csv"
        env = _env_with_data(tmp_path)

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_align.py"),
             "--refined-works", str(refined_path),
             "--embeddings", str(tmp_path / "embeddings.npz"),
             "--citations", str(tmp_path / "citations.csv"),
             "--out-embeddings", str(out_emb),
             "--out-citations", str(out_cit),
             "--run-id", "test-align-001",
             ],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, result.stderr + result.stdout

        # Shape invariant
        assert out_emb.exists()
        data = np.load(str(out_emb))
        assert data["vectors"].shape[0] == n, \
            f"Expected {n} rows, got {data['vectors'].shape[0]}"

        # Domain invariant
        assert out_cit.exists()
        cit_df = pd.read_csv(out_cit)
        from utils import normalize_doi
        refined_doi_set = {normalize_doi(f"10.1/work{i}") for i in range(n)}
        for doi in cit_df["source_doi"]:
            assert normalize_doi(doi) in refined_doi_set, f"{doi!r} not in refined set"

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_align.py"), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        assert "--run-id" in result.stdout


# ---------------------------------------------------------------------------
# Makefile contract
# ---------------------------------------------------------------------------

class TestMakefileContract:
    def _read_makefile(self):
        with open(MAKEFILE) as f:
            return f.read()

    def test_corpus_align_target_exists(self):
        import re
        mk = self._read_makefile()
        assert re.search(r"^corpus-align\s*:", mk, re.MULTILINE), \
            "corpus-align target missing from Makefile"

    def test_corpus_meta_target_includes_corpus_align(self):
        """dvc.yaml must define an align stage (corpus-align delegates to dvc repro align).

        Previously the test checked the Makefile corpus meta-target listed
        corpus-align as a prerequisite. Now DVC owns the pipeline DAG:
        the align stage is declared in dvc.yaml, and corpus-align in the
        Makefile simply calls 'dvc repro align'.
        """
        with open(DVC_YAML) as f:
            dvc = yaml.safe_load(f)
        assert "align" in dvc.get("stages", {}), \
            "align stage missing from dvc.yaml (corpus-align delegates to 'dvc repro align')"

    def test_refined_embeddings_variable_declared(self):
        import re
        mk = self._read_makefile()
        assert re.search(r"^REFINED_EMB\s*:?=", mk, re.MULTILINE), \
            "REFINED_EMB variable not declared in Makefile"

    def test_refined_citations_variable_declared(self):
        import re
        mk = self._read_makefile()
        assert re.search(r"^REFINED_CIT\s*:?=", mk, re.MULTILINE), \
            "REFINED_CIT variable not declared in Makefile"

    def test_corpus_align_checks_for_refined(self):
        """dvc.yaml align stage must declare refined_works.csv as a dependency.

        Previously the Makefile corpus-align recipe contained a fail-fast check
        for the presence of refined_works.csv. Now DVC owns the dependency graph:
        the contract is expressed in dvc.yaml deps, which DVC enforces before
        running the align stage.
        """
        with open(DVC_YAML) as f:
            dvc = yaml.safe_load(f)
        assert "align" in dvc.get("stages", {}), "align stage missing from dvc.yaml"
        deps = dvc["stages"]["align"].get("deps", [])
        dep_paths = [str(d) for d in deps]
        assert any("refined_works.csv" in p for p in dep_paths), \
            "dvc.yaml align stage must list refined_works.csv in deps"
