"""Figure 4 (companion paper): community sizes before/after each zone.

The ticket asks for an alluvial / Sankey flow between Louvain community
structures before and after each validated zone.  Alluvial layouts are
fragile with unknown community counts, so this script renders the
robust fallback mentioned in the ticket: a grouped bar chart showing
community sizes on each side of each validated zone.

Reads ``tab_community_shifts.csv`` (or ``tab_community_shifts_{zone}.csv``
parts) from ``--tables-dir``.  Falls back to a stub plot annotated with
``TODO(t0064)`` when the file is missing, so the Make target still
succeeds on partial upstream data.

Expected schema:
    zone, side, community_id, size[, label]

Usage::

    uv run python scripts/plot_companion_community.py \\
        --output content/figures/fig_companion_community.png \\
        [--tables-dir path/to/tables]
"""

from __future__ import annotations

import argparse
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from _companion_plot_utils import (
    add_tables_dir_arg,
    companion_config,
    read_csv_or_none,
    save_companion_figure,
)
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_companion_community")
apply_style()


def _stub_frame() -> pd.DataFrame:
    rows = []
    for zone in ("zone 1 (stub)", "zone 2 (stub)"):
        for side in ("before", "after"):
            for cid in range(3):
                rows.append(
                    {
                        "zone": zone,
                        "side": side,
                        "community_id": cid,
                        "size": 40 + 12 * cid + (6 if side == "after" else 0),
                        "label": f"c{cid}",
                    }
                )
    return pd.DataFrame(rows)


def _load_shifts(tables_dir: str) -> tuple[pd.DataFrame, bool]:
    primary = os.path.join(tables_dir, "tab_community_shifts.csv")
    df = read_csv_or_none(primary)
    if df is not None and not df.empty:
        return df, False
    parts = []
    if os.path.isdir(tables_dir):
        for name in sorted(os.listdir(tables_dir)):
            if name.startswith("tab_community_shifts_") and name.endswith(".csv"):
                part = pd.read_csv(os.path.join(tables_dir, name))
                if "zone" not in part.columns:
                    part["zone"] = name[len("tab_community_shifts_") : -len(".csv")]
                parts.append(part)
    if parts:
        return pd.concat(parts, ignore_index=True), False
    log.warning(
        "tab_community_shifts.csv missing in %s; rendering stub (TODO t0064).",
        tables_dir,
    )
    return _stub_frame(), True


def main() -> None:
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    add_tables_dir_arg(parser)
    args = parser.parse_args(extra)

    cfg = companion_config()
    stub_tag = cfg.get("stub_figure_todo", "t0064")

    df, is_stub = _load_shifts(args.tables_dir)
    zones = sorted(df["zone"].unique())
    n_zones = max(1, len(zones))

    fig, axes = plt.subplots(
        1,
        n_zones,
        figsize=(FIGWIDTH, 3.2),
        sharey=True,
    )
    if n_zones == 1:
        axes = [axes]

    for ax, zone in zip(axes, zones):
        sub = df[df["zone"] == zone].copy()
        pivot = (
            sub.groupby(["community_id", "side"])["size"]
            .sum()
            .unstack("side")
            .fillna(0.0)
            .sort_index()
        )
        communities = list(pivot.index)
        x = np.arange(len(communities))
        width = 0.4

        before = pivot.get("before", pd.Series(0, index=communities))
        after = pivot.get("after", pd.Series(0, index=communities))

        ax.bar(x - width / 2, before, width, label="before", color=LIGHT)
        ax.bar(x + width / 2, after, width, label="after", color=DARK)
        ax.set_xticks(x)
        ax.set_xticklabels([f"c{int(c)}" for c in communities])
        ax.set_title(str(zone))
        ax.set_xlabel("Community")
    axes[0].set_ylabel("Size (documents)")
    axes[0].legend(frameon=False, fontsize=7)

    if is_stub:
        fig.suptitle(
            f"Community shifts — STUB (TODO {stub_tag})",
            fontsize=8,
            color="#B22222",
        )

    fig.tight_layout(rect=(0, 0, 1, 0.95 if is_stub else 1.0))
    save_companion_figure(fig, io_args.output, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
