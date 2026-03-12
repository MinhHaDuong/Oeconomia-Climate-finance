#!/usr/bin/env python3
"""Enrich missing abstracts in the refined corpus.

Four-step pipeline, each cached independently:
  1. Cross-source backfill (unified_works.csv DOI match)
  2. OpenAlex re-query (batch API, abstract_inverted_index)
  3. ISTEX fulltext extraction (local TEI XML)
  4. Semantic Scholar fallback (per-DOI API)

Note: Crossref is skipped because OpenAlex already ingests all Crossref
metadata, so step 2 covers everything Crossref would provide.

Usage:
    python scripts/enrich_abstracts.py [--dry-run] [--step N]
"""

import argparse
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, RAW_DIR, MAILTO, save_csv,
                   reconstruct_abstract, normalize_doi, polite_get)

MIN_ABSTRACT_LEN = 20
CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")


def is_missing(val):
    """True if abstract value is empty/missing."""
    if pd.isna(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none")


def clean_abstract(text):
    """Strip HTML/XML/JATS tags, normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)  # strip tags
    text = re.sub(r"&[a-z]+;", " ", text)  # strip entities
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < MIN_ABSTRACT_LEN:
        return ""
    return text


def load_cache(name):
    """Load a CSV cache file as {key: abstract} dict."""
    path = os.path.join(CACHE_DIR, f"{name}.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return dict(zip(df["key"].astype(str), df["abstract"].fillna("")))


def save_cache(name, data):
    """Save {key: abstract} dict as CSV cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{name}.csv")
    df = pd.DataFrame([
        {"key": k, "abstract": v} for k, v in data.items()
    ])
    df.to_csv(path, index=False)


# --- Step 1: Cross-source backfill ---

def step1_cross_source(df):
    """Fill missing abstracts from other records with the same DOI."""
    missing = df.index[df["_missing"]]
    if len(missing) == 0:
        return 0

    # Load unified_works for DOI-based abstract lookup
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    unified = pd.read_csv(unified_path, usecols=["doi", "abstract"])
    unified["doi_norm"] = unified["doi"].apply(normalize_doi)
    unified = unified[unified["abstract"].notna() & (unified["abstract"].str.len() > MIN_ABSTRACT_LEN)]

    # Build DOI → best abstract map (longest abstract wins)
    doi_abs = {}
    for _, row in unified.iterrows():
        d = row["doi_norm"]
        if d and d not in ("", "nan", "none"):
            a = str(row["abstract"])
            if d not in doi_abs or len(a) > len(doi_abs[d]):
                doi_abs[d] = a

    filled = 0
    for idx in missing:
        doi = normalize_doi(df.at[idx, "doi"])
        if doi and doi in doi_abs:
            ab = clean_abstract(doi_abs[doi])
            if ab:
                df.at[idx, "abstract"] = ab
                df.at[idx, "_missing"] = False
                filled += 1
    return filled


# --- Step 2: OpenAlex re-query ---

def step2_openalex(df):
    """Re-query OpenAlex for works that may now have abstracts."""
    cache = load_cache("openalex_abstracts")
    missing = df.index[df["_missing"] & df["source"].str.contains("openalex", na=False)]
    if len(missing) == 0:
        return 0

    # Collect source_ids to query (skip cached)
    to_query = []
    for idx in missing:
        sid = str(df.at[idx, "source_id"])
        if sid in cache:
            continue
        to_query.append((idx, sid))

    print(f"  OpenAlex: {len(to_query)} uncached IDs to query")

    # Batch query (50 per request)
    batch_size = 50
    for i in range(0, len(to_query), batch_size):
        batch = to_query[i:i + batch_size]
        ids = [sid for _, sid in batch]
        id_filter = "|".join(ids)
        params = {
            "filter": f"openalex_id:{id_filter}",
            "select": "id,abstract_inverted_index",
            "per_page": batch_size,
            "mailto": MAILTO,
        }
        try:
            resp = polite_get("https://api.openalex.org/works",
                              params=params, delay=0.15)
            results = {
                r["id"].replace("https://openalex.org/", ""):
                    reconstruct_abstract(r.get("abstract_inverted_index"))
                for r in resp.json().get("results", [])
            }
            for sid in ids:
                cache[sid] = results.get(sid, "")
        except Exception as e:
            print(f"  Warning: batch {i} failed: {e}")
            for sid in ids:
                cache.setdefault(sid, "")

        if (i // batch_size) % 20 == 0 and i > 0:
            print(f"  OpenAlex: {i + len(batch)}/{len(to_query)}")

    save_cache("openalex_abstracts", cache)

    # Apply cached results
    filled = 0
    for idx in missing:
        sid = str(df.at[idx, "source_id"])
        ab = clean_abstract(cache.get(sid, ""))
        if ab:
            df.at[idx, "abstract"] = ab
            df.at[idx, "_missing"] = False
            filled += 1
    return filled


# --- Step 3: ISTEX fulltext extraction ---

def step3_istex(df):
    """Extract abstracts from locally downloaded ISTEX TEI XML files."""
    missing = df.index[
        df["_missing"] & df["source"].str.contains("istex", na=False)
    ]
    if len(missing) == 0:
        return 0

    raw_ids = set(os.listdir(RAW_DIR)) if os.path.isdir(RAW_DIR) else set()

    filled = 0
    for idx in missing:
        sid = str(df.at[idx, "source_id"])
        if sid not in raw_ids:
            continue

        doc_dir = os.path.join(RAW_DIR, sid)

        # Try TEI XML first
        tei_path = os.path.join(doc_dir, f"{sid}.tei.xml")
        if os.path.exists(tei_path):
            ab = extract_abstract_tei(tei_path)
            if ab:
                df.at[idx, "abstract"] = ab
                df.at[idx, "_missing"] = False
                filled += 1
                continue

        # Try cleaned text fallback (first paragraph)
        cleaned_path = os.path.join(doc_dir, f"{sid}.cleaned")
        if os.path.exists(cleaned_path):
            ab = extract_first_paragraph(cleaned_path)
            if ab:
                df.at[idx, "abstract"] = ab
                df.at[idx, "_missing"] = False
                filled += 1

    return filled


def extract_abstract_tei(path):
    """Extract abstract text from a TEI XML file."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        # TEI namespace
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}
        for ab_elem in root.iter("{http://www.tei-c.org/ns/1.0}abstract"):
            text = "".join(ab_elem.itertext())
            return clean_abstract(text)
        # Try without namespace
        for ab_elem in root.iter("abstract"):
            text = "".join(ab_elem.itertext())
            return clean_abstract(text)
    except Exception:
        pass
    return ""


def extract_first_paragraph(path):
    """Extract first substantial paragraph from cleaned text."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read(5000)
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        if paragraphs:
            return clean_abstract(paragraphs[0])
    except Exception:
        pass
    return ""


# --- Step 4: Semantic Scholar ---

def step4_semantic_scholar(df):
    """Fetch abstracts from Semantic Scholar for remaining DOI-bearing works."""
    cache = load_cache("s2_abstracts")
    missing = df.index[df["_missing"] & df["_has_doi"]]
    if len(missing) == 0:
        return 0

    to_query = []
    for idx in missing:
        doi = normalize_doi(df.at[idx, "doi"])
        if doi in cache:
            continue
        to_query.append((idx, doi))

    print(f"  Semantic Scholar: {len(to_query)} uncached DOIs to query")

    for i, (idx, doi) in enumerate(to_query):
        try:
            resp = requests.get(
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
                params={"fields": "abstract"},
                timeout=15,
            )
            if resp.status_code == 200:
                ab = resp.json().get("abstract", "") or ""
                cache[doi] = clean_abstract(ab)
            elif resp.status_code in (404, 400):
                cache[doi] = ""
            elif resp.status_code == 429:
                print(f"  S2 rate limited, sleeping 60s...")
                time.sleep(60)
                cache[doi] = ""
            else:
                cache[doi] = ""
        except Exception as e:
            if i < 3:
                print(f"  Warning: S2 {doi}: {e}")
            cache[doi] = ""
        time.sleep(3.0)

        if (i + 1) % 50 == 0:
            print(f"  Semantic Scholar: {i + 1}/{len(to_query)}")
            save_cache("s2_abstracts", cache)

    save_cache("s2_abstracts", cache)

    filled = 0
    for idx in missing:
        doi = normalize_doi(df.at[idx, "doi"])
        ab = cache.get(doi, "")
        if ab:
            df.at[idx, "abstract"] = ab
            df.at[idx, "_missing"] = False
            filled += 1
    return filled


# --- Main ---

STEPS = {
    1: ("Cross-source backfill", step1_cross_source),
    2: ("OpenAlex re-query", step2_openalex),
    3: ("ISTEX fulltext extraction", step3_istex),
    4: ("Semantic Scholar fallback", step4_semantic_scholar),
}


def main():
    parser = argparse.ArgumentParser(description="Enrich missing abstracts")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show counts, don't modify data")
    parser.add_argument("--step", type=int, default=0,
                        help="Run only this step (1-5, 0=all)")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Input/output works CSV (default: unified_works.csv)")
    args = parser.parse_args()

    path = args.works_input
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} works from {path}")

    # Compute working columns
    df["_missing"] = df["abstract"].apply(is_missing)
    doi_s = df["doi"].apply(normalize_doi)
    df["_has_doi"] = doi_s.apply(lambda x: bool(x) and x not in ("", "nan", "none"))

    total_missing = df["_missing"].sum()
    print(f"Missing abstracts: {total_missing} / {len(df)} "
          f"({total_missing / len(df) * 100:.1f}%)\n")

    if args.dry_run:
        print("Dry run — not modifying data.")
        return

    steps = STEPS if args.step == 0 else {args.step: STEPS[args.step]}

    for step_num in sorted(steps):
        name, func = steps[step_num]
        before = df["_missing"].sum()
        print(f"Step {step_num}: {name} ({before} still missing)")
        filled = func(df)
        after = df["_missing"].sum()
        print(f"  → filled {filled}, remaining: {after}\n")

    # Save
    final_missing = df["_missing"].sum()
    df.drop(columns=["_missing", "_has_doi"], inplace=True)
    save_csv(df, path)

    print(f"Done. Abstracts: {len(df) - final_missing}/{len(df)} "
          f"({(len(df) - final_missing) / len(df) * 100:.1f}%)")
    print(f"Filled {total_missing - final_missing} abstracts total.")


if __name__ == "__main__":
    main()
