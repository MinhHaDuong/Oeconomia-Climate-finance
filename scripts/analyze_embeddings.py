"""Semantic landscape analysis: UMAP projection + KMeans clustering.

Phase 2 analysis step: loads pre-computed embeddings.npz (from enrich_embeddings.py)
and produces UMAP projections, KMeans clusters, and cross-validation with
co-citation communities.

Method:
- Load embeddings.npz vectors and associated works metadata
- UMAP dimensionality reduction to 2D
- KMeans clustering to identify discourse communities
- Cross-validate with co-citation communities (if available)

Produces:
- data/catalogs/semantic_clusters.csv: Cluster assignments with UMAP coordinates
"""

import argparse
import os
import warnings
from collections import Counter

import numpy as np
import pandas as pd
from utils import (
    CATALOGS_DIR,
    EMBEDDINGS_PATH,
    get_logger,
    load_analysis_config,
    normalize_doi,
    work_key,
)

log = get_logger("analyze_embeddings")

warnings.filterwarnings("ignore", category=FutureWarning)

CLUSTERS_PATH = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--works-input",
        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
        help="Works CSV with metadata (default: enriched_works.csv)",
    )
    parser.add_argument(
        "--embeddings-input",
        default=EMBEDDINGS_PATH,
        help="Embeddings .npz file (default: embeddings.npz)",
    )
    args = parser.parse_args()

    # Defer heavy imports so --help works without analysis group installed
    import umap
    from sklearn.cluster import KMeans

    # --- Load works metadata ---
    log.info("Loading works from %s...", args.works_input)
    works = pd.read_csv(args.works_input)

    # Filter: must have a title, year in range (from config)
    _cfg = load_analysis_config()
    _year_min = _cfg["periodization"]["year_min"]
    _year_max = _cfg["periodization"]["year_max"]
    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
    df = works[has_title & in_range].copy().reset_index(drop=True)
    log.info("Works with titles (%d-%d): %d", _year_min, _year_max, len(df))

    # --- Load pre-computed embeddings ---
    log.info("Loading embeddings from %s...", args.embeddings_input)
    cache = np.load(args.embeddings_input, allow_pickle=True)
    cached_keys = cache["keys"]
    cached_vecs = cache["vectors"]
    key_to_vec = dict(zip(cached_keys, cached_vecs))
    log.info("Loaded %d cached embeddings", len(key_to_vec))

    # Build keys and align embeddings to df order
    df["_key"] = df.apply(work_key, axis=1)
    dim = cached_vecs.shape[1]
    embeddings = np.zeros((len(df), dim), dtype=np.float32)
    n_matched = 0
    for i, key in enumerate(df["_key"]):
        if key in key_to_vec:
            embeddings[i] = key_to_vec[key]
            n_matched += 1
    log.info("Matched %d / %d works to embeddings", n_matched, len(df))
    n_unmatched = len(df) - n_matched
    if n_unmatched > 0:
        match_pct = 100 * n_matched / len(df)
        log.warning("%d works have no embedding (%.1f%% match rate) — "
                    "zero vectors will distort UMAP/clustering. "
                    "Re-run enrich_embeddings.py if this is unexpected.", n_unmatched, match_pct)

    # ============================================================
    # Step 1: UMAP dimensionality reduction
    # ============================================================

    log.info("Computing UMAP projection...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.05,
        metric="cosine",
        random_state=42,
        low_memory=True,
    )
    coords = reducer.fit_transform(embeddings)
    df["umap_x"] = coords[:, 0]
    df["umap_y"] = coords[:, 1]
    log.info("UMAP done: %s", coords.shape)

    # ============================================================
    # Step 2: KMeans clustering
    # ============================================================

    cfg = load_analysis_config()
    k = cfg["clustering"]["k"]
    log.info("Clustering with KMeans (k=%d from config/analysis.yaml)...", k)
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=20)
    df["semantic_cluster"] = kmeans.fit_predict(coords)
    n_clusters = k
    log.info("Semantic clusters: %d", n_clusters)

    # Cluster sizes
    for c in range(n_clusters):
        log.info("  Cluster %d: %d", c, (df['semantic_cluster'] == c).sum())

    # ============================================================
    # Step 3: Characterize clusters
    # ============================================================

    log.info("=== Cluster keyword profiles ===")
    for c in range(n_clusters):
        members = df[df["semantic_cluster"] == c]
        all_kw = []
        for kw_str in members["keywords"].dropna():
            all_kw.extend([k.strip().lower() for k in str(kw_str).split(";")])
        kw_counts = Counter(all_kw).most_common(10)
        kw_str = ", ".join(f"{k} ({n})" for k, n in kw_counts)
        median_year = int(members["year"].median())
        log.info("Cluster %d (n=%d, median year=%d): %s", c, len(members), median_year, kw_str)

    # ============================================================
    # Step 4: Cross-validate with co-citation communities
    # ============================================================

    cocit_path = os.path.join(CATALOGS_DIR, "communities.csv")
    if os.path.exists(cocit_path):
        log.info("=== Cross-validation with co-citation communities ===")
        cocit = pd.read_csv(cocit_path)
        df["doi_norm"] = df["doi"].apply(normalize_doi)
        cocit["doi_norm"] = cocit["doi"].apply(normalize_doi)

        merged = df.merge(cocit[["doi_norm", "community"]], on="doi_norm", how="inner")
        if len(merged) > 0:
            cross_tab = pd.crosstab(
                merged["semantic_cluster"],
                merged["community"],
                margins=True,
            )
            log.info("Matched %d works with both assignments:\n%s", len(merged), cross_tab)
        else:
            log.info("No DOI matches between semantic clusters and co-citation communities")

    # --- Save cluster assignments ---
    out = df[["source", "doi", "title", "first_author", "year", "language",
              "semantic_cluster", "umap_x", "umap_y"]].copy()
    out.to_csv(CLUSTERS_PATH, index=False)
    log.info("Saved cluster assignments → %s. Done.", CLUSTERS_PATH)


if __name__ == "__main__":
    main()
