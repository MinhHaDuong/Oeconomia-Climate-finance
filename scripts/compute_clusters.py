"""KMeans clustering, alluvial flow tables, and cluster labeling.

Reads:  refined_works.csv, refined_embeddings.npz
Writes: tab_alluvial.csv, cluster_labels.json, tab_core_shares.csv
        (all in TABLES_DIR; full corpus only for tab_core_shares.csv)

Flags:
  --core-only  Restrict to highly-cited papers (cited_by_count >= 50)

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
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    get_logger,
    load_analysis_config,
    load_analysis_corpus,
    normalize_doi,
)

log = get_logger("compute_clusters")

warnings.filterwarnings("ignore", category=FutureWarning)

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Args ---
parser = argparse.ArgumentParser(description="Compute alluvial tables and cluster labels")
parser.add_argument("--core-only", action="store_true",
                    help="Restrict to core papers (cited_by_count >= 50)")
parser.add_argument("--breaks", type=str, default=None,
                    help="Comma-separated period break years (default: from config/analysis.yaml)")
parser.add_argument("--v1-only", action="store_true",
                    help="Restrict to v1.0-submission corpus (in_v1==1)")
args = parser.parse_args()

# Output naming depends on mode
if args.core_only:
    _suffix = "_core"
elif args.v1_only:
    _suffix = "_v1"
else:
    _suffix = ""
TAB_AL = f"tab_alluvial{_suffix}.csv"
LABEL_FILE = f"cluster_labels{_suffix}.json"


# ============================================================
# Step 1: Load data + embeddings
# ============================================================

df, embeddings = load_analysis_corpus(core_only=args.core_only,
                                      v1_only=args.v1_only)
log.info("Loaded %d works, embeddings shape: %s", len(df), embeddings.shape)


# ============================================================
# Step 2: Global KMeans clustering (k=6, fit once)
# ============================================================

K_DEFAULT = 6
_cfg = load_analysis_config()
CITE_THRESHOLD = _cfg["clustering"]["cite_threshold"]

V1_CENTROIDS_PATH = os.path.join(BASE_DIR, "config", "v1_cluster_centroids.npy")

if args.v1_only and os.path.exists(V1_CENTROIDS_PATH):
    # Seed with reference centroids so cluster IDs stay consistent
    # with the v1.0-submission figures (no post-hoc remapping needed)
    ref_centroids = np.load(V1_CENTROIDS_PATH)
    log.info("Fitting KMeans (k=%d) seeded with v1 reference centroids...", K_DEFAULT)
    kmeans = KMeans(n_clusters=K_DEFAULT, init=ref_centroids, n_init=1)
else:
    log.info("Fitting global KMeans (k=%d)...", K_DEFAULT)
    kmeans = KMeans(n_clusters=K_DEFAULT, random_state=42, n_init=20)
df["cluster"] = kmeans.fit_predict(embeddings)

log.info("Cluster sizes:")
for c in range(K_DEFAULT):
    n = (df["cluster"] == c).sum()
    log.info("  Cluster %d: %d", c, n)


# ============================================================
# Step 3: ARI alignment check with Louvain communities
# ============================================================

cocit_path = os.path.join(CATALOGS_DIR, "communities.csv")
if os.path.exists(cocit_path):
    log.info("=== KMeans / Louvain alignment check ===")
    cocit = pd.read_csv(cocit_path)
    df["doi_norm"] = df["doi"].apply(normalize_doi)
    cocit["doi_norm"] = cocit["doi"].apply(normalize_doi)

    merged = df.merge(cocit[["doi_norm", "community"]], on="doi_norm", how="inner")
    n_overlap = len(merged)
    log.info("Papers in both KMeans and Louvain: n = %d", n_overlap)

    if n_overlap >= 10:
        ari = adjusted_rand_score(merged["cluster"], merged["community"])
        log.info("Adjusted Rand Index: %.3f", ari)
        if ari < 0.2:
            log.info("  -> Weak alignment: semantic and citation communities capture different dimensions.")
        elif ari < 0.5:
            log.info("  -> Moderate alignment: broad correspondence with notable divergences.")
        else:
            log.info("  -> Strong alignment: embedding-based and citation-based structure converge.")
    else:
        log.info("  Too few overlapping papers (%d) for meaningful ARI.", n_overlap)
else:
    log.warning("communities.csv not found, skipping ARI alignment check.")


# ============================================================
# Step 4: Segment into manuscript periods
# ============================================================

# Period boundaries: from --breaks CLI or config/analysis.yaml
_p_cfg = _cfg["periodization"]
if args.breaks:
    all_breaks = [int(y.strip()) for y in args.breaks.split(",")]
else:
    all_breaks = _p_cfg["breaks"]
boundaries = [_p_cfg["year_min"]] + all_breaks + [_p_cfg["year_max"] + 1]
period_labels = []
for i in range(len(boundaries) - 1):
    lo = boundaries[i]
    hi = boundaries[i + 1] - 1
    period_labels.append(f"{lo}\u2013{hi}")

log.info("Period boundaries: %s (manuscript three-act structure)", all_breaks)
log.info("Period labels: %s", period_labels)


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
log.info("Saved alluvial table -> tables/%s", TAB_AL)
log.info("Period x Cluster distribution:\n%s", alluvial_data)

if not args.core_only:
    core_mask_full = df["cited_by_count"] >= CITE_THRESHOLD
    core_crosstab = pd.crosstab(df.loc[core_mask_full, "period"],
                                df.loc[core_mask_full, "cluster"])
    core_crosstab = core_crosstab.reindex(period_labels, fill_value=0)
    for c in alluvial_data.columns:
        if c not in core_crosstab.columns:
            core_crosstab[c] = 0
    core_shares_file = f"tab_core_shares{_suffix}.csv"
    core_crosstab.to_csv(os.path.join(TABLES_DIR, core_shares_file))
    log.info("Saved core shares table -> tables/%s", core_shares_file)


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

log.info("Cluster labels:")
for c, label in cluster_labels.items():
    log.info("  %s: %s", c, label)

with open(os.path.join(TABLES_DIR, LABEL_FILE), "w") as f:
    json.dump({str(k): v for k, v in cluster_labels.items()}, f)
log.info("Saved cluster labels -> tables/%s", LABEL_FILE)

log.info("Done.")
