"""Lexical TF-IDF bar charts at structural break years.

Reads:  tab_lexical_tfidf.csv (pre-computed by compute_lexical.py)
Writes: fig_lexical_tfidf_{year}.png (and .pdf unless --no-pdf) for each break year

Flags: --no-pdf

Run compute_breakpoints.py and compute_lexical.py first.
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from utils import BASE_DIR, save_figure

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

# --- Args ---
parser = argparse.ArgumentParser(description="Plot lexical TF-IDF bar charts at break years")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
args = parser.parse_args()


def _plot_break_year(tdf, break_year, n_show=20, xlim=None, no_pdf=False):
    """Plot lexical comparison figure from pre-computed TF-IDF table rows.

    tdf: DataFrame subset for one break_year (columns: term, diff, clean, etc.)
    """
    n_before = tdf["n_before"].iloc[0]
    n_after = tdf["n_after"].iloc[0]
    sig_95 = tdf["sig_95"].iloc[0]
    sig_99 = tdf["sig_99"].iloc[0]
    window_after = 3  # matches compute_lexical.py WINDOW_AFTER

    print(f"  Permutation thresholds: p<0.05={sig_95:.4f}, p<0.01={sig_99:.4f}")

    # Filter to clean terms only
    clean = tdf[tdf["clean"]].copy()
    clean_sorted = clean.sort_values("diff")

    # Top N rising and falling terms
    top_after = clean_sorted.tail(n_show).iloc[::-1]
    top_before = clean_sorted.head(n_show)

    terms = list(top_before["term"].values[::-1]) + list(top_after["term"].values)
    diffs = list(top_before["diff"].values[::-1]) + list(top_after["diff"].values)

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

    ax.annotate(f"← Before {break_year}  (n={n_before})", xy=(0, 0),
                xytext=(0.02, 0.02), textcoords="axes fraction",
                fontsize=10, color="#457B9D", fontweight="bold")
    ax.annotate(f"After {break_year} →  (n={n_after})", xy=(0, 1),
                xytext=(0.75, 0.97), textcoords="axes fraction",
                fontsize=10, color="#E63946", fontweight="bold")

    after_label = f"{break_year+1}–{break_year+window_after}"
    ax.set_title(
        f"Lexical comparison around {break_year}\n"
        f"(before {break_year}: {n_before} abstracts, {after_label}: {n_after} abstracts)",
        fontsize=12, pad=15,
    )

    plt.tight_layout()
    fname = f"fig_lexical_tfidf_{break_year}"
    save_figure(fig, os.path.join(FIGURES_DIR, fname), no_pdf=no_pdf)
    print(f"    Saved {fname}.png (A={n_before}, B={n_after})")
    plt.close()


# --- Load pre-computed TF-IDF table ---
tfidf_path = os.path.join(TABLES_DIR, "tab_lexical_tfidf.csv")
try:
    tfidf_all = pd.read_csv(tfidf_path)
except FileNotFoundError:
    raise FileNotFoundError(
        f"Missing {tfidf_path}. Run: uv run python scripts/compute_lexical.py"
    ) from None

break_years = sorted(tfidf_all["break_year"].unique())
print(f"Loaded {len(tfidf_all)} rows for break years: {break_years}")

# Compute shared x-axis range across all break years
global_max = 0
for yr in break_years:
    subset = tfidf_all[tfidf_all["break_year"] == yr]
    clean_diffs = subset.loc[subset["clean"], "diff"].abs()
    if len(clean_diffs) > 0:
        global_max = max(global_max, clean_diffs.max())
shared_xlim = (-global_max * 1.15, global_max * 1.15)
print(f"Shared x-axis range: [{shared_xlim[0]:.4f}, {shared_xlim[1]:.4f}]")

# Generate figures
for yr in break_years:
    subset = tfidf_all[tfidf_all["break_year"] == yr]
    print(f"\nBreak year {yr}:")
    _plot_break_year(subset, yr, xlim=shared_xlim, no_pdf=args.no_pdf)

print("\nDone.")
