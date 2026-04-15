"""Citation graph divergence: implementation functions (G1-G8).

Private module -- no main, no argparse. Called by compute_divergence.py.

Methods:
  G1  PageRank volatility       -- Kendall tau displacement year-to-year
  G2  Spectral gap              -- lambda_2 - lambda_1 of normalized Laplacian
  G3  Bibliographic coupling age -- median ref_year for papers published in year y
  G4  Cross-tradition citation   -- fraction of cross-community new citations
  G5  Preferential attachment    -- power-law exponent of in-degree CCDF
  G6  Citation entropy           -- Shannon entropy of in-degree distribution
  G7  Disruption index CD        -- mean CD per year (simplified)
  G8  Betweenness centrality     -- mean betweenness of largest connected component

"""

import warnings

import networkx as nx
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.sparse.linalg import eigsh
from scipy.stats import entropy, kendalltau
from utils import get_logger

log = get_logger("_divergence_citation")

warnings.filterwarnings("ignore", category=RuntimeWarning)


# ── Data loading ───────────────────────────────────────────────────────────


def load_citation_data(input_paths):
    """Load works and citations, build internal edge list.

    Parameters
    ----------
    input_paths : list[str] | None
        If provided, [works_csv, citations_csv] (used by tests).

    Returns
    -------
    (works, citations, internal_edges) : tuple

    """
    works_path = (
        input_paths[0] if input_paths and len(input_paths) >= 2 else REFINED_WORKS_PATH
    )
    works = pd.read_csv(
        works_path,
        usecols=["doi", "year", "cited_by_count"],
        dtype={"year": float},
    )
    works = works.dropna(subset=["doi"]).copy()
    works["year"] = works["year"].astype(int)

    if input_paths and len(input_paths) >= 2:
        citations = pd.read_csv(input_paths[1])
    else:
        citations = load_refined_citations()

    internal_edges = _build_internal_edges(works, citations)
    log.info(
        "Loaded %d works, %d citations, %d internal edges",
        len(works),
        len(citations),
        len(internal_edges),
    )
    return works, citations, internal_edges


def _build_internal_edges(works, citations):
    """Match citation edges where both endpoints are in the corpus.

    Returns DataFrame with columns: source_doi, ref_doi, source_year.
    """
    corpus_dois = set(works["doi"].values)
    doi_to_year = dict(zip(works["doi"], works["year"]))

    mask = (
        citations["source_doi"].isin(corpus_dois)
        & citations["ref_doi"].isin(corpus_dois)
        & (citations["ref_doi"] != "")
    )
    internal = citations.loc[mask, ["source_doi", "ref_doi"]].copy()
    internal["source_year"] = internal["source_doi"].map(doi_to_year)
    log.info(
        "Internal edges: %d / %d total citation rows", len(internal), len(citations)
    )
    return internal


# ── Shared helpers ─────────────────────────────────────────────────────────


def _get_years(works):
    """Return full year range from works."""
    year_min = int(works["year"].min())
    year_max = int(works["year"].max())
    return list(range(year_min, year_max + 1))


def _cumulative_graph(works, internal_edges, up_to_year):
    """Build directed graph of papers and internal citations up to `up_to_year`."""
    G = nx.DiGraph()
    nodes = works.loc[works["year"] <= up_to_year, "doi"].values
    G.add_nodes_from(nodes)
    mask = internal_edges["source_year"] <= up_to_year
    edges = internal_edges.loc[mask, ["source_doi", "ref_doi"]].values
    G.add_edges_from(edges)
    return G


def _incremental_graphs(works, internal_edges, years):
    """Yield (year, G) pairs, building the graph incrementally.

    Each iteration adds that year's nodes and edges to the running graph.
    The caller receives the *same* mutable DiGraph object each iteration
    (so must not store references across iterations without copying).
    """
    # Pre-group nodes and edges by year for O(1) lookup
    nodes_by_year = works.groupby("year")["doi"].apply(list).to_dict()
    edges_by_year = (
        internal_edges.groupby("source_year")[["source_doi", "ref_doi"]]
        .apply(lambda g: g.values.tolist())
        .to_dict()
    )
    G = nx.DiGraph()
    for y in years:
        new_nodes = nodes_by_year.get(y, [])
        if new_nodes:
            G.add_nodes_from(new_nodes)
        new_edges = edges_by_year.get(y, [])
        if new_edges:
            G.add_edges_from(new_edges)
        yield y, G


def _dict_to_df(results, hyperparams=""):
    """Convert {year: value} dict to DataFrame with standard columns."""
    rows = []
    for y, val in sorted(results.items()):
        rows.append(
            {
                "year": y,
                "window": "cumulative",
                "hyperparams": hyperparams,
                "value": val,
            }
        )
    return pd.DataFrame(rows)


# ── G1: PageRank volatility ───────────────────────────────────────────────


def compute_g1_pagerank(works, citations, internal_edges, cfg):
    """Kendall tau displacement of PageRank rankings year-to-year.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    cit_cfg = cfg["divergence"]["citation"]
    damping = cit_cfg["G1_pagerank"]["damping"]
    years = _get_years(works)

    log.info("G1: PageRank volatility")
    results = {}
    prev_ranks = None
    prev_nodes = None

    for y, G in _incremental_graphs(works, internal_edges, years):
        if G.number_of_nodes() < 3 or G.number_of_edges() < 1:
            results[y] = np.nan
            prev_ranks = None
            prev_nodes = None
            continue

        pr = nx.pagerank(G, alpha=damping, max_iter=200)
        nodes = sorted(pr.keys())
        ranks = np.array([pr[n] for n in nodes])

        if prev_ranks is not None and prev_nodes is not None:
            common = sorted(set(nodes) & set(prev_nodes))
            if len(common) >= 3:
                curr_vals = np.array([pr[n] for n in common])
                prev_map = dict(zip(prev_nodes, prev_ranks))
                prev_vals = np.array([prev_map[n] for n in common])
                tau, _ = kendalltau(curr_vals, prev_vals)
                results[y] = 1.0 - tau if not np.isnan(tau) else np.nan
            else:
                results[y] = np.nan
        else:
            results[y] = np.nan

        prev_ranks = ranks
        prev_nodes = nodes

    return _dict_to_df(results)


# ── G2: Spectral gap ─────────────────────────────────────────────────────


def compute_g2_spectral(works, citations, internal_edges, cfg):
    """Spectral gap of normalized Laplacian (undirected version).

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    years = _get_years(works)
    log.info("G2: Spectral gap")
    results = {}

    for y, G_dir in _incremental_graphs(works, internal_edges, years):
        G = G_dir.to_undirected()

        if G.number_of_nodes() < 3:
            results[y] = np.nan
            continue

        components = list(nx.connected_components(G))
        if not components:
            results[y] = np.nan
            continue

        lcc = max(components, key=len)
        if len(lcc) < 3:
            results[y] = np.nan
            continue

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
                results[y] = float(eigenvalues[1] - eigenvalues[0])
            else:
                results[y] = np.nan
        except Exception as exc:
            log.debug("G2 eigsh failed for year %d: %s", y, exc)
            results[y] = np.nan

    return _dict_to_df(results)


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

        refs = citations.loc[
            citations["source_doi"].isin(year_dois) & citations["ref_year"].notna(),
            "ref_year",
        ]
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
    except Exception:
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
    except Exception as exc:
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


# ── G5: Preferential attachment exponent ──────────────────────────────────


def _power_law(x, alpha, c):
    """Power-law CCDF: P(X >= x) = c * x^(-alpha)."""
    return c * np.power(x, -alpha)


def compute_g5_pa_exponent(works, citations, internal_edges, cfg):
    """Power-law exponent of cumulative in-degree distribution.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    years = _get_years(works)
    log.info("G5: Preferential attachment exponent")
    results = {}

    for y, G in _incremental_graphs(works, internal_edges, years):
        in_degrees = np.array([d for _, d in G.in_degree()])
        pos_deg = in_degrees[in_degrees > 0]
        if len(pos_deg) < 10:
            results[y] = np.nan
            continue

        unique_k, counts = np.unique(pos_deg, return_counts=True)
        ccdf = np.cumsum(counts[::-1])[::-1] / len(pos_deg)

        try:
            popt, _ = curve_fit(
                _power_law, unique_k.astype(float), ccdf, p0=[1.5, 1.0], maxfev=5000
            )
            results[y] = float(popt[0])
        except (RuntimeError, ValueError):
            results[y] = np.nan

    return _dict_to_df(results)


# ── G6: Citation entropy ──────────────────────────────────────────────────


def compute_g6_entropy(works, citations, internal_edges, cfg):
    """Shannon entropy of in-degree distribution per yearly snapshot.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    years = _get_years(works)
    log.info("G6: Citation entropy")
    results = {}

    for y, G in _incremental_graphs(works, internal_edges, years):
        in_degrees = np.array([d for _, d in G.in_degree()])
        pos_deg = in_degrees[in_degrees > 0]
        if len(pos_deg) < 3:
            results[y] = np.nan
            continue

        unique_k, counts = np.unique(pos_deg, return_counts=True)
        results[y] = float(entropy(counts))

    return _dict_to_df(results)


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


# ── G8: Betweenness centrality ────────────────────────────────────────────


def compute_g8_betweenness(works, citations, internal_edges, cfg):
    """Mean betweenness centrality of nodes in the largest connected component.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    cit_cfg = cfg["divergence"]["citation"]
    max_nodes = cit_cfg["G8_betweenness"]["max_nodes"]
    years = _get_years(works)

    log.info("G8: Betweenness centrality dynamics")
    results = {}

    for y, G_dir in _incremental_graphs(works, internal_edges, years):
        G = G_dir.to_undirected()

        if G.number_of_nodes() < 3:
            results[y] = np.nan
            continue

        components = list(nx.connected_components(G))
        lcc = max(components, key=len)
        if len(lcc) < 3:
            results[y] = np.nan
            continue

        H = G.subgraph(lcc)
        n = H.number_of_nodes()

        if n > max_nodes:
            bc = nx.betweenness_centrality(H, k=max_nodes)
        else:
            bc = nx.betweenness_centrality(H)

        vals = list(bc.values())
        results[y] = float(np.mean(vals)) if vals else np.nan

    return _dict_to_df(results)
