"""Citation graph divergence methods (G1-G8).

Each function takes (works, citations, internal_edges, cfg) and returns
a DataFrame with columns: year, window, hyperparams, value.

G1, G2, G5, G6, G8 use sliding windows (ticket 0048) to compare
graph metrics between before/after windows, matching the semantic methods.
G3, G4, G7 are per-year methods and use cumulative windows.

Private module — no main, no argparse. Called via compute_divergence.py
dispatcher.
"""

import warnings

import networkx as nx
import numpy as np
import pandas as pd
from _divergence_citation import (
    _cumulative_graph,
    _dict_to_df,
    _get_years,
    _iter_sliding_pairs,
)
from scipy.optimize import curve_fit
from scipy.sparse.linalg import eigsh
from scipy.spatial.distance import jensenshannon
from scipy.stats import entropy
from utils import get_logger

log = get_logger("_citation_methods")


# ── Graph metric helpers (shared by sliding methods) ─────────────────────


def _pagerank_vector(G, damping):
    """Compute PageRank on a graph, return (nodes, values) or None."""
    if G.number_of_nodes() < 3 or G.number_of_edges() < 1:
        return None
    pr = nx.pagerank(G, alpha=damping, max_iter=200)
    nodes = sorted(pr.keys())
    vals = np.array([pr[n] for n in nodes])
    return nodes, vals


def _compare_pagerank_distributions(pr_before, pr_after, n_bins=20):
    """Compare two PageRank distributions via Jensen-Shannon divergence.

    Unlike per-node comparison (which requires shared nodes), this compares
    the *shape* of the PageRank value distributions — whether concentration
    or spread changed between windows. Works correctly on disjoint node sets.

    Parameters
    ----------
    pr_before, pr_after : tuple (nodes, values)
        Output of _pagerank_vector().
    n_bins : int
        Number of histogram bins for discretizing the distributions.

    Returns
    -------
    float
        JS divergence squared, in [0, 1]. 0 = identical distributions.

    """
    _nodes_b, vals_b = pr_before
    _nodes_a, vals_a = pr_after

    # Bin into histograms over a shared range (handles different-sized distributions).
    # PageRank values already sum to 1.0; jensenshannon normalizes internally.
    actual_bins = min(n_bins, min(len(vals_b), len(vals_a)))
    if actual_bins < 2:
        return np.nan
    bin_max = max(vals_b.max(), vals_a.max())
    bins = np.linspace(0, bin_max, actual_bins + 1)
    hist_b, _ = np.histogram(vals_b, bins=bins)
    hist_a, _ = np.histogram(vals_a, bins=bins)

    # Add epsilon to avoid zero bins before jensenshannon (which uses log internally).
    eps = 1e-10
    hist_b = hist_b + eps
    hist_a = hist_a + eps

    return float(jensenshannon(hist_b, hist_a) ** 2)


def _spectral_gap(G_dir):
    """Compute spectral gap of the normalized Laplacian (undirected)."""
    G = G_dir.to_undirected()
    if G.number_of_nodes() < 3:
        return np.nan

    components = list(nx.connected_components(G))
    if not components:
        raise ValueError("Graph with >= 3 nodes must have at least one component")

    lcc = max(components, key=len)
    if len(lcc) < 3:
        return np.nan

    H = G.subgraph(lcc)
    n = H.number_of_nodes()

    try:
        if n <= 200:
            L = nx.normalized_laplacian_matrix(H).toarray()
            eigenvalues = np.sort(np.linalg.eigvalsh(L))
        else:
            L = nx.normalized_laplacian_matrix(H).astype(float)
            eigenvalues = np.sort(
                eigsh(L, k=min(2, n - 1), which="SM", return_eigenvectors=False)
            )
        if len(eigenvalues) >= 2:
            return float(eigenvalues[1] - eigenvalues[0])
        return np.nan
    except (np.linalg.LinAlgError, ArithmeticError, ValueError) as exc:
        log.debug("Spectral gap computation failed: %s", exc)
        return np.nan


def _pa_exponent(G):
    """Fit power-law exponent to in-degree distribution."""
    in_degrees = np.array([d for _, d in G.in_degree()])
    pos_deg = in_degrees[in_degrees > 0]
    if len(pos_deg) < 10:
        return np.nan

    unique_k, counts = np.unique(pos_deg, return_counts=True)
    if len(unique_k) < 2:
        return np.nan
    ccdf = np.cumsum(counts[::-1])[::-1] / len(pos_deg)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            popt, _ = curve_fit(
                _power_law,
                unique_k.astype(float),
                ccdf,
                p0=[1.5, 1.0],
                maxfev=5000,
            )
        return float(popt[0])
    except (RuntimeError, ValueError):
        return np.nan


def _citation_entropy(G):
    """Shannon entropy of in-degree distribution."""
    in_degrees = np.array([d for _, d in G.in_degree()])
    pos_deg = in_degrees[in_degrees > 0]
    if len(pos_deg) < 3:
        return np.nan

    _unique_k, counts = np.unique(pos_deg, return_counts=True)
    return float(entropy(counts))


def _mean_betweenness(G_dir, max_nodes):
    """Mean betweenness centrality of largest connected component."""
    G = G_dir.to_undirected()
    if G.number_of_nodes() < 3:
        return np.nan

    components = list(nx.connected_components(G))
    lcc = max(components, key=len)
    if len(lcc) < 3:
        return np.nan

    H = G.subgraph(lcc)
    n = H.number_of_nodes()

    if n > max_nodes:
        bc = nx.betweenness_centrality(H, k=max_nodes)
    else:
        bc = nx.betweenness_centrality(H)

    vals = list(bc.values())
    return float(np.mean(vals)) if vals else np.nan


# ── G1: PageRank divergence (sliding) ────────────────────────────────────


def compute_g1_pagerank(works, citations, internal_edges, cfg):
    """PageRank distribution divergence between before/after sliding windows.

    Compares the *shape* of PageRank value distributions using
    Jensen-Shannon divergence (ticket 0059). This works correctly on
    disjoint node sets — sliding windows rarely share nodes, so per-node
    comparison (the old Kendall-tau approach) was dominated by zero-padding.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    cit_cfg = cfg["divergence"]["citation"]
    g1_cfg = cit_cfg["G1_pagerank"]
    damping = g1_cfg["damping"]
    n_bins = g1_cfg.get("n_bins", 20)

    log.info("G1: PageRank distribution divergence (sliding, JS)")
    results = []

    for year, w, G_before, G_after in _iter_sliding_pairs(works, internal_edges, cfg):
        pr_before = _pagerank_vector(G_before, damping)
        pr_after = _pagerank_vector(G_after, damping)

        if pr_before is None or pr_after is None:
            results.append(
                {
                    "year": year,
                    "window": str(w),
                    "hyperparams": f"n_bins={n_bins}",
                    "value": np.nan,
                }
            )
            continue

        value = _compare_pagerank_distributions(pr_before, pr_after, n_bins)
        results.append(
            {
                "year": year,
                "window": str(w),
                "hyperparams": f"n_bins={n_bins}",
                "value": value,
            }
        )

    return pd.DataFrame(results)


# ── Shared sliding-window scaffold ──────────────────────────────────────


def _sliding_abs_diff(works, internal_edges, cfg, metric_fn, label):
    """Compute abs-difference of a graph metric across sliding windows.

    Parameters
    ----------
    metric_fn : callable(G) -> float
        Graph metric to compare. Should return np.nan on failure.
    label : str
        Human-readable label for logging.

    """
    log.info("%s (sliding)", label)
    results = []
    for year, w, G_before, G_after in _iter_sliding_pairs(works, internal_edges, cfg):
        val_before = metric_fn(G_before)
        val_after = metric_fn(G_after)
        if np.isnan(val_before) or np.isnan(val_after):
            value = np.nan
        else:
            value = abs(val_after - val_before)
        results.append(
            {"year": year, "window": str(w), "hyperparams": "", "value": value}
        )
    return pd.DataFrame(results)


# ── G2: Spectral gap divergence (sliding) ────────────────────────────────


def compute_g2_spectral(works, citations, internal_edges, cfg):
    """Spectral gap divergence between before/after sliding windows.

    Computes the absolute difference in spectral gap of the normalized
    Laplacian between before and after windows.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    return _sliding_abs_diff(
        works, internal_edges, cfg, _spectral_gap, "G2: Spectral gap divergence"
    )


# ── G3: Bibliographic coupling age shift ──────────────────────────────────


def compute_g3_age_shift(works, citations, internal_edges, cfg):
    """Median publication year of references for papers published each year.

    Uses ref_year from citations.csv directly (not limited to internal edges).

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    years = _get_years(works)
    log.info("G3: Bibliographic coupling age shift")
    results = {}

    for y in years:
        year_dois = set(works.loc[works["year"] == y, "doi"].values)
        if not year_dois:
            results[y] = np.nan
            continue

        refs = pd.to_numeric(
            citations.loc[
                citations["source_doi"].isin(year_dois) & citations["ref_year"].notna(),
                "ref_year",
            ],
            errors="coerce",
        ).dropna()
        if len(refs) < 3:
            results[y] = np.nan
            continue

        results[y] = float(refs.median())

    return _dict_to_df(results)


# ── G4: Cross-tradition citation ratio ────────────────────────────────────


def _bisect_communities(G_und):
    """Split an undirected graph into 2 communities.

    Tries spectral bisection first, falls back to label propagation.
    Returns dict {node: 0|1} or None on failure.
    """
    try:
        from networkx.algorithms.community import spectral_bisection

        c1, c2 = spectral_bisection(G_und)
        return {n: 0 for n in c1} | {n: 1 for n in c2}
    except (ImportError, nx.NetworkXError, np.linalg.LinAlgError, ValueError):
        pass

    try:
        comms = list(nx.community.label_propagation_communities(G_und))
        if len(comms) < 2:
            return None
        community = {}
        for i, c in enumerate(comms[:2]):
            for n in c:
                community[n] = i
        for i, c in enumerate(comms[2:]):
            for n in c:
                community[n] = i % 2
        return community
    except (nx.NetworkXError, ValueError) as exc:
        log.debug("G4 community detection failed: %s", exc)
        return None


def compute_g4_cross_trad(works, citations, internal_edges, cfg):
    """Fraction of new internal citations crossing a 2-community boundary.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    years = _get_years(works)
    log.info("G4: Cross-tradition citation ratio")
    results = {}

    if len(internal_edges) < 10:
        log.info("G4: Too few internal edges (%d), skipping", len(internal_edges))
        return _dict_to_df({y: np.nan for y in years})

    ref_year = int(np.median(years))
    G_full = _cumulative_graph(works, internal_edges, ref_year)
    G_und = G_full.to_undirected()

    if G_und.number_of_nodes() < 4:
        return _dict_to_df({y: np.nan for y in years})

    community = _bisect_communities(G_und)
    if community is None:
        return _dict_to_df({y: np.nan for y in years})

    for y in years:
        new_edges = internal_edges.loc[
            internal_edges["source_year"] == y, ["source_doi", "ref_doi"]
        ]
        if len(new_edges) < 2:
            results[y] = np.nan
            continue

        ne = new_edges.copy()
        ne["s_comm"] = ne["source_doi"].map(community)
        ne["r_comm"] = ne["ref_doi"].map(community)
        valid = ne.dropna(subset=["s_comm", "r_comm"])
        total = len(valid)
        if total == 0:
            results[y] = np.nan
            continue
        cross = (valid["s_comm"] != valid["r_comm"]).sum()
        results[y] = int(cross) / total

    return _dict_to_df(results)


# ── G5: Preferential attachment exponent divergence (sliding) ────────────


def _power_law(x, alpha, c):
    """Power-law CCDF: P(X >= x) = c * x^(-alpha)."""
    return c * np.power(x, -alpha)


def compute_g5_pa_exponent(works, citations, internal_edges, cfg):
    """Power-law exponent divergence between before/after sliding windows.

    Computes the absolute difference in fitted power-law exponent
    of the in-degree distribution between before and after windows.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    return _sliding_abs_diff(
        works,
        internal_edges,
        cfg,
        _pa_exponent,
        "G5: Preferential attachment exponent divergence",
    )


# ── G6: Citation entropy divergence (sliding) ────────────────────────────


def compute_g6_entropy(works, citations, internal_edges, cfg):
    """Shannon entropy divergence between before/after sliding windows.

    Computes the absolute difference in Shannon entropy of the
    in-degree distribution between before and after windows.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    return _sliding_abs_diff(
        works,
        internal_edges,
        cfg,
        _citation_entropy,
        "G6: Citation entropy divergence",
    )


# ── G7: Disruption index CD ──────────────────────────────────────────────


def _g7_ref_year_proxy(works, citations, years):
    """Proxy when internal edges are too sparse: IQR of ref_year."""
    results = {}
    for y in years:
        year_dois = set(works.loc[works["year"] == y, "doi"].values)
        if not year_dois:
            results[y] = np.nan
            continue
        refs = citations.loc[
            citations["source_doi"].isin(year_dois) & citations["ref_year"].notna(),
            "ref_year",
        ]
        if len(refs) < 5:
            results[y] = np.nan
            continue
        ages = y - refs
        results[y] = float(ages.quantile(0.75) - ages.quantile(0.25))
    return results


def compute_g7_disruption(works, citations, internal_edges, cfg):
    """Simplified disruption index.

    For each paper i published in year y, compute CD_i using citation data.
    CD_i = (n_i - n_j) / (n_i + n_j + n_k)

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    years = _get_years(works)
    log.info("G7: Disruption index (simplified)")
    results = {}

    if len(internal_edges) < 5:
        log.info(
            "G7: Too few internal edges (%d), using ref_year shift proxy",
            len(internal_edges),
        )
        return _dict_to_df(
            _g7_ref_year_proxy(works, citations, years), hyperparams="mode=proxy"
        )

    corpus_dois = set(works["doi"].values)

    # Build paper_refs: {source_doi -> set of ref_dois} using vectorized filter
    corpus_cit = citations.loc[citations["source_doi"].isin(corpus_dois)]
    paper_refs = corpus_cit.groupby("source_doi")["ref_doi"].apply(set).to_dict()

    # Build paper_citers: {ref_doi -> set of source_dois} using vectorized groupby
    paper_citers = internal_edges.groupby("ref_doi")["source_doi"].apply(set).to_dict()

    for y in years:
        year_papers = works.loc[works["year"] == y, "doi"].values
        cd_vals = []
        for paper_i in year_papers:
            refs_i = paper_refs.get(paper_i, set())
            citers_i = paper_citers.get(paper_i, set())

            if not citers_i and not refs_i:
                continue

            n_i = 0
            n_j = 0
            for citer in citers_i:
                citer_refs = paper_refs.get(citer, set())
                if citer_refs & refs_i:
                    n_j += 1
                else:
                    n_i += 1

            citers_of_refs = set()
            for ref in refs_i:
                citers_of_refs |= paper_citers.get(ref, set())
            n_k = len(citers_of_refs - citers_i)

            denom = n_i + n_j + n_k
            if denom > 0:
                cd_vals.append((n_i - n_j) / denom)

        results[y] = float(np.mean(cd_vals)) if cd_vals else np.nan

    return _dict_to_df(results)


# ── G8: Betweenness centrality divergence (sliding) ──────────────────────


def compute_g8_betweenness(works, citations, internal_edges, cfg):
    """Betweenness centrality divergence between before/after sliding windows.

    Computes the absolute difference in mean betweenness centrality
    of the largest connected component between before and after windows.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    cit_cfg = cfg["divergence"]["citation"]
    max_nodes = cit_cfg["G8_betweenness"]["max_nodes"]

    def _betweenness(G):
        return _mean_betweenness(G, max_nodes)

    return _sliding_abs_diff(
        works,
        internal_edges,
        cfg,
        _betweenness,
        "G8: Betweenness centrality divergence",
    )
