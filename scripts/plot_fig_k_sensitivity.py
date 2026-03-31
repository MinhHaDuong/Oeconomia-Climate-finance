"""K-sensitivity figure: structural break persistence across cluster counts.

Reads:  tab_k_sensitivity.csv
Writes: fig_k_sensitivity.png (and .pdf if --pdf)

Flags: --pdf

Run compute_breakpoints.py --robustness first to generate tab_k_sensitivity.csv.

Usage:
    uv run python scripts/plot_fig_k_sensitivity.py --output content/figures/fig_k_sensitivity.png
"""

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd
from plot_style import COP_EVENTS
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, save_figure

log = get_logger("plot_fig_k_sensitivity")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

K_DEFAULT = 6


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(description="Plot k-sensitivity figure")
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    parser.add_argument("--k-sensitivity",
                        default=os.path.join(TABLES_DIR, "tab_k_sensitivity.csv"),
                        help="Path to tab_k_sensitivity.csv")
    args = parser.parse_args(extra)

    # --- Load data ---
    k_path = io_args.input[0] if io_args.input else args.k_sensitivity
    if not os.path.exists(k_path):
        raise FileNotFoundError(
            f"Missing {k_path}. Run: uv run python scripts/compute_breakpoints.py --k-sensitivity --output {k_path}"
        )
    k_df = pd.read_csv(k_path)
    k_values = [int(col.replace("js_k", "")) for col in k_df.columns if col.startswith("js_k")]

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(12, 5))
    k_colors = {4: "#E63946", 5: "#F4A261", 6: "#457B9D", 7: "#2A9D8F"}
    for k in k_values:
        col = f"js_k{k}"
        valid = k_df[["year", col]].dropna()
        ax.plot(valid["year"], valid[col], "-o", color=k_colors.get(k, "grey"), markersize=4,
                label=f"k={k}", alpha=0.8, linewidth=1.5 if k == K_DEFAULT else 1.0)

    for yr in COP_EVENTS.keys():
        if 2004 <= yr <= 2024:
            ax.axvline(yr, color="grey", linestyle="--", alpha=0.4, linewidth=0.8)

    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel("JS divergence (w=3)", fontsize=11)
    ax.set_title("K-sensitivity: do structural breaks persist across cluster counts?",
                 fontsize=12, pad=15)
    ax.legend(fontsize=9, framealpha=0.9)
    plt.tight_layout()

    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf)
    plt.close()
    log.info("Saved %s", io_args.output)


if __name__ == "__main__":
    main()
