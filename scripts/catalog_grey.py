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
                   normalize_doi, polite_get, save_csv)

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
        print(f"No seed file at {SEED_FILE} (optional). "
              "Create one to add known grey literature.")
        return []

    if not HAS_YAML:
        print("PyYAML not installed. Install with: pip install pyyaml")
        print("Skipping seed file.")
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
    print(f"Loaded {len(records)} entries from seed file")
    return records


def query_worldbank():
    """Search World Bank Open Knowledge Repository."""
    records = []
    page = 0
    page_size = 20
    total = None

    print("Querying World Bank OKR...")
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
            print(f"  World Bank API error: {e}")
            break

        embedded = data.get("_embedded", {})
        objects = embedded.get("searchResult", {}).get("_embedded", {}).get(
            "objects", [])

        if total is None:
            total = data.get("_embedded", {}).get("searchResult", {}).get(
                "totalElements", "?")
            print(f"  Total results: {total}")

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
        print(f"  Fetched {fetched}...")

        # Limit to first 200 results from World Bank
        if fetched >= 200:
            print("  Reached 200-item cap for World Bank results.")
            break

    print(f"  Got {len(records)} World Bank records")
    return records


def main():
    all_records = []
    all_records.extend(load_seed())
    all_records.extend(query_worldbank())

    if not all_records:
        print("No grey literature records found.")
        return

    df = pd.DataFrame(all_records, columns=WORKS_COLUMNS)

    # Deduplicate by title (rough)
    df["_norm_title"] = df["title"].str.lower().str.strip()
    df = df.drop_duplicates(subset="_norm_title", keep="first")
    df = df.drop(columns="_norm_title")

    save_csv(df, os.path.join(CATALOGS_DIR, "grey_works.csv"))
    print(f"\nSummary: {len(df)} grey literature works")


if __name__ == "__main__":
    main()
