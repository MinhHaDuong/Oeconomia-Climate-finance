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
import atexit
import os
from difflib import SequenceMatcher

import pandas as pd
from utils import (
    CATALOGS_DIR,
    MAILTO,
    OPENALEX_API_KEY,
    get_logger,
    normalize_doi,
    normalize_title,
    polite_get,
)

log = get_logger("enrich_dois")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "doi_resolved.csv")
TITLE_SIM_THRESHOLD = 0.85
OPENALEX_SEARCH_URL = "https://api.openalex.org/works"


class _DiskCache:
    """Batched disk cache: accumulates writes and flushes every N updates.

    Replaces the previous global-variable cache (_disk_cache, _disk_cache_dirty)
    with an encapsulated object that manages its own lifecycle.
    """

    def __init__(self, path: str, flush_every: int = 50) -> None:
        self._path = path
        self._flush_every = flush_every
        self._data: dict[str, str] | None = None
        self._dirty = 0
        atexit.register(self.flush)

    def load(self) -> dict[str, str]:
        """Load {key: value} cache from CSV. Cached in memory after first load."""
        if self._data is not None:
            return self._data
        if not os.path.exists(self._path):
            self._data = {}
            return self._data
        try:
            df = pd.read_csv(self._path, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError:
            log.warning("Cache file empty or corrupt: %s — starting fresh", self._path)
            self._data = {}
            return self._data
        self._data = dict(zip(df["source_id"], df["doi"]))
        return self._data

    def mark_dirty(self) -> None:
        """Record a write; auto-flush when flush_every threshold is reached."""
        self._dirty += 1
        if self._dirty >= self._flush_every:
            self.flush()

    def flush(self) -> None:
        """Force-write cache to disk."""
        if self._data is None or self._dirty == 0:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        rows = [{"source_id": k, "doi": v} for k, v in self._data.items()]
        pd.DataFrame(rows).to_csv(self._path, index=False)
        self._dirty = 0


_cache = _DiskCache(CACHE_FILE)


def load_cache() -> dict[str, str]:
    """Load {source_id: doi_or_empty} cache. Cached in memory after first load."""
    return _cache.load()


def save_cache(cache: dict[str, str] | None = None) -> None:
    """Persist cache to CSV. Batches writes — flushes every 50 updates."""
    if cache is not None:
        _cache._data = cache
    _cache.mark_dirty()


def flush_cache() -> None:
    """Force-write cache to disk."""
    _cache.flush()


def title_similarity(a: str, b: str) -> float:
    """Normalized title similarity ratio."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _normalize_author(author: object) -> str:
    """Normalize author string: lowercase, strip, first author only.

    Used both for cache keys and for appending author to OpenAlex search.
    """
    if not author:
        return ""
    return str(author).split(";")[0].split(",")[0].strip().lower()


CROSSREF_SEARCH_URL = "https://api.crossref.org/works"


def _search_openalex(title: str) -> tuple[str | None, str | None, float]:
    """Query OpenAlex works search. Returns (doi, oa_id, similarity)."""
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
        log.warning("OpenAlex search failed for '%s': %s", title[:60], e)
        return None, None, 0.0

    best_doi, best_id, best_sim = None, None, 0.0
    for r in results:
        r_title = r.get("title", "")
        sim = title_similarity(title, r_title)
        if sim > best_sim:
            best_sim = sim
            raw_doi = r.get("doi", "")
            best_doi = normalize_doi(raw_doi) if raw_doi else None
            best_id = r.get("id", "").replace("https://openalex.org/", "")

    return best_doi, best_id, best_sim


def _search_crossref(title: str) -> tuple[str | None, float]:
    """Query Crossref works search. Returns (doi, similarity)."""
    params = {
        "query.title": title[:200],
        "rows": 3,
        "mailto": MAILTO,
    }
    try:
        resp = polite_get(CROSSREF_SEARCH_URL, params=params, delay=1.0)
        items = resp.json().get("message", {}).get("items", [])
    except Exception as e:
        log.warning("Crossref search failed for '%s': %s", title[:60], e)
        return None, 0.0

    best_doi, best_sim = None, 0.0
    for item in items:
        cr_titles = item.get("title", [])
        cr_title = cr_titles[0] if cr_titles else ""
        sim = title_similarity(title, cr_title)
        if sim > best_sim:
            best_sim = sim
            best_doi = normalize_doi(item.get("DOI", ""))

    return best_doi, best_sim


def search_doi(title: str, year: object = None, author: object = None) -> tuple[str | None, str | None, float]:
    """Search for a DOI by title: OpenAlex first, Crossref fallback.

    Returns (doi, openalex_id, similarity) or (None, None, 0).
    """
    # Try OpenAlex first
    doi, oa_id, sim = _search_openalex(title)
    if doi and sim >= TITLE_SIM_THRESHOLD:
        return doi, oa_id, sim

    # Fallback: Crossref
    cr_doi, cr_sim = _search_crossref(title)
    if cr_doi and cr_sim >= TITLE_SIM_THRESHOLD:
        return cr_doi, oa_id, cr_sim

    # Return best OA result even if below threshold (caller decides)
    return doi, oa_id, sim


# --- Cache-transparent DOI resolver for external callers ---

_title_cache: dict[str, str] = {}  # in-memory: cache_key → doi or ""


def find_doi(title: str | None, year: object = None, author: object = None) -> str:
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
        ynorm = str(int(float(year))) if year and pd.notna(year) else ""  # type: ignore[arg-type]
    except (ValueError, TypeError):
        ynorm = ""
    title_key = f"title:{tnorm}"
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

    # Level 3: query OpenAlex (title is guaranteed non-None here — early return above)
    assert title is not None
    doi, _oa_id, sim = search_doi(title, year, author=author)
    result = doi if doi and sim >= TITLE_SIM_THRESHOLD else ""

    # Store in both caches — write to all applicable keys
    write_keys = [precise_key, title_key] if precise_key else [title_key]
    for key in write_keys:
        _title_cache[key] = result
        cache[key] = result
    save_cache(cache)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without modifying files")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max works to process (0=all)")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Input works CSV (default: unified_works.csv)")
    args = parser.parse_args()

    # Load corpus
    corpus_path = args.works_input
    df = pd.read_csv(corpus_path)
    log.info("Loaded %d works from %s", len(df), corpus_path)

    # Identify DOI-less works with titles
    # All DOI-less works are candidates — Crossref fallback can find DOIs
    # that OpenAlex lacks (previously OA-only works were skipped)
    doi_col = df["doi"].fillna("").astype(str).str.strip()
    has_doi = doi_col.apply(lambda x: bool(x) and x.lower() not in ("", "nan", "none"))
    has_title = df["title"].notna() & (df["title"].str.strip() != "")
    candidates = df[~has_doi & has_title].copy()
    log.info("Candidates: %d", len(candidates))

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

    # Final save — cache only, enrich_join.py applies to the monolith (#428)
    save_cache(cache)
    log.info("Done. Resolved: %d, Not found: %d. Cache: %s",
             resolved, not_found, CACHE_FILE)


if __name__ == "__main__":
    main()
