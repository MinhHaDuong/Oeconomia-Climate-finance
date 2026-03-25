# WARNING: AI-generated, not human-reviewed
"""Analyze the $100bn climate finance accounting sub-literature.

Tests whether the $100bn pledge sub-topic clusters in citation space
vs semantic space — the 'social structure' hypothesis.

Steps:
1. Load refined_works.csv and identify $100bn-related papers
2. Report counts and top-20 by cited_by_count
3. Semantic space clustering (silhouette, intra vs inter distance)
4. Citation space clustering (bibliographic coupling → SVD → silhouette)
5. Temporal trend
6. Distinctive references

Output: content/tables/tab_100bn_papers.csv
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

from utils import BASE_DIR, CATALOGS_DIR, get_logger

warnings.filterwarnings("ignore")

log = get_logger("analyze_100bn")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
OUTPUT_PATH = os.path.join(TABLES_DIR, "tab_100bn_papers.csv")


def contains_pattern(text_series, *patterns):
    """Return boolean mask: True if any pattern matches."""
    mask = pd.Series(False, index=text_series.index)
    for pat in patterns:
        mask |= text_series.str.contains(pat, na=False, regex=True)
    return mask


def identify_100bn_papers(works):
    """Identify $100bn-related papers using keyword search and deduplicate."""
    log.info("Identifying $100bn-related papers ...")

    # Combine title + abstract for search (lowercased)
    works["_text"] = (
        works["title"].fillna("").str.lower()
        + " "
        + works["abstract"].fillna("").str.lower()
    )

    # Pattern groups — all require direct climate finance context to avoid false positives.
    # Uses non-capturing (?:...) groups to avoid pandas regex warnings.

    # "$100bn / 100 billion" must co-occur in close proximity with "climate finance"
    mask_100bn = contains_pattern(
        works["_text"],
        r"100 billion.*climate finance",
        r"climate finance.*100 billion",
        r"100bn.*climate finance",
        r"climate finance.*100bn",
    )

    # Title-focused: papers about $100bn + climate in the title
    mask_title_100 = (
        works["title"].fillna("").str.lower().str.contains(r"100 billion|100bn", na=False, regex=True)
        & works["title"].fillna("").str.lower().str.contains(r"climate", na=False, regex=True)
    )

    mask_accounting = contains_pattern(
        works["_text"],
        r"climate finance accounting",
        r"climate finance measurement",
        r"climate finance tracking",
    )

    mask_additionality = (
        contains_pattern(works["_text"], r"new and additional")
        & contains_pattern(works["_text"], r"climate finance|climate fund")
    )

    mask_definition = contains_pattern(
        works["_text"],
        r"climate finance definition",
        r"what counts as climate finance",
    )

    mask_oxfam = (
        contains_pattern(works["_text"], r"oxfam.*climate finance")
        | contains_pattern(works["_text"], r"climate finance.*oxfam")
    )

    mask_oecd = contains_pattern(
        works["_text"],
        r"oecd.*climate finance.*(?:reporting|tracking|rio marker)",
        r"(?:reporting|tracking|rio marker).*climate finance.*oecd",
    )

    mask_scf = contains_pattern(
        works["_text"],
        r"standing committee on finance",
        r"scf biennial",
    )

    mask_rio = (
        contains_pattern(works["_text"], r"rio marker")
        & contains_pattern(works["_text"], r"climate finance|climate fund")
    )

    # Combined final mask — each sub-pattern already requires climate finance context
    mask_final = (
        mask_100bn
        | mask_title_100
        | mask_accounting
        | mask_additionality
        | mask_definition
        | mask_oxfam
        | mask_oecd
        | mask_scf
        | mask_rio
    )

    papers_100bn = works[mask_final].copy()
    log.info("  Found %d $100bn-related papers (before dedup)", len(papers_100bn))

    # Deduplicate near-identical papers by title.
    # Some papers (e.g. COP27 joint editorials) appear in 10-100+ journals with
    # the same title. Keep only the most-cited instance to prevent them from
    # dominating distinctive-reference analysis while inflating the sub-corpus.
    title_norm = papers_100bn["title"].fillna("").str.strip().str.lower()
    dup_titles = title_norm[title_norm.duplicated(keep=False)]
    if len(dup_titles) > 0:
        n_before = len(papers_100bn)
        # Keep the row with highest cited_by_count for each duplicate title group
        papers_100bn["_title_norm"] = title_norm
        # Fill NaN cited_by_count with 0 for groupby idxmax
        papers_100bn["cited_by_count_filled"] = papers_100bn["cited_by_count"].fillna(0)
        idx_keep = papers_100bn.groupby("_title_norm")["cited_by_count_filled"].idxmax()
        papers_100bn = papers_100bn.drop(columns=["cited_by_count_filled"])
        papers_100bn = papers_100bn.loc[idx_keep].drop(columns=["_title_norm"])
        log.info(
            "  Deduplicated %d → %d papers (dropped %d duplicate titles)",
            n_before, len(papers_100bn), n_before - len(papers_100bn),
        )
    log.info("  Found %d $100bn-related papers (after dedup)", len(papers_100bn))

    # Report counts per sub-pattern
    for name, mask in [
        ("100 billion co-occurring with CF (abstract)", mask_100bn),
        ("Title: 100bn/100 billion + climate", mask_title_100),
        ("CF accounting/measurement/tracking", mask_accounting),
        ("New and additional + CF context", mask_additionality),
        ("CF definition / what counts", mask_definition),
        ("Oxfam + climate finance", mask_oxfam),
        ("OECD + CF + reporting/tracking/Rio markers", mask_oecd),
        ("Standing Committee on Finance / SCF biennial", mask_scf),
        ("Rio markers + CF", mask_rio),
    ]:
        n = mask.sum()
        log.info("    %-45s %d", name, n)

    return papers_100bn, mask_final


def analyze_semantic_space(works, papers_100bn, mask_final, vectors):
    """Compute semantic space clustering metrics for $100bn sub-corpus."""
    log.info("=== SEMANTIC SPACE CLUSTERING ===")

    # Row indices of $100bn papers in the embeddings matrix
    idx_100bn = papers_100bn.index.tolist()
    idx_rest = works[~mask_final].index.tolist()

    # L2-normalize for cosine distances
    vecs_norm = normalize(vectors, norm="l2")
    vecs_100bn_norm = vecs_norm[idx_100bn]
    vecs_rest_norm = vecs_norm[idx_rest]

    # Centroid of $100bn papers
    centroid_100bn = vecs_100bn_norm.mean(axis=0)
    centroid_rest = vecs_rest_norm.mean(axis=0)

    # Intra-group distance: mean distance of $100bn papers to their centroid
    intra_dist = np.mean(np.linalg.norm(vecs_100bn_norm - centroid_100bn, axis=1))

    # Inter-group distance: mean distance of $100bn papers to rest centroid
    inter_dist = np.linalg.norm(centroid_100bn - centroid_rest)

    # Mean distance of all papers to rest centroid (baseline)
    rng = np.random.default_rng(42)
    sample_idx = rng.choice(len(idx_rest), min(5000, len(idx_rest)), replace=False)
    sample_rest = vecs_rest_norm[sample_idx]
    baseline_intra_rest = np.mean(np.linalg.norm(sample_rest - centroid_rest, axis=1))

    log.info("$100bn group size: %d", len(idx_100bn))
    log.info("Rest group size: %d", len(idx_rest))
    log.info("Intra-group distance (100bn → their centroid): %.4f", intra_dist)
    log.info("Inter-centroid distance (100bn centroid → rest centroid): %.4f", inter_dist)
    log.info("Baseline intra-group distance (rest → rest centroid): %.4f", baseline_intra_rest)
    log.info("Cohesion ratio (inter/intra): %.3f", inter_dist / intra_dist)

    # Silhouette score for $100bn as a single cluster vs rest
    N_SAMPLE = min(3000, len(idx_rest))
    rng2 = np.random.default_rng(42)
    rest_sample_idx = rng2.choice(len(idx_rest), N_SAMPLE, replace=False)

    X_silh = np.vstack([vecs_100bn_norm, vecs_rest_norm[rest_sample_idx]])
    labels_silh = np.array([1] * len(idx_100bn) + [0] * N_SAMPLE)

    sil_semantic = silhouette_score(X_silh, labels_silh, metric="euclidean", sample_size=min(2000, len(X_silh)))
    log.info("Silhouette score (semantic space): %.4f", sil_semantic)
    log.info("  (Range: -1 to +1; >0.1 = mild clustering, >0.25 = meaningful)")

    return sil_semantic, intra_dist, inter_dist


def analyze_citation_space(works, papers_100bn, mask_final):
    """Compute citation space clustering via bibliographic coupling → SVD."""
    log.info("=== CITATION SPACE CLUSTERING (BIBLIOGRAPHIC COUPLING) ===")

    idx_100bn = papers_100bn.index.tolist()
    idx_rest = works[~mask_final].index.tolist()

    log.info("Loading refined_citations.csv ...")
    cites = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_citations.csv"))
    log.info("  %d citation links", len(cites))

    # Build bibliographic coupling matrix
    doi_to_idx = {}
    for i, row in works.iterrows():
        if pd.notna(row.get("doi")) and row["doi"]:
            doi_to_idx[str(row["doi"]).lower().strip()] = i

    # Filter citations to papers in our corpus
    cites_clean = cites.dropna(subset=["source_doi", "ref_doi"]).copy()
    cites_clean["source_doi"] = cites_clean["source_doi"].str.lower().str.strip()
    cites_clean["ref_doi"] = cites_clean["ref_doi"].str.lower().str.strip()

    paper_dois = set(doi_to_idx.keys())
    cites_in_corpus = cites_clean[cites_clean["source_doi"].isin(paper_dois)]
    log.info("  Citations from corpus papers: %d", len(cites_in_corpus))

    # Map source papers
    cites_in_corpus = cites_in_corpus.copy()
    cites_in_corpus["paper_idx"] = cites_in_corpus["source_doi"].map(doi_to_idx)
    cites_in_corpus = cites_in_corpus.dropna(subset=["paper_idx"])
    cites_in_corpus["paper_idx"] = cites_in_corpus["paper_idx"].astype(int)

    # Encode references
    unique_refs = cites_in_corpus["ref_doi"].unique()
    ref_to_col = {r: c for c, r in enumerate(unique_refs)}
    cites_in_corpus["ref_idx"] = cites_in_corpus["ref_doi"].map(ref_to_col)

    n_papers = len(works)
    n_refs = len(unique_refs)
    log.info("  Building incidence matrix: %d papers × %d refs", n_papers, n_refs)

    row_ids = cites_in_corpus["paper_idx"].values
    col_ids = cites_in_corpus["ref_idx"].values
    data = np.ones(len(row_ids))

    # Build sparse incidence matrix
    incidence = csr_matrix((data, (row_ids, col_ids)), shape=(n_papers, n_refs))

    # Apply TF-IDF-like weighting (log-normalized, IDF)
    ref_doc_freq = np.asarray((incidence > 0).sum(axis=0)).flatten()
    idf = np.log1p(n_papers / (ref_doc_freq + 1))
    incidence_tfidf = incidence.multiply(idf)

    # SVD to get 100D citation space
    log.info("  Running SVD (k=100) ...")
    U, S, _Vt = svds(incidence_tfidf, k=100)
    order = np.argsort(-S)
    U = U[:, order]
    S = S[order]

    # L2-normalize rows
    citation_vecs = normalize(U * S, norm="l2")

    # Get $100bn paper indices that have citation data
    idx_100bn_with_doi = [i for i in idx_100bn if i < len(citation_vecs) and np.any(citation_vecs[i] != 0)]
    idx_rest_with_doi = [i for i in idx_rest if i < len(citation_vecs) and np.any(citation_vecs[i] != 0)]

    log.info("  $100bn papers with citation data: %d / %d", len(idx_100bn_with_doi), len(idx_100bn))
    log.info("  Rest papers with citation data: %d / %d", len(idx_rest_with_doi), len(idx_rest))

    sil_citation = None
    if len(idx_100bn_with_doi) > 5:
        cvecs_100bn = citation_vecs[idx_100bn_with_doi]
        cvecs_rest = citation_vecs[idx_rest_with_doi]

        ccentroid_100bn = cvecs_100bn.mean(axis=0)
        ccentroid_rest = cvecs_rest.mean(axis=0)

        cintra_dist = np.mean(np.linalg.norm(cvecs_100bn - ccentroid_100bn, axis=1))
        cinter_dist = np.linalg.norm(ccentroid_100bn - ccentroid_rest)

        rng3 = np.random.default_rng(42)
        csample_idx = rng3.choice(len(idx_rest_with_doi), min(5000, len(idx_rest_with_doi)), replace=False)
        csample_rest = cvecs_rest[csample_idx]
        cbaseline_intra = np.mean(np.linalg.norm(csample_rest - ccentroid_rest, axis=1))

        log.info("$100bn papers with citation data: %d", len(idx_100bn_with_doi))
        log.info("Intra-group distance (100bn → centroid): %.4f", cintra_dist)
        log.info("Inter-centroid distance (100bn → rest): %.4f", cinter_dist)
        log.info("Baseline intra-group distance (rest → rest centroid): %.4f", cbaseline_intra)
        log.info("Cohesion ratio (inter/intra): %.3f", cinter_dist / cintra_dist)

        # Silhouette in citation space
        N_SAMPLE_C = min(3000, len(idx_rest_with_doi))
        rng4 = np.random.default_rng(42)
        rest_csample = rng4.choice(len(idx_rest_with_doi), N_SAMPLE_C, replace=False)

        X_csilh = np.vstack([cvecs_100bn, cvecs_rest[rest_csample]])
        labels_csilh = np.array([1] * len(idx_100bn_with_doi) + [0] * N_SAMPLE_C)

        sil_citation = silhouette_score(X_csilh, labels_csilh, metric="euclidean",
                                        sample_size=min(2000, len(X_csilh)))
        log.info("Silhouette score (citation space): %.4f", sil_citation)
        log.info("  (Range: -1 to +1; >0.1 = mild clustering, >0.25 = meaningful)")
    else:
        log.info("Not enough $100bn papers with citation data for citation space analysis")

    return sil_citation, cites_clean


def analyze_distinctive_refs(works, papers_100bn, mask_final, cites_clean):
    """Find references distinctively cited by $100bn papers vs rest of corpus."""
    log.info("=== DISTINCTIVE REFERENCES (TOP-10) ===")

    bn100_dois = set(papers_100bn["doi"].dropna().str.lower().str.strip())
    rest_dois = set(works[~mask_final]["doi"].dropna().str.lower().str.strip())

    n_100bn_papers = len(bn100_dois)
    n_rest_papers = len(rest_dois)

    refs_100bn = cites_clean[cites_clean["source_doi"].isin(bn100_dois)][["ref_doi", "ref_title", "ref_first_author", "ref_year"]].copy()
    refs_rest = cites_clean[cites_clean["source_doi"].isin(rest_dois)][["ref_doi", "ref_title", "ref_first_author", "ref_year"]].copy()

    ref_count_100bn = refs_100bn.groupby("ref_doi").size().rename("count_100bn")
    ref_count_rest = refs_rest.groupby("ref_doi").size().rename("count_rest")

    ref_compare = pd.concat([ref_count_100bn, ref_count_rest], axis=1).fillna(0)
    ref_compare["freq_100bn"] = ref_compare["count_100bn"] / max(n_100bn_papers, 1)
    ref_compare["freq_rest"] = ref_compare["count_rest"] / max(n_rest_papers, 1)
    ref_compare["distinctiveness"] = ref_compare["freq_100bn"] / (ref_compare["freq_rest"] + 0.001)

    # Only consider references cited by at least 3 $100bn papers
    ref_compare = ref_compare[ref_compare["count_100bn"] >= 3]

    top_refs = ref_compare.nlargest(10, "distinctiveness")

    # Add metadata — prefer titles from citations table; fall back to works corpus
    ref_meta = refs_100bn.drop_duplicates("ref_doi").set_index("ref_doi")[["ref_title", "ref_first_author", "ref_year"]]
    top_refs = top_refs.join(ref_meta)

    # For references with no title in the citations table, look up in the works corpus
    if "doi" in works.columns:
        for ref_doi, row in top_refs.iterrows():
            if pd.isna(row.get("ref_title")) or str(row.get("ref_title", "")).strip() in ("", "nan"):
                doi_norm = str(ref_doi).lower().strip()
                matches = works[works["doi"].str.lower().str.strip() == doi_norm]
                if not matches.empty:
                    m = matches.iloc[0]
                    top_refs.at[ref_doi, "ref_title"] = str(m.get("title", "") or "")
                    top_refs.at[ref_doi, "ref_first_author"] = str(m.get("first_author", "") or "")
                    yr = m.get("year", "")
                    top_refs.at[ref_doi, "ref_year"] = str(int(yr)) if pd.notna(yr) else ""

    log.info("Min citation threshold: 3 citations from $100bn papers")
    log.info("References meeting threshold: %d", len(ref_compare))
    for rank, (doi, row) in enumerate(top_refs.iterrows(), 1):
        title = str(row.get("ref_title", ""))[:55] if pd.notna(row.get("ref_title")) else "(no title)"
        author = str(row.get("ref_first_author", ""))[:20] if pd.notna(row.get("ref_first_author")) else ""
        year = int(row["ref_year"]) if pd.notna(row.get("ref_year")) else "?"
        log.info(
            "%d  %d  %5.0f%%  %8.1fx  %s (%s, %s)",
            rank, int(row["count_100bn"]), 100 * row["freq_100bn"],
            row["distinctiveness"], title, author, year,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Analyze the $100bn climate finance accounting sub-literature"
    )
    parser.add_argument("--no-pdf", action="store_true", help="No-op (no figures generated here)")
    _args = parser.parse_args()

    os.makedirs(TABLES_DIR, exist_ok=True)

    # Step 1: Load data
    log.info("Loading refined_works.csv ...")
    works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
    log.info("  %d papers total", len(works))

    log.info("Loading refined_embeddings.npz ...")
    emb_data = np.load(os.path.join(CATALOGS_DIR, "refined_embeddings.npz"))
    vectors = emb_data["vectors"].astype(np.float32)
    assert len(vectors) == len(works), (
        f"Embeddings ({len(vectors)}) and works ({len(works)}) count mismatch"
    )
    log.info("  Embeddings shape: %s", vectors.shape)

    # Step 2: Identify $100bn papers
    papers_100bn, mask_final = identify_100bn_papers(works)
    log.info("Total corpus: %d papers", len(works))
    log.info("$100bn sub-corpus: %d papers (%.1f%%)",
             len(papers_100bn), 100 * len(papers_100bn) / len(works))

    # Step 3: Top-20 by citation count
    log.info("=== TOP-20 $100bn PAPERS BY CITATION COUNT ===")
    top20 = (
        papers_100bn
        .sort_values("cited_by_count", ascending=False)
        .head(20)
        [["title", "first_author", "year", "journal", "cited_by_count", "doi"]]
    )
    log.info("\n%s", top20.to_string(index=False, max_colwidth=60))

    # Step 4a: Semantic space clustering
    sil_semantic, intra_dist, inter_dist = analyze_semantic_space(
        works, papers_100bn, mask_final, vectors
    )

    # Step 4b: Citation space clustering
    sil_citation, cites_clean = analyze_citation_space(works, papers_100bn, mask_final)

    # Step 5: Temporal trend
    log.info("=== TEMPORAL TREND ===")
    years_range = range(2000, 2025)
    corpus_by_year = works[works["year"].isin(years_range)].groupby("year").size().rename("corpus_total")
    bn100_by_year = papers_100bn[papers_100bn["year"].isin(years_range)].groupby("year").size().rename("100bn_count")

    trend = pd.concat([corpus_by_year, bn100_by_year], axis=1).fillna(0)
    trend["100bn_count"] = trend["100bn_count"].astype(int)
    trend["share_pct"] = (trend["100bn_count"] / trend["corpus_total"] * 100).round(1)

    log.info("%-6s %8s %8s %8s", "Year", "$100bn", "Total", "Share%")
    for yr, row in trend.iterrows():
        log.info("%-6d %8d %8d %8.1f", int(yr), int(row["100bn_count"]),
                 int(row["corpus_total"]), row["share_pct"])

    # Step 6: Distinctive references
    analyze_distinctive_refs(works, papers_100bn, mask_final, cites_clean)

    # Save $100bn papers list
    log.info("Saving $100bn papers to %s ...", OUTPUT_PATH)
    save_cols = ["doi", "title", "first_author", "year", "journal",
                 "cited_by_count", "abstract", "source_count", "in_v1"]
    save_cols = [c for c in save_cols if c in papers_100bn.columns]
    papers_100bn[save_cols].sort_values("cited_by_count", ascending=False).to_csv(
        OUTPUT_PATH, index=False
    )
    log.info("  Saved %d papers", len(papers_100bn))

    # Summary
    log.info("=== SUMMARY: SOCIAL STRUCTURE HYPOTHESIS TEST ===")
    log.info("$100bn sub-corpus: %d papers (%.1f%% of corpus)",
             len(papers_100bn), 100 * len(papers_100bn) / len(works))
    log.info("SEMANTIC SPACE:")
    log.info("  Silhouette score: %.4f", sil_semantic)
    log.info("  Intra-group dist: %.4f", intra_dist)
    log.info("  Inter-centroid dist: %.4f", inter_dist)
    log.info("  Cohesion ratio: %.3f", inter_dist / intra_dist)
    if sil_semantic > 0.15:
        log.info("  → CLUSTERS in semantic space (content is distinctive)")
    elif sil_semantic > 0.05:
        log.info("  → Mild clustering in semantic space")
    else:
        log.info("  → Does NOT cluster in semantic space (content similar to rest)")

    if sil_citation is not None:
        log.info("CITATION SPACE:")
        log.info("  Silhouette score: %.4f", sil_citation)
        diff = sil_citation - sil_semantic
        if diff > 0.05:
            log.info("  CONFIRMS social structure hypothesis:")
            log.info("  $100bn debate clusters more in CITATION space than semantic space.")
        elif sil_semantic - sil_citation > 0.05:
            log.info("  REJECTS social structure hypothesis:")
            log.info("  $100bn papers cluster more in SEMANTIC space — content drives clustering.")
        else:
            log.info("  WEAK / MIXED result: Δ silhouette = %+.4f (citation - semantic).", diff)

    log.info("Output saved: %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
