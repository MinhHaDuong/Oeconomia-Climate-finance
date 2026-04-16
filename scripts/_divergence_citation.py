"""Citation graph divergence: data loading and graph infrastructure.

Private module — no main, no argparse. Called by compute_divergence.py.

Graph method implementations (G1-G8) live in _citation_methods.py.
This module provides:
  - load_citation_data() — load works + citations, build internal edges
  - _build_internal_edges() — filter to corpus-internal citation edges
  - _get_years() — year range from works
  - _cumulative_graph() — build DiGraph up to a year
  - _sliding_window_graph() — build DiGraph for a half-window (before/after)
  - _iter_sliding_pairs() — yield (year, window, G_before, G_after) pairs
  - _dict_to_df() — convert {year: value} to standard DataFrame
"""

import networkx as nx
import pandas as pd
from pipeline_loaders import load_analysis_corpus, load_refined_citations
from utils import get_logger

log = get_logger("_divergence_citation")


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
    if input_paths and len(input_paths) >= 2:
        works = pd.read_csv(
            input_paths[0],
            usecols=["doi", "year", "cited_by_count"],
            dtype={"year": float},
        )
        works["year"] = works["year"].astype(int)
        citations = pd.read_csv(input_paths[1])
    else:
        works, _ = load_analysis_corpus(with_embeddings=False)
        citations = load_refined_citations()

    works = works.dropna(subset=["doi"]).copy()

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


# ── Graph helpers ─────────────────────────────────────────────────────────


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


# ── Sliding window helpers (ticket 0048) ─────────────────────────────────


def _sliding_window_graph(works, internal_edges, year, window, side):
    """Build directed graph for one half-window.

    side='before': papers in [year - window, year]
    side='after':  papers in [year + 1, year + 1 + window]

    Only edges where both endpoints are in the node set are included.
    """
    if side == "before":
        year_lo, year_hi = year - window, year
    else:
        year_lo, year_hi = year + 1, year + 1 + window

    G = nx.DiGraph()
    mask = (works["year"] >= year_lo) & (works["year"] <= year_hi)
    nodes = works.loc[mask, "doi"].values
    G.add_nodes_from(nodes)

    node_set = set(nodes)
    edge_mask = internal_edges["source_year"].between(year_lo, year_hi)
    edges = internal_edges.loc[edge_mask, ["source_doi", "ref_doi"]].values
    valid_edges = [(s, t) for s, t in edges if s in node_set and t in node_set]
    G.add_edges_from(valid_edges)
    return G


def _iter_sliding_pairs(works, internal_edges, cfg):
    """Yield (year, window, G_before, G_after) for each valid sliding pair.

    Mirrors the semantic _iter_window_pairs pattern:
      before = [year - w, year], after = [year + 1, year + 1 + w]
    Skips pairs where either half has fewer than min_papers nodes.

    TODO: G1/G2/G5/G6/G8 each call this independently, rebuilding graphs
    for the same (year, window) pairs. A cache dict keyed by (year, w) could
    avoid redundant graph construction when multiple methods run sequentially.
    """
    from _divergence_io import get_min_papers

    div_cfg = cfg["divergence"]
    windows = div_cfg["windows"]
    min_papers = get_min_papers(len(works), cfg)

    year_min = int(works["year"].min())
    year_max = int(works["year"].max())

    for w in windows:
        for year in range(year_min + w, year_max - w):
            G_before = _sliding_window_graph(works, internal_edges, year, w, "before")
            G_after = _sliding_window_graph(works, internal_edges, year, w, "after")
            if G_before.number_of_nodes() < min_papers:
                continue
            if G_after.number_of_nodes() < min_papers:
                continue
            yield year, w, G_before, G_after
