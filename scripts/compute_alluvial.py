"""Endogenous structural break detection: compute alluvial tables and cluster labels.

Reads:  refined_works.csv, refined_embeddings.npz
Writes: tab_breakpoints.csv, tab_breakpoint_robustness.csv,
        tab_alluvial.csv, cluster_labels.json,
        tab_core_shares.csv (full corpus only: core paper counts per period/cluster),
        tab_lexical_tfidf.csv (full corpus only),
        tab_k_sensitivity.csv + fig_k_sensitivity.png (--robustness only)

Flags: --core-only, --censor-gap N, --robustness, --no-pdf

Downstream scripts read these outputs:
  plot_fig_breakpoints.py  →  tab_breakpoints.csv, tab_breakpoint_robustness.csv, tab_alluvial.csv
  plot_fig_alluvial.py     →  tab_alluvial.csv, cluster_labels.json, tab_core_shares.csv
"""

import argparse
import json
import os
import re
import warnings
from collections import Counter

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
from scipy.spatial.distance import cosine as cosine_dist
from scipy.stats import pearsonr
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score

from utils import BASE_DIR, CATALOGS_DIR, load_refined_embeddings, normalize_doi, save_figure

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

# COP events (needed for the k-sensitivity figure in --robustness mode)
COP_EVENTS = {
    1992: "Rio",
    1997: "Kyoto",
    2009: "Copenhagen",
    2010: "Cancún",
    2015: "Paris",
    2021: "Glasgow",
    2024: "Baku",
}

# --- Args ---
parser = argparse.ArgumentParser(description="Compute alluvial tables and cluster labels")
parser.add_argument("--robustness", action="store_true", help="Run k-sensitivity analysis")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
parser.add_argument("--core-only", action="store_true",
                    help="Restrict to core papers (cited_by_count >= 50)")
parser.add_argument("--censor-gap", type=int, default=0,
                    help="Number of transition years to censor before each test point (default: 0)")
args = parser.parse_args()

# Output naming depends on mode
if args.core_only:
    FIG_BP = "fig_breakpoints_core"
    FIG_AL = "fig_alluvial_core"
    TAB_BP = "tab_breakpoints_core.csv"
    TAB_BP_ROBUST = "tab_breakpoint_robustness_core.csv"
    TAB_AL = "tab_alluvial_core.csv"
    LABEL_FILE = "cluster_labels_core.json"
else:
    FIG_BP = "fig_breakpoints"
    FIG_AL = "fig_alluvial"
    TAB_BP = "tab_breakpoints.csv"
    TAB_BP_ROBUST = "tab_breakpoint_robustness.csv"
    TAB_AL = "tab_alluvial.csv"
    LABEL_FILE = "cluster_labels.json"

if args.censor_gap > 0:
    suffix = f"_censor{args.censor_gap}"
    FIG_BP += suffix
    TAB_BP = TAB_BP.replace(".csv", f"{suffix}.csv")
    TAB_BP_ROBUST = TAB_BP_ROBUST.replace(".csv", f"{suffix}.csv")


# ============================================================
# Step 0: Load data + embeddings
# ============================================================

print("Loading unified works...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

# Filter: must have title, year in range (matches embedding generation)
has_title = works["title"].notna() & (works["title"].str.len() > 0)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_title & in_range].copy().reset_index(drop=True)
print(f"Works with titles (1990-2025): {len(df)}")

print("Loading cached embeddings...")
embeddings = load_refined_embeddings()
if len(embeddings) != len(df):
    raise RuntimeError(
        f"Embedding cache size mismatch ({len(embeddings)} vs {len(df)}). "
        "Re-run analyze_embeddings.py first."
    )
print(f"Embedding shape: {embeddings.shape}")

# Core filtering: keep only highly-cited papers
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
# Step 1: Global KMeans clustering (k=6, fit once)
# ============================================================

K_DEFAULT = 6
N_MIN = 20 if args.core_only else 30  # Lower threshold for smaller core corpus

print(f"\nFitting global KMeans (k={K_DEFAULT}) on full corpus...")
kmeans = KMeans(n_clusters=K_DEFAULT, random_state=42, n_init=20)
df["cluster"] = kmeans.fit_predict(embeddings)

# Cluster sizes
print("\nCluster sizes:")
for c in range(K_DEFAULT):
    n = (df["cluster"] == c).sum()
    print(f"  Cluster {c}: {n}")


# ============================================================
# Step 1b: ARI alignment check with Louvain communities
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
            print("    Both figures show complementary structure.")
        elif ari < 0.5:
            print("  → Moderate alignment: broad correspondence with notable divergences.")
        else:
            print("  → Strong alignment: embedding-based and citation-based structure converge.")
    else:
        print(f"  Too few overlapping papers ({n_overlap}) for meaningful ARI.")
else:
    print("\nWARNING: communities.csv not found, skipping ARI alignment check.")


# ============================================================
# Step 2: Sliding-window structural break detection
# ============================================================

def compute_js_divergence(p, q):
    """Jensen-Shannon divergence between two probability distributions."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    # Ensure proper distributions
    p = p / p.sum() if p.sum() > 0 else p
    q = q / q.sum() if q.sum() > 0 else q
    m = 0.5 * (p + q)
    # Avoid log(0)
    with np.errstate(divide="ignore", invalid="ignore"):
        kl_pm = np.where(p > 0, p * np.log2(p / m), 0)
        kl_qm = np.where(q > 0, q * np.log2(q / m), 0)
    return float(0.5 * np.nansum(kl_pm) + 0.5 * np.nansum(kl_qm))


def compute_divergence_series(df, embeddings, k, window_sizes, start_year=2005, end_year=2023,
                              censor_gap=0):
    """Compute JS divergence and cosine distance for each year and window size.

    Parameters
    ----------
    censor_gap : int
        Number of transition years to censor before each test point.
        With censor_gap=0, before window is [y-w, y] (unchanged default).
        With censor_gap=k, before window becomes [y-w-k, y-k].
    """
    # Fit KMeans
    km = KMeans(n_clusters=k, random_state=42, n_init=20)
    labels = km.fit_predict(embeddings)

    results = {}
    for w in window_sizes:
        js_series = {}
        cos_series = {}
        for y in range(start_year, end_year + 1):
            # Before window: [y-w-censor_gap, y-censor_gap]
            mask_before = (df["year"] >= y - w - censor_gap) & (df["year"] <= y - censor_gap)
            # After window: [y+1, y+1+w] (unchanged)
            mask_after = (df["year"] >= y + 1) & (df["year"] <= y + 1 + w)

            idx_before = df.index[mask_before]
            idx_after = df.index[mask_after]

            if len(idx_before) < N_MIN or len(idx_after) < N_MIN:
                js_series[y] = np.nan
                cos_series[y] = np.nan
                continue

            # JS divergence on cluster proportions
            labels_before = labels[idx_before]
            labels_after = labels[idx_after]
            prop_before = np.bincount(labels_before, minlength=k) / len(labels_before)
            prop_after = np.bincount(labels_after, minlength=k) / len(labels_after)
            js_series[y] = compute_js_divergence(prop_before, prop_after)

            # Cosine distance between mean embeddings
            emb_before = embeddings[idx_before].mean(axis=0)
            emb_after = embeddings[idx_after].mean(axis=0)
            cos_series[y] = cosine_dist(emb_before, emb_after)

        results[w] = {"js": js_series, "cos": cos_series}
    return results


WINDOW_SIZES = [2, 3, 4]

print("\n=== Structural break detection ===")
print(f"Window sizes: {WINDOW_SIZES}, start year: 2005, n_min: {N_MIN}, censor_gap: {args.censor_gap}")

div_results = compute_divergence_series(
    df, embeddings, K_DEFAULT, WINDOW_SIZES, start_year=2005, end_year=2023,
    censor_gap=args.censor_gap
)

# Build breakpoints table
years = list(range(2005, 2024))
bp_data = {"year": years}
for w in WINDOW_SIZES:
    bp_data[f"js_w{w}"] = [div_results[w]["js"].get(y, np.nan) for y in years]
    bp_data[f"cos_w{w}"] = [div_results[w]["cos"].get(y, np.nan) for y in years]

bp_df = pd.DataFrame(bp_data)

# Z-score normalize
for metric in ["js", "cos"]:
    for w in WINDOW_SIZES:
        col = f"{metric}_w{w}"
        vals = bp_df[col].dropna()
        if len(vals) > 1 and vals.std() > 0:
            bp_df[f"z_{col}"] = (bp_df[col] - vals.mean()) / vals.std()
        else:
            bp_df[f"z_{col}"] = np.nan

bp_df.to_csv(os.path.join(TABLES_DIR, TAB_BP), index=False)
print(f"\nSaved divergence table → tables/{TAB_BP}")


# ============================================================
# Step 2b: Detect robust breakpoints
# ============================================================

def find_local_maxima(series, threshold=1.5):
    """Find local maxima above z-score threshold. Returns list of (year, z_score)."""
    peaks = []
    years_list = list(series.dropna().index)
    for i, y in enumerate(years_list):
        z = series.loc[y]
        if np.isnan(z) or z <= threshold:
            continue
        # Check local maximum
        is_max = True
        if i > 0 and not np.isnan(series.loc[years_list[i - 1]]):
            if series.loc[years_list[i - 1]] >= z:
                is_max = False
        if i < len(years_list) - 1 and not np.isnan(series.loc[years_list[i + 1]]):
            if series.loc[years_list[i + 1]] >= z:
                is_max = False
        if is_max:
            peaks.append((y, z))
    return peaks


def find_robust_breakpoints(candidates_by_w, window_sizes):
    """Identify years that appear as peaks in >=2 window sizes (±1 year)."""
    all_peak_years = {}
    for w in window_sizes:
        for y, z in candidates_by_w.get(w, []):
            if y not in all_peak_years:
                all_peak_years[y] = {}
            all_peak_years[y][w] = z

    robust = []
    checked = set()
    for y in sorted(all_peak_years.keys()):
        if y in checked:
            continue
        # Count window sizes that have a peak at y ± 1
        supporting = {}
        for w in window_sizes:
            for dy in [-1, 0, 1]:
                if y + dy in all_peak_years and w in all_peak_years.get(y + dy, {}):
                    supporting[w] = all_peak_years[y + dy][w]
                    break
        if len(supporting) >= 2:
            mean_z = np.mean(list(supporting.values()))
            robust.append({"year": y, "n_windows": len(supporting), "mean_z": mean_z,
                           "windows": supporting})
            checked.update(range(y - 1, y + 2))
    return sorted(robust, key=lambda x: -x["mean_z"])


# Collect candidate breakpoints per metric per window size
bp_indexed = bp_df.set_index("year")
candidates = {"js": {}, "cos": {}}
for metric in ["js", "cos"]:
    for w in WINDOW_SIZES:
        col = f"z_{metric}_w{w}"
        if col in bp_indexed.columns:
            candidates[metric][w] = find_local_maxima(bp_indexed[col])

robust_js = find_robust_breakpoints(candidates["js"], WINDOW_SIZES)
robust_cos = find_robust_breakpoints(candidates["cos"], WINDOW_SIZES)

# Combine: flag breakpoints supported by both metrics
all_robust_years = {}
for bp in robust_js:
    y = bp["year"]
    all_robust_years[y] = {"js_z": bp["mean_z"], "cos_z": 0, "js_windows": bp["n_windows"],
                           "cos_windows": 0, "support": "JS only"}
for bp in robust_cos:
    y = bp["year"]
    for dy in [-1, 0, 1]:
        if y + dy in all_robust_years:
            all_robust_years[y + dy]["cos_z"] = bp["mean_z"]
            all_robust_years[y + dy]["cos_windows"] = bp["n_windows"]
            all_robust_years[y + dy]["support"] = "both"
            break
    else:
        all_robust_years[y] = {"js_z": 0, "cos_z": bp["mean_z"], "js_windows": 0,
                               "cos_windows": bp["n_windows"], "support": "cosine only"}

# Sort by combined z-score
robust_list = []
for y, info in all_robust_years.items():
    combined_z = info["js_z"] + info["cos_z"]
    robust_list.append({
        "year": y,
        "js_mean_z": round(info["js_z"], 3),
        "cos_mean_z": round(info["cos_z"], 3),
        "combined_z": round(combined_z, 3),
        "js_windows": info["js_windows"],
        "cos_windows": info["cos_windows"],
        "support": info["support"],
    })
robust_list.sort(key=lambda x: -x["combined_z"])

robust_df = pd.DataFrame(robust_list)
robust_df.to_csv(os.path.join(TABLES_DIR, TAB_BP_ROBUST), index=False)
print(f"\nSaved robustness table → tables/{TAB_BP_ROBUST}")

print("\n=== Robust breakpoints ===")
for bp in robust_list[:5]:
    print(f"  {bp['year']}: JS z={bp['js_mean_z']}, cos z={bp['cos_mean_z']}, "
          f"support={bp['support']}")

# Detected breakpoints (for Fig 2 visualization)
detected_breaks = sorted([bp["year"] for bp in robust_list[:3]])
print(f"\nDetected robust breakpoints: {detected_breaks}")

# Periodization: use the manuscript's three-act structure
# (detected breaks inform this, but the alluvial uses 3 periods for clarity)
all_breaks = [2007, 2015]
supplementary = []  # kept for backward compat with breakpoint visualization
print(f"Period boundaries: {all_breaks} (manuscript three-act structure)")

# Volume confound check
print("\n=== Volume confound check ===")
yearly_counts = df.groupby("year").size()
growth_rate = yearly_counts.pct_change().dropna()

for metric in ["js", "cos"]:
    for w in WINDOW_SIZES:
        col = f"{metric}_w{w}"
        valid = bp_df[["year", col]].dropna().set_index("year")
        common_years = valid.index.intersection(growth_rate.index)
        if len(common_years) >= 5:
            r, p = pearsonr(
                valid.loc[common_years, col],
                growth_rate.loc[common_years],
            )
            flag = " *** CONFOUNDED" if abs(r) > 0.5 else ""
            print(f"  {col} vs volume growth: r={r:.3f}, p={p:.3f}{flag}")


# ============================================================
# Step 3: Segment into data-derived periods
# ============================================================

# Build period boundaries: [start, break1, break2, break3, end]
boundaries = [1990] + all_breaks + [2026]
period_labels = []
for i in range(len(boundaries) - 1):
    lo = boundaries[i]
    hi = boundaries[i + 1] - 1
    if i == len(boundaries) - 2:
        hi = 2025
    period_labels.append(f"{lo}–{hi}")

print(f"\nData-derived periods: {period_labels}")


def assign_period(year):
    for i in range(len(boundaries) - 1):
        lo = boundaries[i]
        hi = boundaries[i + 1]
        if lo <= year < hi:
            return period_labels[i]
    return period_labels[-1]


df["period"] = df["year"].apply(assign_period)


# ============================================================
# Step 4: Per-period cluster distributions
# ============================================================

# Cross-tabulation
alluvial_data = pd.crosstab(df["period"], df["cluster"])
# Reorder by period
alluvial_data = alluvial_data.reindex(period_labels)
alluvial_data.to_csv(os.path.join(TABLES_DIR, TAB_AL))
print(f"\nSaved alluvial table → tables/{TAB_AL}")
print("\nPeriod × Cluster distribution:")
print(alluvial_data)

# Core share per cell (for annotation in full-corpus mode)
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
# Step 5: Label communities from abstract TF-IDF
# ============================================================

# Use abstract text (not noisy OpenAlex keywords) to label clusters.
# For each cluster, find terms most distinctive vs. corpus average.

LABEL_STOPWORDS = {
    # Corpus-wide generic terms
    "climate", "climate change", "change", "finance", "financial", "carbon",
    "emission", "emissions", "mitigation", "adaptation",
    # Academic boilerplate
    "paper", "study", "analysis", "results", "approach", "article", "research",
    "literature", "review", "data", "work", "based", "findings", "using",
    "new", "use", "used", "model", "evidence", "impact", "effects", "effect",
    "role", "case", "sector", "risk", "market", "markets", "investment",
    # Geographic / institutional generics
    "countries", "country", "policy", "policies", "global", "world",
    "international", "national", "economic", "economics", "development",
    # Tech buzzwords (uninformative as cluster labels)
    "blockchain", "esg", "theory", "usd",
    # Metadata artifacts
    "pdf", "http", "https", "www", "vol", "pp",
}

# Acronym → expansion mappings: collapse expansions into acronyms in text
# so component words don't get double-counted in TF-IDF.
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
min_df_val = 3 if args.core_only else 5  # lower for smaller corpus
label_vectorizer = TfidfVectorizer(
    ngram_range=(1, 2), max_features=8000, sublinear_tf=True,
    stop_words="english", min_df=min_df_val, max_df=0.8,
)
X_label = label_vectorizer.fit_transform(abstracts_for_tfidf)
label_features = np.array(label_vectorizer.get_feature_names_out())

# Corpus-wide mean TF-IDF
corpus_mean = np.asarray(X_label.mean(axis=0)).flatten()

cluster_labels = {}
for c in range(K_DEFAULT):
    c_mask = df["cluster"].values == c
    if c_mask.sum() == 0:
        cluster_labels[c] = f"Cluster {c}"
        continue
    c_mean = np.asarray(X_label[c_mask].mean(axis=0)).flatten()
    distinctiveness = c_mean - corpus_mean

    # Collect candidate terms above baseline, filtering stopwords.
    # Build separate unigram and bigram pools to ensure bigrams aren't
    # drowned out by individually high-scoring unigrams.
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
    # Interleave: bigrams first (more informative), then unigrams
    candidates = bi_candidates + uni_candidates

    # Promote bigrams: if a bigram's score is within 50% of the best
    # unigram it contains, prefer the bigram (more informative).
    unigram_scores = {t: s for t, s in candidates if " " not in t}
    bigrams = [(t, s) for t, s in candidates if " " in t]
    promoted = set()
    for bigram, bi_score in bigrams:
        parts = bigram.split()
        best_uni = max((unigram_scores.get(p, 0) for p in parts), default=0)
        if best_uni > 0 and bi_score >= best_uni * 0.5:
            promoted.add(bigram)

    # Select terms until we reach 10 words, preferring bigrams
    MAX_WORDS = 10

    def _word_count(terms):
        return sum(len(t.split()) for t in terms)

    scored = []
    used_tokens = set()
    # First pass: promoted bigrams
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
    # Second pass: fill remaining words with unigrams
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
    # Merge pass: if two selected unigrams form a bigram whose distinctiveness
    # exceeds the weaker unigram, merge them to free a slot.
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
                    # Only merge if bigram is more distinctive than weaker component
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
    # Fill freed slots
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

with open(os.path.join(CATALOGS_DIR, LABEL_FILE), "w") as f:
    json.dump({str(k): v for k, v in cluster_labels.items()}, f)
print(f"Saved cluster labels → data/catalogs/{LABEL_FILE}")


# ============================================================
# Robustness: k-sensitivity analysis
# ============================================================

if args.robustness and not args.core_only:
    print("\n=== Robustness: k-sensitivity (k=4,5,6,7) ===")
    k_values = [4, 5, 6, 7]
    k_results = {}

    for k in k_values:
        print(f"  Running k={k}...")
        res = compute_divergence_series(
            df, embeddings, k, [3], start_year=2005, end_year=2023,
            censor_gap=args.censor_gap
        )
        k_results[k] = res[3]["js"]

    # Build table
    k_data = {"year": years}
    for k in k_values:
        k_data[f"js_k{k}"] = [k_results[k].get(y, np.nan) for y in years]
    k_df = pd.DataFrame(k_data)
    k_df.to_csv(os.path.join(TABLES_DIR, "tab_k_sensitivity.csv"), index=False)
    print(f"Saved k-sensitivity table → tables/tab_k_sensitivity.csv")

    # Overlay plot
    fig, ax = plt.subplots(figsize=(12, 5))
    k_colors = {4: "#E63946", 5: "#F4A261", 6: "#457B9D", 7: "#2A9D8F"}
    for k in k_values:
        col = f"js_k{k}"
        valid = k_df[["year", col]].dropna()
        ax.plot(valid["year"], valid[col], "-o", color=k_colors[k], markersize=4,
                label=f"k={k}", alpha=0.8, linewidth=1.5 if k == K_DEFAULT else 1.0)

    for yr, label in COP_EVENTS.items():
        if 2004 <= yr <= 2024:
            ax.axvline(yr, color="grey", linestyle="--", alpha=0.4, linewidth=0.8)

    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel("JS divergence (w=3)", fontsize=11)
    ax.set_title("K-sensitivity: do structural breaks persist across cluster counts?",
                 fontsize=12, pad=15)
    ax.legend(fontsize=9, framealpha=0.9)
    plt.tight_layout()
    save_figure(fig, os.path.join(FIGURES_DIR, "fig_k_sensitivity"), no_pdf=args.no_pdf)
    plt.close()

# ============================================================
# Step 8: Lexical validation of the 2009 break (TF-IDF)
# ============================================================

if args.core_only:
    print("\nDone (core-only mode — skipping lexical validation).")
    import sys; sys.exit(0)

print("\n=== Lexical validation: TF-IDF at detected breakpoints ===")

# Use the first detected break for the main comparison
main_break = detected_breaks[0] if detected_breaks else 2009
mask_A = df["year"] < main_break
mask_B = (df["year"] >= main_break + 1) & (df["year"] <= main_break + 3)

texts_A = df.loc[mask_A, "abstract"].dropna().tolist()
texts_B = df.loc[mask_B, "abstract"].dropna().tolist()
n_A = len(texts_A)
n_B = len(texts_B)
print(f"Period A (before {main_break}): {n_A} abstracts")
print(f"Period B ({main_break+1}-{main_break+3}):   {n_B} abstracts")

if n_A >= 5 and n_B >= 5:
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.9,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(texts_A + texts_B)
    feature_names = np.array(vectorizer.get_feature_names_out())

    mean_A = np.asarray(X[:n_A].mean(axis=0)).flatten()
    mean_B = np.asarray(X[n_A:].mean(axis=0)).flatten()
    diff = mean_B - mean_A

    # --- Denoising: require minimum document frequency within enriched period ---
    # For each term, count how many docs in period A / B contain it
    X_A = X[:n_A]
    X_B = X[n_A:]
    doc_freq_A = np.asarray((X_A > 0).sum(axis=0)).flatten()
    doc_freq_B = np.asarray((X_B > 0).sum(axis=0)).flatten()

    MIN_PERIOD_DF = 3  # term must appear in ≥3 docs within its enriched period

    # Extra stop words: generic English words not in sklearn's stop list that
    # surface as noise in the small pre-2009 corpus (41 abstracts)
    EXTRA_STOPS = {"mid", "vol", "hope", "gives", "new", "use", "used", "using"}

    def is_clean_term(term):
        """Filter out noise: numbers, very short tokens, extra stop words."""
        tokens = term.split()
        # Reject single-char or two-char unigrams
        if len(tokens) == 1 and len(tokens[0]) < 3:
            return False
        # Reject purely numeric terms
        if all(t.isdigit() for t in tokens):
            return False
        # Reject extra stop words (as unigrams or bigram components)
        if len(tokens) == 1 and tokens[0] in EXTRA_STOPS:
            return False
        return True

    # Build mask: term passes if (a) clean token AND (b) sufficient df in enriched period
    valid_mask = np.zeros(len(feature_names), dtype=bool)
    for i, term in enumerate(feature_names):
        if not is_clean_term(term):
            continue
        if diff[i] < 0 and doc_freq_A[i] >= MIN_PERIOD_DF:
            valid_mask[i] = True
        elif diff[i] > 0 and doc_freq_B[i] >= MIN_PERIOD_DF:
            valid_mask[i] = True
        elif diff[i] == 0:
            valid_mask[i] = True

    n_filtered = (~valid_mask).sum()
    print(f"Denoising: filtered {n_filtered}/{len(feature_names)} terms "
          f"(min {MIN_PERIOD_DF} docs in enriched period, {len(EXTRA_STOPS)} extra stop words)")

    # Apply mask to get clean top terms
    valid_indices = np.where(valid_mask)[0]
    diff_clean = diff[valid_mask]
    idx_top_B = valid_indices[np.argsort(diff_clean)[-25:][::-1]]
    idx_top_A = valid_indices[np.argsort(diff_clean)[:25]]

    print(f"\nTop 25 terms enriched AFTER {main_break} (period B):")
    for i in idx_top_B:
        print(f"  +{diff[i]:.4f}  {feature_names[i]}")

    print(f"\nTop 25 terms enriched BEFORE {main_break} (period A):")
    for i in idx_top_A:
        print(f"  {diff[i]:.4f}  {feature_names[i]}")

    # Save full table (with doc freq and clean flag for transparency)
    tfidf_df = pd.DataFrame({
        "term": feature_names,
        "mean_tfidf_before": mean_A,
        "mean_tfidf_after": mean_B,
        "diff": diff,
        "doc_freq_before": doc_freq_A.astype(int),
        "doc_freq_after": doc_freq_B.astype(int),
        "clean": valid_mask,
    }).sort_values("diff", ascending=False)
    tfidf_df.to_csv(os.path.join(TABLES_DIR, "tab_lexical_tfidf.csv"), index=False)
    print(f"\nSaved TF-IDF table → tables/tab_lexical_tfidf.csv "
          f"({valid_mask.sum()} clean / {len(tfidf_df)} total terms)")

    # --- Reusable TF-IDF bar chart function ---
    def plot_tfidf_bars(df_works, break_year, window_after=3, n_show=20,
                        suffix="", extra_stops=EXTRA_STOPS, xlim=None):
        """Compare vocabulary before vs after a break year.

        Period A: all abstracts before break_year.
        Period B: abstracts in [break_year+1, break_year+window_after].
        """
        mA = df_works["year"] < break_year
        mB = (df_works["year"] >= break_year + 1) & (df_works["year"] <= break_year + window_after)
        tA = df_works.loc[mA, "abstract"].dropna().tolist()
        tB = df_works.loc[mB, "abstract"].dropna().tolist()
        nA, nB = len(tA), len(tB)
        if nA < 5 or nB < 5:
            print(f"  Skipping {break_year}: too few abstracts (A={nA}, B={nB})")
            return None

        vec = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2),
            min_df=3, max_df=0.9, sublinear_tf=True,
        )
        X = vec.fit_transform(tA + tB)
        names = np.array(vec.get_feature_names_out())
        mA_vec = np.asarray(X[:nA].mean(axis=0)).flatten()
        mB_vec = np.asarray(X[nA:].mean(axis=0)).flatten()
        d = mB_vec - mA_vec

        # Permutation test: significance threshold for |ΔTF-IDF|
        N_PERM = 1000
        rng = np.random.RandomState(42)
        max_abs_diffs = np.zeros(N_PERM)
        n_total = nA + nB
        for p in range(N_PERM):
            perm = rng.permutation(n_total)
            perm_A = np.asarray(X[perm[:nA]].mean(axis=0)).flatten()
            perm_B = np.asarray(X[perm[nA:]].mean(axis=0)).flatten()
            max_abs_diffs[p] = np.max(np.abs(perm_B - perm_A))
        sig_95 = np.percentile(max_abs_diffs, 95)
        sig_99 = np.percentile(max_abs_diffs, 99)
        print(f"  Permutation test ({N_PERM} perm): |ΔTFIDF| threshold "
              f"p<0.05={sig_95:.4f}, p<0.01={sig_99:.4f}")

        # Denoising
        dfA = np.asarray((X[:nA] > 0).sum(axis=0)).flatten()
        dfB = np.asarray((X[nA:] > 0).sum(axis=0)).flatten()
        ok = np.zeros(len(names), dtype=bool)
        for i, t in enumerate(names):
            toks = t.split()
            if len(toks) == 1 and len(toks[0]) < 3:
                continue
            if all(tok.isdigit() for tok in toks):
                continue
            if len(toks) == 1 and toks[0] in extra_stops:
                continue
            if d[i] < 0 and dfA[i] >= MIN_PERIOD_DF:
                ok[i] = True
            elif d[i] > 0 and dfB[i] >= MIN_PERIOD_DF:
                ok[i] = True
        clean_idx = np.where(ok)[0]
        d_clean = d[ok]
        idx_after = clean_idx[np.argsort(d_clean)[-n_show:][::-1]]
        idx_before = clean_idx[np.argsort(d_clean)[:n_show]]

        # Build plot data
        terms = list(names[idx_before][::-1]) + list(names[idx_after])
        diffs = list(d[idx_before][::-1]) + list(d[idx_after])

        fig, ax = plt.subplots(figsize=(10, 10))
        colors = ["#457B9D" if v < 0 else "#E63946" for v in diffs]
        y = range(len(terms))
        ax.barh(y, diffs, color=colors, alpha=0.85)
        ax.set_yticks(y)
        ax.set_yticklabels(terms, fontsize=8)
        ax.axvline(0, color="black", linewidth=0.8)

        # Significance bands from permutation test
        ax.axvspan(-sig_95, sig_95, alpha=0.08, color="grey", zorder=0)
        ax.axvline(-sig_95, color="black", linestyle=":", alpha=0.3, linewidth=0.8)
        ax.axvline(sig_95, color="black", linestyle=":", alpha=0.3, linewidth=0.8)
        ax.axvline(-sig_99, color="black", linestyle="--", alpha=0.3, linewidth=0.8)
        ax.axvline(sig_99, color="black", linestyle="--", alpha=0.3, linewidth=0.8)
        # Label thresholds at top
        ax.text(sig_95, len(terms) + 0.3, "p<.05", fontsize=7, ha="center",
                color="black", alpha=0.5)
        ax.text(sig_99, len(terms) + 0.3, "p<.01", fontsize=7, ha="center",
                color="black", alpha=0.5)
        ax.text(-sig_95, len(terms) + 0.3, "p<.05", fontsize=7, ha="center",
                color="black", alpha=0.5)
        ax.text(-sig_99, len(terms) + 0.3, "p<.01", fontsize=7, ha="center",
                color="black", alpha=0.5)

        ax.set_xlabel("ΔTF-IDF (after − before)", fontsize=11)
        if xlim is not None:
            ax.set_xlim(xlim)

        # Horizontal separator between the two groups
        ax.axhline(n_show - 0.5, color="grey", linewidth=0.5, linestyle="--", alpha=0.5)

        # Period labels in the margin (outside bars, using ax.annotate)
        ax.annotate(f"← Before {break_year}  (n={nA})", xy=(0, 0),
                    xytext=(0.02, 0.02), textcoords="axes fraction",
                    fontsize=10, color="#457B9D", fontweight="bold")
        ax.annotate(f"After {break_year} →  (n={nB})", xy=(0, 1),
                    xytext=(0.75, 0.97), textcoords="axes fraction",
                    fontsize=10, color="#E63946", fontweight="bold")

        after_label = f"{break_year+1}–{break_year+window_after}"
        ax.set_title(
            f"Lexical comparison around {break_year}\n"
            f"(before {break_year}: {nA} abstracts, {after_label}: {nB} abstracts)",
            fontsize=12, pad=15,
        )

        plt.tight_layout()
        fname = f"fig_lexical_tfidf{suffix}"
        save_figure(fig, os.path.join(FIGURES_DIR, fname), no_pdf=args.no_pdf)
        print(f"    (A={nA}, B={nB})")
        plt.close()
        return {"break_year": break_year, "n_before": nA, "n_after": nB,
                "top_before": list(names[idx_before]),
                "top_after": list(names[idx_after])}

    # --- Pre-compute global x-axis range across all break years ---
    # Use detected breaks + COP controls
    break_years = sorted(detected_breaks) + [yr for yr in [2015, 2021]
                                              if yr not in detected_breaks]
    global_max = 0
    for yr in break_years:
        mA = df["year"] < yr
        mB = (df["year"] >= yr + 1) & (df["year"] <= yr + 3)
        tA = df.loc[mA, "abstract"].dropna().tolist()
        tB = df.loc[mB, "abstract"].dropna().tolist()
        if len(tA) < 5 or len(tB) < 5:
            continue
        vec = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2),
            min_df=3, max_df=0.9, sublinear_tf=True,
        )
        X = vec.fit_transform(tA + tB)
        mA_v = np.asarray(X[:len(tA)].mean(axis=0)).flatten()
        mB_v = np.asarray(X[len(tA):].mean(axis=0)).flatten()
        global_max = max(global_max, np.max(np.abs(mB_v - mA_v)))
    shared_xlim = (-global_max * 1.15, global_max * 1.15)
    print(f"  Shared x-axis range: [{shared_xlim[0]:.4f}, {shared_xlim[1]:.4f}]")

    # --- Run for all break years with shared scale ---
    for idx, yr in enumerate(break_years):
        suffix = f"_{yr}"
        print(f"\n  Break year {yr}:")
        plot_tfidf_bars(df, yr, window_after=3, suffix=suffix, xlim=shared_xlim)

else:
    print("WARNING: Too few abstracts for TF-IDF comparison.")

print("\nDone.")
