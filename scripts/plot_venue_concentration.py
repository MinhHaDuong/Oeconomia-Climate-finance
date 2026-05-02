#!/usr/bin/env python3
"""Plot venue concentration (HHI and Shannon entropy) over time.

Dual-panel figure: top panel = HHI, bottom panel = Shannon entropy.
Transition zones from tab_breakpoints.csv overlaid as vertical shaded bands.

Inputs:
  - content/tables/tab_venue_concentration.csv
  - content/tables/tab_breakpoints.csv (for transition zones)

Outputs:
  - content/figures/fig_venue_concentration.png

Usage:
    uv run python scripts/plot_venue_concentration.py \
        --output content/figures/fig_venue_concentration.png \
        --input content/tables/tab_venue_concentration.csv content/tables/tab_breakpoints.csv
"""

import os

import numpy as np
import pandas as pd
from plot_style import DARK, DPI, FIGWIDTH, FILL, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, save_figure

apply_style()
import matplotlib.pyplot as plt


def _get_transition_years(bp_df, top_n=2):
    """Extract years with highest Z-scores from breakpoints table.

    Returns the top_n years ranked by max absolute Z-score across
    JS and cosine w3 columns.
    """
    z_cols = [c for c in bp_df.columns if c.startswith("z_")]
    if not z_cols:
        return []
    bp_df = bp_df.copy()
    bp_df["z_max"] = bp_df[z_cols].abs().max(axis=1)
    top = bp_df.nlargest(top_n, "z_max")
    return sorted(top["year"].tolist())


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    import argparse

    parser = argparse.ArgumentParser(description="Plot venue concentration")
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    args = parser.parse_args(extra)

    # Load concentration data
    if io_args.input and len(io_args.input) >= 1:
        conc_path = io_args.input[0]
    else:
        conc_path = os.path.join(
            BASE_DIR, "content", "tables", "tab_venue_concentration.csv"
        )
    conc = pd.read_csv(conc_path)

    # Load breakpoints for transition zones
    if io_args.input and len(io_args.input) >= 2:
        bp_path = io_args.input[1]
    else:
        bp_path = os.path.join(BASE_DIR, "content", "tables", "tab_breakpoints.csv")

    transition_years = []
    if os.path.exists(bp_path):
        bp_df = pd.read_csv(bp_path)
        transition_years = _get_transition_years(bp_df)

    years = conc["year"].values
    hhi = conc["hhi"].values
    entropy = conc["shannon_entropy"].values

    # Dual-panel figure
    fig, (ax_hhi, ax_ent) = plt.subplots(
        2, 1, figsize=(FIGWIDTH, 4.5), sharex=True, gridspec_kw={"hspace": 0.15}
    )

    # Transition zone shading on both panels
    for yr in transition_years:
        for ax in (ax_hhi, ax_ent):
            ax.axvspan(yr - 0.5, yr + 0.5, color=FILL, alpha=0.5, zorder=0)

    # Top panel: HHI
    ax_hhi.plot(years, hhi, color=DARK, linewidth=1.0)
    ax_hhi.set_ylabel("HHI", fontsize=8)
    ax_hhi.tick_params(labelsize=7)
    ax_hhi.set_ylim(bottom=0)

    # Bottom panel: Shannon entropy
    ax_ent.plot(years, entropy, color=DARK, linewidth=1.0)
    ax_ent.set_ylabel("Shannon entropy", fontsize=8)
    ax_ent.set_xlabel("Year", fontsize=8)
    ax_ent.tick_params(labelsize=7)
    ax_ent.set_ylim(bottom=0)

    # Annotate transition years
    for yr in transition_years:
        idx = np.where(years == yr)[0]
        if len(idx) > 0:
            i = idx[0]
            ax_hhi.annotate(
                str(yr),
                xy=(yr, hhi[i]),
                xytext=(0, 6),
                textcoords="offset points",
                ha="center",
                fontsize=6,
                color=MED,
            )

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, pdf=args.pdf, dpi=DPI)


if __name__ == "__main__":
    main()
