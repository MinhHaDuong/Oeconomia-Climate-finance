"""Lexical TF-IDF bar charts at structural break years.

Reads:  tab_lexical_tfidf.csv (pre-computed by compute_lexical.py)
Writes: fig_lexical_tfidf_{year}.png (and .pdf if --pdf) for each break year

The --output path is used as a stamp file (touched after all figures are
written) because the number of output files depends on the data.

Usage:
    uv run python scripts/plot_fig_lexical_tfidf.py --output .lexical_tfidf.stamp
    uv run python scripts/plot_fig_lexical_tfidf.py --output .lexical_tfidf.stamp \
        --input content/tables/tab_lexical_tfidf.csv [--pdf]
"""

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, save_figure

log = get_logger("plot_fig_lexical_tfidf")


def _plot_break_year(tdf, break_year, figures_dir, n_show=20,
                     xlim=None, pdf=False):
    """Plot lexical comparison figure from pre-computed TF-IDF table rows.

    tdf: DataFrame subset for one break_year (columns: term, diff, clean, etc.)
    """
    n_before = tdf["n_before"].iloc[0]
    n_after = tdf["n_after"].iloc[0]
    sig_95 = tdf["sig_95"].iloc[0]
    sig_99 = tdf["sig_99"].iloc[0]
    window_after = 3  # matches compute_lexical.py WINDOW_AFTER

    log.info("  Permutation thresholds: p<0.05=%.4f, p<0.01=%.4f",
             sig_95, sig_99)

    # Filter to clean terms only
    clean = tdf[tdf["clean"]].copy()
    clean_sorted = clean.sort_values("diff")

    # Top N rising and falling terms
    top_after = clean_sorted.tail(n_show).iloc[::-1]
    top_before = clean_sorted.head(n_show)

    terms = (list(top_before["term"].values[::-1])
             + list(top_after["term"].values))
    diffs = (list(top_before["diff"].values[::-1])
             + list(top_after["diff"].values))

    fig, ax = plt.subplots(figsize=(10, 10))
    colors = ["#457B9D" if v < 0 else "#E63946" for v in diffs]
    y = range(len(terms))
    ax.barh(y, diffs, color=colors, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(terms, fontsize=8)
    ax.axvline(0, color="black", linewidth=0.8)

    ax.axvspan(-sig_95, sig_95, alpha=0.08, color="grey", zorder=0)
    ax.axvline(-sig_95, color="black", linestyle=":", alpha=0.3,
               linewidth=0.8)
    ax.axvline(sig_95, color="black", linestyle=":", alpha=0.3,
               linewidth=0.8)
    ax.axvline(-sig_99, color="black", linestyle="--", alpha=0.3,
               linewidth=0.8)
    ax.axvline(sig_99, color="black", linestyle="--", alpha=0.3,
               linewidth=0.8)
    ax.text(sig_95, len(terms) + 0.3, "p<.05", fontsize=7,
            ha="center", color="black", alpha=0.5)
    ax.text(sig_99, len(terms) + 0.3, "p<.01", fontsize=7,
            ha="center", color="black", alpha=0.5)
    ax.text(-sig_95, len(terms) + 0.3, "p<.05", fontsize=7,
            ha="center", color="black", alpha=0.5)
    ax.text(-sig_99, len(terms) + 0.3, "p<.01", fontsize=7,
            ha="center", color="black", alpha=0.5)

    ax.set_xlabel("\u0394TF-IDF (after \u2212 before)", fontsize=11)
    if xlim is not None:
        ax.set_xlim(xlim)

    ax.axhline(n_show - 0.5, color="grey", linewidth=0.5,
               linestyle="--", alpha=0.5)

    ax.annotate(f"\u2190 Before {break_year}  (n={n_before})", xy=(0, 0),
                xytext=(0.02, 0.02), textcoords="axes fraction",
                fontsize=10, color="#457B9D", fontweight="bold")
    ax.annotate(f"After {break_year} \u2192  (n={n_after})", xy=(0, 1),
                xytext=(0.75, 0.97), textcoords="axes fraction",
                fontsize=10, color="#E63946", fontweight="bold")

    after_label = f"{break_year+1}\u2013{break_year+window_after}"
    ax.set_title(
        f"Lexical comparison around {break_year}\n"
        f"(before {break_year}: {n_before} abstracts, "
        f"{after_label}: {n_after} abstracts)",
        fontsize=12, pad=15,
    )

    plt.tight_layout()
    fname = f"fig_lexical_tfidf_{break_year}"
    save_figure(fig, os.path.join(figures_dir, fname), pdf=pdf)
    log.info("    Saved %s.png (A=%d, B=%d)", fname, n_before, n_after)
    plt.close()


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output, inputs=io_args.input)

    parser = argparse.ArgumentParser(
        description="Plot lexical TF-IDF bar charts at break years")
    parser.add_argument("--pdf", action="store_true",
                        help="Also save PDF output")
    args = parser.parse_args(extra)

    figures_dir = os.path.join(BASE_DIR, "content", "figures")
    tables_dir = os.path.join(BASE_DIR, "content", "tables")
    os.makedirs(figures_dir, exist_ok=True)

    # --- Input resolution ---
    tfidf_path = (
        io_args.input[0] if io_args.input
        else os.path.join(tables_dir, "tab_lexical_tfidf.csv")
    )

    # --- Load pre-computed TF-IDF table ---
    try:
        tfidf_all = pd.read_csv(tfidf_path)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Missing {tfidf_path}. "
            "Run: uv run python scripts/compute_lexical.py"
        ) from None

    break_years = sorted(tfidf_all["break_year"].unique())
    log.info("Loaded %d rows for break years: %s",
             len(tfidf_all), break_years)

    # Compute shared x-axis range across all break years
    global_max = 0
    for yr in break_years:
        subset = tfidf_all[tfidf_all["break_year"] == yr]
        clean_diffs = subset.loc[subset["clean"], "diff"].abs()
        if len(clean_diffs) > 0:
            global_max = max(global_max, clean_diffs.max())
    shared_xlim = (-global_max * 1.15, global_max * 1.15)
    log.info("Shared x-axis range: [%.4f, %.4f]",
             shared_xlim[0], shared_xlim[1])

    # Generate figures
    for yr in break_years:
        subset = tfidf_all[tfidf_all["break_year"] == yr]
        log.info("Break year %d:", yr)
        _plot_break_year(subset, yr, figures_dir,
                         xlim=shared_xlim, pdf=args.pdf)

    # Touch stamp file
    with open(io_args.output, "w") as f:
        f.write(f"Generated {len(break_years)} figures\n")

    log.info("Done.")


if __name__ == "__main__":
    main()
