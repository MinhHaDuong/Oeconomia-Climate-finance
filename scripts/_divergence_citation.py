"""Citation graph divergence: data loading and graph infrastructure.

Private module — no main, no argparse. Called by compute_divergence.py.

Graph method implementations (G1-G8) live in _citation_methods.py.
This module provides:
  - load_citation_data() — load works + citations, build internal edges
  - _build_internal_edges() — filter to corpus-internal citation edges
  - _get_years() — year range from works
  - _cumulative_graph() — build DiGraph up to a year
  - _incremental_graphs() — yield (year, G) pairs incrementally
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


def _incremental_graphs(works, internal_edges, years):
    """Yield (year, G) pairs, building the graph incrementally.

    Each iteration adds that year's nodes and edges to the running graph.
    The caller receives the *same* mutable DiGraph object each iteration
    (so must not store references across iterations without copying).
    """
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
