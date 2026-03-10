"""Detect intellectual traditions in pre-2007 climate finance literature (v3).

Hybrid approach combining:
  A) Seed-based tradition mapping: define seed papers from the manuscript's
     bibliography, trace their citation neighborhoods, compute centroids,
     classify all pre-2007 papers by nearest centroid.
  B) Spectral clustering on pre-2007 embeddings with k=3,4,5 as an
     unsupervised complement.

Informed by v1 (semantic KMeans, silhouette=0.065) and v2 (co-citation Louvain,
5 communities). The seed-based approach addresses the fact that the three
traditions posited by the paper don't separate in unsupervised embedding space.

Produces:
- content/tables/traditions_v3_seed_classification.csv
- content/tables/traditions_v3_seed_summary.csv
- content/tables/traditions_v3_seed_tfidf.csv
- content/tables/traditions_v3_spectral_summary.csv
"""

import os
import sys
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import SpectralClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_distances

# Add scripts dir to path for utils import
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_REPO = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(MAIN_REPO, "..", "..", "..", "..", "scripts"))
sys.path.insert(0, SCRIPT_DIR)

from utils import CATALOGS_DIR, normalize_doi, normalize_title

# --- Paths ---
BASE_DIR = MAIN_REPO
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npz")

# ============================================================
# SEED DEFINITIONS
# ============================================================
# Based on manuscript Section 1 bibliography.
# Each tradition has seed papers identified by DOI or title fragment.

TRADITION_SEEDS = {
    "Environmental economics": [
        # Ayres & Kneese 1969 - no DOI in corpus likely
        {"title_fragment": "production consumption externalities", "author": "ayres", "year": 1969},
        # Nordhaus 1992
        {"doi": "10.1126/science.258.5086.1315", "author": "nordhaus", "year": 1992},
        # Manne & Richels 1992
        {"doi": "10.1016/0301-4215(92)90024-v", "author": "manne", "year": 1992},
        # Stern 2007
        {"title_fragment": "economics of climate change", "author": "stern", "year": 2007},
        # Weitzman 2007
        {"doi": "10.1257/jel.45.3.703", "author": "weitzman", "year": 2007},
        # Weitzman 2009
        {"doi": "10.1162/rest.91.1.1", "author": "weitzman", "year": 2009},
        # Hourcade 2015 - dark matter
        {"doi": "10.1057/9781137446138_7", "author": "hourcade", "year": 2015},
        # Monasterolo 2020
        {"doi": "10.1146/annurev-resource-110119-031134", "author": "monasterolo", "year": 2020},
    ],
    "Development economics": [
        # Desrosieres 1998 - unlikely in corpus
        {"title_fragment": "politics of large numbers", "author": "desrosi", "year": 1998},
        # Michaelowa 2007
        {"doi": "10.1007/s10584-007-9270-3", "author": "michaelowa", "year": 2007},
        # Corfee-Morlot 2009
        {"doi": "10.1787/220062444715", "author": "corfee", "year": 2009},
        # Corfee-Morlot 2012
        {"doi": "10.1787/5k8zth7s6s6d-en", "author": "corfee", "year": 2012},
        # Buchner 2011
        {"doi": "10.1787/5k44zcqbbj42-en", "author": "buchner", "year": 2011},
        # Buchner 2013 / CPI Global Landscape
        {"title_fragment": "global landscape of climate finance", "author": "buchner", "year": 2013},
        # Caruso & Ellis 2013
        {"doi": "10.1787/5k44wj0s6fq2-en", "author": "caruso", "year": 2013},
        # Jachnik 2015
        {"doi": "10.1787/5js4x001rqf8-en", "author": "jachnik", "year": 2015},
        # Steckel 2016
        {"doi": "10.1002/wcc.437", "author": "steckel", "year": 2016},
    ],
    "Burden-sharing": [
        # Negishi 1960
        {"doi": "10.1111/j.1467-999x.1960.tb00275.x", "author": "negishi", "year": 1960},
        # Kaul 2003
        {"title_fragment": "providing global public goods", "author": "kaul", "year": 2003},
        # Kaul 2017
        {"doi": "10.1142/9789814641814_0007", "author": "kaul", "year": 2017},
        # Roberts & Weikmans 2017
        {"doi": "10.1007/s10784-016-9347-4", "author": "roberts", "year": 2017},
        # Roberts 2021
        {"doi": "10.1038/s41558-021-00990-2", "author": "roberts", "year": 2021},
        # Stadelmann 2011
        {"doi": "10.1080/17565529.2011.599550", "author": "stadelmann", "year": 2011},
        # Stadelmann 2013
        {"doi": "10.1080/14693062.2013.791146", "author": "stadelmann", "year": 2013},
        # Khan & Weikmans 2019
        {"doi": "10.1007/s10584-019-02563-x", "author": "khan", "year": 2019},
        # Pauw 2022
        {"doi": "10.1080/14693062.2022.2114985", "author": "pauw", "year": 2022},
        # Skovgaard 2017
        {"doi": "10.1007/s10784-016-9348-3", "author": "skovgaard", "year": 2017},
    ],
}


def match_seed(seed, works_df):
    """Find a seed paper in the corpus by DOI or title+author+year."""
    matches = []

    # Try DOI match first
    if "doi" in seed and seed["doi"]:
        doi_norm = normalize_doi(seed["doi"])
        mask = works_df["doi_norm"] == doi_norm
        if mask.any():
            matches = works_df.index[mask].tolist()

    # Fall back to title fragment + author + year
    if not matches and "title_fragment" in seed:
        frag = seed["title_fragment"].lower()
        author = seed.get("author", "").lower()
        year = seed.get("year")
        for idx, row in works_df.iterrows():
            t = normalize_title(str(row.get("title", "") or ""))
            fa = str(row.get("first_author", "") or "").lower()
            aa = str(row.get("all_authors", "") or "").lower()
            y = row.get("year")
            if frag in t:
                if author in fa or author in aa:
                    if year is None or (pd.notna(y) and abs(float(y) - year) < 2):
                        matches.append(idx)

    return matches


# ============================================================
# Load data
# ============================================================
print("=" * 70)
print("TRADITION DETECTION v3: Seed-based + Spectral clustering")
print("=" * 70)

print("\nLoading data...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")
works["doi_norm"] = works["doi"].apply(normalize_doi)
works["cited_by_count"] = pd.to_numeric(works["cited_by_count"], errors="coerce").fillna(0)

# Load embeddings (aligned with filtered works: abstract present + 1990-2025)
has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
emb_mask = has_abstract & in_range
emb_df = works[emb_mask].copy().reset_index(drop=True)

embeddings = np.load(EMBEDDINGS_PATH, allow_pickle=True)["vectors"]
assert len(embeddings) == len(emb_df), f"Embedding mismatch: {len(embeddings)} vs {len(emb_df)}"
print(f"Papers with embeddings: {len(emb_df)} ({embeddings.shape[1]}D)")

# Pre-2007 subset
pre2007_mask = emb_df["year"] <= 2006
pre2007_idx = emb_df.index[pre2007_mask].values
pre2007_df = emb_df.loc[pre2007_mask].copy().reset_index(drop=True)
pre2007_emb = embeddings[pre2007_idx]
print(f"Pre-2007 papers with embeddings: {len(pre2007_df)}")

# Load citations
print("Loading citations...")
cit = pd.read_csv(os.path.join(CATALOGS_DIR, "citations.csv"), low_memory=False)
cit["source_doi"] = cit["source_doi"].apply(normalize_doi)
cit["ref_doi"] = cit["ref_doi"].apply(normalize_doi)
cit = cit[(cit["source_doi"] != "") & (cit["ref_doi"] != "")]
cit = cit[~cit["source_doi"].isin(["nan", "none"])]
cit = cit[~cit["ref_doi"].isin(["nan", "none"])]
print(f"Citation pairs with DOIs: {len(cit)}")


# ============================================================
# PART A: SEED-BASED TRADITION MAPPING
# ============================================================
print("\n" + "=" * 70)
print("PART A: SEED-BASED TRADITION MAPPING")
print("=" * 70)

# Step 1: Look up seed papers in the corpus
print("\n--- Step 1: Matching seed papers in corpus ---")
seed_indices = {}  # tradition -> list of emb_df indices
seed_details = []

for tradition, seeds in TRADITION_SEEDS.items():
    matched = []
    for seed in seeds:
        # Match against emb_df (which has embeddings)
        hits = match_seed(seed, emb_df)
        label = seed.get("doi", seed.get("title_fragment", "?"))
        author = seed.get("author", "?")
        year = seed.get("year", "?")
        if hits:
            matched.extend(hits)
            for h in hits:
                row = emb_df.loc[h]
                seed_details.append({
                    "tradition": tradition,
                    "seed_label": f"{author} ({year})",
                    "matched_title": str(row["title"])[:80],
                    "doi": row["doi_norm"],
                    "year": row["year"],
                    "cited_by_count": row["cited_by_count"],
                })
            print(f"  [{tradition}] {author} ({year}): FOUND ({len(hits)} match(es))")
        else:
            print(f"  [{tradition}] {author} ({year}): NOT FOUND")

    seed_indices[tradition] = list(set(matched))

print(f"\nSeed papers found per tradition:")
for t, idx_list in seed_indices.items():
    print(f"  {t}: {len(idx_list)} papers")

# Step 2: Trace citation neighborhoods
print("\n--- Step 2: Citation neighborhoods ---")

# Build lookup: doi_norm -> emb_df index
doi_to_embidx = {}
for idx, row in emb_df.iterrows():
    d = row["doi_norm"]
    if d and d not in ("nan", "none", ""):
        doi_to_embidx[d] = idx

# For each tradition, find corpus papers that cite seed papers or are co-cited
tradition_neighborhoods = {}
for tradition, seed_idx_list in seed_indices.items():
    seed_dois = set()
    for idx in seed_idx_list:
        d = emb_df.loc[idx, "doi_norm"]
        if d and d not in ("nan", "none", ""):
            seed_dois.add(d)

    # Papers that cite any seed paper (seed appears as ref_doi)
    citers = set()
    if seed_dois:
        citing_mask = cit["ref_doi"].isin(seed_dois)
        citer_dois = set(cit.loc[citing_mask, "source_doi"].unique())
        for d in citer_dois:
            if d in doi_to_embidx:
                citers.add(doi_to_embidx[d])

    # Papers cited by seed papers (seed appears as source_doi)
    cited_by_seeds = set()
    if seed_dois:
        cited_mask = cit["source_doi"].isin(seed_dois)
        cited_dois = set(cit.loc[cited_mask, "ref_doi"].unique())
        for d in cited_dois:
            if d in doi_to_embidx:
                cited_by_seeds.add(doi_to_embidx[d])

    neighborhood = set(seed_idx_list) | citers | cited_by_seeds
    tradition_neighborhoods[tradition] = neighborhood
    print(f"  {tradition}: {len(seed_idx_list)} seeds + {len(citers)} citers + "
          f"{len(cited_by_seeds)} cited = {len(neighborhood)} total neighborhood")

# Step 3: Compute embedding centroids per tradition
print("\n--- Step 3: Tradition centroids ---")
tradition_centroids = {}
for tradition, neighborhood in tradition_neighborhoods.items():
    if not neighborhood:
        print(f"  {tradition}: EMPTY neighborhood, skipping centroid")
        continue
    idx_list = [i for i in neighborhood if i < len(embeddings)]
    if not idx_list:
        print(f"  {tradition}: No valid embedding indices, skipping")
        continue
    centroid = embeddings[idx_list].mean(axis=0)
    tradition_centroids[tradition] = centroid
    print(f"  {tradition}: centroid from {len(idx_list)} papers")

# Step 4: Classify all pre-2007 papers by nearest centroid
print("\n--- Step 4: Nearest-centroid classification (pre-2007) ---")

if len(tradition_centroids) < 2:
    print("WARNING: Fewer than 2 traditions have centroids. Cannot classify.")
    classified = False
else:
    classified = True
    tradition_names = list(tradition_centroids.keys())
    centroids_matrix = np.array([tradition_centroids[t] for t in tradition_names])

    # Compute cosine distances from each pre-2007 paper to each centroid
    distances = cosine_distances(pre2007_emb, centroids_matrix)  # (N, 3)

    # Assign to nearest
    assignments = distances.argmin(axis=1)
    min_distances = distances.min(axis=1)
    max_distances = distances.max(axis=1)

    # Compute "confidence": ratio of (2nd nearest - nearest) / nearest
    sorted_dists = np.sort(distances, axis=1)
    margin = sorted_dists[:, 1] - sorted_dists[:, 0]  # gap between closest and 2nd closest

    pre2007_df["tradition"] = [tradition_names[a] for a in assignments]
    pre2007_df["tradition_distance"] = min_distances
    pre2007_df["tradition_margin"] = margin

    # Orphan threshold: papers with very small margin (ambiguous)
    MARGIN_THRESHOLD = np.percentile(margin, 10)  # bottom 10% margin = orphans
    pre2007_df["is_orphan"] = margin < MARGIN_THRESHOLD

    print(f"\nClassification of {len(pre2007_df)} pre-2007 papers:")
    for t in tradition_names:
        mask = pre2007_df["tradition"] == t
        n = mask.sum()
        non_orphan = (mask & ~pre2007_df["is_orphan"]).sum()
        print(f"  {t}: {n} total ({non_orphan} confident, "
              f"{(mask & pre2007_df['is_orphan']).sum()} ambiguous)")

    n_orphan = pre2007_df["is_orphan"].sum()
    print(f"\n  Ambiguous (margin < {MARGIN_THRESHOLD:.4f}): {n_orphan} papers "
          f"({100*n_orphan/len(pre2007_df):.1f}%)")

    # Step 5: Top papers per tradition
    print("\n--- Step 5: Top papers per tradition (by citation count) ---")
    for t in tradition_names:
        mask = pre2007_df["tradition"] == t
        subset = pre2007_df[mask].nlargest(8, "cited_by_count")
        print(f"\n  {t} — Top 8:")
        for _, row in subset.iterrows():
            title_short = str(row.get("title", "") or "")[:65]
            print(f"    [{int(row['cited_by_count']):5d}] {str(row.get('first_author',''))[:20]:20s} "
                  f"({int(row['year'])}) {title_short}")

    # Step 6: Characteristic TF-IDF terms per tradition
    print("\n--- Step 6: Characteristic terms (TF-IDF) per tradition ---")
    tfidf_rows = []
    # Build TF-IDF on pre-2007 abstracts
    abstracts = pre2007_df["abstract"].fillna("").tolist()
    vectorizer = TfidfVectorizer(
        max_features=5000, stop_words="english", ngram_range=(1, 2),
        min_df=3, max_df=0.5
    )
    tfidf_matrix = vectorizer.fit_transform(abstracts)
    feature_names = vectorizer.get_feature_names_out()

    for t in tradition_names:
        mask = (pre2007_df["tradition"] == t).values
        if mask.sum() == 0:
            continue
        # Mean TF-IDF for this tradition vs. rest
        mean_t = tfidf_matrix[mask].mean(axis=0).A1
        mean_rest = tfidf_matrix[~mask].mean(axis=0).A1
        diff = mean_t - mean_rest
        top_idx = diff.argsort()[-15:][::-1]
        terms = [(feature_names[i], diff[i]) for i in top_idx]
        print(f"\n  {t}:")
        for term, score in terms:
            print(f"    {term:30s} {score:.4f}")
            tfidf_rows.append({"tradition": t, "term": term, "diff_score": round(score, 5)})

    # Step 7: Overlap analysis
    print("\n--- Step 7: Overlap between traditions ---")
    # Look at papers that are within 10% margin of being in another tradition
    close_margin = np.percentile(margin, 25)
    for t in tradition_names:
        mask = pre2007_df["tradition"] == t
        close = (mask & (pre2007_df["tradition_margin"] < close_margin)).sum()
        print(f"  {t}: {close} papers ({100*close/mask.sum():.0f}%) "
              f"within margin < {close_margin:.4f} of another tradition")

    # Inter-centroid distances
    print("\n  Inter-centroid cosine distances:")
    for i in range(len(tradition_names)):
        for j in range(i + 1, len(tradition_names)):
            d = cosine_distances(
                centroids_matrix[i:i+1], centroids_matrix[j:j+1]
            )[0, 0]
            print(f"    {tradition_names[i]} <-> {tradition_names[j]}: {d:.4f}")

    # Save outputs
    print("\n--- Saving seed-based results ---")

    # Classification CSV
    out_cols = ["doi_norm", "title", "first_author", "year", "cited_by_count",
                "tradition", "tradition_distance", "tradition_margin", "is_orphan"]
    save_path = os.path.join(TABLES_DIR, "traditions_v3_seed_classification.csv")
    pre2007_df[out_cols].to_csv(save_path, index=False)
    print(f"  Saved {len(pre2007_df)} rows -> {save_path}")

    # Summary CSV
    summary_rows = []
    for t in tradition_names:
        mask = pre2007_df["tradition"] == t
        subset = pre2007_df[mask]
        summary_rows.append({
            "tradition": t,
            "n_papers": len(subset),
            "n_confident": (~subset["is_orphan"]).sum(),
            "n_ambiguous": subset["is_orphan"].sum(),
            "mean_distance": subset["tradition_distance"].mean(),
            "median_citations": subset["cited_by_count"].median(),
            "n_seeds_found": len(seed_indices.get(t, [])),
            "n_neighborhood": len(tradition_neighborhoods.get(t, set())),
        })
    summary_df = pd.DataFrame(summary_rows)
    save_path = os.path.join(TABLES_DIR, "traditions_v3_seed_summary.csv")
    summary_df.to_csv(save_path, index=False)
    print(f"  Saved summary -> {save_path}")

    # TF-IDF terms CSV
    tfidf_df = pd.DataFrame(tfidf_rows)
    save_path = os.path.join(TABLES_DIR, "traditions_v3_seed_tfidf.csv")
    tfidf_df.to_csv(save_path, index=False)
    print(f"  Saved TF-IDF terms -> {save_path}")


# ============================================================
# PART B: SPECTRAL CLUSTERING
# ============================================================
print("\n" + "=" * 70)
print("PART B: SPECTRAL CLUSTERING (pre-2007 embeddings)")
print("=" * 70)

print(f"\nPre-2007 papers: {len(pre2007_df)} with {pre2007_emb.shape[1]}D embeddings")

spectral_results = []
for k in [3, 4, 5]:
    print(f"\n--- k={k} ---")
    sc = SpectralClustering(
        n_clusters=k, affinity="rbf", gamma=1.0,
        random_state=42, n_init=10, assign_labels="kmeans"
    )
    labels = sc.fit_predict(pre2007_emb)

    sil = silhouette_score(pre2007_emb, labels, metric="cosine", sample_size=min(5000, len(labels)))
    print(f"  Silhouette (cosine): {sil:.4f}")

    # Cluster sizes
    counts = Counter(labels)
    for c in sorted(counts):
        print(f"  Cluster {c}: {counts[c]} papers")

    # Top papers per cluster
    pre2007_df[f"spectral_k{k}"] = labels
    for c in sorted(counts):
        mask = labels == c
        subset = pre2007_df[mask].nlargest(5, "cited_by_count")
        print(f"\n  Cluster {c} top 5:")
        for _, row in subset.iterrows():
            title_short = str(row.get("title", "") or "")[:60]
            print(f"    [{int(row['cited_by_count']):5d}] {str(row.get('first_author',''))[:18]:18s} "
                  f"({int(row['year'])}) {title_short}")

    # Characteristic terms
    print(f"\n  Characteristic terms per cluster (k={k}):")
    for c in sorted(counts):
        mask_c = (labels == c)
        if mask_c.sum() == 0:
            continue
        mean_c = tfidf_matrix[mask_c].mean(axis=0).A1
        mean_rest = tfidf_matrix[~mask_c].mean(axis=0).A1
        diff = mean_c - mean_rest
        top_idx = diff.argsort()[-8:][::-1]
        terms = [feature_names[i] for i in top_idx]
        print(f"    Cluster {c}: {', '.join(terms)}")

    spectral_results.append({
        "k": k,
        "silhouette_cosine": round(sil, 4),
        "cluster_sizes": str(dict(sorted(counts.items()))),
    })

    # Cross-tabulation with seed traditions (if available)
    if classified:
        ct = pd.crosstab(pre2007_df["tradition"], pre2007_df[f"spectral_k{k}"])
        print(f"\n  Cross-tabulation (seed tradition x spectral k={k}):")
        print(ct.to_string())

# Save spectral summary
spectral_df = pd.DataFrame(spectral_results)
save_path = os.path.join(TABLES_DIR, "traditions_v3_spectral_summary.csv")
spectral_df.to_csv(save_path, index=False)
print(f"\n  Saved spectral summary -> {save_path}")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if classified:
    print("\nSeed-based approach:")
    for t in tradition_names:
        mask = pre2007_df["tradition"] == t
        n = mask.sum()
        pct = 100 * n / len(pre2007_df)
        print(f"  {t}: {n} papers ({pct:.1f}%)")
    print(f"  Ambiguous (bottom 10% margin): {pre2007_df['is_orphan'].sum()} papers")

print("\nSpectral clustering silhouettes:")
for r in spectral_results:
    print(f"  k={r['k']}: silhouette={r['silhouette_cosine']}")

print("\nDone.")
