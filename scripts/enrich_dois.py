#!/usr/bin/env python3
"""Resolve missing DOIs via OpenAlex title+year search.

For each work in refined_works.csv that lacks a DOI but has a title,
queries the OpenAlex works endpoint and fuzzy-matches on title.
Idempotent: caches results so re-runs skip already-resolved works.

Produces:
- Updates refined_works.csv in place (fills doi column)
- Cache at catalogs/enrich_cache/doi_resolved.csv

Usage:
    python scripts/enrich_dois.py [--dry-run] [--limit N]
"""

import argparse
import os
from difflib import SequenceMatcher

import pandas as pd

from utils import (CATALOGS_DIR, MAILTO, OPENALEX_API_KEY, normalize_doi,
                   normalize_title, polite_get, save_csv, get_logger)

log = get_logger("enrich_dois")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "doi_resolved.csv")
TITLE_SIM_THRESHOLD = 0.85
OPENALEX_SEARCH_URL = "https://api.openalex.org/works"


_disk_cache = None
_disk_cache_dirty = 0  # count of unsaved writes


def load_cache():
    """Load {source_id: doi_or_empty} cache. Cached in memory after first load."""
    global _disk_cache
    if _disk_cache is not None:
        return _disk_cache
    if not os.path.exists(CACHE_FILE):
        _disk_cache = {}
        return _disk_cache
    try:
        df = pd.read_csv(CACHE_FILE, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        log.warning("Cache file empty or corrupt: %s — starting fresh", CACHE_FILE)
        _disk_cache = {}
        return _disk_cache
    _disk_cache = dict(zip(df["source_id"], df["doi"]))
    return _disk_cache


def save_cache(cache=None):
    """Persist cache to CSV. Batches writes — flushes every 50 updates."""
    global _disk_cache, _disk_cache_dirty
    if cache is not None:
        _disk_cache = cache
    _disk_cache_dirty += 1
    if _disk_cache_dirty < 50:
        return
    flush_cache()


def flush_cache():
    """Force-write cache to disk."""
    global _disk_cache_dirty
    if _disk_cache is None or _disk_cache_dirty == 0:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    rows = [{"source_id": k, "doi": v} for k, v in _disk_cache.items()]
    pd.DataFrame(rows).to_csv(CACHE_FILE, index=False)
    _disk_cache_dirty = 0


import atexit
atexit.register(flush_cache)


def title_similarity(a, b):
    """Normalized title similarity ratio."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _normalize_author(author):
    """Normalize author string: lowercase, strip, first author only.

    Used both for cache keys and for appending author to OpenAlex search.
    """
    if not author:
        return ""
    return str(author).split(";")[0].split(",")[0].strip().lower()


def search_doi(title, year=None, author=None):
    """Search OpenAlex for a work by title.

    Title-only search with similarity ranking. Year and author are accepted
    for API compatibility but not used in the query — year filters exclude
    correct matches when OpenAlex's year differs from the source, and author
    appended to search pollutes fulltext matching. Both are still used for
    cache keying in find_doi().

    Returns (doi, openalex_id, similarity) or (None, None, 0).
    """
    params = {
        "search": title[:200],
        "select": "id,doi,title,publication_year",
        "per_page": 5,
        "mailto": MAILTO,
    }
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY

    try:
        resp = polite_get(OPENALEX_SEARCH_URL, params=params, delay=1.0)
        results = resp.json().get("results", [])
    except Exception as e:
        log.warning("Search failed for '%s': %s", title[:60], e)
        return None, None, 0

    best_doi, best_id, best_sim = None, None, 0
    for r in results:
        r_title = r.get("title", "")
        sim = title_similarity(title, r_title)
        if sim > best_sim:
            best_sim = sim
            raw_doi = r.get("doi", "")
            best_doi = normalize_doi(raw_doi) if raw_doi else None
            best_id = r.get("id", "").replace("https://openalex.org/", "")

    return best_doi, best_id, best_sim


# --- Cache-transparent DOI resolver for external callers ---

_title_cache = {}  # in-memory: cache_key → doi or ""


def find_doi(title, year=None, author=None):
    """Cached DOI lookup. Returns DOI string or empty string.

    Two-level cache (in-memory + on-disk) makes repeated lookups free.
    Callers never touch cache directly — just call find_doi(title, year).

    When author or year is provided, checks a precise title+meta cache key
    (title|author|year) first, then falls back to the title-only key.
    New lookups write to both keys so existing cache entries remain valid
    (zero blast radius).
    """
    tnorm = normalize_title(title) if title else ""
    if not tnorm:
        return ""

    anorm = _normalize_author(author)
    try:
        ynorm = str(int(float(year))) if year and pd.notna(year) else ""
    except (ValueError, TypeError):
        ynorm = ""
    title_key = f"title:{tnorm}"
    precise_parts = [tnorm, anorm, ynorm]
    has_precise = anorm or ynorm
    precise_key = f"title+meta:{tnorm}|{anorm}|{ynorm}" if has_precise else None

    # Build ordered list of cache keys to check: author-keyed first, then title-only
    check_keys = [precise_key, title_key] if precise_key else [title_key]

    # Level 1: in-memory cache
    for key in check_keys:
        if key in _title_cache:
            return _title_cache[key]

    # Level 2: on-disk cache (shared across runs)
    cache = load_cache()
    for key in check_keys:
        if key in cache:
            _title_cache[key] = cache[key]
            return cache[key]

    # Level 3: query OpenAlex
    doi, _oa_id, sim = search_doi(title, year, author=author)
    result = doi if doi and sim >= TITLE_SIM_THRESHOLD else ""

    # Store in both caches — write to all applicable keys
    write_keys = [precise_key, title_key] if precise_key else [title_key]
    for key in write_keys:
        _title_cache[key] = result
        cache[key] = result
    save_cache(cache)

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without modifying files")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max works to process (0=all)")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Input works CSV (default: unified_works.csv)")
    parser.add_argument("--works-output",
                        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
                        help="Output works CSV (default: enriched_works.csv)")
    args = parser.parse_args()

    # Load corpus
    corpus_path = args.works_input
    output_path = args.works_output
    df = pd.read_csv(corpus_path)
    log.info("Loaded %d works from %s", len(df), corpus_path)

    # Identify DOI-less works with titles
    # Skip OpenAlex-only sources: if OA doesn't have a DOI, re-querying OA won't help
    doi_col = df["doi"].fillna("").astype(str).str.strip()
    has_doi = doi_col.apply(lambda x: bool(x) and x.lower() not in ("", "nan", "none"))
    has_title = df["title"].notna() & (df["title"].str.strip() != "")
    is_oa_only = (df["from_openalex"] == 1) & (df["source_count"] == 1)
    candidates = df[~has_doi & has_title & ~is_oa_only].copy()
    skipped_oa = int((~has_doi & has_title & is_oa_only).sum())
    log.info("Candidates: %d (skipped %d OA-only)", len(candidates), skipped_oa)

    # Load cache — skip already-processed
    cache = load_cache()
    to_process = candidates[~candidates["source_id"].isin(cache)]
    log.info("Cached: %d, to process: %d",
             len(candidates) - len(to_process), len(to_process))

    if args.limit > 0:
        to_process = to_process.head(args.limit)
        log.info("Limited to: %d", len(to_process))

    if args.dry_run:
        log.info("[DRY RUN] Would search OpenAlex for %d works", len(to_process))
        for _, row in to_process.head(10).iterrows():
            log.info("  %s: %s", row['source_id'], str(row['title'])[:80])
        if len(to_process) > 10:
            log.info("  ... and %d more", len(to_process) - 10)
        return

    # Process
    resolved = 0
    not_found = 0
    has_author_col = "first_author" in to_process.columns
    for i, (idx, row) in enumerate(to_process.iterrows()):
        title = str(row["title"])
        year = row.get("year")
        sid = row["source_id"]
        author = str(row["first_author"]) if has_author_col else None

        doi, oa_id, sim = search_doi(title, year, author=author)

        if doi and sim >= TITLE_SIM_THRESHOLD:
            cache[sid] = doi
            resolved += 1
            if resolved <= 20 or resolved % 100 == 0:
                log.info("[%d/%d] MATCH (sim=%.2f): %s → %s",
                         i + 1, len(to_process), sim, title[:60], doi)
        else:
            # Cache empty string to avoid re-querying
            cache[sid] = ""
            not_found += 1

        # Save cache periodically
        if (i + 1) % 200 == 0:
            save_cache(cache)
            log.info("Checkpoint: %d/%d (resolved=%d, not_found=%d)",
                     i + 1, len(to_process), resolved, not_found)

    # Final save
    save_cache(cache)
    log.info("Done. Resolved: %d, Not found: %d", resolved, not_found)

    if resolved == 0:
        log.info("No new DOIs to apply.")
        # Still copy input → output if they differ
        if output_path != corpus_path:
            save_csv(df, output_path)
            log.info("Copied %d rows to %s", len(df), output_path)
        return

    # Apply resolved DOIs to corpus
    resolved_map = {k: v for k, v in cache.items() if v}
    log.info("Applying %d resolved DOIs → %s...", len(resolved_map), output_path)

    mask = df["source_id"].isin(resolved_map) & ~has_doi
    applied = 0
    for idx in df[mask].index:
        sid = df.at[idx, "source_id"]
        new_doi = resolved_map[sid]
        df.at[idx, "doi"] = new_doi
        applied += 1

    save_csv(df, output_path)
    log.info("Applied %d DOIs. Saved %s", applied, output_path)


if __name__ == "__main__":
    main()
