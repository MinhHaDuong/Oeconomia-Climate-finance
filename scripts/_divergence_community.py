"""Community divergence (G9): Louvain partition + Jensen-Shannon divergence.

For each sliding-window pair (before, after):
  1. Build a union undirected graph: nodes from both windows, plus all
     internal edges where both endpoints are in the union node set
  2. Run Louvain community detection on the union graph
  3. Count the fraction of before-window docs in each community (p_before)
  4. Count the fraction of after-window docs in each community (p_after)
  5. Compute JS divergence between p_before and p_after

Private module — no main, no argparse. Called via compute_divergence.py
dispatcher.
"""

import community as community_louvain
import networkx as nx
import numpy as np
import pandas as pd
from _divergence_citation import _iter_sliding_pairs
from scipy.spatial.distance import jensenshannon
from utils import get_logger

log = get_logger("_divergence_community")


def compute_community_divergence(works, citations, internal_edges, cfg):
    """Compute community divergence across sliding windows."""
    div_cfg = cfg["divergence"]
    cit_cfg = div_cfg.get("citation", {})
    comm_cfg = cit_cfg.get("G9_community", {})
    resolution = comm_cfg.get("resolution", 1.0)
    seed = div_cfg["random_seed"]

    log.info("G9: Community divergence (Louvain + JS, resolution=%.2f)", resolution)
    results = []

    for year, w, G_before, G_after in _iter_sliding_pairs(works, internal_edges, cfg):
        value = _community_js_for_pair(
            G_before, G_after, internal_edges, resolution, seed
        )
        results.append(
            {
                "year": year,
                "window": str(w),
                "hyperparams": f"res={resolution}",
                "value": value,
            }
        )

    return pd.DataFrame(results)


def _build_union_graph(G_before, G_after, internal_edges):
    """Build undirected union graph with cross-window edges.

    Uses vectorized pandas .isin() filtering (same pattern as
    _divergence_citation._build_internal_edges) instead of iterrows().
    """
    union_nodes = set(G_before.nodes()) | set(G_after.nodes())
    G_union = nx.Graph()
    G_union.add_nodes_from(union_nodes)

    mask = internal_edges["source_doi"].isin(union_nodes) & internal_edges[
        "ref_doi"
    ].isin(union_nodes)
    edges = internal_edges.loc[mask, ["source_doi", "ref_doi"]].values
    G_union.add_edges_from(edges)

    return G_union


def _community_js_for_pair(G_before, G_after, internal_edges, resolution, seed):
    """Compute JS divergence of community share vectors for one window pair."""
    G_union = _build_union_graph(G_before, G_after, internal_edges)

    if G_union.number_of_nodes() < 3 or G_union.number_of_edges() < 1:
        return np.nan

    partition = community_louvain.best_partition(
        G_union, resolution=resolution, random_state=seed
    )

    before_nodes = set(G_before.nodes())
    after_nodes = set(G_after.nodes())

    all_communities = sorted(set(partition.values()))
    n_communities = len(all_communities)
    if n_communities < 2:
        return 0.0

    comm_to_idx = {c: i for i, c in enumerate(all_communities)}

    p_before = np.zeros(n_communities)
    for node in before_nodes:
        if node in partition:
            p_before[comm_to_idx[partition[node]]] += 1

    p_after = np.zeros(n_communities)
    for node in after_nodes:
        if node in partition:
            p_after[comm_to_idx[partition[node]]] += 1

    if p_before.sum() == 0 or p_after.sum() == 0:
        return np.nan

    p_before = p_before / p_before.sum()
    p_after = p_after / p_after.sum()

    js = jensenshannon(p_before, p_after)
    return float(js**2)
