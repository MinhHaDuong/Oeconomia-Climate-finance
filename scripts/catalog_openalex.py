#!/usr/bin/env python3
"""Unified OpenAlex harvester for climate finance literature.

Replaces the former two-script approach (catalog_openalex.py +
catalog_openalex_historical.py) with a single tiered query engine.

Query terms are defined in config/openalex_queries.yaml (4 tiers).
Raw API responses are stored in pool/openalex/ (gzipped JSONL, append-only).
Extracted records go to catalogs/openalex_works.csv.

Usage:
    python scripts/catalog_openalex.py [OPTIONS]

    --tier N          Run only tier N (default: all tiers)
    --resume          Skip OpenAlex IDs already in the pool
    --from-date D     Only fetch works created on or after YYYY-MM-DD
    --pool-only       Download to pool, don't build CSV
    --extract-only    Build CSV from existing pool, don't download
    --dry-run         Show queries and expected counts, don't fetch
    --limit N         Max records per query (0=all)
    --delay S         Delay between requests (default: 0.15)

When --resume is used without --from-date, the script auto-detects the date
of the last successful run from a sidecar file (data/pool/openalex/_last_run.txt)
so that only newly-created OpenAlex records are paginated. This avoids wasting
the daily API budget re-paginating unchanged results.
"""

import argparse
import os
import re
from datetime import date

import pandas as pd
import yaml
from openalex_pool import (
    OA_API,
    LAST_RUN_PATH,
    SIDECAR_PATH,
    build_filter,
    budget_exhausted,
    capture_budget,
    dry_run_query,
    fetch_query,
    load_query_dates,
    query_slug,
    read_last_run_date,
    save_query_dates,
    write_last_run_date,
    _download_tiers,
)
from utils import (
    CATALOGS_DIR,
    CONFIG_DIR,
    MAILTO,
    OPENALEX_API_KEY,
    WORKS_COLUMNS,
    get_logger,
    load_collect_config,
    load_pool_ids,
    load_pool_records,
    normalize_doi,
    polite_get,
    reconstruct_abstract,
    save_csv,
)

log = get_logger("catalog_openalex")


def load_query_config():
    """Load tiered query configuration from YAML."""
    yaml_path = os.path.join(CONFIG_DIR, "openalex_queries.yaml")
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
    for tier_cfg in tiers.values():
        for term in tier_cfg.get("terms", []):
            slug_to_tier[query_slug(term)] = tier_cfg

    # Load all pool records
    log.info("Loading pool records...")
    all_raw = load_pool_records("openalex")
    log.info("%d raw records in pool", len(all_raw))

    # Deduplicate by OpenAlex ID
    seen_ids = set()
    unique_raw = []
    for r in all_raw:
        oa_id = r.get("id", "").replace("https://openalex.org/", "")
        if oa_id not in seen_ids:
            seen_ids.add(oa_id)
            unique_raw.append(r)
    log.info("%d unique after dedup", len(unique_raw))

    # Default: use the least restrictive tier (min_concept_groups=0)
    # Since we can't easily track which pool file a record came from
    # when records are merged, we apply the most lenient filter.
    # Stricter filtering happens in corpus_filter.py.
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

    log.info("%d records after relevance filter (%d filtered)",
             len(records), n_filtered)
    log.info("%d outgoing citation links extracted", len(all_refs))

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
    parser.add_argument("--from-date", type=str, default=None,
                        help="Only fetch works created on/after YYYY-MM-DD "
                             "(auto-detected from last run when --resume)")
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
    collect_cfg = load_collect_config()
    year_min = collect_cfg["year_min"]
    year_max = collect_cfg["year_max"]
    log.info("Year bounds from corpus_collect.yaml: %d–%d", year_min, year_max)
    tiers = config.get("tiers", {})

    # Filter to requested tier
    if args.tier:
        tiers = {args.tier: tiers[args.tier]}

    if args.extract_only:
        log.info("=== Extract-only mode: building CSV from pool ===")
        df = extract_from_pool(config)
        log.info("Done. %d works in openalex_works.csv", len(df))
        return

    # Load per-query sidecar dates for incremental runs
    query_dates = load_query_dates() if args.resume else {}
    global_from_date = args.from_date  # explicit --from-date overrides per-query

    if global_from_date:
        log.info("Global date filter: from_created_date >= %s", global_from_date)
    elif query_dates:
        n_dated = sum(1 for k in query_dates if k != "_global")
        if "_global" in query_dates:
            log.info("Sidecar: global last-run date %s", query_dates['_global'])
        else:
            log.info("Sidecar: %d queries with per-query dates", n_dated)
    else:
        log.info("No sidecar found -- full pagination for all queries")

    if not OPENALEX_API_KEY:
        log.warning("No OPENALEX_API_KEY found -- using free tier (lower budget)")

    # Load existing pool IDs for resume
    existing_ids = set()
    if args.resume:
        raw_ids = load_pool_ids("openalex")
        existing_ids = {
            rid.replace("https://openalex.org/", "") for rid in raw_ids
        }
        log.info("Pool contains %d existing OpenAlex IDs", len(existing_ids))

    # Capture budget at start of run
    budget_start = None
    budget_end = None
    today = date.today().isoformat()

    # Download phase
    grand_total, queries_completed, queries_skipped, budget_start = _download_tiers(
        tiers, args, existing_ids, query_dates, global_from_date,
        year_min, year_max, today,
    )

    if args.dry_run:
        log.info("=" * 60)
        log.info("DRY RUN TOTAL: %s results across all queries", f"{grand_total:,}")
        log.info("(Actual unique count will be lower due to overlap)")
        return

    # Capture budget at end of run via a lightweight probe
    # Skip when budget was already exhausted — no point probing again
    if budget_exhausted(budget_start or "?"):
        budget_end = budget_start
    else:
        try:
            end_params = {"filter": 'default.search:"climate finance"',
                          "per_page": 1, "mailto": MAILTO}
            if OPENALEX_API_KEY:
                end_params["api_key"] = OPENALEX_API_KEY
            end_resp = polite_get(OA_API, params=end_params, delay=args.delay)
            budget_end = capture_budget(end_resp)
        except Exception:
            budget_end = "?"

    log.info("=" * 60)
    log.info("Download complete. %d new records added to pool.", grand_total)
    log.info("Queries: %d completed, %d skipped", queries_completed, queries_skipped)
    log.info("Budget: $%s -> $%s", budget_start, budget_end)

    # Also write legacy sidecar for backwards compatibility
    write_last_run_date(date_str=today)
    log.info("Sidecar updated: %d queries dated %s", queries_completed, today)

    if not args.pool_only:
        log.info("=== Extracting CSV from pool ===")
        df = extract_from_pool(config)
        log.info("Done. %d works in openalex_works.csv", len(df))


if __name__ == "__main__":
    main()
