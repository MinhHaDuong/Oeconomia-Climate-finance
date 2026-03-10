#!/usr/bin/env python3
"""Unified OpenAlex harvester for climate finance literature.

Replaces the former two-script approach (catalog_openalex.py +
catalog_openalex_historical.py) with a single tiered query engine.

Query terms are defined in data/openalex_queries.yaml (4 tiers).
Raw API responses are stored in pool/openalex/ (gzipped JSONL, append-only).
Extracted records go to catalogs/openalex_works.csv.

Usage:
    python scripts/catalog_openalex.py [OPTIONS]

    --tier N          Run only tier N (default: all tiers)
    --resume          Skip OpenAlex IDs already in the pool
    --pool-only       Download to pool, don't build CSV
    --extract-only    Build CSV from existing pool, don't download
    --dry-run         Show queries and expected counts, don't fetch
    --limit N         Max records per query (0=all)
    --delay S         Delay between requests (default: 0.15)
"""

import argparse
import os
import re
import sys

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from utils import (BASE_DIR, CATALOGS_DIR, WORKS_COLUMNS, MAILTO,
                   normalize_doi, reconstruct_abstract, polite_get,
                   save_csv, pool_path, append_to_pool, load_pool_ids,
                   load_pool_records)

OA_API = "https://api.openalex.org/works"

# Fields to request from OpenAlex (reduces payload, includes referenced_works)
OA_SELECT = ",".join([
    "id", "doi", "display_name", "publication_year", "authorships",
    "primary_location", "abstract_inverted_index", "language", "keywords",
    "concepts", "cited_by_count", "referenced_works", "type",
])


def load_query_config():
    """Load tiered query configuration from YAML."""
    yaml_path = os.path.join(BASE_DIR, "data", "openalex_queries.yaml")
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


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


def build_record(r):
    """Build a works record dict from a raw OpenAlex API response.

    Returns:
        (record_dict, abstract_text, title_text)
    """
    authorships = r.get("authorships", [])
    first_author = ""
    all_authors_list = []
    affs_set = set()
    for auth in authorships:
        name = auth.get("author", {}).get("display_name", "")
        if name:
            all_authors_list.append(name)
            if not first_author:
                first_author = name
        for inst in auth.get("institutions", []):
            inst_name = inst.get("display_name")
            if inst_name:
                affs_set.add(inst_name)

    loc = r.get("primary_location") or {}
    source = loc.get("source") or {}
    journal = source.get("display_name", "")

    kw_list = r.get("keywords", [])
    keywords = " ; ".join(
        k.get("keyword", k.get("display_name", ""))
        for k in (kw_list or []) if isinstance(k, dict)
    )

    concepts = r.get("concepts", [])
    categories = " ; ".join(
        c.get("display_name", "") for c in (concepts or [])
        if c.get("level", 99) <= 2
    )

    abstract = reconstruct_abstract(r.get("abstract_inverted_index"))
    title = r.get("display_name", "")

    rec = {
        "source": "openalex",
        "source_id": r.get("id", "").replace("https://openalex.org/", ""),
        "doi": normalize_doi(r.get("doi")),
        "title": title,
        "first_author": first_author,
        "all_authors": " ; ".join(all_authors_list),
        "year": r.get("publication_year", ""),
        "journal": journal,
        "abstract": abstract,
        "language": r.get("language", ""),
        "keywords": keywords,
        "categories": categories,
        "cited_by_count": r.get("cited_by_count", ""),
        "affiliations": " ; ".join(sorted(affs_set)),
    }
    return rec, abstract, title


def extract_references(r):
    """Extract outgoing citation links from referenced_works field.

    Returns list of dicts suitable for citations.csv.
    """
    source_doi = normalize_doi(r.get("doi"))
    source_id = r.get("id", "").replace("https://openalex.org/", "")
    refs = []
    for ref_url in r.get("referenced_works", []) or []:
        ref_oa_id = ref_url.replace("https://openalex.org/", "")
        refs.append({
            "source_doi": source_doi,
            "source_id": source_id,
            "ref_oa_id": ref_oa_id,
        })
    return refs


def query_slug(term):
    """Convert a search term to a safe filename slug."""
    return re.sub(r"[^\w]", "_", term.lower()).strip("_")


# --- Download phase ---

def fetch_query(search_term, delay, limit, existing_ids, pool_file):
    """Fetch all works matching a search term, append raw JSON to pool.

    Returns (n_new, n_skipped) counts.
    """
    cursor = "*"
    total_fetched = 0
    n_new = 0
    batch = []

    while cursor:
        params = {
            "filter": f'default.search:"{search_term}"',
            "select": OA_SELECT,
            "per_page": 200,
            "cursor": cursor,
            "mailto": MAILTO,
        }
        resp = polite_get(OA_API, params=params, delay=delay)
        data = resp.json()

        remaining = resp.headers.get("X-RateLimit-Remaining-USD", "?")
        meta = data.get("meta", {})
        total = meta.get("count", "?")

        for r in data.get("results", []):
            oa_id = r.get("id", "").replace("https://openalex.org/", "")
            if oa_id in existing_ids:
                continue
            existing_ids.add(oa_id)
            batch.append(r)
            n_new += 1

        total_fetched += len(data.get("results", []))

        # Flush batch to pool every 500 records
        if len(batch) >= 500:
            append_to_pool(batch, pool_file)
            batch = []

        print(f"  [{search_term}] {total_fetched}/{total} "
              f"(new: {n_new}, budget: ${remaining})", end="\r")

        cursor = meta.get("next_cursor")
        if limit and total_fetched >= limit:
            break

    # Flush remaining
    if batch:
        append_to_pool(batch, pool_file)

    print()
    return n_new


def dry_run_query(search_term, delay):
    """Check how many results a query would return without fetching."""
    params = {
        "filter": f'default.search:"{search_term}"',
        "per_page": 1,
        "mailto": MAILTO,
    }
    resp = polite_get(OA_API, params=params, delay=delay)
    data = resp.json()
    return data.get("meta", {}).get("count", 0)


# --- Extract phase ---

def extract_from_pool(config):
    """Build openalex_works.csv and citations from pool records.

    Applies tier-based relevance filtering during extraction.
    """
    concept_groups = {
        k: set(v) for k, v in config.get("concept_groups", {}).items()
    }
    tiers = config.get("tiers", {})

    # Build a map: pool filename slug → tier config
    slug_to_tier = {}
    for tier_num, tier_cfg in tiers.items():
        for term in tier_cfg.get("terms", []):
            slug_to_tier[query_slug(term)] = tier_cfg

    # Load all pool records
    print("Loading pool records...")
    all_raw = load_pool_records("openalex")
    print(f"  {len(all_raw)} raw records in pool")

    # Deduplicate by OpenAlex ID
    seen_ids = set()
    unique_raw = []
    for r in all_raw:
        oa_id = r.get("id", "").replace("https://openalex.org/", "")
        if oa_id not in seen_ids:
            seen_ids.add(oa_id)
            unique_raw.append(r)
    print(f"  {len(unique_raw)} unique after dedup")

    # Default: use the least restrictive tier (min_concept_groups=0)
    # Since we can't easily track which pool file a record came from
    # when records are merged, we apply the most lenient filter.
    # Stricter filtering happens in corpus_refine.py.
    default_min = 0

    records = []
    all_refs = []
    n_filtered = 0

    for r in unique_raw:
        rec, abstract, title = build_record(r)

        # Relevance filter (use tier 3 threshold as conservative default
        # for records we can't attribute to a specific tier)
        check_text = abstract if abstract else title
        if default_min > 0 and not passes_relevance(
                check_text, concept_groups, default_min):
            n_filtered += 1
            continue

        records.append(rec)

        # Extract citation links
        refs = extract_references(r)
        all_refs.extend(refs)

    print(f"  {len(records)} records after relevance filter "
          f"({n_filtered} filtered)")
    print(f"  {len(all_refs)} outgoing citation links extracted")

    # Save works CSV
    df = pd.DataFrame(records, columns=WORKS_COLUMNS)
    save_csv(df, os.path.join(CATALOGS_DIR, "openalex_works.csv"))

    # Save OpenAlex-sourced citation links
    if all_refs:
        refs_df = pd.DataFrame(all_refs)
        refs_path = os.path.join(CATALOGS_DIR, "openalex_citations.csv")
        save_csv(refs_df, refs_path)

    return df


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Unified OpenAlex harvester for climate finance")
    parser.add_argument("--tier", type=int, default=0,
                        help="Run only this tier (default: all)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip OpenAlex IDs already in pool")
    parser.add_argument("--pool-only", action="store_true",
                        help="Download to pool, don't build CSV")
    parser.add_argument("--extract-only", action="store_true",
                        help="Build CSV from pool, don't download")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show queries and expected counts")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max records per query (0=all)")
    parser.add_argument("--delay", type=float, default=0.15,
                        help="Delay between requests")
    args = parser.parse_args()

    config = load_query_config()
    tiers = config.get("tiers", {})

    # Filter to requested tier
    if args.tier:
        tiers = {args.tier: tiers[args.tier]}

    if args.extract_only:
        print("=== Extract-only mode: building CSV from pool ===")
        df = extract_from_pool(config)
        print(f"\nDone. {len(df)} works in openalex_works.csv")
        return

    # Load existing pool IDs for resume
    existing_ids = set()
    if args.resume:
        raw_ids = load_pool_ids("openalex")
        # Strip URL prefix to match the short ID format used in fetch_query
        existing_ids = {
            rid.replace("https://openalex.org/", "") for rid in raw_ids
        }
        print(f"Pool contains {len(existing_ids)} existing OpenAlex IDs")

    # Download phase
    grand_total = 0
    for tier_num in sorted(tiers.keys()):
        tier_cfg = tiers[tier_num]
        desc = tier_cfg.get("description", f"Tier {tier_num}")
        terms = tier_cfg.get("terms", [])
        min_groups = tier_cfg.get("min_concept_groups", 0)

        print(f"\n{'=' * 60}")
        print(f"TIER {tier_num}: {desc}")
        print(f"  {len(terms)} queries, min_concept_groups={min_groups}")
        print(f"{'=' * 60}")

        for term in terms:
            slug = query_slug(term)
            pf = pool_path("openalex", slug)

            if args.dry_run:
                count = dry_run_query(term, args.delay)
                print(f"  \"{term}\": {count:,} results")
                grand_total += count
                continue

            print(f"\nQuerying: \"{term}\"")
            n_new = fetch_query(
                term, args.delay, args.limit, existing_ids, pf)
            grand_total += n_new

    if args.dry_run:
        print(f"\n{'=' * 60}")
        print(f"DRY RUN TOTAL: {grand_total:,} results across all queries")
        print(f"(Actual unique count will be lower due to overlap)")
        return

    print(f"\n{'=' * 60}")
    print(f"Download complete. {grand_total} new records added to pool.")

    if not args.pool_only:
        print(f"\n=== Extracting CSV from pool ===")
        df = extract_from_pool(config)
        print(f"\nDone. {len(df)} works in openalex_works.csv")


if __name__ == "__main__":
    main()
