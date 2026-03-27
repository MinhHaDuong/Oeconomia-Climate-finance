#!/usr/bin/env python3
"""Collect climate finance course reading lists from universities worldwide.

Five-stage pipeline:
  1. search   — Discover candidate URLs via DuckDuckGo + seed list
  2. fetch    — Download page content (HTML/PDF)
  3. classify — LLM classifies pages as syllabi or not
  4. extract  — LLM extracts bibliographic references
  5. normalize — Deduplicate + enrich via CrossRef (cached)

Each stage reads the previous stage's output and writes JSONL checkpoints.
Interruptible: re-run any stage to resume from checkpoint.

Usage:
    python scripts/collect_syllabi.py --stage search [--limit N]
    python scripts/collect_syllabi.py --stage fetch
    python scripts/collect_syllabi.py --stage classify
    python scripts/collect_syllabi.py --stage extract
    python scripts/collect_syllabi.py --stage normalize
"""

import argparse
import os

from syllabi_crossref import (
    CROSSREF_CACHE_PATH,
    _load_crossref_cache,
    _save_crossref_cache_entry,
    crossref_lookup,
)
from syllabi_harvest import stage_search as _stage_search
from syllabi_io import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_TEXT_CHARS,
    _jsonl_lock,
    append_jsonl,
    extract_json_from_text,
    extract_pdf_text,
    llm_call,
    load_jsonl,
    make_chunks,
)
from syllabi_process import (
    EXTRACT_CACHE_PATH,
    EXTRACT_PROMPT,
    _extract_cache_key,
    _extract_cache_lock,
    _load_extract_cache,
    _save_extract_cache_entry,
)
from syllabi_process import stage_classify as _stage_classify
from syllabi_process import stage_extract as _stage_extract
from syllabi_process import stage_normalize as _stage_normalize
from utils import (
    BASE_DIR,
    DATA_DIR,
    MAILTO,
    clean_doi,
    dedup_courses,
    get_logger,
    normalize_title,
    polite_get,
    save_csv,
)

log = get_logger("collect_syllabi")

# --- Paths ---
SYLLABI_DIR = os.path.join(DATA_DIR, "syllabi")
PDF_DIR = os.path.join(SYLLABI_DIR, "pdfs")
SEARCH_PATH = os.path.join(SYLLABI_DIR, "search_results.jsonl")
PAGES_PATH = os.path.join(SYLLABI_DIR, "pages.jsonl")
CLASSIFIED_PATH = os.path.join(SYLLABI_DIR, "classified.jsonl")
REFERENCES_PATH = os.path.join(SYLLABI_DIR, "raw_references.jsonl")
OUTPUT_CSV = os.path.join(SYLLABI_DIR, "reading_lists.csv")

_clean_doi = clean_doi  # Alias for backward compatibility with tests


# ============================================================
# Stage wrappers — delegate to syllabi_harvest / syllabi_process
# ============================================================

def stage_search(limit=0):
    """Discover candidate URLs via DuckDuckGo + seed list."""
    _stage_search(SEARCH_PATH, SYLLABI_DIR, limit=limit)


def stage_fetch():
    """Download page content for each candidate URL."""
    import syllabi_harvest
    syllabi_harvest.stage_fetch(SEARCH_PATH, PAGES_PATH, PDF_DIR)


def stage_classify():
    """LLM classifies fetched pages as syllabi or not."""
    _stage_classify(PAGES_PATH, CLASSIFIED_PATH)


def stage_extract():
    """LLM extracts bibliographic references from confirmed syllabi."""
    _stage_extract(PAGES_PATH, CLASSIFIED_PATH, REFERENCES_PATH)


def stage_normalize():
    """Deduplicate and enrich references via CrossRef (cached)."""
    _stage_normalize(REFERENCES_PATH, OUTPUT_CSV)


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Collect climate finance course reading lists")
    parser.add_argument("--stage", required=True,
                        choices=["search", "fetch", "classify", "extract", "normalize"],
                        help="Pipeline stage to run")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of queries (search) or items to process")
    args = parser.parse_args()

    os.makedirs(SYLLABI_DIR, exist_ok=True)

    if args.stage == "search":
        stage_search(limit=args.limit)
    elif args.stage == "fetch":
        stage_fetch()
    elif args.stage == "classify":
        stage_classify()
    elif args.stage == "extract":
        stage_extract()
    elif args.stage == "normalize":
        stage_normalize()


if __name__ == "__main__":
    main()
