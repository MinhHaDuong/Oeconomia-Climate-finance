#!/usr/bin/env python3
"""Embedding semantic quality validation.

Tests whether pre-computed embeddings capture topical similarity by comparing
within-cluster vs. between-cluster cosine similarity, and provides a
nearest-neighbour spot-check for human inspection.

No API calls — all computation is local (numpy/scipy on refined_embeddings.npz).

Saves results to content/tables/qa_embeddings_report.json

Usage:
    uv run python scripts/qa_embeddings.py [--n-pairs 200] [--n-neighbours 5] [--seed 42]
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
from scipy import stats
from utils import (
    CATALOGS_DIR,
    REFINED_EMBEDDINGS_PATH,
    REFINED_WORKS_PATH,
    get_logger,
)

log = get_logger("qa_embeddings")

CLUSTERS_PATH = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")
OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "content", "tables", "qa_embeddings_report.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors. Returns 0.0 if either is zero."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Cohen's d effect size using pooled standard deviation."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0.0:
        return 0.0
    return float((np.mean(group1) - np.mean(group2)) / pooled_std)


def _ci_95(arr: np.ndarray) -> list[float]:
    """95% confidence interval on the mean (normal approximation)."""
    mean = np.mean(arr)
    se = np.std(arr, ddof=1) / np.sqrt(len(arr))
    return [float(mean - 1.96 * se), float(mean + 1.96 * se)]


def _load_embeddings_with_clusters():
    """Load refined embeddings and match with cluster assignments.

    Returns (vectors, cluster_labels, works_df) where vectors and
    cluster_labels are row-aligned numpy arrays, and works_df has the
    metadata for the matched subset.
    """
    log.info("Loading refined embeddings from %s", REFINED_EMBEDDINGS_PATH)
    vectors = np.load(REFINED_EMBEDDINGS_PATH)["vectors"]
    log.info("  shape: %s", vectors.shape)

    log.info("Loading refined works from %s", REFINED_WORKS_PATH)
    works = pd.read_csv(REFINED_WORKS_PATH, low_memory=False)
    log.info("  rows: %d", len(works))

    log.info("Loading semantic clusters from %s", CLUSTERS_PATH)
    clusters = pd.read_csv(CLUSTERS_PATH, usecols=["doi", "title", "first_author", "semantic_cluster"])
    log.info("  rows: %d", len(clusters))

    # Match works to clusters: primary key is DOI, fallback is title+first_author
    # Deduplicate clusters to avoid many-to-many joins
    clusters_with_doi = clusters[clusters["doi"].notna()].drop_duplicates(subset="doi", keep="first")
    clusters_no_doi = clusters[clusters["doi"].isna()].drop_duplicates(
        subset=["title", "first_author"], keep="first"
    )

    # Add row index to works so we can map back to embedding vectors
    works["_row_idx"] = range(len(works))

    # Match by DOI
    works_with_doi = works[works["doi"].notna()].copy()
    matched_doi = works_with_doi.merge(
        clusters_with_doi[["doi", "semantic_cluster"]], on="doi", how="inner"
    )

    # Match by title+first_author for DOI-less works
    works_no_doi = works[works["doi"].isna()].copy()
    matched_title = works_no_doi.merge(
        clusters_no_doi[["title", "first_author", "semantic_cluster"]],
        on=["title", "first_author"],
        how="inner",
    )

    matched = pd.concat([matched_doi, matched_title], ignore_index=True)
    log.info("Matched %d / %d refined works to cluster assignments", len(matched), len(works))

    # Extract aligned vectors and cluster labels
    row_indices = matched["_row_idx"].values
    matched_vectors = vectors[row_indices]
    cluster_labels = matched["semantic_cluster"].values

    return matched_vectors, cluster_labels, matched


# ---------------------------------------------------------------------------
# Test 1: within-cluster vs. between-cluster similarity
# ---------------------------------------------------------------------------

def compute_within_vs_between(
    vectors: np.ndarray,
    labels: np.ndarray,
    n_pairs: int,
    rng: np.random.Generator,
) -> dict:
    """Sample within-cluster and between-cluster pairs, compare similarity."""
    unique_clusters = np.unique(labels)
    n_clusters = len(unique_clusters)
    log.info("Sampling %d within-cluster and %d between-cluster pairs across %d clusters",
             n_pairs, n_pairs, n_clusters)

    # Build cluster-to-indices mapping
    cluster_indices = {c: np.where(labels == c)[0] for c in unique_clusters}
    # Only use clusters with >= 2 members for within-cluster sampling
    viable_clusters = [c for c, idx in cluster_indices.items() if len(idx) >= 2]

    # --- Within-cluster pairs ---
    within_sims = []
    for _ in range(n_pairs):
        # Pick a random viable cluster, then two distinct members
        c = rng.choice(viable_clusters)
        idx = cluster_indices[c]
        i, j = rng.choice(len(idx), size=2, replace=False)
        sim = _cosine_similarity(vectors[idx[i]], vectors[idx[j]])
        within_sims.append(sim)
    within_sims = np.array(within_sims)

    # --- Between-cluster pairs ---
    between_sims = []
    for _ in range(n_pairs):
        # Pick two different clusters, one member from each
        c1, c2 = rng.choice(unique_clusters, size=2, replace=False)
        i = rng.choice(cluster_indices[c1])
        j = rng.choice(cluster_indices[c2])
        sim = _cosine_similarity(vectors[i], vectors[j])
        between_sims.append(sim)
    between_sims = np.array(between_sims)

    # --- Statistics ---
    mean_within = float(np.mean(within_sims))
    mean_between = float(np.mean(between_sims))
    effect_size = _cohens_d(within_sims, between_sims)
    u_stat, p_value = stats.mannwhitneyu(
        within_sims, between_sims, alternative="greater"
    )

    result = {
        "mean_within": mean_within,
        "mean_between": mean_between,
        "std_within": float(np.std(within_sims, ddof=1)),
        "std_between": float(np.std(between_sims, ddof=1)),
        "ci_within": _ci_95(within_sims),
        "ci_between": _ci_95(between_sims),
        "effect_size": effect_size,
        "effect_size_metric": "cohens_d",
        "mann_whitney_u": float(u_stat),
        "p_value": float(p_value),
        "n_within_pairs": n_pairs,
        "n_between_pairs": n_pairs,
        "n_clusters": n_clusters,
    }

    log.info("  mean within:  %.4f  CI [%.4f, %.4f]",
             mean_within, result["ci_within"][0], result["ci_within"][1])
    log.info("  mean between: %.4f  CI [%.4f, %.4f]",
             mean_between, result["ci_between"][0], result["ci_between"][1])
    log.info("  Cohen's d:    %.3f", effect_size)
    log.info("  Mann-Whitney U: %.1f  p = %.2e", u_stat, p_value)

    return result


# ---------------------------------------------------------------------------
# Test 2: nearest-neighbour spot-check
# ---------------------------------------------------------------------------

# Landmark works for spot-checking: search terms matched against titles
LANDMARK_QUERIES = [
    "Stern Review",
    "IPCC",
    "Paris Agreement",
    "green bond",
    "carbon tax",
    "climate risk",
    "stranded assets",
    "adaptation finance",
    "carbon market",
    "ESG",
]


def find_nearest_neighbours(
    vectors: np.ndarray,
    works_df: pd.DataFrame,
    n_landmarks: int,
    n_neighbours: int,
    rng: np.random.Generator,
) -> list[dict]:
    """Find nearest neighbours for landmark works or high-cited fallbacks."""
    # L2-normalize all vectors for fast cosine similarity via dot product
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # avoid division by zero
    normed = vectors / norms

    landmarks = []

    # Try to find landmarks by title search
    for query in LANDMARK_QUERIES:
        if len(landmarks) >= n_landmarks:
            break
        mask = works_df["title"].str.contains(query, case=False, na=False)
        candidates = works_df[mask]
        if len(candidates) > 0:
            # Pick the most cited one
            if "cited_by_count" in candidates.columns:
                best = candidates.sort_values("cited_by_count", ascending=False).iloc[0]
            else:
                best = candidates.iloc[0]
            idx = works_df.index.get_loc(best.name)
            if idx not in [lm["idx"] for lm in landmarks]:
                landmarks.append({"idx": idx, "title": best["title"], "doi": best.get("doi", "")})

    # Fallback: fill remaining slots with high-cited works
    if len(landmarks) < n_landmarks and "cited_by_count" in works_df.columns:
        existing_indices = {lm["idx"] for lm in landmarks}
        top_cited = works_df.sort_values("cited_by_count", ascending=False)
        for _, row in top_cited.iterrows():
            if len(landmarks) >= n_landmarks:
                break
            idx = works_df.index.get_loc(row.name)
            if idx not in existing_indices:
                landmarks.append({"idx": idx, "title": row["title"], "doi": row.get("doi", "")})
                existing_indices.add(idx)

    # If still not enough, pick random works
    if len(landmarks) < n_landmarks:
        existing_indices = {lm["idx"] for lm in landmarks}
        available = [i for i in range(len(works_df)) if i not in existing_indices]
        picks = rng.choice(available, size=min(n_landmarks - len(landmarks), len(available)), replace=False)
        for idx in picks:
            row = works_df.iloc[idx]
            landmarks.append({"idx": int(idx), "title": row["title"], "doi": row.get("doi", "")})

    log.info("Selected %d landmark works for nearest-neighbour spot-check", len(landmarks))

    # Find neighbours for each landmark
    results = []
    for lm in landmarks:
        query_vec = normed[lm["idx"]]
        # Cosine similarity = dot product on L2-normalized vectors
        sims = normed @ query_vec
        # Exclude self
        sims[lm["idx"]] = -1.0
        top_k = np.argsort(sims)[-n_neighbours:][::-1]

        neighbours = []
        for ni in top_k:
            row = works_df.iloc[ni]
            neighbours.append({
                "doi": str(row.get("doi", "")),
                "title": str(row["title"]),
                "similarity": float(sims[ni]),
            })

        results.append({
            "query_doi": str(lm["doi"]),
            "query_title": str(lm["title"]),
            "neighbours": neighbours,
        })
        log.info("  %s", lm["title"][:70])
        for nb in neighbours:
            log.info("    %.4f  %s", nb["similarity"], nb["title"][:60])

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-pairs", type=int, default=200,
                        help="Number of pairs to sample for within/between test (default: 200)")
    parser.add_argument("--n-neighbours", type=int, default=5,
                        help="Number of nearest neighbours per landmark (default: 5)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    # Load data
    vectors, labels, works_df = _load_embeddings_with_clusters()

    # Test 1: within-cluster vs between-cluster similarity
    log.info("=== Test 1: within-cluster vs between-cluster similarity ===")
    wb_result = compute_within_vs_between(vectors, labels, args.n_pairs, rng)

    # Test 2: nearest-neighbour spot-check
    log.info("=== Test 2: nearest-neighbour spot-check ===")
    nn_result = find_nearest_neighbours(
        vectors, works_df, n_landmarks=10, n_neighbours=args.n_neighbours, rng=rng
    )

    # Save report
    report = {
        "within_vs_between": wb_result,
        "nearest_neighbours": nn_result,
        "parameters": {
            "n_pairs": args.n_pairs,
            "n_neighbours": args.n_neighbours,
            "seed": args.seed,
            "n_works_matched": len(works_df),
            "n_embeddings_total": int(np.load(REFINED_EMBEDDINGS_PATH)["vectors"].shape[0]),
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    log.info("Report saved to %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
