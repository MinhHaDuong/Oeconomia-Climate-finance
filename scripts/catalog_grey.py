#!/usr/bin/env python3
"""Build catalog of grey literature (reports, policy documents).

Combines:
  - Curated seed list from config/grey_sources.yaml
  - World Bank Open Knowledge Repository API search

Produces: data/catalogs/grey_works.csv

Usage:
    python scripts/catalog_grey.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, CONFIG_DIR, WORKS_COLUMNS,
                   get_logger, normalize_doi, polite_get, save_csv,
                   load_collect_config)

log = get_logger("catalog_grey")

# Try to import yaml; fall back to a simple parser if not installed
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SEED_FILE = os.path.join(CONFIG_DIR, "grey_sources.yaml")

WB_SEARCH_URL = "https://openknowledge.worldbank.org/server/api/discover/search/objects"


def load_seed():
    """Load curated grey literature entries from YAML."""
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
    for e in (entries or []):
        records.append({
            "source": "grey",
            "source_id": e.get("doi", e.get("url", "")),
            "doi": normalize_doi(e.get("doi", "")),
            "title": e.get("title", ""),
            "first_author": e.get("author", ""),
            "all_authors": e.get("author", ""),
            "year": str(e.get("year", "")),
            "journal": e.get("source_org", ""),
            "abstract": e.get("abstract", ""),
            "language": e.get("language", "en"),
            "keywords": e.get("keywords", ""),
            "categories": "grey literature",
            "cited_by_count": "",
            "affiliations": e.get("source_org", ""),
        })
    log.info("Loaded %d entries from seed file", len(records))
    return records


def query_worldbank():
    """Search World Bank Open Knowledge Repository."""
    records = []
    page = 0
    page_size = 20
    total = None

    log.info("Querying World Bank OKR...")
    while True:
        params = {
            "query": "climate finance",
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
            raw_metadata = item.get("metadata", {})
            # metadata is a dict of field_name -> list of {value, ...}
            metadata = {}
            if isinstance(raw_metadata, dict):
                for key, entries in raw_metadata.items():
                    vals = []
                    for entry in (entries if isinstance(entries, list) else []):
                        v = entry.get("value", "") if isinstance(entry, dict) else str(entry)
                        if v:
                            vals.append(v)
                    metadata[key] = " ; ".join(vals)
            elif isinstance(raw_metadata, list):
                for m in raw_metadata:
                    key = m.get("key", "")
                    val = m.get("value", "")
                    if key in metadata:
                        metadata[key] += " ; " + val
                    else:
                        metadata[key] = val

            records.append({
                "source": "grey",
                "source_id": item.get("uuid", ""),
                "doi": normalize_doi(metadata.get("dc.identifier.doi", "")),
                "title": metadata.get("dc.title", ""),
                "first_author": metadata.get("dc.contributor.author",
                                             "").split(" ; ")[0],
                "all_authors": metadata.get("dc.contributor.author", ""),
                "year": (metadata.get("dc.date.issued", "") or "")[:4],
                "journal": "World Bank",
                "abstract": metadata.get("dc.description.abstract", ""),
                "language": metadata.get("dc.language.iso", ""),
                "keywords": metadata.get("dc.subject", ""),
                "categories": "grey literature",
                "cited_by_count": "",
                "affiliations": "World Bank",
            })

        page += 1
        fetched = page * page_size
        log.info("  Fetched %d...", fetched)

        # Limit to first 200 results from World Bank
        if fetched >= 200:
            log.info("  Reached 200-item cap for World Bank results.")
            break

    log.info("  Got %d World Bank records", len(records))
    return records


def main():
    collect_cfg = load_collect_config()
    year_min = collect_cfg["year_min"]
    year_max = collect_cfg["year_max"]
    log.info("Year bounds from corpus_collect.yaml: %d–%d", year_min, year_max)

    all_records = []
    all_records.extend(load_seed())
    all_records.extend(query_worldbank())

    if not all_records:
        log.info("No grey literature records found.")
        return

    df = pd.DataFrame(all_records, columns=WORKS_COLUMNS)

    # Apply year bounds — extract numeric year and filter
    df["_year_num"] = pd.to_numeric(
        df["year"].astype(str).str[:4], errors="coerce"
    )
    n_before = len(df)
    df = df[df["_year_num"].isna() | (
        (df["_year_num"] >= year_min) & (df["_year_num"] <= year_max)
    )].copy()
    df = df.drop(columns="_year_num")
    n_filtered = n_before - len(df)
    if n_filtered:
        log.info("Year filter removed %d records outside %d–%d",
                 n_filtered, year_min, year_max)

    # Deduplicate by title (rough)
    df["_norm_title"] = df["title"].str.lower().str.strip()
    df = df.drop_duplicates(subset="_norm_title", keep="first")
    df = df.drop(columns="_norm_title")

    save_csv(df, os.path.join(CATALOGS_DIR, "grey_works.csv"))
    log.info("Summary: %d grey literature works", len(df))


if __name__ == "__main__":
    main()
