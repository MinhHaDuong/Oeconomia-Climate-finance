"""Endogenous structural break detection and alluvial community flows.

Method:
- Fit KMeans (k=6) once on full embedding corpus
- Sliding-window Jensen-Shannon divergence + cosine distance on cluster distributions
- Z-score normalized breakpoint detection (robust across window sizes)
- Alluvial diagram using data-derived periods

Produces:
- figures/fig2_breakpoints.pdf: JS divergence time series with COP overlay
- figures/fig2_alluvial.pdf: Community flows across data-derived periods
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

from utils import BASE_DIR, CATALOGS_DIR, normalize_doi

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
args = parser.parse_args()


# ============================================================
# Step 0: Load data + embeddings
# ============================================================

print("Loading unified works...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "unified_works.csv"))
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
# Step 5: Label communities from top keywords
# ============================================================

# TF-IDF-like distinctive keyword extraction
# For each cluster, find keywords that are over-represented vs. corpus average
# Require both high distinctiveness AND meaningful frequency
import re as _re

generic = {"climate change", "climate finance", "climate", "finance", "economics",
           "business", "political science", "geography", "environmental science",
           "general economics, econometrics and finance", "general energy",
           "environmental economics", "development economics", "sustainable development",
           "developing countries", "renewable energy", "energy policy", ""}


def clean_keyword(kw):
    """Strip OpenAlex disambiguation parentheticals like '(medicine)', '(building)'."""
    return _re.sub(r"\s*\([^)]*\)\s*$", "", kw).strip()


# Corpus-wide keyword frequencies
all_kw_corpus = []
for kw_str in df["keywords"].dropna():
    all_kw_corpus.extend([clean_keyword(k.strip().lower()) for k in str(kw_str).split(";")])
corpus_counts = Counter(k for k in all_kw_corpus if k not in generic)
corpus_total = sum(corpus_counts.values())

cluster_labels = {}
for c in range(K_DEFAULT):
    members = df[df["cluster"] == c]
    cluster_kw = []
    for kw_str in members["keywords"].dropna():
        cluster_kw.extend([clean_keyword(k.strip().lower()) for k in str(kw_str).split(";")])
    cluster_counts = Counter(k for k in cluster_kw if k not in generic)
    cluster_total = sum(cluster_counts.values())
    if cluster_total == 0:
        cluster_labels[c] = f"Cluster {c}"
        continue

    # Score = TF-IDF × sqrt(count) to balance distinctiveness with frequency
    # Minimum 20 occurrences in cluster to avoid rare junk
    scored = []
    for kw, count in cluster_counts.items():
        if count < 20 or len(kw) < 3:
            continue
        tf = count / cluster_total
        df_corpus = corpus_counts.get(kw, 1) / corpus_total
        score = (tf / df_corpus) * np.sqrt(count)
        scored.append((kw, score, count))
    scored.sort(key=lambda x: -x[1])
    top3 = [kw for kw, _, _ in scored[:3]]
    cluster_labels[c] = " / ".join(top3) if top3 else f"Cluster {c}"

print("\nCluster labels:")
for c, label in cluster_labels.items():
    print(f"  {c}: {label}")


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

ax.axhline(1.5, color="black", linestyle=":", alpha=0.3, label="z = 1.5 threshold")
ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel("Z-scored JS divergence", fontsize=11)
ax.set_title("Structural break detection: embedding-based cluster redistribution over time",
             fontsize=12, pad=15)
ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "fig2_breakpoints.pdf"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FIGURES_DIR, "fig2_breakpoints.png"), dpi=150, bbox_inches="tight")
print(f"\nSaved Figure 2a → figures/fig2_breakpoints.pdf")
plt.close()


# ============================================================
# Step 7: Render alluvial figure
# ============================================================

fig, ax = plt.subplots(figsize=(14, 7))

n_periods = len(period_labels)
n_clusters = K_DEFAULT
palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))

# X positions for period columns
x_positions = np.linspace(0, 1, n_periods)
col_width = 0.06  # Half-width of each column bar

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
                        fontsize=7, color="black", fontweight="bold")

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
    ax.text(x, -0.03, period, ha="center", va="top", fontsize=9, fontweight="bold")

# Legend
handles = [mpatches.Patch(facecolor=palette[c], label=cluster_labels.get(c, f"Cluster {c}"))
           for c in range(n_clusters)]
ax.legend(handles=handles, loc="upper right", fontsize=7, framealpha=0.9,
          title="Intellectual communities", title_fontsize=8)

ax.set_xlim(-0.1, 1.1)
ax.set_ylim(-0.08, 1.0)
subtitle = ("periods from structural break detection"
            if not supplementary else
            f"2009 break data-derived; {', '.join(str(y) for y in supplementary)} COP-imposed")
ax.set_title(
    f"Intellectual community flows across periods\n"
    f"(KMeans clusters on abstract embeddings, {subtitle})",
    fontsize=12, pad=15,
)
ax.axis("off")

plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, "fig2_alluvial.pdf"), dpi=300, bbox_inches="tight")
fig.savefig(os.path.join(FIGURES_DIR, "fig2_alluvial.png"), dpi=150, bbox_inches="tight")
print(f"Saved Figure 2b → figures/fig2_alluvial.pdf")
plt.close()


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
    fig.savefig(os.path.join(FIGURES_DIR, "fig2_k_sensitivity.pdf"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIGURES_DIR, "fig2_k_sensitivity.png"), dpi=150, bbox_inches="tight")
    print(f"Saved k-sensitivity figure → figures/fig2_k_sensitivity.pdf")
    plt.close()

print("\nDone.")
