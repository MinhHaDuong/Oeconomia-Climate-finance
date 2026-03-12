#!/usr/bin/env python3
"""Citation graph quality control: verify our citations.csv against Crossref ground truth.

Randomly samples source DOIs from citations.csv, re-fetches from Crossref,
and computes precision/recall at the reference-DOI level.
Also profiles the never-fetched DOIs to quantify the structural coverage ceiling.

Saves results to content/tables/qc_citations_report.json

Usage:
    uv run python scripts/qc_citations.py [--sample-n 30] [--seed 42]
"""

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, MAILTO, normalize_doi

HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "content", "tables", "qc_citations_report.json"
)


def fetch_crossref_refs(doi):
    """Return (cr_total, cr_doi_refs, status) for a DOI."""
    url = f"https://api.crossref.org/works/{doi}"
    try:
        time.sleep(0.15)
        resp = requests.get(
            url, headers=HEADERS, timeout=30, params={"mailto": MAILTO}
        )
        if resp.status_code == 404:
            return 0, 0, "not_in_crossref"
        if resp.status_code != 200:
            return 0, 0, f"HTTP {resp.status_code}"
        data = resp.json()["message"]
        refs = data.get("reference", [])
        doi_refs = {
            normalize_doi(r.get("DOI", ""))
            for r in refs
            if normalize_doi(r.get("DOI", "")) not in ("", "nan", "none")
        }
        return len(refs), doi_refs, "ok"
    except Exception as e:
        return 0, 0, f"error: {e}"


def main():
    parser = argparse.ArgumentParser(description="QC citations.csv against Crossref")
    parser.add_argument("--sample-n", type=int, default=30,
                        help="Number of fetched DOIs to verify (default 30)")
    parser.add_argument("--never-fetched-n", type=int, default=30,
                        help="Number of never-fetched DOIs to probe (default 30)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Works CSV to read DOIs from (default: unified_works.csv)")
    args = parser.parse_args()

    np.random.seed(args.seed)

    # ── Load data ────────────────────────────────────────────────────────────────
    cit_path = os.path.join(CATALOGS_DIR, "citations.csv")
    works_path = args.works_input

    cit = pd.read_csv(cit_path, low_memory=False)
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)

    works = pd.read_csv(works_path, usecols=["doi", "source", "year"])
    works["doi_norm"] = works["doi"].apply(normalize_doi)

    fetched_dois = set(cit["source_doi"].dropna()) - {"", "nan", "none"}
    all_dois = set(works["doi_norm"].dropna()) - {"", "nan", "none"}
    never_fetched = all_dois - fetched_dois

    print(f"Corpus DOIs:          {len(all_dois):>7}")
    print(f"Fetched source DOIs:  {len(fetched_dois):>7}")
    print(f"Never fetched:        {len(never_fetched):>7}")

    # ── Sample 1: verify fetched DOIs ────────────────────────────────────────
    has_doi_ref = cit[
        cit["ref_doi"].notna() & (cit["ref_doi"] != "") & (cit["ref_doi"] != "nan")
    ]
    candidate_source_dois = has_doi_ref["source_doi"].unique()
    # Stratify by source
    merged = pd.DataFrame({"doi_norm": candidate_source_dois}).merge(
        works[["doi_norm", "source"]], on="doi_norm", how="left"
    ).dropna(subset=["source"])
    n = min(args.sample_n, len(merged))
    samples = []
    for src in merged["source"].unique():
        sub = merged[merged["source"] == src]
        k = max(1, int(n * len(sub) / len(merged)))
        k = min(k, len(sub))
        samples.append(sub.sample(k, random_state=args.seed))
    sample_df = pd.concat(samples).head(n)

    print(f"\nVerification sample:  {len(sample_df)} fetched DOIs")
    print("Querying Crossref...")

    verify_results = []
    for _, row in sample_df.iterrows():
        doi = row["doi_norm"]
        our_refs = set(
            has_doi_ref[has_doi_ref["source_doi"] == doi]["ref_doi"].dropna()
        ) - {"", "nan", "none"}
        our_total = len(cit[cit["source_doi"] == doi])

        cr_total, cr_doi_refs, status = fetch_crossref_refs(doi)
        if status != "ok":
            verify_results.append({"doi": doi, "source": row.get("source", ""),
                                   "status": status})
            print(f"  {doi}: {status}")
            continue

        matched = our_refs & cr_doi_refs
        precision = len(matched) / len(our_refs) if our_refs else 1.0
        recall = len(matched) / len(cr_doi_refs) if cr_doi_refs else 1.0
        verify_results.append({
            "doi": doi,
            "source": row.get("source", ""),
            "status": "ok",
            "our_total": our_total,
            "our_doi_refs": len(our_refs),
            "cr_total": cr_total,
            "cr_doi_refs": len(cr_doi_refs),
            "matched": len(matched),
            "only_ours": len(our_refs - cr_doi_refs),
            "only_cr": len(cr_doi_refs - our_refs),
            "precision": round(precision, 6),
            "recall": round(recall, 6),
        })

    ok_v = [r for r in verify_results if r.get("status") == "ok"]
    prec = np.mean([r["precision"] for r in ok_v]) if ok_v else float("nan")
    rec = np.mean([r["recall"] for r in ok_v]) if ok_v else float("nan")
    agg_prec = (
        sum(r["matched"] for r in ok_v) / sum(r["our_doi_refs"] for r in ok_v)
        if sum(r["our_doi_refs"] for r in ok_v) > 0 else float("nan")
    )
    agg_rec = (
        sum(r["matched"] for r in ok_v) / sum(r["cr_doi_refs"] for r in ok_v)
        if sum(r["cr_doi_refs"] for r in ok_v) > 0 else float("nan")
    )
    phantom = sum(1 for r in ok_v if r.get("only_ours", 0) > 0)
    missing = sum(1 for r in ok_v if r.get("only_cr", 0) > 0)

    print(f"\nVerification results:")
    print(f"  Success: {len(ok_v)}/{len(verify_results)}")
    print(f"  Mean precision: {prec:.4f}  Mean recall: {rec:.4f}")
    print(f"  Agg precision:  {agg_prec:.4f}  Agg recall:  {agg_rec:.4f}")
    print(f"  Papers with phantom refs: {phantom}")
    print(f"  Papers with missing refs: {missing}")

    # ── Sample 2: probe never-fetched DOIs ───────────────────────────────────
    never_list = list(never_fetched)
    np.random.shuffle(never_list)
    probe_sample = never_list[:args.never_fetched_n]

    print(f"\nProbing {len(probe_sample)} never-fetched DOIs...")
    probe_results = []
    for doi in probe_sample:
        cr_total, cr_doi_refs, status = fetch_crossref_refs(doi)
        probe_results.append({
            "doi": doi,
            "status": status,
            "cr_total": int(cr_total) if isinstance(cr_total, (int, float)) else 0,
            "cr_doi_refs": len(cr_doi_refs) if isinstance(cr_doi_refs, set) else 0,
        })

    n_found = sum(1 for r in probe_results if r["status"] == "ok")
    n_has_refs = sum(1 for r in probe_results if r.get("cr_total", 0) > 0)
    n_has_doi_refs = sum(1 for r in probe_results if r.get("cr_doi_refs", 0) > 0)
    mean_doi_refs = (
        np.mean([r["cr_doi_refs"] for r in probe_results if r["status"] == "ok"])
        if n_found > 0 else 0.0
    )
    est_new = int(len(never_fetched) * (n_has_doi_refs / len(probe_results))
                  * mean_doi_refs) if probe_results else 0

    print(f"  In Crossref: {n_found}/{len(probe_results)}")
    print(f"  With any refs: {n_has_refs}")
    print(f"  With DOI refs: {n_has_doi_refs}")
    print(f"  Est. new DOI-refs if all fetched: ~{est_new}")

    # ── Coverage summary ─────────────────────────────────────────────────────
    total_rows = len(cit)
    doi_ref_rows = (
        cit["ref_doi"].notna() & (cit["ref_doi"] != "") & (cit["ref_doi"] != "nan")
    ).sum()
    coverage_pct = round(len(fetched_dois) / len(all_dois) * 100, 1)

    # ── Save JSON report ─────────────────────────────────────────────────────
    report = {
        "generated": pd.Timestamp.now().isoformat(),
        "corpus": {
            "total_dois": len(all_dois),
            "fetched_dois": len(fetched_dois),
            "never_fetched_dois": len(never_fetched),
            "coverage_pct": coverage_pct,
            "total_citation_rows": int(total_rows),
            "doi_ref_rows": int(doi_ref_rows),
        },
        "verification": {
            "sample_n": len(verify_results),
            "success_n": len(ok_v),
            "mean_precision": round(float(prec), 6),
            "mean_recall": round(float(rec), 6),
            "aggregate_precision": round(float(agg_prec), 6),
            "aggregate_recall": round(float(agg_rec), 6),
            "papers_with_phantom_refs": int(phantom),
            "papers_with_missing_refs": int(missing),
            "details": verify_results,
        },
        "never_fetched_probe": {
            "probe_n": len(probe_results),
            "found_in_crossref": int(n_found),
            "with_any_refs": int(n_has_refs),
            "with_doi_refs": int(n_has_doi_refs),
            "mean_doi_refs_per_doi": round(float(mean_doi_refs), 2),
            "estimated_new_doi_refs": int(est_new),
            "details": probe_results,
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
