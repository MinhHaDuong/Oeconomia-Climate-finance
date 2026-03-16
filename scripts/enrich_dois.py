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
import sys
from difflib import SequenceMatcher

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, MAILTO, OPENALEX_API_KEY, normalize_doi,
                   normalize_title, polite_get, save_csv)

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "doi_resolved.csv")
TITLE_SIM_THRESHOLD = 0.85
OPENALEX_SEARCH_URL = "https://api.openalex.org/works"


def load_cache():
    """Load {source_id: doi_or_empty} cache."""
    if not os.path.exists(CACHE_FILE):
        return {}
    df = pd.read_csv(CACHE_FILE, dtype=str, keep_default_na=False)
    return dict(zip(df["source_id"], df["doi"]))


def save_cache(cache):
    """Persist cache to CSV."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    rows = [{"source_id": k, "doi": v} for k, v in cache.items()]
    pd.DataFrame(rows).to_csv(CACHE_FILE, index=False)


def title_similarity(a, b):
    """Normalized title similarity ratio."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def search_doi(title, year=None):
    """Search OpenAlex for a work by title, optionally filtered by year.

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
        year_int = int(float(year)) if year and pd.notna(year) else None
    except (ValueError, TypeError):
        year_int = None
    if year_int:
        params["filter"] = f"publication_year:{year_int}"

    try:
        resp = polite_get(OPENALEX_SEARCH_URL, params=params, delay=1.0)
        results = resp.json().get("results", [])
    except Exception as e:
        print(f"  Search failed for '{title[:60]}': {e}")
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
    print(f"Loaded {len(df)} works from {corpus_path}")

    # Identify DOI-less works with titles
    # Skip OpenAlex-only sources: if OA doesn't have a DOI, re-querying OA won't help
    doi_col = df["doi"].fillna("").astype(str).str.strip()
    has_doi = doi_col.apply(lambda x: bool(x) and x.lower() not in ("", "nan", "none"))
    has_title = df["title"].notna() & (df["title"].str.strip() != "")
    is_oa_only = (df["from_openalex"] == 1) & (df["source_count"] == 1)
    candidates = df[~has_doi & has_title & ~is_oa_only].copy()
    skipped_oa = int((~has_doi & has_title & is_oa_only).sum())
    print(f"Candidates (no DOI, has title, non-OA-only): {len(candidates)}")
    print(f"Skipped (OpenAlex-only, DOI unresolvable): {skipped_oa}")

    # Load cache — skip already-processed
    cache = load_cache()
    to_process = candidates[~candidates["source_id"].isin(cache)]
    print(f"Already cached: {len(candidates) - len(to_process)}")
    print(f"To process: {len(to_process)}")

    if args.limit > 0:
        to_process = to_process.head(args.limit)
        print(f"Limited to: {len(to_process)}")

    if args.dry_run:
        print("\n[DRY RUN] Would search OpenAlex for these works:")
        for _, row in to_process.head(10).iterrows():
            print(f"  {row['source_id']}: {str(row['title'])[:80]}")
        if len(to_process) > 10:
            print(f"  ... and {len(to_process) - 10} more")
        return

    # Process
    resolved = 0
    not_found = 0
    for i, (idx, row) in enumerate(to_process.iterrows()):
        title = str(row["title"])
        year = row.get("year")
        sid = row["source_id"]

        doi, oa_id, sim = search_doi(title, year)

        if doi and sim >= TITLE_SIM_THRESHOLD:
            cache[sid] = doi
            resolved += 1
            if resolved <= 20 or resolved % 100 == 0:
                print(f"  [{i+1}/{len(to_process)}] MATCH (sim={sim:.2f}): "
                      f"{title[:60]} → {doi}")
        else:
            # Cache empty string to avoid re-querying
            cache[sid] = ""
            not_found += 1

        # Save cache periodically
        if (i + 1) % 200 == 0:
            save_cache(cache)
            print(f"  Checkpoint: {i+1}/{len(to_process)} "
                  f"(resolved={resolved}, not_found={not_found})")

    # Final save
    save_cache(cache)
    print(f"\nDone. Resolved: {resolved}, Not found: {not_found}")

    if resolved == 0:
        print("No new DOIs to apply.")
        # Still copy input → output if they differ
        if output_path != corpus_path:
            save_csv(df, output_path)
            print(f"Copied {len(df)} rows to {output_path}")
        return

    # Apply resolved DOIs to corpus
    resolved_map = {k: v for k, v in cache.items() if v}
    print(f"Applying {len(resolved_map)} resolved DOIs → {output_path}...")

    mask = df["source_id"].isin(resolved_map) & ~has_doi
    applied = 0
    for idx in df[mask].index:
        sid = df.at[idx, "source_id"]
        new_doi = resolved_map[sid]
        df.at[idx, "doi"] = new_doi
        applied += 1

    save_csv(df, output_path)
    print(f"Applied {applied} DOIs. Saved {output_path}")


if __name__ == "__main__":
    main()
