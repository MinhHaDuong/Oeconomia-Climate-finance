"""Detect intellectual traditions preceding climate finance (pre-2007) via semantic clustering.

Approach:
1. Filter corpus to year <= 2006 (pre-crystallization period)
2. Run KMeans with k=3,4,5 on sentence-BERT embeddings
3. Characterize clusters via TF-IDF top terms
4. Identify most-cited papers per cluster
5. Assess whether clusters map to the three hypothesized traditions:
   - Environmental economics (carbon pricing, externalities, IAMs)
   - Development economics (ODA, aid flows, concessionality)
   - Burden-sharing (equity, Negishi weights, "who should pay")

Outputs:
- stdout: detailed cluster profiles
- content/tables/traditions_clusters.csv: cluster assignments for pre-2007 papers
- content/tables/traditions_top_papers.csv: top-cited papers per cluster
- content/tables/traditions_top_terms.csv: TF-IDF top terms per cluster
"""

import logging
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore", category=FutureWarning)

log = logging.getLogger(__name__)

# --- Paths (match project conventions from utils.py) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get(
    "CLIMATE_FINANCE_DATA",
    os.path.expanduser("~/data/projets/Oeconomia-Climate-finance"),
)
CATALOGS_DIR = os.path.join(DATA_DIR, "catalogs")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npz")

# =============================================================================
# 1. Load data and align embeddings (same logic as analyze_bimodality.py)
# =============================================================================
log.info("=" * 70)
log.info("DETECTING PRE-2007 INTELLECTUAL TRADITIONS VIA SEMANTIC CLUSTERING")
log.info("=" * 70)

log.info("\nLoading data...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce").fillna(0)

# Embeddings are aligned with: abstract present, len>50, year in [1990,2025]
has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df_all = works[has_abstract & in_range].copy().reset_index(drop=True)

embeddings_all = np.load(EMBEDDINGS_PATH, allow_pickle=True)["vectors"]
assert len(embeddings_all) == len(df_all), (
    f"Embedding alignment mismatch: {len(embeddings_all)} embeddings vs {len(df_all)} papers"
)
log.info(f"Loaded {len(df_all)} papers with {embeddings_all.shape[1]}D embeddings")

# =============================================================================
# 2. Filter to pre-2007 papers
# =============================================================================
pre2007_mask = df_all["year"] <= 2006
df = df_all[pre2007_mask].copy().reset_index(drop=True)
embeddings = embeddings_all[pre2007_mask.values]

log.info(f"\nPre-2007 subset: {len(df)} papers ({embeddings.shape[1]}D)")
log.info(f"Year range: {int(df['year'].min())}–{int(df['year'].max())}")
log.info(f"Median citations: {df['cited_by_count'].median():.0f}, "
      f"mean: {df['cited_by_count'].mean():.1f}")

# =============================================================================
# 3. KMeans clustering for k=3,4,5
# =============================================================================
log.info("\n" + "=" * 70)
log.info("KMEANS CLUSTERING (k=3, 4, 5)")
log.info("=" * 70)

results = {}
for k in [3, 4, 5]:
    km = KMeans(n_clusters=k, n_init=20, random_state=42, max_iter=500)
    labels = km.fit_predict(embeddings)
    sil = silhouette_score(embeddings, labels, sample_size=min(5000, len(embeddings)))
    inertia = km.inertia_
    results[k] = {"labels": labels, "model": km, "silhouette": sil, "inertia": inertia}
    log.info(f"\nk={k}: silhouette={sil:.3f}, inertia={inertia:.0f}")
    sizes = pd.Series(labels).value_counts().sort_index()
    for c, n in sizes.items():
        log.info(f"  Cluster {c}: {n} papers ({100*n/len(df):.1f}%)")

# =============================================================================
# 4. TF-IDF characterization for each k
# =============================================================================
log.info("\n" + "=" * 70)
log.info("TF-IDF TOP TERMS PER CLUSTER")
log.info("=" * 70)

# Build TF-IDF on abstracts
abstracts = df["abstract"].fillna("").tolist()
tfidf = TfidfVectorizer(
    max_features=5000,
    stop_words="english",
    ngram_range=(1, 2),
    min_df=3,
    max_df=0.5,
)
tfidf_matrix = tfidf.fit_transform(abstracts)
feature_names = np.array(tfidf.get_feature_names_out())

N_TOP_TERMS = 20

all_top_terms = {}  # k -> {cluster -> [terms]}
for k in [3, 4, 5]:
    log.info(f"\n--- k={k} (silhouette={results[k]['silhouette']:.3f}) ---")
    labels = results[k]["labels"]
    all_top_terms[k] = {}

    for c in range(k):
        mask = labels == c
        # Mean TF-IDF for this cluster
        cluster_tfidf = tfidf_matrix[mask].mean(axis=0).A1
        # Subtract global mean to get distinctive terms
        global_tfidf = tfidf_matrix.mean(axis=0).A1
        diff = cluster_tfidf - global_tfidf
        top_idx = diff.argsort()[::-1][:N_TOP_TERMS]
        top_terms = feature_names[top_idx]
        top_scores = diff[top_idx]

        all_top_terms[k][c] = list(top_terms)

        n_papers = mask.sum()
        median_cite = df.loc[mask, "cited_by_count"].median()
        log.info(f"\n  Cluster {c} ({n_papers} papers, median cites={median_cite:.0f}):")
        for term, score in zip(top_terms[:15], top_scores[:15]):
            log.info(f"    {score:+.4f}  {term}")

# =============================================================================
# 5. Top-cited papers per cluster (for best k)
# =============================================================================
log.info("\n" + "=" * 70)
log.info("TOP-CITED PAPERS PER CLUSTER")
log.info("=" * 70)

N_TOP_PAPERS = 10

for k in [3, 4, 5]:
    log.info(f"\n{'='*50}")
    log.info(f"k={k}")
    log.info(f"{'='*50}")
    labels = results[k]["labels"]
    df[f"cluster_k{k}"] = labels

    for c in range(k):
        cluster_papers = df[labels == c].nlargest(N_TOP_PAPERS, "cited_by_count")
        terms_str = ", ".join(all_top_terms[k][c][:8])
        log.info(f"\n  Cluster {c} — Top terms: {terms_str}")
        log.info(f"  {'—'*60}")
        for _, row in cluster_papers.iterrows():
            title = str(row.get("title", ""))[:80]
            author = str(row.get("first_author", ""))[:25]
            yr = int(row["year"]) if pd.notna(row["year"]) else "?"
            cites = int(row["cited_by_count"])
            log.info(f"    [{cites:>5} cites] {author} ({yr}) {title}")

# =============================================================================
# 6. Silhouette comparison and recommendation
# =============================================================================
log.info("\n" + "=" * 70)
log.info("SUMMARY: SILHOUETTE SCORES")
log.info("=" * 70)
for k in [3, 4, 5]:
    log.info(f"  k={k}: silhouette = {results[k]['silhouette']:.4f}")

best_k = max(results, key=lambda k: results[k]["silhouette"])
log.info(f"\nBest silhouette at k={best_k}")

# =============================================================================
# 7. Year distribution per cluster (for k=3)
# =============================================================================
log.info("\n" + "=" * 70)
log.info("YEAR DISTRIBUTION PER CLUSTER (k=3)")
log.info("=" * 70)

labels_3 = results[3]["labels"]
for c in range(3):
    years = df.loc[labels_3 == c, "year"]
    log.info(f"  Cluster {c}: mean year={years.mean():.1f}, "
          f"median={years.median():.0f}, "
          f"range={int(years.min())}–{int(years.max())}")

# =============================================================================
# 8. Language distribution per cluster (k=3)
# =============================================================================
log.info("\n" + "=" * 70)
log.info("LANGUAGE DISTRIBUTION PER CLUSTER (k=3)")
log.info("=" * 70)

for c in range(3):
    langs = df.loc[labels_3 == c, "language"].fillna("unknown")
    lang_counts = langs.value_counts().head(5)
    log.info(f"  Cluster {c}:")
    for lang, count in lang_counts.items():
        pct = 100 * count / (labels_3 == c).sum()
        log.info(f"    {lang}: {count} ({pct:.1f}%)")

# =============================================================================
# 9. Source distribution per cluster (k=3)
# =============================================================================
log.info("\n" + "=" * 70)
log.info("SOURCE DISTRIBUTION PER CLUSTER (k=3)")
log.info("=" * 70)

for c in range(3):
    sources = df.loc[labels_3 == c, "source"].fillna("unknown")
    src_counts = sources.value_counts()
    log.info(f"  Cluster {c}:")
    for src, count in src_counts.items():
        pct = 100 * count / (labels_3 == c).sum()
        log.info(f"    {src}: {count} ({pct:.1f}%)")

# =============================================================================
# 10. Also try k=3 on CORE pre-2007 papers (cited >= 50)
# =============================================================================
log.info("\n" + "=" * 70)
log.info("CORE PAPERS ONLY (cited_by_count >= 50, k=3)")
log.info("=" * 70)

core_mask = df["cited_by_count"] >= 50
df_core = df[core_mask].copy().reset_index(drop=True)
emb_core = embeddings[core_mask.values]
log.info(f"Core pre-2007 papers: {len(df_core)}")

if len(df_core) >= 10:
    km_core = KMeans(n_clusters=3, n_init=20, random_state=42, max_iter=500)
    labels_core = km_core.fit_predict(emb_core)
    sil_core = silhouette_score(emb_core, labels_core)
    log.info(f"Silhouette (core, k=3): {sil_core:.3f}")

    # TF-IDF on core
    abstracts_core = df_core["abstract"].fillna("").tolist()
    tfidf_core = TfidfVectorizer(
        max_features=3000, stop_words="english",
        ngram_range=(1, 2), min_df=2, max_df=0.6,
    )
    tfidf_core_mat = tfidf_core.fit_transform(abstracts_core)
    feat_core = np.array(tfidf_core.get_feature_names_out())

    for c in range(3):
        mask_c = labels_core == c
        cluster_tfidf = tfidf_core_mat[mask_c].mean(axis=0).A1
        global_tfidf = tfidf_core_mat.mean(axis=0).A1
        diff = cluster_tfidf - global_tfidf
        top_idx = diff.argsort()[::-1][:15]
        top_terms = feat_core[top_idx]

        n_papers = mask_c.sum()
        log.info(f"\n  Core Cluster {c} ({n_papers} papers):")
        for term in top_terms[:12]:
            log.info(f"    {term}")

        # Top papers
        cluster_papers = df_core[mask_c].nlargest(5, "cited_by_count")
        log.info("  Top papers:")
        for _, row in cluster_papers.iterrows():
            title = str(row.get("title", ""))[:75]
            author = str(row.get("first_author", ""))[:25]
            yr = int(row["year"]) if pd.notna(row["year"]) else "?"
            cites = int(row["cited_by_count"])
            log.info(f"    [{cites:>5}] {author} ({yr}) {title}")

    df_core["cluster_core_k3"] = labels_core
else:
    log.info("Too few core papers for clustering.")

# =============================================================================
# 11. Save outputs
# =============================================================================
log.info("\n" + "=" * 70)
log.info("SAVING OUTPUTS")
log.info("=" * 70)

# Cluster assignments (k=3, full pre-2007)
out_clusters = df[["title", "first_author", "year", "cited_by_count",
                    "cluster_k3", "cluster_k4", "cluster_k5"]].copy()
out_clusters.to_csv(os.path.join(TABLES_DIR, "traditions_clusters.csv"), index=False)
log.info(f"Saved {len(out_clusters)} rows -> content/tables/traditions_clusters.csv")

# Top papers per cluster (k=3)
top_papers_rows = []
for c in range(3):
    cluster_papers = df[results[3]["labels"] == c].nlargest(N_TOP_PAPERS, "cited_by_count")
    for _, row in cluster_papers.iterrows():
        top_papers_rows.append({
            "cluster": c,
            "title": row.get("title", ""),
            "first_author": row.get("first_author", ""),
            "year": row["year"],
            "cited_by_count": row["cited_by_count"],
            "doi": row.get("doi", ""),
        })
top_papers_df = pd.DataFrame(top_papers_rows)
top_papers_df.to_csv(os.path.join(TABLES_DIR, "traditions_top_papers.csv"), index=False)
log.info(f"Saved {len(top_papers_df)} rows -> content/tables/traditions_top_papers.csv")

# Top terms per cluster (k=3)
terms_rows = []
for c in range(3):
    for rank, term in enumerate(all_top_terms[3][c]):
        terms_rows.append({"cluster": c, "rank": rank + 1, "term": term})
terms_df = pd.DataFrame(terms_rows)
terms_df.to_csv(os.path.join(TABLES_DIR, "traditions_top_terms.csv"), index=False)
log.info(f"Saved {len(terms_df)} rows -> content/tables/traditions_top_terms.csv")

log.info("\nDone.")
