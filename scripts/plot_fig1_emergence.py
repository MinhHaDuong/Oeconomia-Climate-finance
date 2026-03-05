#!/usr/bin/env python3
"""Plot Figure 1: Economics vs. "climate finance" in economics (1990–2025).

Three series on a single log-scale chart:
  - All economics publications — left axis, log, line
  - "Climate finance" in economics — left axis, log, bars
  - Share of economics (%) — right axis, linear, dashed line

Years 2022–2025 shown dotted/hatched to flag incomplete OpenAlex indexing.

Inputs:
  - $DATA/catalogs/openalex_econ_yearly.csv  (from count_openalex_econ_cf.py)

Outputs:
  - figures/fig1_emergence.png (+.pdf unless --no-pdf)

Usage:
    uv run python scripts/plot_fig1_emergence.py [--no-pdf]
"""

import argparse
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(__file__))
from utils import BASE_DIR, CATALOGS_DIR, save_figure
from plot_helpers import C_DENOM, C_NUMER, C_SHARE, load_series, plot_panel

# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Plot Figure 1: emergence")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
args = parser.parse_args()

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
os.makedirs(FIGURES_DIR, exist_ok=True)

INCOMPLETE_FROM = 2022

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
years, econ, cf, share_pct = load_series(
    os.path.join(CATALOGS_DIR, "openalex_econ_yearly.csv"))

print(f"OpenAlex econ: {int(econ.sum()):,} | CF-in-econ: {int(cf.sum()):,}")

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 5.5))

ax2 = plot_panel(ax, years, econ, cf, share_pct, incomplete_from=INCOMPLETE_FROM)

# -- Customize for main figure --
ax.set_ylabel("Publications per year (log scale)", fontsize=11)
ax2.set_ylabel("Share of economic publications\non climate finance (%)",
               fontsize=10, color=C_SHARE)
ax2.tick_params(axis="y", labelcolor=C_SHARE, labelsize=9)
ax2.spines["right"].set_color(C_SHARE)
ax2.spines["right"].set_alpha(0.5)

# Incompleteness label
ax.text(INCOMPLETE_FROM + 1.5, 0.90, "Incomplete\nindexing",
        transform=ax.get_xaxis_transform(),
        fontsize=8, color="grey", alpha=0.7, ha="center", va="top",
        fontstyle="italic")

# Title + subtitle
ax.set_title(
    'Emergence of "Climate finance" in the economic literature\n',
    fontsize=13, fontweight="bold", loc="left",
)
ax.text(0.0, 1.02,
        "Source: OpenAlex (articles + reviews / Economics), 1990\u20132025",
        transform=ax.transAxes, fontsize=9.5, color="grey", va="bottom")

ax.set_xlabel("Year", fontsize=11)
ax.xaxis.set_major_locator(ticker.MultipleLocator(5))
ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))

# Legend
legend_elements = [
    Line2D([0], [0], color=C_DENOM, lw=2.5, label="All economics"),
    Patch(facecolor=C_NUMER, alpha=0.85,
          label='"Climate finance" (title OR abstract)'),
    Line2D([0], [0], color=C_SHARE, lw=1.8, ls="--", marker="s", ms=3,
           label="Share (%, right axis)"),
]
ax.legend(handles=legend_elements, loc="center right", fontsize=9,
          framealpha=0.9, ncol=1, bbox_to_anchor=(0.62, 0.45))

plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, "fig1_emergence"), no_pdf=args.no_pdf)
plt.close()
print("Done.")
