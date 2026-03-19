#!/usr/bin/env python3
"""Harvest climate finance literature from Semantic Scholar.

Uses the same tiered query taxonomy as catalog_openalex.py
(config/openalex_queries.yaml). Raw API responses stored in
pool/semanticscholar/ (gzipped JSONL, append-only).

Semantic Scholar Academic Graph API:
  https://api.semanticscholar.org/graph/v1/paper/search
  Free tier: 1 request/second (no API key), 10 req/s with key.
  Returns: paperId, DOI, title, abstract, year, citationCount,
           references, citations, fieldsOfStudy.

Usage:
    python scripts/catalog_semanticscholar.py [OPTIONS]

    --tier N          Run only tier N (default: all tiers)
    --resume          Skip S2 IDs already in the pool
    --pool-only       Download to pool, don't build CSV
    --extract-only    Build CSV from existing pool, don't download
    --dry-run         Show queries and expected counts
    --limit N         Max results per query (0=all, API max ~10K per query)
    --delay S         Delay between requests (default: 1.0)
"""

import argparse
import os
import re
import time

import pandas as pd
import yaml

from utils import (CONFIG_DIR, CATALOGS_DIR, WORKS_COLUMNS,
                   get_logger, normalize_doi, save_csv,
                   pool_path, append_to_pool, load_pool_ids,
                   load_pool_records)

log = get_logger("catalog_semanticscholar")

S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"

# Fields to request from S2
S2_FIELDS = ",".join([
    "paperId", "externalIds", "title", "abstract", "year",
    "authors", "venue", "citationCount", "fieldsOfStudy",
    "publicationTypes", "referenceCount", "s2FieldsOfStudy",
])


def load_query_config():
    """Load tiered query configuration from YAML."""
    yaml_path = os.path.join(CONFIG_DIR, "openalex_queries.yaml")
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def passes_relevance(text, concept_groups, min_groups):
    """Check if text mentions at least min_groups concept groups."""
    if min_groups == 0:
        return True
    if not text:
        return False
    words = set(re.findall(r'[a-z]{3,}', text.lower()))
    groups_hit = sum(1 for group_words in concept_groups.values()
                     if words & group_words)
    return groups_hit >= min_groups


def query_slug(term):
    """Convert a search term to a safe filename slug."""
    return re.sub(r"[^\w]", "_", term.lower()).strip("_")


def s2_get(url, params, delay=1.0, max_retries=5):
    """GET with rate limiting and retry for Semantic Scholar API."""
    import requests
    headers = {"User-Agent": "ClimateFinancePipeline/1.0 (mailto:minh.haduong@cnrs.fr)"}
    api_key = os.environ.get("S2_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key

    for attempt in range(max_retries):
        time.sleep(delay)
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 3 * (attempt + 1)))
            log.warning("  Rate limited. Waiting %ds...", wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"Failed after {max_retries} retries: {url}")


def build_record(r):
    """Build a works record dict from an S2 API response."""
    authors = r.get("authors", []) or []
    first_author = authors[0].get("name", "") if authors else ""
    all_authors = " ; ".join(a.get("name", "") for a in authors)

    ext_ids = r.get("externalIds", {}) or {}
    doi = normalize_doi(ext_ids.get("DOI", ""))

    fields = r.get("fieldsOfStudy", []) or []
    s2_fields = r.get("s2FieldsOfStudy", []) or []
    categories = " ; ".join(
        fields + [f.get("category", "") for f in s2_fields
                  if f.get("source") == "s2-fos-model"]
    )

    pub_types = r.get("publicationTypes", []) or []

    return {
        "source": "semanticscholar",
        "source_id": r.get("paperId", ""),
        "doi": doi,
        "title": r.get("title", ""),
        "first_author": first_author,
        "all_authors": all_authors,
        "year": r.get("year", ""),
        "journal": r.get("venue", ""),
        "abstract": r.get("abstract", "") or "",
        "language": "",  # S2 doesn't provide language
        "keywords": "",  # S2 doesn't provide author keywords
        "categories": categories,
        "cited_by_count": r.get("citationCount", ""),
        "affiliations": "",  # S2 doesn't provide affiliations in search
    }


# --- Download phase ---

def fetch_query(search_term, delay, limit, existing_ids, pool_file):
    """Fetch all papers matching a search term from S2, append to pool.

    S2 search API uses offset-based pagination (max offset ~10,000).
    """
    offset = 0
    per_page = 100  # S2 max is 100
    n_new = 0
    batch = []

    while True:
        params = {
            "query": search_term,
            "fields": S2_FIELDS,
            "offset": offset,
            "limit": per_page,
        }
        resp = s2_get(S2_API, params=params, delay=delay)
        data = resp.json()

        total = data.get("total", 0)
        results = data.get("data", [])

        if not results:
            break

        for r in results:
            s2_id = r.get("paperId", "")
            if s2_id in existing_ids:
                continue
            existing_ids.add(s2_id)
            batch.append(r)
            n_new += 1

        offset += len(results)

        # Flush batch every 500 records
        if len(batch) >= 500:
            append_to_pool(batch, pool_file)
            batch = []

        log.info("  [%s] %d/%d (new: %d)", search_term, offset, total, n_new)

        # S2 caps at ~10K offset
        if offset >= total or offset >= 9999:
            break
        if limit and offset >= limit:
            break

    if batch:
        append_to_pool(batch, pool_file)

    return n_new


def dry_run_query(search_term, delay):
    """Check how many results a query would return."""
    params = {"query": search_term, "limit": 1}
    resp = s2_get(S2_API, params=params, delay=delay)
    data = resp.json()
    return data.get("total", 0)


# --- Extract phase ---

def extract_from_pool(config):
    """Build semanticscholar_works.csv from pool records."""
    concept_groups = {
        k: set(v) for k, v in config.get("concept_groups", {}).items()
    }

    log.info("Loading pool records...")
    all_raw = load_pool_records("semanticscholar")
    log.info("  %d raw records in pool", len(all_raw))

    seen_ids = set()
    unique_raw = []
    for r in all_raw:
        s2_id = r.get("paperId", "")
        if s2_id not in seen_ids:
            seen_ids.add(s2_id)
            unique_raw.append(r)
    log.info("  %d unique after dedup", len(unique_raw))

    records = []
    for r in unique_raw:
        rec = build_record(r)
        records.append(rec)

    log.info("  %d records extracted", len(records))

    df = pd.DataFrame(records, columns=WORKS_COLUMNS)
    save_csv(df, os.path.join(CATALOGS_DIR, "semanticscholar_works.csv"))
    return df


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Semantic Scholar harvester for climate finance")
    parser.add_argument("--tier", type=int, default=0,
                        help="Run only this tier (default: all)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip S2 IDs already in pool")
    parser.add_argument("--pool-only", action="store_true",
                        help="Download to pool, don't build CSV")
    parser.add_argument("--extract-only", action="store_true",
                        help="Build CSV from pool, don't download")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show queries and expected counts")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max results per query (0=all, S2 caps at ~10K)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay between requests (default: 1.0s)")
    args = parser.parse_args()

    config = load_query_config()
    tiers = config.get("tiers", {})

    if args.tier:
        tiers = {args.tier: tiers[args.tier]}

    if args.extract_only:
        log.info("=== Extract-only mode: building CSV from pool ===")
        df = extract_from_pool(config)
        log.info("Done. %d works in semanticscholar_works.csv", len(df))
        return

    existing_ids = set()
    if args.resume:
        existing_ids = load_pool_ids("semanticscholar", id_field="paperId")
        log.info("Pool contains %d existing S2 IDs", len(existing_ids))

    grand_total = 0
    for tier_num in sorted(tiers.keys()):
        tier_cfg = tiers[tier_num]
        desc = tier_cfg.get("description", f"Tier {tier_num}")
        terms = tier_cfg.get("terms", [])

        log.info("=" * 60)
        log.info("TIER %d: %s", tier_num, desc)
        log.info("  %d queries", len(terms))
        log.info("=" * 60)

        for term in terms:
            slug = query_slug(term)
            pf = pool_path("semanticscholar", slug)

            if args.dry_run:
                count = dry_run_query(term, args.delay)
                log.info("  \"%s\": %s results", term, f"{count:,}")
                grand_total += count
                continue

            log.info("Querying: \"%s\"", term)
            n_new = fetch_query(
                term, args.delay, args.limit, existing_ids, pf)
            grand_total += n_new

    if args.dry_run:
        log.info("=" * 60)
        log.info("DRY RUN TOTAL: %s results across all queries", f"{grand_total:,}")
        return

    log.info("Download complete. %d new records added to pool.", grand_total)

    if not args.pool_only:
        log.info("=== Extracting CSV from pool ===")
        df = extract_from_pool(config)
        log.info("Done. %d works in semanticscholar_works.csv", len(df))


if __name__ == "__main__":
    main()
