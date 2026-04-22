"""Figure 1 (companion paper): Z-score time series at the lead window.

Renders four distance-method Z-score curves (S2 Energy, L1 JS,
G9 Community, G2 Spectral) on a primary axis plus the two C2ST AUC
traces (embedding, lexical) on a twin axis, for the lead window
(``companion.lead_window`` in ``config/analysis.yaml``, default 3).

Inputs (all in ``--tables-dir``, default ``content/tables/``):
  tab_summary_S2_energy.csv, tab_summary_L1.csv,
  tab_summary_G9_community.csv, tab_summary_G2_spectral.csv
  tab_div_C2ST_embedding.csv, tab_div_C2ST_lexical.csv

Output: one PNG at the path given by ``--output`` (Make controls it).

Usage::

    uv run python scripts/plot_companion_zseries.py \\
        --output content/figures/fig_companion_zseries.png \\
        [--tables-dir path/to/tables]

The script degrades gracefully: missing input tables simply omit the
corresponding curve; the figure is still produced so the Make target
succeeds on partial data.
"""

import argparse
import sys

import matplotlib.pyplot as plt
from _companion_plot_utils import (
    add_tables_dir_arg,
    companion_config,
    load_c2st_tables,
    load_summary_tables,
    save_companion_figure,
    window_rows,
)
from plot_style import DPI, FIGWIDTH, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_companion_zseries")
apply_style()


def main() -> None:
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    add_tables_dir_arg(parser)
    args = parser.parse_args(extra)

    cfg = companion_config()
    window = int(cfg["lead_window"])
    z_thr = float(cfg["z_threshold"])
    y0, y1 = int(cfg["year_min"]), int(cfg["year_max"])
    colors = cfg["colors"]["series"]
    methods_labels = cfg["methods"]

    summaries = load_summary_tables(args.tables_dir)
    c2sts = load_c2st_tables(args.tables_dir)

    if not summaries and not c2sts:
        log.warning(
            "No input tables found in %s; rendering empty figure.", args.tables_dir
        )

    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.8))

    # Primary axis — Z-scores for distance methods.
    ax.axhspan(
        -z_thr,
        z_thr,
        color="#E8E8E8",
        alpha=0.6,
        zorder=0,
        label=f"|Z| < {z_thr:g} (null 95%)",
    )
    ax.axhline(z_thr, color=MED, linewidth=0.6, linestyle="--", zorder=1)
    ax.axhline(-z_thr, color=MED, linewidth=0.6, linestyle="--", zorder=1)

    max_abs_z = z_thr
    for method, df in summaries.items():
        sub = window_rows(df, window).sort_values("year")
        if sub.empty:
            continue
        color = colors.get(method, None)
        label = methods_labels.get(method, method)

        # Subsampling ribbon: draw before the line so the line sits on top.
        has_ribbon = (
            "z_trim_lo" in sub.columns
            and "z_trim_hi" in sub.columns
            and sub["z_trim_lo"].notna().any()
        )
        if has_ribbon:
            ribbon = sub.dropna(subset=["z_trim_lo", "z_trim_hi"])
            ax.fill_between(
                ribbon["year"],
                ribbon["z_trim_lo"],
                ribbon["z_trim_hi"],
                color=color,
                alpha=0.2,
                linewidth=0,
                zorder=2,
            )

        ax.plot(
            sub["year"],
            sub["z_score"],
            label=label,
            color=color,
            linewidth=1.2,
            zorder=3,
        )
        mx = sub["z_score"].abs().max()
        if mx and mx > max_abs_z:
            max_abs_z = float(mx)

    ax.set_xlabel("Year")
    ax.set_ylabel(f"Z-score (window = {window})")
    ax.set_xlim(y0, y1)
    y_pad = max_abs_z * 1.15
    ax.set_ylim(-y_pad, y_pad)

    # Twin axis — C2ST AUCs.
    ax2 = ax.twinx()
    ax2.set_ylabel("C2ST AUC")
    ax2.set_ylim(0.5, 1.0)
    ax2.axhline(cfg["auc_chance"], color=MED, linewidth=0.4, linestyle=":", zorder=1)
    for key, df in c2sts.items():
        sub = window_rows(df, window).sort_values("year")
        if sub.empty:
            continue
        ax2.plot(
            sub["year"],
            sub["value"],
            label=methods_labels.get(key, key),
            color=colors.get(key, None),
            linewidth=1.0,
            linestyle="-.",
            zorder=2,
        )

    # Combined legend beneath the axes.
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    if h1 or h2:
        fig.legend(
            h1 + h2,
            l1 + l2,
            loc="lower center",
            ncol=4,
            frameon=False,
            bbox_to_anchor=(0.5, -0.02),
            fontsize=6.5,
        )

    fig.tight_layout()
    save_companion_figure(fig, io_args.output, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
