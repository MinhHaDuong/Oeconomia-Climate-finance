#!/usr/bin/env python3
"""Query Scopus API for climate finance literature.

Requires SCOPUS_API_KEY environment variable (free for institutional users).
Produces: data/catalogs/scopus_works.csv

Usage:
    export SCOPUS_API_KEY="your-key"
    python scripts/catalog_scopus.py [--limit N]
"""

import argparse
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, WORKS_COLUMNS, normalize_doi, save_csv)

SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"


def main():
    parser = argparse.ArgumentParser(description="Query Scopus for climate finance")
    parser.add_argument("--limit", type=int, default=0, help="Max records (0=all)")
    args = parser.parse_args()

    api_key = os.environ.get("SCOPUS_API_KEY", "")
    if not api_key:
        print("""Scopus API key not found. To use this script:

1. Register at https://dev.elsevier.com/
2. Create an API key (free for CNRS institutional users)
3. Set environment variable:
       export SCOPUS_API_KEY="your-key-here"
4. Ensure you are on your institutional network (or VPN)
5. Re-run this script

Skipping Scopus catalog (this is optional).""")
        return

    query = 'TITLE-ABS-KEY("climate finance" OR "finance climat" OR "finance climatique")'
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }

    records = []
    start = 0
    count = 25
    total = None

    while True:
        params = {
            "query": query,
            "start": start,
            "count": count,
        }
        resp = requests.get(SCOPUS_SEARCH_URL, params=params, headers=headers,
                            timeout=30)
        if resp.status_code == 401:
            print("ERROR: Authentication failed. Check your API key and network.")
            return
        if resp.status_code == 429:
            print("Rate limited. Waiting 60s...")
            time.sleep(60)
            continue
        resp.raise_for_status()

        data = resp.json().get("search-results", {})
        if total is None:
            total = int(data.get("opensearch:totalResults", 0))
            print(f"Total results: {total}")

        entries = data.get("entry", [])
        if not entries:
            break

        for e in entries:
            doi = normalize_doi(e.get("prism:doi"))
            records.append({
                "source": "scopus",
                "source_id": e.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
                "doi": doi,
                "title": e.get("dc:title", ""),
                "first_author": e.get("dc:creator", ""),
                "all_authors": e.get("dc:creator", ""),
                "year": (e.get("prism:coverDate", "") or "")[:4],
                "journal": e.get("prism:publicationName", ""),
                "abstract": e.get("dc:description", ""),
                "language": "",
                "keywords": "",
                "categories": e.get("prism:aggregationType", ""),
                "cited_by_count": e.get("citedby-count", ""),
                "affiliations": e.get("affiliation", [{}])[0].get(
                    "affilname", "") if e.get("affiliation") else "",
            })

        start += count
        print(f"  Fetched {start}/{total}")

        if args.limit and start >= args.limit:
            break
        if start >= total:
            break

        time.sleep(0.5)

    if not records:
        print("No records found.")
        return

    df = pd.DataFrame(records, columns=WORKS_COLUMNS)
    save_csv(df, os.path.join(CATALOGS_DIR, "scopus_works.csv"))

    print(f"\nSummary: {len(df)} works")


if __name__ == "__main__":
    main()
