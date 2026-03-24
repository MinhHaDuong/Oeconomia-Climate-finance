"""
Analyze interactions between time, semantic, lexical, and citation clustering spaces.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sklearn.preprocessing import normalize
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer

SEED = 42
K = 6
SAMPLE_SIZE = 3000
DATA_DIR = "data/catalogs"


def load_data():
    print("Loading data...")
    works = pd.read_csv(f"{DATA_DIR}/refined_works.csv")
    embeddings = np.load(f"{DATA_DIR}/refined_embeddings.npz")["vectors"]
    citations = pd.read_csv(f"{DATA_DIR}/refined_citations.csv", usecols=["source_doi", "ref_doi"])
    print(f"  Works: {len(works)}, Embeddings: {embeddings.shape}, Citations: {len(citations)}")
    return works, embeddings, citations


def filter_works(works, embeddings):
    """Filter works: has title, year in [1990, 2024]. Return filtered works + aligned embeddings."""
    mask = (
        works["title"].notna() &
        works["year"].between(1990, 2024)
    )
    filtered_works = works[mask].reset_index(drop=True)
    filtered_embeddings = embeddings[mask]
    print(f"  Filtered to {len(filtered_works)} works (year 1990-2024, has title)")
    return filtered_works, filtered_embeddings, mask


def get_window_mask(works, year_start, year_end):
    return works["year"].between(year_start, year_end)


def build_lexical_vectors(works_window, max_features=5000):
    """Build TF-IDF matrix from keywords + title."""
    texts = []
    for _, row in works_window.iterrows():
        parts = []
        if pd.notna(row.get("keywords")) and row["keywords"]:
            parts.append(str(row["keywords"]))
        if pd.notna(row.get("title")) and row["title"]:
            parts.append(str(row["title"]))
        texts.append(" ".join(parts))
    vectorizer = TfidfVectorizer(max_features=max_features, min_df=2, sublinear_tf=True)
    try:
        X = vectorizer.fit_transform(texts)
        return X
    except Exception:
        return None


def build_citation_coupling_vectors(works_window, citations, n_components=50):
    """
    Build bibliographic coupling vectors for works in window.
    Entry (i, j) = 1 if work_i cites ref_j.
    Then SVD to 50D, L2 normalize.
    """
    dois_in_window = set(works_window["doi"].dropna().tolist())
    # Filter citations where source is in window
    mask_src = citations["source_doi"].isin(dois_in_window)
    cites_window = citations[mask_src].copy()

    if len(cites_window) == 0:
        return None, None

    # Build index
    doi_to_idx = {doi: i for i, doi in enumerate(works_window["doi"].fillna("").tolist())}
    ref_dois = cites_window["ref_doi"].dropna().unique().tolist()
    ref_to_idx = {r: i for i, r in enumerate(ref_dois)}

    rows, cols = [], []
    for _, row in cites_window.iterrows():
        if row["source_doi"] in doi_to_idx and pd.notna(row["ref_doi"]) and row["ref_doi"] in ref_to_idx:
            rows.append(doi_to_idx[row["source_doi"]])
            cols.append(ref_to_idx[row["ref_doi"]])

    if len(rows) == 0:
        return None, None

    n_works = len(works_window)
    n_refs = len(ref_dois)
    mat = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n_works, n_refs))

    # SVD
    k = min(n_components, min(mat.shape) - 1)
    if k < 2:
        return None, None

    try:
        U, s, Vt = svds(mat.astype(float), k=k)
        # Weight by singular values
        vectors = U * s[np.newaxis, :]
        # L2 normalize
        norms = np.linalg.norm(vectors, axis=1)
        nonzero = norms > 0
        vectors_norm = np.zeros_like(vectors)
        vectors_norm[nonzero] = vectors[nonzero] / norms[nonzero, np.newaxis]
        return vectors_norm, nonzero
    except Exception as e:
        print(f"    SVD failed: {e}")
        return None, None


def kmeans_labels(X, k=K, seed=SEED):
    """Fit KMeans, return labels."""
    km = KMeans(n_clusters=k, random_state=seed, n_init=10)
    if hasattr(X, "toarray"):
        km.fit(X)
    else:
        km.fit(X)
    return km.labels_


def compute_silhouette(X, labels, sample_size=SAMPLE_SIZE, seed=SEED):
    """Compute silhouette score with sampling."""
    n = X.shape[0] if hasattr(X, "shape") else len(X)
    if n < 20:
        return float("nan")
    sample_size = min(sample_size, n)
    rng = np.random.RandomState(seed)
    idx = rng.choice(n, size=sample_size, replace=False)
    if hasattr(X, "toarray"):
        X_sample = X[idx].toarray()
    else:
        X_sample = X[idx]
    labels_sample = labels[idx]
    if len(np.unique(labels_sample)) < 2:
        return float("nan")
    return silhouette_score(X_sample, labels_sample)


def print_separator(char="=", width=70):
    print(char * width)


# ──────────────────────────────────────────────────────────────────────────────
# Main analysis
# ──────────────────────────────────────────────────────────────────────────────

def main():
    works, embeddings, citations = load_data()
    works, embeddings, _ = filter_works(works, embeddings)

    windows = [
        (2000, 2004),
        (2005, 2009),
        (2010, 2014),
        (2015, 2019),
        (2020, 2024),
    ]

    print_separator()
    print("Q1: CROSS-SPACE AGREEMENT OVER TIME (ARI, k=6)")
    print_separator()
    print(f"{'Window':<12} {'N':>6} {'ARI sem↔lex':>12} {'ARI sem↔cit':>12} {'ARI lex↔cit':>12}")
    print("-" * 60)

    q1_results = []
    for (y0, y1) in windows:
        wmask = get_window_mask(works, y0, y1)
        w = works[wmask].reset_index(drop=True)
        emb = embeddings[wmask.values]
        n = len(w)

        if n < 30:
            print(f"{y0}-{y1:<4}   {n:>6}  (too few works)")
            continue

        # --- Semantic labels ---
        sem_labels = kmeans_labels(emb, K)

        # --- Lexical labels ---
        lex_mat = build_lexical_vectors(w)
        if lex_mat is not None and lex_mat.shape[1] >= K:
            lex_labels = kmeans_labels(lex_mat, K)
        else:
            lex_labels = None

        # --- Citation labels ---
        cit_vecs, cit_nonzero = build_citation_coupling_vectors(w, citations)
        if cit_vecs is not None:
            cit_labels_full = np.full(n, -1, dtype=int)
            cit_labels_km = kmeans_labels(cit_vecs[cit_nonzero], K)
            cit_labels_full[cit_nonzero] = cit_labels_km
        else:
            cit_labels_full = None

        # --- ARI computations (on shared/valid works) ---
        def ari_pair(labels_a, labels_b):
            if labels_a is None or labels_b is None:
                return float("nan")
            # Only works where both are valid (citation might have -1)
            mask_valid = (labels_a >= 0) & (labels_b >= 0)
            if mask_valid.sum() < 20:
                return float("nan")
            return adjusted_rand_score(labels_a[mask_valid], labels_b[mask_valid])

        a_sl = ari_pair(sem_labels, lex_labels)
        a_sc = ari_pair(sem_labels, cit_labels_full)
        a_lc = ari_pair(lex_labels, cit_labels_full)

        def fmt(v):
            return f"{v:>12.4f}" if not np.isnan(v) else f"{'n/a':>12}"

        print(f"{y0}-{y1:<4}   {n:>6} {fmt(a_sl)} {fmt(a_sc)} {fmt(a_lc)}")
        q1_results.append(dict(window=f"{y0}-{y1}", n=n, ari_sem_lex=a_sl, ari_sem_cit=a_sc, ari_lex_cit=a_lc))

    # Trend summary
    print()
    print("Trend summary:")
    if len(q1_results) >= 2:
        for col in ["ari_sem_lex", "ari_sem_cit", "ari_lex_cit"]:
            vals = [r[col] for r in q1_results if not np.isnan(r[col])]
            if len(vals) >= 2:
                trend = "INCREASING" if vals[-1] > vals[0] else "DECREASING"
                print(f"  {col}: {vals[0]:.4f} → {vals[-1]:.4f}  ({trend})")

    # ──────────────────────────────────────────────────────────────────────────
    print()
    print_separator()
    print("Q2: CITATION SPACE STRUCTURE IN 2001-2005 (cluster characterization)")
    print_separator()

    wmask_q2 = get_window_mask(works, 2001, 2005)
    w_q2 = works[wmask_q2].reset_index(drop=True)
    print(f"Works in 2001-2005: {len(w_q2)}")

    cit_vecs_q2, cit_nonzero_q2 = build_citation_coupling_vectors(w_q2, citations)
    if cit_vecs_q2 is not None:
        n_valid = cit_nonzero_q2.sum()
        print(f"Works with citation vectors: {n_valid}")

        w_valid = w_q2[cit_nonzero_q2].reset_index(drop=True)
        vecs_valid = cit_vecs_q2[cit_nonzero_q2]

        # Silhouette
        sil_q2 = compute_silhouette(vecs_valid, kmeans_labels(vecs_valid, K))
        print(f"Silhouette (k={K}): {sil_q2:.4f}")

        # KMeans k=6
        km_labels = kmeans_labels(vecs_valid, K)
        w_valid = w_valid.copy()
        w_valid["cluster"] = km_labels

        print(f"\nCluster characterization (k={K}):")
        print("-" * 70)
        for c in range(K):
            sub = w_valid[w_valid["cluster"] == c]
            n_c = len(sub)
            med_year = sub["year"].median()
            mean_cbc = sub["cited_by_count"].mean() if "cited_by_count" in sub.columns else float("nan")

            # Top keywords
            kw_text = " ; ".join(sub["keywords"].dropna().astype(str).tolist())
            # Count keyword frequencies
            from collections import Counter
            kw_list = [k.strip().lower() for k in kw_text.split(";") if k.strip() and len(k.strip()) > 2]
            kw_counts = Counter(kw_list).most_common(8)
            top_kw = ", ".join([f"{k}({v})" for k, v in kw_counts[:5]])

            print(f"\n  Cluster {c} (n={n_c}, med_year={med_year:.0f}, mean_cited={mean_cbc:.1f}):")
            print(f"  Top keywords: {top_kw}")
            # Top titles
            top_titles = sub.sort_values("cited_by_count", ascending=False)["title"].head(3).tolist()
            for t in top_titles:
                print(f"    - {str(t)[:80]}")
    else:
        print("  Could not build citation vectors for 2001-2005")

    # ──────────────────────────────────────────────────────────────────────────
    print()
    print_separator()
    print("Q3: LANGUAGE AS A STRUCTURING VARIABLE")
    print_separator()

    print(f"\n{'Window':<12} {'N_total':>8} {'Pct_nonEN':>10} {'Sil_all':>10} {'N_EN':>8} {'Sil_EN':>10}")
    print("-" * 65)

    for (y0, y1) in windows:
        wmask = get_window_mask(works, y0, y1)
        w = works[wmask].reset_index(drop=True)
        emb = embeddings[wmask.values]
        n = len(w)

        if n < 30:
            continue

        en_mask = w["language"] == "en"
        pct_nonen = 100.0 * (~en_mask).sum() / n

        # Silhouette k=6, all works
        sem_labels_all = kmeans_labels(emb, K)
        sil_all = compute_silhouette(emb, sem_labels_all)

        # Silhouette k=6, English only
        emb_en = emb[en_mask.values]
        n_en = en_mask.sum()
        if n_en >= 30:
            sem_labels_en = kmeans_labels(emb_en, K)
            sil_en = compute_silhouette(emb_en, sem_labels_en)
        else:
            sil_en = float("nan")

        def fmt(v):
            return f"{v:>10.4f}" if not np.isnan(v) else f"{'n/a':>10}"

        print(f"{y0}-{y1:<4}   {n:>8} {pct_nonen:>10.1f} {fmt(sil_all)} {n_en:>8} {fmt(sil_en)}")

    # k=2 silhouette: semantic space, English vs non-English
    print("\nk=2 semantic silhouette (EN vs non-EN):")
    print(f"{'Window':<12} {'N':>6} {'Sil_k2':>10}")
    print("-" * 35)
    for (y0, y1) in windows:
        wmask = get_window_mask(works, y0, y1)
        w = works[wmask].reset_index(drop=True)
        emb = embeddings[wmask.values]
        n = len(w)
        if n < 30:
            continue
        en_mask = (w["language"] == "en").values.astype(int)
        if len(np.unique(en_mask)) < 2:
            print(f"{y0}-{y1:<4}   {n:>6} {'n/a':>10}")
            continue
        sil_k2 = compute_silhouette(emb, en_mask)
        print(f"{y0}-{y1:<4}   {n:>6} {sil_k2:>10.4f}")

    # ──────────────────────────────────────────────────────────────────────────
    print()
    print_separator()
    print("Q4: CORE vs FULL STRUCTURE (semantic silhouette, k=6)")
    print_separator()

    CORE_THRESHOLD = 50
    print(f"\nCore = cited_by_count >= {CORE_THRESHOLD}")
    print(f"\n{'Window':<12} {'N_all':>7} {'Sil_all':>10} {'N_core':>8} {'Sil_core':>10}")
    print("-" * 55)

    for (y0, y1) in windows:
        wmask = get_window_mask(works, y0, y1)
        w = works[wmask].reset_index(drop=True)
        emb = embeddings[wmask.values]
        n = len(w)

        if n < 30:
            continue

        # All
        sem_labels_all = kmeans_labels(emb, K)
        sil_all = compute_silhouette(emb, sem_labels_all)

        # Core
        core_mask = w["cited_by_count"] >= CORE_THRESHOLD
        emb_core = emb[core_mask.values]
        n_core = core_mask.sum()
        if n_core >= 30:
            sem_labels_core = kmeans_labels(emb_core, K)
            sil_core = compute_silhouette(emb_core, sem_labels_core)
        else:
            sil_core = float("nan")

        def fmt(v):
            return f"{v:>10.4f}" if not np.isnan(v) else f"{'n/a':>10}"

        print(f"{y0}-{y1:<4}   {n:>7} {fmt(sil_all)} {n_core:>8} {fmt(sil_core)}")

    print()
    print_separator("=")
    print("Analysis complete.")
    print_separator("=")


if __name__ == "__main__":
    main()
