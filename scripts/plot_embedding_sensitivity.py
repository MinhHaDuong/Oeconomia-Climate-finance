"""Plot embedding sensitivity analysis: PCA sweep and JL random projections.

Reads tab_sens_{pca,jl}_{method}.csv files and produces one figure per
(method, projection_type) pair.

PCA: one curve per dimension, color-coded from light (d=32) to dark (d=512),
     plus original in black.

JL:  fan/ribbon plot: median +/- IQR across 20 runs, one ribbon per dimension.

Usage:
    python3 scripts/plot_embedding_sensitivity.py \
        --output content/figures/fig_sensitivity.png \
        --input content/tables/tab_sens_pca_S1_MMD.csv
"""

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

log = get_logger("plot_embedding_sensitivity")

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

FIGWIDTH = 135 / 25.4   # ~5.3 inches
FIGHEIGHT = 3.2
DPI = 300

METHOD_LABELS = {
    "S1_MMD": "S1 MMD",
    "S2_energy": "S2 Energy distance",
    "S3_sliced_wasserstein": "S3 Sliced Wasserstein",
    "S4_frechet": "S4 Frechet distance",
}

# PCA dimension color scale: light (low d) to dark (high d)
PCA_COLORS = {
    32: "#bdbdbd",
    64: "#969696",
    128: "#737373",
    256: "#525252",
    512: "#252525",
}

# JL dimension colors
JL_COLORS = {
    64: "#1f77b4",
    128: "#ff7f0e",
    256: "#2ca02c",
}


def _parse_projection_tag(hyperparams):
    """Extract projection tag from hyperparams string.

    Returns (projection_type, dimension, run_number_or_None).
    Examples:
        'projection=original'     -> ('original', None, None)
        'projection=pca_128'      -> ('pca', 128, None)
        'projection=jl_64_run03'  -> ('jl', 64, 3)
    """
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


def _detect_method(df, filepath):
    """Detect method name from filename."""
    basename = os.path.basename(filepath)
    # Pattern: tab_sens_{pca,jl}_{method}.csv
    m = re.match(r"tab_sens_(?:pca|jl)_(.+)\.csv", basename)
    if m:
        return m.group(1)
    return None


def _detect_projection_type(df):
    """Detect whether this is PCA or JL data."""
    tags = df["hyperparams"].apply(lambda h: _parse_projection_tag(h)[0])
    if "pca" in tags.values:
        return "pca"
    if "jl" in tags.values:
        return "jl"
    return "unknown"


def _strip_projection_from_hp(hp):
    """Remove projection=... from hyperparams, returning the base hyperparams."""
    return re.sub(r";?projection=\S+", "", str(hp)).strip(";").strip()


def plot_pca(df, method, out_stem):
    """Plot PCA dimensionality sensitivity: one curve per dimension."""
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))

    # Parse projection info
    df = df.copy()
    parsed = df["hyperparams"].apply(_parse_projection_tag)
    df["proj_type"] = [p[0] for p in parsed]
    df["proj_dim"] = [p[1] for p in parsed]
    df["base_hp"] = df["hyperparams"].apply(_strip_projection_from_hp)

    # For methods with multiple hyperparams (e.g. S1 with bandwidth multipliers),
    # pick the first one (or default) for cleaner plotting
    base_hps = sorted(df["base_hp"].unique())
    # Use default/empty or first
    target_hp = ""
    for hp in base_hps:
        if hp in ("", "default"):
            target_hp = hp
            break
    if target_hp == "" and base_hps:
        target_hp = base_hps[0]

    sub = df[df["base_hp"] == target_hp].copy()

    # Plot original in black
    orig = sub[sub["proj_type"] == "original"].sort_values("year")
    if not orig.empty:
        ax.plot(orig["year"], orig["value"], color="black", linewidth=1.2,
                label="original (1024d)", zorder=10)

    # Plot each PCA dimension
    for d in sorted(PCA_COLORS.keys()):
        pca_d = sub[sub["proj_dim"] == d].sort_values("year")
        if pca_d.empty:
            continue
        ax.plot(pca_d["year"], pca_d["value"],
                color=PCA_COLORS[d], linewidth=0.9,
                label=f"PCA d={d}")

    label = METHOD_LABELS.get(method, method)
    hp_note = f" ({target_hp})" if target_hp and target_hp != "default" else ""
    ax.set_title(f"{label} — PCA dimensionality sensitivity{hp_note}")
    ax.set_xlabel("Year")
    ax.set_ylabel("Divergence value")

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best", frameon=False, fontsize=6)

    fig.tight_layout()
    out_path = f"{out_stem}_{method}_pca.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    log.info("Saved PCA plot: %s", out_path)


def plot_jl(df, method, out_stem):
    """Plot JL random projection stability: fan/ribbon (median +/- IQR)."""
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGHEIGHT))

    # Parse projection info
    df = df.copy()
    parsed = df["hyperparams"].apply(_parse_projection_tag)
    df["proj_type"] = [p[0] for p in parsed]
    df["proj_dim"] = [p[1] for p in parsed]
    df["run"] = [p[2] for p in parsed]
    df["base_hp"] = df["hyperparams"].apply(_strip_projection_from_hp)

    # Pick one base hyperparam setting for clarity
    base_hps = sorted(df["base_hp"].unique())
    target_hp = ""
    for hp in base_hps:
        if hp in ("", "default"):
            target_hp = hp
            break
    if target_hp == "" and base_hps:
        target_hp = base_hps[0]

    sub = df[(df["base_hp"] == target_hp) & (df["proj_type"] == "jl")].copy()

    for d in sorted(JL_COLORS.keys()):
        dim_data = sub[sub["proj_dim"] == d]
        if dim_data.empty:
            continue

        # Compute median and IQR per year
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
    hp_note = f" ({target_hp})" if target_hp and target_hp != "default" else ""
    ax.set_title(f"{label} — Random projection stability (JL){hp_note}")
    ax.set_xlabel("Year")
    ax.set_ylabel("Divergence value")

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best", frameon=False, fontsize=6)

    fig.tight_layout()
    out_path = f"{out_stem}_{method}_jl.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    log.info("Saved JL plot: %s", out_path)


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    if not io_args.input:
        log.error("No --input files provided")
        sys.exit(1)

    out_stem = os.path.splitext(io_args.output)[0]

    for path in io_args.input:
        if not os.path.exists(path):
            log.warning("Input not found: %s", path)
            continue

        df = pd.read_csv(path)
        method = _detect_method(df, path)
        if method is None:
            log.warning("Cannot determine method from filename: %s", path)
            continue

        proj_type = _detect_projection_type(df)
        if proj_type == "pca":
            plot_pca(df, method, out_stem)
        elif proj_type == "jl":
            plot_jl(df, method, out_stem)
        else:
            log.warning("Unknown projection type in %s; skipping", path)

    log.info("All sensitivity plots done.")


if __name__ == "__main__":
    main()
