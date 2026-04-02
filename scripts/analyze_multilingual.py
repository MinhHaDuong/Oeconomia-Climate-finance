"""Multilingual epistemic structure analysis.

Computes language x geography statistics, semantic isolation scores,
and citation directionality for the multilingual research note.

Outputs a JSON report with all preliminary results.
"""

import json
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics.pairwise import cosine_distances

from build_het_core import is_global_south, is_non_english
from pipeline_loaders import (
    CATALOGS_DIR,
    REFINED_WORKS_PATH,
    load_refined_citations,
    load_refined_embeddings,
)
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("analyze_multilingual")


def classify_quadrant(row):
    """Assign work to one of four quadrants: EN-N, EN-S, nonEN-N, nonEN-S.

    Returns None if classification is impossible (missing language or affiliation).
    """
    lang = str(row.get("language", "") or "").lower().strip()
    if not lang:
        return None

    is_en = not is_non_english(row)
    aff = str(row.get("affiliations", "") or "").lower().strip()
    if not aff:
        return None  # Cannot determine geography without affiliations

    south = is_global_south(row)
    if is_en and not south:
        return "EN-N"
    elif is_en and south:
        return "EN-S"
    elif not is_en and not south:
        return "nonEN-N"
    else:
        return "nonEN-S"


def compute_language_stats(df):
    """Table T1: corpus composition by language."""
    lang_counts = df["language"].fillna("missing").value_counts()
    total = len(df)
    result = {}
    for lang, count in lang_counts.items():
        result[lang] = {"n": int(count), "pct": round(100 * count / total, 2)}
    return result


def compute_quadrant_stats(df):
    """Table T2: four-quadrant classification."""
    df = df.copy()
    df["quadrant"] = df.apply(classify_quadrant, axis=1)
    classified = df.dropna(subset=["quadrant"])

    total_classified = len(classified)
    result = {}
    for q in ["EN-N", "EN-S", "nonEN-N", "nonEN-S"]:
        subset = classified[classified["quadrant"] == q]
        n = len(subset)
        result[q] = {
            "n": int(n),
            "pct": round(100 * n / total_classified, 2) if total_classified else 0.0,
            "mean_cited_by": round(float(subset["cited_by_count"].mean()), 1) if n else 0.0,
            "median_cited_by": round(float(subset["cited_by_count"].median()), 1) if n else 0.0,
        }
    result["unclassified"] = int(len(df) - total_classified)
    return result


def compute_contingency(df, clusters_df):
    """Table T3: language x cluster contingency table + chi-squared test."""
    merged = df.merge(
        clusters_df[["doi", "semantic_cluster"]],
        on="doi",
        how="inner",
    )
    merged["lang_group"] = merged["language"].fillna("missing").apply(
        lambda x: x if x in ("en", "pt", "de", "es", "fr", "zh", "ja", "missing") else "other"
    )

    ct = pd.crosstab(merged["lang_group"], merged["semantic_cluster"])
    chi2, p, dof, expected = stats.chi2_contingency(ct)

    # Standardized residuals
    residuals = (ct.values - expected) / np.sqrt(expected)

    return {
        "contingency_table": ct.to_dict(),
        "chi2": round(float(chi2), 2),
        "p_value": float(p),
        "dof": int(dof),
        "significant_cells": [
            {
                "lang": ct.index[i],
                "cluster": int(ct.columns[j]),
                "residual": round(float(residuals[i, j]), 2),
            }
            for i in range(residuals.shape[0])
            for j in range(residuals.shape[1])
            if abs(residuals[i, j]) > 2.0
        ],
    }


def compute_isolation_scores(df, embeddings, k=10):
    """Compute semantic isolation score for each work.

    Isolation = mean cosine distance to k nearest EN-North neighbors.
    """
    df = df.copy()
    df["quadrant"] = df.apply(classify_quadrant, axis=1)
    classified_mask = df["quadrant"].notna()

    # Get EN-North indices
    en_north_mask = df["quadrant"] == "EN-N"
    en_north_indices = df.index[en_north_mask & classified_mask].tolist()

    if len(en_north_indices) < k:
        log.warning("Too few EN-North works (%d) for k=%d", len(en_north_indices), k)
        return {}

    en_north_emb = embeddings[en_north_indices]

    # Compute isolation for each classified non-EN-North work
    results = {}
    for quadrant in ["EN-S", "nonEN-N", "nonEN-S"]:
        q_mask = df["quadrant"] == quadrant
        q_indices = df.index[q_mask].tolist()
        if not q_indices:
            continue

        q_emb = embeddings[q_indices]

        # Compute cosine distances to all EN-North works in chunks
        chunk_size = 500
        isolation_scores = []
        for start in range(0, len(q_indices), chunk_size):
            end = min(start + chunk_size, len(q_indices))
            chunk_emb = q_emb[start:end]
            dists = cosine_distances(chunk_emb, en_north_emb)
            # Mean of k nearest neighbors
            for row_dists in dists:
                knn_dists = np.partition(row_dists, k)[:k]
                isolation_scores.append(float(np.mean(knn_dists)))

        scores = np.array(isolation_scores)
        results[quadrant] = {
            "n": len(scores),
            "mean": round(float(np.mean(scores)), 4),
            "median": round(float(np.median(scores)), 4),
            "std": round(float(np.std(scores)), 4),
            "p10": round(float(np.percentile(scores, 10)), 4),
            "p90": round(float(np.percentile(scores, 90)), 4),
        }

    # EN-North baseline: distance to own quadrant (sampled)
    sample_size = min(2000, len(en_north_indices))
    rng = np.random.RandomState(42)
    sample_idx = rng.choice(len(en_north_indices), sample_size, replace=False)
    sample_emb = en_north_emb[sample_idx]
    dists = cosine_distances(sample_emb, en_north_emb)
    baseline_scores = []
    for row_dists in dists:
        # partition k+1 smallest, skip self (index 0 after partition)
        knn_dists = np.partition(row_dists, k + 1)[:k + 1]
        knn_dists = np.sort(knn_dists)[1:]  # drop the self-distance (0)
        baseline_scores.append(float(np.mean(knn_dists)))
    baseline = np.array(baseline_scores)
    results["EN-N"] = {
        "n": len(baseline),
        "mean": round(float(np.mean(baseline)), 4),
        "median": round(float(np.median(baseline)), 4),
        "std": round(float(np.std(baseline)), 4),
        "p10": round(float(np.percentile(baseline, 10)), 4),
        "p90": round(float(np.percentile(baseline, 90)), 4),
        "note": f"baseline sample of {sample_size}",
    }

    return results


def compute_citation_directionality(df, citations_df):
    """Table T6: citation flows by geography (N->N, N->S, S->N, S->S)."""
    df = df.copy()
    df["quadrant"] = df.apply(classify_quadrant, axis=1)
    geo_map = {"EN-N": "N", "nonEN-N": "N", "EN-S": "S", "nonEN-S": "S"}
    df["geo"] = df["quadrant"].map(geo_map)

    doi_geo = df.dropna(subset=["geo"]).set_index("doi")["geo"]

    # Vectorized: map source and ref DOIs to geography
    src_geo = citations_df["source_doi"].map(doi_geo)
    ref_geo = citations_df["ref_doi"].map(doi_geo)

    classified_mask = src_geo.notna() & ref_geo.notna()
    flow_labels = src_geo[classified_mask] + "\u2192" + ref_geo[classified_mask]
    flow_counts = flow_labels.value_counts().to_dict()

    flows = {
        "N\u2192N": flow_counts.get("N\u2192N", 0),
        "N\u2192S": flow_counts.get("N\u2192S", 0),
        "S\u2192N": flow_counts.get("S\u2192N", 0),
        "S\u2192S": flow_counts.get("S\u2192S", 0),
        "unclassified": int((~classified_mask).sum()),
    }

    total_classified = sum(v for k, v in flows.items() if k != "unclassified")
    if total_classified > 0:
        flows["pct"] = {
            k: round(100 * v / total_classified, 2)
            for k, v in flows.items()
            if k != "unclassified"
        }
        ns = flows["N\u2192S"]
        sn = flows["S\u2192N"]
        flows["asymmetry_ratio"] = round(ns / sn, 3) if sn > 0 else None

    return flows


def compute_core_composition(df):
    """Language and geography composition of the core subset (cited >= 50)."""
    core = df[df["cited_by_count"] >= 50].copy()
    core["quadrant"] = core.apply(classify_quadrant, axis=1)
    core["is_en"] = ~core.apply(is_non_english, axis=1)

    total = len(core)
    en_count = int(core["is_en"].sum())
    quadrant_counts = core["quadrant"].value_counts().to_dict()

    return {
        "total": total,
        "english": en_count,
        "english_pct": round(100 * en_count / total, 1) if total > 0 else 0,
        "quadrants": {k: int(v) for k, v in quadrant_counts.items()},
    }


def main():
    args, _ = parse_io_args()
    validate_io(output=args.output)

    log.info("Loading corpus...")
    df = pd.read_csv(REFINED_WORKS_PATH, low_memory=False)
    embeddings = load_refined_embeddings()
    assert len(df) == len(embeddings), (
        f"Row mismatch: {len(df)} works vs {embeddings.shape[0]} embeddings"
    )
    df = df.reset_index(drop=True)
    log.info("Loaded %d works with %s embeddings", len(df), embeddings.shape)

    log.info("Loading citations...")
    citations_df = load_refined_citations()
    log.info("Loaded %d citation edges", len(citations_df))

    clusters_path = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")
    clusters_df = pd.read_csv(clusters_path, low_memory=False)
    log.info("Loaded %d cluster assignments", len(clusters_df))

    report = {}

    log.info("Computing language stats...")
    report["language_stats"] = compute_language_stats(df)

    log.info("Computing quadrant stats...")
    report["quadrant_stats"] = compute_quadrant_stats(df)

    log.info("Computing language x cluster contingency...")
    report["contingency"] = compute_contingency(df, clusters_df)

    log.info("Computing isolation scores (k=10)...")
    report["isolation_k10"] = compute_isolation_scores(df, embeddings, k=10)

    log.info("Computing isolation scores (k=5)...")
    report["isolation_k5"] = compute_isolation_scores(df, embeddings, k=5)

    log.info("Computing isolation scores (k=20)...")
    report["isolation_k20"] = compute_isolation_scores(df, embeddings, k=20)

    log.info("Computing citation directionality...")
    report["citation_flows"] = compute_citation_directionality(df, citations_df)

    log.info("Computing core composition...")
    report["core_composition"] = compute_core_composition(df)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info("Report saved to %s", args.output)


if __name__ == "__main__":
    main()
