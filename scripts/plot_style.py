"""Shared style for Oeconomia submission figures.

All in-paper figures import this module for consistent grayscale styling,
serif fonts, and period annotations calibrated for 12.7 cm (5 inch) width.
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# --- Dimensions ---
FIGWIDTH = 120 / 25.4  # 120 mm = 4.724 inches
DPI = 300

# --- Grayscale palette ---
DARK = "#333333"
MED = "#777777"
LIGHT = "#BBBBBB"
FILL = "#DDDDDD"
WHITE = "#FFFFFF"

# --- Periods ---
PERIODS = [
    ("Before", 1990, 2006),
    ("Crystallisation", 2007, 2014),
    ("Disputes", 2015, 2025),
]

# Period break years (boundaries between acts). Derived from PERIODS above.
PERIOD_BREAKS = [2007, 2015]

INCOMPLETE_FROM = 2022  # OpenAlex indexing incomplete from this year

# --- rcParams for Oeconomia house style ---
RCPARAMS = {
    "font.family": "serif",
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
    "axes.linewidth": 0.5,
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.minor.width": 0.3,
    "ytick.minor.width": 0.3,
    "lines.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
}


def apply_style():
    """Apply Oeconomia rcParams globally."""
    mpl.rcParams.update(RCPARAMS)


def add_period_bands(ax, y_frac=0.97, fontsize=7):
    """Draw subtle vertical shading and labels for the three periods.

    Parameters
    ----------
    ax : matplotlib Axes
    y_frac : float
        Vertical position of labels as fraction of axes height.
    fontsize : float
        Font size for period labels.
    """
    colors = [FILL, "#EEEEEE", FILL]
    for (label, start, end), color in zip(PERIODS, colors):
        ax.axvspan(start - 0.5, end + 0.5, color=color, alpha=0.4,
                   zorder=0, linewidth=0)
        mid = (start + end) / 2
        ax.text(mid, y_frac, label, transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=fontsize, fontstyle="italic",
                color=MED)


def add_period_lines(ax, events=None):
    """Draw thin dashed vertical lines at period boundaries.

    Parameters
    ----------
    ax : matplotlib Axes
    events : dict, optional
        Mapping {year: label} for event annotations.
        Default: Bali 2007 and Paris 2015.
    """
    if events is None:
        events = {2007: "Bali 2007", 2015: "Paris 2015"}
    for year, label in events.items():
        ax.axvline(year - 0.5, color=MED, linewidth=0.5, linestyle="--",
                   zorder=1)
        ax.text(year - 0.3, 0.93, label, transform=ax.get_xaxis_transform(),
                ha="left", va="top", fontsize=7, color=DARK, rotation=90)
