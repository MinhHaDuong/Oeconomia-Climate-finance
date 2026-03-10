"""Export corpus composition table by source for the technical report.

Produces:
- content/tables/tab_corpus_sources.csv: detailed stats per source
- stdout: formatted markdown table

Shows for each source: query description, records before/after refinement,
non-English share, journal-article share, DOI coverage, reference coverage,
abstract availability, Open Access status, and local fulltext availability.
"""

import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, save_csv, BASE_DIR, RAW_DIR, MAILTO

CORE_THRESHOLD = 50

# Source metadata: label and query description from catalog_*.py scripts
SOURCE_META = {
    "openalex": {
        "label": "OpenAlex",
        "query": 'title/abstract search: "climate finance", "finance climat"',
    },
    "openalex_historical": {
        "label": "OpenAlex (historical)",
        "query": "14 pre-2009 terms (CDM, carbon finance, adaptation fund, ...)",
    },
    "istex": {
        "label": "ISTEX",
        "query": "French institutional full-text repository (Springer, Elsevier, Wiley)",
    },
    "bibcnrs": {
        "label": "bibCNRS",
        "query": "non-English queries: FR, ZH, JA via WoS/EconLit/FRANCIS",
    },
    "scispsace": {
        "label": "SciSpace",
        "query": "AI-curated seed expansion (systematic review + RIS export)",
    },
    "grey": {
        "label": "Grey literature",
        "query": "World Bank OKR API + curated YAML (OECD, UNFCCC reports)",
    },
    "teaching": {
        "label": "Teaching canon",
        "query": "MBA/doctoral syllabi (hand-curated seed list)",
    },
}

PRIMARY_SOURCES = list(SOURCE_META.keys())

OA_CACHE = os.path.join(CATALOGS_DIR, "oa_status_cache.csv")


def fetch_oa_status(df):
    """Fetch Open Access status from OpenAlex for works with OA source_ids.

    Uses batch filter endpoint (50 IDs per request) to minimise API calls.
    Caches results to avoid re-fetching across runs.
    """
    # Only OpenAlex works have queryable source_ids
    oa_mask = df["source"].str.contains("openalex", na=False)
    oa_ids = df.loc[oa_mask, "source_id"].dropna().unique().tolist()
    print(f"OpenAlex works to check for OA: {len(oa_ids)}")

    # Load cache
    cached = {}
    if os.path.exists(OA_CACHE):
        cache_df = pd.read_csv(OA_CACHE)
        cached = dict(zip(cache_df["source_id"], cache_df["is_oa"]))
        print(f"  Loaded {len(cached)} cached OA statuses")

    # Find uncached IDs
    uncached = [sid for sid in oa_ids if sid not in cached]
    print(f"  Uncached: {len(uncached)}")

    # Batch query OpenAlex (50 IDs per request)
    batch_size = 50
    for i in range(0, len(uncached), batch_size):
        batch = uncached[i:i + batch_size]
        id_filter = "|".join(batch)
        params = {
            "filter": f"openalex_id:{id_filter}",
            "select": "id,open_access",
            "per_page": batch_size,
            "mailto": MAILTO,
        }
        try:
            resp = requests.get(
                "https://api.openalex.org/works", params=params, timeout=30,
            )
            resp.raise_for_status()
            for r in resp.json().get("results", []):
                sid = r["id"].replace("https://openalex.org/", "")
                is_oa = r.get("open_access", {}).get("is_oa", False)
                cached[sid] = bool(is_oa)
        except Exception as e:
            print(f"  Warning: batch {i}-{i+batch_size} failed: {e}")
            # Mark batch as unknown (False)
            for sid in batch:
                cached.setdefault(sid, False)
        if (i // batch_size) % 20 == 0 and i > 0:
            print(f"  Fetched OA status for {i + len(batch)}/{len(uncached)}")
        time.sleep(0.15)

    # Save updated cache
    cache_out = pd.DataFrame([
        {"source_id": k, "is_oa": v} for k, v in cached.items()
    ])
    cache_out.to_csv(OA_CACHE, index=False)
    print(f"  Saved {len(cache_out)} OA statuses to cache")

    # Map back to df
    df["is_oa"] = df["source_id"].map(cached).fillna(False).astype(bool)
    return df


def detect_local_fulltext(df):
    """Check which ISTEX records have fulltext downloaded locally."""
    raw_ids = set()
    if os.path.isdir(RAW_DIR):
        raw_ids = set(os.listdir(RAW_DIR))
    df["has_fulltext"] = (
        df["source"].str.contains("istex", na=False)
        & df["source_id"].isin(raw_ids)
    )
    n = df["has_fulltext"].sum()
    print(f"Local fulltext: {n} works (ISTEX downloads in {RAW_DIR})")
    return df


def main():
    # Load refined corpus (after filtering)
    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    df["doi_lower"] = df["doi"].str.lower().str.strip()
    df["has_doi"] = df["doi_lower"].apply(
        lambda x: bool(x) and str(x) not in ("", "nan", "none")
    )
    df["is_english"] = df["language"].str.lower().str.startswith("en", na=True)
    df["has_journal"] = df["journal"].notna() & (df["journal"].str.strip() != "")

    # Abstract availability
    abs_s = df["abstract"].fillna("").astype(str).str.strip()
    df["has_abstract"] = (abs_s.str.len() > 10) & (abs_s != "nan")

    print(f"Loaded {len(df)} refined works from {path}")

    # Load unified corpus (before filtering) for raw counts
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    unified = pd.read_csv(unified_path, usecols=["source"])
    print(f"Loaded {len(unified)} unified works from {unified_path}")

    # Load citations for reference coverage
    cit_path = os.path.join(CATALOGS_DIR, "citations.csv")
    cit = pd.read_csv(cit_path, usecols=["source_doi"], low_memory=False)
    source_dois = set(cit["source_doi"].str.lower().str.strip().dropna()) - {
        "", "nan", "none",
    }
    df["has_refs"] = df["doi_lower"].isin(source_dois)
    print(f"Loaded {len(cit)} citation rows")

    # Open Access status from OpenAlex API
    df = fetch_oa_status(df)

    # Local fulltext (ISTEX downloads)
    df = detect_local_fulltext(df)

    # Compute per-source statistics
    rows = []
    for src in PRIMARY_SOURCES:
        mask_u = unified["source"].str.contains(src, na=False)
        mask_r = df["source"].str.contains(src, na=False)
        sub = df[mask_r]
        meta = SOURCE_META[src]
        n_raw = int(mask_u.sum())
        n_refined = len(sub)
        if n_refined == 0:
            rows.append({
                "Source": meta["label"], "Query": meta["query"],
                "Raw": n_raw, "Refined": n_refined,
            })
            continue
        rows.append({
            "Source": meta["label"],
            "Query": meta["query"],
            "Raw": n_raw,
            "Refined": n_refined,
            "non-EN": int((~sub["is_english"]).sum()),
            "%Journal": f"{sub['has_journal'].mean() * 100:.0f}%",
            "%DOI": f"{sub['has_doi'].mean() * 100:.0f}%",
            "%Refs": f"{sub['has_refs'].mean() * 100:.0f}%",
            "%Abstract": f"{sub['has_abstract'].mean() * 100:.0f}%",
            "%OA": f"{sub['is_oa'].mean() * 100:.0f}%",
            "%FullText": f"{sub['has_fulltext'].mean() * 100:.0f}%",
        })

    # Totals row (deduplicated)
    rows.append({
        "Source": "TOTAL (deduplicated)",
        "Query": "",
        "Raw": len(unified),
        "Refined": len(df),
        "non-EN": int((~df["is_english"]).sum()),
        "%Journal": f"{df['has_journal'].mean() * 100:.0f}%",
        "%DOI": f"{df['has_doi'].mean() * 100:.0f}%",
        "%Refs": f"{df['has_refs'].mean() * 100:.0f}%",
        "%Abstract": f"{df['has_abstract'].mean() * 100:.0f}%",
        "%OA": f"{df['is_oa'].mean() * 100:.0f}%",
        "%FullText": f"{df['has_fulltext'].mean() * 100:.0f}%",
    })

    summary = pd.DataFrame(rows)

    # Save CSV
    out_path = os.path.join(BASE_DIR, "content", "tables", "tab_corpus_sources.csv")
    save_csv(summary, out_path)

    # Print markdown table
    print()
    print(
        "| Source | Query | Raw | Refined | non-EN "
        "| %Journal | %DOI | %Refs | %Abstract | %OA | %FullText |"
    )
    print("|:-------|:------|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in summary.iterrows():
        non_en = int(row.get("non-EN", 0)) if pd.notna(row.get("non-EN")) else 0
        print(
            f"| {row['Source']} | {row['Query']} "
            f"| {int(row['Raw']):,} | {int(row['Refined']):,} | {non_en:,} "
            f"| {row.get('%Journal', '')} | {row.get('%DOI', '')} "
            f"| {row.get('%Refs', '')} "
            f"| {row.get('%Abstract', '')} | {row.get('%OA', '')} "
            f"| {row.get('%FullText', '')} |"
        )
    print()


if __name__ == "__main__":
    main()
