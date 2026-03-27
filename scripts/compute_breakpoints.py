"""Structural break detection from embedding-based divergence series.

Reads:  refined_works.csv, refined_embeddings.npz
Writes: tab_breakpoints.csv, tab_breakpoint_robustness.csv
        tab_k_sensitivity.csv (--robustness only)

Flags:
  --core-only     Restrict to highly-cited papers (cited_by_count >= 50)
  --censor-gap N  Censor N transition years before each test point (default: 0)
  --robustness    Also run k-sensitivity table (k=4,5,6,7)
  --no-pdf        Accepted for interface compatibility; no-op (no figures generated)

Note: The k-sensitivity *figure* is produced by plot_fig_k_sensitivity.py.
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
from scipy.spatial.distance import cosine as cosine_dist
from scipy.stats import pearsonr
from sklearn.cluster import KMeans
from utils import BASE_DIR, get_logger, load_analysis_corpus

log = get_logger("compute_breakpoints")

warnings.filterwarnings("ignore", category=FutureWarning)

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Args ---
parser = argparse.ArgumentParser(description="Compute structural break tables")
parser.add_argument("--robustness", action="store_true", help="Run k-sensitivity analysis")
parser.add_argument("--no-pdf", action="store_true", help="No-op (no figures generated here)")
parser.add_argument("--core-only", action="store_true",
                    help="Restrict to core papers (cited_by_count >= 50)")
parser.add_argument("--censor-gap", type=int, default=0,
                    help="Number of transition years to censor before each test point (default: 0)")
args = parser.parse_args()

# Output naming depends on mode
TAB_BP = "tab_breakpoints_core.csv" if args.core_only else "tab_breakpoints.csv"
TAB_BP_ROBUST = ("tab_breakpoint_robustness_core.csv" if args.core_only
                 else "tab_breakpoint_robustness.csv")
if args.censor_gap > 0:
    suffix = f"_censor{args.censor_gap}"
    TAB_BP = TAB_BP.replace(".csv", f"{suffix}.csv")
    TAB_BP_ROBUST = TAB_BP_ROBUST.replace(".csv", f"{suffix}.csv")


# ============================================================
# Step 1: Load data + embeddings
# ============================================================

df, embeddings = load_analysis_corpus(core_only=args.core_only)
log.info("Loaded %d works, embeddings shape: %s", len(df), embeddings.shape)

K_DEFAULT = 6
N_MIN = 20 if args.core_only else 30


# ============================================================
# Step 2: Sliding-window divergence series
# ============================================================

def compute_js_divergence(p, q):
    """Jensen-Shannon divergence between two probability distributions."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    p = p / p.sum() if p.sum() > 0 else p
    q = q / q.sum() if q.sum() > 0 else q
    m = 0.5 * (p + q)
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
    km = KMeans(n_clusters=k, random_state=42, n_init=20)
    labels = km.fit_predict(embeddings)

    results = {}
    for w in window_sizes:
        js_series = {}
        cos_series = {}
        for y in range(start_year, end_year + 1):
            mask_before = (df["year"] >= y - w - censor_gap) & (df["year"] <= y - censor_gap)
            mask_after = (df["year"] >= y + 1) & (df["year"] <= y + 1 + w)

            idx_before = df.index[mask_before]
            idx_after = df.index[mask_after]

            if len(idx_before) < N_MIN or len(idx_after) < N_MIN:
                js_series[y] = np.nan
                cos_series[y] = np.nan
                continue

            labels_before = labels[idx_before]
            labels_after = labels[idx_after]
            prop_before = np.bincount(labels_before, minlength=k) / len(labels_before)
            prop_after = np.bincount(labels_after, minlength=k) / len(labels_after)
            js_series[y] = compute_js_divergence(prop_before, prop_after)

            emb_before = embeddings[idx_before].mean(axis=0)
            emb_after = embeddings[idx_after].mean(axis=0)
            cos_series[y] = cosine_dist(emb_before, emb_after)

        results[w] = {"js": js_series, "cos": cos_series}
    return results


WINDOW_SIZES = [2, 3, 4]

log.info("=== Structural break detection ===")
log.info("Window sizes: %s, start year: 2005, n_min: %d, censor_gap: %d",
         WINDOW_SIZES, N_MIN, args.censor_gap)

div_results = compute_divergence_series(
    df, embeddings, K_DEFAULT, WINDOW_SIZES, start_year=2005, end_year=2023,
    censor_gap=args.censor_gap
)

years = list(range(2005, 2024))
bp_data = {"year": years}
for w in WINDOW_SIZES:
    bp_data[f"js_w{w}"] = [div_results[w]["js"].get(y, np.nan) for y in years]
    bp_data[f"cos_w{w}"] = [div_results[w]["cos"].get(y, np.nan) for y in years]

bp_df = pd.DataFrame(bp_data)

for metric in ["js", "cos"]:
    for w in WINDOW_SIZES:
        col = f"{metric}_w{w}"
        vals = bp_df[col].dropna()
        if len(vals) > 1 and vals.std() > 0:
            bp_df[f"z_{col}"] = (bp_df[col] - vals.mean()) / vals.std()
        else:
            bp_df[f"z_{col}"] = np.nan

bp_df.to_csv(os.path.join(TABLES_DIR, TAB_BP), index=False)
log.info("Saved divergence table -> tables/%s", TAB_BP)


# ============================================================
# Step 3: Detect robust breakpoints
# ============================================================

def find_local_maxima(series, threshold=1.5):
    """Find local maxima above z-score threshold. Returns list of (year, z_score)."""
    peaks = []
    years_list = list(series.dropna().index)
    for i, y in enumerate(years_list):
        z = series.loc[y]
        if np.isnan(z) or z <= threshold:
            continue
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


bp_indexed = bp_df.set_index("year")
candidates = {"js": {}, "cos": {}}
for metric in ["js", "cos"]:
    for w in WINDOW_SIZES:
        col = f"z_{metric}_w{w}"
        if col in bp_indexed.columns:
            candidates[metric][w] = find_local_maxima(bp_indexed[col])

robust_js = find_robust_breakpoints(candidates["js"], WINDOW_SIZES)
robust_cos = find_robust_breakpoints(candidates["cos"], WINDOW_SIZES)

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
log.info("Saved robustness table -> tables/%s", TAB_BP_ROBUST)

log.info("=== Robust breakpoints ===")
for bp in robust_list[:5]:
    log.info("  %d: JS z=%s, cos z=%s, support=%s",
             bp['year'], bp['js_mean_z'], bp['cos_mean_z'], bp['support'])

detected_breaks = sorted([bp["year"] for bp in robust_list[:3]])
log.info("Detected robust breakpoints: %s", detected_breaks)

# Step 4: Volume confound check
log.info("=== Volume confound check ===")
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
            log.info("  %s vs volume growth: r=%.3f, p=%.3f%s", col, r, p, flag)


# ============================================================
# Step 5: K-sensitivity table (figure in plot_fig_k_sensitivity.py)
# ============================================================

if args.robustness and not args.core_only:
    log.info("=== Robustness: k-sensitivity (k=4,5,6,7) ===")
    k_values = [4, 5, 6, 7]
    k_results = {}

    for k in k_values:
        log.info("  Running k=%d...", k)
        res = compute_divergence_series(
            df, embeddings, k, [3], start_year=2005, end_year=2023,
            censor_gap=args.censor_gap
        )
        k_results[k] = res[3]["js"]

    k_data = {"year": years}
    for k in k_values:
        k_data[f"js_k{k}"] = [k_results[k].get(y, np.nan) for y in years]
    k_df = pd.DataFrame(k_data)
    k_df.to_csv(os.path.join(TABLES_DIR, "tab_k_sensitivity.csv"), index=False)
    log.info("Saved k-sensitivity table -> tables/tab_k_sensitivity.csv")
    log.info("Run plot_fig_k_sensitivity.py to generate the figure.")

log.info("Done.")
