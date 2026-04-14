"""Citation graph divergence: 8 structural signals from the citation network.

Builds cumulative directed citation graphs from refined_citations.csv and
refined_works.csv. For each year y, the graph includes all papers published
up to year y and citations between them.

Methods
-------
G1: PageRank volatility       — Kendall tau displacement year-to-year
G2: Spectral gap              — lambda_2 - lambda_1 of normalized Laplacian
G3: Bibliographic coupling age — median ref_year for papers published in year y
G4: Cross-tradition citation   — fraction of cross-community new citations
G5: Preferential attachment    — power-law exponent of in-degree CCDF
G6: Citation entropy           — Shannon entropy of in-degree distribution
G7: Disruption index CD        — mean CD per year (simplified)
G8: Betweenness centrality     — mean betweenness of largest connected component

Reads:
  refined_works.csv, refined_citations.csv

Writes:
  Long-format CSV: year, method, window, hyperparams, value

Also applies PELT break detection (ruptures) at penalties 1, 3, 5.

Usage:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke python3 scripts/compute_divergence_citation.py \
        --output content/tables/tab_citation_divergence.csv
"""

import os
import warnings

import networkx as nx
import numpy as np
import pandas as pd
import ruptures
from scipy import sparse
from scipy.optimize import curve_fit
from scipy.sparse.linalg import eigsh
from scipy.stats import entropy, kendalltau
from script_io_args import parse_io_args, validate_io
from utils import CATALOGS_DIR, get_logger

log = get_logger("compute_divergence_citation")

warnings.filterwarnings("ignore", category=RuntimeWarning)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(input_paths=None):
    """Load works and citations DataFrames.

    Parameters
    ----------
    input_paths : list[str] | None
        If provided, [works_path, citations_path].

    Returns
    -------
    works : pd.DataFrame
    citations : pd.DataFrame
    """
    if input_paths and len(input_paths) >= 2:
        works_path, cit_path = input_paths[0], input_paths[1]
    else:
        works_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
        cit_path = os.path.join(CATALOGS_DIR, "refined_citations.csv")

    works = pd.read_csv(works_path, usecols=["doi", "year", "cited_by_count"],
                         dtype={"year": float})
    works = works.dropna(subset=["doi"]).copy()
    works["doi"] = works["doi"].str.strip().str.lower()
    works["year"] = works["year"].astype(int)

    citations = pd.read_csv(cit_path)
    citations["source_doi"] = citations["source_doi"].fillna("").str.strip().str.lower()
    citations["ref_doi"] = citations["ref_doi"].fillna("").str.strip().str.lower()
    # ref_year may have NaN; keep as float
    if "ref_year" in citations.columns:
        citations["ref_year"] = pd.to_numeric(citations["ref_year"], errors="coerce")

    return works, citations


def build_internal_edges(works, citations):
    """Match citation edges where both endpoints are in the corpus.

    Returns DataFrame with columns: source_doi, ref_doi, source_year.
    """
    corpus_dois = set(works["doi"].values)
    doi_to_year = dict(zip(works["doi"], works["year"]))

    mask = (citations["source_doi"].isin(corpus_dois) &
            citations["ref_doi"].isin(corpus_dois) &
            (citations["ref_doi"] != ""))
    internal = citations.loc[mask, ["source_doi", "ref_doi"]].copy()
    internal["source_year"] = internal["source_doi"].map(doi_to_year)
    log.info("Internal edges: %d / %d total citation rows",
             len(internal), len(citations))
    return internal


# ---------------------------------------------------------------------------
# Graph construction helpers
# ---------------------------------------------------------------------------

def cumulative_graph(works, internal_edges, up_to_year):
    """Build directed graph of papers and internal citations up to `up_to_year`."""
    G = nx.DiGraph()
    nodes = works.loc[works["year"] <= up_to_year, "doi"].values
    G.add_nodes_from(nodes)
    mask = internal_edges["source_year"] <= up_to_year
    edges = internal_edges.loc[mask, ["source_doi", "ref_doi"]].values
    G.add_edges_from(edges)
    return G


# ---------------------------------------------------------------------------
# G1: PageRank volatility
# ---------------------------------------------------------------------------

def compute_g1_pagerank_volatility(works, internal_edges, years):
    """Kendall tau displacement of PageRank rankings year-to-year."""
    log.info("G1: PageRank volatility")
    results = {}
    prev_ranks = None
    prev_nodes = None

    for y in years:
        G = cumulative_graph(works, internal_edges, y)
        if G.number_of_nodes() < 3 or G.number_of_edges() < 1:
            results[y] = np.nan
            prev_ranks = None
            prev_nodes = None
            continue

        pr = nx.pagerank(G, max_iter=200)
        nodes = sorted(pr.keys())
        ranks = np.array([pr[n] for n in nodes])

        if prev_ranks is not None and prev_nodes is not None:
            # Align on common nodes
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

    return results


# ---------------------------------------------------------------------------
# G2: Spectral gap
# ---------------------------------------------------------------------------

def compute_g2_spectral_gap(works, internal_edges, years):
    """Spectral gap of normalized Laplacian (undirected version)."""
    log.info("G2: Spectral gap")
    results = {}

    for y in years:
        G_dir = cumulative_graph(works, internal_edges, y)
        G = G_dir.to_undirected()

        # Largest connected component
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
                # Dense computation for small graphs
                L = nx.normalized_laplacian_matrix(H).toarray()
                eigenvalues = np.sort(np.linalg.eigvalsh(L))
            else:
                L = nx.normalized_laplacian_matrix(H).astype(float)
                eigenvalues = np.sort(eigsh(L, k=min(2, n - 1),
                                            which="SM",
                                            return_eigenvectors=False))
            if len(eigenvalues) >= 2:
                results[y] = float(eigenvalues[1] - eigenvalues[0])
            else:
                results[y] = np.nan
        except Exception as exc:
            log.debug("G2 eigsh failed for year %d: %s", y, exc)
            results[y] = np.nan

    return results


# ---------------------------------------------------------------------------
# G3: Bibliographic coupling age shift
# ---------------------------------------------------------------------------

def compute_g3_age_shift(works, citations, years):
    """Median publication year of references for papers published each year.

    Uses ref_year from citations.csv directly (not limited to internal edges).
    """
    log.info("G3: Bibliographic coupling age shift")
    doi_to_year = dict(zip(works["doi"], works["year"]))
    results = {}

    for y in years:
        # Papers published in year y
        year_dois = set(works.loc[works["year"] == y, "doi"].values)
        if not year_dois:
            results[y] = np.nan
            continue

        # Their references
        refs = citations.loc[
            citations["source_doi"].isin(year_dois) &
            citations["ref_year"].notna(),
            "ref_year"
        ]
        if len(refs) < 3:
            results[y] = np.nan
            continue

        results[y] = float(refs.median())

    return results


# ---------------------------------------------------------------------------
# G4: Cross-tradition citation ratio
# ---------------------------------------------------------------------------

def compute_g4_cross_tradition(works, internal_edges, years):
    """Fraction of new internal citations crossing a 2-community boundary.

    Uses spectral clustering (2 communities) on the cumulative graph at the
    median year. If too few internal edges, returns NaN for all years.
    """
    log.info("G4: Cross-tradition citation ratio")
    results = {}

    if len(internal_edges) < 10:
        log.info("G4: Too few internal edges (%d), skipping", len(internal_edges))
        return {y: np.nan for y in years}

    # Build full graph for community detection
    ref_year = int(np.median(years))
    G_full = cumulative_graph(works, internal_edges, ref_year)
    G_und = G_full.to_undirected()

    # 2-community split via label propagation (robust for sparse graphs)
    if G_und.number_of_nodes() < 4:
        return {y: np.nan for y in years}

    try:
        from networkx.algorithms.community import spectral_bisection
        c1, c2 = spectral_bisection(G_und)
        community = {}
        for n in c1:
            community[n] = 0
        for n in c2:
            community[n] = 1
    except Exception:
        # Fallback: label propagation
        try:
            comms = list(nx.community.label_propagation_communities(G_und))
            if len(comms) < 2:
                return {y: np.nan for y in years}
            community = {}
            for i, c in enumerate(comms[:2]):
                for n in c:
                    community[n] = i
            # Remaining nodes
            for i, c in enumerate(comms[2:]):
                for n in c:
                    community[n] = i % 2
        except Exception as exc:
            log.debug("G4 community detection failed: %s", exc)
            return {y: np.nan for y in years}

    for y in years:
        new_edges = internal_edges.loc[internal_edges["source_year"] == y,
                                        ["source_doi", "ref_doi"]]
        if len(new_edges) < 2:
            results[y] = np.nan
            continue

        cross = 0
        total = 0
        for _, row in new_edges.iterrows():
            s, r = row["source_doi"], row["ref_doi"]
            if s in community and r in community:
                total += 1
                if community[s] != community[r]:
                    cross += 1
        results[y] = cross / total if total > 0 else np.nan

    return results


# ---------------------------------------------------------------------------
# G5: Preferential attachment exponent
# ---------------------------------------------------------------------------

def _power_law(x, alpha, c):
    """Power-law CCDF: P(X >= x) = c * x^(-alpha)."""
    return c * np.power(x, -alpha)


def compute_g5_pa_exponent(works, internal_edges, years):
    """Power-law exponent of cumulative in-degree distribution."""
    log.info("G5: Preferential attachment exponent")
    results = {}

    for y in years:
        G = cumulative_graph(works, internal_edges, y)
        in_degrees = np.array([d for _, d in G.in_degree()])
        # Filter to positive degrees
        pos_deg = in_degrees[in_degrees > 0]
        if len(pos_deg) < 10:
            results[y] = np.nan
            continue

        # Log-log CCDF
        unique_k, counts = np.unique(pos_deg, return_counts=True)
        ccdf = np.cumsum(counts[::-1])[::-1] / len(pos_deg)

        try:
            popt, _ = curve_fit(_power_law, unique_k.astype(float), ccdf,
                                p0=[1.5, 1.0], maxfev=5000)
            results[y] = float(popt[0])  # alpha
        except (RuntimeError, ValueError):
            results[y] = np.nan

    return results


# ---------------------------------------------------------------------------
# G6: Citation entropy
# ---------------------------------------------------------------------------

def compute_g6_entropy(works, internal_edges, years):
    """Shannon entropy of in-degree distribution per yearly snapshot."""
    log.info("G6: Citation entropy")
    results = {}

    for y in years:
        G = cumulative_graph(works, internal_edges, y)
        in_degrees = np.array([d for _, d in G.in_degree()])
        pos_deg = in_degrees[in_degrees > 0]
        if len(pos_deg) < 3:
            results[y] = np.nan
            continue

        # Histogram of in-degrees
        unique_k, counts = np.unique(pos_deg, return_counts=True)
        results[y] = float(entropy(counts))

    return results


# ---------------------------------------------------------------------------
# G7: Disruption index CD (simplified)
# ---------------------------------------------------------------------------

def compute_g7_disruption(works, citations, internal_edges, years):
    """Simplified disruption index.

    For each paper i published in year y, compute CD_i using citation data.
    Since citations.csv gives us outgoing references (i -> refs), we build
    a reverse index of who cites whom from internal_edges.

    CD_i = (n_i - n_j) / (n_i + n_j + n_k) where:
    - n_i = papers citing i but NOT citing any of i's references
    - n_j = papers citing i AND at least one of i's references
    - n_k = papers NOT citing i but citing at least one of i's references
    """
    log.info("G7: Disruption index (simplified)")
    results = {}

    if len(internal_edges) < 5:
        log.info("G7: Too few internal edges (%d), using ref_year shift proxy",
                 len(internal_edges))
        return _g7_ref_year_proxy(works, citations, years)

    # Build forward refs: paper -> set of refs (from all citations, not just internal)
    corpus_dois = set(works["doi"].values)
    paper_refs = {}
    for _, row in citations.iterrows():
        s = row["source_doi"]
        r = row["ref_doi"]
        if s in corpus_dois:
            paper_refs.setdefault(s, set()).add(r)

    # Build reverse citation index from internal edges: paper -> set of citers
    paper_citers = {}
    for _, row in internal_edges.iterrows():
        src, ref = row["source_doi"], row["ref_doi"]
        paper_citers.setdefault(ref, set()).add(src)

    doi_to_year_map = dict(zip(works["doi"], works["year"]))

    for y in years:
        year_papers = works.loc[works["year"] == y, "doi"].values
        cd_vals = []
        for paper_i in year_papers:
            refs_i = paper_refs.get(paper_i, set())
            citers_i = paper_citers.get(paper_i, set())

            if not citers_i and not refs_i:
                continue

            # n_i: cite i but not any ref of i
            n_i = 0
            # n_j: cite i AND at least one ref of i
            n_j = 0
            for citer in citers_i:
                citer_refs = paper_refs.get(citer, set())
                if citer_refs & refs_i:
                    n_j += 1
                else:
                    n_i += 1

            # n_k: cite at least one ref of i but NOT i
            citers_of_refs = set()
            for ref in refs_i:
                citers_of_refs |= paper_citers.get(ref, set())
            n_k = len(citers_of_refs - citers_i)

            denom = n_i + n_j + n_k
            if denom > 0:
                cd_vals.append((n_i - n_j) / denom)

        results[y] = float(np.mean(cd_vals)) if cd_vals else np.nan

    return results


def _g7_ref_year_proxy(works, citations, years):
    """Proxy when internal edges are too sparse: interquartile range of ref_year."""
    results = {}
    for y in years:
        year_dois = set(works.loc[works["year"] == y, "doi"].values)
        if not year_dois:
            results[y] = np.nan
            continue
        refs = citations.loc[
            citations["source_doi"].isin(year_dois) &
            citations["ref_year"].notna(),
            "ref_year"
        ]
        if len(refs) < 5:
            results[y] = np.nan
            continue
        # IQR of reference ages (current year - ref_year)
        ages = y - refs
        results[y] = float(ages.quantile(0.75) - ages.quantile(0.25))
    return results


# ---------------------------------------------------------------------------
# G8: Betweenness centrality dynamics
# ---------------------------------------------------------------------------

def compute_g8_betweenness(works, internal_edges, years):
    """Mean betweenness centrality of nodes in the largest connected component."""
    log.info("G8: Betweenness centrality dynamics")
    results = {}

    for y in years:
        G_dir = cumulative_graph(works, internal_edges, y)
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

        # Subsample for tractability
        if n > 500:
            bc = nx.betweenness_centrality(H, k=500)
        else:
            bc = nx.betweenness_centrality(H)

        vals = list(bc.values())
        results[y] = float(np.mean(vals)) if vals else np.nan

    return results


# ---------------------------------------------------------------------------
# PELT break detection
# ---------------------------------------------------------------------------

def detect_breaks_pelt(series_dict, penalties=(1, 3, 5)):
    """Apply PELT to each method's time series.

    Parameters
    ----------
    series_dict : dict
        {method_name: {year: value, ...}}
    penalties : tuple of float
        Penalty values for PELT.

    Returns
    -------
    list of dict
        Each dict: {method, penalty, breakpoints (list of years)}.
    """
    results = []
    for method, yv in series_dict.items():
        years = sorted(yv.keys())
        vals = np.array([yv[y] for y in years])
        valid = ~np.isnan(vals)
        if valid.sum() < 4:
            for pen in penalties:
                results.append({
                    "method": method,
                    "penalty": pen,
                    "breakpoints": [],
                })
            continue

        # Interpolate NaN gaps for PELT (needs contiguous signal)
        signal = vals.copy()
        if np.any(~valid):
            from numpy import interp
            xp = np.where(valid)[0]
            fp = signal[valid]
            signal = interp(np.arange(len(signal)), xp, fp)

        signal_2d = signal.reshape(-1, 1)

        for pen in penalties:
            try:
                algo = ruptures.Pelt(model="l2", min_size=2, jump=1)
                bkps = algo.fit(signal_2d).predict(pen=pen)
                # bkps are 1-indexed positions; last is always len(signal)
                bp_years = [years[b - 1] for b in bkps if b < len(years)]
                results.append({
                    "method": method,
                    "penalty": pen,
                    "breakpoints": bp_years,
                })
            except Exception as exc:
                log.debug("PELT failed for %s pen=%s: %s", method, pen, exc)
                results.append({
                    "method": method,
                    "penalty": pen,
                    "breakpoints": [],
                })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    works, citations = load_data(io_args.input)
    log.info("Loaded %d works, %d citation rows", len(works), len(citations))

    internal_edges = build_internal_edges(works, citations)

    year_min = int(works["year"].min())
    year_max = int(works["year"].max())
    years = list(range(year_min, year_max + 1))
    log.info("Year range: %d-%d", year_min, year_max)

    # Compute all 8 methods
    all_series = {}

    all_series["G1_pagerank_volatility"] = compute_g1_pagerank_volatility(
        works, internal_edges, years)

    all_series["G2_spectral_gap"] = compute_g2_spectral_gap(
        works, internal_edges, years)

    all_series["G3_age_shift"] = compute_g3_age_shift(
        works, citations, years)

    all_series["G4_cross_tradition"] = compute_g4_cross_tradition(
        works, internal_edges, years)

    all_series["G5_pa_exponent"] = compute_g5_pa_exponent(
        works, internal_edges, years)

    all_series["G6_citation_entropy"] = compute_g6_entropy(
        works, internal_edges, years)

    all_series["G7_disruption"] = compute_g7_disruption(
        works, citations, internal_edges, years)

    all_series["G8_betweenness"] = compute_g8_betweenness(
        works, internal_edges, years)

    # Assemble long-format output
    rows = []
    for method, yv in all_series.items():
        for y, val in sorted(yv.items()):
            rows.append({
                "year": y,
                "method": method,
                "window": "cumulative",
                "hyperparams": "",
                "value": val,
            })

    df_out = pd.DataFrame(rows)
    log.info("Output shape: %s", df_out.shape)

    # Non-NaN counts per method
    for m in all_series:
        n_valid = sum(1 for v in all_series[m].values() if not np.isnan(v))
        log.info("  %s: %d/%d valid values", m, n_valid, len(years))

    # Apply PELT break detection
    breaks = detect_breaks_pelt(all_series)
    break_rows = []
    for br in breaks:
        break_rows.append({
            "method": br["method"],
            "penalty": br["penalty"],
            "breakpoints": ";".join(str(y) for y in br["breakpoints"]),
        })
    df_breaks = pd.DataFrame(break_rows)

    # Save divergence series
    df_out.to_csv(io_args.output, index=False)
    log.info("Saved divergence series -> %s", io_args.output)

    # Save breaks alongside (same stem + _breaks suffix)
    out_stem = os.path.splitext(io_args.output)[0]
    breaks_path = f"{out_stem}_breaks.csv"
    df_breaks.to_csv(breaks_path, index=False)
    log.info("Saved breakpoints -> %s", breaks_path)


if __name__ == "__main__":
    main()
