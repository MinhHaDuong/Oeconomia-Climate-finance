#!/usr/bin/env python3
"""Heatmap: co-citation communities vs KMeans clusters across 4 time windows.

Produces a 2x2 figure where each subplot shows a contingency heatmap:
  - X-axis: co-citation communities (sorted by size, descending)
  - Y-axis: KMeans clusters (k=6 on embeddings)
  - Cell intensity: number of unique citing papers

Indirect mapping: for each co-citation community, count unique corpus papers
(that have a KMeans cluster assignment) citing at least one reference in that
community.

Usage:
    uv run python scripts/plot_heatmap_communities_clusters.py \
        --output content/figures/heatmap_communities_clusters.png [--pdf]
    uv run python scripts/plot_heatmap_communities_clusters.py \
        --output content/figures/heatmap_communities_clusters.png \
        --input refined_works.csv refined_embeddings.npz refined_citations.csv
"""

import argparse
import os
from collections import defaultdict

import numpy as np
import pandas as pd
from plot_style import DARK, DPI, MED, apply_style
from scipy.sparse import lil_matrix
from script_io_args import parse_io_args, validate_io
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    get_logger,
    load_analysis_config,
    load_cluster_labels,
    load_refined_citations,
    load_refined_embeddings,
    normalize_doi,
    save_figure,
)

log = get_logger("plot_heatmap_communities_clusters")

# --- Parameters ---
WINDOWS = [
    {"label": "Pre-2007", "cutoff": 2006},
    {"label": "Pre-2015", "cutoff": 2014},
    {"label": "Pre-2020", "cutoff": 2019},
    {"label": "Full",     "cutoff": 2024},
]
TOP_N = 250
MIN_COCIT = 3
RESOLUTION = 1.0
RANDOM_STATE = 42
K_CLUSTERS = 6


def detect_communities(cit, ref_counts, source_groups,
                       cutoff_year, top_n, min_cocit, resolution,
                       random_state):
    """Build co-citation network and detect Louvain communities."""
    import community as community_louvain
    import networkx as nx

    log.info("  Window: year <= %d", cutoff_year)

    pre_refs = set(
        cit[cit["ref_year_num"] <= cutoff_year]["ref_doi"]
    ) - {"", "nan", "none"}

    pre_ref_counts = ref_counts[ref_counts.index.isin(pre_refs)]
    actual_n = min(top_n, len(pre_ref_counts))
    if actual_n == 0:
        return {}
    top_refs = pre_ref_counts.head(actual_n).index.tolist()
    top_set = set(top_refs)
    ref_to_idx = {ref: i for i, ref in enumerate(top_refs)}
    log.info("    Top %d refs, citation range: %s..%s",
             actual_n,
             pre_ref_counts.iloc[0],
             pre_ref_counts.iloc[actual_n - 1])

    cocit_matrix = lil_matrix((actual_n, actual_n), dtype=np.float64)
    for ref_list in source_groups.values:
        refs_in_top = [r for r in ref_list if r in top_set]
        if len(refs_in_top) < 2:
            continue
        for i in range(len(refs_in_top)):
            for j in range(i + 1, len(refs_in_top)):
                a = ref_to_idx[refs_in_top[i]]
                b = ref_to_idx[refs_in_top[j]]
                cocit_matrix[a, b] += 1
                cocit_matrix[b, a] += 1

    cocit_dense = cocit_matrix.toarray()

    G = nx.Graph()
    for i, doi in enumerate(top_refs):
        G.add_node(doi)
    for i in range(actual_n):
        for j in range(i + 1, actual_n):
            w = cocit_dense[i, j]
            if w >= min_cocit:
                G.add_edge(top_refs[i], top_refs[j], weight=w)

    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    log.info("    Network: %d nodes, %d edges (%d isolates removed)",
             G.number_of_nodes(), G.number_of_edges(), len(isolates))

    if G.number_of_nodes() == 0:
        return {}

    partition = community_louvain.best_partition(
        G, weight="weight", resolution=resolution,
        random_state=random_state,
    )
    n_comm = len(set(partition.values()))
    log.info("    Louvain: %d communities", n_comm)

    return partition


def build_heatmap_data(partition, ref_to_citers, doi_to_cluster,
                       k_clusters):
    """Build contingency matrix: communities (sorted by size) vs clusters."""
    if not partition:
        return None, [], []

    comm_dois = defaultdict(set)
    for doi, c in partition.items():
        comm_dois[c].add(doi)

    sorted_comms = sorted(
        comm_dois.keys(),
        key=lambda c: len(comm_dois[c]),
        reverse=True,
    )

    n_comms = len(sorted_comms)
    matrix = np.zeros((k_clusters, n_comms), dtype=int)

    for col_idx, comm_id in enumerate(sorted_comms):
        citers_by_cluster = defaultdict(set)
        for ref_doi in comm_dois[comm_id]:
            for src_doi in ref_to_citers.get(ref_doi, set()):
                cl = doi_to_cluster[src_doi]
                citers_by_cluster[cl].add(src_doi)

        for cl in range(k_clusters):
            matrix[cl, col_idx] = len(citers_by_cluster[cl])

    comm_labels = [
        f"C{i}\n({len(comm_dois[sorted_comms[i]])})"
        for i in range(n_comms)
    ]
    comm_sizes = [len(comm_dois[c]) for c in sorted_comms]

    return matrix, comm_labels, comm_sizes


def _render_heatmap(heatmap_data, cluster_short, out_stem, pdf):
    """Render 2x2 heatmap figure and save it."""
    import matplotlib.pyplot as plt

    log.info("--- Step 5: Plotting ---")

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    fig.suptitle("Co-citation communities vs KMeans clusters",
                 fontsize=11, fontweight="bold", y=0.98)

    cluster_labels_y = [cluster_short[i] for i in range(K_CLUSTERS)]

    for idx, w in enumerate(WINDOWS):
        ax = axes[idx // 2][idx % 2]
        label = w["label"]
        data = heatmap_data[label]
        matrix = data["matrix"]
        comm_labels = data["comm_labels"]
        n_comm = data["n_communities"]

        if matrix is None or matrix.size == 0:
            ax.set_title(f"{label} -- no communities")
            ax.axis("off")
            continue

        display = np.log1p(matrix).astype(float)
        ax.imshow(display, aspect="auto", cmap="Greys",
                  interpolation="nearest",
                  vmin=0, vmax=np.log1p(matrix.max()))

        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                val = matrix[i, j]
                if val > 0:
                    threshold = display.max() * 0.6
                    color = ("white" if display[i, j] > threshold
                             else DARK)
                    fontsize = 6 if matrix.shape[1] > 10 else 7
                    ax.text(j, i, str(val), ha="center",
                            va="center", fontsize=fontsize,
                            color=color)

        ax.set_xticks(range(len(comm_labels)))
        ax.set_xticklabels(comm_labels, fontsize=6, ha="center")
        ax.set_yticks(range(K_CLUSTERS))
        ax.set_yticklabels(cluster_labels_y, fontsize=7)

        ax.set_xlabel("Co-citation community (refs)", fontsize=7)
        if idx % 2 == 0:
            ax.set_ylabel("KMeans cluster", fontsize=7)

        ax.set_title(f"{label} ({n_comm} communities)", fontsize=9)

        ax.set_xticks(np.arange(-0.5, len(comm_labels), 1),
                      minor=True)
        ax.set_yticks(np.arange(-0.5, K_CLUSTERS, 1), minor=True)
        ax.grid(which="minor", color=MED, linewidth=0.3, alpha=0.5)
        ax.tick_params(which="minor", length=0)

        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(0.5)
            spine.set_color(MED)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save_figure(fig, out_stem, pdf=pdf, dpi=DPI)
    plt.close(fig)


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output, inputs=io_args.input)

    parser = argparse.ArgumentParser(
        description="Heatmap: communities vs clusters")
    parser.add_argument("--pdf", action="store_true",
                        help="Also save PDF output")
    args = parser.parse_args(extra)

    apply_style()
    import community as community_louvain  # noqa: F401
    import matplotlib.pyplot as plt
    import networkx as nx  # noqa: F401
    from sklearn.cluster import KMeans

    out_stem = os.path.splitext(io_args.output)[0]

    # --- Input resolution ---
    works_path = (
        io_args.input[0] if io_args.input
        else os.path.join(CATALOGS_DIR, "refined_works.csv")
    )
    if io_args.input and len(io_args.input) >= 2:
        emb_path = io_args.input[1]
    else:
        emb_path = None
    if io_args.input and len(io_args.input) >= 3:
        cit_path = io_args.input[2]
    else:
        cit_path = None

    cluster_short = load_cluster_labels()

    # ============================================================
    # Step 1: Load data and run KMeans
    # ============================================================

    log.info("=" * 70)
    log.info("HEATMAP: CO-CITATION COMMUNITIES vs KMEANS CLUSTERS")
    log.info("=" * 70)

    log.info("--- Step 1: Load data and run KMeans ---")
    works = pd.read_csv(works_path)
    works["year"] = pd.to_numeric(works["year"], errors="coerce")

    _cfg = load_analysis_config()
    _year_min = _cfg["periodization"]["year_min"]
    _year_max = _cfg["periodization"]["year_max"]
    has_abstract = (works["abstract"].notna()
                    & (works["abstract"].str.len() > 50))
    in_range = ((works["year"] >= _year_min)
                & (works["year"] <= _year_max))
    df = works[has_abstract & in_range].copy().reset_index(drop=True)
    log.info("Works with abstracts (%d-%d): %d",
             _year_min, _year_max, len(df))

    if emb_path is not None:
        embeddings = np.load(emb_path)["vectors"]
    else:
        embeddings = load_refined_embeddings()
    # Filter embeddings to match df (abstract + year filter)
    all_mask = (has_abstract & in_range).values
    if len(embeddings) == len(works):
        embeddings = embeddings[all_mask]
    if len(embeddings) != len(df):
        raise RuntimeError(
            f"Embedding cache size mismatch ({len(embeddings)} vs "
            f"{len(df)}). Re-run analyze_embeddings.py first."
        )
    log.info("Embedding shape: %s", embeddings.shape)

    kmeans = KMeans(n_clusters=K_CLUSTERS, random_state=42, n_init=20)
    df["cluster"] = kmeans.fit_predict(embeddings)
    df["doi_norm"] = df["doi"].apply(normalize_doi)

    doi_to_cluster = {}
    for _, row in df.iterrows():
        d = row["doi_norm"]
        if d and d not in ("", "nan", "none"):
            doi_to_cluster[d] = row["cluster"]

    log.info("Papers with KMeans cluster assignments: %d",
             len(doi_to_cluster))

    # ============================================================
    # Step 2: Load citations (once)
    # ============================================================

    log.info("--- Step 2: Load citations ---")
    works["doi_norm"] = works["doi"].apply(normalize_doi)

    if cit_path is not None:
        cit = pd.read_csv(cit_path, low_memory=False)
    else:
        cit = load_refined_citations()
    cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
    cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
    cit = cit[
        cit["source_doi"].notna()
        & ~cit["source_doi"].isin(["", "nan", "none"])
        & cit["ref_doi"].notna()
        & ~cit["ref_doi"].isin(["", "nan", "none"])
    ]
    cit["ref_year_num"] = pd.to_numeric(cit["ref_year"], errors="coerce")
    log.info("Citation pairs with valid DOIs: %d", len(cit))

    source_groups = cit.groupby("source_doi")["ref_doi"].apply(list)
    ref_counts = cit.groupby("ref_doi").size().sort_values(
        ascending=False)
    log.info("Unique source papers: %d", len(source_groups))
    log.info("Unique referenced DOIs: %d", len(ref_counts))

    # ============================================================
    # Step 3: Build co-citation communities for each window
    # ============================================================

    log.info("--- Step 3: Detect communities for each window ---")
    window_partitions = {}
    for w in WINDOWS:
        window_partitions[w["label"]] = detect_communities(
            cit, ref_counts, source_groups,
            w["cutoff"], TOP_N, MIN_COCIT, RESOLUTION, RANDOM_STATE,
        )

    # ============================================================
    # Step 4: Build heatmaps (indirect mapping)
    # ============================================================

    log.info("--- Step 4: Build heatmaps ---")

    ref_to_citers = defaultdict(set)
    for _, row in cit.iterrows():
        ref = row["ref_doi"]
        src = row["source_doi"]
        if src in doi_to_cluster:
            ref_to_citers[ref].add(src)
    log.info("Refs cited by at least one clustered paper: %d",
             len(ref_to_citers))

    heatmap_data = {}
    for w in WINDOWS:
        label = w["label"]
        matrix, comm_labels, comm_sizes = build_heatmap_data(
            window_partitions[label], ref_to_citers,
            doi_to_cluster, K_CLUSTERS,
        )
        heatmap_data[label] = {
            "matrix": matrix,
            "comm_labels": comm_labels,
            "comm_sizes": comm_sizes,
            "n_communities": (
                len(set(window_partitions[label].values()))
                if window_partitions[label] else 0
            ),
        }
        if matrix is not None:
            log.info(
                "  %s: %d communities, max cell = %d, "
                "total citers = %d",
                label, matrix.shape[1], matrix.max(), matrix.sum(),
            )

    # ============================================================
    # Step 5: Plot 2x2 heatmap figure
    # ============================================================

    _render_heatmap(heatmap_data, cluster_short, out_stem, args.pdf)

    log.info("Done.")


if __name__ == "__main__":
    main()
