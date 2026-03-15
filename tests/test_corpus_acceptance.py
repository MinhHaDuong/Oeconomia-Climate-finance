"""Corpus acceptance test — publication-quality gate.

Run:  uv run pytest tests/test_corpus_acceptance.py -v --tb=long

If ALL tests pass, the corpus is ready for Phase 2 analysis and publication.
If ANY test fails, the failure message includes:
  - Probable cause
  - How to fix
  - Estimated time
  - Risk if left unfixed
"""

import os
import sys
import textwrap

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from refine_flags import _has_safe_words, _load_config
from utils import (
    CATALOGS_DIR,
    EMBEDDINGS_PATH,
    FROM_COLS,
    REFINED_CITATIONS_PATH,
    REFINED_EMBEDDINGS_PATH,
    WORKS_COLUMNS,
    normalize_doi,
)


# ── Paths ────────────────────────────────────────────────────

REFINED_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
ENRICHED_PATH = os.path.join(CATALOGS_DIR, "enriched_works.csv")
AUDIT_PATH = os.path.join(CATALOGS_DIR, "corpus_audit.csv")
CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
CACHE_PATH = os.path.join(CATALOGS_DIR, "llm_relevance_cache.csv")


# ── Expected ranges (update when pipeline changes) ──────────

CORPUS_MIN = 20_000   # hard floor: fewer means catastrophic bug
CORPUS_MAX = 40_000   # hard ceiling: more means filter not running
CORE_MIN = 1_500      # cited_by_count >= 50
CORE_MAX = 5_000
FLAG_RATE_MAX = 0.30   # at most 30% of enriched corpus should be flagged
PROTECTION_MIN = 5_000 # at least this many papers protected
ENGLISH_PCT_MIN = 75.0
YEAR_MIN = 1960  # foundational works predate "climate finance"
YEAR_MAX = 2026
REQUIRED_COLUMNS = [
    "source", "source_id", "doi", "title", "year",
    "cited_by_count", "abstract",
]


# ── Helpers ──────────────────────────────────────────────────

def _diagnosis(probable_cause, fix, time_estimate, risk):
    """Format a diagnostic message for test failures."""
    return textwrap.dedent(f"""

    PROBABLE CAUSE: {probable_cause}
    FIX: {fix}
    TIME: {time_estimate}
    RISK IF UNFIXED: {risk}
    """)


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def refined():
    if not os.path.isfile(REFINED_PATH):
        pytest.skip(f"refined_works.csv not found at {REFINED_PATH}")
    return pd.read_csv(REFINED_PATH, low_memory=False)


@pytest.fixture(scope="module")
def enriched():
    if not os.path.isfile(ENRICHED_PATH):
        pytest.skip(f"enriched_works.csv not found at {ENRICHED_PATH}")
    return pd.read_csv(ENRICHED_PATH, low_memory=False)


@pytest.fixture(scope="module")
def audit():
    if not os.path.isfile(AUDIT_PATH):
        pytest.skip(f"corpus_audit.csv not found at {AUDIT_PATH}")
    return pd.read_csv(AUDIT_PATH, low_memory=False)


@pytest.fixture(scope="module")
def reranker_cache():
    if not os.path.isfile(CACHE_PATH):
        pytest.skip(f"llm_relevance_cache.csv not found at {CACHE_PATH}")
    return pd.read_csv(CACHE_PATH)


@pytest.fixture(scope="module")
def refine_config():
    return _load_config()


QC_CITATIONS_REPORT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "content", "tables", "qc_citations_report.json"
)


# ═══════════════════════════════════════════════════════════
# 1. FILE EXISTENCE — do all Phase 1 outputs exist?
# ═══════════════════════════════════════════════════════════

class TestFileExistence:
    """All Phase 1 output files must be present on disk."""

    def test_refined_works_exists(self):
        assert os.path.isfile(REFINED_PATH), \
            f"refined_works.csv missing at {REFINED_PATH}" + _diagnosis(
                "corpus_refine.py --apply was not run, or ran on a different machine",
                "uv run python scripts/corpus_refine.py --apply",
                "5-30 min (depends on reranker cache)",
                "No corpus for Phase 2 — all analysis blocked",
            )

    def test_corpus_audit_exists(self):
        assert os.path.isfile(AUDIT_PATH), \
            f"corpus_audit.csv missing at {AUDIT_PATH}" + _diagnosis(
                "corpus_refine.py did not write the audit trail",
                "uv run python scripts/corpus_refine.py --apply",
                "5-30 min",
                "No provenance for removed papers — irreproducible",
            )

    def test_embeddings_exist(self):
        assert os.path.isfile(EMBEDDINGS_PATH), \
            f"embeddings.npz missing at {EMBEDDINGS_PATH}" + _diagnosis(
                "enrich_embeddings.py was not run",
                "uv run python scripts/enrich_embeddings.py",
                "~16 min on CPU for full corpus",
                "No embedding-based analysis (bimodality, PCA, outliers)",
            )

    def test_citations_exist(self):
        assert os.path.isfile(CITATIONS_PATH), \
            f"citations.csv missing at {CITATIONS_PATH}" + _diagnosis(
                "Citation enrichment was not run",
                "make citations",
                "~2 hours (API rate-limited)",
                "No citation graph, co-citation analysis, or genealogy",
            )

    def test_reranker_cache_exists(self):
        assert os.path.isfile(CACHE_PATH), \
            f"llm_relevance_cache.csv missing at {CACHE_PATH}" + _diagnosis(
                "Reranker scoring was not run (Flag 6)",
                "uv run python scripts/corpus_refine.py --apply (with reranker backend)",
                "~10 min on GPU, ~2 hours on CPU",
                "Flag 6 will score from scratch on next run — slow but not broken",
            )


# ═══════════════════════════════════════════════════════════
# 2. CORPUS SIZE — plausible range guards
# ═══════════════════════════════════════════════════════════

class TestCorpusSize:
    """Corpus size must fall within expected ranges."""

    def test_row_count_in_range(self, refined):
        n = len(refined)
        assert CORPUS_MIN <= n <= CORPUS_MAX, \
            f"Corpus has {n:,} papers (expected {CORPUS_MIN:,}–{CORPUS_MAX:,})" + _diagnosis(
                f"{'Filter too aggressive' if n < CORPUS_MIN else 'Filter not running or new sources added'}",
                "Review corpus_refine.py flags and thresholds; compare corpus_audit.csv",
                "1-2 hours to diagnose",
                "Wrong corpus size invalidates all quantitative claims in manuscript",
            )

    def test_core_count_in_range(self, refined):
        core = refined[refined["cited_by_count"] >= 50]
        n = len(core)
        assert CORE_MIN <= n <= CORE_MAX, \
            f"Core has {n:,} papers (expected {CORE_MIN:,}–{CORE_MAX:,})" + _diagnosis(
                "cited_by_count data stale or threshold changed",
                "Re-run enrich_citations_openalex.py to update citation counts",
                "~30 min",
                "Core subset figures (bimodality, PCA) use wrong population",
            )

    def test_nonzero_per_period(self, refined):
        """Each historical period must have papers."""
        year = refined["year"].dropna()
        for label, lo, hi in [("Before (1990-2006)", 1990, 2006),
                               ("Crystallization (2007-2014)", 2007, 2014),
                               ("Established (2015-2025)", 2015, 2025)]:
            n = ((year >= lo) & (year <= hi)).sum()
            assert n > 100, \
                f"Period '{label}' has only {n} papers (expected > 100)" + _diagnosis(
                    "Year filtering or enrichment failure",
                    "Check enriched_works.csv year distribution",
                    "30 min",
                    "Periodization claims unsupported by data",
                )


# ═══════════════════════════════════════════════════════════
# 3. SCHEMA — required columns and types
# ═══════════════════════════════════════════════════════════

class TestSchema:
    """refined_works.csv must have the expected schema."""

    def test_required_columns_present(self, refined):
        missing = [c for c in REQUIRED_COLUMNS if c not in refined.columns]
        assert not missing, \
            f"Missing columns: {missing}" + _diagnosis(
                "Pipeline script changed column names or order",
                "Check corpus_refine.py and enriched_works.csv schema",
                "15 min",
                "Phase 2 scripts will crash on missing columns",
            )

    def test_year_range(self, refined):
        year = refined["year"].dropna()
        assert year.min() >= YEAR_MIN, \
            f"Earliest year {year.min()} < {YEAR_MIN}" + _diagnosis(
                "Stale papers from pre-1990 not filtered",
                "Add year filter to corpus_refine.py",
                "15 min",
                "Minor — pre-1990 papers may dilute analysis",
            )
        assert year.max() <= YEAR_MAX, \
            f"Latest year {year.max()} > {YEAR_MAX}" + _diagnosis(
                "Future-dated papers from preprints or data errors",
                "Filter year > current year in enrichment",
                "15 min",
                "Minor — a few future-dated papers won't affect analysis",
            )

    def test_no_duplicate_dois(self, refined):
        dois = refined["doi"].dropna()
        doi_norm = dois.apply(normalize_doi)
        dupes = doi_norm[doi_norm.duplicated() & (doi_norm != "")]
        n_dupes = len(dupes)
        assert n_dupes == 0, \
            f"{n_dupes} duplicate DOIs found. Examples: {dupes.head(5).tolist()}" + _diagnosis(
                "Deduplication in catalog_merge.py missed some entries",
                "Check merge priority and normalize_doi logic",
                "1 hour",
                "Double-counting inflates publication counts and distorts analysis",
            )

    def test_title_not_null(self, refined):
        null_titles = refined["title"].isna().sum()
        pct = 100 * null_titles / len(refined)
        assert pct < 1.0, \
            f"{null_titles} papers ({pct:.1f}%) have null titles" + _diagnosis(
                "Flag 1 (missing_metadata) not catching title-less papers",
                "Review flag_missing_metadata in refine_flags.py",
                "15 min",
                "Papers without titles cannot be identified by readers",
            )


# ═══════════════════════════════════════════════════════════
# 4. AUDIT TRAIL — every paper accounted for
# ═══════════════════════════════════════════════════════════

class TestAuditTrail:
    """corpus_audit.csv must account for every enriched paper."""

    def test_audit_covers_enriched(self, audit, enriched):
        assert len(audit) == len(enriched), \
            f"Audit has {len(audit):,} rows but enriched has {len(enriched):,}" + _diagnosis(
                "corpus_refine.py crashed mid-run or was interrupted",
                "Re-run: uv run python scripts/corpus_refine.py --apply",
                "5-30 min",
                "Cannot verify which papers were removed or why",
            )

    def test_audit_has_action_column(self, audit):
        assert "action" in audit.columns, \
            "'action' column missing from audit" + _diagnosis(
                "corpus_refine.py schema changed",
                "Check corpus_refine.py audit output logic",
                "15 min",
                "Audit trail is useless without keep/remove decisions",
            )

    def test_audit_actions_valid(self, audit):
        valid = {"keep", "remove"}
        actions = set(audit["action"].dropna().unique())
        invalid = actions - valid
        assert not invalid, \
            f"Invalid audit actions: {invalid}" + _diagnosis(
                "New action type introduced without updating test",
                "Update valid set or fix corpus_refine.py",
                "5 min",
                "Audit analysis may miscount kept/removed papers",
            )

    def test_audit_keep_matches_refined(self, audit, refined):
        n_keep = (audit["action"] == "keep").sum()
        assert n_keep == len(refined), \
            f"Audit says {n_keep:,} kept but refined has {len(refined):,}" + _diagnosis(
                "Mismatch between audit and actual filtering",
                "Re-run corpus_refine.py --apply from clean state",
                "5-30 min",
                "Audit trail disagrees with actual corpus — irreproducible",
            )


# ═══════════════════════════════════════════════════════════
# 5. FLAG SANITY — flags are plausible, not pathological
# ═══════════════════════════════════════════════════════════

class TestFlagSanity:
    """Flags should remove a reasonable fraction, not everything or nothing."""

    def test_flag_rate_not_excessive(self, audit, enriched):
        n_flagged = (audit["action"] == "remove").sum()
        rate = n_flagged / len(enriched)
        assert rate <= FLAG_RATE_MAX, \
            f"Flag rate {rate:.1%} exceeds {FLAG_RATE_MAX:.0%} " \
            f"({n_flagged:,} of {len(enriched):,})" + _diagnosis(
                "Reranker threshold too aggressive or new flags over-triggering",
                "Review threshold in corpus_refine.yaml; inspect corpus_audit.csv",
                "1-2 hours",
                "Corpus too small — quantitative claims become unreliable",
            )

    def test_flag_rate_nonzero(self, audit, enriched):
        n_flagged = (audit["action"] == "remove").sum()
        assert n_flagged > 100, \
            f"Only {n_flagged} papers flagged — filter may not be running" + _diagnosis(
                "All flags disabled or reranker cache empty",
                "Check config/corpus_refine.yaml backend and flags",
                "30 min",
                "Corpus contains noise — irrelevant papers dilute analysis",
            )

    def test_each_flag_present(self, audit):
        """Each flag type should catch at least one paper."""
        expected_flags = {
            "missing_metadata", "no_abstract_irrelevant",
            "title_blacklist", "citation_isolated_old", "llm_irrelevant",
        }
        flags_col = audit["flags"].dropna()
        observed = set()
        for cell in flags_col:
            for flag in str(cell).split("|"):
                # Strip sub-type suffixes (e.g., "missing_metadata:author" → "missing_metadata")
                base = flag.strip().split(":")[0]
                observed.add(base)
        observed.discard("")
        observed.discard("nan")
        missing_flags = expected_flags - observed
        assert not missing_flags, \
            f"Flags never triggered: {missing_flags}" + _diagnosis(
                "Flag function disabled, data changed, or config key missing",
                "Run corpus_refine.py in dry-run mode and check flag breakdown",
                "15 min",
                "Silent filter failure — some noise categories not caught",
            )

    def test_protection_count(self, audit):
        n_protected = audit["protected"].sum() if "protected" in audit.columns else 0
        assert n_protected >= PROTECTION_MIN, \
            f"Only {n_protected:,} protected papers (expected >= {PROTECTION_MIN:,})" + _diagnosis(
                "Protection thresholds too high or cited_by_count data stale",
                "Check protection config and citation count enrichment",
                "30 min",
                "Important papers may have been removed",
            )


# ═══════════════════════════════════════════════════════════
# 6. RERANKER CACHE — completeness and score distribution
# ═══════════════════════════════════════════════════════════

class TestRerankerCache:
    """Reranker scores should be complete and well-distributed."""

    def test_cache_has_scores(self, reranker_cache):
        assert "score" in reranker_cache.columns, \
            "Cache missing 'score' column" + _diagnosis(
                "Old LLM-only cache format without continuous scores",
                "Re-run corpus_refine.py with backend: reranker",
                "~10 min on GPU",
                "No threshold tuning possible without continuous scores",
            )

    def test_cache_size_sufficient(self, reranker_cache, refined):
        # At least 50% of refined papers should have scores
        n_with_doi = refined["doi"].dropna().nunique()
        n_cached = len(reranker_cache)
        coverage = n_cached / n_with_doi if n_with_doi > 0 else 0
        assert coverage > 0.50, \
            f"Reranker cache has {n_cached:,} entries for {n_with_doi:,} DOIs " \
            f"({coverage:.0%} coverage)" + _diagnosis(
                "Scoring was interrupted (reranker_max_batches > 0?)",
                "Set reranker_max_batches: 0 and re-run on GPU",
                "~10 min on GPU, ~2 hours on CPU",
                "Uncached papers scored at each run — slow and wastes compute",
            )

    def test_score_distribution_reasonable(self, reranker_cache):
        scores = reranker_cache["score"].dropna()
        assert len(scores) > 100, "Too few scores for distribution check"
        # Scores should not all be identical (degenerate model)
        assert scores.std() > 0.001, \
            f"Score std = {scores.std():.6f} — degenerate distribution" + _diagnosis(
                "Model not loaded correctly or all inputs identical",
                "Re-run calibrate_reranker.py; check model download",
                "30 min",
                "Flag 6 is non-functional — no relevance filtering",
            )
        # Median should be low (most papers get near-zero scores)
        assert scores.median() < 0.1, \
            f"Median score = {scores.median():.4f} — expected < 0.1" + _diagnosis(
                "Query may be too generic, matching everything",
                "Re-run calibrate_reranker.py with query optimization",
                "~1 hour",
                "Flag 6 underfiring — irrelevant papers not caught",
            )


# ═══════════════════════════════════════════════════════════
# 7. EMBEDDINGS — alignment with refined corpus
# ═══════════════════════════════════════════════════════════

class TestEmbeddings:
    """Embeddings must cover the refined corpus."""

    def test_embedding_count(self, refined):
        if not os.path.isfile(EMBEDDINGS_PATH):
            pytest.skip("embeddings.npz not found")
        data = np.load(EMBEDDINGS_PATH)
        n_emb = data["vectors"].shape[0]
        n_refined = len(refined)
        # Embeddings are from the enriched corpus (pre-filtering),
        # so n_emb >= n_refined is expected
        assert n_emb >= n_refined * 0.80, \
            f"Only {n_emb:,} embeddings for {n_refined:,} refined papers " \
            f"({100*n_emb/n_refined:.0f}% coverage)" + _diagnosis(
                "Embedding generation ran on a smaller corpus version",
                "uv run python scripts/enrich_embeddings.py (incremental)",
                "~5 min for delta",
                "Embedding-based analyses (bimodality, PCA) use wrong subset",
            )

    def test_embedding_dimensions(self):
        if not os.path.isfile(EMBEDDINGS_PATH):
            pytest.skip("embeddings.npz not found")
        data = np.load(EMBEDDINGS_PATH)
        dim = data["vectors"].shape[1]
        assert dim == 384, \
            f"Embedding dimension = {dim}, expected 384 (MiniLM-L12)" + _diagnosis(
                "Different model used for embeddings",
                "Delete embeddings.npz and re-run enrich_embeddings.py",
                "~16 min",
                "All embedding-based analysis invalid (wrong vector space)",
            )

    def test_no_all_zero_rows(self):
        """Papers with embeddings should not have all-zero vectors."""
        if not os.path.isfile(EMBEDDINGS_PATH):
            pytest.skip("embeddings.npz not found")
        data = np.load(EMBEDDINGS_PATH)
        vectors = data["vectors"]
        zero_rows = np.all(vectors == 0, axis=1).sum()
        pct = 100 * zero_rows / vectors.shape[0]
        assert pct < 5.0, \
            f"{zero_rows:,} all-zero embedding rows ({pct:.1f}%)" + _diagnosis(
                "Papers with empty abstracts encoded as zero vectors",
                "Check abstract enrichment coverage",
                "30 min to diagnose",
                "Zero vectors cluster at origin, distorting centroid and outlier detection",
            )


# ═══════════════════════════════════════════════════════════
# 8. CORPUS ALIGN — refined_embeddings.npz and refined_citations.csv
#    must be present, fresh, and row-aligned with refined_works.csv
# ═══════════════════════════════════════════════════════════

class TestCorpusAlign:
    """refined_embeddings.npz and refined_citations.csv must exist, be fresh,
    and satisfy the Phase 1→2 contract invariants.

    Failures here mean: run  uv run python scripts/corpus_align.py
    """

    def test_refined_embeddings_exist(self):
        assert os.path.isfile(REFINED_EMBEDDINGS_PATH), \
            f"refined_embeddings.npz missing at {REFINED_EMBEDDINGS_PATH}" + _diagnosis(
                "corpus_align.py was not run after corpus_refine.py",
                "uv run python scripts/corpus_align.py",
                "~2 min",
                "Phase 2 scripts will crash or use the wrong (unaligned) embeddings",
            )

    def test_refined_citations_exist(self):
        assert os.path.isfile(REFINED_CITATIONS_PATH), \
            f"refined_citations.csv missing at {REFINED_CITATIONS_PATH}" + _diagnosis(
                "corpus_align.py was not run after corpus_refine.py",
                "uv run python scripts/corpus_align.py",
                "~2 min",
                "Phase 2 citation/co-citation scripts will crash",
            )

    def test_refined_embeddings_row_count(self, refined):
        """Exact 1:1 alignment: one embedding per refined_works.csv row."""
        if not os.path.isfile(REFINED_EMBEDDINGS_PATH):
            pytest.skip("refined_embeddings.npz not found")
        n_emb = np.load(REFINED_EMBEDDINGS_PATH)["vectors"].shape[0]
        n_refined = len(refined)
        assert n_emb == n_refined, \
            f"refined_embeddings.npz has {n_emb:,} rows but refined_works.csv has {n_refined:,}" + _diagnosis(
                "corpus_align.py was run against a different version of refined_works.csv",
                "uv run python scripts/corpus_align.py",
                "~2 min",
                "Row misalignment: embedding[i] no longer corresponds to refined_works row i",
            )

    def test_refined_embeddings_freshness(self):
        """refined_embeddings.npz must not be older than refined_works.csv."""
        if not os.path.isfile(REFINED_EMBEDDINGS_PATH):
            pytest.skip("refined_embeddings.npz not found")
        emb_mtime = os.path.getmtime(REFINED_EMBEDDINGS_PATH)
        refined_mtime = os.path.getmtime(REFINED_PATH)
        assert emb_mtime >= refined_mtime, \
            "refined_embeddings.npz is older than refined_works.csv" + _diagnosis(
                "refined_works.csv was regenerated but corpus_align.py was not re-run",
                "uv run python scripts/corpus_align.py",
                "~2 min",
                "Stale alignment: embeddings no longer match current corpus rows",
            )

    def test_refined_citations_freshness(self):
        """refined_citations.csv must not be older than refined_works.csv."""
        if not os.path.isfile(REFINED_CITATIONS_PATH):
            pytest.skip("refined_citations.csv not found")
        cit_mtime = os.path.getmtime(REFINED_CITATIONS_PATH)
        refined_mtime = os.path.getmtime(REFINED_PATH)
        assert cit_mtime >= refined_mtime, \
            "refined_citations.csv is older than refined_works.csv" + _diagnosis(
                "refined_works.csv was regenerated but corpus_align.py was not re-run",
                "uv run python scripts/corpus_align.py",
                "~2 min",
                "Stale alignment: citation graph may include removed papers",
            )

    def test_refined_citations_source_dois_in_corpus(self, refined):
        """All source_doi values in refined_citations.csv must be in refined_works."""
        if not os.path.isfile(REFINED_CITATIONS_PATH):
            pytest.skip("refined_citations.csv not found")
        refined_dois = set(
            normalize_doi(d) for d in refined["doi"].dropna()
            if normalize_doi(d) not in ("", "nan", "none")
        )
        cit_header = pd.read_csv(REFINED_CITATIONS_PATH, nrows=0).columns.tolist()
        if "source_doi" not in cit_header:
            pytest.skip("source_doi column missing from refined_citations.csv")
        # Sample check: read first 50k rows to keep test fast
        cit_sample = pd.read_csv(REFINED_CITATIONS_PATH, usecols=["source_doi"],
                                  nrows=50_000, low_memory=False)
        norm_sources = cit_sample["source_doi"].dropna().apply(normalize_doi)
        strays = norm_sources[~norm_sources.isin(refined_dois) &
                              (norm_sources != "") & (norm_sources != "nan")]
        n_strays = len(strays)
        assert n_strays == 0, \
            f"{n_strays} source_dois in refined_citations.csv not found in refined_works" + _diagnosis(
                "corpus_align.py was run against a different refined_works.csv",
                "uv run python scripts/corpus_align.py",
                "~2 min",
                "Citation graph references removed papers — co-citation analysis corrupted",
            )


# ═══════════════════════════════════════════════════════════
# 9. CITATIONS (raw cache) — coverage and consistency
# ═══════════════════════════════════════════════════════════

class TestCitations:
    """Citation graph should have reasonable coverage."""

    def test_citation_row_count(self):
        if not os.path.isfile(CITATIONS_PATH):
            pytest.skip("citations.csv not found")
        # Count lines efficiently (don't load full dataframe)
        with open(CITATIONS_PATH) as f:
            n_lines = sum(1 for _ in f) - 1  # minus header
        assert n_lines > 500_000, \
            f"Only {n_lines:,} citation rows (expected > 500K)" + _diagnosis(
                "Citation enrichment incomplete or ran on old corpus",
                "make citations",
                "~2 hours",
                "Co-citation analysis and genealogy underpowered",
            )

    def test_citation_columns(self):
        if not os.path.isfile(CITATIONS_PATH):
            pytest.skip("citations.csv not found")
        header = pd.read_csv(CITATIONS_PATH, nrows=0).columns.tolist()
        required = ["source_doi", "ref_doi"]
        missing = [c for c in required if c not in header]
        assert not missing, \
            f"citations.csv missing columns: {missing}" + _diagnosis(
                "Citation enrichment script schema changed",
                "Check enrich_citations_batch.py output format",
                "15 min",
                "Co-citation and genealogy scripts will crash",
            )


# ═══════════════════════════════════════════════════════════
# 9. CONTENT QUALITY — language, abstracts, sources
# ═══════════════════════════════════════════════════════════

class TestContentQuality:
    """Corpus content must meet publication quality standards."""

    def test_english_majority(self, refined):
        if "language" not in refined.columns:
            pytest.skip("No language column")
        lang = refined["language"].fillna("unknown").str.lower()
        en_pct = 100 * lang.isin(["en", "english"]).sum() / len(refined)
        assert en_pct >= ENGLISH_PCT_MIN, \
            f"English papers = {en_pct:.1f}% (expected >= {ENGLISH_PCT_MIN}%)" + _diagnosis(
                "Language detection misclassified or corpus scope too broad",
                "Run qa_detect_language.py to verify",
                "~2 min",
                "Minor — multilingual corpus is by design, but English should dominate",
            )

    def test_abstract_coverage(self, refined):
        has_abstract = refined["abstract"].fillna("").str.len() > 50
        pct = 100 * has_abstract.sum() / len(refined)
        assert pct > 50, \
            f"Only {pct:.1f}% of papers have abstracts > 50 chars" + _diagnosis(
                "Abstract enrichment incomplete",
                "Re-run enrich_abstracts.py",
                "~30 min (API-dependent)",
                "Reranker scoring, embedding quality, and TF-IDF all degrade",
            )

    def test_multi_source_coverage(self, refined):
        """At least some papers should appear in multiple sources."""
        if "source_count" not in refined.columns:
            pytest.skip("No source_count column")
        multi = (refined["source_count"] >= 2).sum()
        assert multi > 100, \
            f"Only {multi} multi-source papers (expected > 100)" + _diagnosis(
                "Source deduplication not working or only one source loaded",
                "Check catalog_merge.py source_count logic",
                "30 min",
                "Multi-source agreement is a validation signal — low count weakens confidence",
            )

    def test_source_diversity(self, refined):
        """Corpus should draw from multiple sources."""
        present_cols = [c for c in FROM_COLS if c in refined.columns]
        n_sources = sum(1 for c in present_cols if (refined[c] == 1).any())
        assert n_sources >= 3, \
            f"Only {n_sources} unique sources (expected >= 3)" + _diagnosis(
                "Some catalog scripts not run or sources excluded",
                "Check catalog_merge.py and source pipeline",
                "1 hour",
                "Corpus lacks breadth — single-source bias",
            )

    def test_from_cols_present(self, refined):
        """All from_* boolean provenance columns must be present."""
        missing = [c for c in FROM_COLS if c not in refined.columns]
        assert not missing, \
            f"Missing from_* columns: {missing}" + _diagnosis(
                "catalog_merge.py was not updated to produce from_* columns",
                "Re-run: uv run python scripts/catalog_merge.py",
                "5 min",
                "Source provenance tracking broken — multi-source analysis impossible",
            )


# ═══════════════════════════════════════════════════════════
# 10. BLACKLIST VALIDATION — noise terms properly caught
# ═══════════════════════════════════════════════════════════

class TestBlacklistValidation:
    """Every noise title term must be caught by flags or excused by safe words."""

    @staticmethod
    def _get_flags(row):
        """Parse flags from audit CSV (pipe-delimited, with optional :suffix)."""
        flags = row.get("flags", "")
        s = str(flags) if flags else ""
        if not s or s == "nan":
            return []
        return [f.strip().split(":")[0] for f in s.split("|")]

    def test_blacklist_terms_caught(self, audit, refine_config):
        """For each noise term, all title matches are either flagged or have safe words."""
        noise_title = refine_config["noise_title"]
        safe_title = refine_config["safe_title"]

        missed_report = []
        for term in noise_title:
            matches = audit[audit["title"].str.lower().str.contains(term, na=False)]
            if matches.empty:
                continue

            flagged = matches[matches.apply(
                lambda row: "title_blacklist" in self._get_flags(row), axis=1
            )]
            unflagged = matches[~matches.index.isin(flagged.index)]
            truly_missed = unflagged[~unflagged["title"].apply(
                lambda t: _has_safe_words(str(t), safe_title)
            )]
            if len(truly_missed) > 0:
                examples = truly_missed["title"].head(3).tolist()
                missed_report.append(f"  '{term}': {len(truly_missed)} missed — {examples}")

        assert not missed_report, \
            "Blacklist terms not properly caught:\n" + "\n".join(missed_report) + _diagnosis(
                "Noise terms in titles not matched by flag_title_blacklist",
                "Review noise_title list in config/corpus_refine.yaml",
                "15 min",
                "Irrelevant papers (blockchain, deep learning, etc.) remain in corpus",
            )

    def test_blacklist_summary(self, audit, refine_config, capsys):
        """Print blacklist coverage summary (always passes)."""
        noise_title = refine_config["noise_title"]
        safe_title = refine_config["safe_title"]

        lines = ["\n  Blacklist coverage:"]
        for term in noise_title:
            matches = audit[audit["title"].str.lower().str.contains(term, na=False)]
            n_matches = len(matches)
            if n_matches == 0:
                lines.append(f"    '{term}': 0 matches")
                continue
            flagged = matches[matches.apply(
                lambda row: "title_blacklist" in self._get_flags(row), axis=1
            )]
            n_safe = n_matches - len(flagged)
            safe_note = f" ({n_safe} kept: safe words)" if n_safe else ""
            lines.append(f"    '{term}': {n_matches} total, {len(flagged)} flagged{safe_note}")
        print("\n".join(lines))


# ═══════════════════════════════════════════════════════════
# 11. CITATION QUALITY — QC report checks
# ═══════════════════════════════════════════════════════════

class TestCitationQuality:
    """Check qc_citations_report.json if available (warns if missing/stale)."""

    def test_citation_report_exists(self):
        """Warn (don't fail) if qc_citations_report.json is missing."""
        if not os.path.isfile(QC_CITATIONS_REPORT_PATH):
            import warnings
            warnings.warn(
                f"qc_citations_report.json not found at {QC_CITATIONS_REPORT_PATH}. "
                "Run: uv run python scripts/qc_citations.py to generate it."
            )
            pytest.skip("qc_citations_report.json not found (needs live API calls)")

    def test_citation_report_freshness(self, refined):
        """Warn if report is stale (DOI count mismatch or > 30 days old)."""
        if not os.path.isfile(QC_CITATIONS_REPORT_PATH):
            pytest.skip("qc_citations_report.json not found")
        import json
        import time
        with open(QC_CITATIONS_REPORT_PATH) as f:
            report = json.load(f)

        # Check age
        mtime = os.path.getmtime(QC_CITATIONS_REPORT_PATH)
        age_days = (time.time() - mtime) / 86400
        if age_days > 30:
            import warnings
            warnings.warn(
                f"qc_citations_report.json is {age_days:.0f} days old. "
                "Consider re-running: uv run python scripts/qc_citations.py"
            )

        # Check DOI count matches current corpus
        report_dois = report.get("corpus", {}).get("total_dois", 0)
        current_dois = refined["doi"].dropna().nunique()
        if report_dois > 0 and abs(report_dois - current_dois) > 500:
            import warnings
            warnings.warn(
                f"Report covers {report_dois:,} DOIs but refined has {current_dois:,}. "
                "Re-run: uv run python scripts/qc_citations.py"
            )

    def test_citation_precision_recall(self):
        """If report exists, recall must be >= 0.95 and sample size >= 20."""
        if not os.path.isfile(QC_CITATIONS_REPORT_PATH):
            pytest.skip("qc_citations_report.json not found")
        import json
        with open(QC_CITATIONS_REPORT_PATH) as f:
            report = json.load(f)

        verification = report.get("verification", {})
        precision = verification.get("aggregate_precision", 0)
        recall = verification.get("aggregate_recall", 0)
        sample_size = verification.get("sample_n", 0)

        assert sample_size >= 20, \
            f"QC sample size = {sample_size} (expected >= 20)" + _diagnosis(
                "qc_citations.py ran with too small a sample",
                "Re-run with larger sample: uv run python scripts/qc_citations.py",
                "~10 min",
                "Quality metrics not statistically meaningful",
            )
        # Recall should be very high (we don't miss known references)
        assert recall >= 0.95, \
            f"Citation recall = {recall:.3f} (expected >= 0.95)" + _diagnosis(
                "Citation enrichment missing known references",
                "Check Crossref/OpenAlex API coverage gaps",
                "1-2 hours",
                "Citation graph has missing edges — co-citation communities underconnected",
            )
        # Precision may be lower (~0.65) because OpenAlex includes refs
        # that Crossref doesn't have (not false positives, just additional sources)
        if precision < 0.60:
            import warnings
            warnings.warn(
                f"Citation precision = {precision:.3f}. This is expected when "
                "OpenAlex includes references not in Crossref. Check report details."
            )


# ═══════════════════════════════════════════════════════════
# 12. STATISTICS — compute and print summary
# ═══════════════════════════════════════════════════════════

class TestStatisticsSummary:
    """Compute and display publication-ready statistics.

    This test always passes — it prints a summary for human review.
    """

    def test_print_summary(self, refined, audit, reranker_cache):
        n = len(refined)
        n_enriched = len(audit)
        n_removed = (audit["action"] == "remove").sum()
        n_protected = audit["protected"].sum() if "protected" in audit.columns else 0
        n_core = (refined["cited_by_count"] >= 50).sum()
        year = refined["year"].dropna()

        # Flag breakdown from audit
        flags_col = audit["flags"].dropna()
        flag_counts = {}
        for cell in flags_col:
            for flag in str(cell).split("|"):
                base = flag.strip().split(":")[0]
                if base and base != "nan":
                    flag_counts[base] = flag_counts.get(base, 0) + 1

        # Language distribution
        lang = refined["language"].fillna("unknown").str.lower()
        en_pct = 100 * lang.isin(["en", "english"]).sum() / n

        # Abstract coverage
        has_abstract = refined["abstract"].fillna("").str.len() > 50
        abstract_pct = 100 * has_abstract.sum() / n

        # Embeddings
        emb_count = 0
        if os.path.isfile(EMBEDDINGS_PATH):
            emb_count = np.load(EMBEDDINGS_PATH)["vectors"].shape[0]

        # Citations
        cite_rows = 0
        if os.path.isfile(CITATIONS_PATH):
            with open(CITATIONS_PATH) as f:
                cite_rows = sum(1 for _ in f) - 1

        # Reranker
        n_cached = len(reranker_cache)
        scores = reranker_cache["score"].dropna()

        # ── Print ──
        lines = [
            "",
            "=" * 64,
            "  CORPUS ACCEPTANCE SUMMARY",
            "=" * 64,
            "",
            f"  Enriched works:     {n_enriched:>8,}",
            f"  Refined works:      {n:>8,}",
            f"  Removed:            {n_removed:>8,}  ({100*n_removed/n_enriched:.1f}%)",
            f"  Protected:          {n_protected:>8,}",
            f"  Core (cited >= 50): {n_core:>8,}",
            "",
            f"  Year range:         {int(year.min())}–{int(year.max())}",
            f"  English:            {en_pct:>7.1f}%",
            f"  With abstract:      {abstract_pct:>7.1f}%",
            f"  Embeddings:         {emb_count:>8,}",
            f"  Citation rows:      {cite_rows:>8,}",
            "",
            "  Flag breakdown:",
        ]
        for flag, count in sorted(flag_counts.items(),
                                   key=lambda x: -x[1]):
            lines.append(f"    {flag:<30s} {count:>6,}")

        lines += [
            "",
            f"  Reranker cache:     {n_cached:>8,} entries",
            f"  Score mean:         {scores.mean():>8.4f}",
            f"  Score median:       {scores.median():>8.4f}",
            f"  Score std:          {scores.std():>8.4f}",
            "",
            "=" * 64,
        ]
        print("\n".join(lines))

        # Per-period breakdown
        period_lines = ["\n  Per-period breakdown:"]
        for label, lo, hi in [("1990–2006", 1990, 2006),
                               ("2007–2014", 2007, 2014),
                               ("2015–2025", 2015, 2025)]:
            mask = (year >= lo) & (year <= hi)
            period_lines.append(f"    {label}:  {mask.sum():>6,} papers")
        print("\n".join(period_lines))

        # Source breakdown (via from_* boolean columns)
        present_from_cols = [c for c in FROM_COLS if c in refined.columns]
        source_lines = ["\n  Source breakdown:"]
        for col in present_from_cols:
            cnt = (refined[col] == 1).sum()
            if cnt > 0:
                src_name = col.replace("from_", "")
                source_lines.append(f"    {src_name:<25s} {cnt:>6,}")
        print("\n".join(source_lines))
        print()
