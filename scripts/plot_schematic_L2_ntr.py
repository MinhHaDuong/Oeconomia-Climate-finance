"""Schematic figure: Novelty, Transience, Resonance (Barron et al. NTR method).

Illustrates the principle of NTR using a conceptual timeline diagram
and a synthetic term-frequency trace.  No corpus data required.

Usage::

    uv run python scripts/plot_schematic_L2_ntr.py \\
        --output content/figures/schematic_L2_ntr.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, FILL, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_L2_ntr")
apply_style()

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #
FOCAL_YEAR = 2005
YEAR_MIN = 1998
YEAR_MAX = 2012
PAST_START = FOCAL_YEAR - 3
PAST_END = FOCAL_YEAR - 1
FUTURE_START = FOCAL_YEAR + 1
FUTURE_END = FOCAL_YEAR + 3

# Synthetic term frequency: a Gaussian spike centered on the focal year.
_years = np.arange(YEAR_MIN, YEAR_MAX + 1)
_signal = np.exp(-0.5 * ((_years - FOCAL_YEAR) / 1.5) ** 2)
# High-resonance version: still elevated after focal year
_high_res = _signal.copy()
_high_res[_years > FOCAL_YEAR] *= np.exp(
    -0.3 * (_years[_years > FOCAL_YEAR] - FOCAL_YEAR)
)
# Low-resonance version: drops fast after focal year
_low_res = _signal.copy()
_low_res[_years > FOCAL_YEAR] *= np.exp(
    -1.8 * (_years[_years > FOCAL_YEAR] - FOCAL_YEAR)
)
# Scale to [0, 1]
_high_res /= _high_res.max()
_low_res /= _low_res.max()


def _bar_color(year: int) -> str:
    """Return bar color: dark for focal, medium for windows, light for rest."""
    if year == FOCAL_YEAR:
        return DARK
    if PAST_START <= year <= PAST_END:
        return "#4477AA"  # blue-ish for past window
    if FUTURE_START <= year <= FUTURE_END:
        return "#CC4444"  # red-ish for future window
    return LIGHT


def main() -> None:
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    fig, (ax_top, ax_bot) = plt.subplots(
        2,
        1,
        figsize=(FIGWIDTH, 4.8),
        gridspec_kw={"height_ratios": [1.1, 1.8]},
    )
    fig.subplots_adjust(hspace=0.55)

    # ------------------------------------------------------------------ #
    # Top panel: timeline with arrows                                     #
    # ------------------------------------------------------------------ #
    ax = ax_top
    ax.set_xlim(YEAR_MIN - 0.5, YEAR_MAX + 1.5)
    ax.set_ylim(-0.05, 1.05)
    ax.axis("off")

    # Horizontal timeline
    ax.annotate(
        "",
        xy=(YEAR_MAX + 1.2, 0.5),
        xytext=(YEAR_MIN - 0.3, 0.5),
        arrowprops=dict(arrowstyle="-|>", color=DARK, lw=0.8),
    )
    # Year tick marks
    for yr in range(YEAR_MIN, YEAR_MAX + 1):
        ax.plot([yr, yr], [0.47, 0.53], color=DARK, lw=0.5)
    # Year labels (every 2 years)
    for yr in range(YEAR_MIN, YEAR_MAX + 1, 2):
        ax.text(yr, 0.40, str(yr), ha="center", va="top", fontsize=6.5, color=MED)

    # Focal-year marker
    ax.plot([FOCAL_YEAR], [0.5], "o", color=DARK, ms=6, zorder=5)
    ax.text(
        FOCAL_YEAR,
        0.66,
        f"focal year t={FOCAL_YEAR}",
        ha="center",
        va="bottom",
        fontsize=7,
        color=DARK,
        fontweight="bold",
    )

    # Past arrow (left, blue)
    arrow_y = 0.78
    ax.annotate(
        "",
        xy=(PAST_START - 0.3, arrow_y),
        xytext=(FOCAL_YEAR - 0.1, arrow_y),
        arrowprops=dict(arrowstyle="<|-|>", color="#4477AA", lw=1.2),
    )
    ax.text(
        (PAST_START + FOCAL_YEAR) / 2 - 0.5,
        arrow_y + 0.03,
        "Past window (t−3 to t−1)\nKL backward → Novelty",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color="#4477AA",
    )

    # Future arrow (right, red)
    ax.annotate(
        "",
        xy=(FUTURE_END + 0.3, arrow_y),
        xytext=(FOCAL_YEAR + 0.1, arrow_y),
        arrowprops=dict(arrowstyle="<|-|>", color="#CC4444", lw=1.2),
    )
    ax.text(
        (FOCAL_YEAR + FUTURE_END) / 2 + 0.5,
        arrow_y + 0.03,
        "Future window (t+1 to t+3)\nKL forward → Transience",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color="#CC4444",
    )

    # Resonance text box
    ax.text(
        (YEAR_MIN + YEAR_MAX) / 2,
        0.08,
        "Resonance = Novelty − Transience   (innovations that stuck)",
        ha="center",
        va="bottom",
        fontsize=7,
        color=DARK,
        style="italic",
        bbox=dict(boxstyle="round,pad=0.3", fc="#F0F0F0", ec=LIGHT, lw=0.6),
    )

    ax.set_title(
        "NTR: did the year's vocabulary stick around?", fontsize=9, color=DARK, pad=4
    )

    # ------------------------------------------------------------------ #
    # Bottom panel: bar chart comparing high vs low resonance             #
    # ------------------------------------------------------------------ #
    ax2 = ax_bot
    width = 0.38

    bars_high = ax2.bar(
        _years - width / 2,
        _high_res,
        width=width,
        color="#4477AA",
        alpha=0.75,
        label="High resonance (term persists)",
    )
    bars_low = ax2.bar(
        _years + width / 2,
        _low_res,
        width=width,
        color="#CC4444",
        alpha=0.75,
        label="Low resonance (term fades)",
    )

    # Shade focal year
    ax2.axvspan(FOCAL_YEAR - 0.5, FOCAL_YEAR + 0.5, color=FILL, alpha=0.5, zorder=0)
    ax2.axvline(FOCAL_YEAR, color=DARK, lw=0.8, ls="--", zorder=2)
    ax2.text(
        FOCAL_YEAR,
        1.03,
        "t",
        ha="center",
        va="bottom",
        fontsize=7,
        color=DARK,
        fontweight="bold",
    )

    # Past / future window shading
    ax2.axvspan(PAST_START - 0.5, PAST_END + 0.5, color="#4477AA", alpha=0.08, zorder=0)
    ax2.axvspan(
        FUTURE_START - 0.5, FUTURE_END + 0.5, color="#CC4444", alpha=0.08, zorder=0
    )

    ax2.set_xlabel("Year")
    ax2.set_ylabel("Relative term frequency")
    ax2.set_xlim(YEAR_MIN - 0.7, YEAR_MAX + 0.7)
    ax2.set_xticks(range(YEAR_MIN, YEAR_MAX + 1, 2))
    ax2.set_ylim(0, 1.15)
    ax2.legend(loc="upper right", fontsize=6.5, frameon=False)
    ax2.set_title(
        "Conceptual example: same spike, different resonance",
        fontsize=8,
        color=MED,
        pad=3,
    )

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved schematic_L2_ntr to %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
