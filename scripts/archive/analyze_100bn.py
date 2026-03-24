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

import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

warnings.filterwarnings("ignore")

# Add scripts dir to path for utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import BASE_DIR, CATALOGS_DIR, get_logger

log = get_logger("analyze_100bn")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

OUTPUT_PATH = os.path.join(TABLES_DIR, "tab_100bn_papers.csv")


# ---------------------------------------------------------------------------
# Step 1: Load data
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Step 2: Identify $100bn papers using keyword search
# ---------------------------------------------------------------------------
log.info("Identifying $100bn-related papers ...")

# Combine title + abstract for search (lowercased)
works["_text"] = (
    works["title"].fillna("").str.lower()
    + " "
    + works["abstract"].fillna("").str.lower()
)

def contains_pattern(text_series, *patterns):
    """Return boolean mask: True if any pattern matches."""
    mask = pd.Series(False, index=text_series.index)
    for pat in patterns:
        mask |= text_series.str.contains(pat, na=False, regex=True)
    return mask


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

print("\n" + "="*70)
print("STEP 2: $100bn SUB-CORPUS IDENTIFICATION")
print("="*70)
print(f"Total corpus: {len(works):,} papers")
print(f"$100bn sub-corpus: {len(papers_100bn):,} papers ({100*len(papers_100bn)/len(works):.1f}%)")

# ---------------------------------------------------------------------------
# Step 3: Top-20 by cited_by_count
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 3: TOP-20 $100bn PAPERS BY CITATION COUNT")
print("="*70)

top20 = (
    papers_100bn
    .sort_values("cited_by_count", ascending=False)
    .head(20)
    [["title", "first_author", "year", "journal", "cited_by_count", "doi"]]
)
print(top20.to_string(index=False, max_colwidth=60))

# ---------------------------------------------------------------------------
# Step 4a: Semantic space clustering
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 4a: SEMANTIC SPACE CLUSTERING")
print("="*70)

# Row indices of $100bn papers in the embeddings matrix
idx_100bn = papers_100bn.index.tolist()
idx_rest = works[~mask_final].index.tolist()

vecs_100bn = vectors[idx_100bn]
vecs_rest = vectors[idx_rest]

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
inter_dist_100bn_to_rest = np.linalg.norm(centroid_100bn - centroid_rest)

# Mean distance of all papers to rest centroid (baseline)
# Use random sample for speed
rng = np.random.default_rng(42)
sample_idx = rng.choice(len(idx_rest), min(5000, len(idx_rest)), replace=False)
sample_rest = vecs_rest_norm[sample_idx]
baseline_intra_rest = np.mean(np.linalg.norm(sample_rest - centroid_rest, axis=1))

print(f"$100bn group size: {len(idx_100bn)}")
print(f"Rest group size: {len(idx_rest)}")
print(f"Intra-group distance (100bn → their centroid): {intra_dist:.4f}")
print(f"Inter-centroid distance (100bn centroid → rest centroid): {inter_dist_100bn_to_rest:.4f}")
print(f"Baseline intra-group distance (rest → rest centroid): {baseline_intra_rest:.4f}")
print(f"Cohesion ratio (inter/intra): {inter_dist_100bn_to_rest/intra_dist:.3f}")

# Silhouette score for $100bn as a single cluster vs rest
# Use sample for efficiency
N_SAMPLE = min(3000, len(idx_rest))
rng2 = np.random.default_rng(42)
rest_sample_idx = rng2.choice(len(idx_rest), N_SAMPLE, replace=False)

X_silh = np.vstack([vecs_100bn_norm, vecs_rest_norm[rest_sample_idx]])
labels_silh = np.array([1]*len(idx_100bn) + [0]*N_SAMPLE)

sil_semantic = silhouette_score(X_silh, labels_silh, metric="euclidean", sample_size=min(2000, len(X_silh)))
print(f"\nSilhouette score (semantic space): {sil_semantic:.4f}")
print("  (Range: -1 to +1; >0.1 = mild clustering, >0.25 = meaningful)")

# ---------------------------------------------------------------------------
# Step 4b: Citation space clustering (bibliographic coupling → SVD)
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 4b: CITATION SPACE CLUSTERING (BIBLIOGRAPHIC COUPLING)")
print("="*70)

log.info("Loading refined_citations.csv ...")
cites = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_citations.csv"))
log.info("  %d citation links", len(cites))

# Build bibliographic coupling matrix
# Papers that cite the same references are coupled
# Use DOIs as paper identifiers
doi_to_idx = {}
for i, row in works.iterrows():
    if pd.notna(row.get("doi")) and row["doi"]:
        doi_to_idx[str(row["doi"]).lower().strip()] = i

# Filter citations to papers in our corpus
cites_clean = cites.dropna(subset=["source_doi", "ref_doi"]).copy()
cites_clean["source_doi"] = cites_clean["source_doi"].str.lower().str.strip()
cites_clean["ref_doi"] = cites_clean["ref_doi"].str.lower().str.strip()

# Build a paper-reference incidence matrix
# Rows = papers in corpus, Cols = unique references (DOIs)
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
# IDF: downweight very commonly cited references
ref_doc_freq = np.asarray((incidence > 0).sum(axis=0)).flatten()
idf = np.log1p(n_papers / (ref_doc_freq + 1))
incidence_tfidf = incidence.multiply(idf)

# SVD to get 100D citation space
log.info("  Running SVD (k=100) ...")
U, S, Vt = svds(incidence_tfidf, k=100)
# Sort by descending singular value
order = np.argsort(-S)
U = U[:, order]
S = S[order]

# L2-normalize rows
citation_vecs = normalize(U * S, norm="l2")

# Get $100bn paper indices that have citation data
# (some papers may have no DOI or no citations)
has_doi = works["doi"].notna() & (works["doi"] != "")
idx_100bn_with_doi = [i for i in idx_100bn if i < len(citation_vecs) and np.any(citation_vecs[i] != 0)]
idx_rest_with_doi = [i for i in idx_rest if i < len(citation_vecs) and np.any(citation_vecs[i] != 0)]

log.info("  $100bn papers with citation data: %d / %d", len(idx_100bn_with_doi), len(idx_100bn))
log.info("  Rest papers with citation data: %d / %d", len(idx_rest_with_doi), len(idx_rest))

if len(idx_100bn_with_doi) > 5:
    cvecs_100bn = citation_vecs[idx_100bn_with_doi]
    cvecs_rest = citation_vecs[idx_rest_with_doi]

    # Centroids
    ccentroid_100bn = cvecs_100bn.mean(axis=0)
    ccentroid_rest = cvecs_rest.mean(axis=0)

    # Distances
    cintra_dist = np.mean(np.linalg.norm(cvecs_100bn - ccentroid_100bn, axis=1))
    cinter_dist = np.linalg.norm(ccentroid_100bn - ccentroid_rest)

    rng3 = np.random.default_rng(42)
    csample_idx = rng3.choice(len(idx_rest_with_doi), min(5000, len(idx_rest_with_doi)), replace=False)
    csample_rest = cvecs_rest[csample_idx]
    cbaseline_intra = np.mean(np.linalg.norm(csample_rest - ccentroid_rest, axis=1))

    print(f"$100bn papers with citation data: {len(idx_100bn_with_doi)}")
    print(f"Intra-group distance (100bn → centroid): {cintra_dist:.4f}")
    print(f"Inter-centroid distance (100bn → rest): {cinter_dist:.4f}")
    print(f"Baseline intra-group distance (rest → rest centroid): {cbaseline_intra:.4f}")
    print(f"Cohesion ratio (inter/intra): {cinter_dist/cintra_dist:.3f}")

    # Silhouette in citation space
    N_SAMPLE_C = min(3000, len(idx_rest_with_doi))
    rng4 = np.random.default_rng(42)
    rest_csample = rng4.choice(len(idx_rest_with_doi), N_SAMPLE_C, replace=False)

    X_csilh = np.vstack([cvecs_100bn, cvecs_rest[rest_csample]])
    labels_csilh = np.array([1]*len(idx_100bn_with_doi) + [0]*N_SAMPLE_C)

    sil_citation = silhouette_score(X_csilh, labels_csilh, metric="euclidean",
                                    sample_size=min(2000, len(X_csilh)))
    print(f"\nSilhouette score (citation space): {sil_citation:.4f}")
    print("  (Range: -1 to +1; >0.1 = mild clustering, >0.25 = meaningful)")
else:
    print("Not enough $100bn papers with citation data for citation space analysis")
    sil_citation = None

# ---------------------------------------------------------------------------
# Step 5: Temporal trend
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 5: TEMPORAL TREND")
print("="*70)

years_range = range(2000, 2025)
corpus_by_year = works[works["year"].isin(years_range)].groupby("year").size().rename("corpus_total")
bn100_by_year = papers_100bn[papers_100bn["year"].isin(years_range)].groupby("year").size().rename("100bn_count")

trend = pd.concat([corpus_by_year, bn100_by_year], axis=1).fillna(0)
trend["100bn_count"] = trend["100bn_count"].astype(int)
trend["share_pct"] = (trend["100bn_count"] / trend["corpus_total"] * 100).round(1)

print(f"{'Year':<6} {'$100bn':>8} {'Total':>8} {'Share%':>8}")
print("-" * 35)
for yr, row in trend.iterrows():
    print(f"{int(yr):<6} {int(row['100bn_count']):>8} {int(row['corpus_total']):>8} {row['share_pct']:>8.1f}")

# ---------------------------------------------------------------------------
# Step 6: Distinctive references
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("STEP 6: DISTINCTIVE REFERENCES (TOP-10)")
print("="*70)

# Papers in $100bn sub-corpus with DOIs
bn100_dois = set(papers_100bn["doi"].dropna().str.lower().str.strip())
rest_dois = set(works[~mask_final]["doi"].dropna().str.lower().str.strip())

n_100bn_papers = len(bn100_dois)
n_rest_papers = len(rest_dois)

# References cited by $100bn papers
refs_100bn = cites_clean[cites_clean["source_doi"].isin(bn100_dois)][["ref_doi", "ref_title", "ref_first_author", "ref_year"]].copy()
refs_rest = cites_clean[cites_clean["source_doi"].isin(rest_dois)][["ref_doi", "ref_title", "ref_first_author", "ref_year"]].copy()

# Count how many $100bn papers cite each reference
ref_count_100bn = refs_100bn.groupby("ref_doi").size().rename("count_100bn")
ref_count_rest = refs_rest.groupby("ref_doi").size().rename("count_rest")

# Merge
ref_compare = pd.concat([ref_count_100bn, ref_count_rest], axis=1).fillna(0)
ref_compare["freq_100bn"] = ref_compare["count_100bn"] / max(n_100bn_papers, 1)
ref_compare["freq_rest"] = ref_compare["count_rest"] / max(n_rest_papers, 1)
ref_compare["distinctiveness"] = ref_compare["freq_100bn"] / (ref_compare["freq_rest"] + 0.001)

# Only consider references cited by at least 3 $100bn papers
ref_compare = ref_compare[ref_compare["count_100bn"] >= 3]

# Get top-10 most distinctive
top_refs = ref_compare.nlargest(10, "distinctiveness")

# Add metadata — prefer titles from citations table; fall back to works corpus
ref_meta = refs_100bn.drop_duplicates("ref_doi").set_index("ref_doi")[["ref_title", "ref_first_author", "ref_year"]]
top_refs = top_refs.join(ref_meta)

# For references with no title in the citations table, look up in the works corpus
doi_to_work = works.set_index("doi")[["title", "first_author", "year"]] if "doi" in works.columns else None
if doi_to_work is not None:
    for ref_doi, row in top_refs.iterrows():
        if pd.isna(row.get("ref_title")) or str(row.get("ref_title", "")).strip() in ("", "nan"):
            # Try to find in works corpus
            doi_norm = str(ref_doi).lower().strip()
            matches = works[works["doi"].str.lower().str.strip() == doi_norm]
            if not matches.empty:
                m = matches.iloc[0]
                top_refs.at[ref_doi, "ref_title"] = str(m.get("title", "") or "")
                top_refs.at[ref_doi, "ref_first_author"] = str(m.get("first_author", "") or "")
                yr = m.get("year", "")
                top_refs.at[ref_doi, "ref_year"] = str(int(yr)) if pd.notna(yr) else ""

print(f"Min citation threshold: 3 citations from $100bn papers")
print(f"References meeting threshold: {len(ref_compare)}")
print()
print(f"{'#':<3} {'Count':>6} {'Freq%':>6} {'Distinct':>9}  Title (Author, Year)")
print("-" * 90)
for rank, (doi, row) in enumerate(top_refs.iterrows(), 1):
    title = str(row.get("ref_title", ""))[:55] if pd.notna(row.get("ref_title")) else "(no title)"
    author = str(row.get("ref_first_author", ""))[:20] if pd.notna(row.get("ref_first_author")) else ""
    year = int(row["ref_year"]) if pd.notna(row.get("ref_year")) else "?"
    print(f"{rank:<3} {int(row['count_100bn']):>6} {100*row['freq_100bn']:>5.0f}%  {row['distinctiveness']:>8.1f}x  {title} ({author}, {year})")

# ---------------------------------------------------------------------------
# Save $100bn papers list
# ---------------------------------------------------------------------------
log.info("Saving $100bn papers to %s ...", OUTPUT_PATH)

save_cols = ["doi", "title", "first_author", "year", "journal",
             "cited_by_count", "abstract", "source_count", "in_v1"]
save_cols = [c for c in save_cols if c in papers_100bn.columns]

papers_100bn[save_cols].sort_values("cited_by_count", ascending=False).to_csv(
    OUTPUT_PATH, index=False
)
log.info("  Saved %d papers", len(papers_100bn))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "="*70)
print("SUMMARY: SOCIAL STRUCTURE HYPOTHESIS TEST")
print("="*70)
print(f"$100bn sub-corpus: {len(papers_100bn)} papers ({100*len(papers_100bn)/len(works):.1f}% of corpus)")
print()
print(f"SEMANTIC SPACE:")
print(f"  Silhouette score: {sil_semantic:.4f}")
print(f"  Intra-group dist: {intra_dist:.4f}")
print(f"  Inter-centroid dist: {inter_dist_100bn_to_rest:.4f}")
print(f"  Cohesion ratio: {inter_dist_100bn_to_rest/intra_dist:.3f}")
if sil_semantic > 0.15:
    print("  → CLUSTERS in semantic space (content is distinctive)")
elif sil_semantic > 0.05:
    print("  → Mild clustering in semantic space")
else:
    print("  → Does NOT cluster in semantic space (content similar to rest)")
print()
if sil_citation is not None:
    print(f"CITATION SPACE:")
    print(f"  Silhouette score: {sil_citation:.4f}")
    print(f"  Intra-group dist: {cintra_dist:.4f}")
    print(f"  Inter-centroid dist: {cinter_dist:.4f}")
    print(f"  Cohesion ratio: {cinter_dist/cintra_dist:.3f}")
    if sil_citation > 0.15:
        print("  → CLUSTERS in citation space (social network is cohesive)")
    elif sil_citation > 0.05:
        print("  → Mild clustering in citation space")
    else:
        print("  → Does NOT cluster in citation space")
    print()
    print("INTERPRETATION:")
    diff = sil_citation - sil_semantic
    if diff > 0.05:
        print("  CONFIRMS social structure hypothesis:")
        print("  $100bn debate clusters more in CITATION space than semantic space.")
        print("  These papers form a citation community despite semantic overlap")
        print("  with the broader climate finance literature.")
    elif sil_semantic - sil_citation > 0.05:
        print("  REJECTS social structure hypothesis:")
        print("  $100bn papers cluster more in SEMANTIC space — content drives clustering.")
    else:
        print(f"  WEAK / MIXED result: Δ silhouette = {diff:+.4f} (citation - semantic).")
        print("  Both scores are near zero — the $100bn sub-corpus is NOT a tight cluster")
        print("  in either space, suggesting it is a diffuse topic woven through the")
        print("  literature rather than a separable community.")
print()
print(f"Output saved: {OUTPUT_PATH}")
