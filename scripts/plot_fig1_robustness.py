#!/usr/bin/env python3
"""Plot Figure A.1a: robustness checks across three datasets.

Panels:
  A. OpenAlex — Economics concept (with Econ/Finance overlap)
  B. OpenAlex — Finance concept (with Econ/Finance overlap)
  C. RePEc — Economics proxy (sparse, lollipop style)

Bars in panels A and B are stacked: green = tagged with both Economics
and Finance concepts; blue = exclusive to that panel's concept scope.
Overlap computed from ID-level set operations (count_openalex_econ_fin_overlap.py).

Inputs:
  - $DATA/catalogs/openalex_econ_yearly.csv
  - $DATA/catalogs/openalex_finance_yearly.csv
  - $DATA/catalogs/openalex_econ_fin_overlap.csv
  - $DATA/catalogs/repec_econ_yearly.csv

Outputs:
  - figures/figA_1a_robustness.png (+.pdf unless --no-pdf)

Usage:
  uv run python scripts/plot_fig1_robustness.py [--no-pdf]
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

sys.path.insert(0, os.path.dirname(__file__))
from utils import BASE_DIR, CATALOGS_DIR, save_figure
from plot_helpers import C_SHARE, load_series, plot_panel


def main():
    parser = argparse.ArgumentParser(description="Plot Figure A.1a robustness checks")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    args = parser.parse_args()

    p_econ = os.path.join(CATALOGS_DIR, "openalex_econ_yearly.csv")
    p_fin = os.path.join(CATALOGS_DIR, "openalex_finance_yearly.csv")
    p_overlap = os.path.join(CATALOGS_DIR, "openalex_econ_fin_overlap.csv")
    p_repec = os.path.join(CATALOGS_DIR, "repec_econ_yearly.csv")

    missing = [p for p in [p_econ, p_fin, p_overlap, p_repec] if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError("Missing required input files:\n- " + "\n- ".join(missing))

    # Denominators from per-scope CSVs
    y1, d1, _, _ = load_series(p_econ)
    y2, d2, _, _ = load_series(p_fin)
    y3, d3, n3, s3 = load_series(p_repec)

    # Consistent numerator decomposition from ID-level set operations
    ov_df = pd.read_csv(p_overlap).sort_values("year")
    n_both = ov_df["n_both"].to_numpy(dtype=float)
    n_econ_total = ov_df["n_econ_cf"].to_numpy(dtype=float)
    n_fin_total = ov_df["n_fin_cf"].to_numpy(dtype=float)

    # Recompute shares using consistent numerators
    s1 = np.where(d1 > 0, n_econ_total / d1 * 100.0, np.nan)
    s2 = np.where(d2 > 0, n_fin_total / d2 * 100.0, np.nan)

    # --- Plot ---
    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True)

    ax2_1 = plot_panel(axes[0], y1, d1, n_econ_total, s1,
                       "A. OpenAlex (Economics concept)", incomplete_from=2022,
                       overlap=n_both, overlap_label="Also tagged Finance")
    ax2_2 = plot_panel(axes[1], y2, d2, n_fin_total, s2,
                       "B. OpenAlex (Finance concept)", incomplete_from=2022,
                       overlap=n_both, overlap_label="Also tagged Economics")
    ax2_3 = plot_panel(axes[2], y3, d3, n3, s3,
                       "C. RePEc (Economics proxy)", incomplete_from=None,
                       numer_mode="line")

    nonzero_repec = int((n3 > 0).sum())
    max_repec = int(n3.max()) if len(n3) else 0
    axes[2].text(
        0.02, 0.92,
        f"Sparse signal: {nonzero_repec}/{len(n3)} years non-zero; max={max_repec}",
        transform=axes[2].transAxes, fontsize=8, color="grey", va="top",
    )

    for a in axes:
        a.set_ylabel("Count (log)")
        a.xaxis.set_major_locator(ticker.MultipleLocator(5))
        a.xaxis.set_minor_locator(ticker.MultipleLocator(1))
    axes[2].set_xlabel("Year")

    for a2 in [ax2_1, ax2_2, ax2_3]:
        a2.set_ylabel("Share (%)", color=C_SHARE)

    fig.suptitle(
        "Economics baseline vs Finance and RePEc checks",
        fontsize=13, y=0.995,
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.985))

    save_figure(fig, os.path.join(BASE_DIR, "content", "figures", "fig_robustness"),
                no_pdf=args.no_pdf)
    plt.close(fig)
    print("Done.")


if __name__ == "__main__":
    main()
