#!/usr/bin/env python3
"""Harvest climate finance literature under its pre-2009 names from OpenAlex.

Searches for CDM, GEF, carbon finance, adaptation financing, etc. — the
vocabulary used before "climate finance" became the standard term (~2009).
No year cap: lets the data show when these literatures thin out naturally.

Relevance filter: abstract (or title) must mention at least 2 of 4 concept
groups (climate, finance, development, environment).

Deduplicates against existing openalex_works.csv.

Produces: data/catalogs/openalex_historical_works.csv

Usage:
    python scripts/catalog_openalex_historical.py [--limit N] [--delay S] [--resume]
"""

import argparse
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, WORKS_COLUMNS, MAILTO,
                   normalize_doi, reconstruct_abstract, polite_get,
                   save_csv, load_checkpoint, append_checkpoint,
                   delete_checkpoint)

CHECKPOINT = os.path.join(CATALOGS_DIR, ".openalex_historical_checkpoint.jsonl")

# --- Search terms (no year cap) ---
HISTORICAL_QUERIES = [
    # Kyoto mechanisms
    "Clean Development Mechanism",
    "CDM climate",
    "Kyoto mechanism finance",
    # Adaptation/mitigation financing
    "adaptation financing climate",
    "adaptation fund climate",
    "mitigation finance",
    "mitigation investment climate",
    # Institutions
    "Global Environment Facility climate",
    # Carbon markets
    "carbon finance",
    "carbon market development",
    # Development-era framing
    "climate aid development",
    "environmental finance developing",
    "green investment climate",
]

# --- Relevance filter: 2-of-4 concept groups ---
CONCEPT_GROUPS = {
    "climate": {"climate", "emission", "greenhouse", "warming", "carbon",
                "mitigation", "adaptation", "ghg", "co2"},
    "finance": {"finance", "fund", "investment", "cost", "market", "aid",
                "grant", "loan", "subsidy", "fiscal", "monetary", "budget"},
    "development": {"development", "developing", "country", "nation",
                    "capacity", "transfer", "poverty", "oda"},
    "environment": {"environment", "energy", "renewable", "sustainable",
                    "conservation", "ecology", "biodiversity", "forest"},
}
MIN_GROUPS = 2


def passes_relevance(text):
    """Check if text mentions at least MIN_GROUPS concept groups."""
    if not text:
        return False
    words = set(re.findall(r'[a-z]{3,}', text.lower()))
    groups_hit = sum(1 for group_words in CONCEPT_GROUPS.values()
                     if words & group_words)
    return groups_hit >= MIN_GROUPS


def build_record(r):
    """Build a record dict from an OpenAlex result (same as catalog_openalex.py)."""
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
    keywords = " ; ".join(k.get("display_name", "") for k in (kw_list or []))

    concepts = r.get("concepts", [])
    categories = " ; ".join(
        c.get("display_name", "") for c in (concepts or [])
        if c.get("level", 99) <= 2
    )

    abstract = reconstruct_abstract(r.get("abstract_inverted_index"))
    title = r.get("display_name", "")

    return {
        "source": "openalex_historical",
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
    }, abstract, title


def fetch_historical(search_term, delay, limit, existing_ids, existing_dois):
    """Fetch works matching a search term, applying relevance filter."""
    records = []
    cursor = "*"
    total_fetched = 0
    total_relevant = 0
    total_skipped_dup = 0
    total_skipped_irrelevant = 0

    while cursor:
        params = {
            "filter": f'default.search:"{search_term}"',
            "per_page": 200,
            "cursor": cursor,
            "mailto": MAILTO,
        }
        resp = polite_get("https://api.openalex.org/works", params=params,
                          delay=delay)
        data = resp.json()

        remaining = resp.headers.get("X-RateLimit-Remaining-USD", "?")
        meta = data.get("meta", {})
        total = meta.get("count", "?")

        for r in data.get("results", []):
            oa_id = r.get("id", "").replace("https://openalex.org/", "")
            if oa_id in existing_ids:
                total_skipped_dup += 1
                continue

            # Also skip if DOI already in main corpus
            doi = normalize_doi(r.get("doi"))
            if doi and doi in existing_dois:
                existing_ids.add(oa_id)
                total_skipped_dup += 1
                continue

            existing_ids.add(oa_id)

            rec, abstract, title = build_record(r)

            # Relevance filter: check abstract, fall back to title
            check_text = abstract if abstract else title
            if not passes_relevance(check_text):
                total_skipped_irrelevant += 1
                continue

            records.append(rec)
            total_relevant += 1

        total_fetched += len(data.get("results", []))
        print(f"  [{search_term}] {total_fetched}/{total} "
              f"(relevant: {total_relevant}, dup: {total_skipped_dup}, "
              f"irrelevant: {total_skipped_irrelevant}, budget: ${remaining})")

        # Checkpoint every 2000 records
        if len(records) >= 2000:
            append_checkpoint(records, CHECKPOINT)
            records = []

        cursor = meta.get("next_cursor")

        if limit and total_fetched >= limit:
            print(f"  Reached limit ({limit}), stopping.")
            break

    return records, total_relevant


def main():
    parser = argparse.ArgumentParser(
        description="Harvest historical climate finance literature from OpenAlex")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max records per query (0=all)")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="Delay between requests in seconds")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint")
    args = parser.parse_args()

    # Load existing OpenAlex IDs and DOIs to skip duplicates
    existing_ids = set()
    existing_dois = set()

    main_csv = os.path.join(CATALOGS_DIR, "openalex_works.csv")
    if os.path.exists(main_csv):
        main_df = pd.read_csv(main_csv)
        existing_ids = set(main_df["source_id"].dropna().astype(str))
        existing_dois = set(main_df["doi"].dropna().astype(str))
        existing_dois.discard("")
        print(f"Loaded {len(existing_ids)} existing OpenAlex IDs, "
              f"{len(existing_dois)} DOIs to skip")

    if args.resume:
        checkpoint_records = load_checkpoint(CHECKPOINT)
        for r in checkpoint_records:
            existing_ids.add(r["source_id"])
        print(f"Resuming with {len(checkpoint_records)} already in checkpoint")
    else:
        delete_checkpoint(CHECKPOINT)

    # Run all historical queries
    grand_total = 0
    for term in HISTORICAL_QUERIES:
        print(f"\nQuerying: \"{term}\"")
        recs, n_relevant = fetch_historical(
            term, args.delay, args.limit, existing_ids, existing_dois)
        if recs:
            append_checkpoint(recs, CHECKPOINT)
        grand_total += n_relevant

    # Load all from checkpoint and save
    final_records = load_checkpoint(CHECKPOINT)
    if not final_records:
        print("\nNo new records found.")
        return

    df = pd.DataFrame(final_records, columns=WORKS_COLUMNS)
    out_path = os.path.join(CATALOGS_DIR, "openalex_historical_works.csv")
    save_csv(df, out_path)
    delete_checkpoint(CHECKPOINT)

    print(f"\nSummary:")
    print(f"  New works harvested: {len(df)}")
    print(f"  With DOI: {(df['doi'] != '').sum()}")
    yr = pd.to_numeric(df["year"], errors="coerce")
    print(f"  Year range: {yr.min():.0f} - {yr.max():.0f}")
    print(f"  Pre-2009: {(yr < 2009).sum()}")
    print(f"  2009-2015: {((yr >= 2009) & (yr <= 2015)).sum()}")
    print(f"  Post-2015: {(yr > 2015).sum()}")


if __name__ == "__main__":
    main()
