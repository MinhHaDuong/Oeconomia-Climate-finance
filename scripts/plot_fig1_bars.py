"""Fig 1 (bars): Corpus documents per year, 2000-2024.

Stacked bar chart showing total corpus size and the subset mentioning
"climate finance" in title or abstract. For Oeconomia submission.
"""

import argparse
import os
import re

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

from plot_style import (
    apply_style, FIGWIDTH, DPI, MED, LIGHT, DARK, FILL,
    INCOMPLETE_FROM, PERIODS, add_period_bands, add_period_lines,
)
from utils import CATALOGS_DIR, save_figure, BASE_DIR

apply_style()

matplotlib.rcParams.update({
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
})

CF_PATTERN = re.compile(r"\bclimate[\s-]?finance\b", re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser(description="Plot Fig 1 bar chart")
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF output")
    parser.add_argument("--v1-only", action="store_true",
                        help="Restrict to v1.0-submission corpus (in_v1==1)")
    args = parser.parse_args()

    # --- Load corpus ---
    csv_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    usecols = ["year", "title", "abstract"]
    if args.v1_only:
        usecols.append("in_v1")
    df = pd.read_csv(csv_path, usecols=usecols, dtype={"year": "Int64"})
    if args.v1_only:
        df = df[df["in_v1"] == 1]
    df = df[(df["year"] >= 1992) & (df["year"] <= 2023)].copy()

    # Flag papers mentioning "climate finance" in title or abstract
    title = df["title"].fillna("")
    abstract = df["abstract"].fillna("")
    df["has_cf"] = title.str.contains(CF_PATTERN) | abstract.str.contains(CF_PATTERN)

    yearly = df.groupby("year")["has_cf"].agg(["sum", "count"])
    yearly.columns = ["cf", "total"]
    yearly["other"] = yearly["total"] - yearly["cf"]
    yearly = yearly.sort_index()

    years = yearly.index.values
    cf = yearly["cf"].values
    other = yearly["other"].values

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.5))

    ax.bar(years, cf, color=DARK, edgecolor="white", linewidth=0.3,
           zorder=2, label='of which: "climate finance" in title or abstract')
    ax.bar(years, other, bottom=cf, color=LIGHT, edgecolor="white",
           linewidth=0.3, zorder=2, label="UNFCCC financial mechanism literature")

    # --- Period bands ---
    bands = [
        ("Before", 1990, 2007, FILL, 1999),
        ("Crystallisation", 2007, 2015, "#E8E8E8", None),
        ("Disputes", 2015, 2024, FILL, None),
    ]
    for label, x0, x1, color, label_x in bands:
        ax.axvspan(x0, x1, color=color, alpha=0.7, zorder=0, linewidth=0)
        cx = label_x if label_x else (x0 + x1) / 2
        ax.text(cx, 0.97, label, transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=8, fontstyle="italic",
                color=DARK)
    # Event labels at period boundaries
    for year, label in [
        (1992, "Rio\nUNFCCC\n(1992)"),
        (2007, "Bali\nAction Plan\n(2007)"),
        (2015, "Paris\nAgreement\n(2015)"),
    ]:
        ax.text(year, 0.88, label, transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=7.5, color=DARK,
                multialignment="center")

    # --- Legend (reverse order to match stacked bars: broader on top) ---
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1],
              loc="upper left", frameon=False, bbox_to_anchor=(0.0, 0.62))

    # --- Axes ---
    ax.set_xlim(1990, 2023.5)
    ax.set_xticks(range(1995, 2024, 5))
    ax.tick_params(axis="x", rotation=0)

    # No axis spines — ticks only
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_ylabel("")
    ax.set_xlabel("")

    # Replace topmost visible tick (4000) with "Number of works", no tick mark
    yticks = [t for t in ax.get_yticks() if t <= 4000]
    ylabels = [str(int(v)) for v in yticks]
    ylabels[-1] = "Number\nof works"
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=9)
    tick_labels = ax.get_yticklabels()
    tick_labels[-1].set_fontsize(10)
    tick_labels[-1].set_color(DARK)
    ax.yaxis.get_major_ticks()[-1].tick1line.set_visible(False)
    ax.yaxis.get_major_ticks()[-1].tick2line.set_visible(False)

    fig.tight_layout()

    # --- Save ---
    stem = "fig_bars_v1" if args.v1_only else "fig_bars"
    out_path = os.path.join(BASE_DIR, "content", "figures", stem)
    save_figure(fig, out_path, no_pdf=args.no_pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
