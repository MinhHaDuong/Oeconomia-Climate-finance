#!/usr/bin/env python3
"""Enrich teaching gap papers with metadata from OpenAlex API.

Reads:  data/catalogs/teaching_gaps.csv
Writes: data/catalogs/teaching_works.csv (enriched, WORKS_COLUMNS format)

Usage:
    python scripts/enrich_teaching_gaps.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, WORKS_COLUMNS, normalize_doi,
                   polite_get, reconstruct_abstract, save_csv)


def fetch_openalex_by_doi(doi):
    """Fetch work metadata from OpenAlex by DOI."""
    url = f"https://api.openalex.org/works/doi:{doi}"
    try:
        resp = polite_get(url, delay=0.15)
        return resp.json()
    except Exception as e:
        print(f"  OpenAlex lookup failed for {doi}: {e}")
        return None


def fetch_openalex_by_title(title, year=""):
    """Fetch work metadata from OpenAlex by title search."""
    params = {"search": title}
    if year:
        params["filter"] = f"publication_year:{year}"
    url = "https://api.openalex.org/works"
    try:
        resp = polite_get(url, params=params, delay=0.15)
        results = resp.json().get("results", [])
        if results:
            return results[0]
    except Exception as e:
        print(f"  OpenAlex search failed for '{title}': {e}")
    return None


def openalex_to_works_row(work):
    """Convert OpenAlex work dict to WORKS_COLUMNS row."""
    if not work:
        return None

    # Authors
    authorships = work.get("authorships", [])
    first_author = ""
    all_authors = []
    for a in authorships:
        name = a.get("author", {}).get("display_name", "")
        if name:
            all_authors.append(name)
            if not first_author:
                first_author = name

    # Abstract
    abstract = ""
    aii = work.get("abstract_inverted_index")
    if aii:
        abstract = reconstruct_abstract(aii)

    # DOI
    doi_raw = work.get("doi", "") or ""
    doi = normalize_doi(doi_raw)

    # Journal
    journal = ""
    loc = work.get("primary_location", {}) or {}
    src = loc.get("source", {}) or {}
    journal = src.get("display_name", "")

    # Keywords
    keywords = []
    for kw in work.get("keywords", []):
        keywords.append(kw.get("display_name", ""))

    # Concepts/topics
    categories = []
    for topic in work.get("topics", []):
        categories.append(topic.get("display_name", ""))

    # Affiliations
    affiliations = []
    for a in authorships:
        for inst in a.get("institutions", []):
            name = inst.get("display_name", "")
            if name and name not in affiliations:
                affiliations.append(name)

    return {
        "source": "teaching",
        "source_id": work.get("id", ""),
        "doi": doi,
        "title": work.get("title", ""),
        "first_author": first_author,
        "all_authors": "; ".join(all_authors),
        "year": str(work.get("publication_year", "")),
        "journal": journal,
        "abstract": abstract,
        "language": work.get("language", ""),
        "keywords": "; ".join(keywords[:10]),
        "categories": "; ".join(categories[:5]),
        "cited_by_count": str(work.get("cited_by_count", 0)),
        "affiliations": "; ".join(affiliations[:10]),
    }


def main():
    gaps_path = os.path.join(CATALOGS_DIR, "teaching_gaps.csv")
    gaps_df = pd.read_csv(gaps_path, dtype=str, keep_default_na=False)
    print(f"Loaded {len(gaps_df)} gap readings")

    rows = []
    for idx, gap in gaps_df.iterrows():
        doi = gap.get("doi", "").strip()
        title = gap.get("title", "").strip()
        year = gap.get("year", "").strip()

        work = None
        if doi:
            print(f"  [{idx+1}/{len(gaps_df)}] Fetching DOI: {doi}")
            work = fetch_openalex_by_doi(doi)
        elif title:
            print(f"  [{idx+1}/{len(gaps_df)}] Searching: {title[:60]}")
            work = fetch_openalex_by_title(title, year)

        if work:
            row = openalex_to_works_row(work)
            if row:
                rows.append(row)
                print(f"    → {row['first_author']} ({row['year']}) {row['title'][:60]}")
            else:
                print(f"    → Parse failed")
        else:
            # Keep minimal record from gap data
            row = {col: "" for col in WORKS_COLUMNS}
            row["source"] = "teaching"
            row["doi"] = doi
            row["title"] = title
            row["first_author"] = gap.get("first_author", "")
            row["all_authors"] = gap.get("all_authors", "")
            row["year"] = year
            if row["title"] or row["doi"]:
                rows.append(row)
            print(f"    → Not found, keeping minimal record")

    df = pd.DataFrame(rows)
    # Ensure WORKS_COLUMNS order
    for col in WORKS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[WORKS_COLUMNS]

    # Drop rows with no title and no DOI
    df = df[(df["title"].str.strip() != "") | (df["doi"].str.strip() != "")]

    works_path = os.path.join(CATALOGS_DIR, "teaching_works.csv")
    save_csv(df, works_path)
    print(f"\nEnriched {len(df)} works saved to {works_path}")
    print(f"  With abstracts: {(df['abstract'].str.len() > 50).sum()}")
    print(f"  With DOIs: {(df['doi'].str.strip() != '').sum()}")


if __name__ == "__main__":
    main()
