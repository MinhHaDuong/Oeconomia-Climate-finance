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
import json
import os
import re
import sys
from datetime import date

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CONFIG_DIR, CATALOGS_DIR, WORKS_COLUMNS, MAILTO, OPENALEX_API_KEY,
                   get_logger, normalize_doi, reconstruct_abstract, polite_get,
                   save_csv, pool_path, append_to_pool, load_pool_ids,
                   load_pool_records, POOL_DIR, load_collect_config)

log = get_logger("catalog_openalex")

OA_API = "https://api.openalex.org/works"

# Sidecar file recording per-query completion dates.
# Used by --resume to auto-detect --from-date per query, so completed
# queries are skipped or date-filtered independently.
SIDECAR_PATH = os.path.join(POOL_DIR, "openalex", "_query_dates.json")

# Legacy single-date sidecar (for backwards compatibility)
LAST_RUN_PATH = os.path.join(POOL_DIR, "openalex", "_last_run.txt")

# Fields to request from OpenAlex (reduces payload, includes referenced_works)
OA_SELECT = ",".join([
    "id", "doi", "display_name", "publication_year", "authorships",
    "primary_location", "abstract_inverted_index", "language", "keywords",
    "concepts", "cited_by_count", "referenced_works", "type",
])


def build_filter(search_term, from_date=None, year_min=None, year_max=None):
    """Build the OpenAlex filter parameter string.

    Args:
        search_term: The search query text.
        from_date:   Optional YYYY-MM-DD string to limit to works created
                     on or after this date (OpenAlex from_created_date filter).
        year_min:    Optional minimum publication year (inclusive).
        year_max:    Optional maximum publication year (inclusive).

    Returns:
        Filter string for the OpenAlex API ``filter`` parameter.
    """
    f = f'default.search:"{search_term}"'
    if from_date:
        f += f",from_created_date:{from_date}"
    if year_min is not None and year_max is not None:
        # OpenAlex publication_year filter: >N means strictly greater,
        # so >1989 gives >=1990; <2025 gives <=2024.
        f += f",publication_year:>{year_min - 1},publication_year:<{year_max + 1}"
    return f


def load_query_dates(path=None):
    """Load per-query completion dates from sidecar JSON.

    Returns dict {query_slug: "YYYY-MM-DD"} or empty dict if missing.
    Falls back to legacy single-date file if JSON doesn't exist.
    """
    if path is None:
        path = SIDECAR_PATH
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    # Fallback: legacy single-date sidecar → treat as global date for all queries
    if os.path.exists(LAST_RUN_PATH):
        with open(LAST_RUN_PATH) as fh:
            d = fh.read().strip()
        if d:
            return {"_global": d}
    return {}


def save_query_dates(dates, path=None):
    """Save per-query completion dates to sidecar JSON."""
    if path is None:
        path = SIDECAR_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(dates, fh, indent=2, sort_keys=True)


def read_last_run_date(path=None):
    """Read the global last-run date (legacy compat).

    Returns the date string (YYYY-MM-DD) or None if no sidecar exists.
    """
    if path is None:
        path = LAST_RUN_PATH
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        content = fh.read().strip()
    return content if content else None


def write_last_run_date(path=None, date_str=None):
    """Write today's date to the legacy sidecar file."""
    if path is None:
        path = LAST_RUN_PATH
    if date_str is None:
        date_str = date.today().isoformat()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(date_str + "\n")


def capture_budget(resp):
    """Extract remaining API budget from response headers.

    Returns the value of X-RateLimit-Remaining-USD or '?' if absent.
    """
    return resp.headers.get("X-RateLimit-Remaining-USD", "?")


def budget_exhausted(remaining):
    """Return True if the API budget is known to be zero or negative."""
    if remaining == "?":
        return False
    try:
        return float(remaining) <= 0
    except (ValueError, TypeError):
        return False


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


def query_slug(term):
    """Convert a search term to a safe filename slug."""
    return re.sub(r"[^\w]", "_", term.lower()).strip("_")


# --- Download phase ---

def fetch_query(search_term, delay, limit, existing_ids, pool_file,
                from_date=None, year_min=None, year_max=None):
    """Fetch all works matching a search term, append raw JSON to pool.

    Args:
        from_date: Optional YYYY-MM-DD to restrict to recently-created works.
        year_min:  Optional minimum publication year (inclusive).
        year_max:  Optional maximum publication year (inclusive).

    Returns (n_new, out_of_budget) — count of new records and whether
    the API budget was exhausted during pagination.
    """
    cursor = "*"
    total_fetched = 0
    n_new = 0
    batch = []

    while cursor:
        params = {
            "filter": build_filter(search_term, from_date,
                                   year_min=year_min, year_max=year_max),
            "select": OA_SELECT,
            "per_page": 200,
            "cursor": cursor,
            "mailto": MAILTO,
        }
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY
        resp = polite_get(OA_API, params=params, delay=delay)

        if resp.status_code == 429:
            remaining = capture_budget(resp)
            log.warning("Rate limited during pagination, stopping query.")
            break

        data = resp.json()

        remaining = capture_budget(resp)
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

        log.info("[%s] %d/%s (new: %d, budget: $%s)",
                 search_term, total_fetched, total, n_new, remaining)

        if budget_exhausted(remaining):
            log.warning("API budget exhausted ($%s remaining), stopping.", remaining)
            break

        cursor = meta.get("next_cursor")
        if limit and total_fetched >= limit:
            break

    # Flush remaining
    if batch:
        append_to_pool(batch, pool_file)

    return n_new, budget_exhausted(remaining)


def dry_run_query(search_term, delay, from_date=None, year_min=None, year_max=None):
    """Check how many results a query would return without fetching."""
    params = {
        "filter": build_filter(search_term, from_date,
                               year_min=year_min, year_max=year_max),
        "per_page": 1,
        "mailto": MAILTO,
    }
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
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
    grand_total = 0
    queries_completed = 0
    queries_skipped = 0
    stop_no_budget = False

    for tier_num in sorted(tiers.keys()):
        if stop_no_budget:
            break
        tier_cfg = tiers[tier_num]
        desc = tier_cfg.get("description", f"Tier {tier_num}")
        terms = tier_cfg.get("terms", [])
        min_groups = tier_cfg.get("min_concept_groups", 0)

        log.info("=" * 60)
        log.info("TIER %s: %s", tier_num, desc)
        log.info("%d queries, min_concept_groups=%d", len(terms), min_groups)
        log.info("=" * 60)

        for term in terms:
            slug = query_slug(term)
            pf = pool_path("openalex", slug)

            # Resolve from_date for this query:
            # explicit --from-date > per-query sidecar > global sidecar > None
            if global_from_date:
                from_date = global_from_date
            elif slug in query_dates:
                from_date = query_dates[slug]
            elif "_global" in query_dates:
                from_date = query_dates["_global"]
            else:
                from_date = None

            if args.dry_run:
                count = dry_run_query(term, args.delay, from_date,
                                      year_min=year_min, year_max=year_max)
                date_info = f" (since {from_date})" if from_date else ""
                log.info('"%s": %s results%s', term, f"{count:,}", date_info)
                grand_total += count
                continue

            # Probe budget before first real query
            if budget_start is None:
                probe_params = {
                    "filter": build_filter(term, from_date,
                                           year_min=year_min, year_max=year_max),
                    "per_page": 1, "mailto": MAILTO,
                }
                if OPENALEX_API_KEY:
                    probe_params["api_key"] = OPENALEX_API_KEY
                probe_resp = polite_get(OA_API, params=probe_params,
                                        delay=args.delay)
                budget_start = capture_budget(probe_resp)
                if probe_resp.status_code == 429:
                    log.warning("Rate limited on budget probe — budget exhausted.")
                    budget_start = "0"
                log.info("Budget at start: $%s", budget_start)
                if budget_exhausted(budget_start):
                    log.warning("Budget already exhausted at start — aborting.")
                    stop_no_budget = True
                    break

            date_info = f" (since {from_date})" if from_date else ""
            log.info('Querying: "%s"%s', term, date_info)
            n_new, out_of_budget = fetch_query(
                term, args.delay, args.limit, existing_ids, pf,
                from_date=from_date, year_min=year_min, year_max=year_max)
            grand_total += n_new
            queries_completed += 1

            # Record per-query completion date
            query_dates[slug] = today
            save_query_dates(query_dates)

            if out_of_budget:
                log.warning("Budget exhausted — skipping remaining queries.")
                stop_no_budget = True
                break

    if args.dry_run:
        log.info("=" * 60)
        log.info("DRY RUN TOTAL: %s results across all queries", f"{grand_total:,}")
        log.info("(Actual unique count will be lower due to overlap)")
        return

    # Capture budget at end of run via a lightweight probe
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
