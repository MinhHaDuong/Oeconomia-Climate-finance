"""Plot one embedding sensitivity figure (PCA or JL).

Reads a single tab_sens_{pca,jl}_{method}.csv and produces one PNG.

PCA: one curve per dimension, light (d=32) to dark (d=512), black for original.
JL:  fan/ribbon plot with median +/- IQR across runs, one ribbon per dimension.

Usage:
    python3 scripts/plot_sensitivity.py --projection pca \
        --input content/tables/tab_sens_pca_S1_MMD.csv \
        --output content/figures/fig_sensitivity_pca_S1_MMD.png

    python3 scripts/plot_sensitivity.py --projection jl \
        --input content/tables/tab_sens_jl_S2_energy.csv \
        --output content/figures/fig_sensitivity_jl_S2_energy.png
"""

import argparse
import os
import re
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_sensitivity")

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.size": 8,
    "axes.titlesize": 10,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 6,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "axes.linewidth": 0.5,
    "lines.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
})

FIGWIDTH = 135 / 25.4
FIGHEIGHT = 3.2
DPI = 300

METHOD_LABELS = {
    "S1_MMD": "S1 MMD",
    "S2_energy": "S2 Energy distance",
    "S3_sliced_wasserstein": "S3 Sliced Wasserstein",
    "S4_frechet": "S4 Frechet distance",
}

PCA_COLORS = {32: "#bdbdbd", 64: "#969696", 128: "#737373", 256: "#525252", 512: "#252525"}
JL_COLORS = {64: "#1f77b4", 128: "#ff7f0e", 256: "#2ca02c"}


def _parse_projection_tag(hyperparams):
    """Extract projection tag from hyperparams string."""
    match = re.search(r"projection=(\S+)", str(hyperparams))
    if not match:
        return None, None, None
    tag = match.group(1)
    if tag == "original":
        return "original", None, None
    m = re.match(r"pca_(\d+)", tag)
    if m:
        return "pca", int(m.group(1)), None
    m = re.match(r"jl_(\d+)_run(\d+)", tag)
    if m:
        return "jl", int(m.group(1)), int(m.group(2))
    return tag, None, None


def _strip_projection_from_hp(hp):
    return re.sub(r";?projection=\S+", "", str(hp)).strip(";").strip()


def _detect_method(filepath):
    m = re.match(r"tab_sens_(?:pca|jl)_(.+)\.csv", os.path.basename(filepath))
    return m.group(1) if m else "unknown"


def _pick_base_hp(df):
    """Pick a single base hyperparam setting for clean plotting."""
    base_hps = sorted(df["base_hp"].unique())
    for hp in base_hps:
        if hp in ("", "default"):
            return hp
    return base_hps[0] if base_hps else ""


def plot_pca(df, method, output_path):
    """One figure: one curve per PCA dimension + original baseline."""
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))

    df = df.copy()
    parsed = df["hyperparams"].apply(_parse_projection_tag)
    df["proj_type"] = [p[0] for p in parsed]
    df["proj_dim"] = [p[1] for p in parsed]
    df["base_hp"] = df["hyperparams"].apply(_strip_projection_from_hp)

    target_hp = _pick_base_hp(df)
    sub = df[df["base_hp"] == target_hp]

    orig = sub[sub["proj_type"] == "original"].sort_values("year")
    if not orig.empty:
        ax.plot(orig["year"], orig["value"], color="black", linewidth=1.2,
                label="original (1024d)", zorder=10)

    for d in sorted(PCA_COLORS.keys()):
        pca_d = sub[sub["proj_dim"] == d].sort_values("year")
        if not pca_d.empty:
            ax.plot(pca_d["year"], pca_d["value"],
                    color=PCA_COLORS[d], linewidth=0.9, label=f"PCA d={d}")

    label = METHOD_LABELS.get(method, method)
    ax.set_title(f"{label} — PCA dimensionality sensitivity")
    ax.set_xlabel("Year")
    ax.set_ylabel("Divergence value")
    ax.legend(loc="best", frameon=False, fontsize=6)
    fig.tight_layout()
    fig.savefig(output_path, dpi=DPI)
    plt.close(fig)
    log.info("Saved %s", output_path)


def plot_jl(df, method, output_path):
    """One figure: fan/ribbon (median ± IQR) per JL dimension."""
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))

    df = df.copy()
    parsed = df["hyperparams"].apply(_parse_projection_tag)
    df["proj_type"] = [p[0] for p in parsed]
    df["proj_dim"] = [p[1] for p in parsed]
    df["run"] = [p[2] for p in parsed]
    df["base_hp"] = df["hyperparams"].apply(_strip_projection_from_hp)

    target_hp = _pick_base_hp(df)
    sub = df[(df["base_hp"] == target_hp) & (df["proj_type"] == "jl")]

    for d in sorted(JL_COLORS.keys()):
        dim_data = sub[sub["proj_dim"] == d]
        if dim_data.empty:
            continue
        stats = dim_data.groupby("year")["value"].agg(
            ["median", lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
        ).reset_index()
        stats.columns = ["year", "median", "q25", "q75"]
        stats = stats.sort_values("year")

        color = JL_COLORS[d]
        ax.fill_between(stats["year"], stats["q25"], stats["q75"],
                        alpha=0.25, color=color)
        ax.plot(stats["year"], stats["median"], color=color, linewidth=1.0,
                label=f"JL d={d} (median ± IQR)")

    label = METHOD_LABELS.get(method, method)
    ax.set_title(f"{label} — Random projection stability (JL)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Divergence value")
    ax.legend(loc="best", frameon=False, fontsize=6)
    fig.tight_layout()
    fig.savefig(output_path, dpi=DPI)
    plt.close(fig)
    log.info("Saved %s", output_path)


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--projection", required=True, choices=["pca", "jl"])
    args = parser.parse_args(extra)

    if not io_args.input:
        log.error("--input required")
        sys.exit(1)

    input_path = io_args.input[0]
    df = pd.read_csv(input_path)
    method = _detect_method(input_path)

    if args.projection == "pca":
        plot_pca(df, method, io_args.output)
    else:
        plot_jl(df, method, io_args.output)


if __name__ == "__main__":
    main()
