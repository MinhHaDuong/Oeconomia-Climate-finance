"""Lexical TF-IDF bar charts at structural break years.

Reads:  refined_works.csv,
        tab_breakpoint_robustness.csv (for detected break years)
Writes: fig_lexical_tfidf_{year}.png (and .pdf unless --no-pdf) for each break year

Flags: --no-pdf

Run compute_breakpoints.py and compute_lexical.py first.

Note: This script re-reads refined_works.csv and re-computes TF-IDF rather than
reading tab_lexical_tfidf.csv, because:
  - The table only stores the main break year comparison
  - This script generates charts for all detected breaks + control years (2015, 2021)
  - Each break year requires a separate TF-IDF vocabulary (different before/after split)
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from utils import BASE_DIR, save_figure, load_analysis_corpus

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

# --- Args ---
parser = argparse.ArgumentParser(description="Plot lexical TF-IDF bar charts at break years")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
args = parser.parse_args()

from compute_lexical import EXTRA_STOPS, MIN_PERIOD_DF, is_clean_term


# --- Load data ---
df, _ = load_analysis_corpus(with_embeddings=False)
print(f"Loaded {len(df)} works")

robust_path = os.path.join(TABLES_DIR, "tab_breakpoint_robustness.csv")
try:
    robust_df = pd.read_csv(robust_path)
except FileNotFoundError:
    raise FileNotFoundError(
        f"Missing {robust_path}. Run: uv run python scripts/compute_breakpoints.py"
    )
detected_breaks = sorted(robust_df["year"].tolist()[:3])
print(f"Detected break years: {detected_breaks}")


def _compute_tfidf(df_works, break_year, window_after=3):
    """Compute TF-IDF matrices for a before/after comparison at break_year.

    Returns (X, names, nA, nB) or None if too few abstracts.
    """
    mA = df_works["year"] < break_year
    mB = (df_works["year"] >= break_year + 1) & (df_works["year"] <= break_year + window_after)
    tA = df_works.loc[mA, "abstract"].dropna().tolist()
    tB = df_works.loc[mB, "abstract"].dropna().tolist()
    nA, nB = len(tA), len(tB)
    if nA < 5 or nB < 5:
        return None
    vec = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2),
        min_df=3, max_df=0.9, sublinear_tf=True,
    )
    X = vec.fit_transform(tA + tB)
    return X, np.array(vec.get_feature_names_out()), nA, nB


def _plot_from_precomputed(X, names, nA, nB, break_year, window_after=3, n_show=20,
                           suffix="", xlim=None):
    """Plot lexical comparison figure from pre-computed TF-IDF matrices.

    Writes: fig_lexical_tfidf{suffix}.png
    """
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

    # Denoising (uses shared is_clean_term from compute_lexical)
    dfA = np.asarray((X[:nA] > 0).sum(axis=0)).flatten()
    dfB = np.asarray((X[nA:] > 0).sum(axis=0)).flatten()
    ok = np.zeros(len(names), dtype=bool)
    for i, t in enumerate(names):
        if not is_clean_term(t):
            continue
        if d[i] < 0 and dfA[i] >= MIN_PERIOD_DF:
            ok[i] = True
        elif d[i] > 0 and dfB[i] >= MIN_PERIOD_DF:
            ok[i] = True
    clean_idx = np.where(ok)[0]
    d_clean = d[ok]
    idx_after = clean_idx[np.argsort(d_clean)[-n_show:][::-1]]
    idx_before = clean_idx[np.argsort(d_clean)[:n_show]]

    terms = list(names[idx_before][::-1]) + list(names[idx_after])
    diffs = list(d[idx_before][::-1]) + list(d[idx_after])

    fig, ax = plt.subplots(figsize=(10, 10))
    colors = ["#457B9D" if v < 0 else "#E63946" for v in diffs]
    y = range(len(terms))
    ax.barh(y, diffs, color=colors, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(terms, fontsize=8)
    ax.axvline(0, color="black", linewidth=0.8)

    ax.axvspan(-sig_95, sig_95, alpha=0.08, color="grey", zorder=0)
    ax.axvline(-sig_95, color="black", linestyle=":", alpha=0.3, linewidth=0.8)
    ax.axvline(sig_95, color="black", linestyle=":", alpha=0.3, linewidth=0.8)
    ax.axvline(-sig_99, color="black", linestyle="--", alpha=0.3, linewidth=0.8)
    ax.axvline(sig_99, color="black", linestyle="--", alpha=0.3, linewidth=0.8)
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

    ax.axhline(n_show - 0.5, color="grey", linewidth=0.5, linestyle="--", alpha=0.5)

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
    print(f"    Saved {fname}.png (A={nA}, B={nB})")
    plt.close()


# --- Compute TF-IDF once per break year, then plot with shared x-axis scale ---
break_years = sorted(detected_breaks) + [yr for yr in [2015, 2021] if yr not in detected_breaks]

# Step 1: compute all TF-IDF matrices (one pass)
tfidf_cache = {}
for yr in break_years:
    result = _compute_tfidf(df, yr)
    if result is None:
        print(f"  Skipping {yr}: too few abstracts")
        continue
    tfidf_cache[yr] = result

# Step 2: find shared x-axis range from cached matrices
global_max = 0
for yr, (X, names, nA, nB) in tfidf_cache.items():
    mA_v = np.asarray(X[:nA].mean(axis=0)).flatten()
    mB_v = np.asarray(X[nA:].mean(axis=0)).flatten()
    global_max = max(global_max, np.max(np.abs(mB_v - mA_v)))
shared_xlim = (-global_max * 1.15, global_max * 1.15)
print(f"Shared x-axis range: [{shared_xlim[0]:.4f}, {shared_xlim[1]:.4f}]")

# Step 3: generate figures using cached matrices (no re-computation)
for yr in break_years:
    if yr not in tfidf_cache:
        continue
    X, names, nA, nB = tfidf_cache[yr]
    print(f"\nBreak year {yr}:")
    _plot_from_precomputed(X, names, nA, nB, yr, suffix=f"_{yr}", xlim=shared_xlim)

print("\nDone.")
