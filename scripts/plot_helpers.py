"""Shared plotting helpers for Figure 1 and its appendix variants.

Provides:
- load_series(): load a yearly CSV into (years, denom, numer, share) arrays
- plot_panel(): denominator line + numerator bars + share curve on twin axes
"""

import numpy as np
import pandas as pd
import matplotlib.ticker as ticker


# -- Standard colors --
C_DENOM = "#E07B39"     # orange — denominator line
C_NUMER = "#4C72B0"     # blue — numerator bars
C_SHARE = "#8B0000"     # dark red — share curve
C_OVERLAP = "#2ca02c"   # green — overlap portion in stacked bars


def load_series(path):
    """Load a yearly CSV and return (years, denom, numer, share_pct) arrays.

    Expects columns: year, n_economics, n_climate_finance.
    """
    df = pd.read_csv(path).sort_values("year")
    years = df["year"].to_numpy()
    denom = df["n_economics"].to_numpy(dtype=float)
    numer = df["n_climate_finance"].to_numpy(dtype=float)
    share = np.where(denom > 0, numer / denom * 100.0, np.nan)
    return years, denom, numer, share


def plot_panel(ax, years, denom, numer, share, title=None, incomplete_from=None,
               overlap=None, overlap_label=None, numer_mode="bars"):
    """Plot a denominator line + numerator bars + share curve on ax.

    If overlap is provided, bars are stacked: overlap at bottom (green),
    remainder on top (blue). overlap is clipped to [0, numer].

    Returns the twin axes (ax2) for the share series.
    """
    ax2 = ax.twinx()

    # -- Incompleteness masks --
    if incomplete_from is None:
        complete = np.ones_like(years, dtype=bool)
        incomplete = np.zeros_like(years, dtype=bool)
        bridge = np.zeros_like(years, dtype=bool)
    else:
        complete = years < incomplete_from
        incomplete = years >= incomplete_from
        bridge = years == (incomplete_from - 1)
    inc_bridge = incomplete | bridge

    # -- Denominator line (left axis, log) --
    ax.plot(years[complete], denom[complete], color=C_DENOM, lw=2.0, zorder=2)
    if inc_bridge.any():
        ax.plot(years[inc_bridge], denom[inc_bridge],
                color=C_DENOM, lw=2.0, ls=":", alpha=0.45, zorder=2)

    # -- Numerator (left axis, log): bars by default, or line for sparse series --
    comp_mask = complete & (numer > 0)
    inc_mask = incomplete & (numer > 0)

    if numer_mode == "line":
        all_nonzero = numer > 0
        if all_nonzero.any():
            ax.plot(years[all_nonzero], numer[all_nonzero],
                    color=C_NUMER, lw=1.8, marker="o", ms=4, zorder=4)
            ax.vlines(years[all_nonzero], ymin=1, ymax=numer[all_nonzero],
                      color=C_NUMER, alpha=0.25, lw=1.0, zorder=3)
    elif overlap is not None:
        ov = np.clip(overlap, 0, numer)
        remainder = numer - ov

        # Complete years: stacked bars
        if comp_mask.any():
            ax.bar(years[comp_mask], ov[comp_mask],
                   color=C_OVERLAP, alpha=0.85, width=0.8, zorder=3,
                   label=overlap_label or "Both Econ & Finance")
            ax.bar(years[comp_mask], remainder[comp_mask], bottom=ov[comp_mask],
                   color=C_NUMER, alpha=0.85, width=0.8, zorder=3)
        # Incomplete years: stacked with hatch
        if inc_mask.any():
            ax.bar(years[inc_mask], ov[inc_mask],
                   color=C_OVERLAP, alpha=0.35, width=0.8, zorder=3,
                   hatch="///", edgecolor=C_OVERLAP, linewidth=0.5)
            ax.bar(years[inc_mask], remainder[inc_mask], bottom=ov[inc_mask],
                   color=C_NUMER, alpha=0.35, width=0.8, zorder=3,
                   hatch="///", edgecolor=C_NUMER, linewidth=0.5)
    else:
        ax.bar(years[comp_mask], numer[comp_mask],
               color=C_NUMER, alpha=0.85, width=0.8, zorder=3)
        if inc_mask.any():
            ax.bar(years[inc_mask], numer[inc_mask],
                   color=C_NUMER, alpha=0.35, width=0.8, zorder=3,
                   hatch="///", edgecolor=C_NUMER, linewidth=0.5)

    # -- Count labels (every 2 years to avoid clutter) --
    labeled = [yr for yr, n in zip(years, numer) if n > 0]
    for yr, n in zip(years, numer):
        if n > 0 and (yr % 2 == 0 or yr == labeled[-1]):
            ax.text(yr, n, f"{int(n)}", ha="center", va="bottom",
                    fontsize=6.5, color=C_NUMER, fontweight="bold", zorder=5)

    # -- Share curve (right axis, linear) --
    comp_share = complete & (numer > 0)
    inc_share = inc_bridge & (numer > 0)
    ax2.plot(years[comp_share], share[comp_share],
             color=C_SHARE, lw=1.4, ls="--", marker="s", ms=2.5, alpha=0.85)
    if inc_share.any():
        ax2.plot(years[inc_share], share[inc_share],
                 color=C_SHARE, lw=1.4, ls=":", marker="s", ms=2.5, alpha=0.4)

    # -- Incompleteness vertical line --
    if incomplete_from is not None:
        ax.axvline(incomplete_from - 0.5, color="grey", ls="--", lw=0.9, alpha=0.5)

    # -- Axis formatting --
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(
        ticker.FuncFormatter(lambda x, _: f"{int(x):,}" if x >= 1 else ""))
    ax2.yaxis.set_major_formatter(
        ticker.FuncFormatter(lambda x, _: f"{x:.3f}%"))
    ax.grid(True, which="both", alpha=0.25)
    ax.set_xlim(1989, 2026)

    if title:
        ax.set_title(title, fontsize=10.5, loc="left", fontweight="bold")

    return ax2
