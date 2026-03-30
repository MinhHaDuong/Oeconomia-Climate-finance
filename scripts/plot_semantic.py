"""Semantic landscape scatter plot, colored by a chosen variable.

Reads semantic_clusters.csv (produced by analyze_embeddings.py) and
refined_works.csv (for language/period metadata). Produces one figure
per invocation, parameterized by --color-by {cluster, language, period}.

Usage:
    uv run python plot_semantic.py --color-by cluster  --output fig_semantic.png
    uv run python plot_semantic.py --color-by language --output fig_semantic_lang.png
    uv run python plot_semantic.py --color-by period   --output fig_semantic_period.png
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from script_io_args import parse_io_args, validate_io
from utils import CATALOGS_DIR, get_logger, save_figure

log = get_logger("plot_semantic")

CLUSTERS_CSV = os.path.join(CATALOGS_DIR, "semantic_clusters.csv")


def _plot_cluster(df, ax):
    """Color by semantic cluster assignment."""
    n_clusters = df["semantic_cluster"].nunique()
    palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))
    for c in sorted(df["semantic_cluster"].unique()):
        members = df[df["semantic_cluster"] == c]
        ax.scatter(
            members["umap_x"], members["umap_y"],
            c=[palette[c]], s=8, alpha=0.5,
            label=f"Cluster {c} (n={len(members)})",
        )
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9, markerscale=3)
    ax.set_title(
        "Semantic landscape of climate finance literature\n"
        "(multilingual abstract embeddings, UMAP projection)",
        fontsize=13,
    )


def _plot_language(df, ax):
    """Color by language, highlighting non-English works."""
    lang_map = {
        "en": "English", "fr": "French", "zh": "Chinese",
        "ja": "Japanese", "de": "German", "es": "Spanish", "pt": "Portuguese",
    }
    df = df.copy()
    df["lang_label"] = df["language"].map(lang_map).fillna("Other")
    lang_colors = {
        "English": "lightgrey", "French": "#E63946", "Chinese": "#E9C46A",
        "Japanese": "#264653", "German": "#2A9D8F", "Spanish": "#F4A261",
        "Portuguese": "#606C38", "Other": "#ADB5BD",
    }
    en = df[df["lang_label"] == "English"]
    ax.scatter(
        en["umap_x"], en["umap_y"],
        c=lang_colors["English"], s=3, alpha=0.2,
        label=f"English (n={len(en)})",
    )
    for lang in ["French", "Chinese", "Japanese", "German", "Spanish", "Portuguese", "Other"]:
        subset = df[df["lang_label"] == lang]
        if len(subset) > 0:
            ax.scatter(
                subset["umap_x"], subset["umap_y"],
                c=lang_colors[lang], s=20, alpha=0.8,
                label=f"{lang} (n={len(subset)})",
                edgecolors="white", linewidths=0.3,
            )
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9, markerscale=2)
    ax.set_title(
        "Language distribution in the semantic landscape\n"
        "(non-English works highlighted)",
        fontsize=13,
    )


def _plot_period(df, ax):
    """Color by publication period."""
    period_map = {
        (1990, 2008): "1990\u20132008",
        (2009, 2015): "2009\u20132015",
        (2016, 2021): "2016\u20132021",
        (2022, 2024): "2022\u20132024",
    }
    period_colors = {
        "1990\u20132008": "#ADB5BD",
        "2009\u20132015": "#F4A261",
        "2016\u20132021": "#E76F51",
        "2022\u20132024": "#264653",
    }

    def assign_period(year):
        for (lo, hi), label in period_map.items():
            if lo <= year <= hi:
                return label
        return "Other"

    df = df.copy()
    df["period"] = df["year"].apply(assign_period)
    for period in ["1990\u20132008", "2009\u20132015", "2016\u20132021", "2022\u20132024"]:
        subset = df[df["period"] == period]
        ax.scatter(
            subset["umap_x"], subset["umap_y"],
            c=period_colors[period], s=5, alpha=0.4,
            label=f"{period} (n={len(subset)})",
        )
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9, markerscale=4)
    ax.set_title(
        "Temporal evolution of the semantic landscape\n"
        "(colored by article's periodization)",
        fontsize=13,
    )


PLOTTERS = {
    "cluster": _plot_cluster,
    "language": _plot_language,
    "period": _plot_period,
}


def main() -> None:
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--color-by", required=True, choices=["cluster", "language", "period"],
        help="Variable to color the scatter plot by",
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    args = parser.parse_args(extra)

    # Load data
    log.info("Loading clusters from %s", CLUSTERS_CSV)
    df = pd.read_csv(CLUSTERS_CSV)
    log.info("Loaded %d works with UMAP coordinates", len(df))

    # Plot
    sns.set_style("whitegrid")
    fig, ax = plt.subplots(figsize=(12, 9))
    PLOTTERS[args.color_by](df, ax)
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    plt.tight_layout()

    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf)
    log.info("Saved → %s", io_args.output)
    plt.close()


if __name__ == "__main__":
    main()
