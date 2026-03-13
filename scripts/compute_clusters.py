"""KMeans clustering, alluvial flow tables, and cluster labeling.

Reads:  refined_works.csv, refined_embeddings.npz
Writes: tab_alluvial.csv, cluster_labels.json, tab_core_shares.csv
        (all in TABLES_DIR; full corpus only for tab_core_shares.csv)

Flags:
  --core-only  Restrict to highly-cited papers (cited_by_count >= 50)
  --no-pdf     Accepted for interface compatibility; no-op (no figures generated)

Note: Period boundaries are hard-coded to the manuscript three-act structure
(2007, 2015). They are independent of the break detection in compute_breakpoints.py.

Downstream scripts:
  plot_fig_alluvial.py  →  tab_alluvial.csv, cluster_labels.json, tab_core_shares.csv
"""

import argparse
import json
import os
import re
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score

from utils import BASE_DIR, CATALOGS_DIR, load_refined_embeddings, normalize_doi

warnings.filterwarnings("ignore", category=FutureWarning)

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Args ---
parser = argparse.ArgumentParser(description="Compute alluvial tables and cluster labels")
parser.add_argument("--no-pdf", action="store_true", help="No-op (no figures generated here)")
parser.add_argument("--core-only", action="store_true",
                    help="Restrict to core papers (cited_by_count >= 50)")
# parse_known_args: silently ignore flags forwarded by compute_alluvial.py shim
args, _unknown = parser.parse_known_args()

# Output naming depends on mode
TAB_AL = "tab_alluvial_core.csv" if args.core_only else "tab_alluvial.csv"
LABEL_FILE = "cluster_labels_core.json" if args.core_only else "cluster_labels.json"


# ============================================================
# Step 1: Load data + embeddings
# Note: each split script (breakpoints, clusters, lexical) loads refined_works.csv
# independently. When run via the compute_alluvial.py shim this means 3× I/O,
# but at ~30K rows the cost is negligible vs. the KMeans/TF-IDF compute time.
# ============================================================

print("Loading unified works...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

has_title = works["title"].notna() & (works["title"].str.len() > 0)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
keep_mask = (has_title & in_range).values
df = works[keep_mask].copy().reset_index(drop=True)
print(f"Works with titles (1990-2025): {len(df)}")

print("Loading cached embeddings...")
all_embeddings = load_refined_embeddings()
if len(all_embeddings) != len(works):
    raise RuntimeError(
        f"Embedding/refined_works row count mismatch ({len(all_embeddings)} vs {len(works)}). "
        "Re-run: uv run python scripts/corpus_align.py"
    )
embeddings = all_embeddings[keep_mask]
print(f"Embedding shape: {embeddings.shape}")

CITE_THRESHOLD = 50
df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
if args.core_only:
    core_mask = df["cited_by_count"] >= CITE_THRESHOLD
    core_indices = df.index[core_mask].values
    df = df.loc[core_mask].reset_index(drop=True)
    embeddings = embeddings[core_indices]
    print(f"Core-only mode: {len(df)} papers (cited_by_count >= {CITE_THRESHOLD})")
    assert len(df) == len(embeddings), "Embedding alignment error after core filtering"


# ============================================================
# Step 2: Global KMeans clustering (k=6, fit once)
# ============================================================

K_DEFAULT = 6

print(f"\nFitting global KMeans (k={K_DEFAULT}) on full corpus...")
kmeans = KMeans(n_clusters=K_DEFAULT, random_state=42, n_init=20)
df["cluster"] = kmeans.fit_predict(embeddings)

print("\nCluster sizes:")
for c in range(K_DEFAULT):
    n = (df["cluster"] == c).sum()
    print(f"  Cluster {c}: {n}")


# ============================================================
# Step 3: ARI alignment check with Louvain communities
# ============================================================

cocit_path = os.path.join(CATALOGS_DIR, "communities.csv")
if os.path.exists(cocit_path):
    print("\n=== KMeans / Louvain alignment check ===")
    cocit = pd.read_csv(cocit_path)
    df["doi_norm"] = df["doi"].apply(normalize_doi)
    cocit["doi_norm"] = cocit["doi"].apply(normalize_doi)

    merged = df.merge(cocit[["doi_norm", "community"]], on="doi_norm", how="inner")
    n_overlap = len(merged)
    print(f"Papers in both KMeans and Louvain: n = {n_overlap}")

    if n_overlap >= 10:
        ari = adjusted_rand_score(merged["cluster"], merged["community"])
        print(f"Adjusted Rand Index: {ari:.3f}")
        if ari < 0.2:
            print("  → Weak alignment: semantic and citation communities capture different dimensions.")
        elif ari < 0.5:
            print("  → Moderate alignment: broad correspondence with notable divergences.")
        else:
            print("  → Strong alignment: embedding-based and citation-based structure converge.")
    else:
        print(f"  Too few overlapping papers ({n_overlap}) for meaningful ARI.")
else:
    print("\nWARNING: communities.csv not found, skipping ARI alignment check.")


# ============================================================
# Step 4: Segment into manuscript periods
# ============================================================

# Period boundaries are independent of break detection results.
# The three-act structure (2007, 2015) is fixed for the manuscript.
all_breaks = [2007, 2015]
boundaries = [1990] + all_breaks + [2026]
period_labels = []
for i in range(len(boundaries) - 1):
    lo = boundaries[i]
    hi = boundaries[i + 1] - 1
    if i == len(boundaries) - 2:
        hi = 2025
    period_labels.append(f"{lo}–{hi}")

print(f"\nPeriod boundaries: {all_breaks} (manuscript three-act structure)")
print(f"Period labels: {period_labels}")


def assign_period(year):
    for i in range(len(boundaries) - 1):
        lo = boundaries[i]
        hi = boundaries[i + 1]
        if lo <= year < hi:
            return period_labels[i]
    return period_labels[-1]


df["period"] = df["year"].apply(assign_period)


# ============================================================
# Step 5: Per-period cluster distributions
# ============================================================

alluvial_data = pd.crosstab(df["period"], df["cluster"])
alluvial_data = alluvial_data.reindex(period_labels)
alluvial_data.to_csv(os.path.join(TABLES_DIR, TAB_AL))
print(f"\nSaved alluvial table → tables/{TAB_AL}")
print("\nPeriod × Cluster distribution:")
print(alluvial_data)

if not args.core_only:
    core_mask_full = df["cited_by_count"] >= CITE_THRESHOLD
    core_crosstab = pd.crosstab(df.loc[core_mask_full, "period"],
                                df.loc[core_mask_full, "cluster"])
    core_crosstab = core_crosstab.reindex(period_labels, fill_value=0)
    for c in alluvial_data.columns:
        if c not in core_crosstab.columns:
            core_crosstab[c] = 0
    core_crosstab.to_csv(os.path.join(TABLES_DIR, "tab_core_shares.csv"))
    print("Saved core shares table → tables/tab_core_shares.csv")


# ============================================================
# Step 6: Label communities from abstract TF-IDF
# ============================================================

LABEL_STOPWORDS = {
    "climate", "climate change", "change", "finance", "financial", "carbon",
    "emission", "emissions", "mitigation", "adaptation",
    "paper", "study", "analysis", "results", "approach", "article", "research",
    "literature", "review", "data", "work", "based", "findings", "using",
    "new", "use", "used", "model", "evidence", "impact", "effects", "effect",
    "role", "case", "sector", "risk", "market", "markets", "investment",
    "countries", "country", "policy", "policies", "global", "world",
    "international", "national", "economic", "economics", "development",
    "blockchain", "esg", "theory", "usd",
    "pdf", "http", "https", "www", "vol", "pp",
}

ACRONYM_EXPANSIONS = {
    r"\benvironmental[,]?\s+social\s+(?:and\s+)?governance\b": "ESG",
    r"\bclean\s+development\s+mechanism\b": "CDM",
    r"\bemissions?\s+trading\s+(?:system|scheme)\b": "ETS",
    r"\bunited\s+nations\s+framework\s+convention\s+on\s+climate\s+change\b": "UNFCCC",
    r"\bconference\s+of\s+(?:the\s+)?parties\b": "COP",
    r"\bgreen\s+climate\s+fund\b": "GCF",
    r"\bsustainable\s+development\s+goals?\b": "SDGs",
    r"\bnationally\s+determined\s+contributions?\b": "NDCs",
}


def _collapse_acronyms(text):
    """Replace known expansions with their acronyms to avoid double-counting."""
    for pattern, acronym in ACRONYM_EXPANSIONS.items():
        text = re.sub(pattern, acronym, text, flags=re.IGNORECASE)
    return text


abstracts_for_tfidf = [_collapse_acronyms(a) for a in df["abstract"].fillna("").tolist()]
min_df_val = 3 if args.core_only else 5
label_vectorizer = TfidfVectorizer(
    ngram_range=(1, 2), max_features=8000, sublinear_tf=True,
    stop_words="english", min_df=min_df_val, max_df=0.8,
)
X_label = label_vectorizer.fit_transform(abstracts_for_tfidf)
label_features = np.array(label_vectorizer.get_feature_names_out())

corpus_mean = np.asarray(X_label.mean(axis=0)).flatten()

def _word_count(terms):
    return sum(len(t.split()) for t in terms)


cluster_labels = {}
for c in range(K_DEFAULT):
    c_mask = df["cluster"].values == c
    if c_mask.sum() == 0:
        cluster_labels[c] = f"Cluster {c}"
        continue
    c_mean = np.asarray(X_label[c_mask].mean(axis=0)).flatten()
    distinctiveness = c_mean - corpus_mean

    uni_candidates = []
    bi_candidates = []
    for i in np.argsort(distinctiveness)[::-1]:
        term = label_features[i]
        tokens = term.split()
        if any(t in LABEL_STOPWORDS for t in tokens):
            continue
        if distinctiveness[i] <= 0:
            break
        if " " in term:
            if len(bi_candidates) < 20:
                bi_candidates.append((term, float(distinctiveness[i])))
        else:
            if len(tokens[0]) < 3:
                continue
            if len(uni_candidates) < 30:
                uni_candidates.append((term, float(distinctiveness[i])))
        if len(uni_candidates) >= 30 and len(bi_candidates) >= 20:
            break
    candidates = bi_candidates + uni_candidates

    unigram_scores = {t: s for t, s in candidates if " " not in t}
    bigrams = [(t, s) for t, s in candidates if " " in t]
    promoted = set()
    for bigram, bi_score in bigrams:
        parts = bigram.split()
        best_uni = max((unigram_scores.get(p, 0) for p in parts), default=0)
        if best_uni > 0 and bi_score >= best_uni * 0.5:
            promoted.add(bigram)

    MAX_WORDS = 10

    scored = []
    used_tokens = set()
    for term, _ in candidates:
        if term not in promoted:
            continue
        if _word_count(scored) + len(term.split()) > MAX_WORDS:
            continue
        tokens = set(term.split())
        stems = {t.rstrip("s") for t in tokens}
        used_stems = {t.rstrip("s") for t in used_tokens}
        if stems.issubset(used_stems):
            continue
        scored.append(term)
        used_tokens.update(tokens)
        if _word_count(scored) >= MAX_WORDS:
            break
    for term, _ in candidates:
        if _word_count(scored) >= MAX_WORDS:
            break
        if " " in term and term not in promoted:
            continue
        if _word_count(scored) + len(term.split()) > MAX_WORDS:
            continue
        tokens = set(term.split())
        if tokens.issubset(used_tokens):
            continue
        stems = {t.rstrip("s") for t in tokens}
        used_stems = {t.rstrip("s") for t in used_tokens}
        if stems.issubset(used_stems):
            continue
        scored.append(term)
        used_tokens.update(tokens)

    bigram_dist = {}
    for idx_f, feat in enumerate(label_features):
        if " " in feat:
            bigram_dist[feat] = distinctiveness[idx_f]
    unigram_dist = {}
    for idx_f, feat in enumerate(label_features):
        if " " not in feat:
            unigram_dist[feat] = distinctiveness[idx_f]
    merged = True
    while merged:
        merged = False
        for i, a in enumerate(scored):
            if " " in a:
                continue
            for j, b in enumerate(scored):
                if j <= i or " " in b:
                    continue
                for bigram in (f"{a} {b}", f"{b} {a}"):
                    if bigram not in bigram_dist:
                        continue
                    weaker = min(unigram_dist.get(a, 0), unigram_dist.get(b, 0))
                    if bigram_dist[bigram] >= weaker:
                        scored[i] = bigram
                        scored.pop(j)
                        used_tokens.update(bigram.split())
                        merged = True
                        break
                if merged:
                    break
            if merged:
                break
    for term, _ in candidates:
        if _word_count(scored) >= MAX_WORDS:
            break
        if _word_count(scored) + len(term.split()) > MAX_WORDS:
            continue
        tokens = set(term.split())
        if tokens.issubset(used_tokens):
            continue
        stems = {t.rstrip("s") for t in tokens}
        used_stems = {t.rstrip("s") for t in used_tokens}
        if stems.issubset(used_stems):
            continue
        if " " in term and term not in promoted:
            continue
        scored.append(term)
        used_tokens.update(tokens)

    cluster_labels[c] = " / ".join(scored) if scored else f"Cluster {c}"

print("\nCluster labels:")
for c, label in cluster_labels.items():
    print(f"  {c}: {label}")

with open(os.path.join(TABLES_DIR, LABEL_FILE), "w") as f:
    json.dump({str(k): v for k, v in cluster_labels.items()}, f)
print(f"Saved cluster labels → tables/{LABEL_FILE}")

print("\nDone.")
