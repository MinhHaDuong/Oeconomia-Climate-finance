#!/usr/bin/env python3
"""Build catalog of grey literature (reports, policy documents).

Combines:
  - Curated seed list from config/grey_sources.yaml
  - World Bank Open Knowledge Repository API search

Produces: data/catalogs/grey_works.csv

Usage:
    python scripts/catalog_grey.py
"""

import argparse
import os

import pandas as pd
from utils import (
    CATALOGS_DIR,
    CONFIG_DIR,
    WORKS_COLUMNS,
    get_logger,
    load_collect_config,
    normalize_doi,
    polite_get,
    save_csv,
)

log = get_logger("catalog_grey")

# Try to import yaml; fall back to a simple parser if not installed
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SEED_FILE = os.path.join(CONFIG_DIR, "grey_sources.yaml")

WB_SEARCH_URL = "https://openknowledge.worldbank.org/server/api/discover/search/objects"
WB_MAX_RESULTS = 500  # safety cap — if hit, query needs splitting


def load_seed(year_min=None, year_max=None):
    """Load curated grey literature entries from YAML, filtered by year bounds."""
    if not os.path.exists(SEED_FILE):
        log.info("No seed file at %s (optional). "
                 "Create one to add known grey literature.", SEED_FILE)
        return []

    if not HAS_YAML:
        log.warning("PyYAML not installed. Install with: pip install pyyaml")
        log.warning("Skipping seed file.")
        return []

    with open(SEED_FILE, encoding="utf-8") as f:
        entries = yaml.safe_load(f)

    records = []
    skipped = 0
    for e in (entries or []):
        year_str = str(e.get("year", ""))
        year_num = int(year_str[:4]) if year_str[:4].isdigit() else None
        if year_num is not None:
            if year_min and year_num < year_min:
                skipped += 1
                continue
            if year_max and year_num > year_max:
                skipped += 1
                continue
        records.append({
            "source": "grey",
            "source_id": e.get("doi", e.get("url", "")),
            "doi": normalize_doi(e.get("doi", "")),
            "title": e.get("title", ""),
            "first_author": e.get("author", ""),
            "all_authors": e.get("author", ""),
            "year": year_str,
            "journal": e.get("source_org", ""),
            "abstract": e.get("abstract", ""),
            "language": e.get("language", "en"),
            "keywords": e.get("keywords", ""),
            "categories": "grey literature",
            "cited_by_count": "",
            "affiliations": e.get("source_org", ""),
        })
    log.info("Loaded %d entries from seed file (skipped %d outside %s–%s)",
             len(records), skipped, year_min, year_max)
    return records


def query_worldbank(wb_queries, year_min=None, year_max=None):
    """Search World Bank Open Knowledge Repository.

    Args:
        wb_queries: Search query string or list of strings
                    (from config/corpus_collect.yaml).
        year_min:   Optional minimum publication year (inclusive).
        year_max:   Optional maximum publication year (inclusive).

    """
    if isinstance(wb_queries, str):
        wb_queries = [wb_queries]

    all_records = []
    seen_ids = set()

    for wb_query in wb_queries:
        records = _query_worldbank_single(wb_query, year_min, year_max)
        new = 0
        for r in records:
            if r["source_id"] and r["source_id"] in seen_ids:
                continue
            seen_ids.add(r["source_id"])
            all_records.append(r)
            new += 1
        log.info("  Query %r: %d results, %d new (after dedup)",
                 wb_query, len(records), new)

    log.info("  World Bank total: %d unique records from %d queries",
             len(all_records), len(wb_queries))
    return all_records


def _parse_wb_metadata(raw_metadata) -> dict:
    """Normalise the two metadata shapes returned by the World Bank API.

    The API may return either:
    - a dict mapping field names to lists of ``{"value": ..., ...}`` dicts, or
    - a flat list of ``{"key": ..., "value": ...}`` dicts.

    Returns a plain ``{field: "val1 ; val2"}`` dict in both cases.
    """
    metadata: dict = {}
    if isinstance(raw_metadata, dict):
        for key, entries in raw_metadata.items():
            vals = [
                entry.get("value", "") if isinstance(entry, dict) else str(entry)
                for entry in (entries if isinstance(entries, list) else [])
                if (entry.get("value", "") if isinstance(entry, dict) else str(entry))
            ]
            metadata[key] = " ; ".join(vals)
    elif isinstance(raw_metadata, list):
        for m in raw_metadata:
            key = m.get("key", "")
            val = m.get("value", "")
            metadata[key] = (metadata[key] + " ; " + val) if key in metadata else val
    return metadata


def _wb_record_from_metadata(metadata: dict, item: dict, year_str: str) -> dict:
    """Build a works-catalog record from parsed World Bank metadata."""
    return {
        "source": "grey",
        "source_id": item.get("uuid", ""),
        "doi": normalize_doi(metadata.get("dc.identifier.doi", "")),
        "title": metadata.get("dc.title", ""),
        "first_author": metadata.get("dc.contributor.author", "").split(" ; ")[0],
        "all_authors": metadata.get("dc.contributor.author", ""),
        "year": year_str,
        "journal": "World Bank",
        "abstract": metadata.get("dc.description.abstract", ""),
        "language": metadata.get("dc.language.iso", ""),
        "keywords": metadata.get("dc.subject", ""),
        "categories": "grey literature",
        "cited_by_count": "",
        "affiliations": "World Bank",
    }


def _query_worldbank_single(wb_query, year_min=None, year_max=None):
    """Run a single World Bank query. Called by query_worldbank()."""
    records = []
    page = 0
    page_size = 20
    total = None

    # Append server-side year filtering (DSpace 7 / Solr syntax)
    query = wb_query
    if year_min and year_max:
        query += f" AND dc.date.issued:[{year_min} TO {year_max}]"
    elif year_min:
        query += f" AND dc.date.issued:[{year_min} TO *]"
    elif year_max:
        query += f" AND dc.date.issued:[* TO {year_max}]"

    log.info("Querying World Bank OKR...")
    log.info("  Query: %s", query)
    while True:
        params = {
            "query": query,
            "size": page_size,
            "page": page,
            "dsoType": "item",
        }
        try:
            resp = polite_get(WB_SEARCH_URL, params=params, delay=0.5)
            data = resp.json()
        except Exception as e:
            log.error("  World Bank API error: %s", e)
            break

        embedded = data.get("_embedded", {})
        objects = embedded.get("searchResult", {}).get("_embedded", {}).get(
            "objects", [])

        if total is None:
            total = data.get("_embedded", {}).get("searchResult", {}).get(
                "totalElements", "?")
            log.info("  Total results: %s", total)

        if not objects:
            break

        for obj in objects:
            item = obj.get("_embedded", {}).get("indexableObject", {})
            metadata = _parse_wb_metadata(item.get("metadata", {}))

            year_str = (metadata.get("dc.date.issued", "") or "")[:4]
            # Client-side year filter as safety net (server-side may not
            # support dc.date.issued range syntax on all DSpace instances)
            year_num = int(year_str) if year_str.isdigit() else None
            if year_num is not None:
                if year_min and year_num < year_min:
                    continue
                if year_max and year_num > year_max:
                    continue
            records.append(_wb_record_from_metadata(metadata, item, year_str))

        page += 1
        fetched = page * page_size
        log.info("  Fetched %d...", fetched)

        if fetched >= WB_MAX_RESULTS:
            log.warning("  Reached %d-item safety cap. "
                        "Query may need splitting to avoid truncation.",
                        WB_MAX_RESULTS)
            break

    # Log whether we fetched everything
    if isinstance(total, int) and total > len(records):
        log.warning("  World Bank: fetched %d of %d total results — "
                    "some records were truncated. "
                    "Consider splitting the query by decade.",
                    len(records), total)
    log.info("  Got %d World Bank records", len(records))
    return records


def main():
    collect_cfg = load_collect_config()
    year_min = collect_cfg["year_min"]
    year_max = collect_cfg["year_max"]
    log.info("Year bounds from corpus_collect.yaml: %d–%d", year_min, year_max)

    wb_queries = collect_cfg["queries"]["worldbank"]

    all_records = []
    all_records.extend(load_seed(year_min=year_min, year_max=year_max))
    all_records.extend(query_worldbank(wb_queries, year_min=year_min,
                                       year_max=year_max))

    if not all_records:
        log.info("No grey literature records found.")
        return

    df = pd.DataFrame(all_records, columns=WORKS_COLUMNS)

    # Deduplicate by title (rough)
    df["_norm_title"] = df["title"].str.lower().str.strip()
    df = df.drop_duplicates(subset="_norm_title", keep="first")
    df = df.drop(columns="_norm_title")

    save_csv(df, os.path.join(CATALOGS_DIR, "grey_works.csv"))
    log.info("Summary: %d grey literature works", len(df))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
