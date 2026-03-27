"""Shared utilities for the literature indexing pipeline.

Thin facade: owns logging setup and CSV schema constants, then re-exports
all symbols from the four focused modules so existing imports work unchanged.

    from utils import normalize_doi, get_logger, load_analysis_corpus  # still works

Canonical homes for new code:
    pipeline_text.py     — pure text transforms (DOI, title, abstract, language)
    pipeline_io.py       — HTTP, CSV, checkpoint, pool, run reports, figures
    pipeline_loaders.py  — paths, config YAMLs, corpus/embeddings/citations
    pipeline_progress.py — WatchedProgress, priority scoring
"""

import logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name=None):
    """Return a configured logger for pipeline scripts.

    First call installs a shared StreamHandler on the 'pipeline' root logger
    with elapsed-time timestamps.  Subsequent calls just return a child logger.

    Usage in scripts::

        from utils import get_logger
        log = get_logger("enrich_abstracts")
        log.info("Step 1: cross-source backfill (%d missing)", n)
    """
    root = logging.getLogger("pipeline")
    if not root.handlers:
        root.setLevel(logging.DEBUG)
        root.propagate = False  # prevent duplicates if DVC configures root logger
        handler = logging.StreamHandler()       # stderr, auto-flushes
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
    if name:
        return root.getChild(name)
    return root


_utils_log = get_logger("utils")

# ---------------------------------------------------------------------------
# Paths — re-exported from pipeline_loaders so callers need not change
# ---------------------------------------------------------------------------

from pipeline_loaders import (  # noqa: E402, F401
    BASE_DIR,
    CATALOGS_DIR,
    CONFIG_DIR,
    DATA_DIR,
    EMBEDDINGS_CACHE_DIR,
    EMBEDDINGS_CACHE_PATH,
    EMBEDDINGS_PATH,
    EXPORTS_DIR,
    POOL_DIR,
    RAW_DIR,
    REFINED_CITATIONS_PATH,
    REFINED_EMBEDDINGS_PATH,
    REFINED_WORKS_PATH,
)

# ---------------------------------------------------------------------------
# CSV schemas — constants used by many catalog scripts
# ---------------------------------------------------------------------------

WORKS_COLUMNS = [
    "source", "source_id", "doi", "title", "first_author", "all_authors",
    "year", "journal", "abstract", "language", "keywords", "categories",
    "cited_by_count", "affiliations",
]

# Source provenance — boolean columns indicating which sources contributed each work.
# These replace the old pipe-separated `source` column for multi-source tracking.
SOURCE_NAMES = ["openalex", "istex", "bibcnrs", "scispace", "grey", "teaching"]
FROM_COLS = [f"from_{s}" for s in SOURCE_NAMES]

REFS_COLUMNS = [
    "source_doi", "source_id", "ref_doi", "ref_title", "ref_first_author",
    "ref_year", "ref_journal", "ref_raw",
]

# ---------------------------------------------------------------------------
# HTTP constants — re-exported from pipeline_io
# ---------------------------------------------------------------------------

from pipeline_io import (  # noqa: E402, F401
    MAILTO,
    OPENALEX_API_KEY,
    POLITE_MAX_RETRIES,
    RETRY_MAX_RETRIES,
)

# ---------------------------------------------------------------------------
# Re-exports from pipeline_text
# ---------------------------------------------------------------------------

from pipeline_text import (  # noqa: E402, F401
    ISO_639_1_CODES,
    LANG_NORMALIZE,
    clean_doi,
    detect_language,
    is_valid_iso639_1,
    normalize_doi,
    normalize_doi_safe,
    normalize_lang,
    normalize_title,
    reconstruct_abstract,
)

# ---------------------------------------------------------------------------
# Re-exports from pipeline_io
# ---------------------------------------------------------------------------

from pipeline_io import (  # noqa: E402, F401
    append_checkpoint,
    append_to_pool,
    dedup_courses,
    delete_checkpoint,
    load_checkpoint,
    load_pool_ids,
    load_pool_records,
    make_run_id,
    polite_get,
    pool_path,
    retry_get,
    save_csv,
    save_figure,
    save_run_report,
)

# ---------------------------------------------------------------------------
# Re-exports from pipeline_loaders
# ---------------------------------------------------------------------------

from pipeline_loaders import (  # noqa: E402, F401
    load_analysis_config,
    load_analysis_corpus,
    load_analysis_periods,
    load_cluster_labels,
    load_collect_config,
    load_embeddings,
    load_refined_citations,
    load_refined_embeddings,
    work_key,
)

# ---------------------------------------------------------------------------
# Re-exports from pipeline_progress
# ---------------------------------------------------------------------------

from pipeline_progress import (  # noqa: E402, F401
    EX_STUCK,
    WatchedProgress,
    compute_priority_scores,
    sort_dois_by_priority,
)
