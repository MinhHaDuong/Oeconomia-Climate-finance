"""Endogenous structural break detection and alluvial community flows.

Method:
- Fit KMeans (k=6) once on full embedding corpus
- Sliding-window Jensen-Shannon divergence + cosine distance on cluster distributions
- Z-score normalized breakpoint detection (robust across window sizes)
- Alluvial diagram using data-derived periods

Produces:
- figures/fig2_breakpoints.pdf: JS divergence time series with COP overlay
- figures/fig3_alluvial.pdf: Community flows across data-derived periods
- tables/tab2_breakpoints.csv: Yearly divergence metrics for w=2,3,4
- tables/tab2_breakpoint_robustness.csv: Top breakpoints, stability flags
- tables/tab2_alluvial.csv: Period-community paper counts

With --robustness flag:
- tables/tab2_k_sensitivity.csv: JS divergence for k=4,5,6,7
"""

import argparse
import os
import warnings
from collections import Counter

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.spatial.distance import cosine as cosine_dist
from scipy.stats import pearsonr
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

import matplotlib.ticker as ticker
from sklearn.feature_extraction.text import TfidfVectorizer

from utils import BASE_DIR, CATALOGS_DIR, normalize_doi, save_figure

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npy")

# COP events (from analyze_temporal.py)
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
parser = argparse.ArgumentParser(description="Alluvial analysis with breakpoint detection")
parser.add_argument("--robustness", action="store_true", help="Run k-sensitivity analysis")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
args = parser.parse_args()


# ============================================================
# Step 0: Load data + embeddings
# ============================================================

print("Loading unified works...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

# Filter: must have abstract, year in range (matches embedding generation)
has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_abstract & in_range].copy().reset_index(drop=True)
print(f"Works with abstracts (1990-2025): {len(df)}")

print(f"Loading cached embeddings from {EMBEDDINGS_PATH}...")
embeddings = np.load(EMBEDDINGS_PATH)
if len(embeddings) != len(df):
    raise RuntimeError(
        f"Embedding cache size mismatch ({len(embeddings)} vs {len(df)}). "
        "Re-run analyze_embeddings.py first."
    )
print(f"Embedding shape: {embeddings.shape}")


# ============================================================
# Step 1: Global KMeans clustering (k=6, fit once)
# ============================================================

K_DEFAULT = 6
N_MIN = 30  # Minimum papers per window

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


def compute_divergence_series(df, embeddings, k, window_sizes, start_year=2005, end_year=2023):
    """Compute JS divergence and cosine distance for each year and window size."""
    # Fit KMeans
    km = KMeans(n_clusters=k, random_state=42, n_init=20)
    labels = km.fit_predict(embeddings)

    results = {}
    for w in window_sizes:
        js_series = {}
        cos_series = {}
        for y in range(start_year, end_year + 1):
            # Before window: [y-w, y]
            mask_before = (df["year"] >= y - w) & (df["year"] <= y)
            # After window: [y+1, y+1+w]
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
print(f"Window sizes: {WINDOW_SIZES}, start year: 2005, n_min: {N_MIN}")

div_results = compute_divergence_series(
    df, embeddings, K_DEFAULT, WINDOW_SIZES, start_year=2005, end_year=2023
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

bp_df.to_csv(os.path.join(TABLES_DIR, "tab2_breakpoints.csv"), index=False)
print(f"\nSaved divergence table → tables/tab2_breakpoints.csv")


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


# Collect candidate breakpoints per metric per window size
bp_indexed = bp_df.set_index("year")
candidates = {"js": {}, "cos": {}}
for metric in ["js", "cos"]:
    for w in WINDOW_SIZES:
        col = f"z_{metric}_w{w}"
        if col in bp_indexed.columns:
            candidates[metric][w] = find_local_maxima(bp_indexed[col])

# Find robust breakpoints (appear in >=2 window sizes within ±1 year)
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
robust_df.to_csv(os.path.join(TABLES_DIR, "tab2_breakpoint_robustness.csv"), index=False)
print(f"\nSaved robustness table → tables/tab2_breakpoint_robustness.csv")

print("\n=== Robust breakpoints ===")
for bp in robust_list[:5]:
    print(f"  {bp['year']}: JS z={bp['js_mean_z']}, cos z={bp['cos_mean_z']}, "
          f"support={bp['support']}")

# Select breakpoints for periodization
# If fewer than 3 robust breakpoints, supplement with COP milestones (2015, 2021)
# and clearly label which are data-derived vs COP-imposed
detected_breaks = sorted([bp["year"] for bp in robust_list[:3]])
print(f"\nDetected robust breakpoints: {detected_breaks}")

# Fallback: if fewer than 3, supplement with COP milestones
COP_SUPPLEMENTS = [2015, 2021]
supplementary = []
if len(detected_breaks) < 3:
    for cop_year in COP_SUPPLEMENTS:
        if cop_year not in detected_breaks and len(detected_breaks) + len(supplementary) < 3:
            # Check it's not within ±1 year of a detected break
            if all(abs(cop_year - d) > 1 for d in detected_breaks):
                supplementary.append(cop_year)
    if supplementary:
        print(f"  Supplementing with COP milestones: {supplementary} (sub-threshold in data)")

all_breaks = sorted(detected_breaks + supplementary)
print(f"Period boundaries: {all_breaks} "
      f"({'data-derived' if not supplementary else 'hybrid: ' + str(len(detected_breaks)) + ' data-derived + ' + str(len(supplementary)) + ' COP-imposed'})")

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
alluvial_data.to_csv(os.path.join(TABLES_DIR, "tab2_alluvial.csv"))
print(f"\nSaved alluvial table → tables/tab2_alluvial.csv")
print("\nPeriod × Cluster distribution:")
print(alluvial_data)


# ============================================================
# Step 5: Label communities from abstract TF-IDF
# ============================================================

# Use abstract text (not noisy OpenAlex keywords) to label clusters.
# For each cluster, find terms most distinctive vs. corpus average.

import json

LABEL_STOPWORDS = {
    "climate", "climate change", "finance", "financial", "paper", "study",
    "analysis", "results", "approach", "article", "research", "literature",
    "review", "data", "work", "based", "findings", "using", "new", "use",
    "used", "countries", "country", "policy", "policies", "global", "world",
    "international", "national", "economic", "economics", "development",
}

abstracts_for_tfidf = df["abstract"].fillna("").tolist()
label_vectorizer = TfidfVectorizer(
    ngram_range=(1, 2), max_features=8000, sublinear_tf=True,
    stop_words="english", min_df=5, max_df=0.8,
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

    # Filter out domain stopwords
    scored = []
    for i in np.argsort(distinctiveness)[::-1]:
        term = label_features[i]
        tokens = term.split()
        if any(t in LABEL_STOPWORDS for t in tokens):
            continue
        if len(tokens) == 1 and len(tokens[0]) < 3:
            continue
        scored.append(term)
        if len(scored) == 3:
            break
    cluster_labels[c] = " / ".join(scored) if scored else f"Cluster {c}"

print("\nCluster labels:")
for c, label in cluster_labels.items():
    print(f"  {c}: {label}")

with open(os.path.join(CATALOGS_DIR, "cluster_labels.json"), "w") as f:
    json.dump({str(k): v for k, v in cluster_labels.items()}, f)
print("Saved cluster labels → data/catalogs/cluster_labels.json")


# ============================================================
# Step 6: Render breakpoints figure
# ============================================================

sns.set_style("whitegrid")

fig, ax = plt.subplots(figsize=(12, 5))

colors_w = {2: "#E63946", 3: "#457B9D", 4: "#2A9D8F"}
for w in WINDOW_SIZES:
    col = f"z_js_w{w}"
    valid = bp_df[["year", col]].dropna()
    ax.plot(valid["year"], valid[col], "-o", color=colors_w[w], markersize=4,
            label=f"JS div (w={w})", alpha=0.8)

# Mark robust breakpoints (data-derived)
for bp in robust_list[:3]:
    ax.axvspan(bp["year"] - 0.3, bp["year"] + 0.3, alpha=0.25, color="orange",
               zorder=0, label="Data-derived break" if bp == robust_list[0] else "")

# Mark supplementary COP breaks
for yr in supplementary:
    ax.axvspan(yr - 0.3, yr + 0.3, alpha=0.15, color="blue",
               zorder=0, label="COP supplement" if yr == supplementary[0] else "")

# COP event lines
for yr, label in COP_EVENTS.items():
    if 2004 <= yr <= 2024:
        ax.axvline(yr, color="grey", linestyle="--", alpha=0.5, linewidth=0.8)
        ax.text(yr, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 2.5,
                label, ha="center", va="top", fontsize=7, color="grey",
                rotation=0)

# Significance bands
ax.axhspan(-1.5, 1.5, alpha=0.08, color="grey", zorder=0)  # non-significant zone
ax.axhline(1.5, color="black", linestyle=":", alpha=0.4, linewidth=0.8)
ax.axhline(2.0, color="black", linestyle="--", alpha=0.4, linewidth=0.8)
ax.axhline(-1.5, color="black", linestyle=":", alpha=0.4, linewidth=0.8)
ax.text(2024.3, 1.5, "z=1.5", fontsize=7, va="center", color="black", alpha=0.5)
ax.text(2024.3, 2.0, "z=2.0", fontsize=7, va="center", color="black", alpha=0.5)
ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel("Structural divergence (z-score)", fontsize=11)
ax.set_title("Detecting structural shifts in climate finance scholarship",
             fontsize=12, pad=15)
ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, "fig2_breakpoints"), no_pdf=args.no_pdf)
print(f"  (Figure 2)")
plt.close()


# ============================================================
# Step 7: Render alluvial figure
# ============================================================

fig, ax = plt.subplots(figsize=(7, 3.5))

n_periods = len(period_labels)
n_clusters = K_DEFAULT
palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))

# X positions for period columns (leave room for legend on right)
x_positions = np.linspace(0, 0.62, n_periods)
col_width = 0.04  # Half-width of each column bar

# Compute cumulative positions for each period's stack
period_stacks = {}
for pi, period in enumerate(period_labels):
    total = alluvial_data.loc[period].sum() if period in alluvial_data.index else 0
    if total == 0:
        period_stacks[period] = {}
        continue
    # Normalize to height
    max_height = 0.9
    y_bottom = 0.05
    stacks = {}
    for c in range(n_clusters):
        count = alluvial_data.loc[period, c] if period in alluvial_data.index else 0
        height = (count / total) * max_height
        stacks[c] = {"bottom": y_bottom, "height": height, "count": count}
        y_bottom += height
    period_stacks[period] = stacks

# Draw column bars
for pi, period in enumerate(period_labels):
    x = x_positions[pi]
    stacks = period_stacks[period]
    for c in range(n_clusters):
        if c not in stacks:
            continue
        s = stacks[c]
        if s["height"] > 0:
            rect = plt.Rectangle(
                (x - col_width, s["bottom"]), 2 * col_width, s["height"],
                facecolor=palette[c], edgecolor="white", linewidth=0.5, alpha=0.9,
            )
            ax.add_patch(rect)
            # Label if tall enough
            if s["height"] > 0.04:
                ax.text(x, s["bottom"] + s["height"] / 2,
                        f'{s["count"]}', ha="center", va="center",
                        fontsize=5, color="black", fontweight="bold")

# Draw flows between adjacent periods
for pi in range(n_periods - 1):
    period_a = period_labels[pi]
    period_b = period_labels[pi + 1]
    x_a = x_positions[pi] + col_width
    x_b = x_positions[pi + 1] - col_width

    stacks_a = period_stacks[period_a]
    stacks_b = period_stacks[period_b]

    for c in range(n_clusters):
        if c not in stacks_a or c not in stacks_b:
            continue
        sa = stacks_a[c]
        sb = stacks_b[c]
        if sa["height"] <= 0 or sb["height"] <= 0:
            continue

        # Draw curved ribbon from cluster c in period_a to cluster c in period_b
        from matplotlib.patches import FancyArrowPatch
        from matplotlib.path import Path

        y_a_bot = sa["bottom"]
        y_a_top = sa["bottom"] + sa["height"]
        y_b_bot = sb["bottom"]
        y_b_top = sb["bottom"] + sb["height"]

        # Bezier control points for smooth flow
        cx1 = x_a + (x_b - x_a) * 0.4
        cx2 = x_a + (x_b - x_a) * 0.6

        # Top edge
        verts_top = [
            (x_a, y_a_top), (cx1, y_a_top), (cx2, y_b_top), (x_b, y_b_top),
        ]
        # Bottom edge (reversed)
        verts_bot = [
            (x_b, y_b_bot), (cx2, y_b_bot), (cx1, y_a_bot), (x_a, y_a_bot),
        ]
        verts = verts_top + verts_bot + [(x_a, y_a_top)]  # close path
        codes = (
            [Path.MOVETO] + [Path.CURVE4] * 3 +
            [Path.LINETO] + [Path.CURVE4] * 3 +
            [Path.CLOSEPOLY]
        )
        path = Path(verts, codes)
        patch = mpatches.PathPatch(
            path, facecolor=palette[c], alpha=0.35, edgecolor="none",
        )
        ax.add_patch(patch)

# Period labels
for pi, period in enumerate(period_labels):
    x = x_positions[pi]
    ax.text(x, -0.03, period, ha="center", va="top", fontsize=6, fontweight="bold")

# Legend: text labels right next to the last data column
last_stacks = period_stacks[period_labels[-1]]
for c in range(n_clusters):
    if c not in last_stacks:
        continue
    s = last_stacks[c]
    if s["height"] <= 0:
        continue
    label_text = cluster_labels.get(c, f"Cluster {c}").replace(" / ", "\n")
    ax.text(x_positions[-1] + col_width + 0.008, s["bottom"] + s["height"] / 2,
            label_text, ha="left", va="center", fontsize=5.5,
            linespacing=1.3, color=palette[c] * 0.6)  # darker than fill

ax.set_xlim(-0.06, 0.85)
ax.set_ylim(-0.06, 1.0)
total = int(alluvial_data.values.sum())
ax.set_title(
    f"Thematic recomposition of climate finance scholarship, 1990–2025\n"
    f"(N = {total:,} publications; band width = number of publications per thematic cluster)",
    fontsize=7, pad=8,
)
ax.axis("off")

plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, "fig3_alluvial"), no_pdf=args.no_pdf)
print(f"  (Figure 3)")
plt.close()


# ============================================================
# Step 7b: Interactive HTML version with paper tooltips
# ============================================================

import html as html_mod

# Collect top-3 most-cited papers per (period, cluster)
top_papers = {}
for period in period_labels:
    for c in range(n_clusters):
        cell = df[(df["period"] == period) & (df["cluster"] == c)]
        cell_sorted = cell.sort_values("cited_by_count", ascending=False).head(3)
        papers = []
        for _, row in cell_sorted.iterrows():
            author = str(row.get("first_author", "?"))
            if len(author) > 25:
                author = author[:23] + "…"
            yr = int(row["year"]) if pd.notna(row["year"]) else "?"
            title = str(row.get("title", ""))
            if len(title) > 80:
                title = title[:78] + "…"
            cites = int(row["cited_by_count"]) if pd.notna(row["cited_by_count"]) else 0
            papers.append(f"{author} ({yr}), {title} [{cites} cit.]")
        top_papers[(period, c)] = papers

# SVG dimensions
svg_w, svg_h = 1350, 675
pad_l, pad_r, pad_t, pad_b = 75, 420, 82, 52
chart_w = svg_w - pad_l - pad_r
chart_h = svg_h - pad_t - pad_b

# Map normalized coords to SVG
def to_sx(xnorm):
    return pad_l + (xnorm / 0.62) * chart_w

def to_sy(ynorm):
    return pad_t + chart_h - (ynorm / 1.0) * chart_h

def rgba(c_idx, alpha=0.9):
    r, g, b, _ = palette[c_idx]
    return f"rgba({int(r*255)},{int(g*255)},{int(b*255)},{alpha})"

def rgb_dark(c_idx, factor=0.6):
    r, g, b, _ = palette[c_idx]
    return f"rgb({int(r*255*factor)},{int(g*255*factor)},{int(b*255*factor)})"

svg_parts = []
svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
                  f'font-family="sans-serif">')

# Title
total = int(alluvial_data.values.sum())
svg_parts.append(f'<text x="{svg_w//2}" y="28" text-anchor="middle" font-size="16" font-weight="bold">'
                 f'Thematic recomposition of climate finance scholarship, 1990–2025</text>')
svg_parts.append(f'<text x="{svg_w//2}" y="50" text-anchor="middle" font-size="13" fill="#666">'
                 f'(N = {total:,} publications; hover over a cell to see top-cited papers)</text>')

# Flow ribbons (draw first, behind bars)
for pi in range(n_periods - 1):
    pa, pb = period_labels[pi], period_labels[pi + 1]
    xa = x_positions[pi]
    xb = x_positions[pi + 1]
    sa_all, sb_all = period_stacks[pa], period_stacks[pb]
    cw = col_width
    for c in range(n_clusters):
        if c not in sa_all or c not in sb_all:
            continue
        sa, sb = sa_all[c], sb_all[c]
        if sa["height"] <= 0 or sb["height"] <= 0:
            continue
        x1 = to_sx(xa + cw)
        x2 = to_sx(xb - cw)
        y1t, y1b = to_sy(sa["bottom"] + sa["height"]), to_sy(sa["bottom"])
        y2t, y2b = to_sy(sb["bottom"] + sb["height"]), to_sy(sb["bottom"])
        cx1 = x1 + (x2 - x1) * 0.4
        cx2 = x1 + (x2 - x1) * 0.6
        d = (f"M{x1},{y1t} C{cx1},{y1t} {cx2},{y2t} {x2},{y2t} "
             f"L{x2},{y2b} C{cx2},{y2b} {cx1},{y1b} {x1},{y1b} Z")
        svg_parts.append(f'<path d="{d}" fill="{rgba(c, 0.3)}" stroke="none"/>')

# Column bars (clickable)
for pi, period in enumerate(period_labels):
    x = x_positions[pi]
    stacks = period_stacks[period]
    for c in range(n_clusters):
        if c not in stacks:
            continue
        s = stacks[c]
        if s["height"] <= 0:
            continue
        rx = to_sx(x - col_width)
        ry = to_sy(s["bottom"] + s["height"])
        rw = to_sx(x + col_width) - rx
        rh = to_sy(s["bottom"]) - ry
        cell_id = f"cell_{pi}_{c}"
        paper_lines = "<br>".join(html_mod.escape(p) for p in top_papers.get((period, c), ["(no papers)"]))
        cluster_name = html_mod.escape(cluster_labels.get(c, f"Cluster {c}"))
        # Build tooltip HTML, then escape quotes for embedding in attribute
        tooltip_inner = (f'<b>{period} — {cluster_name}</b><br>'
                         f'<b>{s["count"]} publications</b><br><br>'
                         f'{paper_lines}')
        tooltip_attr = tooltip_inner.replace('"', '&quot;')
        svg_parts.append(
            f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
            f'fill="{rgba(c)}" stroke="white" stroke-width="0.5" '
            f'class="cell" data-tooltip="{tooltip_attr}" '
            f'style="cursor:pointer"/>'
        )
        # Count label
        if s["height"] > 0.04:
            tx = to_sx(x)
            ty = to_sy(s["bottom"] + s["height"] / 2)
            svg_parts.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" '
                f'dominant-baseline="central" font-size="12" font-weight="bold" '
                f'fill="black" pointer-events="none">{s["count"]}</text>'
            )

# Period labels
for pi, period in enumerate(period_labels):
    tx = to_sx(x_positions[pi])
    svg_parts.append(f'<text x="{tx:.1f}" y="{svg_h - 18}" text-anchor="middle" '
                     f'font-size="14" font-weight="bold">{period}</text>')

# Legend labels next to last column
for c in range(n_clusters):
    if c not in last_stacks:
        continue
    s = last_stacks[c]
    if s["height"] <= 0:
        continue
    label_lines = cluster_labels.get(c, f"Cluster {c}").split(" / ")
    base_y = to_sy(s["bottom"] + s["height"] / 2)
    lx = to_sx(x_positions[-1] + col_width) + 12
    # Vertically center the multi-line label
    line_h = 17
    start_y = base_y - (len(label_lines) - 1) * line_h / 2
    for li, line in enumerate(label_lines):
        svg_parts.append(
            f'<text x="{lx:.1f}" y="{start_y + li * line_h:.1f}" '
            f'font-size="12" fill="{rgb_dark(c)}" dominant-baseline="central">'
            f'{html_mod.escape(line)}</text>'
        )

svg_parts.append('</svg>')

# Build full HTML with tooltip logic
html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Fig 3 – Alluvial (interactive)</title>
<style>
body {{ margin: 20px; font-family: sans-serif; background: #fafafa; }}
#container {{ position: relative; display: inline-block; }}
#tooltip {{
  display: none; position: absolute; pointer-events: none;
  background: white; border: 1px solid #ccc; border-radius: 6px;
  padding: 14px 18px; font-size: 13px; line-height: 1.5;
  box-shadow: 2px 2px 8px rgba(0,0,0,0.15); max-width: 520px; z-index: 10;
}}
.cell:hover {{ filter: brightness(0.9); }}
</style>
</head><body>
<div id="container">
{''.join(svg_parts)}
<div id="tooltip"></div>
</div>
<script>
const tooltip = document.getElementById('tooltip');
document.querySelectorAll('.cell').forEach(el => {{
  el.addEventListener('mouseenter', e => {{
    tooltip.innerHTML = el.dataset.tooltip;
    tooltip.style.display = 'block';
  }});
  el.addEventListener('mousemove', e => {{
    const box = document.getElementById('container').getBoundingClientRect();
    let left = e.clientX - box.left + 15;
    let top = e.clientY - box.top + 10;
    if (left + 300 > box.width) left = e.clientX - box.left - 320;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }});
  el.addEventListener('mouseleave', () => {{ tooltip.style.display = 'none'; }});
}});
</script>
</body></html>"""

html_path = os.path.join(FIGURES_DIR, "fig3_alluvial.html")
with open(html_path, "w") as f:
    f.write(html_content)
print(f"Saved interactive version → figures/fig3_alluvial.html")


# ============================================================
# Robustness: k-sensitivity analysis
# ============================================================

if args.robustness:
    print("\n=== Robustness: k-sensitivity (k=4,5,6,7) ===")
    k_values = [4, 5, 6, 7]
    k_results = {}

    for k in k_values:
        print(f"  Running k={k}...")
        res = compute_divergence_series(
            df, embeddings, k, [3], start_year=2005, end_year=2023
        )
        k_results[k] = res[3]["js"]

    # Build table
    k_data = {"year": years}
    for k in k_values:
        k_data[f"js_k{k}"] = [k_results[k].get(y, np.nan) for y in years]
    k_df = pd.DataFrame(k_data)
    k_df.to_csv(os.path.join(TABLES_DIR, "tab2_k_sensitivity.csv"), index=False)
    print(f"Saved k-sensitivity table → tables/tab2_k_sensitivity.csv")

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
    save_figure(fig, os.path.join(FIGURES_DIR, "figA_k_sensitivity"), no_pdf=args.no_pdf)
    plt.close()

# ============================================================
# Step 8: Lexical validation of the 2009 break (TF-IDF)
# ============================================================

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
    tfidf_df.to_csv(os.path.join(TABLES_DIR, "tab2_lexical_tfidf.csv"), index=False)
    print(f"\nSaved TF-IDF table → tables/tab2_lexical_tfidf.csv "
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
        fname = f"figA_lexical_tfidf{suffix}"
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
