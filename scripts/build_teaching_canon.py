#!/usr/bin/env python3
"""Build a teaching canon: match syllabus readings to our corpus, score, identify gaps.

Reads:  config/teaching_sources.yaml, catalogs/refined_works.csv
Writes: catalogs/teaching_canon.csv   (scored works in corpus)
        catalogs/teaching_gaps.csv    (syllabus readings NOT in corpus)
        catalogs/teaching_works.csv   (gap works formatted for merge pipeline)
        tables/teaching_canon.csv          (summary table for publication)

Usage:
    python scripts/build_teaching_canon.py
"""

import os
import sys

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from utils import CONFIG_DIR, CATALOGS_DIR, WORKS_COLUMNS, normalize_doi, normalize_title, save_csv

YAML_PATH = os.path.join(CONFIG_DIR, "teaching_sources.yaml")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")


def load_teaching_sources():
    """Load and flatten teaching_sources.yaml into a list of (reading, institution_meta) tuples."""
    with open(YAML_PATH, encoding="utf-8") as f:
        sources = yaml.safe_load(f)

    readings = []
    for src in sources:
        meta = {
            "institution": src["institution"],
            "course": src["course"],
            "level": src["level"],
            "region": src["region"],
            "year": src.get("year", ""),
        }
        for r in src.get("readings", []):
            reading = dict(r)
            reading["_meta"] = meta
            readings.append(reading)

    print(f"Loaded {len(readings)} readings from {len(sources)} institutions")
    return readings, sources


def match_readings_to_corpus(readings, corpus_df):
    """Match each reading to corpus by DOI (primary) or fuzzy title (fallback).

    Returns: list of dicts with match info.
    """
    # Build corpus lookup indices
    corpus_df["_doi_norm"] = corpus_df["doi"].apply(
        lambda x: normalize_doi(x) if pd.notna(x) else "")
    corpus_df["_title_norm"] = corpus_df["title"].apply(
        lambda x: normalize_title(str(x)) if pd.notna(x) else "")

    doi_index = {}
    for idx, row in corpus_df.iterrows():
        d = row["_doi_norm"]
        if d:
            doi_index[d] = idx

    title_year_index = {}
    for idx, row in corpus_df.iterrows():
        t = row["_title_norm"]
        y = str(row.get("year", ""))[:4]
        if t and len(t) > 10:
            key = (t, y)
            if key not in title_year_index:
                title_year_index[key] = idx

    # Also build title-only index for books (year may differ)
    title_index = {}
    for idx, row in corpus_df.iterrows():
        t = row["_title_norm"]
        if t and len(t) > 20:
            if t not in title_index:
                title_index[t] = idx

    matches = []
    unmatched = []

    for r in readings:
        meta = r["_meta"]
        matched_idx = None
        match_method = None

        # Try DOI match
        rdoi = normalize_doi(r.get("doi", ""))
        if rdoi:
            if rdoi in doi_index:
                matched_idx = doi_index[rdoi]
                match_method = "doi"

        # Try title+year match
        if matched_idx is None and r.get("title"):
            rtitle = normalize_title(r["title"])
            ryear = str(r.get("year", ""))[:4]
            key = (rtitle, ryear)
            if key in title_year_index:
                matched_idx = title_year_index[key]
                match_method = "title+year"
            elif rtitle in title_index:
                matched_idx = title_index[rtitle]
                match_method = "title"

        # Try partial title match (for books with subtitle variations)
        if matched_idx is None and r.get("title"):
            rtitle = normalize_title(r["title"])
            if len(rtitle) > 15:
                # Search for titles that start with or contain the reading title
                for t, idx in title_index.items():
                    if rtitle in t or t in rtitle:
                        matched_idx = idx
                        match_method = "title_partial"
                        break

        if matched_idx is not None:
            matches.append({
                "corpus_idx": matched_idx,
                "match_method": match_method,
                "reading_doi": r.get("doi", ""),
                "reading_title": r.get("title", ""),
                "institution": meta["institution"],
                "level": meta["level"],
                "region": meta["region"],
            })
        else:
            unmatched.append({
                "doi": r.get("doi", ""),
                "title": r.get("title", ""),
                "authors": r.get("authors", ""),
                "year": r.get("year", ""),
                "institution": meta["institution"],
                "level": meta["level"],
                "region": meta["region"],
            })

    print(f"  Matched: {len(matches)}, Unmatched: {len(unmatched)}")
    return matches, unmatched


def build_canon_table(matches, corpus_df):
    """Aggregate matches per corpus paper: count institutions, collect levels/regions."""
    # Group by corpus index
    from collections import defaultdict
    paper_data = defaultdict(lambda: {
        "institutions": set(),
        "levels": set(),
        "regions": set(),
        "match_methods": set(),
    })

    for m in matches:
        idx = m["corpus_idx"]
        paper_data[idx]["institutions"].add(m["institution"])
        paper_data[idx]["levels"].add(m["level"])
        paper_data[idx]["regions"].add(m["region"])
        paper_data[idx]["match_methods"].add(m["match_method"])

    rows = []
    for idx, data in paper_data.items():
        row = corpus_df.loc[idx]
        rows.append({
            "doi": row.get("doi", ""),
            "title": row.get("title", ""),
            "first_author": row.get("first_author", ""),
            "year": row.get("year", ""),
            "cited_by_count": row.get("cited_by_count", ""),
            "teaching_count": len(data["institutions"]),
            "teaching_institutions": "|".join(sorted(data["institutions"])),
            "teaching_levels": "|".join(sorted(data["levels"])),
            "teaching_regions": "|".join(sorted(data["regions"])),
            "in_corpus": True,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("teaching_count", ascending=False)
    return df


def build_gaps_table(unmatched):
    """Build table of readings not found in corpus."""
    if not unmatched:
        return pd.DataFrame()

    # Deduplicate by DOI or title
    seen = set()
    unique = []
    for u in unmatched:
        key = normalize_doi(u.get("doi", "")) or normalize_title(u.get("title", ""))
        if key and key not in seen:
            seen.add(key)
            unique.append(u)

    # Group institutions per unique reading
    from collections import defaultdict
    gap_data = defaultdict(lambda: {
        "doi": "", "title": "", "authors": "", "year": "",
        "institutions": set(), "levels": set(), "regions": set(),
    })

    for u in unmatched:
        key = normalize_doi(u.get("doi", "")) or normalize_title(u.get("title", ""))
        if not key:
            continue
        d = gap_data[key]
        d["doi"] = d["doi"] or u.get("doi", "")
        d["title"] = d["title"] or u.get("title", "")
        d["authors"] = d["authors"] or u.get("authors", "")
        d["year"] = d["year"] or u.get("year", "")
        d["institutions"].add(u["institution"])
        d["levels"].add(u["level"])
        d["regions"].add(u["region"])

    rows = []
    for key, d in gap_data.items():
        rows.append({
            "doi": d["doi"],
            "title": d["title"],
            "first_author": d["authors"].split(",")[0].strip() if d["authors"] else "",
            "all_authors": d["authors"],
            "year": d["year"],
            "teaching_count": len(d["institutions"]),
            "teaching_institutions": "|".join(sorted(d["institutions"])),
            "teaching_levels": "|".join(sorted(d["levels"])),
            "teaching_regions": "|".join(sorted(d["regions"])),
            "in_corpus": False,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("teaching_count", ascending=False)
    return df


def build_teaching_works(gaps_df):
    """Create a works CSV from gap readings for the merge pipeline."""
    if gaps_df.empty:
        return pd.DataFrame(columns=WORKS_COLUMNS)

    rows = []
    for _, gap in gaps_df.iterrows():
        row = {col: "" for col in WORKS_COLUMNS}
        row["source"] = "teaching"
        row["doi"] = gap.get("doi", "")
        row["title"] = gap.get("title", "")
        row["first_author"] = gap.get("first_author", "")
        row["all_authors"] = gap.get("all_authors", "")
        row["year"] = str(gap.get("year", ""))
        rows.append(row)

    df = pd.DataFrame(rows)
    # Only keep rows that have at least a title or DOI
    df = df[(df["title"].str.strip() != "") | (df["doi"].str.strip() != "")]
    return df[WORKS_COLUMNS]


def print_summary(canon_df, gaps_df, sources):
    """Print summary statistics."""
    print(f"\n{'='*60}")
    print(f"TEACHING CANON SUMMARY")
    print(f"{'='*60}")
    print(f"  Institutions surveyed: {len(sources)}")
    print(f"  Papers matched in corpus: {len(canon_df)}")
    if not gaps_df.empty:
        print(f"  Readings NOT in corpus: {len(gaps_df)}")
    else:
        print(f"  Readings NOT in corpus: 0")

    if len(canon_df) > 0:
        print(f"\n  Top 20 most-taught papers:")
        for _, row in canon_df.head(20).iterrows():
            title = str(row["title"])[:60]
            count = row["teaching_count"]
            insts = row["teaching_institutions"]
            print(f"    [{count} inst] {row['first_author']} ({row['year']}) {title}")

        # Distribution by level
        print(f"\n  Level distribution (among matched):")
        for level in ["doctoral", "mba", "masters", "mooc", "professional"]:
            mask = canon_df["teaching_levels"].str.contains(level, na=False)
            print(f"    {level}: {mask.sum()} papers")

        # Distribution by region
        print(f"\n  Region distribution (among matched):")
        for region in ["North America", "Europe", "Asia", "Latin America", "Global"]:
            mask = canon_df["teaching_regions"].str.contains(region, na=False)
            print(f"    {region}: {mask.sum()} papers")

    if not gaps_df.empty and len(gaps_df) > 0:
        multi_inst_gaps = gaps_df[gaps_df["teaching_count"] >= 2]
        if len(multi_inst_gaps) > 0:
            print(f"\n  Gap readings in 2+ institutions (high priority to add):")
            for _, row in multi_inst_gaps.iterrows():
                title = str(row["title"])[:60] if row["title"] else row["doi"]
                print(f"    [{row['teaching_count']} inst] {title}")


def main():
    print("Loading teaching sources...")
    readings, sources = load_teaching_sources()

    print("Loading corpus...")
    # Prefer refined (after teaching merge + refinement);
    # fall back to unified if refined not yet available.
    corpus_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    if not os.path.exists(corpus_path):
        corpus_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    corpus_df = pd.read_csv(corpus_path, dtype=str, keep_default_na=False)
    print(f"  Corpus: {len(corpus_df)} works")

    print("\nMatching readings to corpus...")
    matches, unmatched = match_readings_to_corpus(readings, corpus_df)

    print("\nBuilding canon table...")
    canon_df = build_canon_table(matches, corpus_df)

    print("Building gaps table...")
    gaps_df = build_gaps_table(unmatched)

    # Save outputs
    canon_path = os.path.join(CATALOGS_DIR, "teaching_canon.csv")
    save_csv(canon_df, canon_path)

    if not gaps_df.empty:
        gaps_path = os.path.join(CATALOGS_DIR, "teaching_gaps.csv")
        save_csv(gaps_df, gaps_path)

        # Build teaching_works.csv for merge pipeline
        teaching_works = build_teaching_works(gaps_df)
        if len(teaching_works) > 0:
            works_path = os.path.join(CATALOGS_DIR, "teaching_works.csv")
            save_csv(teaching_works, works_path)

    # Save summary table for publication
    os.makedirs(TABLES_DIR, exist_ok=True)
    summary_path = os.path.join(TABLES_DIR, "teaching_canon.csv")
    # Include both matched and gap readings in summary
    if not gaps_df.empty:
        summary = pd.concat([
            canon_df[["doi", "title", "first_author", "year", "cited_by_count",
                       "teaching_count", "teaching_institutions", "teaching_levels",
                       "teaching_regions", "in_corpus"]],
            gaps_df[["doi", "title", "first_author", "year",
                      "teaching_count", "teaching_institutions", "teaching_levels",
                      "teaching_regions", "in_corpus"]],
        ], ignore_index=True)
    else:
        summary = canon_df[["doi", "title", "first_author", "year", "cited_by_count",
                             "teaching_count", "teaching_institutions", "teaching_levels",
                             "teaching_regions", "in_corpus"]].copy()
    summary = summary.sort_values("teaching_count", ascending=False)
    save_csv(summary, summary_path)

    print_summary(canon_df, gaps_df, sources)


if __name__ == "__main__":
    main()
