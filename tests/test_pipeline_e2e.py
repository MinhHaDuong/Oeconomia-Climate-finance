"""End-to-end pipeline smoke test with mini CSV fixtures (#156).

Exercises each Phase 1 script in sequence with tiny synthetic data:
  catalog_merge → enrich_dois → corpus_filter --extend → --filter → corpus_align

Runs in < 10 seconds, no network calls.
Would have caught: glob loading wrong files, missing from_* columns.
"""

import os
import subprocess
import sys
from contextlib import contextmanager

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from utils import WORKS_COLUMNS, FROM_COLS, normalize_doi


# ============================================================
# Fixture helpers
# ============================================================

@contextmanager
def _patched_merge_dirs(workspace):
    """Temporarily redirect catalog_merge and utils paths to a test workspace.

    Patches BASE_DIR and CATALOGS_DIR on both catalog_merge and utils modules,
    restoring originals on exit (even if the test raises).
    """
    import catalog_merge as cm
    import utils
    catalogs_dir = str(workspace / "data" / "catalogs")
    orig = (cm.BASE_DIR, cm.CATALOGS_DIR, utils.BASE_DIR, utils.CATALOGS_DIR)
    cm.BASE_DIR = str(workspace)
    cm.CATALOGS_DIR = catalogs_dir
    utils.BASE_DIR = str(workspace)
    utils.CATALOGS_DIR = catalogs_dir
    try:
        yield catalogs_dir
    finally:
        cm.BASE_DIR, cm.CATALOGS_DIR, utils.BASE_DIR, utils.CATALOGS_DIR = orig


def _run_merge(workspace):
    """Run catalog_merge.main() with paths redirected to workspace."""
    import catalog_merge as cm
    with _patched_merge_dirs(workspace):
        cm.main()


def _make_source_csv(path, source_name, rows):
    """Write a source catalog CSV with WORKS_COLUMNS + from_* columns."""
    for r in rows:
        r.setdefault("source", source_name)
        for col in WORKS_COLUMNS:
            r.setdefault(col, "")
        for col in FROM_COLS:
            src = col.replace("from_", "")
            r.setdefault(col, 1 if src == source_name else 0)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return df


def _make_dvc_yaml(base_dir, source_files):
    """Write a minimal dvc.yaml whose catalog_merge deps point to our fixtures.

    base_dir: the workspace root (where dvc.yaml lives, same as BASE_DIR).
    source_files: absolute paths to source CSV files.
    """
    deps = [os.path.relpath(f, base_dir) for f in source_files]
    import yaml
    dvc = {
        "stages": {
            "catalog_merge": {
                "cmd": "true",
                "deps": deps,
            }
        }
    }
    dvc_path = os.path.join(base_dir, "dvc.yaml")
    with open(dvc_path, "w") as f:
        yaml.safe_dump(dvc, f)
    return dvc_path


# ============================================================
# Shared pipeline workspace fixture
# ============================================================

@pytest.fixture
def pipeline_workspace(tmp_path):
    """Set up a mini workspace with source catalogs and config.

    Directory layout mirrors the repo:
        tmp_path/
            data/catalogs/  (source CSVs + outputs)
            config/corpus_filter.yaml
            dvc.yaml
    """
    data_dir = tmp_path / "data"
    catalogs_dir = data_dir / "catalogs"
    catalogs_dir.mkdir(parents=True)

    # --- Source catalogs ---
    # OpenAlex: 4 works (1 shares DOI with istex for dedup testing)
    openalex_rows = [
        {"source_id": "W001", "doi": "10.1/shared-doi", "title": "Climate finance mechanisms",
         "first_author": "Smith", "year": "2015", "cited_by_count": "120",
         "abstract": "Climate finance and carbon markets in developing countries",
         "journal": "Nature Climate Change", "language": "en"},
        {"source_id": "W002", "doi": "10.1/oa-only", "title": "Green bonds and climate risk",
         "first_author": "Jones", "year": "2018", "cited_by_count": "85",
         "abstract": "Green bond market growth and climate risk assessment",
         "journal": "J Finance", "language": "en"},
        {"source_id": "W003", "doi": "", "title": "Adaptation funding in Africa",
         "first_author": "Diallo", "year": "2020", "cited_by_count": "30",
         "abstract": "Climate adaptation finance flows to African nations",
         "journal": "World Development", "language": "en"},
        {"source_id": "W004", "doi": "10.1/noise-paper", "title": "Deep learning for image recognition",
         "first_author": "Zhang", "year": "2021", "cited_by_count": "5",
         "abstract": "Neural network architectures for computer vision",
         "journal": "AI Journal", "language": "en"},
    ]
    oa_path = catalogs_dir / "openalex_works.csv"
    _make_source_csv(oa_path, "openalex", openalex_rows)

    # ISTEX: 3 works (1 duplicate DOI, 1 no-DOI title match, 1 unique)
    istex_rows = [
        {"source_id": "I001", "doi": "10.1/shared-doi", "title": "Climate finance mechanisms",
         "first_author": "Smith", "year": "2015", "cited_by_count": "100",
         "abstract": "ISTEX version of climate finance paper",
         "journal": "Nature Clim Change", "language": "en"},
        {"source_id": "I002", "doi": "", "title": "Adaptation funding in Africa",
         "first_author": "Diallo", "year": "2020", "cited_by_count": "25",
         "abstract": "ISTEX duplicate by title+year",
         "journal": "World Dev", "language": "en"},
        {"source_id": "I003", "doi": "10.1/istex-unique", "title": "Carbon tax policy evaluation",
         "first_author": "Martin", "year": "2012", "cited_by_count": "200",
         "abstract": "Evaluating carbon tax policies in European nations",
         "journal": "Energy Policy", "language": "en"},
    ]
    istex_path = catalogs_dir / "istex_works.csv"
    _make_source_csv(istex_path, "istex", istex_rows)

    # Grey: 1 work with no DOI, no abstract (tests missing abstract flag)
    grey_rows = [
        {"source_id": "G001", "doi": "", "title": "UNFCCC Standing Committee report",
         "first_author": "", "year": "2014", "cited_by_count": "0",
         "abstract": "", "journal": "", "language": "en"},
    ]
    grey_path = catalogs_dir / "grey_works.csv"
    _make_source_csv(grey_path, "grey", grey_rows)

    # Empty source files (with headers) for remaining required sources
    for name in ["bibcnrs", "teaching", "scispace"]:
        empty_path = catalogs_dir / f"{name}_works.csv"
        # Write header-only CSV so pandas can parse it (no EmptyDataError)
        header_cols = WORKS_COLUMNS + FROM_COLS
        pd.DataFrame(columns=header_cols).to_csv(empty_path, index=False)

    # --- dvc.yaml (lives at workspace root, same as BASE_DIR) ---
    source_files = [
        str(oa_path), str(istex_path), str(grey_path),
        str(catalogs_dir / "bibcnrs_works.csv"),
        str(catalogs_dir / "teaching_works.csv"),
        str(catalogs_dir / "scispace_works.csv"),
    ]
    _make_dvc_yaml(str(tmp_path), source_files)

    # Note: corpus_filter subprocess reads config from the repo's config/ dir,
    # not from this workspace. Tests depend on the repo's production config
    # (which blacklists "deep learning", etc.). This is intentional — the smoke
    # test validates the real pipeline, not a synthetic config.

    return tmp_path


# ============================================================
# Stage 1: catalog_merge
# ============================================================

class TestCatalogMerge:
    def test_merge_produces_unified_works(self, pipeline_workspace):
        """catalog_merge.py reads source CSVs via dvc.yaml and writes unified_works.csv."""
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        _run_merge(ws)

        unified_path = catalogs_dir / "unified_works.csv"
        assert unified_path.exists(), "catalog_merge did not produce unified_works.csv"

        df = pd.read_csv(unified_path, dtype=str, keep_default_na=False)

        # Schema: all WORKS_COLUMNS + FROM_COLS + source_count present
        for col in WORKS_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"
        for col in FROM_COLS:
            assert col in df.columns, f"Missing from_* column: {col}"
        assert "source_count" in df.columns

        # Row count: 8 input rows → dedup should reduce
        # shared-doi (OA+ISTEX) → 1, title-match (Adaptation) → 1, rest unique = 4
        # Total: 6 unique works
        assert len(df) == 6, f"Expected 6 unified works after dedup, got {len(df)}"

        # DOI dedup: shared-doi appears once, prefers OpenAlex cited_by_count (max)
        shared = df[df["doi"].apply(normalize_doi) == "10.1/shared-doi"]
        assert len(shared) == 1, "DOI dedup failed: shared-doi should appear once"
        assert int(shared.iloc[0]["cited_by_count"]) == 120, \
            "DOI dedup should keep max cited_by_count (120 from OA, not 100 from ISTEX)"

        # Multi-source tracking: shared-doi has from_openalex=1 AND from_istex=1
        assert int(shared.iloc[0]["from_openalex"]) == 1
        assert int(shared.iloc[0]["from_istex"]) == 1
        assert int(shared.iloc[0]["source_count"]) >= 2

        # Title dedup: "Adaptation funding in Africa" (no DOI, same year) → 1 row
        adapt = df[df["title"].str.contains("Adaptation", na=False)]
        assert len(adapt) == 1, "Title+year dedup failed"

    def test_merge_does_not_load_enriched_files(self, pipeline_workspace):
        """Regression: catalog_merge must NOT glob *_works.csv — only dvc.yaml deps.

        This catches the bug where globbing loaded enriched_works.csv, extended_works.csv,
        etc., inflating the corpus from 48K to 128K.
        """
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        # Plant decoy files that a glob would pick up
        decoy = pd.DataFrame({
            "source": ["openalex"], "source_id": ["DECOY"],
            "doi": ["10.1/decoy"], "title": ["DECOY PAPER"],
            "first_author": ["Decoy"], "year": ["2099"],
            "cited_by_count": ["999"], "abstract": ["decoy"],
            **{col: [""] for col in WORKS_COLUMNS if col not in
               ["source", "source_id", "doi", "title", "first_author",
                "year", "cited_by_count", "abstract"]},
            **{col: [0] for col in FROM_COLS},
        })
        decoy.to_csv(catalogs_dir / "enriched_works.csv", index=False)
        decoy.to_csv(catalogs_dir / "extended_works.csv", index=False)

        _run_merge(ws)

        df = pd.read_csv(catalogs_dir / "unified_works.csv", dtype=str,
                         keep_default_na=False)
        assert "DECOY" not in df["source_id"].values, \
            "catalog_merge loaded enriched/extended decoy files — dvc.yaml deps not enforced"


# ============================================================
# Stage 2: enrich_dois (dry-run, no API calls)
# ============================================================

class TestEnrichDois:
    def test_no_candidates_copies_input(self, pipeline_workspace):
        """When all works have DOIs, enrich_dois copies input to output unchanged."""
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        # Create input where all rows have DOIs → 0 candidates → no API calls,
        # no cache read (avoids DVC stub files in worktrees).
        df = pd.DataFrame({
            "source_id": ["W1", "W2", "W3"],
            "doi": ["10.1/a", "10.1/b", "10.1/c"],
            "title": ["Climate finance mechanisms", "Green bonds", "Carbon tax"],
            "year": ["2020", "2021", "2019"],
            "from_openalex": [1, 1, 1],
            "source_count": [1, 1, 1],
            "cited_by_count": [10, 20, 30],
        })
        input_path = catalogs_dir / "enrich_input.csv"
        df.to_csv(input_path, index=False)
        output_path = catalogs_dir / "enrich_output.csv"

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "enrich_dois.py"),
             "--works-input", str(input_path),
             "--works-output", str(output_path)],
            capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, \
            f"enrich_dois failed:\n{result.stdout}\n{result.stderr}"
        assert output_path.exists()
        out_df = pd.read_csv(output_path)
        assert len(out_df) == 3, "Row count should be preserved"
        # All DOIs preserved
        assert set(out_df["doi"]) == {"10.1/a", "10.1/b", "10.1/c"}

    def test_accepts_cli_args(self):
        """enrich_dois accepts --works-input, --works-output, --dry-run, --limit."""
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "enrich_dois.py"), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        for flag in ["--works-input", "--works-output", "--dry-run", "--limit"]:
            assert flag in result.stdout, f"enrich_dois should accept {flag}"

    def test_load_cache_handles_empty_file(self, tmp_path):
        """load_cache() returns {} when cache file is empty (DVC stub)."""
        import enrich_dois
        orig_cache = enrich_dois.CACHE_FILE
        try:
            empty_file = tmp_path / "doi_resolved.csv"
            empty_file.write_text("")
            enrich_dois.CACHE_FILE = str(empty_file)
            assert enrich_dois.load_cache() == {}
        finally:
            enrich_dois.CACHE_FILE = orig_cache


# ============================================================
# Stage 3: corpus_filter --extend
# ============================================================

class TestCorpusFilterExtend:
    def test_extend_preserves_all_rows(self, pipeline_workspace):
        """--extend adds flag columns without removing any rows."""
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        _run_merge(ws)

        unified_path = catalogs_dir / "unified_works.csv"
        extended_path = catalogs_dir / "extended_works.csv"
        n_input = len(pd.read_csv(unified_path))

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--extend", "--cheap",
             "--works-input", str(unified_path),
             "--works-output", str(extended_path)],
            capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, \
            f"corpus_filter --extend failed:\n{result.stdout}\n{result.stderr}"
        assert extended_path.exists()

        ext_df = pd.read_csv(extended_path)
        assert len(ext_df) == n_input, \
            f"--extend changed row count: {n_input} → {len(ext_df)}"

        # Flag columns added
        for col in ["missing_metadata", "no_abstract_irrelevant", "title_blacklist",
                     "protected", "protect_reason", "action"]:
            assert col in ext_df.columns, f"Missing column in extended output: {col}"

        # from_* columns preserved (regression: these were lost in early versions)
        for col in FROM_COLS:
            assert col in ext_df.columns, f"Missing from_* column: {col}"

    def test_extend_flags_noise(self, pipeline_workspace):
        """--extend flags the 'deep learning' paper via title_blacklist."""
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        _run_merge(ws)

        unified_path = catalogs_dir / "unified_works.csv"
        extended_path = catalogs_dir / "extended_works.csv"

        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--extend", "--cheap",
             "--works-input", str(unified_path),
             "--works-output", str(extended_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        ext_df = pd.read_csv(extended_path)
        noise = ext_df[ext_df["title"].str.contains("Deep learning", case=False, na=False)]
        assert len(noise) == 1, "Expected exactly 1 noise paper"
        assert noise.iloc[0]["title_blacklist"] == True, \
            "Deep learning paper should be flagged by title_blacklist"


# ============================================================
# Stage 4: corpus_filter --filter
# ============================================================

class TestCorpusFilterApply:
    def test_filter_removes_flagged(self, pipeline_workspace):
        """--filter removes flagged non-protected papers and produces audit."""
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        _run_merge(ws)

        unified_path = catalogs_dir / "unified_works.csv"
        extended_path = catalogs_dir / "extended_works.csv"
        refined_path = catalogs_dir / "refined_works.csv"
        audit_path = catalogs_dir / "corpus_audit.csv"

        # Extend
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--extend", "--cheap",
             "--works-input", str(unified_path),
             "--works-output", str(extended_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

        n_extended = len(pd.read_csv(extended_path))

        # Filter
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--filter",
             "--works-input", str(extended_path),
             "--works-output", str(refined_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, \
            f"corpus_filter --filter failed:\n{result.stdout}\n{result.stderr}"
        assert refined_path.exists()

        refined_df = pd.read_csv(refined_path)
        assert len(refined_df) < n_extended, \
            f"Filter did not remove any rows: {n_extended} → {len(refined_df)}"
        assert len(refined_df) > 0, "Filter removed ALL rows"

        # The noise paper ("Deep learning") should be gone
        assert not refined_df["title"].str.contains(
            "Deep learning", case=False, na=False).any(), \
            "Noise paper should have been removed by filter"

        # Audit trail produced
        assert audit_path.exists(), "corpus_audit.csv not produced"
        audit_df = pd.read_csv(audit_path)
        assert "action" in audit_df.columns
        actions = set(audit_df["action"].dropna())
        assert "keep" in actions
        assert "remove" in actions

        # No flag columns leak into refined output
        flag_cols = ["missing_metadata", "no_abstract_irrelevant", "title_blacklist",
                     "citation_isolated_old", "semantic_outlier", "llm_irrelevant"]
        for col in flag_cols:
            assert col not in refined_df.columns, \
                f"Flag column {col} should not be in refined_works.csv"


# ============================================================
# Stage 5: corpus_align
# ============================================================

class TestCorpusAlign:
    def test_align_produces_contract_outputs(self, pipeline_workspace):
        """corpus_align aligns embeddings and citations to refined_works.csv."""
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        _run_merge(ws)

        unified_path = catalogs_dir / "unified_works.csv"
        extended_path = catalogs_dir / "extended_works.csv"
        refined_path = catalogs_dir / "refined_works.csv"

        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--extend", "--cheap",
             "--works-input", str(unified_path),
             "--works-output", str(extended_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--filter",
             "--works-input", str(extended_path),
             "--works-output", str(refined_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

        refined_df = pd.read_csv(refined_path, dtype=str, keep_default_na=False)
        n_refined = len(refined_df)
        assert n_refined > 0, "No refined works to align"

        # Create synthetic embeddings keyed by DOI
        refined_dois = [normalize_doi(d) for d in refined_df["doi"] if normalize_doi(d)]
        all_keys = refined_dois + ["10.1/extra-not-in-refined"]
        n_emb = len(all_keys)
        vectors = np.random.rand(n_emb, 16).astype(np.float32)
        emb_path = catalogs_dir / "embeddings.npz"
        np.savez_compressed(str(emb_path), vectors=vectors,
                            keys=np.array(all_keys, dtype=object))

        # Create synthetic citations (some in refined, some not)
        cit_rows = []
        for doi in refined_dois[:3]:
            cit_rows.append({
                "source_doi": doi, "source_id": "", "ref_doi": "10.1/ref1",
                "ref_title": "Ref", "ref_first_author": "A", "ref_year": "2000",
                "ref_journal": "J", "ref_raw": "",
            })
        # Add out-of-refined citation
        cit_rows.append({
            "source_doi": "10.1/not-in-refined", "source_id": "", "ref_doi": "10.1/ref2",
            "ref_title": "Ref2", "ref_first_author": "B", "ref_year": "2001",
            "ref_journal": "J2", "ref_raw": "",
        })
        cit_df = pd.DataFrame(cit_rows)
        cit_path = catalogs_dir / "citations.csv"
        cit_df.to_csv(cit_path, index=False)

        # Run corpus_align
        out_emb = catalogs_dir / "refined_embeddings.npz"
        out_cit = catalogs_dir / "refined_citations.csv"

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_align.py"),
             "--refined-works", str(refined_path),
             "--embeddings", str(emb_path),
             "--citations", str(cit_path),
             "--out-embeddings", str(out_emb),
             "--out-citations", str(out_cit),
             "--run-id", "smoke-test"],
            capture_output=True, text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, \
            f"corpus_align failed:\n{result.stdout}\n{result.stderr}"

        # Shape invariant: embedding rows == refined rows
        assert out_emb.exists()
        emb_data = np.load(str(out_emb))
        assert emb_data["vectors"].shape[0] == n_refined, \
            f"Embedding shape[0]={emb_data['vectors'].shape[0]} != {n_refined} refined rows"

        # Domain invariant: all citation source_doi in refined DOI set
        assert out_cit.exists()
        refined_cit = pd.read_csv(out_cit)
        refined_doi_set = {normalize_doi(d) for d in refined_df["doi"]
                           if normalize_doi(d)}
        for doi in refined_cit["source_doi"]:
            assert normalize_doi(doi) in refined_doi_set, \
                f"Citation source_doi {doi!r} not in refined set"

        # Out-of-refined citation dropped
        assert not refined_cit["source_doi"].apply(normalize_doi).isin(
            {"10.1/not-in-refined"}).any(), \
            "Citation from non-refined DOI should have been dropped"


# ============================================================
# Full pipeline sequence test
# ============================================================

class TestFullPipeline:
    def test_end_to_end_sequence(self, pipeline_workspace):
        """Run all 5 stages in sequence and verify final output shapes."""
        ws = pipeline_workspace
        catalogs_dir = ws / "data" / "catalogs"

        # Stage 1: merge
        _run_merge(ws)

        unified = pd.read_csv(catalogs_dir / "unified_works.csv")
        assert len(unified) >= 4, "Merge should produce at least 4 works"

        # Stage 2: enrich — copy unified → enriched (enrich_dois tested separately;
        # subprocess can't override CATALOGS_DIR for cache path, and DVC stubs
        # in worktrees cause EmptyDataError).
        enriched_path = catalogs_dir / "enriched_works.csv"
        import shutil
        shutil.copy(catalogs_dir / "unified_works.csv", enriched_path)
        enriched = pd.read_csv(enriched_path)
        assert len(enriched) == len(unified), "Enrich should preserve row count"

        # Stage 3: extend
        extended_path = catalogs_dir / "extended_works.csv"
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--extend", "--cheap",
             "--works-input", str(enriched_path),
             "--works-output", str(extended_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"Extend failed:\n{r.stdout}\n{r.stderr}"
        extended = pd.read_csv(extended_path)
        assert len(extended) == len(enriched), "Extend should preserve row count"

        # Stage 4: filter
        refined_path = catalogs_dir / "refined_works.csv"
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_filter.py"),
             "--filter",
             "--works-input", str(extended_path),
             "--works-output", str(refined_path)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"Filter failed:\n{r.stdout}\n{r.stderr}"
        refined = pd.read_csv(refined_path)
        assert 0 < len(refined) <= len(extended), "Filter should reduce rows"

        # Stage 5: align (with synthetic embeddings + citations)
        refined_df = pd.read_csv(refined_path, dtype=str, keep_default_na=False)
        refined_dois = [normalize_doi(d) for d in refined_df["doi"]
                        if normalize_doi(d)]
        keys = refined_dois if refined_dois else ["dummy"]
        vectors = np.random.rand(len(keys), 8).astype(np.float32)
        emb_path = catalogs_dir / "embeddings.npz"
        np.savez_compressed(str(emb_path), vectors=vectors,
                            keys=np.array(keys, dtype=object))

        cit_rows = [{"source_doi": d, "source_id": "", "ref_doi": "10.1/ref",
                      "ref_title": "R", "ref_first_author": "", "ref_year": "2000",
                      "ref_journal": "", "ref_raw": ""}
                     for d in refined_dois[:2]]
        if cit_rows:
            pd.DataFrame(cit_rows).to_csv(catalogs_dir / "citations.csv", index=False)
        else:
            pd.DataFrame(columns=["source_doi", "source_id", "ref_doi",
                                   "ref_title", "ref_first_author", "ref_year",
                                   "ref_journal", "ref_raw"]).to_csv(
                catalogs_dir / "citations.csv", index=False)

        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "corpus_align.py"),
             "--refined-works", str(refined_path),
             "--embeddings", str(emb_path),
             "--citations", str(catalogs_dir / "citations.csv"),
             "--out-embeddings", str(catalogs_dir / "refined_embeddings.npz"),
             "--out-citations", str(catalogs_dir / "refined_citations.csv"),
             "--run-id", "e2e-smoke"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"Align failed:\n{r.stdout}\n{r.stderr}"

        # Final invariants
        emb_data = np.load(str(catalogs_dir / "refined_embeddings.npz"))
        assert emb_data["vectors"].shape[0] == len(refined), \
            "Final embedding shape mismatch"

        cit_out = pd.read_csv(catalogs_dir / "refined_citations.csv")
        doi_set = {normalize_doi(d) for d in refined_df["doi"] if normalize_doi(d)}
        for d in cit_out["source_doi"]:
            assert normalize_doi(d) in doi_set, f"Leaked citation: {d}"
