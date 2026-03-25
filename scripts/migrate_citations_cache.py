#!/usr/bin/env python3
"""One-time migration: split v1 citations.csv into source-specific caches.

Reads the v1.0-submission citations.csv from the DVC remote and splits it
into enrich_cache/crossref_refs.csv and enrich_cache/openalex_refs.csv.

Crossref rows: those NOT produced by OpenAlex (source_id doesn't start with "openalex:")
OpenAlex rows: source_id starts with "openalex:" — convert to OA_REFS_COLUMNS schema

After migration, deletes the old done-files (citations_done.csv, citations_oa_done.txt).

Usage:
    uv run python scripts/migrate_citations_cache.py
"""

import os
import shutil
import sys

import pandas as pd

# Add scripts/ to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from utils import CATALOGS_DIR, REFS_COLUMNS, get_logger, normalize_doi

log = get_logger("migrate_citations_cache")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")

# v1 citations.csv on the DVC remote (verified present)
V1_HASH = "76fc749c6d68943ed0ff472c10b94c13"
DVC_REMOTE = os.environ.get(
    "DVC_REMOTE_PATH",
    "/data/projets/dvc/oeconomia-climate-finance",
)
V1_PATH = os.path.join(DVC_REMOTE, "files", "md5",
                        V1_HASH[:2], V1_HASH[2:])

# New cache schemas
OA_REFS_COLUMNS = [
    "source_doi", "ref_oa_id", "ref_doi", "ref_title",
    "ref_first_author", "ref_year", "ref_journal",
]

# Old files to delete
OLD_DONE_FILES = [
    os.path.join(CACHE_DIR, "citations_done.csv"),
    os.path.join(CACHE_DIR, "citations_oa_done.txt"),
    # Legacy location
    os.path.join(CATALOGS_DIR, ".citations_oa_done.txt"),
]


def main():
    crossref_cache = os.path.join(CACHE_DIR, "crossref_refs.csv")
    openalex_cache = os.path.join(CACHE_DIR, "openalex_refs.csv")

    # Safety check: don't overwrite existing caches
    for path in [crossref_cache, openalex_cache]:
        if os.path.exists(path) and os.path.getsize(path) > 100:
            log.error("Cache already exists: %s — aborting to avoid data loss", path)
            sys.exit(1)

    # Read v1 citations
    if not os.path.exists(V1_PATH):
        log.error("v1 citations.csv not found at %s", V1_PATH)
        log.error("Set DVC_REMOTE_PATH env var if your remote is elsewhere")
        sys.exit(1)

    log.info("Reading v1 citations from %s ...", V1_PATH)
    df = pd.read_csv(V1_PATH, dtype=str, keep_default_na=False)
    log.info("  Total rows: %d", len(df))

    # Split by source_id prefix
    is_openalex = df["source_id"].str.startswith("openalex:", na=False)
    oa_rows = df[is_openalex].copy()
    cr_rows = df[~is_openalex].copy()
    log.info("  OpenAlex rows: %d", len(oa_rows))
    log.info("  Crossref rows: %d", len(cr_rows))

    # Write Crossref cache (already in REFS_COLUMNS schema)
    os.makedirs(CACHE_DIR, exist_ok=True)
    cr_rows.to_csv(crossref_cache, index=False)
    log.info("  Wrote %s (%d rows)", crossref_cache, len(cr_rows))

    # Write OpenAlex cache (convert to OA_REFS_COLUMNS)
    oa_mapped = pd.DataFrame({
        "source_doi": oa_rows["source_doi"],
        "ref_oa_id": oa_rows["source_id"].str.replace("openalex:", "", n=1),
        "ref_doi": oa_rows["ref_doi"],
        "ref_title": oa_rows["ref_title"],
        "ref_first_author": oa_rows["ref_first_author"],
        "ref_year": oa_rows["ref_year"],
        "ref_journal": oa_rows["ref_journal"],
    })
    oa_mapped.to_csv(openalex_cache, index=False)
    log.info("  Wrote %s (%d rows)", openalex_cache, len(oa_mapped))

    # Delete old done-files
    for path in OLD_DONE_FILES:
        if os.path.exists(path):
            os.remove(path)
            log.info("  Deleted old done-file: %s", path)

    # Verify: run merge to produce citations.csv
    log.info("Running merge to verify...")
    from merge_citations import merge_citations
    n = merge_citations()
    log.info("Migration complete: %d rows in citations.csv", n)


if __name__ == "__main__":
    main()
