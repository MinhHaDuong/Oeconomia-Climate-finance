"""OpenAlex download pool and API budget management.

Extracted from catalog_openalex.py (#620) to keep each module under 500 lines.

Functions here handle:
- API filter construction (build_filter)
- API pagination and download (fetch_query, dry_run_query, _download_tiers)
- Budget tracking (capture_budget, budget_exhausted)
- Per-query sidecar dates (load_query_dates, save_query_dates, ...)
- Query slug generation (query_slug)
"""

import json
import os
import re
from datetime import date

from utils import (
    MAILTO,
    OPENALEX_API_KEY,
    POOL_DIR,
    append_to_pool,
    get_logger,
    polite_get,
    pool_path,
)

log = get_logger("openalex_pool")

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


def query_slug(term):
    """Convert a search term to a safe filename slug."""
    return re.sub(r"[^\w]", "_", term.lower()).strip("_")


# --- Download phase ---

def fetch_query(search_term, delay, limit, existing_ids, pool_file,
                from_date=None, year_min=None, year_max=None):
    """Fetch all works matching a search term, append raw JSON to pool.

    Parameters
    ----------
    search_term : str
        OpenAlex search query string.
    delay : float
        Polite delay between API requests (seconds).
    limit : int
        Maximum works to fetch (0 = unlimited).
    existing_ids : set
        OpenAlex IDs already in the pool (skipped on append).
    pool_file : str
        Path to the gzipped JSONL pool file for raw responses.
    from_date : str, optional
        YYYY-MM-DD to restrict to recently-created works.
    year_min : int, optional
        Minimum publication year (inclusive).
    year_max : int, optional
        Maximum publication year (inclusive).

    Returns
    -------
    tuple
        (n_new, out_of_budget) — count of new records and whether
        the API budget was exhausted during pagination.

    """
    cursor = "*"
    total_fetched = 0
    n_new = 0
    batch = []
    remaining = "?"

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


def dry_run_query(search_term, delay, from_date=None, year_min=None,
                  year_max=None):
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


def _download_tiers(tiers, args, existing_ids, query_dates, global_from_date,
                    year_min, year_max, today):
    """Run the download phase across all tiers.

    Returns (total, completed, skipped, budget_start).
    """
    grand_total = 0
    queries_completed = 0
    queries_skipped = 0
    stop_no_budget = False
    budget_start = None

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

            if budget_start is None:
                probe_params = {
                    "filter": build_filter(term, from_date,
                                           year_min=year_min, year_max=year_max),
                    "per_page": 1, "mailto": MAILTO,
                }
                if OPENALEX_API_KEY:
                    probe_params["api_key"] = OPENALEX_API_KEY
                probe_resp = polite_get(OA_API, params=probe_params,
                                        delay=args.delay, max_retries=1)
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

            query_dates[slug] = today
            save_query_dates(query_dates)

            if out_of_budget:
                log.warning("Budget exhausted — skipping remaining queries.")
                stop_no_budget = True
                break

    return grand_total, queries_completed, queries_skipped, budget_start
