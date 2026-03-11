#!/usr/bin/env python3
"""Build a ~1,000-paper HET climate finance core subset.

Pipeline:
  1. Theme gate: keep papers matching climate+finance boolean queries
  2. Discipline filter: keep economics/policy, exclude pure science/engineering
  3. Compute citation centrality (PageRank on citation graph)
  4. Score and rank (centrality + normalized citations/year + teaching bonus)
  5. Select top TARGET_N with diversity quotas
  6. Output CSV

Reads:  $DATA/catalogs/refined_works.csv, $DATA/catalogs/citations.csv,
        $DATA/catalogs/teaching_canon.csv
Writes: $DATA/catalogs/het_mostcited_50.csv

Usage:
    python scripts/build_het_core.py
"""

import os
import re
import sys

import networkx as nx
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, normalize_doi, save_csv

# ── CONFIG ──────────────────────────────────────────────────────────────

TARGET_N = 1000
CURRENT_YEAR = 2026

THEME_QUERIES = [
    r"climate\s+finance",
    r"carbon\s+finance",
    r"climate.{0,20}development\s+finance",
    r"climate.{0,20}\boda\b",
    r"climate.{0,20}\baid\b",
    r"climate.{0,20}public\s+finance",
    r"green\s+bond",
    r"green\s+finance",
    r"carbon\s+market",
    r"carbon\s+tax",
    r"carbon\s+pric",
    r"emission\s+trading",
    r"clean\s+development\s+mechanism",
    r"\bcdm\b",
    r"climate\s+risk",
    r"climate\s+polic",
    r"climate\s+change.{0,30}(?:econom|financ|invest|cost|price|market|fund)",
    r"(?:econom|financ|invest|cost|price|market|fund).{0,30}climate\s+change",
    r"adaptation\s+fund",
    r"green\s+climate\s+fund",
    r"\bgcf\b.{0,20}climate",
    r"sustainable\s+finance",
    r"esg.{0,20}climate",
    r"stranded\s+asset",
]

ALLOWED_TAGS = {
    "economics", "public economics", "development economics",
    "environmental economics", "political economy", "political science",
    "public policy", "natural resource economics", "finance",
    "financial economics", "economic growth", "economic system",
    "law and economics", "international development", "business",
    "economic geography", "agricultural economics", "welfare economics",
    "international trade", "monetary economics", "public finance",
    "microeconomics", "macroeconomics", "econometrics",
    "financial system", "financial crisis", "capital market",
    "socioeconomic development",
}

EXCLUDED_TAGS = {
    "engineering", "materials science", "geology", "chemistry",
    "meteorology", "computer science", "algorithm", "machine learning",
    "artificial intelligence", "remote sensing", "composite material",
    "organic chemistry", "inorganic chemistry", "biochemistry",
    "nanotechnology", "thermodynamics", "electrical engineering",
    "mechanical engineering", "civil engineering",
}

ALLOWED_ORGS = {
    "oecd", "world bank", "imf", "unfccc", "unep", "adb", "afdb",
    "ebrd", "eib", "idb", "ifc", "gef", "undp", "gcf", "cpi",
    "ipcc", "bis", "fao", "unctad", "eclac", "cepal",
    "asian development bank", "african development bank",
    "inter-american development bank", "european investment bank",
    "international monetary fund", "international finance corporation",
    "green climate fund", "global environment facility",
    "world bank group", "un habitat", "un hlagcc",
}

W_CENTRALITY = 0.4
W_CITNORM = 0.6
W_TEACHING = 0.1

QUOTAS = {
    "institutional_reports_min": 0.15,
    "non_english_min": 0.10,
    "global_south_min": 0.20,
}

# Global South country keywords for affiliation matching
GLOBAL_SOUTH_KEYWORDS = {
    "china", "india", "brazil", "indonesia", "mexico", "nigeria",
    "bangladesh", "pakistan", "vietnam", "ethiopia", "egypt",
    "philippines", "kenya", "tanzania", "colombia", "argentina",
    "south africa", "peru", "venezuela", "chile", "ecuador",
    "guatemala", "cameroon", "ghana", "senegal", "morocco",
    "tunisia", "algeria", "thailand", "malaysia", "sri lanka",
    "nepal", "myanmar", "cambodia", "laos", "mongolia",
    "fiji", "samoa", "tonga", "tuvalu", "vanuatu",
    "bolivia", "paraguay", "uruguay", "costa rica", "panama",
    "honduras", "nicaragua", "el salvador", "dominican republic",
    "jamaica", "trinidad", "barbados", "cuba", "haiti",
    "uganda", "mozambique", "zambia", "zimbabwe", "malawi",
    "madagascar", "niger", "mali", "burkina faso", "chad",
    "congo", "rwanda", "burundi", "benin", "togo",
    "sierra leone", "liberia", "guinea", "gambia",
    "jordan", "lebanon", "iraq", "iran", "afghanistan",
    "uzbekistan", "kazakhstan", "kyrgyzstan", "tajikistan",
    "beijing", "shanghai", "mumbai", "delhi", "são paulo",
    "nairobi", "dar es salaam", "lagos", "cairo", "dhaka",
    "jakarta", "manila", "hanoi", "bogota", "lima",
    "buenos aires", "santiago", "quito", "accra", "dakar",
    "addis ababa", "kampala", "lusaka", "harare", "maputo",
    "bangui", "kinshasa", "abidjan", "tunis", "rabat",
    "islamabad", "karachi", "colombo", "kathmandu",
    "flacso", "eclac", "cepal",
}


# ── HELPERS ─────────────────────────────────────────────────────────────

def text_blob(row):
    """Concatenate title + abstract + keywords into one lowercase string."""
    parts = [
        str(row.get("title", "") or ""),
        str(row.get("abstract", "") or ""),
        str(row.get("keywords", "") or ""),
    ]
    return " ".join(parts).lower()


def matches_theme(blob):
    """Check if text blob matches any theme query.

    Includes both specific phrase patterns AND broad conjunctions
    (e.g. "climate" anywhere + "finance" anywhere).
    """
    # Specific phrase/proximity patterns
    for pattern in THEME_QUERIES:
        if re.search(pattern, blob):
            return True

    # Broad conjunctions (from pseudocode: "climate" AND "finance")
    has_climate = bool(re.search(r"\bclimate\b", blob))
    has_carbon = bool(re.search(r"\bcarbon\b", blob))
    has_green = bool(re.search(r"\bgreen\b", blob))
    has_esg = bool(re.search(r"\besg\b", blob))

    finance_terms = (
        r"\bfinanc\w*\b|\binvest\w*\b|\bfund\w*\b|\bbond\w*\b"
        r"|\bmarket\w*\b|\bpric\w*\b|\btax\w*\b|\btrad\w*\b"
        r"|\binsur\w*\b|\bbank\w*\b|\bsubsid\w*\b|\baid\b|\boda\b"
    )
    has_finance = bool(re.search(finance_terms, blob))

    if has_climate and has_finance:
        return True
    if has_carbon and has_finance:
        return True
    if has_green and has_finance:
        return True
    if has_esg and has_finance:
        return True

    return False


def is_institutional_report(row):
    """Detect institutional reports from source, journal, first_author."""
    source = str(row.get("source", "") or "").lower()
    journal = str(row.get("journal", "") or "").lower()
    author = str(row.get("first_author", "") or "").lower()

    if "grey" in source:
        return True

    for org in ALLOWED_ORGS:
        if org in journal or org in author:
            return True
    return False


def field_score(row):
    """Classify paper: 'allow', 'exclude', or 'unknown' based on category tags.

    Uses substring matching to handle both OpenAlex concept tags
    ("Economics") and topic tags ("Climate Change Policy and Economics").
    """
    cats_raw = str(row.get("categories", "") or "").lower()
    if not cats_raw.strip():
        return "unknown"

    has_allowed = any(tag in cats_raw for tag in ALLOWED_TAGS)
    has_excluded = any(tag in cats_raw for tag in EXCLUDED_TAGS)

    if has_allowed:
        return "allow"
    if has_excluded:
        return "exclude"
    return "unknown"


def is_non_english(row):
    """Check if paper is non-English."""
    lang = str(row.get("language", "") or "").lower().strip()
    if not lang:
        return False
    return lang not in ("en", "eng", "en_us", "english")


def is_global_south(row):
    """Detect Global South affiliation from affiliations field."""
    aff = str(row.get("affiliations", "") or "").lower()
    if not aff:
        return False
    for kw in GLOBAL_SOUTH_KEYWORDS:
        if kw in aff:
            return True
    return False


def robust_minmax(values):
    """Min-max normalize, clipping at 1st/99th percentiles."""
    arr = np.array(values, dtype=float)
    if len(arr) == 0:
        return arr
    p1, p99 = np.percentile(arr, [1, 99])
    if p99 - p1 < 1e-10:
        return np.zeros_like(arr)
    clipped = np.clip(arr, p1, p99)
    return (clipped - p1) / (p99 - p1)


# ── PIPELINE ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BUILDING HET CLIMATE FINANCE CORE")
    print("=" * 60)

    # Load corpus
    corpus_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(corpus_path, dtype=str, keep_default_na=False)
    df["cited_by_count_num"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df["year_num"] = pd.to_numeric(df["year"], errors="coerce").fillna(2020)
    df["doi_norm"] = df["doi"].apply(normalize_doi)
    print(f"\nCorpus: {len(df)} papers")

    # Load teaching canon DOIs (bypass theme gate for taught papers)
    canon_path = os.path.join(CATALOGS_DIR, "teaching_canon.csv")
    teaching_dois = set()
    if os.path.exists(canon_path):
        canon = pd.read_csv(canon_path, dtype=str, keep_default_na=False)
        for d in canon["doi"]:
            nd = normalize_doi(d)
            if nd:
                teaching_dois.add(nd)

    # ── Step 1: Theme gate ──────────────────────────────────────────

    print("\n── Step 1: Theme gate ──")
    blobs = df.apply(text_blob, axis=1)
    theme_mask = blobs.apply(matches_theme)
    # Teaching canon papers bypass theme gate (definitionally climate finance)
    canon_mask = df["doi_norm"].isin(teaching_dois) & (df["doi_norm"] != "")
    combined_mask = theme_mask | canon_mask
    s1 = df[combined_mask].copy()
    n_canon_only = (canon_mask & ~theme_mask).sum()
    print(f"  Passed theme gate: {len(s1)} / {len(df)} ({n_canon_only} via teaching canon bypass)")

    # ── Step 2: Discipline + org filter ─────────────────────────────

    print("\n── Step 2: Discipline + org filter ──")
    s1["_is_report"] = s1.apply(is_institutional_report, axis=1)
    s1["_field_score"] = s1.apply(field_score, axis=1)
    s1["_in_canon"] = s1["doi_norm"].isin(teaching_dois) & (s1["doi_norm"] != "")

    keep_mask = s1["_is_report"] | (s1["_field_score"] == "allow") | s1["_in_canon"]
    s2 = s1[keep_mask].copy()

    n_reports = s1["_is_report"].sum()
    n_allow = (s1["_field_score"] == "allow").sum()
    n_exclude = (s1["_field_score"] == "exclude").sum()
    n_unknown = (s1["_field_score"] == "unknown").sum()
    print(f"  Institutional reports: {n_reports}")
    print(f"  Field allow: {n_allow}, exclude: {n_exclude}, unknown: {n_unknown}")
    print(f"  Passed discipline filter: {len(s2)}")

    # ── Step 3: Citation centrality ─────────────────────────────────

    print("\n── Step 3: Citation centrality (PageRank) ──")
    s2_dois = set(s2["doi_norm"]) - {""}

    cit_path = os.path.join(CATALOGS_DIR, "citations.csv")
    if os.path.exists(cit_path):
        cit = pd.read_csv(cit_path, dtype=str, keep_default_na=False)
        cit["source_doi_norm"] = cit["source_doi"].apply(normalize_doi)
        cit["ref_doi_norm"] = cit["ref_doi"].apply(normalize_doi)
        cit = cit[(cit["source_doi_norm"] != "") & (cit["ref_doi_norm"] != "")]

        # Restrict to edges within S2
        edges = cit[
            cit["source_doi_norm"].isin(s2_dois)
            & cit["ref_doi_norm"].isin(s2_dois)
        ]
        print(f"  Citation edges within S2: {len(edges)}")

        G = nx.DiGraph()
        G.add_nodes_from(s2_dois)
        for _, row in edges.iterrows():
            G.add_edge(row["source_doi_norm"], row["ref_doi_norm"])

        n_with_edges = sum(1 for n in G.nodes() if G.degree(n) > 0)
        print(f"  Nodes with edges: {n_with_edges} / {len(s2_dois)}")

        pr = nx.pagerank(G, alpha=0.85)
    else:
        print("  No citations.csv found — centrality = 0 for all")
        pr = {}

    s2["pagerank"] = s2["doi_norm"].map(pr).fillna(0.0)

    # ── Step 4: Score and rank ──────────────────────────────────────

    print("\n── Step 4: Score and rank ──")
    s2["cit_per_year"] = s2["cited_by_count_num"] / np.maximum(
        1, CURRENT_YEAR - s2["year_num"]
    )

    # Load teaching canon
    canon_path = os.path.join(CATALOGS_DIR, "teaching_canon.csv")
    teaching_scores = {}
    if os.path.exists(canon_path):
        canon = pd.read_csv(canon_path, dtype=str, keep_default_na=False)
        for _, row in canon.iterrows():
            d = normalize_doi(row.get("doi", ""))
            tc = pd.to_numeric(row.get("teaching_count", 0), errors="coerce")
            if d and tc > 0:
                teaching_scores[d] = tc
        print(f"  Teaching canon: {len(teaching_scores)} papers loaded")
    s2["teaching_count"] = s2["doi_norm"].map(teaching_scores).fillna(0)

    # Normalize signals
    pr_norm = robust_minmax(s2["pagerank"].values)
    cit_norm = robust_minmax(s2["cit_per_year"].values)
    teach_norm = robust_minmax(s2["teaching_count"].values)

    s2["score"] = (
        W_CENTRALITY * pr_norm
        + W_CITNORM * cit_norm
        + W_TEACHING * teach_norm
    )

    s2 = s2.sort_values("score", ascending=False).reset_index(drop=True)
    print(f"  Score range: {s2['score'].min():.4f} – {s2['score'].max():.4f}")

    # ── Step 5: Select with quotas ──────────────────────────────────

    print(f"\n── Step 5: Select top {TARGET_N} with quotas ──")
    s2["_non_english"] = s2.apply(is_non_english, axis=1)
    s2["_global_south"] = s2.apply(is_global_south, axis=1)

    min_reports = int(TARGET_N * QUOTAS["institutional_reports_min"])
    min_non_eng = int(TARGET_N * QUOTAS["non_english_min"])
    min_gs = int(TARGET_N * QUOTAS["global_south_min"])

    selected_idx = []
    cnt_reports = 0
    cnt_non_eng = 0
    cnt_gs = 0

    # Pre-allocate: guaranteed inclusion for teaching canon papers (2+ inst)
    canon_guaranteed = s2[s2["teaching_count"] >= 2].index.tolist()
    for i in canon_guaranteed:
        pos = s2.index.get_loc(i)
        selected_idx.append(pos)
        row = s2.iloc[pos]
        if row["_is_report"]:
            cnt_reports += 1
        if row["_non_english"]:
            cnt_non_eng += 1
        if row["_global_south"]:
            cnt_gs += 1
    print(f"  Teaching canon guaranteed: {len(selected_idx)}")

    selected_set = set(selected_idx)

    # Main pass: prioritize papers that help meet quotas
    for i in range(len(s2)):
        if len(selected_idx) >= TARGET_N:
            break
        if i in selected_set:
            continue
        row = s2.iloc[i]
        helps_quota = False
        if row["_is_report"] and cnt_reports < min_reports:
            helps_quota = True
        if row["_non_english"] and cnt_non_eng < min_non_eng:
            helps_quota = True
        if row["_global_south"] and cnt_gs < min_gs:
            helps_quota = True

        # Always add if helps quota or if quotas are already met
        quotas_met = (
            cnt_reports >= min_reports
            and cnt_non_eng >= min_non_eng
            and cnt_gs >= min_gs
        )

        if helps_quota or quotas_met:
            selected_idx.append(i)
            selected_set.add(i)
            if row["_is_report"]:
                cnt_reports += 1
            if row["_non_english"]:
                cnt_non_eng += 1
            if row["_global_south"]:
                cnt_gs += 1

    # Fill remaining slots freely from top-scored
    if len(selected_idx) < TARGET_N:
        for i in range(len(s2)):
            if len(selected_idx) >= TARGET_N:
                break
            if i not in selected_set:
                selected_idx.append(i)

    selected = s2.iloc[selected_idx].copy()
    selected = selected.sort_values("score", ascending=False).reset_index(drop=True)

    final_reports = selected["_is_report"].sum()
    final_non_eng = selected["_non_english"].sum()
    final_gs = selected["_global_south"].sum()

    print(f"  Selected: {len(selected)}")
    print(f"  Institutional reports: {final_reports} ({100*final_reports/len(selected):.1f}%)")
    print(f"  Non-English: {final_non_eng} ({100*final_non_eng/len(selected):.1f}%)")
    print(f"  Global South: {final_gs} ({100*final_gs/len(selected):.1f}%)")

    # ── Step 6: Output ──────────────────────────────────────────────

    print(f"\n── Step 6: Output ──")

    out_cols = [
        "doi", "title", "first_author", "all_authors", "year", "journal",
        "language", "categories", "cited_by_count", "affiliations",
        "cit_per_year", "pagerank", "score", "_is_report",
        "teaching_count",
    ]
    out = selected[out_cols].copy()
    out = out.rename(columns={"_is_report": "is_institutional_report"})
    out["cit_per_year"] = out["cit_per_year"].round(2)
    out["pagerank"] = out["pagerank"].map(lambda x: f"{x:.6f}")
    out["score"] = out["score"].round(4)

    het_path = os.path.join(CATALOGS_DIR, "het_mostcited_50.csv")
    save_csv(out, het_path)

    # Print funnel
    print(f"\n{'='*60}")
    print("PIPELINE FUNNEL")
    print(f"{'='*60}")
    print(f"  Corpus:          {len(df):>6}")
    print(f"  S1 (theme):      {len(s1):>6}")
    print(f"  S2 (discipline): {len(s2):>6}")
    print(f"  Selected:        {len(selected):>6}")

    # Top 20
    print(f"\n  Top 20 by score:")
    for i, (_, row) in enumerate(selected.head(20).iterrows()):
        title = str(row["title"])[:55]
        author = str(row["first_author"])[:15]
        yr = str(row["year"])[:4]
        sc = row["score"]
        rep = " [R]" if row["_is_report"] else ""
        print(f"  {i+1:>3}. {author} ({yr}) {title}  [{sc:.3f}]{rep}")

    # Year distribution
    print(f"\n  Year distribution of selected:")
    year_bins = pd.cut(
        pd.to_numeric(selected["year"], errors="coerce"),
        bins=[1990, 2000, 2005, 2010, 2015, 2020, 2026],
        labels=["1990-99", "2000-04", "2005-09", "2010-14", "2015-19", "2020-25"],
    )
    for label, count in year_bins.value_counts().sort_index().items():
        print(f"    {label}: {count}")


if __name__ == "__main__":
    main()
